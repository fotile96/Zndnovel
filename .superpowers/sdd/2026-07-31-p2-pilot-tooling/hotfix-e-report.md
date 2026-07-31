# Hotfix E 报告：`lane_setup.py` 在纯克隆里的鸡生蛋崩溃

## 摘要

用户接下来要在 Claude Code 云端环境跑 opus 车道试点。控制器用 `git archive HEAD | tar -x`
精确模拟一次纯克隆（＝云端拿到的内容）验证首条命令，发现直接崩溃：

```
uv run python tools/lane_setup.py --lane opus --model opus --effort max --append-model-id claude-opus-5
→ FileNotFoundError: .../pilot/lanes/fable/skeleton/cards.zh.yaml
```

根因：`main()` 在 `setup()` 之后调 `record()`，而 `record()` 对 `lanes_root` 下**全部**含
`lane.json` 的车道目录取 `freeze_hashes()`。云端克隆里 `pilot/lanes/` 只有三个入库文件
（`opus/lane.json`、`fable/lane.json`、`pilot-manifest.json`），两条车道的 `data/` 符号链接
与 `skeleton/`+`glossary/` 冻结拷贝都要靠 `lane_setup` 本地重建（按设计不入库，见 `.gitignore`
第 17–31 行）。先建 opus 时 fable 尚未重建 → `freeze_hashes(fable)` 抛 `FileNotFoundError` →
未被捕获，整条命令崩溃。反之亦然——两条车道互为鸡生蛋，纯克隆里 `lane_setup` 完全不可用。

对比：孪生函数 `verify()` 在 Task 5 修复轮已经加了 `try/except FileNotFoundError`（跳过损坏
车道、记一条漂移描述、继续查其余车道），但那轮只覆盖了 `verify()`，`record()` 没有同步。

修复已落地、补测试全绿、突变验证确认测试有判别力、并在 `/tmp` 隔离的纯克隆里端到端复现
原始崩溃命令 + 确认修复后成功。

---

## 修法与落地位置

`tools/lane_setup.py::record()`（第 88–132 行）：把原来的一行 dict comprehension

```python
fresh = {p.name: freeze_hashes(p, repo)
         for p in sorted(lanes_root.iterdir())
         if p.is_dir() and (p / "lane.json").exists()}
```

改成显式循环 + `try/except FileNotFoundError`：

```python
fresh = {}
for p in sorted(lanes_root.iterdir()):
    if not (p.is_dir() and (p / "lane.json").exists()):
        continue
    try:
        fresh[p.name] = freeze_hashes(p, repo)
    except FileNotFoundError as e:
        # 纯克隆场景（云端拿到的内容）：pilot/lanes/ 下只有各车道入库的
        # lane.json，data/ 符号链接与 skeleton/glossary 冻结拷贝要靠
        # setup() 在本地重建。两条车道互为鸡生蛋——先建一条时另一条尚未
        # 重建，freeze_hashes 会在这里触底。record() 是"记录本次搭建结果"
        # 的入口，不是漂移安全网，但同样不该让一条车道的缺失拖垮整条命令：
        # 跳过该车道、continue 处理其余车道。注意 merged 起点是
        # dict(existing)（见下），跳过只是不更新——manifest 里该车道原有
        # 记录原样保留，不会被这次跳过抹掉。
        print(f"跳过 {p.name}：车道尚未搭建或冻结文件缺失（{e}）",
              file=sys.stderr)
        continue
merged = dict(existing)
```

其余语义不变：`merged = dict(existing)` 起点保持不动，后续 `for lane, h in fresh.items()` 循环
（已记录车道哈希变化仍拒绝、`force` 逻辑、非 `"lanes"` 顶层键保留）完全未改。**关键语义确认**：
跳过的车道根本不会进 `fresh`，所以既不会触发下面 `lane in existing` 的漂移检查，也不会覆盖
`merged[lane]`——`merged` 从 `existing` 继承的旧记录原样留在返回值和写回的 manifest 里。这正是
云端场景所需：重建 opus 并重记其哈希，fable 的既有记录原样保留，直到 fable 也被重建后再补记。

`sys` 已在文件顶部 import（第 16 行），无需新增依赖。

---

## TDD Evidence

### RED

新增两条测试到 `tests/test_lane_setup.py`（改代码前跑，针对当时仍是崩溃状态的 `record()`）：

```
$ uv run pytest -q tests/test_lane_setup.py -k "skip"
...
FAILED tests/test_lane_setup.py::test_record_skips_lane_with_missing_frozen_files_without_raising
    - FileNotFoundError: [Errno 2] No such file or directory: '.../lanes/fable/skeleton/cards.zh.yaml'
FAILED tests/test_lane_setup.py::test_record_skip_prints_diagnostic_to_stderr
    - FileNotFoundError: [Errno 2] No such file or directory: '.../lanes/fable/skeleton/cards.zh.yaml'
2 failed, 23 deselected in 0.18s
```

两条测试都以与用户报告的原始错误**逐字相同**的异常类型/触底路径失败，确认测试命中了真实缺陷
而非笔误。

### GREEN

实现修复后：

```
$ uv run pytest -q tests/test_lane_setup.py
.........................                                                [100%]
25 passed in 0.10s

$ uv run pytest -q
........................................................................ [ 34%]
........................................................................ [ 69%]
................................................................         [100%]
208 passed in 2.64s
```

（改动前既有 206 条全绿，净增 2 条新测试，全量 208 条无回归。）

### 新增测试

`tests/test_lane_setup.py`：
- `test_record_skips_lane_with_missing_frozen_files_without_raising`：构造纯克隆场景
  ——opus 完整 `setup()`，fable 只有 `lane.json`（模拟未重建），且 manifest 里 fable 已有一条
  "旧记录"（哈希用固定占位符，模拟此前某次成功 `record()` 留下的基准）。断言 `record()` 不抛
  异常、返回值 `merged["opus"]` 等于当前实际哈希、`merged["fable"]` 与预置的旧记录逐字相等
  （未被抹掉）。
- `test_record_skip_prints_diagnostic_to_stderr`：同样构造场景，用 `capsys` 断言 stderr 输出
  含车道名 `"fable"`。

---

## 突变验证

按 spec 要求，把新加的 `try/except` 临时改回原来的一行 dict comprehension（未提交，仅本地
临时改动），重跑针对性测试：

```python
# MUTATION（临时，验证后已还原）：
fresh = {p.name: freeze_hashes(p, repo)
         for p in sorted(lanes_root.iterdir())
         if p.is_dir() and (p / "lane.json").exists()}
merged = dict(existing)
```

```
$ uv run pytest -q tests/test_lane_setup.py -k "skip"
...
FAILED tests/test_lane_setup.py::test_record_skips_lane_with_missing_frozen_files_without_raising
    - FileNotFoundError: [Errno 2] No such file or directory:
      '/tmp/pytest-.../lanes/fable/skeleton/cards.zh.yaml'
FAILED tests/test_lane_setup.py::test_record_skip_prints_diagnostic_to_stderr
    - FileNotFoundError: [Errno 2] No such file or directory:
      '/tmp/pytest-.../lanes/fable/skeleton/cards.zh.yaml'
2 failed, 23 deselected in 0.14s
```

两条新测试确认转红，且失败原因与修复前的原始崩溃一致（同一 `FileNotFoundError`，同一触底
路径），证明测试确实在检验这段 `try/except` 本身，不是摆设。

还原后（`cp` 回备份，`diff` 确认与修复版逐字相同）：

```
$ uv run pytest -q
208 passed in 2.64s
```

---

## 端到端纯克隆复现验证（本次修复的意义所在）

先在主仓库把修复 commit 掉（`407e879`），再用 `git archive HEAD | tar -x` 在 `/tmp` 造一份纯
克隆，确认其 `pilot/lanes/` 内容与用户报告的现象完全一致：

```
$ find /tmp/znd_clone_e2e/pilot/lanes -maxdepth 3 | sort
/tmp/znd_clone_e2e/pilot/lanes
/tmp/znd_clone_e2e/pilot/lanes/fable
/tmp/znd_clone_e2e/pilot/lanes/fable/lane.json
/tmp/znd_clone_e2e/pilot/lanes/opus
/tmp/znd_clone_e2e/pilot/lanes/opus/lane.json
/tmp/znd_clone_e2e/pilot/lanes/pilot-manifest.json
```

（`pilot-manifest.json` 里已带两条车道此前真实记录的哈希——这是仓库当前已入库的状态，非本次
构造。）

### 命令 1：建 opus 车道

```
$ cd /tmp/znd_clone_e2e && uv run python tools/lane_setup.py --lane opus --model opus --effort max --append-model-id claude-opus-5
```

实际输出：

```
Using CPython 3.14.6 interpreter at: /usr/lib/python-exec/python3.14/python3
Creating virtual environment at: .venv
warning: Failed to hardlink files; falling back to full copy. ...
Installed 7 packages in 19ms
跳过 fable：车道尚未搭建或冻结文件缺失（[Errno 2] No such file or directory: '/tmp/znd_clone_e2e/pilot/lanes/fable/skeleton/cards.zh.yaml'）
/tmp/znd_clone_e2e/pilot/lanes/opus: 车道就绪，冻结哈希已记入 /tmp/znd_clone_e2e/pilot/lanes/pilot-manifest.json
EXIT_CODE=0
```

**结论**：命令成功（exit 0），opus 被重建并记入 manifest；fable 打印了可诊断的跳过提示，没有
崩溃整条命令——这正是原始 bug 报告里失败的那一步，现已修复。

进一步核实 manifest 内容：opus 的哈希与 `git archive` 携带的、此前已记录的原值逐字相同（本就
是零漂移的纯克隆，符合预期）；fable 的既有记录原样保留、完全未被这次调用触碰。

### 命令 2：`--verify`

```
$ cd /tmp/znd_clone_e2e && uv run python tools/lane_setup.py --verify
```

实际输出：

```
fable: 冻结文件缺失或车道损坏（[Errno 2] No such file or directory: '/tmp/znd_clone_e2e/pilot/lanes/fable/skeleton/cards.zh.yaml'）
EXIT_CODE=1
```

**结论**：opus 无漂移报告（未出现在输出里，符合预期）；fable 因未重建被报为「冻结文件缺失或
车道损坏」——**这是正确行为**（verify 是漂移/损坏安全网，如实反映 fable 尚未在本地重建的事
实），未做任何消除该行的处理。

验证完毕后清理了 `/tmp/znd_clone_e2e`，未留存任何痕迹；仓库内真实的 `pilot/lanes/opus`、
`pilot/lanes/fable` 全程未被触碰（`git status --porcelain` 全程不含它们）。

---

## Files Changed

- `tools/lane_setup.py`：`record()` 里 `freeze_hashes()` 调用改为显式循环 + `try/except
  FileNotFoundError`，跳过车道时打印 stderr 提示并 `continue`；其余逻辑（漂移拒绝、`force`、
  非 `"lanes"` 顶层键保留）不变。
- `tests/test_lane_setup.py`：新增 2 条测试
  （`test_record_skips_lane_with_missing_frozen_files_without_raising`、
  `test_record_skip_prints_diagnostic_to_stderr`）。

commit：`407e879 fix: record() 跳过纯克隆里尚未重建的车道而非崩溃`

## Self-Review

- **Completeness**：修复位置与 spec 描述完全一致（`record()` 与 `verify()` 对齐）；两条要求
  的测试场景（不抛异常场景、stderr 提示场景）均补齐；三条验证要求（全量 pytest、突变验证、
  端到端纯克隆复现）均已执行并留痕。
- **Quality**：跳过分支的注释显式写明"跳过不抹除既有记录"的机制依据（`merged` 起点是
  `dict(existing)`，跳过的车道根本不进 `fresh`），呼应 spec 要求的"请确认这一点成立并在注释里
  写明"。未改动 `record()` 其余语义——已记录车道哈希变化仍拒绝（除非 `force=True`）、非
  `"lanes"` 顶层键保留，均由既有回归测试（`test_record_refuses_to_overwrite_when_frozen_hash_
  changed_without_force`、`test_record_preserves_other_top_level_manifest_keys` 等）覆盖，
  全量套件里这些测试依旧绿。
- **Discipline**：未新增第三方依赖（仅用已导入的 `sys`）；未触碰
  `lua_scripts/`/`png/`/`skeleton/`/`glossary/`/`analysis/`；仓库内真实的
  `pilot/lanes/opus`、`pilot/lanes/fable` 全程未被触碰，验证一律在 `/tmp` 隔离副本进行；
  commit message 为中文摘要 + 规范 trailer。
- **Testing**：先红后绿证据完整（2 failed → 208 passed）；突变验证做了且证据完整（还原后
  diff 确认与提交版逐字相同）；端到端复现用真实 `git archive` 纯克隆，两条命令的实际输出均
  记录在案，且如实保留了 fable 的"冻结文件缺失"报告（未为了好看的输出而消除它）。

## Concerns

- 会话开场时 `.superpowers/sdd/2026-07-31-p2-pilot-tooling/progress.md` 处于未提交修改状态，
  本次未touch；另外发现 `.claude/cloud-setup.sh` 也有一份与本任务无关的未提交修改（似为其他
  会话遗留），本次同样未触碰、未纳入 commit，仅在此报告中记录以免被误认为本次修复的一部分。
- 无其余遗留问题：纯克隆里 `lane_setup.py --lane <X> ...` 与 `--verify` 两条命令均已验证在
  云端预期场景（先建一条车道，另一条车道尚未重建）下按设计工作。
