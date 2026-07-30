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
- `ListPlugins` 返回 `{"results":[]}`；`/root/.claude/plugins` 不存在；全盘无 `claude-plugins-official` 缓存目录。
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
2. 若 SDD 流程依赖 `superpowers` 插件，需另找载体（`SKIP_PLUGIN_MARKETPLACE=true` 是环境级、不可由仓库配置绕过）。
3. `cloud-ui-setup.sh` 的上下文探测行若真想留证，得自己写文件而不是靠 stdout。
4. CLAUDE.md 第 1/2/4/9/11/14 条描述待按本记录订正。

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
