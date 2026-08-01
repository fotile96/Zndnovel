# Task 6 报告：生产 worktree 钉死 + P3 运行手册

## 前置状态

```
$ git status
On branch main
Your branch is ahead of 'origin/main' by 89 commits.
nothing to commit, working tree clean

$ git rev-parse HEAD
a4fb60307eed9de4bdaad16f4c14597ce49b1885

$ git worktree list
/Users/fotile96/Zndnovel  a4fb603 [main]

$ ls docs/ops/
cloud-acceptance-2026-07-30.md

$ ls -la /Users/fotile96/ | grep -i Zndnovel
drwxr-xr-x  24 fotile96  staff     768 Aug  1 14:34 Zndnovel
```
（`/Users/fotile96/Zndnovel-prod` 尚不存在，无需处理冲突。）

## Step 1: 写 runbook

按 brief 逐字写入 `docs/ops/p3-production-runbook.md`（66 行，未改写措辞，未写入外层 ```markdown 围栏）。

## Step 2: commit runbook

```
$ git add docs/ops/p3-production-runbook.md
$ git status --short
A  docs/ops/p3-production-runbook.md
$ git commit -m "docs: P3 生产运行手册（并行纪律/自检/canary 升级闸/裁决清单）"
[main fc0e284] docs: P3 生产运行手册（并行纪律/自检/canary 升级闸/裁决清单）
 1 file changed, 66 insertions(+)
 create mode 100644 docs/ops/p3-production-runbook.md
```

commit 哈希：`fc0e28445a3293c6d76ac3065c3a4f142725dbed`

diff scope 核对（`a4fb603..fc0e284`）：仅 `docs/ops/p3-production-runbook.md`，66 insertions，无其他文件变更。

## Step 3: 打 tag 并建 worktree

```
$ git tag prod-run-v1
$ git worktree add ../Zndnovel-prod prod-run-v1
Preparing worktree (detached HEAD fc0e284)
HEAD is now at fc0e284 docs: P3 生产运行手册（并行纪律/自检/canary 升级闸/裁决清单）
```

无报错，worktree 建在仓库外 `/Users/fotile96/Zndnovel-prod`。

## Step 4: 验证 worktree

```
$ git -C /Users/fotile96/Zndnovel-prod describe --tags
prod-run-v1
```
符合预期。

```
$ cd /Users/fotile96/Zndnovel-prod && uv sync --locked
Using CPython 3.14.6 interpreter at: /opt/homebrew/opt/python@3.14/bin/python3.14
Creating virtual environment at: .venv
Resolved 9 packages in 18ms
Installed 7 packages in 10ms
 + iniconfig==2.3.0
 + packaging==26.2
 + pillow==12.3.0
 + pluggy==1.6.0
 + pygments==2.20.0
 + pytest==9.1.1
 + pyyaml==6.0.3
```
worktree 内独立 `.venv` 建立成功（未复用主仓 venv）。

```
$ uv run pytest -q
........................................................................ [ 32%]
........................................................................ [ 65%]
........................................................................ [ 98%]
...                                                                      [100%]
219 passed in 1.69s
```
219 passed，与基线一致。

## 收尾核对

```
$ git worktree list
/Users/fotile96/Zndnovel       fc0e284 [main]
/Users/fotile96/Zndnovel-prod  fc0e284 (detached HEAD)

$ git tag --list "prod-run*"
prod-run-v1

$ git status --short   (主仓)
(空，无未跟踪/未暂存变更)
```

## 偏差与处理

无偏差。所有步骤按 brief 顺序执行（先 commit 手册再打 tag/建 worktree），命令与手册正文逐字照抄。`.superpowers/sdd/2026-08-02-p3-ignition/` 下的工作文件未触碰、未提交（本报告文件本身除外，按任务要求写入该目录）。

## 结论

- 状态：DONE
- commit 哈希：`fc0e28445a3293c6d76ac3065c3a4f142725dbed`
- tag/worktree 验证：`prod-run-v1` 已建，`git -C ../Zndnovel-prod describe --tags` 输出 `prod-run-v1`，符合预期
- worktree 内 pytest：219 passed（与基线一致）
- 顾虑：无
