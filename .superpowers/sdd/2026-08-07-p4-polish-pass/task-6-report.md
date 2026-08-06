# Task 6 report：tools/polish_check.py（保税仓机械闸）

状态：DONE。

## 文件

- `tools/polish_check.py`（新增）
- `tests/test_polish_check.py`（新增，10 个用例）

## 接口（与 brief 一致，另加 `repo=` 参数）

`gate(label, channel, repo=None) -> dict`，返回 `{id: {"hard": [...], "warn":
[...]}}`；`repo=None` 时行为与不传完全一致——沿用 Task 3/4/5 同款
`_dir_for(label, repo)` 套路（`polishlib.seg_dir()` 硬编码仓库根，不接受
覆盖；本模块另起一份只在 `repo` 落空时退化到默认路径），使测试能用
tmp_path 造替身仓库、不触碰真实仓库的 `pilot/polish/`。CLI：`--seg <label>
--channel <ch>`，加了对称的 `--repo`。

## id 集裁剪的实现（本任务最关键的一步）

`check_batch.check()` 开头就断言 `source_rows`/`draft_rows` 的 id 集合完全
一致，不一致立刻返回一条 `R1` 硬伤并放弃后续全部检查。`frozen/source.jsonl`
含该 SEG 全部 id（含锁定 id），`candidates.<channel>.jsonl` 天生只含非锁定
id（`polish_ingest.ingest()` 判死锁定 id 出稿）——两个集合按定义就不相等。

实现（`tools/polish_check.py` 约第 111–145 行）：
1. 读 `frozen/source.jsonl` 建 `src_jp = {id: jp}`。
2. 读 `candidates.<channel>.jsonl`（文件不存在则视为空列表），按 id 建
   `last_by_id`（同 id 后行覆盖前行，实现"取最后一条"，见下）。
3. 求 `ids = list(last_by_id)`，与 `src_jp` 取交集（详见下方"stray id"处理），
   据此**裁剪** `cropped_source = [{"id": i, "jp": src_jp[i]} for i in ids]`
   与 `draft_rows = [{"id": i, "zh": last_by_id[i]["zh"]} for i in ids]`——
   两者 id 集合按构造必然相等，`check()` 的 R1 恒不触发，R2a/R2b/R2c/
   W1/W2/W3 才有机会真正跑到。

已用**变异②**验证：把裁剪代码换成 `cropped_source = source_rows`（不裁剪，
直接传全量 frozen id），10 个测试里 8 个转红，且全部转红形态一致——
`gates == {0: {"hard": [{"id": 0, "rule": "R1", ...}], "warn": []}}`，与
brief 描述的"恒绿闸"完全对应（闸看起来跑了、产出了文件，实际只吐一条 R1
就放弃，别的规则一条都没机会跑）。

**stray id 防御**：若 `candidates` 里出现不属于这个 SEG 的 id（正常流程
不会发生——`ingest()` 已经把非本批 id 判死过一轮），`gate()` 打印告警
（`stderr`）后跳过该 id，不崩溃、不影响其余 id 的裁剪与检查。

## gates.json 的最终结构与"全绿 id 是否收录"的选择

结构：`{id: {"hard": [...], "warn": [...]}}`，**只收有问题的 id**（hard 或
warn 至少一项非空）；全绿的 id 不进字典。

理由：`gates.<channel>.json` 的用途是"标出问题供 Task 7 分流消费"——Task 7
需要的判断是"某 id 是否在这份字典里、`hard` 是否非空"，不需要靠这份文件
反查"全库/全候选有多少 id"，那个信息 `frozen/source.jsonl` 与
`candidates.<channel>.jsonl` 本身就已经提供，没有必要在 `gates.json` 里
重复一份"id: {hard: [], warn: []}"的空壳膨胀文件大小。brief 原文"返回
`{id: {"hard": [...], "warn": [...]}}`"字面上没有明说是否包含全绿 id，
按"机械闸"应该输出"问题清单"而非"全量体检报告"的直觉选择了前者，并在
docstring 里显式写明这个选择，避免后来人以为"id 不在字典里"等于"没检查
过"（正确读法是"检查过且无问题"或"该 id 根本不在这批候选里"，两者需要
结合 `candidates.<channel>.jsonl` 自行区分，`gates.json` 单独不承诺区分
这两种情况——这是本任务范围内可接受的简化，Task 7 消费时天然要先看
`candidates` 文件才知道"这批候选有哪些 id"，`gates.json` 只是叠加在其上
的问题标注层）。

落盘时 JSON 对象键只能是字符串，`gate()` 内存里用 int 键（与仓库里其它
按 id 建索引的字典同一习惯，如 `check_batch.check()` 内部的 `src`/`drf`），
写盘前显式 `{str(k): v for k, v in sorted(gates.items())}` 转换并排序，
与既有先例 `tools/check_charlevel.py` 的 `per_id` 输出同一约定（该模块
第 206 行同样这么做）。`gate()` 的**返回值**仍是 int 键字典，调用方（未来
的 Task 7）若要按 id 查找可以直接用 int，不需要额外转换；只有磁盘文件
是 str 键，这一点在报告与 docstring 里都写明了，避免和"in-memory 用 int、
磁盘用 str"这一常见陷阱混淆。

## active.json 术语映射的取法

`glossary/active.json`（`frozen/glossary/active.json`，Task 4
`polish_setup._copy_glossary()` 已确认会拷贝这一份）实测就是扁平的
`{术语: 定译}` 字典（如 `{"あらすじ": "梗概", "コックリさん": "钱仙", ...}`），
与 `check_batch.check()` 的 `glossary` 参数期望的形状完全一致——不需要
任何转换，`gate()` 直接 `json.loads()` 后原样传入即可。文件不存在时传
`None`（`check()` 内部 `if glossary:` 会整体跳过 W2）。

## speakers 的取法——与 brief 补充信息的一处已知偏差

brief 补充信息第 1 条写"`speakers` 取 `glossary/speakers.json`（本任务
应取冻结面的那份：`frozen/glossary/speakers.json`）"。**实测这个文件目前
并不存在**：用临时仓库跑了一遍 `polish_setup.setup()`，`frozen/glossary/`
下只有 `active.json`/`anchors.yaml`/`polish.md`/`style.md`/`voices/` 五项
（见下方"实测证据"），`speakers.json` 从未被 `_copy_glossary()` 纳入 SEG
冻结快照——这是 Task 4 遗留的一个真实缺口，不是本模块的臆测。

实测证据（本次实施过程中跑过，未落任何东西进真实仓库，只在系统临时目录）：
```
frozen/glossary contents: ['active.json', 'anchors.yaml', 'polish.md', 'style.md', 'voices']
```

处理方式（`tools/polish_check.py` 的 `_load_speakers()`）：
1. 优先读 `frozen/glossary/speakers.json`——一旦上游把这个缺口补上，
   本模块无需任何改动就会自动切到读冻结面。
2. 该文件不存在时，退化到 `<repo>/glossary/speakers.json`（车道/仓库根）
   ——这与 `check_batch.py` 自身 CLI（`main()`）的既有约定完全一致：它
   本来就是从 `groot / "glossary" / "speakers.json"` 读，`groot` 可以是
   `--lane-dir` 或仓库根，从未要求必须来自某个 SEG 的冻结快照。这不是
   本模块发明了新约定，只是复用了 `check_batch.py` 已经在用的那一条。
3. 两处都没有时传 `None`（`check()` 内部对应分支会跳过名字映射校验，
   但**不影响 R2b 的结构对齐检查**——那部分是恒查的，与 `check_batch.py`
   的 P1c 硬化一致）。

为什么不直接去修 `polish_setup.py` 补上这个拷贝：那是 Task 4 已提交、
已有独立测试基线的文件，修补它不在本任务（Task 6）范围内，且会改变
其他任务的测试基线，风险收益不对等；而"退化到仓库根"这个方案本身对
`gate()` 的正确性没有损害（speakers 表变动频率远低于正文译文，不属于
"易变的 opus 车道数据"，仓库根这份缺乏 SEG 级冻结不构成实质风险）。

已用 `test_speakers_fallback_to_repo_root_when_frozen_copy_absent` 验证：
显式断言 `frozen/glossary/speakers.json` 不存在，同时用一个"名字映射
错误"（【绫乃】vs 表里定义的【彩野】）的候选确认 R2b 的**名字映射分支**
确实被触发（不是巧合走了"表未覆盖=只查结构不查名字"的宽松分支）。

## W4 分工说明与 R2b↔Task5 错位侦测的关系

均已写入 `tools/polish_check.py` 模块 docstring："W4 不在此跑"专节明确
`siblings` 恒传 `None`，W4 完全不跑（不是"跑了没查出问题"），职责移交
Task 11；"R2b 与 Task 5 错位侦测的关系"专节点明 R2b 是 Task 5 错位侦测
残留面（模型把错位 zh 又润色改写过、不再逐字等于任何 opus）的主要兜底
——与 Task 5 报告"修复轮"里"残留边界"一节引用本模块的描述对应一致
（Task 5 docstring 第 119–128 行同样点名 Task 6 R2b 作为下游兜底）。

## 同 id 多条候选：取最后一条

`last_by_id` 按 id 建字典、后行覆盖前行——天然实现"最后一条"语义，与
`check_batch.py` 对 forward/patches 的 append-only "后来者为现行"是同一
约定。已用 `test_multiple_candidates_same_id_last_wins` 验证：先确认初始
干净状态、追加一条带 R2b 违规的新记录后应变红、再追加一条改回干净内容后
应变回绿——三段式验证"取最后一条"是动态生效的，不是"一旦出现过问题就
永久标记"。

## 两个变异的红绿实况

命令统一：`uv run pytest tests/test_polish_check.py -q`；每次用 Edit 改
一处、跑测、记录、再用 Edit 还原（未使用 git checkout/restore）。

**变异①（brief 给定）：gate 吞掉 hard 只留 warn**（把
`for v in result["hard"]: gates.setdefault(...)["hard"].append(v)` 换成
`for v in result["hard"]: pass`）→ 5 个测试真红：
`test_missing_speaker_prefix_is_hard`、`test_gates_json_matches_return_value`、
`test_multiple_candidates_same_id_last_wins`、
`test_speakers_fallback_to_repo_root_when_frozen_copy_absent`、
`test_cli_reports_hard_count`——全部因为期望的 R2b hard 条目消失
（`assert 12 in gates` → `assert 12 in {}`）而红，符合预期：hard 被吞掉后
这些原本该报 hard 的 id 完全从问题字典里消失。

**变异②（本任务自行补充）：gate 把 source_rows 用全量 id（不按候选裁剪）
传进 check()**（把 `cropped_source = [{"id": i, "jp": src_jp[i]} for i in
ids]` 换成 `cropped_source = source_rows`）→ 8 个测试真红（10 个里除
`test_stray_candidate_id_skipped_not_crashed` 外全部转红，那一条巧合地
不依赖 gate 报告任何问题，其余全部依赖），全部转红形态一致：
```
gates == {0: {'hard': [{'id': 0, 'rule': 'R1', 'msg': 'id 集合不一致 src=4 draft=3'}], 'warn': []}}
```
即"只剩 R1、别的闸一条都没机会跑"这种恒绿闸形态被精确复现——src=4
是 frozen 全量 id（10/11/12/13），draft=3 是候选覆盖的非锁定 id
（10/11/12），两者天然不等。

两个变异全部按预期真红，没有出现"测试无牙"需要澄清的情况——每次变异
命中的正是它本该命中的那条闸，且都通过 Edit 精确还原（已用
`uv run pytest -q` 确认还原后仍是 635 passed）。

## 测试输出

```
uv run pytest tests/test_polish_check.py -q
..........                                                                [100%]
10 passed in 0.07s~0.13s

uv run pytest -q
635 passed in 3.23s~3.47s        # 625（本任务开始前基线）+ 10（本任务新增）
```

## 与 brief 的偏差

1. `gate()`/CLI 增加 `repo=None` / `--repo`：测试基础设施要求（同
   Task 3/4/5 先例），不改变默认行为。
2. brief 补充信息里"`speakers` 应取 `frozen/glossary/speakers.json`"与
   实测不符（该文件不存在，Task 4 `polish_setup._copy_glossary()` 从未
   拷贝它）——已在"speakers 的取法"一节详细记录裁定与实测证据，采用
   "frozen 优先、缺失退化到仓库根"的方案，不改动 Task 4 已提交文件。
3. brief 只给出一个变异（"gate 吞掉 hard 只留 warn"），补充要求里
   要求"至少再加一个"——已补充变异②（不裁剪 source_rows），专门针对
   本任务 brief 明文强调的"id 集裁剪"这一核心实现点，两个变异合起来
   覆盖了 gate() 里两处最容易被悄悄破坏而不被发现的逻辑。
4. `gates.<channel>.json` 只收有问题的 id、不收全绿 id——brief 字面
   没有明说，已在"gates.json 的最终结构"一节写明选择理由。
5. TDD 步骤：实现与测试同批写出，随后一次性跑通（10 passed，一次到位），
   把关效果改由变异自检兜底验证（两个变异都命中预期测试），与 Task 5
   的先例（brief 明确接受"实现与测试同批写出"这一执行方式）一致。

## Concerns（供后续任务参考，非阻塞）

- Task 7 消费 `gates.<channel>.json` 时需要注意：磁盘上的 key 是 str
  （JSON 限制），若直接用 int 型 id 去 `gates.get(some_int_id)` 会永远
  查不到，需要 `str(id)` 或反向 `int(k)`；已在报告与模块 docstring 里
  分别写明这一点。
- `gates.json` 不区分"该 id 没问题"与"该 id 根本不在这批候选里"——两种
  情况都表现为"不在字典里"。Task 7 若需要区分，应结合
  `candidates.<channel>.jsonl` 自行判断，`gates.json` 单独不承诺这个
  区分能力（设计选择，见"gates.json 的最终结构"一节）。
- speakers 的"frozen 优先、缺失退化仓库根"方案只是权宜之计：如果未来
  某个 SEG 冻结之后，仓库根的 `glossary/speakers.json` 又发生了修订
  （理论上术语层也是 append-only glossary 版本化管理，speakers.json
  本身版本管理机制未知），`gate()` 读到的会是"当前仓库根"而非"冻结时点"
  的 speakers 表，与"SEG 冻结之后所有执行通道共读同一份快照"的设计
  原则有一个理论上的缝隙。建议 Task 4 或后续维护把 `speakers.json` 补进
  `_copy_glossary()` 的拷贝清单，彻底消除这个缝隙（本任务未做，因为
  会改动其他任务已提交的文件与测试基线）。

---
