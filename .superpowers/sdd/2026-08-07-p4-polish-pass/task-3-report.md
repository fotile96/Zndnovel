# Task 3 报告：tools/polish_setup.py（SEG 冻结）

状态：**DONE**
Commit：见下方（提交时填入短哈希）

## 交付文件

- `tools/polish_setup.py`（新建）：`setup()` / `verify()` / `main()`（CLI）+ 内部辅助函数
  `_dir_for` / `_seg_entry` / `_seg_ids` / `_anchor_ids` / `_locked_payload` / `_copy_glossary` /
  `_copy_notes`。
- `tests/test_polish_setup.py`（新建）：brief Step 1 的 3 条核心断言逐字照抄，外加 9 条
  补充用例（覆盖 notes 按章拷贝/缺章告警、repo 隔离、batch 归属、glossary 快照、
  glossary_v 取最高版号、rulings.md 占位、verify 的两种异常路径）。

## 与 brief 的偏差

### 1.（用户已裁定）notes 拷贝改为按 `chapters` 列表，不按批号

brief 骨架写 `_copy_notes(Path(opus_data) / "notes", fz / "notes", lo, hi)`——按批号语义
不成立：`pilot/lanes/opus/data/notes/` 下是按章命名的 25 个文件（`s2s.md`/`crd.md`/…），
没有批号维度。按用户裁定实现为：

```python
def _copy_notes(notes_src: Path, notes_dst: Path, chapters) -> list:
    for ch in chapters:
        src = Path(notes_src) / f"{ch}.md"
        if src.exists():
            shutil.copy2(src, notes_dst / f"{ch}.md")
        else:
            missing.append(ch)
    if missing:
        print(f"!! 告警：...已跳过：{missing}", file=sys.stderr)
    return missing
```

调用处 `_copy_notes(opus_data / "notes", fz / "notes", seg["chapters"])`——`seg["chapters"]`
即 `config/segments.yaml` 段表条目自带的章节列表（如 seg1-s2 是 `[s2s, s2f, crd]`）。

缺章处理（"跳过并在返回/日志里说明，不要静默"的落地）：
1. **日志**：stderr 打印缺失章节清单。
2. **返回**：`setup()` 返回值仍是 `Path`（与 brief 签名一致），但缺失清单被写进同一次调用
   产出的 `manifest.json` 的 `notes_missing` 字段（`d / manifest.json` 与返回的 `d` 同一个
   目录，故"随返回值可查"）——不是新增返回类型，是把说明落进返回目录里的既有产物。

新增回归锁 `test_notes_not_batch_numbered`：断言 `frozen/notes/` 下不出现 `1.md`/`2.md`
这类批号命名的文件，钉住"不按批号拷贝"这一裁定。

### 2.（补充，非用户裁定，工程必要）`seg_dir()` 改为本模块内 `_dir_for(label, repo)`，不直接调用 `polishlib.seg_dir()`

`tools/polishlib.py` 现有实现（Task 2 落地）：

```python
def seg_dir(label) -> Path:
    return REPO / "pilot" / "polish" / label
```

`REPO` 来自 `pipelib`，是真实仓库根，**不接受 repo 覆盖**。brief 骨架里 `setup(label,
opus_data, repo=None)` 却要求 `repo` 参数能接管冻结目录的落点（测试全部传
`repo=mini_repo.root`）——若照抄骨架直接调用 `polishlib.seg_dir(label)`，测试会真的把
`frozen/`/`manifest.json` 写进本仓库真实的 `pilot/polish/segX/`，这正是本任务说明第 6 条
明令禁止的"对真实 SEG 跑 setup"的一种变体（只是段名换成了测试用的 `segX`，仍是脏写）。

处理：本模块自定义

```python
def _dir_for(label, repo) -> Path:
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label
```

`repo=None` 时退化到与 `polishlib.seg_dir()` 完全一致的路径（`REPO/pilot/polish/<label>`），
CLI 场景（`main()` 不传 repo）行为不变；测试传入 `repo=mini_repo.root` 时则完全落在
tmp_path 下。已用 `test_setup_never_touches_real_repo` 钉住：`setup()` 跑完后断言真实
`REPO / "pilot" / "polish" / "segX"` 不存在。

`polishlib.seg_dir()` 本身未改动（Task 2 已冻结，非本任务范围）。

## manifest.json 字段清单（实测落地）

```json
{
  "label": "segX",
  "batches": [1, 2],
  "glossary_v": 3,
  "files": {"frozen/source.jsonl": "<sha256>", "frozen/opus.jsonl": "<sha256>",
            "frozen/locked.json": "<sha256>", "frozen/rulings.md": "<sha256>",
            "frozen/glossary/active.json": "<sha256>", "...": "..."},
  "opus_at": {"forward_lines": 4, "patches_lines": 1,
              "forward_sha": "<sha256 of forward.jsonl>",
              "patches_sha": "<sha256 of patches.jsonl>"},
  "notes_missing": ["crd"],
  "ts": "2026-08-07T...+00:00"
}
```

- `files` 的 key 是相对 `pilot/polish/<label>/` 的路径（含 `frozen/` 前缀），逐文件
  `sha256_file()`——`rglob("*")` 递归覆盖 `frozen/` 下全部真实存在的文件（含
  `glossary/voices/*.md`、`notes/*.md`），不遗漏子目录。
  manifest.json 自身不在 `files` 里（自指不可能，写 manifest 时其内容尚未确定）。
- `opus_at.forward_sha` / `patches_sha`：`patches.jsonl` 不存在时（早期 SEG 尚无任何
  裁补丁）为 `None`，`patches_lines` 为 0——不视为异常。
- `notes_missing`：非空时才有实际意义，但字段始终写出（空列表也写，语义更明确：
  "本次检查过，没有缺"和"没做过这项检查"要能区分）。

## locked.json 格式（实测）

```json
{"ids": [11, 13], "why": {"11": "anchor", "13": "patched"}}
```

- `ids`：段内 id ∩（anchors 全部 item id ∪ opus 车道 patches.jsonl 已有 id），升序。
- `why`：JSON 对象键固定为字符串（`json.loads` 后 `locked["why"]["11"]`，不是
  `locked["why"][11]`——已在测试里按此形式断言，与 brief Step 1 给的断言写法一致）。
- 两者都命中时按用户裁定固定选 `"anchor"`（`_locked_payload` 里 `"anchor" if i in
  anchor_ids else "patched"`，anchor 判断在前，不依赖 set 遍历顺序，稳定可复现）。

## 跑测

```
$ uv run pytest -q tests/test_polish_setup.py
12 passed in 0.16s

$ uv run pytest -q   （全量）
583 passed in 3.06s   （基线 571 + 本任务 12 = 583，吻合）
```

## 变异自检（三个，逐一记录命令 + 红/绿实况 + 判断）

三次变异均只用 **Edit** 工具改动 `tools/polish_setup.py` 源码后立即用 Edit 改回原文本
（未用 `git checkout`/`restore`/`stash`），每次变异后单独跑最相关的测试文件确认。

### 变异①：locked 漏并 anchor 集

```python
locked_ids = set(ids) & (anchor_ids | patched_ids)
# 改为：
locked_ids = set(ids) & patched_ids   # 漏并 anchor_ids
```

命令：`uv run pytest -q tests/test_polish_setup.py::test_setup_freezes_and_locks`
结果：**RED**
```
assert {13} == {11, 13}
Extra items in the right set: 11
```
判断：命中。id=11 只是 anchor（不在 patches 里），漏并 anchor 集后从 `locked["ids"]`
里消失，测试如实抓住。已用 Edit 还原为 `(anchor_ids | patched_ids)`。

### 变异②：opus.jsonl 直接抄 forward，不走 resolve（忽略 patches）

```python
cur = resolve_map(fwd, pat)
# 改为：
cur = resolve_map(fwd, [])   # 不走 resolve 的补丁覆盖，直接用 forward 的原值
```

命令：`uv run pytest -q tests/test_polish_setup.py::test_opus_snapshot_is_resolved`
结果：**RED**
```
AssertionError: assert '补丁前文本' == '补丁后文本'
```
判断：命中。id=13 在 forward.jsonl 里是"补丁前文本"，patches.jsonl 有一条补丁改成
"补丁后文本"；忽略补丁后 `opus.jsonl` 里 13 的 zh 退回补丁前的旧文本，测试如实抓住。
已用 Edit 还原为 `resolve_map(fwd, pat)`。

### 变异③：verify() 恒返回 []

```python
def verify(label, repo=None) -> list:
    return []   # 插在函数体最前面，后面原逻辑变成死代码
    d = _dir_for(label, repo)
    ...
```

命令：`uv run pytest -q tests/test_polish_setup.py::test_verify_detects_drift tests/test_polish_setup.py::test_verify_missing_manifest_reports_not_raises tests/test_polish_setup.py::test_verify_missing_file_reported`
结果：**RED**（3 条全部失败）
```
FAILED test_verify_detects_drift - assert [] != []
FAILED test_verify_missing_manifest_reports_not_raises - assert [] != []
FAILED test_verify_missing_file_reported - assert ([])
```
判断：命中，且是三条独立测试同时抓住（漂移检测、manifest 缺失检测、frozen 内文件
被删检测），说明 verify() 的"假绿"面几乎没有测试盲区。已用 Edit 去掉插入的
`return []`，还原原实现。

## 变异自检小结

| 变异 | 首次结果 | 判断 | 处理 |
|---|---|---|---|
| ① locked 漏并 anchor 集 | RED | 命中 | 直接还原 |
| ② opus.jsonl 不走 resolve | RED | 命中 | 直接还原 |
| ③ verify 恒返回 [] | RED（3 条测试同时） | 命中 | 直接还原 |

三次变异全部一次性打红（没有出现 Task 2 那种"绿变异需要诊断"的情况），三次还原后
均以 `uv run pytest -q` 全量 583 passed 复核，且用 Read 复核过源码与变异前逐字一致。

## 最终验证

```
$ uv run pytest -q
583 passed in 2.92s

$ git status --short
 M .claude/settings.json      ← 其他会话未提交改动，全程未触碰
 M data/api_ledger.jsonl      ← 同上，全程未触碰
?? tests/test_polish_setup.py
?? tools/polish_setup.py
```

`git add` 仅显式列出 `tools/polish_setup.py` `tests/test_polish_setup.py`
`.superpowers/sdd/2026-08-07-p4-polish-pass/task-3-report.md` 三个路径（`task-3-report.md`
是入库携带的 SDD 证据，走 `-f` 一次），未用 `git add -A`/`.`，未触碰
`.claude/settings.json` 与 `data/api_ledger.jsonl`。仅写代码与测试，未对真实 SEG 跑
`setup()`——`pilot/polish/` 目录未被创建（`test_setup_never_touches_real_repo` 亦以断言
的形式钉住这一点）。
