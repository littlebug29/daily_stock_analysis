import subprocess
from pathlib import Path

import pytest

from scripts.check_cjk_comments import (
    CheckerError,
    collect,
    load_allowlist,
    main,
    scan_source,
)


def _lines(path: str, source: str):
    return [f.line for f in scan_source(path, source)]


# --- Python -----------------------------------------------------------------

def test_python_comments_and_docstrings_are_reported():
    source = (
        '"""模块说明"""\n'               # 1 module docstring
        "import os  # 导入\n"            # 2 trailing comment
        "\n"
        "class A:\n"
        '    """类说明\n'                # 5 multi-line class docstring
        "    second line\n"              # 6 (no CJK)
        '    第三行"""\n'                # 7
        "\n"
        "    async def f(self):\n"
        "        '''函数说明'''\n"       # 10 function docstring
        "        # 纯注释\n"             # 11 full-line comment
        "        return 1\n"
    )
    assert _lines("m.py", source) == [1, 2, 5, 7, 10, 11]


def test_python_string_literals_are_not_reported():
    source = (
        "def f(name):\n"
        "    x = 1\n"
        '    msg = "中文消息 # 不是注释"\n'
        "    tpl = f\"你好 {name} # 也不是\"\n"
        "    raw = '''多行\n"
        "    字符串'''\n"
        '    logger.info("日志 %s", msg)\n'
        '    """表达式字符串，不是 docstring"""\n'
        "    return tpl\n"
        'CONST = "常量"\n'
        '"""模块末尾的字符串也不是 docstring"""\n'
    )
    assert _lines("m.py", source) == []


def test_python_english_comment_with_fstring_cjk_on_same_line():
    source = 'x = f"{1}价格"  # English comment\ny = 2  # 中文\n'
    assert _lines("m.py", source) == [2]


def test_python_syntax_error_falls_back_to_comments():
    source = "def broken(:\n    # 坏文件\n"
    assert _lines("m.py", source) == [2]


# --- TS / JS / CSS -----------------------------------------------------------

def test_js_comments_are_reported():
    source = (
        "// 行注释\n"                    # 1
        "/**\n"                          # 2
        " * 文档注释\n"                  # 3
        " */\n"                          # 4
        "const a = 1; /* 块注释 */\n"    # 5
        "<div>{/* JSX 注释 */}</div>\n"  # 6
    )
    assert _lines("a.tsx", source) == [1, 3, 5, 6]


def test_js_strings_and_templates_are_not_reported():
    source = (
        "const s = '中文 // 不是注释';\n"
        'const d = "中文 /* 也不是 */";\n'
        "const t = `模板 ${a ? '是' : `嵌套 ${b}`} // 仍是模板\n"
        "第二行 /* 模板内 */`;\n"
        "const re = /中文\\/ //;\n"
        "const div = x / 2; // 除法后的注释\n"
    )
    assert _lines("a.ts", source) == [6]


def test_jsx_text_url_is_not_a_comment():
    source = (
        "const a = <a href={u}>http://中文.com 文本</a>;\n"
        "const b = 1; // 真注释\n"
    )
    assert _lines("a.tsx", source) == [2]


@pytest.mark.parametrize(
    "source",
    [
        "switch (x) { case 1:// 注释\n}\n",
        "const y = x ? a :// 注释\nb;\n",
        "const o = {a://注释\n1};\n",
        "label:// 注释\n",
    ],
)
def test_js_comment_right_after_colon_is_reported(source):
    assert _lines("a.ts", source) == [1]


def test_js_url_in_jsx_text_is_not_a_comment_or_regex():
    source = (
        "const a = <p>see https://例子.com/路径 [x</p>;\n"
        "// 后续注释\n"
    )
    assert _lines("a.tsx", source) == [2]


def test_js_keyword_property_is_an_operand():
    assert _lines("a.js", "const r = foo.return / 2 /* 注释 */;\n") == [1]


def test_js_comment_inside_template_expression_is_reported():
    source = "const t = `a ${ /* 表达式内注释 */ b }`;\n"
    assert _lines("a.js", source) == [1]


def test_css_only_block_comments():
    source = (
        "/* 样式注释 */\n"
        ".a::before { content: '中文 /* no */'; }\n"
        ".b { background: url(http://x/中文); }\n"
    )
    assert _lines("a.css", source) == [1]


# --- Shell / PowerShell / YAML ----------------------------------------------

def test_shell_comments_vs_strings_and_heredocs():
    source = (
        "#!/bin/bash\n"
        "# 脚本说明\n"                   # 2
        "echo '中文 # 不是注释'\n"
        'echo "中文 # 也不是"\n'
        "echo ${#arr[@]} $# # 末尾注释\n"  # 5
        "cat <<EOF\n"
        "# 文档内容\n"
        "EOF\n"
        "cat <<-'END'\n"
        "\t# 也是数据\n"
        "\tEND\n"
        "echo done # 结束\n"             # 12
        "echo $'it\\'s 中文 # 字符串' # 尾注释\n"  # 13 ANSI-C quoting
    )
    assert _lines("a.sh", source) == [2, 5, 12, 13]


def test_powershell_comments_vs_strings():
    source = (
        "# 行注释\n"                     # 1
        "<# 块注释\n"                    # 2
        "第二行 #>\n"                    # 3
        "Write-Host '中文 # 字符串'\n"
        "$s = @\"\n"
        "# here-string 内容\n"
        "\"@\n"
        "Write-Host \"a\" # 尾注释\n"    # 8
    )
    assert _lines("a.ps1", source) == [1, 2, 3, 8]


def test_yaml_comments_vs_values_and_block_scalars():
    source = (
        "# 顶部注释\n"                   # 1
        "name: 显示名称  # 行尾注释\n"   # 2
        "title: '中文 # 不是注释'\n"
        'desc: "中文 # 也不是"\n'
        "url: http://x#中文\n"
        "instructions: |\n"
        "  # 提示词标题\n"
        "  中文提示词\n"
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        "      - run: |\n"
        "          # 构建步骤\n"         # 13 shell comment in run block
        "          echo '中文 # 字符串'\n"
        "      - name: x\n"
        "        with:\n"
        "          script: |\n"
        "            // 脚本注释\n"     # 18 JS comment in script block
        "            core.info('中文');\n"
        "# 结尾注释\n"                   # 20
    )
    assert _lines("a.yml", source) == [1, 2, 13, 18, 20]


def test_unsupported_extension_is_ignored():
    assert _lines("notes.md", "# 标题\n") == []


# --- Allowlist and path filtering -------------------------------------------

def _git_repo(tmp_path: Path) -> Path:
    files = {
        "src/a.py": "# 中文一\nx = 1\n# 中文二\n",
        "src/b.py": "# 中文\n",
        "tests/c.py": "# 中文\n",
        "web/d.ts": "// 中文\n",
        "README.md": "# 中文\n",
    }
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    (tmp_path / "src" / "untracked.py").write_text("# 中文\n", encoding="utf-8")
    return tmp_path


def test_collect_scans_only_tracked_supported_files(tmp_path):
    root = _git_repo(tmp_path)
    result = collect(root, [], [])
    assert result.scanned == 4
    assert sorted({f.path for f in result.reported}) == ["src/a.py", "src/b.py", "tests/c.py", "web/d.ts"]
    assert result.allowed == []
    assert result.unmatched_paths == []


def test_collect_path_filtering(tmp_path, monkeypatch):
    root = _git_repo(tmp_path)
    monkeypatch.chdir(root)
    result = collect(root, ["src", "web/d.ts"], [])
    assert result.scanned == 3
    assert sorted({f.path for f in result.reported}) == ["src/a.py", "src/b.py", "web/d.ts"]


def test_collect_reports_paths_matching_no_tracked_file(tmp_path, monkeypatch):
    root = _git_repo(tmp_path)
    monkeypatch.chdir(root)
    result = collect(root, ["src/untracked.py", "README.md", "missing"], [])
    assert result.scanned == 0
    assert result.unmatched_paths == ["src/untracked.py", "missing"]


def test_allowlist_by_path_and_line(tmp_path):
    root = _git_repo(tmp_path)
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text(
        "# comment line\n"
        "\n"
        "tests/* | fixtures mirror Chinese input\n"
        "src/a.py:3 | documents a Chinese prompt\n",
        encoding="utf-8",
    )
    result = collect(root, [], load_allowlist(allowlist))
    assert [(f.path, f.line) for f in result.allowed] == [("src/a.py", 3), ("tests/c.py", 1)]
    assert [(f.path, f.line) for f in result.reported] == [("src/a.py", 1), ("src/b.py", 1), ("web/d.ts", 1)]


def test_allowlist_line_range(tmp_path):
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("src/a.py:1-3 | range\n", encoding="utf-8")
    (entry,) = load_allowlist(allowlist)
    assert entry.matches("src/a.py", 2)
    assert not entry.matches("src/a.py", 4)
    assert not entry.matches("src/b.py", 2)


@pytest.mark.parametrize("bad", ["src/a.py\n", "src/a.py |  \n", "src/a.py:5-2 | backwards\n"])
def test_allowlist_rejects_bad_entries(tmp_path, bad):
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text(bad, encoding="utf-8")
    with pytest.raises(CheckerError):
        load_allowlist(allowlist)


def test_repository_allowlist_parses():
    load_allowlist(Path(__file__).resolve().parent.parent / "scripts" / "cjk_comment_allowlist.txt")


# --- CLI exit codes -----------------------------------------------------------

def test_main_report_only_and_fail_on_findings(tmp_path, capsys):
    root = _git_repo(tmp_path)
    missing = tmp_path / "no-allowlist.txt"
    base = ["--root", str(root), "--allowlist", str(missing)]

    assert main(base) == 0
    out = capsys.readouterr().out
    assert "Summary by top-level folder:" in out
    assert "src/a.py" in out
    assert "Total: 5 lines in 4 files" in out

    assert main(base + ["--fail-on-findings"]) == 1
    capsys.readouterr()

    bad = tmp_path / "bad.txt"
    bad.write_text("no reason\n", encoding="utf-8")
    assert main(["--root", str(root), "--allowlist", str(bad)]) == 2


def test_main_warns_on_untracked_path(tmp_path, capsys, monkeypatch):
    root = _git_repo(tmp_path)
    monkeypatch.chdir(root)
    assert main(["--root", str(root), "src/untracked.py"]) == 0
    assert "matches no git-tracked file" in capsys.readouterr().err


def test_main_fail_on_findings_passes_when_clean(tmp_path):
    root = _git_repo(tmp_path)
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("* | everything\n", encoding="utf-8")
    assert main(["--root", str(root), "--allowlist", str(allowlist), "--fail-on-findings"]) == 0
