# P1b 最终评审修复轮（一次性，全部 findings 一起修）

来源：全分支最终评审（opus）。控制器已分诊，本轮只做下面列出的项；被判「留 P2」的不在本轮。

## Critical 1 — e2e 测试写生产 `work/` 树，存在污染 append-only 翻译轨的具体路径

`tests/test_e2e_dryrun.py:28-41` 跑 `build_context --batch 1` 再写 `work/out/batch_1.draft.jsonl`（〔占位〕文本），`check_batch` 随后盖出 `work/out/batch_1.pass.json`，其哈希**与占位草稿匹配**。评审者跑一次 `uv run pytest -q` 就在真实树里留下了这三个文件。

而 `.claude/cloud-setup.sh:274` 把 `uv run pytest -q` 作为冒烟，CLAUDE.md 又规定**每次云端会话第一件事**就是跑这个脚本；`work/` 在快照复用的容器文件系统里是留存的。于是存在这条链：
「译者做完批次 1 → 下一次会话开机 → pytest 覆盖掉 draft 与 pass 标记 → 操作者按生成的计划走 Step 4 `append_forward`」→ 占位文本带着通过的哈希守卫进入 `data/forward.jsonl`。forward 是 append-only，这种垃圾只能被 patch 盖住、永远删不掉。批次 1 恰好是 P2 第一个要翻的批次。

**改法**（评审者给的方案，控制器采纳）：
1. `tools/pipelib.py`：给 `DATA` 与 `WORK` 加环境变量覆盖——
   ```python
   REPO = Path(__file__).resolve().parent.parent
   DATA = Path(os.environ.get("ZND_DATA", REPO / "data"))
   WORK = Path(os.environ.get("ZND_WORK", REPO / "work"))
   ```
   名字、类型、默认值都不变，纯属加一层可覆盖（这是控制器对「pipelib 既有导出不得改」的例外授权：Critical 值这个代价，且改动是加性的）。
2. `tests/test_e2e_dryrun.py`：用签名里**本来就有、当前没用上**的 `tmp_path`，通过 `subprocess.run(env=...)` 把 `ZND_WORK` 指到 `tmp_path`，让这条测试完全 hermetic。`ZND_DATA` **不要**改（这条测试的价值就在于跑真实 `data/`）。读产物时也要用同一个 work 根，别再用 `pipelib.WORK`。
   注意：`env=` 传字典会替换整个环境，务必 `env={**os.environ, "ZND_WORK": str(tmp_path)}`。
3. 跑完 `uv run pytest -q` 后，**真实 `work/` 树里不得新增或被覆盖任何 `batch_1.*` 文件**——请自己验证并把验证方法与结果写进报告（例如先记录 `work/` 下相关文件的 sha256 与 mtime，跑完再比对；若这些文件当前已被此前的测试跑污染，先记录现状再说明）。

## Important 2 — timeline 的结构信息全是「只写不读」，前缀把互斥分支拼成了连续事件

`tools/gen_timeline.py` 产出 76 条 marker（`text`/`recap`）与 457 个 unit 的 `title`/`unit_kind`/`state`，`tools/gen_batches.py` 只用 marker 的**位置**（`cut_reason=branch`），`tools/build_context.py:41-57` 的 `_render_prefix` **一条都不渲染**（`grep` 确认 `recap` 在 `tools/` 下无人读）。

后果：前缀把同一个 `_sel` 节点的分支一与分支二的讲述**首尾相接**、中间什么都没有，模型会把两条互斥的续写读成先后发生的事件。这正是整个 DAG 工作要防的事（CLAUDE.md：「把…沿途出现的全部文本**按出现顺序**拼成长 prompt」）。评审者实测批次 30 的 `--profile api-A --jp-fallback` 前缀：3713 行连续文本，没有场景标题、没有段落边界、没有 marker。

另注：Task 7 修复轮把 `env["timeline"]` 当「死元素」删了——**它之所以是死的，正是因为 marker 渲染从没实现**。删掉它把「缺功能」变成了「看不见的缺功能」。

**改法**：
1. `tools/build_context.py` 的 `_load` 恢复读 `data/timeline.jsonl`（Task 7 修复轮删掉的那一行）。
2. `_render_prefix` 在拼接前缀正文时渲染结构：
   - 每个 unit 的正文之前插一行小标题，用 unit 的 `title`（例如 `### 【场景】{title}`；`title` 为空时可退化为 `state` 或 `src`）；
   - 遇到 marker 时插入它的 `text` 与 `recap`（例如 `> {text}` 换行 `> {recap}`）——这是整条链路里**唯一**标记非线性的信号，必须出现在前缀里。
   - 前缀里只渲染那些**其 id 真的进了本次前缀**的 unit（被 profile 过滤掉的章别不该留下空标题）；marker 按其在 timeline 中的位置夹在相邻 unit 之间。
3. **必须守住的不变量**：`--baseline none` 与其他档的 `context.md` 在 `"## 五、本批任务"` 之前**仍然逐字节相同**。marker/标题都在前缀里、与 baseline 无关，理论上天然成立——但请补一条断言把它钉死（现有 `test_baseline_only_touches_tail` 可扩展）。
4. 补判别性用例：构造一个含 marker 与多 unit 的 timeline 夹具，断言前缀里出现了 marker 的 `text`/`recap` 与各 unit 的 `title`，且顺序与 timeline 一致。去掉渲染代码必须变红。

**不要**做的：不要改 `chapter` 过滤规则（那是下面被 park 掉的设计议题）；不要改 `data/` 下任何产物。

## Important 5 — `tools/resolve.py` 在混合 id 类型上会抛 TypeError

计划规定 extra 车道的 ids 是 str（「下游按 lane 区分处理」）。`build_context`/`check_batch`/`append_forward` 都已按类型无关或分派处理，但 `tools/resolve.py:28` 的最终装配对合并后的 map 做 `sorted(m)`。实测 `sorted({1:'a','snr_x:5':'b'})` → `TypeError: '<' not supported between instances of 'str' and 'int'`。**任何一个 extra 车道批次入了 forward，`resolve.py --require-complete` 就会死**——而那正是产出可注入 `final.jsonl` 的那一步。

**改法**：`sorted(m, key=lambda k: (isinstance(k, str), k))`（int 在前、str 在后，各自内部有序），并补一条用例：混合 int 与 str 键时 `resolve` 不抛且顺序稳定。改动限定在这一处排序，不要动 `resolve_map` 的语义。

## 必须在合并前修的两处注释（人工资产里的错误陈述）

1. `config/route_plan.yaml:83` —— 注释 `# 无卡31 → 日常段跳过 → GAMEOVER` 说反了。实际：`s2s_10` 的 seq 是 `[{card_gate:31,held:true},{goto:s2s_60},{goto:s2s_20}]`，**持卡 31 才跳过日常段**直奔 s2s_60；不持卡时走 s2s_20 → s2s_40「また、いつもの生活」→ s2s_50 ゲームオーバー。在一个「数据即规范」的仓库里，注释把分支说反比代码里同样的错更危险。请改成与代码、与 CLAUDE.md 一致的表述。
2. `config/gates.yaml:9` —— 注释写「crd_177 的前置卡集合」，但 `dag.json` 里 `crds["177"]["req"]` 是 `[25,133,134,135,136,137,138,145]`，而门控里列的 `[133..138,145]` 其实是 `answers`。**只改注释用词（改成「答案卡集合」之类），不要改门控的取值**。顺带在同一处加一句：门控只能锚在某状态**第一个** unit 上（`check_timeline.py:80-81` 的 `first_pos` 只记首次出现），所以卡片单元与场景单元共享状态时无法被门控——这正是当初必须改写 `s5s_20` 的原因，写清楚免得后人「还原」成 `[177]`。

## 顺带修掉的几处 Minor（都很便宜）

- `tools/check_timeline.py:43` —— `held.add(cid)` 在 card unit 的 state 没有 `scene2card` 映射时会把 `None` 塞进 held。当前从展开器不可达，但这个函数是**刻意独立**的重放，不该被畸形输入毒化自己的状态。加一个 `if cid is not None:` 守卫。
- `tools/gen_plan.py:16` 的 `GLOSSARY_V = 6` 与 `tools/build_context.py:101-103` 从 `glossary/glossary.v*.yaml` 推导出的版本号是两个真相源，而生成的计划会让操作者把硬编码那个盖进 append-only 的 forward 行。改法：保持 `render()` 是纯函数，把版本号在 `main()` 里算好（可复用 build_context 的同一段逻辑或抽个小函数）再当参数传进去。
- `tools/build_context.py:94-95` —— 第一节渲染成 `#` 而二～五节是 `##`，同一份 prompt 里标题层级不自洽。统一成 `##`。

## 明确 **不在本轮**（控制器已 park，留给用户裁决）

- `chapter` 字段语义问题（评审 Important 3/4）：`chapter` 同时被当作批次键、前缀过滤器、计划选择器，而它实际是 lua 文件家族码——把 23% 的语料压成一个 `"crd"` 伪章，且 extra 车道的 chapter 是文件名，导致 `cc`/`api-B` 下 extra 批次前缀恒空。修它要改的是**前缀窗口策略**（评审建议改用 timeline 位置窗口，即 `seqs` 的用武之地），属于会改变 P2 试点测量对象的设计分叉，必须由用户拍板。**不要动。**
- `tools/recall.py` 不参照 `patches.jsonl`（评审 Minor 9）：修它等于给 recall 加新语义（已在新版本打过 patch 的 id 算不算已解决），属设计决定。**不要动。**

## 验收

```bash
uv run pytest -q          # 当前基线 95 passed，补测后应更多且无回归
uv run python tools/check_timeline.py    # 仍须 OK 退出码 0
uv run python tools/build_context.py --batch 1   --profile cc --baseline none    # exit 0
uv run python tools/build_context.py --batch 174 --profile cc --baseline none    # exit 0（extra 车道）
# 三个生成器双跑仍字节确定（dag / timeline / batches）——本轮不该改到它们，跑一遍确认没误伤
```
另外**必做**：验证跑完全套 pytest 之后真实 `work/` 树里没有新增/被覆盖的 `batch_1.*`（Critical 1 第 3 点）。

## 提交

按逻辑拆 commit（`type: 中文摘要`）。建议：
- `fix: pipelib 支持 ZND_DATA/ZND_WORK 覆盖，e2e 测试改为 hermetic`
- `feat: context 前缀渲染 timeline 结构（场景标题与回溯标记）`
- `fix: resolve 对混合 id 类型的排序`
- `docs: 订正 route_plan/gates 两处说反的注释` + 其余 Minor 可并入相应 commit

不要 push、不要建分支。不要动 `data/`、`lua_scripts/`、`png/`、`skeleton/`、`glossary/`。
