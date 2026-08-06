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

  **（此条 concern 已在下方修复轮里被评审判为 Important 并处置——见
  "修复轮：speakers.json 补齐冻结面 + frozen-only 无回落"一节。）**

---

# 修复轮：speakers.json 补齐冻结面 + frozen-only 无回落

状态：DONE。commit 见文末。

## Finding 复述（评审判定 Important）

原报告"Concerns"一节自报的那条缝隙被评审确认属实并升级为 Important：
`_copy_glossary()` 确实从未拷贝 `speakers.json`，而且**根因不在 Task 6，
在 spec §3 的冻结清单本身**——`docs/superpowers/specs/2026-08-07-p4-polish
-pass-design.md` §3 列出的 frozen glossary 清单（`active.json + voices/ +
style.md + polish.md + anchors.yaml`）漏了它，而 §8 又把"R2b 说话人"列为
机械闸职责的一部分，两处对不上。

评审进一步指出：我原先的处置（`_load_speakers()` 缺失时回落读
`<repo>/glossary/speakers.json`）**没有关上口子，只是缩小了当前的爆炸
半径**——这正是 `polish_context.render()` 已经用变异测试钉死过的同一类
问题（"润色输入只认冻结面，不读活仓库"）。危害是具体的、非假设的：R2b
的说话人映射**直接影响机械闸的判定结果**；某 SEG 冻结之后，若活仓库的
`glossary/speakers.json` 被修订，该 SEG 的机械闸结论会**静默漂移**，而
`polish_setup.verify()` 对此完全失明（它只哈希 frozen 里已登记的文件，
不知道"活仓库又变了"这件事）。原实现今天能跑对，纯粹是因为仓库根恰好
有那份文件，不是设计上的保证。

控制者裁定：**补齐冻结面，不回落读活仓库**（不是本任务自己拍板，是
接到的明确指令，记录在此备查）。

## 处置：跨 Task 3 文件的改动（有意为之，指令要求）

### 1. `tools/polish_setup.py`：`_copy_glossary()` 加拷 `speakers.json`

```python
shutil.copy2(repo / "glossary" / "active.json", g / "active.json")
shutil.copy2(repo / "glossary" / "speakers.json", g / "speakers.json")   # 新增
shutil.copy2(repo / "glossary" / "style.md", g / "style.md")
...
```
函数 docstring 同步加了一段，说明这是"评审 Task 6 时发现并回填的缺口"、
为什么必须在冻结面里（R2b 依赖 + "冻结之后共读同一份快照"的设计原则 +
`verify()` 的哈希登记逻辑本来就要求"该在冻结面里的文件必须真的在"）。

**副作用（预期内）**：`manifest.json` 的 `files` 哈希集多了一项
`frozen/glossary/speakers.json`，凡是"仓库根缺 `glossary/speakers.json`
就会 setup() 失败"——这是故意的：既然 R2b 需要它，SEG 冻结时仓库根没有
这份文件本身就该是硬性失败，不是静默跳过。

### 2. `tools/polish_check.py`：`_load_speakers()` 改为 frozen-only

```python
def _load_speakers(fz: Path) -> dict | None:
    frozen_p = fz / "glossary" / "speakers.json"
    if frozen_p.exists():
        return json.loads(frozen_p.read_text(encoding="utf-8"))
    return None
```
去掉了 `repo` 参数与仓库根回落分支；调用点 `gate()` 里 `_load_speakers(fz,
repo)` 改回 `_load_speakers(fz)`。模块 docstring"speakers 的取法"一节
整段重写：不再自称"合理权宜"，改为记录评审判定的缺陷、根因归属
（Task 3 的清单缺口，不是 Task 6 的锅）、以及"现在只读冻结面、无回落"
这一定案，并显式对齐 `polish_context.render()` 已确立的同一约定。

### 3. spec 与计划文本（根因所在，不改会再犯）

- `docs/superpowers/specs/2026-08-07-p4-polish-pass-design.md` §3（约第
  45 行）：frozen glossary 清单加上 `speakers.json`，紧跟一段简短说明
  （为什么：R2b 需要、冻结面必须自足、SEG 冻结后活仓库再改不该影响
  已冻结 SEG 的闸结论）。
- `docs/superpowers/plans/2026-08-07-p4-polish-pass.md` Task 3 的 frozen
  内容描述（约第 203 行）与骨架代码里 `_copy_glossary` 调用旁的注释
  （约第 254 行）同步加上 `speakers.json`，并简短点出缘由。

### 4. 补测试

**`tests/test_polish_setup.py`**：
- `_mini_repo` 夹具补一行 `(repo / "glossary" / "speakers.json").write_text(
  '{"直哉":"直哉"}', ...)`——不补的话 `_copy_glossary()` 现在会因源文件
  不存在而 `FileNotFoundError`，所有既有测试会先炸。
- `test_glossary_snapshot_contains_expected_files` 补一条
  `assert (g / "speakers.json").exists()`。
- 新增 `test_speakers_json_frozen_matches_source_and_tracked_by_manifest`：
  三段式验证——①`frozen/glossary/speakers.json` 内容与仓库根源文件逐字
  一致；②`manifest.json["files"]` 里含 `"frozen/glossary/speakers.json"`
  这个 key（即 `verify()` 真的在盯着它，不是白拷贝一份没人核验的文件）；
  ③篡改冻结面里的 `speakers.json` 内容后 `verify()` 必须报出漂移（用
  `any("speakers.json" in x for x in drift)` 断言，与既有的
  `test_verify_missing_file_reported` 等测试同一手法）。

**`tests/test_polish_check.py`**：
- 原 `test_speakers_fallback_to_repo_root_when_frozen_copy_absent`（验证
  "回落"这一行为本身）改名为 `test_speakers_read_from_frozen_copy`，语义
  从"验证回落生效"改为"验证现在从冻结面正常读到了这张表"（内容和断言
  基本不变，因为现在 `_build_mini` 默认就会把 speakers.json 冻结进
  frozen，效果等价，只是不再依赖回落路径）。
- 新增 `test_speakers_frozen_only_no_fallback_to_repo_root`（**这条才是
  真正的回归锁**）：构造对抗场景——手动删掉 frozen 里已拷贝的
  `speakers.json`（模拟"该 SEG 冻结时点没有这张表"或"缺口未回填"的历史
  状态），但仓库根仍留着一份内容不同、且**会导致误判**的表
  （`{"彩野":"彩野"}`）；候选的说话人前缀与原文不同（【绫乃】vs 原文
  【彩野】，两边结构上都有【】，不触发结构型 R2b），只有"读到了仓库根
  那份表并按名字映射比对"才会额外触发名字映射型 R2b。断言
  `"R2b" not in {v["rule"] for v in gates.get(12, {"hard": []})["hard"]}`
  ——如果发生了回落，这个候选会被误判出一条不该有的 R2b。
- `_build_mini` 夹具改为**始终**写 `glossary/speakers.json`（默认空字典
  `{}`，`speakers=` 参数覆盖内容）——原因同上，`polish_setup.setup()`
  现在硬性要求这个源文件存在；docstring 同步更新，不再提"gate() 的
  fallback 读取路径"。

**受牵连但与本 finding 无直接关系的两个夹具文件**（`polish_setup.setup()`
现在硬性要求 `glossary/speakers.json` 存在，凡是自建 mini repo 走
`ps.setup()` 的夹具都要跟着补，否则会在 setup() 阶段就 `FileNotFoundError`
炸掉，这不是新增测试而是让既有测试继续能跑）：
- `tests/test_polish_ingest.py`：三处 `_build_mini`/`_build_mini_recurrence`/
  `_build_mini_short_collision` 夹具各补一行
  `(repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")`。
- `tests/test_polish_context.py`：`_build_mini_seg` 夹具补一行同样的写入
  （空字典 `{}`——这些测试本来就不依赖 speakers 表的具体内容）。

## 变异红绿实况

命令统一：先跑 `uv run pytest tests/test_polish_setup.py tests/test_polish
_check.py -q` 定位受影响测试，再跑全量 `uv run pytest -q` 确认没有连带
破坏；每次变异用 Edit 改一处、跑测、记录、再用 Edit 精确还原（未使用
`git checkout`/`stash`/`restore`）。

**变异④（本轮新增，验证"frozen-only 无回落"这条修复本身有牙）**：把
`_load_speakers(fz)` 改回带 `repo` 参数、缺失时回落读
`<repo>/glossary/speakers.json`（并把 `gate()` 里的调用点同步改回
`_load_speakers(fz, repo)`，精确复现修复前的完整代码路径）→
`test_speakers_frozen_only_no_fallback_to_repo_root` 真红：
```
AssertionError: assert 'R2b' not in {'R2b'}
```
（frozen 里没有表、仓库根有一份会导致误判的表——回落路径一旦被误改
回来，这条候选立刻被判出不该有的 R2b，证明这条回归锁确实在盯着"是否
发生了回落"这件事，不是摆设。）其余 10 条既有测试在这次变异下仍然
通过（`1 failed, 10 passed`）——符合预期：只有专门针对回落场景设计的
这一条会红，其余测试不依赖回落是否发生。变异后已用 Edit 精确还原两处
（函数体与调用点），复跑确认 `test_polish_setup.py`/`test_polish_check.py`
/`test_polish_ingest.py`/`test_polish_context.py` 合计 66 passed。

（Task 6 原报告已有的两个变异①②——"gate 吞掉 hard"、"source_rows 不
裁剪"——本轮未重跑，因为本轮改动没有触碰 `gate()` 内部这两处逻辑，只
改了 `_load_speakers()` 的实现与调用参数；已用全量回归测试 637 passed
确认这两处判据仍然完好。）

## 测试输出

```
uv run pytest tests/test_polish_setup.py tests/test_polish_check.py -q
..........................                                                [100%]
26 passed in 0.40s

# 修 test_polish_ingest.py / test_polish_context.py 夹具前（受
# _copy_glossary() 新增源文件依赖牵连，非本 finding 直接范围）：
uv run pytest -q
597 passed, 40 errors in 3.98s

# 三处 test_polish_ingest.py 夹具 + 一处 test_polish_context.py 夹具补
# glossary/speakers.json 后：
uv run pytest tests/test_polish_ingest.py tests/test_polish_context.py \
  tests/test_polish_setup.py tests/test_polish_check.py -q
..................................................................       [100%]
66 passed in 0.40s/0.42s

uv run pytest -q
637 passed in 3.36s~3.44s   # 625（Task 6 开始前基线）+ 10（Task 6 初版）
                            # + 2（本轮新增：test_polish_setup 1 条 +
                            #   test_polish_check 净增 1 条）
```

## 与指令的关系 / 偏差

1. 指令明确要求"跨 Task 3 的文件，这是有意的"——`tools/polish_setup.py`
   与 `tests/test_polish_setup.py` 的改动均按此执行，未额外征询。
2. 指令要求"更新断言时要确认你改的是期望值而不是把测试改松"——
   `test_glossary_snapshot_contains_expected_files` 只是**增加**一条
   `assert (g / "speakers.json").exists()`，未删减/放松任何既有断言；
   新增的 `test_speakers_json_frozen_matches_source_and_tracked_by_manifest`
   是全新的强断言（内容一致 + manifest 登记 + 篡改可检测三重验证），
   不是放松版本。
3. 指令范围外、但为了让全量测试保持绿而必须一并处理的连带修复：
   `tests/test_polish_ingest.py`（三处夹具）与
   `tests/test_polish_context.py`（一处夹具）补 `glossary/speakers.json`
   源文件——这些改动只是"让 `ps.setup()` 不因缺源文件而炸"，不改变
   这两个文件里任何测试的断言逻辑或期望值。
4. C2（`gates.json` 落盘 str key / 内存 int key）按指令"本轮不用处理"
   保持原样，等待 Task 7 指令点明。

---
