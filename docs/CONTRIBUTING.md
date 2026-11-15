# 贡献指南

感谢你对本项目的关注！欢迎任何形式的贡献。

## 🐛 报告 Bug

1. 先搜索 [Issues](https://github.com/ZhuLinsen/daily_stock_analysis/issues) 确认问题未被报告
2. 使用 Bug Report 模板创建新 Issue
3. 提供详细的复现步骤和环境信息

## 💡 功能建议

1. 先搜索 Issues 确认建议未被提出
2. 使用 Feature Request 模板创建新 Issue
3. 详细描述你的使用场景和期望功能

## 🔧 提交代码

### 开发环境

```bash
# 克隆仓库
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
```

### 提交流程

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交改动：`git commit -m 'feat: add some feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

### Commit 规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
feat: 新功能
fix: Bug 修复
docs: 文档更新
style: 代码格式（不影响功能）
refactor: 重构
perf: 性能优化
test: 测试相关
chore: 构建/工具相关
```

示例：
```
feat: 添加钉钉机器人支持
fix: 修复 429 限流重试逻辑
docs: 更新 README 部署说明
```

### 代码规范

- Python 代码遵循 PEP 8
- 函数和类需要添加 docstring
- 重要逻辑添加注释
- 新功能需要更新相关文档

### CI 自动检查

提交 PR 后，CI 会自动运行以下检查：

仅修改普通 `docs/**`、非治理类 Markdown 或 `LICENSE` 时，CI 保留轻量的变更检测、治理校验、门禁汇总和仅报告的 `cjk-comments` 检查，但跳过 3 个后端测试 shard、Docker、Web 与桌面打包。被离线测试直接读取的契约文档、静态 API 规格与 Markdown fixture 仍会触发后端测试。`AGENTS.md`、`.github/instructions/**`、`.claude/skills/**` 等治理资产仍会由 `ai-governance` 校验；配置、依赖、工作流等会影响运行的文本文件仍执行对应完整检查。

| 检查项 | 说明 | 必须通过 |
|--------|------|:--------:|
| backend-gate | `scripts/ci_gate.sh`（py_compile + flake8 严重错误 + 本地核心脚本 + offline pytest） | ✅ |
| docker-build | Docker 镜像构建与关键模块导入 smoke | ✅ |
| web-gate | 前端变更时执行 `npm run lint` + `npm run build` | ✅（触发时） |
| pr-review | 暂停 PR 自动触发，仅保留维护者通过 `workflow_dispatch` 按 PR 编号手动运行；通过 GitHub API 读取 PR 元数据和 diff，不检出或执行 fork PR 代码 | ❌（辅助项） |
| network-smoke | 定时/手动执行 `pytest -m network` + `scripts/test.sh quick`（非阻断） | ❌（观测项） |
| cjk-comments | `scripts/check_cjk_comments.py` 报告注释 / docstring 中仍含中文（CJK）的文件（仅报告，不阻断） | ❌（观测项） |

**本地运行检查：**

```bash
# backend gate（推荐）
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh

# 前端 gate（如修改了 apps/dsa-web）
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

### CJK 注释检查（仅报告）

`scripts/check_cjk_comments.py` 扫描 git 已跟踪的 Python、Shell、PowerShell、YAML、TS/TSX/JS/JSX/MJS/CJS、CSS 文件，列出注释或 docstring 中含中文（CJK 汉字）的文件及每个文件的行数，并按顶层目录汇总。字符串字面量（含 Python f-string、JS/TS 模板字符串、YAML 引号值和普通块标量）属于运行时数据，不会被报告；YAML 中 `run: |` / `script: |` 块内的 Shell / JS 注释会被报告，但 `run` 块中再嵌入的其他语言代码（如 `python - <<EOF`、`python -c`）不会被检查。只扫描 git 已跟踪文件，新文件需先 `git add`；指定路径未匹配任何已跟踪文件时会输出警告。

```bash
python scripts/check_cjk_comments.py                  # 全仓库
python scripts/check_cjk_comments.py src tests        # 仅指定路径
python scripts/check_cjk_comments.py --show-lines src # 同时输出每一行
```

默认始终以 0 退出；`--fail-on-findings` 会在存在未豁免条目时以 1 退出（CI 当前未开启）。CI 中的 `cjk-comments` job 以仅报告模式运行，不会导致构建失败。

确需保留的中文注释写入 `scripts/cjk_comment_allowlist.txt`，每行一条：`<路径 glob>[:<行号>[-<行号>]] | <原因>`。路径为仓库相对 POSIX 路径，按 `fnmatch` 匹配（`*` 也匹配 `/`），原因必填，`#` 开头的行为注释。

## 📋 优先贡献方向

查看 [README](../README.md) 了解项目当前的核心能力与主要入口：

- 🔔 新通知渠道（钉钉、飞书、Telegram）
- 🤖 新 AI 模型支持（GPT-4、Claude）
- 📊 新数据源接入
- 🐛 Bug 修复和性能优化
- 📖 文档完善和翻译

## ❓ 问题解答

如有任何问题，欢迎：
- 创建 Issue 讨论
- 查看已有 Issue 和 Discussion

再次感谢你的贡献！ 🎉
