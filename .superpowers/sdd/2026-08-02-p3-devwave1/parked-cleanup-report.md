# parked Minor 三条清理报告（2026-08-02）

三条终审后 parked 的 Minor，均属「恒绿/静默失效」一族的尾巴。原则：宁可明确报出来
让人过目，也不要静默给一个看起来正常的结果。

## P1 · `is_clean_key` 会降级「有真实证据」的合法词键

**文件**：`tools/cluster_notes.py`（`is_clean_key`）

**修法**：在 `is_clean_key` 顶部加最优先短路——`if total > 0: return True`，其余判据
（空白/无假名汉字/ASCII/语料外字符/长键零出现）只在 `total == 0` 时才有意义去判断
「0/0 的两种相反含义」；`total > 0` 意味着这个键逐字命中了 ledger 里的原文，歧义
不存在，不该被外观判据错杀。docstring 已补充这条理由。

**真实车道重跑（`pilot/lanes/opus`）**：

```
uv run python tools/cluster_notes.py --lane-dir pilot/lanes/opus
```

- 修前：`成词词族 111、未归词 276 条（其中 13 个键因提取不干净被降级）`
- 修后：`成词词族 111、未归词 276 条（其中 13 个键因提取不干净被降级）`
- **完整 diff：0 字节差异**（`diff before.txt after.txt` 无输出）。

**核实原因**：逐条检查后确认，任务描述里举的两个例子——
`いつか きみが みる お話。`（绘本标题，ledger 里确有 3 次逐字命中：id 11118/16208/
16215）与 `ＴｒｕｅＣｏｌｏｒ`——**目前都没有作为提案标题词键出现在
`pilot/lanes/opus/data/notes/*.md` 的任何 `### N. 词 → 译` 行里**（`grep -n
"いつか" notes/*.md` 与全角 `Ｔｒｕｅ` 均零命中；唯一相关的一条是
`crd.md:226 ★お話／物語` 与 `s2s.md:83` 里提到的『True Color』半角写法，两者的
`extract_terms` 键分别是别的形态，不受本次短路影响）。也就是说这两个键**当前既不
在旧代码的降级列表里，也不会在新代码里出现**——它们不是这条车道数据里正在被误伤
的活键，是复评过程里用于演示 bug 存在性的构造/取证样例。降级数量、成词词族数量
在真实数据上因此不变，这是**预期**结果，不是修复未生效。

**保证「减少的都是有证据的键」**：由于本次真实车道 diff 为 0，没有产生「回归成词」
的键需要列出（回归成词键清单：**无**，见上）。修复的正确性改由单测直接验证这两个
具体例子（见下）；且改动只加了一条最先执行的 `return True` 短路，不改变
`total == 0` 分支的既有逻辑，故不会让任何本来该保持降级的键被放行——`total>0` 是
充分且唯一新增的放行条件，不影响 `total==0` 时的判据。

**测试**（`tests/test_cluster_notes.py`）：
- `test_is_clean_key_total_gt_zero_short_circuits_whitespace_key`：直接用任务描述的
  `いつか きみが みる お話。` + `total=3` 断言判 clean。
- `test_is_clean_key_whitespace_key_zero_total_stays_dirty`：同键 `total=0` 时仍判
  dirty——防止短路被写宽成「只要形状勉强像日文就放行」。

## P2 · ledger 为空/缺失时全体降级且无点名告警

**文件**：`tools/cluster_notes.py::main()`

**修法**：
1. `ledger.jsonl` 读取前先判 `.exists()`（此前missing file 会 `FileNotFoundError`
   直接崩溃，非「全体降级」而是硬崩——一并修掉，两种情形都归到同一条告警路径）。
2. 读完 ledger 后，`if not ledger:` 打印醒目的 `!! 告警：` 行，点名
   `<data-dir>/ledger.jsonl` 没读到或为空，说明后果——corpus_chars 语料字符集为空，
   `is_clean_key` 的语料判据对任何键都成立，全部词键被降级、饱和度判定不可用；并
   提示核对 `--lane-dir` 与 `build_ledger` 是否已跑。rc 维持 0（与 `saturation.py`
   同口径的 advisory 工具）。

**测试**：
- `test_main_warns_on_empty_ledger`：ledger.jsonl 存在但 0 行，断言告警文案出现。
- `test_main_warns_on_missing_ledger_file`：ledger.jsonl 文件根本不存在，断言不崩溃
  且同一告警出现（覆盖「缺失」与「为空」两种情形）。

验证：`uv run python -m pytest tests/test_cluster_notes.py -q` → 17 passed。

## P3 · `ayano_test --qa <不存在的文件>` 抛 traceback

**文件**：`tools/ayano_test.py::main()`

**修法**：在 `load_qa()` 调用之前（与既有的"段绑定校验尽早失败"顺序一致）显式判
`Path(a.qa).exists()`；不存在则打印跳过提示（点名期望路径、说明"本段题库尚未产出，
彩野测试跳过""这不是失败，请把这次跳过记进段末台账"），**返回 2** 而不抛异常。

**退出码选择理由**：选 **rc=2**（不是 0，也不复用其余错误路径已在用的 rc=1）。
- 不能是 0：0 在这个工具里等价于"跑完且全部通过"，把"没跑"伪装成"通过"正是本轮
  反复出现的静默恒绿模式，必须避免。
- 不选复用 rc=1：`ayano_test.py` 里 rc=1 已经承载"真失败/配置错误"语义（未知段
  label、缺 `DEEPSEEK_API_KEY`、题库 segment 与 `--segment` 不符）——这些是**操作者
  搞错了什么**；而"题库还没产出"是**正常的、预期内的缺失**（题库由开发轨按段
  逐段提供，本段的还没写完全属正常）。混进 rc=1 会让段末流程脚本/人工无法区分
  "这段配置错了，需要人管"和"题库没到，跳过即可，等下次"，与"退出码不能与
  『成功』混淆"同一枚硬币的反面——都是「一个数字不该同时代表两件不同的事」。
  故给它一个专属的 rc=2，段末台账/自动化都可单独识别。

**文档核对**（`docs/ops/p3-production-runbook.md` §5 第 3 项）：原文只写了"题库不存在
就跳过并记台账"这一目标行为，未写清"谁来判断跳过、退出码是什么"。已改为明确：
**工具自身**打印跳过提示（点名期望路径）并以 rc=2 退出——不抛异常，也不会被误读成
rc=0 的"跑完且全部通过"；见此跳过即记台账，不必人工先探路径是否存在。同时在
§4.1 关于"ayano_test 不是恒 exit 0"的说明后补了一句 rc=2 的存在与用途。

`docs/ops/p3-production-handoff.md` 段末清单第 3 项检查：该项针对的是 seg1-s2 段，
`config/ayano_qa/seg1-s2.yaml` 本来就存在（`test_real_qa_bank_is_bound_to_its_segment`
可验证，15 题），该段文案本身没有对"题库缺失"场景做任何断言，故与新行为不矛盾，
**未改动**；「本段 seg1-s2 的编号例外」提示按要求原样未动。

**测试**（`tests/test_ayano_test.py`）：
- `test_missing_qa_file_skips_without_traceback`：`--qa` 指向不存在路径，断言不抛
  异常、rc==2、输出含"跳过"/路径本身/"尚未产出"，且注入的 `stream_transport` 断言
  "不该调 API"（零 API 调用即失败早退）。

验证：`uv run python -m pytest tests/test_ayano_test.py -q` → 17 passed。

## 全量回归

```
uv run python -m pytest -q
```
`316 passed`（基线 311 + 本次新增 5 条：P1 两条 + P2 两条 + P3 一条），全绿。

## 改动文件清单

- `tools/cluster_notes.py`（P1 短路 + P2 告警，`git add` 显式路径）
- `tools/ayano_test.py`（P3 跳过分支）
- `tests/test_cluster_notes.py`（P1/P2 新增 4 条测试）
- `tests/test_ayano_test.py`（P3 新增 1 条测试）
- `docs/ops/p3-production-runbook.md`（§5 第 3 项 + §4.1 措辞对齐新行为）

未触碰：`pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`、
`docs/superpowers/plans/translate-seg1-s2.md`、`lua_scripts/`、`png/`、`analysis/`、
`skeleton/`。`docs/ops/p3-production-handoff.md` 只读未改（核对后确认无需改动，
原因见上）。
