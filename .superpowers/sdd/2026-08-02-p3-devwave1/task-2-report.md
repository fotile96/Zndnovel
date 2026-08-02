### Task 2 报告：detect_collapse 降噪（F12 / F9 / F4）

commit: `225f7e99fbe4d4570543b483e083f438537ee358`
`fix: detect_collapse 降噪——假名标点剔除/引用豁免/C3 阈值开关（F12/F9/F4）`

只 `git add tools/detect_collapse.py tests/test_detect_collapse.py`，未触碰
`pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`（该目录
下 `progress.md` 在本任务开始前已由并发的生产会话改动，工作树里始终保持
未暂存状态，未被本任务 add/commit）。

---

## Step 1–2：写失败测试并确认失败

按 brief 原样在 `tests/test_detect_collapse.py` 追加三条测试
（`test_f12_kana_punct_not_counted` / `test_f9_quoted_jp_kana_exempt_but_untranslated_still_caught` /
`test_f4_dup_thresholds_via_params`）。

```
uv run pytest tests/test_detect_collapse.py -v -k 'f12 or f9 or f4'
```
结果：3 FAILED（F12 因「・」计入假名比；F9 因 id=1 也被误判 C1；F4 因
`scan()` 尚无 `dup_min_len`/`dup_min_count` 形参，`unexpected keyword argument`）—
与 brief 预期一致。

## Step 3：实现（含一处对 brief 字面代码的必要修正）

按 brief 逐字落地 (a) `KANA_RE` 收窄、(c) `scan()`/C3 分支改用参数、
(d) `main()` 透传 `--dup-min-len`/`--dup-min-count`。

**(b) `_kana_ratio` 的 F9 部分未逐字照搬**：brief 给出的实现是

```python
if jp:
    s = KANA_RUN_RE.sub(
        lambda m: "" if len(m.group()) <= JP_QUOTE_MAX_LEN and m.group() in jp
        else m.group(), s)
```

先跑一遍确认新测试变绿后，再跑全量 `tests/test_detect_collapse.py`，发现
**这段字面代码回归了两条既有测试**：`test_untranslated_line_is_flagged_by_kana_ratio`
与 `test_main_writes_report_and_always_returns_zero`（两者场景相同：
`jp = zh = "彼女は静かに笑った。"`，整行未译）。

根因：整行未译时 `zh` 与 `jp` 逐字相同，此时 `zh` 中任意假名连串"逐字出现
在 jp 里"都是平凡为真（zh 本来就是 jp 的拷贝）。brief 用长度阈值
（`JP_QUOTE_MAX_LEN=6`）试图挡住这个陷阱——它确实挡住了 brief 自己给的
"长假名串"陷阱测试例（`ずっとまえから、すきでした。ほんとうです。`，其中
"ずっとまえから" 长度 7 超阈值，不豁免，仍报 C1）。但对**漢字假名交替的
正常日文句**（如 `彼女は静かに笑った。`）无效：漢字天然把假名切成
`は`(1)/`かに`(2)/`った`(2) 这样的短连段，每段都 ≤6 且都能在 `jp` 里找到，
于是被逐段豁免，累计后残留假名比归零，C1 漏判——这正是这两条既有测试
在锁的场景，也正是 brief 自己在措辞里警告的"整行未译时 zh≈jp"陷阱，只是
brief 给出的具体实现只堵住了它自己举的那个例子，没堵住既有测试这个例子。

**修正**：加一道前置门槛——只有 `zh != jp`（说明确实发生过翻译动作）时才
进入豁免逻辑；`zh == jp`（逐字未译）时整体跳过豁免，让原始假名比原样生效：

```python
if jp and zh != jp:
    s = KANA_RUN_RE.sub(...)
```

这个门槛不改变 `JP_QUOTE_MAX_LEN`/`KANA_RUN_RE` 本身（未"放宽长度阈值"，
遵守 brief 的告诫），只是补一个 brief 文字描述里已经隐含、但示例代码没
覆盖到的边界条件。

## Step 4：全量确认通过

```
uv run pytest tests/test_detect_collapse.py -v
```
13 passed（3 条新增 + 10 条既有，含被回归又修复的 2 条）。

## Step 5：canary 量化降噪验证

**前置核验**：用 `git stash` 把 `tools/detect_collapse.py`/`tests/test_detect_collapse.py`
临时还原到修前状态，重算一遍 P2 全段 canary，确认与 Task 3 点火时记录的
基线完全一致（`C1=21 / C2=2 / C3=22`，总 45），确认"当前工具树"与"点火
基线"处于同一起点，再 `git stash pop` 恢复本次改动。

```
uv run python tools/canary.py --lane-dir pilot/lanes/opus --batches 1-35 --out <prefix.json>   # 修前
uv run python tools/canary.py --lane-dir pilot/lanes/opus --batches 1-35 --out <postfix.json>  # 修后
```

**规则分布对比**：

| 阶段 | C1 | C2 | C3 | 总数 |
|---|---|---|---|---|
| 修前（=点火基线） | 21 | 2 | 22 | 45 |
| 修后 | 4 | 2 | 22 | 28 |
| 差值 | -17 | 0 | 0 | -17 |

**逐条核查**（修前/修后按 (batch, rule, id) 做差集）：
- 仅修前有（消失）：17 条，全部是 C1，分布 batch19×10 / batch26×2 /
  batch30×1 / batch31×4。
- 仅修后有（新增）：**0 条**。

17 条消失明细核实：
- **batch 31 的 4 条**（id 17006/17007/17009/17010）：F12 修复，源文本含
  「・」项目符号（如 `【■おしらせ】・閲覧方法…`），旧 `KANA_RE` 把
  `゠-ヿ` 整段计入假名，含 `・`；新范围排除后不再误报。
- **batch 30 的 1 条**（id 17005）：同类 F12 修复
  （`【■通知】・阅览方法…`）。
- **batch 19 的 10 条**（id 8280/8281/8282/8283/8284/8285/8300/8302/8366/8371）：
  F9 修复，均为「钱仙」拼字段——コインを指す/『ユ……キ……フル……トキ』
  等把假名逐字复述/引用原文的行，zh 已发生实质翻译（`zh != jp`），残留
  的短假名连串（如 `に`、`にんげん`、`オ……マ……エ……`）逐字见于同行 jp，
  符合"作品内引用"的定义。
- **batch 26 的 2 条**（id 8565/8703）：同类 F9 修复——
  `さくら？ サクラ……是谁啊？` 中的假名同音提示 `さくら`；
  `『オ、マ、エ』『ヤ、オ』` 逐字母引用回溯钱仙场景的揭示文本。

**batch 19 仍残留 2 条 C1（未消失，如实记录）**：
- id 8192：`纸上排列着『是』『否』，还有あかさたなはまやらわ……`——完整
  五十音示例 `あかさたなはまやらわ` 长度 10，超过 `JP_QUOTE_MAX_LEN=6`，
  按设计不豁免，正确地仍被判定为"假名连串过长，需人工复核"。
- id 8301：`ユキフルトキ。`——该行 `zh` 与 `jp` **逐字相同**，本次新增的
  `zh != jp` 门槛把它挡在豁免之外（这条正是为了不漏判 8192/8301 之外那类
  "漢字假名交替、整行未译"场景而必须付出的代价——无法仅凭"是否等于原文"
  区分"故意保留的拟声/咒语式转写"与"真的漏译"，两者在字面上完全等价）。
  brief 预期"batch 19 的 12 条应消失"，实际消失 10 条，这 2 条是已知的、
  有解释的残留，不是回归；P2 复核已判定全部 45 条命中里真崩溃 0 条，这
  2 条属于同一批已判定为误报的候选，留作日后若要进一步收紧再处理。

**结论**：总数 45→28，方向正确（净减少），且经逐条核查 **17 条差异全部
是「误报消失」方向，0 条新增命中**，符合 brief 对 Step 5 的验收要求。

## Step 6：全量测试 + commit

```
uv run pytest -q
```
输出：`244 passed`（较改动前 241 passed 净增 3，即新增的 F12/F9/F4 三条测试）。

```
git add tools/detect_collapse.py tests/test_detect_collapse.py
git commit -m "fix: detect_collapse 降噪——假名标点剔除/引用豁免/C3 阈值开关（F12/F9/F4）"
```
commit: `225f7e99fbe4d4570543b483e083f438537ee358`。

## 偏差与处理小结

| 项 | brief 要求 | 实际处理 | 理由 |
|---|---|---|---|
| F12 | `KANA_RE` 收窄正则 | 逐字照搬 | 无冲突 |
| F9 | `_kana_ratio` 豁免逻辑 | **新增 `zh != jp` 门槛**，其余逐字照搬（`JP_QUOTE_MAX_LEN=6`、`KANA_RUN_RE` 未改） | brief 字面代码回归 2 条既有测试，根因见上；新增门槛是修复回归的最小改动，未触碰 brief 明确要求"不要放宽"的长度阈值 |
| F4 | `scan()`/`main()` 新增两参 | 逐字照搬 | 无冲突 |

## 自查结论

- 三处需求点（F12/F9/F4）均已实现，签名/CLI 形态未破坏 `canary.py` 的
  默认调用与既有测试。
- 全量测试 244 passed（241 + 3 新增），无回归。
- canary 量化验证：45→28，17 条消失、0 条新增，逐条核查全部对应 F9/F12
  的已知误报模式，2 条已知残留（8192/8301）已如实解释，非回归、非新增。
- 提交范围收敛为 brief 指定的两个文件，未触碰 `pilot/lanes/`、`prompts/`、
  生产会话的 SDD 台账目录。

---

## 二轮修正（评审 Critical + 2 Important + 3 Minor）

评审指出：第一轮为修复"整行未译回归"选用的 `zh != jp` 门槛问的是"有没有
动过一个字"，对退化输出（模型复读原文、只顺手把 `、。` 规范化成中文标点）
毫无区分力——评审用全 ledger 量化：`zh==jp` 时 C1 抓住率 98.5%，仅在句尾
加一个「。」就跌到 36.3%（漏报 63.7%），换成"日文标点转中文标点"是
52.7%。这是本次改动引入的**探测能力净损失**，且 F9 现存残留 id 8301
（`ユキフルトキ。`）正是活证据——加一个句号就会消失。commit
`225f7e9`（本报告上半部分）已如实披露这个门槛，但强度判断有误；本轮按
评审指定方向修正。

### Critical：豁免预算 gate

`tools/detect_collapse.py` 的 `_kana_ratio` 由单一 `zh != jp` 短路改为
三重门槛（`zh != jp` 短路保留，但叠加两条量化判据，见函数上方新注释）：

```python
JP_QUOTE_BUDGET = 0.40       # 被豁免假名字符数 / len(zh) 上限
JP_QUOTE_MIN_NOVEL = 0.05    # zh 中「jp 里不存在的字符」占比下限

if jp and zh != jp:
    runs = [m.group() for m in KANA_RUN_RE.finditer(s)
            if len(m.group()) <= JP_QUOTE_MAX_LEN and m.group() in jp]
    novel = sum(1 for c in zh if c not in jp) / max(len(zh), 1)
    if (sum(map(len, runs)) <= JP_QUOTE_BUDGET * len(zh)
            and novel >= JP_QUOTE_MIN_NOVEL):
        s = KANA_RUN_RE.sub(..., s)   # 原豁免逻辑不变
```

`JP_QUOTE_MAX_LEN=6`、`kana_max=0.02` 均未改动（评审明令禁止放宽）。

### 阈值标定（0.32 / 0.40 / 0.50，novel 固定 0.05）

标定脚本：`calibrate_budget.py`（临时脚本，写在 scratchpad，未入库）。
数据来源：
- **成本**（真实译文，是否引入新误报）：`pilot/lanes/opus` 批 1–35 的
  `work/ctx/batch_N/source.jsonl` + `data/forward.jsonl`，共 **4282 行**
  （与评审给出的数字一致）。用各档 `JP_QUOTE_BUDGET` 跑
  `_kana_ratio(zh, names, jp)`，数 `kr > KANA_MAX` 的行数（即 C1 命中数，
  当前修后基线为 4）。
- **收益**（漏报率）：`data/ledger.jsonl` 中 `jp` 含假名的行，共
  **16101 行**（与评审给出的数字一致），构造伪装 `zh = jp + "。"`（复制+
  句尾加句号），同样跑 `_kana_ratio(zh, (), jp)`，统计 `kr <= KANA_MAX`
  （即被漏判）的比例。

| JP_QUOTE_BUDGET | 成本（1–35 批 4282 行 C1 命中数） | 收益（复制+句号伪装集漏报率） |
|---|---|---|
| 0.32 | 4 | 8.6% |
| 0.40 | 4 | 13.1% |
| 0.50 | 4 | 18.0% |

（漏报率的绝对数值与评审报告中引用的数字——0.32 档 12.5%——不完全一致，
应是双方伪装语料/统计口径的细节差异；但**方向与结论一致**：成本在
0.32–0.50 区间内保持不变＝4，收益随预算增大而单调变差，与评审判断相符。）

另单独核实了评审提到的"已知最大合法豁免占比 0.316"：对 batch19/26 全部
12 条已确认合法的 F9 豁免样本逐条计算 `sum(len(exempt runs)) / len(zh)`，
最大值确为 **0.3158**（id 8300，`【她】「『ユ……キ……フル……トキ』」`），
且这 12 条的 `novel` 最小值为 0.053，均 ≥ `JP_QUOTE_MIN_NOVEL=0.05`，不会
被换新判据误伤。

**选择**：三档成本相同（=4，零新增误报）；0.32 相对 0.316 只有 1.3% 余量，
不满足评审要求的 ≥25% 相对余量；0.40 与 0.50 均满足余量要求，但 0.40 的
漏报率（13.1%）优于 0.50（18.0%）——故选 **`JP_QUOTE_BUDGET = 0.40`**。

### Important 1：补测试锁住"近似复制"边界

原有测试（含被第一轮修复的两条既有测试）只覆盖 `zh == jp` 精确相等，未锁
"近似复制"这条真正的漏洞。新增两条：
- `test_f9_approx_copy_with_trailing_period_still_caught`：`zh = jp + "。"`
  （句尾多一个句号），仍报 C1。
- `test_f9_approx_copy_with_punct_swap_still_caught`：把 `jp` 中的
  `、` 换成中文逗号 `，`，其余逐字照抄，仍报 C1。

### Important 2：补对抗侧数字

已在上面标定表的"收益"列给出——第一轮报告的 canary 对比只覆盖"已入线
合法译文侧"（FP 减少、0 新增），未做"新逻辑是否会放过真崩溃"的对抗验证；
本轮用全 ledger 构造的"复制+句号"伪装集补上了这一侧。

### Minor 三条

1. `test_f12_kana_punct_not_counted`：原 zh/jp 长度比恰好等于 `RATIO_HI`
   闭区间上界 1.50（12/8），已改为 `・条目一・条目二—ー゠`（11/8=1.375），
   留出余量，避免日后微调 `RATIO_HI` 时该测试因触碰 C2 边界而以"F12 失败"
   的假象报红。
2. 在 `KANA_RE` 定义上方加"已知遗留"注释，说明平假名段 `぀-ゟ` 仍含
   U+3099/309A 结合符与 309B–309E 非结合浊/半浊音符、假名重复符，与片
   假名侧已单独摘除标点的处理不对称；不改正则，仅记录。
3. 在同一处加注：剔除 `ー`(U+30FC) 会让"未译的长音片假名词"（如
   `スーパー`）少计 1/3 假名字符，C1 灵敏度略降，方向与 F12 目标一致，
   代价可接受。

评审记的备查项（`m.group() in jp` 不校验位置）本轮不处理，已知悉评审已
记台账。

### 验证

```
uv run pytest tests/test_detect_collapse.py -v   # 15 passed（13 + 本轮 2 条新增）
uv run pytest -q                                  # 246 passed（244 + 2）
```

canary 复核：重跑 `tools/canary.py --lane-dir pilot/lanes/opus --batches 1-35`，
输出与本报告上半部分（一轮修后）**逐字节相同**（`json.load` 后 `==` 比较
为 `True`）：collapse 仍为 **28 条**（C1=4 / C2=2 / C3=22）——预算 gate
在真实数据上未改变任何一条既有判定，只堵住了合成的"近似复制"伪装。

commit：`fix: F9 豁免加预算 gate（修复近似复制漏报）`

### 二轮自查结论

- Critical（预算 gate 强度不足）：已修复，三档标定见上表，选定 0.40，
  理由（成本相同、余量达标、收益更优）逐条对应评审判据。
- Important 1（测试未锁近似复制边界）：已补两条测试，均验证通过。
- Important 2（报告缺对抗侧数字）：已在标定表补齐收益列。
- Minor 三条：已处理（缩短 F12 测试余量、两条遗留注释），备查项按评审
  要求本轮不动。
- 提交范围仍只含 `tools/detect_collapse.py`、`tests/test_detect_collapse.py`；
  `pilot/lanes/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`（生产会话台账）
  未触碰。
- 全量测试 246 passed；canary 1–35 批：C1=4，总数=28，与预算 gate 引入前
  完全一致（无回归、无新增）。
