---
status: accepted
---

# Fork daily_stock_analysis and delete non-Vietnam code

We want feature parity with ZhuLinsen/daily_stock_analysis (MIT) for the Vietnamese market only, so we fork it rather than rebuild, and add Vietnam data, news, calendar and Market Phase modules. Code for other markets (CN/HK/US/JP/KR data sources, China-only Channels, zh/ko locales, pinyin matching, dragon-tiger, concept boards) is physically deleted rather than disabled behind config, because a Vietnam-only codebase is easier to read and reason about than one carrying dead paths.

## Considered Options

- **Rebuild from scratch**: rejected; months of work to reach parity and no upstream fixes.
- **Fork and add Vietnam as one more market**: rejected; the product is Vietnam-only.
- **Fork and disable (not delete) non-Vietnam code**: rejected in favour of a clean tree, despite being merge-friendlier.

## Consequences

Until the other markets are deleted (#14), their code paths stay in place and their codes keep routing to upstream data sources. Where code shapes collide, Vietnamese shapes win: any 3-character code (e.g. `IBM`, `AMD`) is read as a Vietnamese Instrument and looked up on the Vietnamese exchanges, never as a US ticker; it fails with a "no Vietnamese data" reason if no Vietnamese listing exists. Codes that can't be Vietnamese (e.g. `AAPL`, `600519`) are unaffected until #14 removes them.

One deliberate exception survives the deletion: secret redaction (`src/utils/sanitize.py`, `src/llm/local_cli_backend.py`) still recognises the deleted China-only Channels' webhook hosts and env-key names (Feishu, DingTalk, WeChat Work). Old `.env` files and logs can still carry those secrets, and dropping the rules would let them leak into logs and LLM prompts; the rules hold no Channel behaviour.

We still intend to merge upstream regularly. Because deleted files and edited shared files diverge from upstream, most merges will conflict; keep Vietnam-specific logic in new modules where possible so conflicts are confined to the deletions and to the seams where Vietnam code plugs in.
