# Task 5 Step 1: gen_timeline main() 与 scene2card 解析 - 报告

范围声明：本报告只覆盖 task-5-brief.md 的 **Step 1**（机制代码）。Step 2（全书
route_plan.yaml 内容编写）、Step 3（CHECKPOINT）、Step 4（最终提交 data/ 产物）
不在本轮范围内，未执行。

## 实现摘要

在 `tools/gen_timeline.py`（此前只有 `Expander` 类）追加三个模块级函数：

1. **`parse_scene2card(lua_text) -> dict[str, int]`**：正则
   `^sceneId2aCard\.(\w+) = (-?\d+)` 逐行匹配 `snr_common.lua`，跳过
   `name == "keyword"` 的反编译噪声行（全文 38 处，键重复覆盖，无场景语义）。
2. **`run_plan(ex, moves)`**：按序解释 route_plan DSL（YAML 顶层 list，每项恰好
   一个键）。`story`/`fragment_sweep`/`replay` 的 DSL 参数名与 Expander 同名方法
   的形参一致，直接 `**kwargs` 展开；`pool` 的 `func`、`script` 的 `file` 换名为
   对应方法的单个位置参数（`file_func`/`file_stem`）。未知的顶层移动键立即抛
   `ValueError`，消息指明第几条移动（1-based）与合法键集合。
3. **`main()`**：读 `config/route_plan.yaml`、`config/unit_funcs.yaml`、
   `data/dag.json`、`data/ledger.jsonl`；解析 `lua_scripts/snr_common.lua` 写
   `data/scene2card.json`（`json.dumps(..., ensure_ascii=False, indent=1,
   sort_keys=True)`，与 `build_dag.py` 写法一致）；构造 `Expander(dag,
   ledger_rows, unit_funcs, scene2card=scene2card)`、跑 `run_plan`；给
   `ex.timeline` 每行加 `seq`（从 1 递增，unit 与 marker 统一编号，`seq` 置于每行
   最前）；用 `pipelib.write_jsonl` 写 `data/timeline.jsonl`；打印
   `scene2card=… moves=… unit=… marker=… covered_ids=…` 一行统计；`return 0`。
   `if __name__ == "__main__": raise SystemExit(main())`，照 `build_dag.py` 惯例。

`main()` 不带 CLI 参数（无 `--check`/`--out-dir`）——brief 未要求，`check_timeline.py`
（Task 4，最邻近的同类脚本）也是同样的无参 `main()` 风格，故未添加 argparse。

`config/route_plan.yaml` 新建，内容严格照抄 brief 给出的 10 条示例移动（一字未
改语义），只加了文件头注释说明这是 Step 1 起步骨架、全书路线待 Step 2 续写。

## 文件清单

### 修改
- `tools/gen_timeline.py`：追加 `parse_scene2card` / `run_plan` / `main`，
  imports 增加 `json`、`re`（`yaml` 延后到 `main()` 内部局部 import，与
  `check_timeline.py` 一致，保持 `Expander` 类本身零第三方依赖）。
- `tests/test_gen_timeline.py`：追加 `import pytest` 与
  `parse_scene2card, run_plan` 的导入，新增 3 个测试函数（见下）。

### 新建
- `config/route_plan.yaml`：10 条起步移动骨架 + 说明注释。

### 运行产物（本轮不入库，按 brief 指示留给 Step 4）
- `data/scene2card.json`（157 条）
- `data/timeline.jsonl`（38 行：37 unit + 1 marker）

## 测了什么与结果

新增 3 个测试（`tests/test_gen_timeline.py`）：

1. `test_parse_scene2card_skips_keyword_and_keeps_real_entries`——内联 lua 片段，
   含 3 行 `keyword` 噪声、3 行真实条目、1 行前导空格条目、1 行无关函数定义；断言
   结果恰为 `{"sof_10": 1, "s1s_20": 2, "s1s_30": 3}` 且不含 `"keyword"` 键。
2. `test_run_plan_dispatches_all_move_kinds_in_order`——用既有 `DAG2/LEDGER2/S2C`
   夹具跑一遍全部 5 种移动（story→fragment_sweep→pool→script→replay），逐行断言
   `ex.timeline` 的 `(type, unit_kind, state, ids)` 形状精确匹配（含 pool/script
   换名是否生效、fscene 是否紧随 card、replay 的 dedup+marker 是否正确），并断言
   `ex.held == {11, 12}`。
3. `test_run_plan_rejects_unknown_move_key`——2 条移动，第 2 条键名 `teleport`
   不在合法集合内，断言 `pytest.raises(ValueError, match=r"第 2 条")`。

结果：
```
$ uv run pytest tests/test_gen_timeline.py -v
...
14 passed in 0.07s   (11 条既有 + 3 条新增)

$ uv run pytest -q
62 passed in 1.98s   (基线 59 → 62，无回归)
```
`uv run pytest -q -W error` 额外探了一遍告警：新增测试与改动代码零告警；发现
`tests/test_build_dag.py` 两个既有用例在 `-W error` 下有一个与 `data/dag.json`
文件句柄相关的 `PytestUnraisableExceptionWarning`——与本次改动无关（该文件本轮
未触碰，最后一次改动在更早的 `18efbd9`），非本轮标准验收命令（`uv run pytest -q`
本身零告警），未处理，仅记录在此供后续参考。

## 双跑确定性验证的命令与输出

方法一：sha256 直接比对（不依赖 git 跟踪状态，更严格）：
```
$ uv run python tools/gen_timeline.py
scene2card=157 moves=10 unit=37 marker=1 covered_ids=1314
$ sha256sum data/timeline.jsonl data/scene2card.json > run1.sha256
$ uv run python tools/gen_timeline.py
scene2card=157 moves=10 unit=37 marker=1 covered_ids=1314
$ sha256sum data/timeline.jsonl data/scene2card.json > run2.sha256
$ diff run1.sha256 run2.sha256
(空输出 —— 两次运行产物字节级相同)
```

方法二：brief 字面给出的 `git diff --stat`（该命令依赖文件已被 git 跟踪，对全新
未跟踪文件天然输出为空、不构成有效验证，故额外临时 `git add` 后复核，验证完立即
`git reset` 撤回暂存，不改变"本轮不入库"的约定）：
```
$ git add data/timeline.jsonl data/scene2card.json
$ uv run python tools/gen_timeline.py
scene2card=157 moves=10 unit=37 marker=1 covered_ids=1314
$ git diff --stat data/timeline.jsonl data/scene2card.json
(空输出 —— 确认一致)
$ git reset -- data/timeline.jsonl data/scene2card.json
(撤回暂存，文件保留在工作区，回到 untracked 状态)
```
两种方法结论一致：确定性成立。

## scene2card.json 条目数

```
$ uv run python -c "import json;d=json.load(open('data/scene2card.json',encoding='utf-8'));print(len(d), d.get('s1s_20'), d.get('sof_10'))"
157 2 1
```
与验收期望 `157 2 1` 完全一致。另外独立核对了 `snr_common.lua` 全文
`sceneId2aCard.` 赋值行共 195 条，其中 `keyword` 38 条、真实键 157 条且互不重复
（`157 = 195 - 38`），157 条之外全文再无其它匹配行（正则命中区间严格落在
lua_scripts/snr_common.lua 第 63–257 行的声明块内，无遗漏也无误伤运行期动态下标
用法如 `sceneId2aCard[p0]`）。

## check_timeline.py 跑起来后的输出摘要

```
$ uv run python tools/check_timeline.py
重复 id: [8170, 8171, 8172, 8173, 8174, 8175, 8176, 8177, 8179, 8180]…共228
缺失 narrative id: [282, 283, 284, 285, 286, 287, 288, 289, 290, 291]…共15379
门控: s5s_20 出现前缺卡 [177]
$ echo $?
1
```
能读到两个产物、打印出错误清单、退出码 1——符合 brief 预期（"这是正常的"）。

**关于"重复 id: 共228"的说明（供 Step 2 参考，非本轮需处理事项）**：10 条起步
移动里，第 6 条 `story: {enter: s1s_150, until: s1s_200_sel}` 因 `s1s_150` 的
`route_has s1s_110` 判定（此前第 5 条移动已经讲过 `s1s_110`）走上了
`s1s_160→…→s1s_210→…→s1s_260_sel` 这条支线，且该支线在 `s1s_260_sel` 默认选项
上触发跨章 `RUN s5`，一路把 `s5s_20…s5s_380` 也带了进来，直到 `until` 始终没有
命中 `s1s_200_sel` 才自然跑到 "end"；随后第 8 条移动又显式 `story: {enter:
s1s_210, until: s1s_260_sel}` 把 `s1s_210…s1s_260_sel` 这一段重讲了一遍，造成
这几个状态的叙事 id 被 emit 两次。这是 10 条示例移动本身的路线设计使然（brief
原文即如此给出，我按指示"照抄"，未改写语义），不是 `run_plan`/`Expander` 的 bug
——`story()`/`route_has` 的分支语义在 Task 3 已过评审，本轮未改动。Step 2 编写
全书路线时大概率需要显式处理这条 `route_has` 分歧（例如让第 6 条移动的 `until`
改到分歧点之前，或接受被 `route_has` 带偏的分支再另行安排"回到主线"的
`story`/`replay`），此处仅如实记录现象，未擅自改动 route_plan 语义或去"造数据"
让 check_timeline 变绿。

## 自评审

### 完整性
- [x] `parse_scene2card`：跳过 `keyword`，157 条真实条目，已用真实
      `snr_common.lua` 与内联夹具双重验证。
- [x] `run_plan`：5 种移动全覆盖测试，未知键抛异常且指明第几条移动。
- [x] `main()`：读四个输入、解析 lua、写 `scene2card.json`（确定性写法）、跑
      `route_plan`、加 `seq`、写 `timeline.jsonl`、打印统计、`return 0`；
      `if __name__ == "__main__"` 收尾照抄 `build_dag.py` 惯例。
- [x] `config/route_plan.yaml`：只放 10 条示例骨架 + 说明注释，未越权编全书路线。
- [x] 双跑确定性：sha256 与 `git diff --stat` 两种方法均验证为空差异。
- [x] `check_timeline.py` 可跑通（不崩溃），退出码 1，符合预期。

### 质量
- 命名与 brief 建议的函数名完全一致（`parse_scene2card`/`run_plan`/`main`），
  行为职责单一。
- `run_plan` 的错误信息同时给出移动序号与合法键集合，便于人工核对 route_plan.yaml
  的 typo（这也是 brief 反复强调"不要静默忽略"的落地）。
- `main()` 未引入 CLI 参数面——brief 未要求，避免过度设计；输出的一行统计信息
  对人工核对（尤其 `scene2card=157`）友好。

### 纪律（YAGNI／只做被要求的）
- 未给 `parse_scene2card` 加"非 keyword 重复键报错"之类未被要求的防御逻辑——
  已用真实数据核实当前 157 条互不重复，不需要；避免过度设计。
- 未对 `run_plan` 内部各移动的关键字参数做逐一 typo 校验包装（例如 `story()`
  参数名拼错时会直接冒出 Python 原生 `TypeError`，已经是"当场暴露"，未叠加多余的
  包装层）——brief 明确要求的只是"未知的顶层移动键"须报错指明第几条，已精确满足。
- 未触碰 `tools/check_timeline.py`、`tools/build_dag.py`、`Expander` 已有方法的
  语义——只做了追加。
- 未尝试让 `check_timeline.py` 变绿、未编全书路线、未伪造数据——`route_plan.yaml`
  严格是 brief 给的 10 条示例骨架。
- 本轮未 `git add` `data/timeline.jsonl`、`data/scene2card.json`，遵照指示留给
  Step 4。

### 测试
- 新增 3 个测试均测真实行为（正则解析结果、方法分派与参数换名、异常路径），无
  针对 `main()` 的 IO 壳测试。
- `uv run pytest -q`：62 passed，无回归（基线 59 + 新增 3）。
- 输出干净：正常运行下无告警；额外 `-W error` 探测到的告警来自本轮未触碰的
  `tests/test_build_dag.py`，已记录不做处理。

## 遗留顾虑

1. **"重复 id" 现象**（见上文 check_timeline 输出摘要一节的详细说明）：10 条示例
   移动本身会因 `route_has` 分歧把 `s1s_210…s1s_260_sel` 讲两遍、并意外带出
   `RUN s5` 的一整段。这是内容/路线设计问题，留给 Step 2 处理，我未改动
   route_plan 语义，仅如实记录供参考。
2. `main()` 目前无 `--out-dir`/`--check` 等 CLI 开关（`build_dag.py`/
   `build_ledger.py` 有，但那是它们各自 brief 要求的）；如果后续 Step 4 提交流程
   需要类似"非破坏性校验"能力，需要另行加需求，本轮未加（YAGNI）。
3. `run_plan` 对"移动 dict 恰好一个键"之外的格式错误（如零键、多键）也会抛
   `ValueError`（防御性实现的自然结果），但本轮未单独写测试覆盖这一分支——brief
   只要求测未知键场景，未在此外扩测试面。
