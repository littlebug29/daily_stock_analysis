#!/usr/bin/env python3
"""Report Chinese (CJK) text in code comments and docstrings.

Scans git-tracked Python, shell, PowerShell, YAML, TS/JS and CSS files and
lists every file that has CJK ideographs inside a comment or a docstring,
with a per-file count of affected lines.

Only comments and docstrings are inspected. String literals (Python strings
and f-strings, JS/TS strings and template literals, shell/YAML quoted values,
YAML block scalars) are runtime data and are never reported.

Usage:
    python scripts/check_cjk_comments.py                 # whole repository
    python scripts/check_cjk_comments.py src tests/foo.py  # selected paths
    python scripts/check_cjk_comments.py --show-lines src  # include each line
    python scripts/check_cjk_comments.py --fail-on-findings

Exit codes: 0 = report-only (default) or no findings, 1 = findings with
``--fail-on-findings``, 2 = usage, git or allowlist error.

See the "CJK Comment Checker" section of docs/CONTRIBUTING_EN.md (and its
counterpart in docs/CONTRIBUTING.md) for the allowlist format.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import io
import re
import subprocess
import sys
import tokenize
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALLOWLIST = ROOT / "scripts" / "cjk_comment_allowlist.txt"

# CJK Unified Ideographs, Extension A, Compatibility Ideographs and the
# supplementary-plane extensions. Punctuation alone is not reported.
CJK_RE = re.compile(
    "[㐀-䶿一-鿿豈-﫿\U00020000-\U0002fa1f]"
)

# A comment piece: (1-based line number, text of the comment on that line).
Piece = Tuple[int, str]
Scanner = Callable[[str], List[Piece]]


class CheckerError(Exception):
    """Fatal configuration problem (bad allowlist, git failure)."""


@dataclass(frozen=True)
class Finding:
    """One source line with CJK text inside a comment or docstring."""

    path: str
    line: int
    text: str


@dataclass(frozen=True)
class AllowEntry:
    """Allowlist entry: a path glob, an optional inclusive line range and a reason."""

    pattern: str
    start: Optional[int]
    end: Optional[int]
    reason: str

    def matches(self, path: str, line: int) -> bool:
        if not fnmatch.fnmatchcase(path, self.pattern):
            return False
        if self.start is None:
            return True
        return self.start <= line <= self.end


@dataclass
class ScanResult:
    """Outcome of scanning a set of tracked files."""

    reported: List[Finding]
    allowed: List[Finding]
    scanned: int
    unmatched_paths: List[str]


@dataclass
class TrackedFiles:
    """Supported tracked files under the requested paths."""

    files: List[str]
    unmatched_paths: List[str]  # requested paths that match no tracked file


@dataclass
class _FolderTotal:
    files: int = 0
    lines: int = 0


def has_cjk(text: str) -> bool:
    """Return True if ``text`` contains at least one CJK ideograph."""
    return CJK_RE.search(text) is not None


def _split_pieces(text: str, first_line: int) -> List[Piece]:
    return [(first_line + k, part) for k, part in enumerate(text.split("\n"))]


# ---------------------------------------------------------------------------
# Python: tokenize for comments, ast for docstrings
# ---------------------------------------------------------------------------

def scan_python(source: str) -> List[Piece]:
    """Return COMMENT tokens and module/class/function docstring lines."""
    pieces: List[Piece] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                pieces.append((tok.start[0], tok.string))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass

    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return pieces

    lines = source.splitlines()
    doc_owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, doc_owners) or not node.body:
            continue
        first = node.body[0]
        if not (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            continue
        value = first.value
        for lineno in range(value.lineno, (value.end_lineno or value.lineno) + 1):
            if lineno > len(lines):
                break
            raw = lines[lineno - 1].encode("utf-8")
            # ast column offsets are UTF-8 byte offsets.
            start = value.col_offset if lineno == value.lineno else 0
            end = value.end_col_offset if lineno == value.end_lineno else len(raw)
            pieces.append((lineno, raw[start:end].decode("utf-8", "replace")))
    return pieces


# ---------------------------------------------------------------------------
# JS / TS / CSS: small C-style lexer
# ---------------------------------------------------------------------------

_REGEX_PREFIX_CHARS = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_PREFIX_WORDS = {
    "return", "typeof", "case", "do", "else", "in", "of", "new", "delete",
    "void", "throw", "yield", "await", "instanceof",
}


# Token kind recorded after a string, template or regex literal.
_LITERAL = "<literal>"
# Token kind recorded for a property name such as ``foo.return``.
_PROPERTY = "<property>"
# JSX element or attribute name after "<".
_JSX_NAME_RE = re.compile(r"[A-Za-z_$][\w$.:-]*")
# "<T," or "<T extends" after the name is a TSX generic, not an element.
_TSX_GENERIC_RE = re.compile(r"\s*(?:,|extends\b)")


class _CLikeLexer:
    """Tracks code, string, template, regex and comment state for JS/TS/CSS.

    ``js=False`` gives the CSS subset: only ``/* */`` comments and quoted strings.
    ``jsx=True`` skips JSX elements: their text is runtime content, while
    comments inside ``{...}`` expressions and between attributes still count.
    """

    def __init__(self, source: str, js: bool, jsx: bool = False) -> None:
        self.src = source
        self.n = len(source)
        self.js = js
        self.jsx = jsx
        self.i = 0
        self.line = 1
        self.pieces: List[Piece] = []
        # Last significant token, used to tell a regex literal from division.
        self.prev = ""

    def run(self) -> List[Piece]:
        self._code(stop_at_brace=False)
        return self.pieces

    def _comment(self, start: int, end: int) -> None:
        self.pieces.extend(_split_pieces(self.src[start:end], self.line))
        self.line += self.src.count("\n", start, end)
        self.i = end

    def _code(self, stop_at_brace: bool) -> None:
        src, depth = self.src, 0
        while self.i < self.n:
            c = src[self.i]
            if c == "\n":
                self.line += 1
                self.i += 1
                continue
            if c in " \t\r\f\v":
                self.i += 1
                continue
            two = src[self.i:self.i + 2]
            if self.js and two == "//":
                end = src.find("\n", self.i)
                self._comment(self.i, self.n if end == -1 else end)
                continue
            if two == "/*":
                end = src.find("*/", self.i + 2)
                self._comment(self.i, self.n if end == -1 else end + 2)
                continue
            if c in "\"'":
                self._string(c)
                self.prev = _LITERAL
                continue
            if self.js and c == "`":
                self._template()
                self.prev = _LITERAL
                continue
            if c == "<" and self.jsx and self._regex_allowed() and self._jsx_element():
                self.prev = _LITERAL
                continue
            if self.js and c == "/" and self._regex_allowed():
                self._regex()
                self.prev = _LITERAL
                continue
            if c.isalnum() or c in "_$" or ord(c) > 127:
                start = self.i
                while self.i < self.n and (
                    src[self.i].isalnum() or src[self.i] in "_$" or ord(src[self.i]) > 127
                ):
                    self.i += 1
                # A keyword used as a property name is an operand, not a keyword.
                self.prev = _PROPERTY if self.prev == "." else src[start:self.i]
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                if stop_at_brace and depth == 0:
                    self.i += 1
                    return
                depth -= 1
            self.prev = c
            self.i += 1

    def _jsx_element(self) -> bool:
        """Skip a JSX element at "<"; return False, consuming nothing, if it is not one."""
        start, start_line, start_pieces = self.i, self.line, len(self.pieces)
        if self.src[self.i + 1:self.i + 2] == ">":
            self.i += 2  # fragment <>
        else:
            name = _JSX_NAME_RE.match(self.src, self.i + 1)
            if not name or _TSX_GENERIC_RE.match(self.src, name.end()):
                return False
            self.i = name.end()
            self_closing = self._jsx_tag_rest()
            if self_closing is None:
                self.i, self.line = start, start_line
                del self.pieces[start_pieces:]
                return False
            if self_closing:
                return True
        self._jsx_children()
        return True

    def _jsx_tag_rest(self) -> Optional[bool]:
        """Skip attributes up to ">" (False) or "/>" (True); None if not a tag."""
        src = self.src
        while self.i < self.n:
            c = src[self.i]
            two = src[self.i:self.i + 2]
            if c == "\n":
                self.line += 1
                self.i += 1
            elif c.isspace() or c == "=":
                self.i += 1
            elif two == "/>":
                self.i += 2
                return True
            elif c == ">":
                self.i += 1
                return False
            elif two == "/*":
                end = src.find("*/", self.i + 2)
                self._comment(self.i, self.n if end == -1 else end + 2)
            elif two == "//":
                end = src.find("\n", self.i)
                self._comment(self.i, self.n if end == -1 else end)
            elif c in "\"'":
                # JSX attribute strings have no escapes.
                end = src.find(c, self.i + 1)
                if end == -1:
                    return None
                self.line += src.count("\n", self.i, end)
                self.i = end + 1
            elif c == "{":
                self._jsx_expression()
            else:
                attr = _JSX_NAME_RE.match(src, self.i)
                if not attr:
                    return None
                self.i = attr.end()
        return None

    def _jsx_children(self) -> None:
        """Skip JSX text and child elements up to and including the closing tag."""
        src = self.src
        while self.i < self.n:
            c = src[self.i]
            if c == "\n":
                self.line += 1
            elif c == "{":
                self._jsx_expression()
                continue
            elif c == "<":
                if src[self.i + 1:self.i + 2] == "/":
                    end = src.find(">", self.i)
                    self.i = self.n if end == -1 else end + 1
                    return
                if self._jsx_element():
                    continue
            self.i += 1

    def _jsx_expression(self) -> None:
        """Lex a ``{...}`` expression inside JSX as code."""
        self.i += 1
        self.prev = "("
        self._code(stop_at_brace=True)

    def _skip_escape(self) -> None:
        """Skip a backslash escape, counting an escaped newline."""
        if self.src[self.i + 1:self.i + 2] == "\n":
            self.line += 1
        self.i += 2

    def _regex_allowed(self) -> bool:
        p = self.prev
        if p == "<":
            # JSX closing tag such as </div>.
            return False
        return p == "" or p in _REGEX_PREFIX_CHARS or p in _REGEX_PREFIX_WORDS

    def _string(self, quote: str) -> None:
        self.i += 1
        while self.i < self.n:
            c = self.src[self.i]
            if c == "\\":
                self._skip_escape()
                continue
            if c == quote:
                self.i += 1
                return
            if c == "\n":
                # Unterminated string.
                return
            self.i += 1

    def _template(self) -> None:
        src = self.src
        self.i += 1
        while self.i < self.n:
            c = src[self.i]
            if c == "\\":
                self._skip_escape()
                continue
            if c == "`":
                self.i += 1
                return
            if c == "\n":
                self.line += 1
            if src[self.i:self.i + 2] == "${":
                self.i += 2
                self.prev = "("
                self._code(stop_at_brace=True)
                continue
            self.i += 1

    def _regex(self) -> None:
        src, i, in_class = self.src, self.i + 1, False
        while i < self.n:
            c = src[i]
            if c == "\\":
                i += 2
                continue
            if c == "\n":
                # Not a regex after all: treat the slash as an operator.
                self.i += 1
                return
            if c == "[":
                in_class = True
            elif c == "]":
                in_class = False
            elif c == "/" and not in_class:
                i += 1
                while i < self.n and (src[i].isalnum() or src[i] == "_"):
                    i += 1
                self.i = i
                return
            i += 1
        self.i += 1


def scan_js(source: str) -> List[Piece]:
    """Return comment pieces from TSX/JS/JSX/MJS/CJS source (JSX allowed)."""
    return _CLikeLexer(source, js=True, jsx=True).run()


def scan_ts(source: str) -> List[Piece]:
    """Return comment pieces from .ts source, where ``<T>x`` is a type assertion."""
    return _CLikeLexer(source, js=True).run()


def scan_css(source: str) -> List[Piece]:
    """Return ``/* */`` comment pieces from CSS source."""
    return _CLikeLexer(source, js=False).run()


# ---------------------------------------------------------------------------
# Shell and PowerShell
# ---------------------------------------------------------------------------

_HEREDOC_RE = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_HASH_WORD_START = set(" \t;&|()")
_PS_HASH_WORD_START = _HASH_WORD_START | set("{}")


def scan_shell(source: str) -> List[Piece]:
    """Return ``#`` comments outside quotes and heredoc bodies."""
    pieces: List[Piece] = []
    quote = ""  # open quote ("'", '"' or "$'"), carried across lines
    heredocs: List[Tuple[str, bool]] = []
    active_heredoc: Optional[Tuple[str, bool]] = None
    for idx, line in enumerate(source.split("\n")):
        lineno = idx + 1
        if active_heredoc is not None:
            term, strip_tabs = active_heredoc
            if (line.lstrip("\t") if strip_tabs else line).rstrip("\r") == term:
                active_heredoc = heredocs.pop(0) if heredocs else None
            continue
        i, n = 0, len(line)
        while i < n:
            c = line[i]
            if quote == "'":
                if c == "'":
                    quote = ""
                i += 1
                continue
            if quote == "$'":
                # ANSI-C quoting allows backslash escapes such as \'.
                if c == "\\":
                    i += 2
                    continue
                if c == "'":
                    quote = ""
                i += 1
                continue
            if quote == '"':
                if c == "\\":
                    i += 2
                    continue
                if c == '"':
                    quote = ""
                i += 1
                continue
            if c == "\\":
                i += 2
                continue
            if c == "$" and line[i + 1:i + 2] == "'":
                quote = "$'"
                i += 2
                continue
            if c in "'\"":
                quote = c
                i += 1
                continue
            if c == "#" and (i == 0 or line[i - 1] in _HASH_WORD_START):
                pieces.append((lineno, line[i:]))
                break
            if line.startswith("<<", i) and not line.startswith("<<<", i):
                match = _HEREDOC_RE.match(line, i)
                if match:
                    heredocs.append((match.group(3), match.group(1) == "-"))
                    i = match.end()
                    continue
            i += 1
        if heredocs and active_heredoc is None:
            active_heredoc = heredocs.pop(0)
    return pieces


def scan_powershell(source: str) -> List[Piece]:
    """Return ``#`` and ``<# #>`` comments outside strings and here-strings."""
    pieces: List[Piece] = []
    state = ""  # "", "'", '"', "block", "@'", '@"'
    for idx, line in enumerate(source.split("\n")):
        lineno = idx + 1
        if state in ("@'", '@"'):
            if line.startswith(state[1] + "@"):
                state = ""
            continue
        i, n = 0, len(line)
        while i < n:
            c = line[i]
            if state == "block":
                end = line.find("#>", i)
                stop = n if end == -1 else end + 2
                pieces.append((lineno, line[i:stop]))
                i = stop
                if end != -1:
                    state = ""
                continue
            if state == "'":
                if c == "'":
                    state = ""
                i += 1
                continue
            if state == '"':
                if c == "`":
                    i += 2
                    continue
                if c == '"':
                    state = ""
                i += 1
                continue
            if c == "@" and line[i + 1:i + 2] in ("'", '"') and not line[i + 2:].strip():
                state = "@" + line[i + 1]
                break
            if line.startswith("<#", i):
                state = "block"
                continue
            if c in "'\"":
                state = c
                i += 1
                continue
            if c == "`":
                i += 2
                continue
            if c == "#" and (i == 0 or line[i - 1] in _PS_HASH_WORD_START):
                pieces.append((lineno, line[i:]))
                break
            i += 1
    return pieces


# ---------------------------------------------------------------------------
# YAML
# ---------------------------------------------------------------------------

_YAML_BLOCK_RE = re.compile(
    r"^(?P<indent>\s*)(?:(?P<dash>-)\s+)?(?:(?P<key>[\w.\-\"' ]+?)\s*:\s+)?"
    r"[|>][+\-0-9]*\s*$"
)
_YAML_QUOTE_PREFIX = set(":-[{,?")
# Block scalar keys whose content is code that has its own comments.
_YAML_CODE_KEYS = {"run": scan_shell, "script": scan_js}


def _yaml_line(line: str, quote: str) -> Tuple[Optional[int], str]:
    """Return (comment start column or None, quote state after the line)."""
    i, n, last = 0, len(line), ""
    while i < n:
        c = line[i]
        if quote == '"':
            if c == "\\":
                i += 2
                continue
            if c == '"':
                quote = ""
            i += 1
            continue
        if quote == "'":
            if c == "'":
                if line[i + 1:i + 2] == "'":
                    i += 2
                    continue
                quote = ""
            i += 1
            continue
        if c in "'\"" and (last == "" or last in _YAML_QUOTE_PREFIX):
            quote = c
            i += 1
            continue
        if c == "#" and (i == 0 or line[i - 1] in " \t"):
            return i, quote
        if c not in " \t":
            last = c
        i += 1
    return None, quote


def scan_yaml(source: str) -> List[Piece]:
    """Return YAML ``#`` comments, plus comments inside ``run``/``script`` blocks.

    Other block scalars are text data and are skipped. Code embedded inside a
    ``run`` block in another language (``python - <<EOF``, ``python -c``) is
    treated as shell data and is not inspected.
    """
    pieces: List[Piece] = []
    lines = source.split("\n")
    quote = ""
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        col, quote = _yaml_line(line, quote)
        head = line if col is None else line[:col]
        if col is not None:
            pieces.append((idx + 1, line[col:]))
        block = None if quote else _YAML_BLOCK_RE.match(head.rstrip())
        idx += 1
        if not block:
            continue
        # Content must be indented deeper than the key (or the "-" item).
        if block.group("key"):
            parent = block.start("key")
        elif block.group("dash"):
            parent = block.start("dash")
        else:
            parent = len(block.group("indent"))
        body_start = idx
        while idx < len(lines):
            body = lines[idx]
            if body.strip() and len(body) - len(body.lstrip(" ")) <= parent:
                break
            idx += 1
        key = (block.group("key") or "").strip().strip("'\"")
        scanner = _YAML_CODE_KEYS.get(key)
        if scanner is None:
            # Plain block scalar: text data, never comments.
            continue
        content = "\n".join(lines[body_start:idx])
        for lineno, text in scanner(content):
            pieces.append((lineno + body_start, text))
    return pieces


# ---------------------------------------------------------------------------
# File collection and reporting
# ---------------------------------------------------------------------------

_SCANNERS = {
    ".py": scan_python,
    ".sh": scan_shell,
    ".bash": scan_shell,
    ".ps1": scan_powershell,
    ".psm1": scan_powershell,
    ".yml": scan_yaml,
    ".yaml": scan_yaml,
    ".ts": scan_ts,
    ".tsx": scan_js,
    ".js": scan_js,
    ".jsx": scan_js,
    ".mjs": scan_js,
    ".cjs": scan_js,
    ".css": scan_css,
}


def scanner_for(path: str) -> Optional[Scanner]:
    """Return the scanner for ``path``'s extension, or None if unsupported."""
    return _SCANNERS.get(PurePosixPath(path).suffix.lower())


def scan_source(path: str, source: str) -> List[Finding]:
    """Return one finding per line of ``source`` with CJK in a comment/docstring."""
    scanner = scanner_for(path)
    if scanner is None:
        return []
    by_line = {}
    for lineno, text in scanner(source):
        if has_cjk(text) and lineno not in by_line:
            by_line[lineno] = text.strip()
    return [Finding(path, line, by_line[line]) for line in sorted(by_line)]


def load_allowlist(path: Path) -> List[AllowEntry]:
    """Parse ``<glob>[:<line>[-<line>]] | <reason>`` entries."""
    if not path.exists():
        return []
    entries: List[AllowEntry] = []
    for num, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        target, sep, reason = line.partition("|")
        target, reason = target.strip(), reason.strip()
        if not sep or not target or not reason:
            raise CheckerError(
                f"{path}:{num}: expected '<path-glob>[:<line>[-<line>]] | <reason>'"
            )
        start = end = None
        match = re.fullmatch(r"(.+):(\d+)(?:-(\d+))?", target)
        if match:
            target = match.group(1)
            start = int(match.group(2))
            end = int(match.group(3) or start)
            if end < start:
                raise CheckerError(f"{path}:{num}: line range end is before start")
        entries.append(AllowEntry(target, start, end, reason))
    return entries


def list_tracked_files(root: Path, paths: Sequence[str]) -> TrackedFiles:
    """List supported tracked files under ``paths`` (default: the whole repository)."""
    pathspecs = []
    for raw in paths:
        candidate = Path(raw)
        absolute = candidate if candidate.is_absolute() else Path.cwd() / candidate
        try:
            pathspecs.append(absolute.resolve().relative_to(root.resolve()).as_posix())
        except ValueError:
            raise CheckerError(f"path is outside the repository: {raw}")
    cmd = ["git", "-C", str(root), "ls-files", "-z", "--"]
    cmd += [spec or "." for spec in pathspecs]
    try:
        out = subprocess.run(cmd, check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CheckerError(f"git ls-files failed: {exc}")
    tracked = [p for p in out.decode("utf-8").split("\0") if p]
    unmatched = [
        raw
        for raw, spec in zip(paths, pathspecs)
        if spec and not any(p == spec or p.startswith(spec + "/") for p in tracked)
    ]
    files = sorted(p for p in tracked if scanner_for(p) and (root / p).is_file())
    return TrackedFiles(files, unmatched)


def collect(root: Path, paths: Sequence[str], allowlist: Sequence[AllowEntry]) -> ScanResult:
    """Scan tracked files under ``paths`` and split findings by the allowlist."""
    reported: List[Finding] = []
    allowed: List[Finding] = []
    tracked = list_tracked_files(root, paths)
    for rel in tracked.files:
        source = (root / rel).read_bytes().decode("utf-8", "replace")
        for finding in scan_source(rel, source):
            if any(entry.matches(rel, finding.line) for entry in allowlist):
                allowed.append(finding)
            else:
                reported.append(finding)
    return ScanResult(reported, allowed, len(tracked.files), tracked.unmatched_paths)


def _top_level(path: str) -> str:
    parts = PurePosixPath(path).parts
    return parts[0] if len(parts) > 1 else "(root)"


def format_report(result: ScanResult, show_lines: bool) -> str:
    """Render per-file counts, a per-folder summary and totals."""
    per_file = defaultdict(list)
    for finding in result.reported:
        per_file[finding.path].append(finding)

    out = ["CJK text in comments/docstrings (lines per file):"]
    for path in sorted(per_file):
        out.append(f"  {len(per_file[path]):5d}  {path}")
        if show_lines:
            for finding in per_file[path]:
                out.append(f"           {finding.line}: {finding.text}")
    if not per_file:
        out.append("  (none)")

    folders: Dict[str, _FolderTotal] = defaultdict(_FolderTotal)
    for path, items in per_file.items():
        total = folders[_top_level(path)]
        total.files += 1
        total.lines += len(items)
    if folders:
        out.append("")
        out.append("Summary by top-level folder:")
        width = max(len(name) for name in folders)
        for name in sorted(folders):
            total = folders[name]
            out.append(f"  {name:<{width}}  {total.files:4d} files  {total.lines:6d} lines")

    total_lines = sum(len(items) for items in per_file.values())
    out.append("")
    out.append(
        f"Total: {total_lines} lines in {len(per_file)} files "
        f"({result.scanned} files scanned, {len(result.allowed)} allowlisted lines)"
    )
    return "\n".join(out)


def _reconfigure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(
        description="Report CJK characters in code comments and docstrings."
    )
    parser.add_argument("paths", nargs="*", help="limit the scan to these files or folders")
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="exit 1 when any non-allowlisted finding remains (default: report only)",
    )
    parser.add_argument("--show-lines", action="store_true", help="print each offending line")
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=DEFAULT_ALLOWLIST,
        help="allowlist file (default: scripts/cjk_comment_allowlist.txt)",
    )
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    _reconfigure_stdout()
    try:
        allowlist = load_allowlist(args.allowlist)
        result = collect(args.root, args.paths, allowlist)
    except CheckerError as exc:
        print(f"[cjk-comments] ERROR: {exc}", file=sys.stderr)
        return 2

    for raw in result.unmatched_paths:
        print(
            f"[cjk-comments] WARNING: {raw} matches no git-tracked file "
            "(untracked files are not scanned; git add them first)",
            file=sys.stderr,
        )
    print(format_report(result, args.show_lines))
    if result.reported and args.fail_on_findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
