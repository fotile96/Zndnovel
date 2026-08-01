# Task 3 报告：F7 行序——ledger `line` 字段 + timeline 单元内行序

**状态**：完成。**预检判定：落 main**（context.md 逐字节相同）。
**commit**：`b285048`（ledger line 字段）、`42472c3`（gen_timeline 行序）、`3d00563`（runbook §4）。
**测试**：`251 passed`（基线 246 + build_ledger 3 + gen_timeline 2）。

---

## Step 1：生产安全预检

### 实验设计（与 brief 的偏差及理由）

brief 给的路径是「`ZND_DATA` 指向临时数据目录 + `--repo pilot/lanes/opus`」。**这条路走不通**：
`build_context.build()` 在传了 `--repo` 时，`_load(repo)` 读的是 `repo/data/*`，
`pipelib.DATA`（即 `ZND_DATA`）根本不参与；`work_root` 也变成 `repo/work`，产物会落进
生产车道的 `work/ctx/batch_100/`。也就是说，按 brief 原样做既不能换掉 ledger，
又会往生产车道里写东西。

改用**等效但更干净**的形态：**造两个只差一个文件的镜像 repo**，全程不写 `pilot/lanes/`。

- `repoA`、`repoB`：scratchpad 下的目录，`skeleton`/`glossary` 符号链接到车道同名目录，
  `data/` 内逐个符号链接到车道 data 的真实目标。
- 车道正在被生产会话写的两个文件（`forward.jsonl`、`patches.jsonl`）先 `cp` 成**冻结副本**，
  A/B 共用同一份——否则两次运行之间生产会话追加译文，差异就不再归因于 ledger。
- 唯一差异：`repoA/data/ledger.jsonl` → 仓库 `data/ledger.jsonl`（旧）；
  `repoB/data/ledger.jsonl` → `scratchpad/newledger/ledger.jsonl`（改过 build_ledger 后
  用 `--out-dir` 生成的新 ledger，**期间 `data/ledger.jsonl` 一字未动**）。
- 批次按指示用 **batch 100**（SEG-3，`chapter=crd`，67 个 id、4 个 seq），profile `cc`、
  baseline `none`；因该批前序大量未译，加 `--jp-fallback` 让前缀能渲染出来
  （这反而**加重**了对 ledger 的读取——2548 条 `〔未译|…〕` 占位全部取自 `ledger[i]["jp"]`）。
- 两次都用**钉死的生产树** `/Users/fotile96/Zndnovel-prod/tools/build_context.py`，cwd 主仓。

### 命令与输出

```
$ uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py \
    --batch 100 --profile cc --baseline none --jp-fallback --repo $SP/repoA
rc=0
$ uv run python tools/build_ledger.py --out-dir $SP/newledger
ledger=16749 (ambient=56)  extra=829
$ uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py \
    --batch 100 --profile cc --baseline none --jp-fallback --repo $SP/repoB
rc=0

$ cmp repoA/.../context.md   repoB/.../context.md    → context.md: IDENTICAL
$ cmp repoA/.../source.jsonl repoB/.../source.jsonl  → source.jsonl: IDENTICAL
$ cmp repoA/.../manifest.json repoB/.../manifest.json → manifest.json: IDENTICAL
$ shasum -a 256 …/context.md
1dafa32210db04018aca46df0fb4a359aaeb2525342878a2e1751ec75d23e2e8  (A)
1dafa32210db04018aca46df0fb4a359aaeb2525342878a2e1751ec75d23e2e8  (B)
```

实验非空跑的证据：前缀正文段 2676 行、未译占位 2548 处、source 67 行、context.md 338692 字节。
`manifest.json` 也相同意味着 `ctx_sha` 相同——批次产物指纹不变。

### 静态复核（补强，不替代实验）

生产树 `build_context.py` 对 ledger 只做四处**按字段名**的取用：
`{r["id"]: r for r in read_jsonl(...)}`（建索引）、`i in env["ledger"]`、
`env["ledger"][i]["jp"]`（source 行）、`led[i]["jp"]`（jp_fallback）。没有任何整行序列化。
顺带查了生产树其余读 ledger 的工具（`resolve` / `saturation` / `recall` / `compare_lanes` /
`check_timeline` / `lane_setup`），同样全是 `id`/`jp`/`kind`/`func`/`chapter` 逐字段取用，
无整行透传。故新增字段不可能改变任何在产批次的产物。

### 判定

**逐字节相同 → 加字段对在产批次无影响 → 本任务全部改动落 main。**

### 清理

实验产物（`repoA`/`repoB`/`newledger`/`tldata`/`frozen`）已删除。
`pilot/lanes/opus/work/ctx/` 仍为 40 个批次目录、**无 `batch_100`**；`git status pilot/` 干净。
全程未向 `pilot/lanes/` 写入任何文件。

---

## Step 2–3：ledger `line` 字段

`tests/test_build_ledger.py` 追加 3 条（先红后绿）：

- `test_rows_carry_lua_line_numbers`（brief 原样）
- `test_global_sort_still_by_id_line_is_additive`——brief 里的 `build_from_text` 助手在该文件
  **不存在**，改用 `build(tmp_path)` 吃一个临时 lua 目录（与该文件既有的「跑真仓库子进程」
  风格一致）；断言 `ids == [19, 20]` 且 `lines == [3, 2]`。
- `test_line_is_lua_file_line_not_vms_ordinal`（自加）——注释/空行让 vms 序号与行号脱钩。

实现：`parse_vms_lines` 的循环改 `enumerate(text.splitlines(), 1)`，row 增 `"line": lineno`。
`build()` 的 `ledger.sort(key=lambda r: r["id"])` **原样未动**。

```
$ uv run python tools/build_ledger.py
ledger=16749 (ambient=56)  extra=829
$ uv run python tools/build_ledger.py --check
check: OK
```

### 第二道安全闸：验证再生只是加字段（brief Step 3 断言脚本，真跑输出）

```
$ uv run python -c "…（brief 脚本，另加 line 合法性断言）…"
OK：仅新增 line 字段，顺序与其余字段逐行一致（16749 行）
```

（断言内容：行数 16749 不变；`id` 逐行相同即顺序未变；除 `line` 外每行字段字典完全相等；
`line` 均为 ≥1 的 int。）

F7 例证复核：`id 17181` → `snr_s1_10_s` 第 **234** 行、`func scene_s1s_30`，与 brief 一致。

---

## Step 4：gen_timeline 调查与落码

### 调查结论

**单元内 id 排序确实出自 `tools/gen_timeline.py`**，具体是 `Expander._ids_for` 末行
`return sorted(set(ids))`——默认按 int 大小即消息号排。`emit_unit` 直接把它写进
`unit["ids"]`，`build_context._render_prefix` 再按这个顺序输出前缀正文
（`out.extend(resolved[i] for i in hit)`，`hit` 保持 `row["ids"]` 的次序）。
`build_context` 侧不再排序，`check_timeline` 也只做集合级校验。**排序源只此一处。**

### 落码

`Expander.__init__` 建 `self.pos = {id: (file, line)}`（narrative 行），`_ids_for` 改为
`sorted(set(ids), key=lambda i: (*self.pos.get(i, ("", 0)), i))`。`id` 作同位置 tie-break，
也是 `line` 缺失时的退化序——**既有夹具（LEDGER/LEDGER2…全部无 `line`）行为完全不变**，
这是 23 条既有 gen_timeline 测试零改动通过的原因。

`tests/test_gen_timeline.py` 追加 2 条：
`test_unit_ids_follow_lua_line_order_not_message_id`（后补行形态：id 8000 在中间行，
断言 `[100, 8000, 200]`，按 id 排会得 `[100, 200, 8000]`）；
`test_ids_fall_back_to_id_order_when_line_absent`（缺 `line` 的退化路径）。

### `data/timeline.jsonl` 未再生（留段边界），但已干跑核实

用临时 `ZND_DATA`（只放 `dag.json` + 新 `ledger.jsonl` 的符号链接）跑 `gen_timeline.py`，
产物落临时目录，`data/timeline.jsonl` 未被触碰（`git status data/` 干净）：

```
scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693
timeline 行数 533，差异仅为 ids 重排，涉及 14 个 unit:
  seq 10 snr_s1_10_s      seq 14 snr_s1_10_s     seq 23 snr_crd_6
  seq 82 snr_crd_30       seq 167 snr_crd_49     seq 181 snr_s2_10_f
  seq 234 snr_crd_77      seq 253 snr_s3_10_s    seq 266 snr_s3_10_fa
  seq 334 snr_s4_10_fa    seq 343 snr_s4_10_fb   seq 353 snr_s3_10_fb
  seq 363 snr_s3_10_fc    seq 373 snr_crd_177
```

断言同时验证：`ids` 之外的字段逐行完全相同、每个 unit 的 id **集合**不变（只是次序变）。

### 逆序计数与 P2 数字的出入（需知悉）

用新 `line` 字段对**当前** `data/timeline.jsonl` 复算：**相邻逆序 21 / 16248 对 = 0.13%**，
brief 记的是 47 / 16529 = 0.28%。分母也不同（16248 vs 16529），说明 P2 那次是在**另一份
timeline 快照**上数的（此后 route_plan / unit_funcs / ambient 规则均有演进）。
量级与结论不受影响，例证 id 17181 精确吻合。以本报告的 21/16248 为准。

`data/batches.jsonl` 全程未被触碰（已冻结）。

---

## Step 5：测试与 commit

```
$ uv run pytest -q
251 passed in 1.40s
```

（基线 246 → +3 build_ledger、+2 gen_timeline。）

commit（**均落 main**，按判定）：

- `b285048` `fix: ledger 增记 lua 行号 line 字段（F7 前半，全局序不变）`
  —— `tools/build_ledger.py` `data/ledger.jsonl` `tests/test_build_ledger.py`
- `42472c3` `fix: timeline 单元内按 (file,line) 行序（F7 后半，数据再生留段边界）`
  —— `tools/gen_timeline.py` `tests/test_gen_timeline.py`
- `3d00563` `docs: runbook §4 补段边界数据再生成条目（F7 timeline 行序）`
  —— `docs/ops/p3-production-runbook.md`

**偏差**：brief 是两个 commit（runbook 并入第二个）。拆成三个的唯一原因是 runbook 那段
要写「落码于 `<commit>`」，同一个 commit 里无法自引用哈希；先落码、再用真实哈希写文档。

全程只 `git add` 上列具体路径，无 `git add -A`/`.`。
`git status` 现只剩生产会话自己的 `.superpowers/sdd/2026-08-02-p3-seg1-s2/progress.md`（未触碰）。

---

## 顾虑 / 交接注意

1. **段边界必做**：`uv run python tools/gen_timeline.py` 并核对差异就是上面那 14 个 unit
   的 ids 重排。在那之前，代码（新树）与数据（`data/timeline.jsonl`）对单元内顺序的口径
   不一致——但生产读的是数据文件，故在产行为不变，这正是留边界的目的。
2. **canary 覆盖不到本次改动**：`build_ledger`/`gen_timeline` 都不在
   `check_batch.check`/`detect_collapse.scan`/`build_context` 三者之内（runbook §4.1）。
   本报告的 A/B 实验就是替代性判定依据，已在 runbook §4 留痕。
3. 若将来有别的工具改成整行透传 ledger 行（如把 ledger row 直接 dump 进产物），
   `line` 字段就会开始影响产物——届时需重做本预检。

---

# 评审修正轮（Approved / Critical 0 / Important 2 / Minor 2）

评审独立复现并确认了预检判定（3 个批次 + 阴性对照 + 「拿旧账本重造已发出的 batch 41
上下文、逐字节相同」的时间旅行验证），偏离 brief 换预检设计的理由亦经读码核实。
以下是 2 条 Important 与 2 条 Minor 的处置。本轮为**纯注释/文档改动，未再生成任何数据文件**。

## Important 1（已修）：F7 覆盖面残留——source.jsonl 那一半本轮不修

评审指出：段边界再生 `timeline.jsonl` 后**只有前缀正文的顺序被修正**；批次自身
`source.jsonl` 的行序**不会变**——`build_context` 组 source 走 `for i in b["ids"]`，
直接取 `data/batches.jsonl` 的 ids 数组，而 batches.jsonl **已冻结、不得再生成**
（manifest 哈希锁定），timeline 再生不回流到它。

**而 P2 记录的原始症状恰恰在这不被修的一半**：「id 17181 排到 source.jsonl 第 58 位」
（评审实测 batch 7 第 59/90 位）。原报告与 runbook 都没写这条边界，读者会误以为 F7 已全闭。

处置：runbook §4 的段边界条目下新增「**F7 覆盖面残留**」小节，明确写出
① 覆盖的是 timeline 单元内次序（`_render_prefix` 按 `unit["ids"]` 渲染）；
② 不覆盖的是 `source.jsonl`（取自冻结的 batches.jsonl），本轮永远不修；
③ P2 的 17181 症状属于不修的那一半；
④ 段边界再生后的实际效果是「前缀顺序修正、本批待译行仍是消息号序」；
⑤ 要连这一半一起修需解冻重生 batches.jsonl，属下一轮生产、不在 P3 范围。

**本报告上文（Step 4「逆序计数」段以及顾虑 1）凡提及 F7 修复效果处，一律以此边界为准。**

## Important 2（已修）：47 vs 21 是口径差异，P2 报告**不需要**第二次订正

原报告写「分母不同说明 P2 是在另一份 timeline 快照上数的」——**该归因错误，作废**。
评审查证：`data/timeline.jsonl` 全历史只有 1 个 commit（df71266），`lua_scripts/` 自 P2
以来零改动，且 47/16529 在今天的数据上可逐位复现。我方独立复算确认（`data/ledger.jsonl`
现状）：

| 口径 | 结果 |
|---|---|
| timeline 单元内相邻对、数 `line` 递减 | **21 / 16248 = 0.13%**（本报告用的数） |
| ledger 按 **lua 文件**分组、按 **line** 排，数 **id** 递减对 | **47 / 16529 = 0.28%**（**P2 的数，今天原样复现**） |
| 同上分组但按 **id** 排，数 **line** 递减对 | 30 / 16529 |
| batches.jsonl 每批内相邻对 | 25 / 16520 |

分母 16529 = 16749 行 − 220 个 lua 文件，是**每文件相邻对**总数，与 timeline 口径无关。
P2 是「按文件分组 + 镜像方向计数」，本报告是「按 timeline 单元 + 正方向计数」。
**两个数各自正确，P2 报告不需要第二次订正**（此前已订正过一次 44→45，不要让人误以为又要改）。

运维上以 **21/16248** 为准——它衡量「产物里真正错位的相邻对」，正是段边界要核对的量；
runbook 写 21 保持不变。

同时统一了两处打架且都没写口径的代码注释：`tools/build_ledger.py` 的 `line` 字段注释
（原写「全库 47 处相邻逆序」）与 `tools/gen_timeline.py` 的 `pos` 注释（原写「21 处」），
现在两处都写明各自口径并互相指引。

## Minor（已修）

1. 原报告称「23 条既有 gen_timeline 测试零改动通过」——**既有为 21 条**，21 + 新增 2 = 23。
   订正：本改动的退化设计（缺 `line` 时按 id 排）使 **21 条既有测试零改动通过**。
2. `build_ledger` 写盘走 `pipelib.write_jsonl`（truncate + 逐行写，非 tmp+rename 原子替换），
   而生产车道以符号链接实时读这个 3MB 文件，存在「重写期间被并发读」的时间窗（故障模式
   是响亮崩溃而非静默污染）。按评审意见**不改 `write_jsonl`**（多工具共用，改动面与风险
   不对等），改为在 runbook §4 数据再生成条目加「**执行时机纪律**」一段：数据再生成只在
   段边界执行，且必须确认生产会话不在跑批——这本就是段边界的定义，写明即可。

## 本轮验证与 commit

```
$ uv run pytest -q
251 passed
```

commit：`docs: F7 覆盖面残留说明与逆序口径订正`——
`docs/ops/p3-production-runbook.md`、`tools/build_ledger.py`（注释）、
`tools/gen_timeline.py`（注释）、本报告文件。只 add 这四个路径，未触碰
`pilot/lanes/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/` 与任何 `data/` 文件。
