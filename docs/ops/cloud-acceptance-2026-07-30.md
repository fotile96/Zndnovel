# 云端环境验收记录 — 2026-07-30

首次云端会话（claude.ai/code cloud environment）的实测归档。云端容器销毁后这些观察不可复现，故入库。

- 采集时间：2026-07-30 15:17–15:22 UTC
- 会话：`e4b03c4e-4eb5-55ba-b969-b0710d23194d`，分支 `claude/cloud-env-acceptance-4f035g`
- HEAD：`2d59bed manually add .claude/settings.json`
- 环境镜像：`sandbox-ccr-default:74306e8bfdefb9f88fc0b5f3d4940d7086b3d3bb`，`CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=cloud_default`
- **本次验收未改动任何 `lua_scripts/`、`png/`、`data/`、`tools/`、`glossary/`、`skeleton/` 内容**；全程 `git status` 干净（`py_compile` 产生的 `tools/__pycache__` 已即时删除）。

---

## 一、结论（先看这段）

**环境达标：可以在云端做本项目的全部现有工作。** 依赖、生成物一致性、测试、git 读写通路全绿：`uv sync --locked` 一致，`build_ledger --check` / `build_dag --check` 均 OK，`pytest 55 passed`，`git fetch --dry-run` 与 `git push --dry-run` 均 exit 0。

**但有一项设计级失效，必须知道：仓库内 `.claude/settings.json` 在云端会话中完全无效。** 它的 `hooks.SessionStart`、`enabledPlugins`、`extraKnownMarketplaces`、`permissions.allow` 四项**一项都没生效**。直接后果：

1. **`--mode session` 冒烟不会自动跑**，每次新会话须手动 `bash .claude/cloud-setup.sh --mode session`（脚本本身没问题，见 §三）。本次能看到 `work/setup-baseline.txt` 是**建环境时 `--mode setup` 留下的**，不是 SessionStart 触发的——「文件存在 ⇒ hook 已触发」这个判据不成立。
2. **`superpowers` / `mattpocock-skills` 插件永远不会加载**（`SKIP_PLUGIN_MARKETPLACE=true` 是环境级开关）。云端做 SDD 流程要么改用别的载体，要么接受手工执行。

另有 4 处 CLAUDE.md 描述与实测不符，详见 §五。**按要求本次未改动任何脚本或 CLAUDE.md。**

---

## 二、逐条事实采集

### 1. 环境指纹

| 项 | 实测值 |
|---|---|
| `$CLAUDE_CODE_REMOTE` | `true` |
| `pwd` | `/home/user/Zndnovel` |
| `id -un` | `root`（`uid=0(root) gid=0(root)`）—— **会话本身也是 root** |
| `python3 -V` | **`Python 3.11.15`**（`/usr/local/bin/python3` → `/usr/bin/python3.11`） |
| `uv --version` | `uv 0.8.17`（`/root/.local/bin/uv`） |
| `uv run python -V` | `Python 3.12.3`（`.venv/bin/python` → `/usr/bin/python3.12`） |
| 其他 | `IS_SANDBOX=yes`、`CLAUDE_CODE_DEBUG=true`、`CLAUDE_EFFORT=max`、`CLAUDE_ADDITIONAL_DIRECTORIES=/mnt/user-data` |

解释器全景（`uv python list`）：镜像自带 `/usr/bin/python3.{10,11,12,13}`，其中 3.12.3 与 3.13.12 均可满足 `requires-python >=3.12`，`uv` 就地选用 3.12.3，**未下载托管解释器**。`.python-version` 不存在（符合规约）。

### 2. `work/setup-baseline.txt` 与 `work/setup-pytest.log`

两者**都存在**，但**不能据此判定 SessionStart hook 已触发**（见 §二.8 的反证）：

```
-rw-r--r-- 1 root root 1522 Jul 30 15:17 work/setup-baseline.txt
-rw-r--r-- 1 root root   99 Jul 30 15:17 work/setup-pytest.log
work/ctx/  work/out/          # 均已建好，空
```

`work/setup-pytest.log` 内容：`55 passed in 2.36s`。
`work/setup-baseline.txt` 内容与 `/var/log/claude-cloud-setup.log` 的 `mode=setup` 报告体一致（`repo=/home/user/Zndnovel`、`head=2d59bed`、`dirty=0`、`python=Python 3.12.3`、`data/ledger.jsonl=16749 行`、`forward.jsonl`/`patches.jsonl` 不存在、台账末 6 行）。

### 3. `/var/log/claude-cloud-setup.log`

存在（1592 bytes，mtime `15:17:01`），**只有一个 `mode=setup` 报告块**，末行 `无告警：环境就绪`。关键读数：

- `mode=setup` 出现 **1** 次，`mode=session` 出现 **0** 次（这是 §一.1 结论的直接证据）。
- `repo=/home/user/Zndnovel` ⇒ **UI setup script 跑过，且成功探测到仓库并以 `--mode setup` 委派**。
- **但 UI 脚本自己的探测行没进这个文件**：`grep -c 'PWD=' = 0`，`grep '探测上下文' = 0`。原因是 `cloud-ui-setup.sh` 把 `PWD=/HOME=/USER=` 打到 stdout，而只有 `cloud-setup.sh` 末尾的报告块被 `tee -a` 到该文件。**所以「云端 setup 阶段的工作目录/HOME/USER」这个本来想留证的问题，实际并未留下证据**（那几行流进了无官方文档的 UI 日志）。我们目前只能反推出「工作目录或 `CLAUDE_PROJECT_DIR` 之一使 `for c in ... /home/*/*` 命中了 `/home/user/Zndnovel`」。

> 备注：本次验收在 §三 手动跑了 2 次 `--mode session`，因此该日志现在含 `mode=setup` ×1 + `mode=session` ×2（48 行）。日后读日志者请知悉后两块是验收产物。

### 4. skills / 插件

**没有任何 `superpowers:*` 或 `mattpocock-skills:*` skill 可用。** 三重独立确认：

- 会话 skill 清单里只有：`session-start-hook, dataviz, artifact-design, artifact-capabilities, update-config, keybindings-help, simplify, fewer-permission-prompts, loop, claude-api, run, diverge, morning, skill-creator, xlsx, pptx, pdf, docx, init, review, security-review` —— 无插件前缀项。
- `ListPlugins` 返回 `{"results":[]}`；`/root/.claude/plugins` 不存在；全盘无 `claude-plugins-official` 缓存目录。<br>　↳ **后补：`ListPlugins` 这一项读数当日晚些时候即不同，见 §七。本行其余两项（无 plugins 目录、无缓存）与结论不受影响。**
- 诊断日志：`load_plugin_hooks_started` → `load_plugin_hooks_completed {"duration_ms":0}`（0 毫秒，即无插件可加载）。

**根因（环境级，不是配置写错）**：`SKIP_PLUGIN_MARKETPLACE=true`。

**并非网络原因**——marketplace 仓库其实可达：`git ls-remote --heads https://github.com/anthropics/claude-plugins-official` exit 0（走 `url.http://local_proxy@127.0.0.1:41729/git/.insteadOf https://github.com/` 重写）。

**反向发现**：`~/.claude` 在云端**并非空白**，且账号级 skill **确实会同步进来**：

```
/root/.claude/skills/{diverge,morning,docx,pdf,pptx,xlsx,skill-creator,session-start-hook}/ + manifest.json
/root/.claude/launcher-settings.json      # 自带 SessionStart + Stop hook、permissions.allow:["Skill"]
/root/.claude/{session-start-git-identity.sh, stop-hook-git-check.sh, stop-hook-reply-gate.py, user-prompt-submit-reply-reminder.py}
```

`CLAUDE_CODE_SYNC_SKILLS=1`，诊断日志有 `skills_sync_starting` / `skills_sync_complete`；`manifest.json` 里 `diverge` 标 `"source": "custom"`。即：**用户自定义 skill 经 claude.ai 同步入云端**（不是从本机 `~/.claude` 继承，但结果上"载入了"）。

### 5. `check-tools`（基镜像版本清单，逐字记录）

```
Python : python3 3.11.15 | python 3.11.15 | pip 24.0 (py3.11) | poetry 2.3.3 | uv 0.8.17
         black 26.3.1 | mypy 1.19.1 | pytest 9.0.2 | ruff 0.15.8
NodeJS : node v22.22.2 | nvm available | npm 10.9.7 | yarn 1.22.22 | pnpm 10.33.0
         eslint v10.1.0 | prettier 3.8.1 | chromedriver 147.0.7727.24
Java   : openjdk 21.0.10 (Ubuntu-124.04) | maven 3.9.11 | gradle 8.14.3
Go     : go1.24.7 linux/amd64
Rust   : rustc 1.94.1 | cargo 1.94.1
C/C++  : clang 18.1.3 | gcc 13.3.0 (Ubuntu 24.04.1) | cmake 3.28.3 | ninja 1.11.1 | conan 2.27.0
Docker : docker 29.3.1 | dockerd 29.3.1 | docker compose v5.1.1
Utils  : mawk 1.3.4 | curl 8.5.0 | git 2.43.0 | grep 3.11 | gzip 1.12 | jq 1.7 | make 4.3
         rg 14.1.0 | sed 4.9 | tar 1.35 | tmux 3.4 | yq 0.0.0 | vim 9.1 | nano 7.2
=> ✅ All tool validations passed
```

底座是 Ubuntu 24.04（gcc `13.3.0-6ubuntu2~24.04.1`、openjdk `21.0.10+7-Ubuntu-124.04`）。**没有 `gh` / `hub`**（GitHub 操作走 MCP）。Chromium 预装于 `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`。**镜像默认 `python3` 是 3.11.15，不是 3.12。**

### 6. git 状态

```
$ git log --oneline -5
2d59bed manually add .claude/settings.json
7e3831a feat: 云端环境初始化脚本入库（两层：UI 薄引导 + 库内真逻辑）
c74920f chore: Python 下限放宽至 >=3.12 并移除 .python-version 精确钉
18efbd9 feat: build_dag 增加 --check/--out-dir，dag.json 可非破坏性校验
f5422c0 chore: SDD 工作台持久工件入库（台账/简报/报告），评审包保持忽略

$ git remote -v
origin  http://local_proxy@127.0.0.1:41729/git/fotile96/Zndnovel (fetch)
origin  http://local_proxy@127.0.0.1:41729/git/fotile96/Zndnovel (push)

$ git status
On branch claude/cloud-env-acceptance-4f035g
nothing to commit, working tree clean
```

**两处需要留意的克隆特性（CLAUDE.md 未记载）**：

- **浅克隆**：`.git/shallow` 存在（graft `b8f1b983…`），`git rev-list --count HEAD = 50`。
- **无 tag**：`git tag -l` 为空 —— **CLAUDE.md 反复引用的 `skeleton-v1` 冻结点在云端克隆里不存在**。任何要解析该 tag 的操作须先 `git fetch --tags origin`（`git fetch --dry-run` 已确认远端有它：`* [new tag] skeleton-v1`）。
- `remote.origin.fetch` 只配了 `+refs/heads/*:refs/remotes/origin/*`，无 tag refspec。
- git 身份由 `~/.claude/session-start-git-identity.sh` 写入 `/root/.gitconfig`：`Claude <noreply@anthropic.com>`；`safe.directory=*`。

### 7. GitHub proxy 通路（dry-run）

```
$ git fetch --dry-run -v
POST git-upload-pack (155/275/284 bytes)
From http://127.0.0.1:41729/git/fotile96/Zndnovel
 = [up to date]      main        -> origin/main
 * [new tag]         skeleton-v1 -> skeleton-v1
exit=0

$ git push --dry-run -v -u origin claude/cloud-env-acceptance-4f035g
 * [new branch]      claude/cloud-env-acceptance-4f035g -> claude/cloud-env-acceptance-4f035g
exit=0
```

读写通路均通。附带的网络策略实测（agent proxy `http://127.0.0.1:34923`，`selective:false`、`toolScoped:false`）：

| 目标 | 结果 |
|---|---|
| `https://pypi.org/simple/` | **200**（在 `NO_PROXY` 直连白名单里） |
| `https://files.pythonhosted.org/` | **200** |
| `https://api.github.com` | **200** |
| `https://raw.githubusercontent.com/...` | **200** |
| `https://example.com` | **200**（策略确为宽松 Trusted，非白名单也放行） |
| `https://github.com`（裸站） | **400** |
| `https://github.com/anthropics/claude-code` | **403** |
| `git ls-remote https://github.com/<任意公开仓库>` | **exit 0**（URL 被重写到 `127.0.0.1:41729` 本地 git proxy） |

即：**GitHub 的 git 与 API 路径通，github.com 的普通网页抓取被拒**（403/407 类按 `/root/.ccr/README.md` 规定不重试、只上报）。

### 8. 为什么判定「项目级 `.claude/settings.json` 未生效」

四条互相独立的证据：

1. **日志**：`/var/log/claude-cloud-setup.log` 在我手动执行前 `mode=session` 计数为 **0**；我手动跑一次后日志 16→32 行并出现 `mode=session` 块 ⇒ 追加机制本身工作正常 ⇒ 之前的"缺失"是真缺失。
2. **诊断日志**（`$CLAUDE_CODE_DIAGNOSTICS_FILE`）：全程只 spawn 了 **1 个** SessionStart hook，且 24ms 完成：
   ```
   15:17:04.597 hook_spawn_started   {"hook_event_name":"SessionStart","index":0}
   15:17:04.614 hook_spawn_completed {"index":0,"duration_ms":24,"exit_code":0}
   ```
   24ms 不可能是 `cloud-setup.sh`（实测 4s）；且 `/root/.gitconfig` mtime = `15:17:04.605` 正落在该窗口内 ⇒ **index 0 就是用户级 `session-start-git-identity.sh`**。没有 index 1 ⇒ 项目级 hook **从未被注册/派生**。
3. **信任状态**：`/root/.claude.json` 中 `projects["/home/user/Zndnovel"]` 有 `hasTrustDialogAccepted = false`、`allowedTools = []`、`hasClaudeMdExternalIncludesApproved = false`。
4. **控制实验**：把 hook 里那串命令原样执行 —— `bash -c '[ -n "$CLAUDE_CODE_REMOTE" ] && bash .claude/cloud-setup.sh --mode session || true'` → exit 0，日志 32→48 行 ⇒ **命令串本身没问题**，问题只在"没人调用它"。

**两个候选机制**：未信任项目（`hasTrustDialogAccepted=false`）导致项目 settings 整体不被采纳；以及 `SKIP_PLUGIN_MARKETPLACE=true` 独立掐死插件路径。本次**未能证明**具体是哪一个门控了 hook（诊断日志无 trust/skip 相关条目）。另观察到 `settings_load_completed {"source_count":4,"error_count":1}`（两次加载都是 1 个 error），**未能归因到具体源**——`.claude/settings.json` 本身是合法 JSON（`json.load` 通过，keys = `enabledPlugins/extraKnownMarketplaces/hooks/permissions`），缺失的候选源有 `/root/.claude/settings.json`、`.claude/settings.local.json`、`/etc/claude-code/managed-settings.json`。

副作用一并记录：`permissions.allow` 那 11 条也未生效（`allowedTools=[]`）。本次会话所有 Bash 调用（含不在白名单里的 `git fetch`、`curl`、`find /`）均未被拦，说明放行来自沙箱模式（`IS_SANDBOX=yes`）而非该白名单 —— **该白名单在云端是纯装饰**。

---

## 三、手动 `--mode session` 运行

```
$ bash .claude/cloud-setup.sh --mode session
exit_code = 0
wall clock = 4s   (15:20:25 → 15:20:29 UTC)
stderr     = 空（无 WARN 行）
告警条数   = 0   → 报告体末行 "无告警：环境就绪"
```

stdout（逐行）：

```
[cloud-setup:session] uv 0.8.17
[cloud-setup:session] uv sync --locked OK（依赖与 uv.lock 一致）
[cloud-setup:session] build_ledger --check OK（生成物与 lua 源一致）
[cloud-setup:session] build_dag --check OK（生成物与 lua 源一致）
[cloud-setup:session] pytest 全绿（55 passed in 2.31s）
[cloud-setup:session] 冒烟耗时 4s
```

- **冒烟耗时 4s**（脚本自报，含两个 `--check` + pytest 2.31s）；整体墙钟也是 4s，即 `uv sync --locked` 命中已有 `.venv`，接近零成本。
- 运行后 `git status --porcelain` 为空 ⇒ **幂等且不污染工作树**（`work/` 已 gitignore）。
- 脚本四件事全部实测到：`uv sync --locked` ✅ / `work/ctx`+`work/out` ✅ / 双 `--check` + pytest ✅ / `work/setup-baseline.txt` ✅。
- **SDD 证据保全告警正确保持沉默**：`git ls-files --others --ignored --exclude-standard -- .superpowers | grep -c '\.md$'` = **0**，且 `.superpowers/` 下 10 份 `*.md` 全部已跟踪（含 `task-4-brief.md`）；`review-*.diff` 计数 0，保持忽略。规约执行到位。
- 另外验证：`tools/extract_{dag,crd,text}.py` 在**系统 python3（3.11.15）**下 `py_compile` 通过；两个 stdout 型的实跑正常（`extract_dag` 1797 行、`extract_crd` 196 行）。「纯 stdlib、系统 python3 直接可跑」的规约成立 —— 但**其真实门槛是 3.11 兼容，不是 3.12**。

---

## 四、`docs/ops/` 目录

本文件是该目录第一份文档。`docs/` 是普通跟踪路径（已有 `docs/superpowers/{plans,specs}` 4 份入库），`.gitignore` 不涉及，无需 `git add -f`。

---

## 五、CLAUDE.md「云端环境」节 逐条对照

| # | CLAUDE.md 描述 | 实测 | 差异说明 |
|---|---|---|---|
| 1 | 「云端会话不继承本机 `~/.claude`（用户级 skills/agents/commands、用户级 enabledPlugins、用户级 CLAUDE.md 全都不载入）」 | ⚠️ **半错** | "不从本机文件系统继承"成立，但结论"不载入"不成立：`CLAUDE_CODE_SYNC_SKILLS=1` 会把**账号级自定义 skill 同步进 `/root/.claude/skills`**（本次 `diverge`、`morning` 在列，manifest 标 `source:custom`），且云端自带 `launcher-settings.json` 的 SessionStart/Stop hook 与 `permissions.allow:["Skill"]`。 |
| 2 | 「只吃仓库内的 `.claude/` 与 CLAUDE.md」 | ❌ **错** | 仓库 `.claude/settings.json` 的 **hooks / enabledPlugins / extraKnownMarketplaces / permissions 四项全部未生效**（§二.8）。云端实际"吃"的是 `~/.claude/launcher-settings.json` + 同步来的 skills + CLAUDE.md。CLAUDE.md 本身**确实生效**（本会话已加载）。 |
| 3 | 「首次建环境由 UI 脚本以 `--mode setup` 调用」 | ✅ 符合 | 日志恰有 1 个 `mode=setup` 块且 `repo=/home/user/Zndnovel`。 |
| 4 | 「之后每次会话由 SessionStart hook 以 `--mode session` 调用」 | ❌ **错** | 本次会话**未调用**；`mode=session` 计数 0，诊断日志只 spawn 了用户级那一个 hook。 |
| 5 | 「（cloud-setup.sh）做四件事：`uv sync --locked` / 建 `work/ctx work/out` / 冒烟 / 写基线报告」 | ✅ 符合 | 四件事全部实测通过，exit 0，0 告警，4s。 |
| 6 | 「另有一条 SDD 证据保全告警」 | ✅ 符合 | 存在且逻辑正确；本次条件不满足故沉默（0 份未入库 `.md`）。 |
| 7 | 「脚本永远 `exit 0`」 | ✅ 符合 | 两次运行均 exit 0。 |
| 8 | 「setup 以 root 跑」 | ✅ 符合（且更进一步） | **会话本身也是 root**（`id -un = root`）。故 CLAUDE.md 担心的"root 建环境／非 root 跑会话的归属问题"在本环境**不会发生**；脚本里的 `chown --reference` 与 `safe.directory` 目前是无害的空转防御。 |
| 9 | 「网络默认 Trusted（PyPI/GitHub 已放行）」 | ⚠️ **不精确** | PyPI 直连 200；GitHub 的 **git（URL 重写至本地 git proxy）与 api.github.com、raw.githubusercontent.com 通**，但 **github.com 网页抓取被拒（裸站 400、带路径 403）**。策略确实宽松（`example.com` 也 200）。 |
| 10 | 「环境变量在 UI 配置且明文可见，不要放 API key」 | ✅ 未违反 | 未见任何项目自定义环境变量；无 `.env`；`GH_TOKEN`/`GITHUB_TOKEN`/`AWS_*` 等均为平台注入。 |
| 11 | 「只设下限 `>=3.12` …（Ubuntu 24.04 自带 3.12）…无需联网下载托管解释器」 | ⚠️ **括号内不精确，但决策正确** | 镜像**默认 `python3` 是 3.11.15**（`/usr/bin/python3` → alternatives → 3.11）；3.12.3 与 3.13.12 以 `/usr/bin/python3.1{2,3}` 形式存在，`uv` 就地选中 3.12.3、**零下载**。结论"不钉精确版可避免下载"成立。 |
| 12 | 「`tools/extract_*.py` 保持纯 stdlib（系统 python3 也能直接跑）」 | ✅ 成立，但门槛需修正 | 实测在 **3.11.15** 下可编译可运行 ⇒ 该规约的真实约束是 **3.11 兼容**（比文中隐含的 3.12 更严）。 |
| 13 | 「约 5 分钟预算 / 只在首次建环境时执行一次 / 其后文件系统被快照复用」 | ➖ 无法验证 | 本次是新环境的首个会话（容器文件 mtime 15:16，setup 15:17:01，会话 15:17:04），无第二个会话可对比。 |
| 14 | 「setup 阶段的工作目录…无文档，故脚本自行探测…先记录实况以便日后收紧」 | ⚠️ **留证失败** | `cloud-ui-setup.sh` 的 `PWD=/HOME=/USER=` 探测行打在 stdout，**没有进 `/var/log/claude-cloud-setup.log`**（该文件只收 `cloud-setup.sh` 的报告块）。原定要收集的实况**并未留下**。 |

### CLAUDE.md 未记载、但影响使用的两点

- **克隆是浅克隆（depth 到 50 个 commit）且不带 tag** ⇒ `skeleton-v1` 在云端不存在，凡"以 tag 为冻结基准"的核对须先 `git fetch --tags origin`。
- **`.claude/settings.json` 的 `permissions.allow` 在云端无效**；放行实际来自 `IS_SANDBOX=yes`。

---

## 六、待决（本次按要求未动脚本/未动 CLAUDE.md）

1. `--mode session` 的自动触发需要替代方案（项目级 hook 在未信任项目下不派生）；在此之前，**新会话开场手动跑一次**是唯一可靠做法。
2. 若 SDD 流程依赖 `superpowers` 插件，需另找载体（`SKIP_PLUGIN_MARKETPLACE=true` 是环境级、不可由仓库配置绕过）。<br>　↳ **已解，见 §八：每命令前缀可覆盖该开关，插件改装到用户级配置面。**
3. `cloud-ui-setup.sh` 的上下文探测行若真想留证，得自己写文件而不是靠 stdout。
4. CLAUDE.md 第 1/2/4/9/11/14 条描述待按本记录订正。

---

## 七、补记：`ListPlugins` 读数变化与 skill 直接调用实测（2026-07-30 后续会话）

本节是**后续会话的追加观察**，不修改 §一/§二.4 的原始结论（那些是 15:17–15:22 UTC 的读数，保持原样）。

- 采集时间：2026-07-30 15:51 UTC（同日，距首次验收约 30 分钟）
- 会话分支：`claude/superpowers-skill-sync-refs-xsjcsl`，HEAD `105dafa`
- `bash .claude/cloud-setup.sh --mode session` 全绿，唯一告警仍是「无 tag」（与 §二.6 一致）

### 1. 新读数：`ListPlugins` 返回 `superpowers` enabled

```json
{"results":[{"id":"plugin_01RiaVdxas1r5zTg8TREbehY","name":"superpowers","description":null,"enabled":true}]}
```

与 §二.4 记录的 `{"results":[]}` **不同**。变化原因未能确定——可能是两次采集之间用户在 claude.ai 侧启用了该插件，也可能是该工具背后的数据面本身有别；**本记录只陈述观察，不断言成因**。

### 2. 但容器侧依旧完全不可用（结论未变）

| 探测 | 结果 |
|---|---|
| `/root/.claude/skills/` | 8 个目录，全部为账户同步 skill，**无 superpowers 系** |
| `/root/.claude/plugins` | 不存在 |
| `SearchSkills(["executing plans","brainstorming","finishing a development branch","subagent driven development"])` | `[]` |
| 会话 skill 清单 | 21 项，**无任何 `插件名:技能名` 形态条目** |

### 3. 新增证据：直接调用 skill（首次验收未做）

§二.4 的三重确认是**清单/文件系统/日志的间接推断**；本次补上直接调用：

| 调用 | 结果 |
|---|---|
| `Skill(superpowers:executing-plans)` | `Unknown skill` |
| `Skill(superpowers:finishing-a-development-branch)` | `Unknown skill` |
| `Skill(executing-plans)`（去前缀） | `Unknown skill` |

去前缀写法同样失败 ⇒ **这不是插件名前缀的命名解析问题，是整个 superpowers 技能集在云端不存在**。

附带结论：**「跨技能引用（父技能收尾跳子技能）能否解析」在云端无法被验证**——父技能就加载不了，根本走不到跳转那一步。

### 4. 影响：仓库内 4 处 `superpowers:*` 引用在云端悬空

```
docs/superpowers/plans/2026-07-30-p0-skeleton.md:3
docs/superpowers/plans/2026-07-30-p1a-data-foundation.md:3
docs/superpowers/plans/2026-07-30-p1b-linearize-context.md:3
docs/superpowers/specs/2026-07-30-translation-pipeline-design.md:146
```

前三处为计划文档首行的 `REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans`。云端推进这些计划只能**人工照计划的 checkbox 结构逐 task 执行**（`.superpowers/sdd/*/progress.md` 台账即此做法），或回本地会话。这是 §六 待决第 2 条的具体化。

### 5. 给后来读者的判据

**「账户面 enabled」≠「本会话可调用」，这是两个平面。** 判断 superpowers 是否真能用，别看 `ListPlugins`，看这三样：`/root/.claude/plugins` 是否存在、会话 skill 清单里有无带前缀条目、直接 `Skill()` 调用是否 `Unknown skill`。根因仍是环境级 `SKIP_PLUGIN_MARKETPLACE=true`，仓库配置绕不过去。

---

## 八、插件失效的解法（2026-07-30，据 anthropics/claude-code#68264 实测）

§二.4 判定 `SKIP_PLUGIN_MARKETPLACE=true` 是环境级开关、仓库配置绕不过去——**这半句仍然对，但"无解"是错的**。上游 issue #68264 给出了可行路径，本节是在本容器上的完整复现与偏差修正。

> issue 内容由用户转贴（`api.github.com` 与 `github.com` 在本环境均 403，MCP 亦因 repo scope 拒绝，无法自取）。

### 1. 病根（issue 的诊断，本容器逐条吻合）

两重失效叠加，缺一都不至于全灭：

| 层 | 现象 | 本容器实测 |
|---|---|---|
| 仓库级 | `.claude/settings.json` 因项目未受信整体不采纳，`enabledPlugins`/`extraKnownMarketplaces` 形同虚设 | §二.8 已证 |
| 环境级 | `SKIP_PLUGIN_MARKETPLACE=true` 在启动时**短路 marketplace 解析**，连取都不去取 | `plugin list` 空、`known_marketplaces.json` 不存在、`echo $SKIP_PLUGIN_MARKETPLACE`→`true` |

关键点：**该变量设成环境变量不生效**（`cloud_default` 运行时重置），**只有每命令前缀能覆盖**。

### 2. 与 issue 环境的三处偏差

issue 报的是 Routine runner 2.1.177，本容器是普通云端会话 2.1.220：

| 偏差 | 影响 |
|---|---|
| `CLAUDE_CODE_REMOTE_SKIP_SETTINGS_SYNC` **未设置** | issue 附注的「git HTTPS 因空密码 `x-access-token:` 全挂」不适用；本容器重写为 `url.http://local_proxy@127.0.0.1:41729/git/.insteadOf https://github.com/`，clone **通** |
| 因而**无须**加第 2 个 source | issue 的「marketplace 作为第 2 routine source 克隆到 `/home/user/`」这步可跳过（本会话也做不到：`add_repo` 拒绝跨 owner，marketplace 与 superpowers 都不在 `fotile96` 名下） |
| 2.1.220 新增**保留名守卫** | issue 的本地路径安装法**已失效**：`claude plugin marketplace add <本地clone路径>` 报 `The name 'claude-plugins-official' is reserved for official Anthropic marketplaces and can only be used with GitHub sources from the 'anthropics' organization` |

### 3. 可行命令（本容器验证通过）

绕开保留名守卫的办法就是**别喂本地路径，直接按 GitHub 源加**——反正 clone 是通的：

```sh
SKIP_PLUGIN_MARKETPLACE=false claude plugin marketplace add anthropics/claude-plugins-official
SKIP_PLUGIN_MARKETPLACE=false claude plugin install superpowers@claude-plugins-official
SKIP_PLUGIN_MARKETPLACE=false claude plugin install mattpocock-skills@claude-plugins-official
```

结果：`superpowers 6.2.0` + `mattpocock-skills 1.2.0`，落在 `~/.claude/plugins/cache/<市场>/<插件>/<版本>/`（即 §二.4 说的「载体二」），共 55 份 `SKILL.md`；superpowers 侧 14 个技能，`executing-plans`/`subagent-driven-development`/`finishing-a-development-branch` 三个都在。

**为什么这样就绕过了病根**：安装会自动写出 `~/.claude/settings.json`（此前不存在）——

```json
{ "extraKnownMarketplaces": { "claude-plugins-official": { "source": { "source": "github", "repo": "anthropics/claude-plugins-official" } } },
  "enabledPlugins": { "superpowers@claude-plugins-official": true } }
```

内容与仓库那份等价，但**这份在用户级配置面，云端真正采纳**。等于把被忽略的仓库声明搬到了生效的那一层。

### 4. false green：当前会话不生效（issue 的警告已复现）

装完 `plugin list` 报两个 `√ enabled`、技能体确实在磁盘上，但同一会话内 `Skill(superpowers:executing-plans)` 仍返回 `Unknown skill`。**组件只在会话启动时挂载，云端无 `/reload-plugins`。** 去前缀 `Skill(executing-plans)` 同样失败——与 §七.3 一致，不是命名解析问题。

因此「跨技能引用能否解析」**本次仍未验证**：技能体虽已落盘（`executing-plans` 内部确实写着 `superpowers:finishing-a-development-branch`），但父技能在本会话挂不上，走不到跳转。**留待下个会话验证。**

### 5. 已固化进 `.claude/cloud-setup.sh` §1.6

新增 `ensure_plugins()`，`setup` 与 `session` 两模式都跑，在 `inspect_user_config` **之前**执行（否则报告拍到的是安装前状态）：

- **幂等**：`~/.claude/plugins/cache/<市场>/<插件>/` 存在即跳过（实测空跑 3s，无网络动作）。
- **不改退出码**：一切失败降级为 warn，遵守「永远 exit 0」约束。
- **两模式分工**：`setup` 早于会话挂载，是理想位置（新建环境即生效）；`session` 是自愈补装，装完仍需下个会话才生效。
- 插件清单 `PLUGINS=(superpowers mattpocock-skills)` 与仓库 `.claude/settings.json` 的声明保持一致。

### 6. 已决：安装**不留存**，根因是「每会话从建环境快照冷启」（2026-07-30 第三会话实测）

- 采集时间：2026-07-30 16:10–16:20 UTC，**同一环境**（该环境创建于 15:50:48Z），新会话
- 会话分支：`claude/superpowers-skill-sync-refs-xsjcsl`；快照里的工作树停在 `105dafa`，`git fetch` 后才见到 §八 那次会话推的 `9780946`

**A 判定：未留存。** 证据必须按「先拍照、后跑脚本」的顺序取——`--mode session` 里的 `ensure_plugins` 自己会补装，跑完再看就分不清了：

| 时点 | 探测 | 结果 |
|---|---|---|
| 跑脚本**前** | `ls /root/.claude/plugins` | `No such file or directory` |
| 跑脚本**前** | `/root/.claude/settings.json`（§八.3 所说安装会写出的那份） | 不存在 |
| 跑脚本**前** | `find /root/.claude/plugins -name SKILL.md \| wc -l` | 0 |
| 跑脚本时 | `ensure_plugins` 实际走的分支 | **安装分支**（`marketplace 已添加` + 两条 `插件已安装`），**不是**「插件已在位…跳过安装」 |
| 跑脚本后 | `/root/.claude/plugins` mtime | `16:12:09`（即本次写入） |

⚠️ 报告行 `user_plugins_installed=claude-plugins-official/superpowers/6.2.0 …` **不能用来判留存**——`ensure_plugins` 按 §八.5 的设计跑在 `inspect_user_config` 之前，这一行拍到的永远是**安装后**状态。判据只有上表「跑脚本前」那三行。

#### 根因：会话看到的是建环境时的快照，会话中途的写入一律丢弃

比原先「文件系统被快照复用」的猜测更硬的证据来自 `/var/log/claude-cloud-setup.log`——**同一个文件，三个写入者，只有 setup 时点的活下来**：

| 写入者 | 时点 | 现在还在吗 |
|---|---|---|
| UI setup 脚本 + `--mode setup` | 15:50:48 / 15:50:54Z（**建环境时**） | **在**（日志第 1–31 行） |
| §七 会话的 `--mode session`（§七 明载「全绿」跑过） | ~15:51Z（**会话中途**） | **没了**，日志里查无此条 |
| 本会话的 `--mode session` | 16:12:14Z | 在（本会话结束后同样会没） |

同一模式在别处复现：

- 工作树回到 `105dafa`（= 建环境时 `origin/main` 的头，15:49:19Z 推送），§八 会话 16:05 推的 `9780946` **不在本地**，`git fetch` 才拿回来。（`origin/claude/cloud-env-acceptance-4f035g` 也不在，但那是另一回事：快照里的克隆是 `--depth` 隐含的 `--single-branch main`。）
- `work/` 目录 mtime `15:50:53`，建环境时建的，留存。

**所以准确的说法不是「`~/.claude` 不留存」，而是：每个会话都从建环境快照冷启，会话内对整机任何位置的写入都随会话销毁。**

#### 为什么 `~/.claude/skills/` 看着像留存

它不是留存，是**每会话重新同步**：

| 时点 | `user_skills` 读数 |
|---|---|
| 15:50:54Z 建环境 | **1 个**：`session-start-hook` |
| 16:10:52（本会话启动时，早于我跑脚本 82 秒） | **8 个**：diverge docx morning pdf pptx session-start-hook skill-creator xlsx |

`CLAUDE_CODE_SYNC_SKILLS=1` 在会话启动时把账户 skill 拉回来；`~/.claude/plugins/` 没有任何对应机制 → 归零。**两个载体命运不同，别拿 skills 目录的存在推断 plugins 也在。**

### 7. B 判定：运行期仍未验证（第三次 false green），但静态引用图这次核完了

安装是本会话临时补的，**挂载早于安装**，于是 §八.4 的 false green 原样复现：

| 探测 | 结果 |
|---|---|
| 会话 skill 清单 | 21 项，**无任何 `superpowers:` 前缀条目**（与 §七.2 同） |
| `Skill(superpowers:executing-plans)` | `Unknown skill` |
| `Skill(superpowers:finishing-a-development-branch)` | `Unknown skill` |
| `SearchSkills(["executing plans","finishing a development branch","subagent driven development","brainstorming"])` | `[]` |
| `ListPlugins` | `superpowers` enabled（与 §七.1 同——账户面读数，与本会话可用性无关，§七.5 的判据继续有效） |

**运行期的跨技能引用依旧走不到**：父技能挂不上，跳转无从谈起。

但技能体这次在磁盘上，于是可以做**静态解析核验**（此前三次会话都做不了）——把安装体内所有 `superpowers:<名>` 引用抽出来，逐个查有无对应 `skills/<名>/SKILL.md`：

| 引用目标 | 出现次数 | 解析 |
|---|---|---|
| `superpowers:test-driven-development` | 5 | OK |
| `superpowers:finishing-a-development-branch` | 5 | OK |
| `superpowers:subagent-driven-development` | 4 | OK |
| `superpowers:using-git-worktrees` | 3 | OK |
| `superpowers:systematic-debugging` / `:requesting-code-review` / `:executing-plans` | 各 2 | OK |
| `superpowers:writing-skills` / `:verification-before-completion` / `:brainstorming` | 各 1 | OK |

**10 个目标全部命中，引用图闭合零悬空。** §七.4 列的仓库内 4 处引用所用的 3 个名字（`executing-plans` / `subagent-driven-development` / `finishing-a-development-branch`）也全部命中。

`executing-plans/SKILL.md` 里的引用原文（§八.4 只提了一句，这里录全）：

```
14: ... If subagents are available, use superpowers:subagent-driven-development instead of this skill.
19: 1. Ensure an isolated workspace: use superpowers:using-git-worktrees to create one or verify the existing one
37: - **REQUIRED SUB-SKILL:** Use superpowers:finishing-a-development-branch
```

即：**引用形式与 `superpowers/6.2.0/skills/` 的目录名严格一一对应，名字层面无歧义；剩下的唯一变量是运行期挂载。**

#### 附带（第 4 问）：agent type 那条轴对本插件**不适用**

issue 提到 `<plugin>:` 形态的 agent type 会 not found。查安装体：

- `superpowers/6.2.0/` 下**没有 `agents/` 目录**；`.agents/` 里只有一个 `plugins/marketplace.json`，不是 agent 定义。
- `subagent-driven-development` 的派单方式是**通用子代理 + 提示词文件**（`implementer-prompt.md` / `task-reviewer-prompt.md` / `re-review-prompt.md`），不引用任何具名 agent type；整个 `skills/` 目录 grep 不到 `subagent_type`。

**superpowers 6.2.0 根本不提供 agent 类型**，这条轴无从失败，也无需验证。`mattpocock-skills/1.2.0` 同理（其 `.agents/` 装的是 ADR 文档）。

### 8. 根治路径：只剩改 UI setup 脚本——本节首次给出「它可行」的证据与「仍未证」的两点

A 判定为不留存 ⇒ `--mode session` 的自愈补装**永远追不上**：每个新会话都从零装一遍，而挂载早于安装，于是**每个会话都不可用**。§八.5 那句「session 是自愈补装，装完仍需下个会话才生效」在「能留存」假设下成立，在实测的「不留存」下**等于永不生效**——这是本次要更正的判断。（`ensure_plugins` 的 session 分支因此每会话白花约 30–60s 网络时间；是否降级为仅 `setup` 模式跑，留待决定，本次未动脚本。）

唯一出路是把安装挪到**建环境时**执行，即改 `.claude/cloud-ui-setup.sh` 并**重贴进 claude.ai 环境设置的 Setup script 字段**。代价与约束：

- **会触发整机快照重建**（改库内的 `cloud-setup.sh` 不会，这正是两层拆分的意义）。
- setup 脚本约有 **7 天缓存**，插件因此**冻结在上次 setup 时的 marketplace HEAD**，不随上游更新。
- setup 有约 5 分钟预算且必须 `exit 0`（非零会让环境创建整体失败）——`ensure_plugins` 已满足（一切失败降级为 warn）。

**本次新增的支持证据**：setup 时点的写入确实进得了快照并跨会话存活（`/var/log/claude-cloud-setup.log` 的 15:50:54 报告、`work/` 的 15:50:53 目录）。所以「装在 setup 就能被下个会话看到」不再是猜测。

**但仍有两处未证，别当作已经成了**：

1. `SKIP_PLUGIN_MARKETPLACE=true` 在会话启动时**依然是 true**。已证它短路 marketplace 解析；**未证**它是否同时挡住「加载已落在 `~/.claude/plugins/cache`、且已在用户级 `settings.json` 里 enable 的插件」。若连加载也挡，装在 setup 同样白装。
2. 会话启动的账户同步会重写 `~/.claude/skills/`；它是否也会覆盖 setup 写下的 `~/.claude/settings.json`（`enabledPlugins` / `extraKnownMarketplaces`）未知。

这两条**在会话内测不了**（挂载发生在会话启动之前），只能靠真重建一次环境来判。
（未证点 ① 后来被 §九 改判为**可以廉价先测**，见下节；本节文字保留原样不追改。）

---

## 九、`SKIP_PLUGIN_MARKETPLACE` 是从微 VM 外面注入的（2026-07-30 第三会话，进程链取证）

§八 一直把这个 flag 当作「环境级开关」，但没查过它究竟由谁设置。用 `ps` + `/proc` 走一遍父进程链，答案是**容器内根本没人设它**。

### 1. 父进程链：变量在哪一环出现

同一次会话启动（16:10:41）：

| pid | 进程 | env 数 | `SKIP_PLUGIN_MARKETPLACE` |
|---|---|---|---|
| 1 | `/process_api --firecracker-init --addr 0.0.0.0:2024 --listen-vsock-port 2024` | **2**（`HOME=/`、`TERM=linux`） | **无** |
| 549 | `/bin/sh -c` 引导：`ln -sf /opt/claude-code/bin/claude /opt/node22/bin/claude` → `environment-manager task-run` | 56 | **true ← 首次出现** |
| 553 | `environment-manager task-run --stdin --session cse_… --session-mode resume-cached --upgrade-claude-code=False` | 58 | true |
| 583 | `claude --settings /root/.claude/launcher-settings.json …` | 69 | true |

pid 1 是 Firecracker 的 init，只有两个变量。**第一个带该变量的进程是 pid 549，而它由 `process_api` 按外部 API 请求拉起**——整套 env 是**宿主/控制面在请求启动会话时一并递进来的**。

`/tmp/environment-manager.out` 里有直供词：

```json
{"msg":"startup_context_env_var_keys","count":20,
 "keys":[…,"CLAUDE_CODE_SYNC_SKILLS","SKIP_PLUGIN_MARKETPLACE","USE_BUILTIN_RIPGREP"]}
```

这 20 个变量来自 **stdin 里 43972 字节的 V0 格式 startup context**，由 sandbox-gateway 递入。三条旁证：`environment-manager` 二进制里 grep 不到该串；容器内没有任何文件设置它；`~/.claude/launcher-settings.json` 里也没有（那份只有 SessionStart/Stop 两个 hook 和 `permissions.allow: ["Skill"]`）。

### 2. `cloud_default` 正解

`CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=cloud_default`——**它是环境类型名，不是什么"运行时重置机制"**。控制面为这个环境类型配了一组固定 env，`SKIP_PLUGIN_MARKETPLACE=true` 是其成员。§八.1 转述 issue 的「设成环境变量不生效，cloud_default 会在运行时重置」，方向对（容器内确实改不动），机理描述错，此处更正。

### 3. 由此改判：环境变量实验变成几乎免费，应当**先做**

§八.8 把「UI 里设 `SKIP_PLUGIN_MARKETPLACE=false`」和「重建整机」绑成一次实验。现在有了**直接可观测量**：UI 配的变量若能进 startup context，新会话里 `echo $SKIP_PLUGIN_MARKETPLACE` 就是 `false`，上面那行日志也会跟着变。**这不需要重建快照**（改环境变量只影响每次会话的 startup context）。

而且若真能翻成 false，很可能**不必改 setup 脚本**：账户面 superpowers 本就 enabled（§七.1），flag 一关，正常插件解析流程可能自行到位。

**修订后的实验顺序：**

1. 只在 UI 环境变量里加 `SKIP_PLUGIN_MARKETPLACE=false`，开新会话，跑：
   ```sh
   echo "$SKIP_PLUGIN_MARKETPLACE"
   grep -o 'startup_context_env_var_keys.*' /tmp/environment-manager.out | head -1
   ls /root/.claude/plugins 2>&1
   ```
   - 变成 `false` → 用户变量能盖过平台变量；再看插件是否自动到位（到位即完结）。
   - 仍是 `true` → 用户变量盖不过平台默认，挂载期 flag 无解；再决定要不要花那次重建。
2. 重建放第 2 步，**知道 flag 结局之后再做**。

### 4. 顺带澄清的三件事

- **§八.8 的「`claude` 可能不在 setup 时的 PATH」风险基本撤销。** 日志显示 UI setup 脚本是作为 **init script 跑在一个完整的 `setup-only` 会话里**（`Running init script` 15:50:48.15 → `Successfully executed init script` 15:50:54.12，**5.97 秒**），拉起它的是**同一个** `/bin/sh -c` 引导，而那条引导第一件事就是建 `claude` 符号链接。故 setup 时点 `claude` 在 PATH。绝对路径回落仍已加上（两行的事），但它不再是可能让方案静默空转的头号风险。**setup 预算也随之确认宽裕**：5 分钟额度只用了 6 秒。
- **`Running init script` 在整段日志里只出现一次**（就是建环境那次）。这独立证实了 CLAUDE.md 那句「setup 脚本不会被自动调用，云端会话开场必须手动跑 `--mode session`」。
- **`/tmp/environment-manager.out` 里只有建环境那次和本次会话**，§七/§八 那次会话同样查无此条——与 `/var/log/claude-cloud-setup.log` 完全同一模式，是 §八.6 快照模型的**第二条独立证据**（而且这次是平台自己写的文件，不是我们的脚本）。

另记一处读数分歧，免得后人踩：`CLAUDE_CODE_VERSION=2.1.42`，而 `claude --version` 报 `2.1.220`。两者都是真的但来源不同，**判断 CLI 行为（如 §八.2 的保留名守卫）要以 `claude --version` 为准**，别信那个环境变量。

### 5. 取证已固化进 `.claude/cloud-setup.sh` §1.4

上面这些是靠会话内手工走 `/proc` 得到的，**而 setup 时点的进程/环境上下文在任何会话里都看不到**（那是另一次启动）。故新增 `capture_forensics()`，`setup`/`session` 两模式都跑、**最先跑**（纯只读，拍下"刚到达"的原始现场），结果写进 `/var/log/claude-cloud-setup.log`——setup 时点的写入是唯一能跨会话存活的位置，两个模式的记录叠在同一文件里可直接对照。

捕获项按「要回答哪个待决问题」挑选，不是无差别 dump：

| 捕获 | 回答的问题 |
|---|---|
| 父进程链（pid / env 数 / cmdline） | 注入层在哪一环；setup 时的引导与会话时是否同一条 |
| 本进程可见变量**名**全集 | **UI 配的自定义环境变量到底有没有到达**（§九.3 的实验就靠这个判） |
| 白名单变量的值（8 个，均非机密） | flag、同步开关、环境类型、CLI 版本的实际取值 |
| `command -v claude` + 镜像内绝对路径 | setup 时点 CLI 可用性（§八.8 风险 1） |
| `~/.claude`、`/opt/node22/bin/claude` 的 mtime | 机械判别「哪些是快照带来的、哪些是本次会话铺的」（§八.6 的 skills 1→8 就是这么反推的） |

**两条设计约束，改动时别破坏：**

1. **放在 `cloud-setup.sh` 而不是 UI 脚本。** 进程链在两者里是同一条（后者是前者的父进程），但放仓库可走 git 演进、随时改、**不触发整机重建**；放 UI 文本框每改一次取证逻辑就烧一次快照。UI 脚本现有的自述上下文已是「仓库探测失败时也有记录」的兜底。
2. **只打变量名，值只走白名单。** env 里有 `AWS_SECRET_ACCESS_KEY`/`GH_TOKEN`/`CLOUDSDK_AUTH_ACCESS_TOKEN` 等，名字本身无害，值绝不能进日志。

**踩到并已修的坑**（首次试跑即复现）：`claude` 进程的 cmdline 里有 `--append-system-prompt`，**整份系统提示词就在参数内且含大量换行**；只做 `tr '\0' ' '` 的话 `cut -c1-170` 仅截掉第一行，其余整篇原样流进日志。必须把换行一起压成空格再截断。`env | cut -d= -f1` 有同类问题（多行值的续行会被当成变量名打出来），已改为先按 `^[A-Za-z_][A-Za-z0-9_]*=` 过滤。落盘日志已核对无残留。

### 6. `ensure_plugins` 同批修正

- **新增 `plugins_prestate=` 行**：本函数跑在 `inspect_user_config` 之前，报告里的 `user_plugins_installed` 永远是**安装后**读数，拿它判留存必然误判（§八.6 就是靠手工先拍照才判出来的）。此后由脚本自己记安装前状态。
- **`claude` 绝对路径回落**：`command -v` 落空时用 `/opt/claude-code/bin/claude`。
- **timeout 90s/次**（原 180 + 240×2 = 660s，超 5 分钟预算一倍；实测全程约 8s）。
- **告警按模式分措辞**：session 模式补装明说「既不对本会话生效，也不会留到下个会话」，不再给人 false green。是否把 session 分支彻底去掉仍未定，暂留（万一哪天 `~/.claude` 变成留存的）。

---

## 附录：复现命令

```bash
echo "$CLAUDE_CODE_REMOTE"; pwd; id -un; python3 -V; uv --version
ls -la work/; cat work/setup-baseline.txt work/setup-pytest.log
cat /var/log/claude-cloud-setup.log
grep -c 'mode=session' /var/log/claude-cloud-setup.log        # 手动跑之前应为 0
check-tools
git log --oneline -5; git remote -v; git status
git tag -l; cat .git/shallow; git rev-list --count HEAD       # 浅克隆 / 无 tag
git fetch --dry-run -v; git push --dry-run -v -u origin <branch>
bash .claude/cloud-setup.sh --mode session; echo "exit=$?"
python3 -c "import json;d=json.load(open('/root/.claude.json'));print(d['projects']['/home/user/Zndnovel']['hasTrustDialogAccepted'])"
grep -E 'hook_spawn|load_plugin_hooks|settings_load' "$CLAUDE_CODE_DIAGNOSTICS_FILE"
for v in SKIP_PLUGIN_MARKETPLACE CLAUDE_CODE_SYNC_SKILLS IS_SANDBOX; do echo "$v=${!v}"; done
```

§七 补记的复现（bash 部分）：

```bash
ls -la /root/.claude/skills/ /root/.claude/plugins/    # 后者应报 No such file
grep -rn "superpowers:" --include="*.md" .             # 仓库内悬空引用
```

其余为工具调用，非 bash：`ListPlugins`、`ListSkills`、`SearchSkills([...])`、
`Skill(superpowers:executing-plans)` / `Skill(superpowers:finishing-a-development-branch)` / `Skill(executing-plans)`。

§八.6–8 的复现。**次序要紧**：前三条必须在跑 `cloud-setup.sh` 之前执行，否则 `ensure_plugins`
会补装，留存与否就再也分不出来了。

```bash
# —— A 判定：必须先拍照 ——
ls -la /root/.claude/plugins/ ; cat /root/.claude/settings.json      # 应双双 No such file
find /root/.claude/plugins -name SKILL.md 2>/dev/null | wc -l        # 应为 0
bash .claude/cloud-setup.sh --mode session                           # 看走的是安装分支还是「已在位…跳过」

# —— 根因：同一日志文件里 setup 时点写入存活、会话时点写入消失 ——
grep -nE '=== claude cloud setup 报告|generated_by' /var/log/claude-cloud-setup.log
stat -c '%y  %n' /root/.claude/plugins /root/.claude/skills /root/.claude/settings.json /home/user/Zndnovel/work
git log --oneline -1                                                 # 快照里的头，非远端最新

# —— B 判定：静态引用图核验 ——
P=/root/.claude/plugins/cache/claude-plugins-official/superpowers/6.2.0
grep -rhoE 'superpowers:[a-z0-9-]+' "$P/skills/" | sort | uniq -c | sort -rn
for t in $(grep -rhoE 'superpowers:[a-z0-9-]+' "$P/skills/" | sed 's/^superpowers://' | sort -u); do
  [ -f "$P/skills/$t/SKILL.md" ] && echo "OK $t" || echo "MISS $t"; done
grep -nE 'superpowers:' "$P/skills/executing-plans/SKILL.md"

# —— 第 4 问：本插件不提供 agent 类型 ——
ls "$P/agents/" ; find "$P/.agents" -type f ; grep -rn 'subagent_type' "$P/skills/"
```

§九 的复现。**注意 cmdline 里嵌着整份系统提示词**，务必连换行一起压掉再截断，
否则会把它整篇打进日志（首次试跑即中招）：

```bash
# 父进程链 + 每环 env 数（变量在「2 → 几十」的那一跳被注入）
p=$$; while [ -n "$p" ] && [ "$p" != 0 ]; do
  printf 'pid=%s envn=%s cmd=%s\n' "$p" \
    "$(tr '\0' '\n' < /proc/$p/environ | grep -cE '^[A-Za-z_][A-Za-z0-9_]*=')" \
    "$(tr '\0\n\r\t' '    ' < /proc/$p/cmdline | cut -c1-170)"
  p=$(awk '{print $4}' /proc/$p/stat); done
tr '\0' '\n' < /proc/1/environ                        # microVM init：只有 HOME/TERM

# 控制面递进来的那 20 个变量（直供词）
grep -o 'startup_context_env_var_keys.*' /tmp/environment-manager.out | head -1
grep -nE 'Running init script|Successfully executed init script' /tmp/environment-manager.out

# 容器内确实没人设它
strings -a /opt/env-runner/environment-manager | grep SKIP_PLUGIN_MARKETPLACE   # 空
grep -rl SKIP_PLUGIN_MARKETPLACE /opt /usr/local/bin /etc /root/.claude          # 只命中 transcript

claude --version; echo "$CLAUDE_CODE_VERSION"          # 2.1.220 vs 2.1.42，以前者为准
```

§九.5 之后，上述取证由 `bash .claude/cloud-setup.sh --mode session` 自动留档，
读 `/var/log/claude-cloud-setup.log` 里的 `--- 现场取证 ---` 段即可。
