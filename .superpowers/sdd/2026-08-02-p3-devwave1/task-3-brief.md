### Task 3: F7 行序——ledger `line` 字段 + timeline 单元内行序

**Files:**
- Modify: `tools/build_ledger.py`、`data/ledger.jsonl`（再生成）、可能 `tools/gen_timeline.py`（视调查结果）
- Test: `tests/test_build_ledger.py`（追加）、可能 `tests/test_gen_timeline.py`
- Modify: `docs/ops/p3-production-runbook.md`（§4 末尾补「段边界数据再生成」两句）

**Interfaces:**
- Consumes: `build_ledger.parse_vms_lines(stem, text)`（`for line in text.splitlines()` 循环，无行号）、`build()` 里 `ledger.sort(key=lambda r: r["id"])`、`build_ledger --check` 门（再生成与入库文件比对）。P2 缺陷 F7：47 处相邻逆序 / 16529 对（0.28%），例证 id 17181 在 lua 第 234 行却排到其单元第 58 位。
- Produces: ledger 行新增 `"line": <lua 行号>` 字段（**全局排序仍按 id，行序不变**——只加字段）；timeline 单元内 id 排序改按 `(file, line)`（代码落地、**数据再生留段边界**）。

**本任务的生产安全判据（先跑再改）**：`data/ledger.jsonl` 被生产实时读取（车道符号链接）。加字段是否影响在产批次，取决于 build_context 是否把 ledger 行原样带进产物。判据实验做在**钉死的生产树**上：

- [ ] **Step 1: 生产安全预检（决定本任务走主仓还是分支）**

```bash
# 用生产树对一个 SEG-1 尚未翻译的批次（从车道 forward 现状推一个，如 b62）生成 ctx 快照 A
uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 62 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus
cp pilot/lanes/opus/work/ctx/batch_62/context.md /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/ctx-A.md
cp pilot/lanes/opus/work/ctx/batch_62/source.jsonl /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/src-A.jsonl
```

然后**先只在本地改代码并再生 ledger 到临时文件**（不覆盖 `data/`），用 `ZND_DATA` 指向含新 ledger 的临时数据目录（其余文件符号链接原 data/）再跑一次生产树 build_context，得快照 B。比对：
- `context.md` A vs B **逐字节相同** → 加字段对在产批次无影响，**本任务直接落 main**（Step 2 起）。
- 有差异 → **停**：把差异样例写进报告，本任务全部改动改落分支 `fix/f7-ledger-line`（同样走完全部步骤，但不合 main），报告注明「段边界合并」，plan 余下任务照常在 main 进行。
- 实验产物（batch_62 的 ctx 目录与临时数据目录）用后删除，`git status` 干净。

- [ ] **Step 2: 写失败测试**

在 `tests/test_build_ledger.py` 追加（沿用该文件既有 fixture 风格）：

```python
def test_rows_carry_lua_line_numbers():
    text = 'v0 = function()\n  vms(10, "NONVOICE", "甲")\n  vms(11, "NONVOICE", "乙")\nend\n'
    rows = parse_vms_lines("snr_test", text)
    assert [r["line"] for r in rows] == [2, 3]


def test_global_sort_still_by_id_line_is_additive():
    # id 逆序出现在文件里：全局排序仍按 id（行序不变约定），line 忠实记录原行号
    text = 'v0 = function()\n  vms(20, "NONVOICE", "乙")\n  vms(19, "NONVOICE", "甲")\nend\n'
    ledger, _ = build_from_text({"snr_test": text})   # 若无此 helper，按该文件既有构造方式改写
    assert [r["id"] for r in ledger] == [19, 20]
    assert [r["line"] for r in ledger] == [3, 2]
```

- [ ] **Step 3: 实现 + 再生 ledger**

`parse_vms_lines` 的循环改 `for lineno, line in enumerate(text.splitlines(), 1):`，row 增 `"line": lineno`。`build()` 的 `ledger.sort(key=lambda r: r["id"])` **保持不变**。再生成：

```bash
uv run python tools/build_ledger.py           # 按该工具实际 CLI 写盘 data/ledger.jsonl
uv run python tools/build_ledger.py --check   # 期望 check: OK
```

验证再生只是加字段：

```bash
uv run python -c "
import json, subprocess
new=[json.loads(l) for l in open('data/ledger.jsonl',encoding='utf-8')]
old=[json.loads(l) for l in subprocess.run(['git','show','HEAD:data/ledger.jsonl'],capture_output=True,text=True).stdout.splitlines()]
assert len(new)==len(old)
assert all(o['id']==n['id'] for o,n in zip(old,new)), 'id 顺序变了！停'
assert all({k:v for k,v in n.items() if k!='line'}==o for o,n in zip(old,new)), '有 line 之外的字段变化！停'
print('OK：仅新增 line 字段，顺序与其余字段逐行一致')
"
```

- [ ] **Step 4: timeline 单元内行序（调查后落码）**

读 `tools/gen_timeline.py`，确认单元内 id 序列的排序来源。若其排序依赖 ledger 文件序（即按 id）：改为按 `(file, line)` 排（`line` 字段现已存在），补一条测试（构造一个含后补行的两行单元，断言输出序为行序）。**不再生成 `data/timeline.jsonl`**——在报告与 runbook §4 末尾补两句：

> 段边界数据再生成：`gen_timeline`（F7 行序）落码于 <commit>，`data/timeline.jsonl` 的再生成属生产条件变更，与工具滚 tag 同流程——段边界执行 `uv run python tools/gen_timeline.py`、核对差异仅为 47 处已知逆序的修正、随 canary 结论一并提交。

若调查发现排序不在 gen_timeline（在 build_context 运行时或其他处），按实际位置落码，同样原则：**代码现在落，行为变化经钉死树在段边界生效/数据再生留段边界**，报告写明实际位置与理由。

- [ ] **Step 5: 全量测试 + commit**

Run: `uv run pytest -q` → 244 passed（Step 4 至少含 1 测试；以实际数为准，报告记录）。

```bash
git add tools/build_ledger.py data/ledger.jsonl tests/test_build_ledger.py
git commit -m "fix: ledger 增记 lua 行号 line 字段（F7 前半，全局序不变）"
git add tools/gen_timeline.py tests/test_gen_timeline.py docs/ops/p3-production-runbook.md
git commit -m "fix: timeline 单元内按 (file,line) 行序（F7 后半，数据再生留段边界）"
```

（若 Step 1 判定走分支：两个 commit 落 `fix/f7-ledger-line`，不合 main，报告写明。）

---

