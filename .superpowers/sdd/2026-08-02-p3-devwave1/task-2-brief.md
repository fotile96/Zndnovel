### Task 2: detect_collapse 降噪（F12 / F9 / F4）

**Files:**
- Modify: `tools/detect_collapse.py`
- Test: `tests/test_detect_collapse.py`（追加，不动既有测试）

**Interfaces:**
- Consumes: 现有 `KANA_RE = re.compile(r"[぀-ゟ゠-ヿ]")`（`:21`）、`_kana_ratio(zh, names)`（`:56`）、`scan(source_rows, draft_rows, names=(), kana_max, ratio_lo, ratio_hi)`（`:65`）、常量 `DUP_MIN_LEN=8` / `DUP_MIN_COUNT=3`（`:40-41`）。
- Produces: 三处向后兼容修改——
  - **F12**：`KANA_RE` 改为 `r"[぀-ゟァ-ヺヽ-ヿ]"`（片假名段起点从 ゠U+30A0 收窄到 ァU+30A1、止于 ヺU+30FA，再补 ヽ-ヿ；即剔除 ゠/・/ー 三个标点）。
  - **F9**：`_kana_ratio(zh, names, jp="")` 新增第三参：剔除角色名后，再把 zh 中**长度 ≤ `JP_QUOTE_MAX_LEN`（新常量，=6）且逐字出现在 jp 原文里**的假名连串剔除（作品内引用的日文原文＝合法假名）。长假名串即使出现在 jp 里也不剔（整行未译正是 C1 要抓的）。`scan()` 里 C1 调用改为 `_kana_ratio(zh, names, jp)`。
  - **F4**：`scan(..., dup_min_len=DUP_MIN_LEN, dup_min_count=DUP_MIN_COUNT)` 新增两参并在 C3 分支使用；`main()` 加 `--dup-min-len`/`--dup-min-count` 透传。
  - `canary.py` 调 `scan(source, draft, names)` 走默认值，**不需要改**；既有测试必须全部继续通过。

- [ ] **Step 1: 写失败测试**

在 `tests/test_detect_collapse.py` 追加：

```python
def test_f12_kana_punct_not_counted():
    # ・（U+30FB）项目符号、ー（U+30FC）、゠（U+30A0）不再计入假名比
    src = [{"id": 1, "jp": "・項目一・項目二"}]
    drf = [{"id": 1, "zh": "・条目一・条目二——ー゠"}]
    assert scan(src, drf) == []


def test_f9_quoted_jp_kana_exempt_but_untranslated_still_caught():
    src = [
        {"id": 1, "jp": "「に」「ん」「げ」「ん」――にんげん、と読めた。"},
        {"id": 2, "jp": "ずっとまえから、すきでした。ほんとうです。"},
    ]
    drf = [
        # 钱仙拼字：引用原文假名（短串，均在 jp 中）→ 不报 C1
        {"id": 1, "zh": "「に」「ん」「げ」「ん」――拼出来是「にんげん」，人类。"},
        # 整行未译（长假名串）→ 仍报 C1
        {"id": 2, "zh": "ずっとまえから、すきでした。ほんとうです。"},
    ]
    hits = scan(src, drf)
    assert [h["id"] for h in hits if h["rule"] == "C1"] == [2]


def test_f4_dup_thresholds_via_params():
    src = [{"id": i, "jp": "x" * 10} for i in (1, 2)]
    drf = [{"id": i, "zh": "同样的八字译文"} for i in (1, 2)]   # 7 字 ×2 次：默认不报
    assert [h for h in scan(src, drf) if h["rule"] == "C3"] == []
    hits = scan(src, drf, dup_min_len=6, dup_min_count=2)       # 收紧后报
    assert len([h for h in hits if h["rule"] == "C3"]) == 2
```

（`scan` 的既有 import 沿用该测试文件现有写法。）

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_detect_collapse.py -v -k 'f12 or f9 or f4'`
Expected: 3 FAIL（第一条因 ・ 计入假名、第二条 id 1 被误报、第三条 `unexpected keyword argument`）。

- [ ] **Step 3: 实现**

`tools/detect_collapse.py` 四处：

(a) `KANA_RE = re.compile(r"[぀-ゟァ-ヺヽ-ヿ]")`，行上注释注明 v2 剔除 ゠(U+30A0)/・(U+30FB)/ー(U+30FC) 三个片假名标点（F12，P2 batch 31 实测 4/6 行因 ・ 误报）。

(b) 新常量 + `_kana_ratio` 扩参：

```python
# F9：作品内引用的日文原文（钱仙拼字、五十音教学等）在译文中合法保留假名。
# 判据：假名连串长度 ≤ 本值且逐字出现在同行 jp 原文中 → 视为引用、不计入假名比。
# 长串即使出现在 jp 中也不豁免——整行未译（zh≈jp）正是 C1 的目标。
JP_QUOTE_MAX_LEN = 6
KANA_RUN_RE = re.compile(r"[぀-ゟァ-ヺヽ-ヿ]+")


def _kana_ratio(zh: str, names, jp: str = "") -> float:
    s = zh
    for n in sorted(names, key=len, reverse=True):
        s = s.replace(n, "")
    if jp:
        s = KANA_RUN_RE.sub(
            lambda m: "" if len(m.group()) <= JP_QUOTE_MAX_LEN and m.group() in jp
            else m.group(), s)
    return len(KANA_RE.findall(s)) / max(len(zh), 1)
```

(c) `scan` 签名加 `dup_min_len=DUP_MIN_LEN, dup_min_count=DUP_MIN_COUNT`；函数体内 `zh_counts` 的 `DUP_MIN_LEN` 与 C3 分支的 `DUP_MIN_COUNT` 改用参数；C1 分支改 `kr = _kana_ratio(zh, names, jp)`。

(d) `main()` 加 `ap.add_argument("--dup-min-len", type=int, default=DUP_MIN_LEN)`、`ap.add_argument("--dup-min-count", type=int, default=DUP_MIN_COUNT)` 并透传给 `scan`。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_detect_collapse.py -v` → 全 passed（含既有测试）。

- [ ] **Step 5: 真实数据降噪验证**

用 canary 量化降噪效果（当前工具树重算 P2 全段，与 Task 3 点火时的 45 条基线对比）：

```bash
uv run python tools/canary.py --lane-dir pilot/lanes/opus --batches 1-35 \
  --out /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/canary-postfix.json
uv run python -c "
import json
v=json.load(open('/private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/canary-postfix.json',encoding='utf-8'))
from collections import Counter
c=Counter(h['rule'] for b in v.values() for h in b['collapse'])
print('collapse 按规则:', dict(c), '总数:', sum(c.values()))
"
```
Expected: 总数明显低于 45（P2 已判定 45 条全是误报，其中 C1 的 ・/引用类与本次修理直接对应；batch 19 的 12 条钱仙 C1 与 batch 31 的 4 条 ・ C1 应消失）。把前后对比数字写进报告——这就是段边界滚 tag 时 canary diff 的预告值，**差异全部应为「误报消失」方向**；若出现任何新增命中，逐条核查并如实报告。

- [ ] **Step 6: 全量测试 + commit**

Run: `uv run pytest -q` → 241 passed。

```bash
git add tools/detect_collapse.py tests/test_detect_collapse.py
git commit -m "fix: detect_collapse 降噪——假名标点剔除/引用豁免/C3 阈值开关（F12/F9/F4）"
```

---

