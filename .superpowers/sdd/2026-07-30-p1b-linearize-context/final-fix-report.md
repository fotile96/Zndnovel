# P1b 最终评审修复轮 — 完成报告

来源：`final-fix-brief.md`。以下逐条给改法、file:line、RED/GREEN 证据；结尾附验收清单完整输出、样例片段、自评审与遗留顾虑。

---

## Critical 1 — e2e 测试写生产 `work/` 树

**改法**：

1. `tools/pipelib.py:7-13`：`DATA`/`WORK` 加 `ZND_DATA`/`ZND_WORK` 环境变量覆盖，名字/类型/默认值不变。
   ```python
   DATA = Path(os.environ.get("ZND_DATA", REPO / "data"))
   WORK = Path(os.environ.get("ZND_WORK", REPO / "work"))
   ```
2. **发现的必要延伸（brief 未逐字列出，但验收标准要求）**：`tools/build_context.py` 的 `ctx_dir` 此前固定用 `repo / "work"`，`repo` 默认 `_REPO`（不受任何环境变量影响）——`build_context.py` 从不消费 `pipelib.WORK`。实测验证：只改 pipelib、不改 build_context.py，单独设 `ZND_WORK` 跑 `tools/build_context.py --batch 1 --profile cc --jp-fallback`，产物仍写进真实 `work/ctx/batch_1/`（见下方"验证方法"）。这意味着 brief 描述的机制（子进程 env 传 `ZND_WORK`）若不动 build_context.py 根本不成立——e2e 测试会在 `read_jsonl(tmp_path/"ctx"/"batch_1"/"source.jsonl")` 处直接 `FileNotFoundError` 崩溃，而不是"不 hermetic"。
   `tools/build_context.py:100-106`：
   ```python
   def build(batch, profile, baseline, repo=None, jp_fallback=False):
       work_root = _WORK if repo is None else Path(repo) / "work"
       repo = Path(repo or _REPO)
   ```
   `repo` 显式传入时（`test_build_context.py` 的 6 个既有用例）保持 `repo/"work"` 不变，不随 `ZND_WORK` 漂移；`repo` 留默认（真实 CLI 路径）时消费 `pipelib.WORK`。`ctx_dir = work_root / "ctx" / f"batch_{batch}"`（`build_context.py:136`）。
   `check_batch.py`/`append_forward.py` 本就直接 `from tools.pipelib import WORK`，不需要改。
3. `tests/test_e2e_dryrun.py:28-44`：用 `tmp_path` 通过 `subprocess.run(env={**os.environ, "ZND_WORK": str(tmp_path)})` 隔离；`ZND_DATA` 不设置；读产物改用 `tmp_path`，不再用 `pipelib.WORK`。

**RED/GREEN 证据**：

- `tests/test_pipelib.py::test_zn_env_vars_override_data_and_work`（真实子进程验证 env 覆盖生效）：GREEN。去掉 `os.environ.get(...)` 那层（改回裸 `REPO/"data"`、`REPO/"work"`）→ RED：
  ```
  E   AssertionError: assert '/home/user/Zndnovel/data' == '/tmp/pytest-.../d'
  ```
- `tests/test_e2e_dryrun.py::test_batch1_context_and_fake_roundtrip`：GREEN。去掉 `build_context.py` 里 `work_root = _WORK if repo is None else ...` 那行（改回 `work_root = repo / "work"`）→ RED：
  ```
  E   FileNotFoundError: [Errno 2] No such file or directory:
      '/tmp/pytest-.../test_batch1_context_and_fake_r0/ctx/batch_1/source.jsonl'
  ```
  （证实：不改 build_context.py，e2e 测试压根跑不起来，不是"不够 hermetic"而是直接崩。）

**work/ 未被污染的验证（brief 要求的"必做"）**：见文末《验收清单完整输出》第 6 节，含四轮独立复现（含一轮真实 `pass.json` 哈希匹配场景）。

---

## Important 2 — timeline 结构信息只写不读

**改法**：

1. `tools/build_context.py:15-29`（`_load`）恢复 `"timeline": read_jsonl(data / "timeline.jsonl")`（Task 7 修复轮删掉的那行）。
2. `tools/build_context.py:41-86`（`_render_prefix`，另抽 `_unit_heading` helper 于 42-45 行）：第一遍保持原语义算出每个 id 是否进前缀（chapter 过滤/译文解析/`jp_fallback`/提前 `return None, i` 全部不变，只是把 `out.append` 改成 `resolved[i] = ...`）；第二遍按 `env["timeline"]` 顺序把 marker 与各 unit 的小标题（`### 【场景】{title}`，`title` 空则退化 `state`/`src`）夹进正文，只渲染其 id 落进 `resolved` 的 unit，`resolved` 耗尽立即停止扫描。
3. **渲染样式的一处偏离字面、有数据支撑的取舍**：marker 只在"已经渲染过至少一个 unit"之后才输出（`started` 标志，`build_context.py:73-85`），比 brief 给的例子更严一档。原因：真实数据实测批次 70（`--profile cc --jp-fallback`）显示，若 marker 不设这道门槛，被 chapter 过滤掉的更早章节会在前缀最前面堆出一堵 **34 条 marker、58 行、前后都没有正文**的墙（见下方样例对比）；这些 marker 原本要消歧的正文已被 profile 过滤掉，脱离正文后只剩噪音，其"分支存在"这层信息也已被骨架卡组的章梗概覆盖。加了 `started` 门槛后，marker 只会出现在两个真正渲染出来的 unit 之间——更贴合 brief 原话"夹在**相邻** unit 之间"（sandwiched，两侧都该是 unit，而不是单侧）。已用 `test_prefix_renders_timeline_markers_and_titles_in_order` 里的"标记零"（无 unit 在前）锁定这条边界；也用真实数据（api-A 批次 30 无此问题，因为它不做 chapter 过滤，第一个 unit 就是全书开头）验证这条改动对"干净"场景零副作用。**这是设计取舍，不是 brief 的字面要求——若认为应严格按字面"必须出现"、不加这道门槛，请告知，改起来是几行内的事（删掉 `started` 变量与其两处判断即可）。**
4. **不变量钉死**：`tests/test_build_context.py::test_baseline_only_touches_tail` 扩展（原有断言不变，追加用 `_multi_unit_env` 构造的、真有 3 unit + 2 marker 的批次 4，比较 `baseline=none` 与 `baseline=revise` 在 `"## 五、本批任务"` 之前逐字节相同，并断言比较的不是两段空前缀）。
5. Minor（`build_context.py:36`）：`_render_skeleton` 的"一、冻结骨架"标题从裸 `#` 改成 `##`，与二~五节层级统一。
6. Minor（`build_context.py:89-97` + `tools/gen_plan.py`）：抽出 `glossary_version(repo)`，`gen_plan.py` 不再消费自己的 `GLOSSARY_V=6` 硬编码，改由 `main()` 调 `glossary_version(REPO)` 算好再传给 `render()`（`render()` 仍是不碰文件系统的纯函数，`glossary_v` 只是新增的显式参数，默认值保留常量供测试兜底）。

**RED/GREEN 证据**：

- `test_prefix_renders_timeline_markers_and_titles_in_order`：GREEN。把 `_render_prefix` 的结构渲染代码整段替换回 `for i in resolved: out.append(resolved[i])`（拼接连续文本）→ RED：
  ```
  E   AssertionError: 缺失 '标题甲'
  ```
- `test_baseline_only_touches_tail`（扩展部分）：同一次回退下 → RED：
  ```
  E   AssertionError: assert '标记一' in '\n译文甲\n译文乙\n译文丙\n\n'
  ```
- `test_skeleton_heading_matches_other_sections_level`：GREEN。`## 一、` 改回 `# 一、` → RED：
  ```
  E   assert '\n## 一、冻结骨架' in '# 批次 1（profile=cc）\n# 一、冻结骨架（中文卡组）\n...'
  ```
- `test_glossary_version_zero_when_absent`：GREEN。`glossary_version()` 硬编码 `return 6` → RED：
  ```
  E   AssertionError: assert 6 == 0
  ```
- `test_main_uses_dynamically_derived_glossary_version`（gen_plan）：GREEN。`main()` 里 `render(...)` 去掉 `glossary_v=glossary_version(REPO)` 那个 kwarg（改回不传）→ RED：
  ```
  E   AssertionError: assert '--glossary-v 9' in '...--glossary-v 6...'
  ```

**样例片段**（真实数据，见文末《渲染后 context.md 前缀样例》一节）。

---

## Important 5 — resolve.py 混合 id 类型排序

**改法**：`tools/resolve.py:26-30`：
```python
write_jsonl(DATA / "final.jsonl",
            [{"id": i, "zh": m[i]} for i in sorted(m, key=lambda k: (isinstance(k, str), k))])
```
`resolve_map` 语义未动，改动限定在这一处排序。

**RED/GREEN 证据**：`test_main_sorts_mixed_int_and_str_ids_without_typeerror`（`tests/test_resolve.py`，用 `monkeypatch.setattr("tools.resolve.DATA", tmp_path)` 跑真实 `main()`，混合 int/str id）：GREEN。把 `key=lambda k: (isinstance(k, str), k)` 去掉（改回裸 `sorted(m)`）→ RED，且是 brief 预告的**同一个** TypeError：
```
E   TypeError: '<' not supported between instances of 'str' and 'int'
```

---

## 两处必须合并前修的注释

1. `config/route_plan.yaml:83`：
   - 改前：`# 无卡31 → 日常段跳过 → GAMEOVER`
   - 改后：`# 持卡31 → 跳过日常段直奔 s2s_60；无卡31 → s2s_20→s2s_40「また、いつもの生活」→ s2s_50 GAMEOVER`
   - 证据：`dag.json` 里 `states["s2s_10"]["seq"] = [{card_gate:31,held:true},{goto:s2s_60},{goto:s2s_20}]`——`held==True` 时 `skip=False`，第一个 `goto s2s_60` 不被跳过，直接命中；`held==False` 时 `skip=True`，`goto s2s_60` 才被跳过，落到第二个 `goto s2s_20`。`s2s_50`/`s2s_60` 的 `title` 分别核实为 `"ゲームオーバー"`/`"夏の予定"`。move 指令本体（`enter/until` 取值）未动，只改了 `#` 后的注释文本。

2. `config/gates.yaml:7-15`：
   - 改前：`# 改用 crd_177 的前置卡集合＝全部章节梗概卡...`
   - 改后：改成"答案卡集合"（`crds["177"].answers`），并说明 `req` 是 `[25,133..138,145]`（多一张卡 25，与 `requires_cards` 列的 `[133..138,145]` 不同），顺带补一句门控只能锚在某状态第一个 unit 上（`check_timeline.py` 的 `first_pos` 只记首次出现）——卡片单元与场景单元共享状态时无法被门控，这正是当初必须把 `[177]` 改写成 answers 集合的根本原因。`requires_cards: [133, 134, 135, 136, 137, 138, 145]` 取值一字未动。

**注释改动验证**：两文件改动后重新 `yaml.safe_load` 解析成功，并逐值比对确认 `s2s_10` 的 `story` move 与 `s5s_20` 的 `requires_cards` 与改动前完全一致；`uv run python tools/check_timeline.py` 仍 `OK`，退出码 0。

---

## 三处 Minor

1. `tools/check_timeline.py:41-47`（`_grant`）：
   ```python
   elif kind == "card":
       cid = scene2card.get(state)
       if cid is not None:
           held.add(cid)
           held.update(dag["crds"].get(str(cid), {}).get("gets", []))
   ```
   （守卫同时包住 `held.add` 与后续 `dag["crds"].get(str(cid))` 查表——cid 为 None 时那次查表本身也是无意义的，一并跳过更干净。）
   **RED/GREEN**：`test_grant_ignores_card_unit_with_no_scene2card_mapping`：GREEN。去掉 `if cid is not None:` 守卫 → RED：`assert None not in {None}`（与 brief 描述完全一致：`None` 被塞进了 `held`）。

2. `tools/gen_plan.py`：见 Important 2 第 6 点（同一处改动，一并说明）。

3. `tools/build_context.py:36`：见 Important 2 第 5 点。

---

## 明确未碰的两处（park 给用户）

- `chapter` 字段语义：`_render_prefix` 里 `if profile in ("api-B", "cc") and ch != cur_ch: continue` 这条过滤规则**一字未改**（`git diff` 已核对，见下）。我的改动只是把"过滤后剩下哪些 id"这一层结果（`resolved`）重新按 timeline 顺序穿起来渲染，没有碰"哪些 id 会被过滤"这层判断逻辑。
- `tools/recall.py`：完全未碰（`git diff 7513ed2..HEAD -- tools/recall.py` 为空，见下）。

---

## 验收清单完整输出

### 1. `uv run pytest -q`

```
........................................................................ [ 68%]
.................................                                        [100%]
105 passed in 2.80s
```
（基线 95 passed，本轮净增 10 条判别性测试，无回归；`-W error::DeprecationWarning` 与常规输出均无告警。）

新增 10 条测试清单：
```
tests/test_build_context.py::test_glossary_version_picks_max
tests/test_build_context.py::test_glossary_version_zero_when_absent
tests/test_build_context.py::test_prefix_renders_timeline_markers_and_titles_in_order
tests/test_build_context.py::test_skeleton_heading_matches_other_sections_level
tests/test_check_timeline.py::test_grant_ignores_card_unit_with_no_scene2card_mapping
tests/test_gen_plan.py::test_main_uses_dynamically_derived_glossary_version
tests/test_gen_plan.py::test_render_glossary_v_is_a_parameter_not_the_module_constant
tests/test_pipelib.py::test_zn_env_vars_default_to_repo_subdirs_when_unset
tests/test_pipelib.py::test_zn_env_vars_override_data_and_work
tests/test_resolve.py::test_main_sorts_mixed_int_and_str_ids_without_typeerror
```
另有 1 条既有测试被**扩展**（非新增计数）：`test_build_context.py::test_baseline_only_touches_tail`。

### 2. `uv run python tools/check_timeline.py`

```
OK
```
exit=0。

### 3. `uv run python tools/build_context.py --batch 1 --profile cc --baseline none`

exit=0。

### 4. `uv run python tools/build_context.py --batch 174 --profile cc --baseline none`

exit=0。已核实 batch 174 确为 extra 车道：`lane=extra chapter=snr_common ids=195`。

### 5. 三个生成器双跑字节确定性

```
$ uv run python tools/build_dag.py       # states=405 scene_meta=527 crds=196, exit=0
$ uv run python tools/gen_timeline.py    # scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693, exit=0
$ uv run python tools/gen_batches.py     # batches: 339 {'main': 173, 'extra': 165, 'ambient': 1}, exit=0
$ diff <(before) data/dag.json        # dag.json: IDENTICAL
$ diff <(before) data/timeline.jsonl  # timeline.jsonl: IDENTICAL
$ diff <(before) data/batches.jsonl   # batches.jsonl: IDENTICAL
$ diff <(before) data/scene2card.json # scene2card.json: IDENTICAL
$ git status --short                  # (空——data/ 无任何漂移)
```

### 6.（必做）`work/` 未被污染的验证

方法：记录 `work/ctx/batch_1/*` 与 `work/out/batch_1.*` 的 sha256 + mtime，跑一次完整 `uv run pytest -q`，再记一次，逐字节 + 逐 mtime 比对。做了三轮，覆盖三种起始状态：

**第一轮**（会话最初的真实污染状态——`work/` 里已有 Task 11 遗留的 `batch_1.{check,draft,pass}.json`）：
```
before: work/out/batch_1.{check.json,draft.jsonl,pass.json} mtime=1785455257（刚被"改动前"的 pytest 跑污染过一次，用作会话基线）
running: uv run pytest -q → 97 passed（当时只完成了 Critical 1）
after:  work/ 全树 find+sha256+mtime 逐行 diff → 空 diff
```

**第二轮**（Important 2 + Minor 落地后，batch_1 的 ctx 内容因 `_render_skeleton` 标题层级修复而合法地变化了一次——这是我改动本身的预期效果，不是污染）：
```
uv run pytest -q → 103 passed → work/ 全树 diff → 空
```

**第三轮 / 最终定论**（brief 描述的完整危险场景：手工模拟"译者产出真的 draft → check_batch 判 PASS → 生成哈希匹配的 pass.json"，即 `work/out/batch_1.{draft.jsonl,check.json,pass.json}` 三件套齐全且 pass.json 哈希与 draft 真实匹配）：
```
$ before=$(find work -path "work/ctx/batch_1/*" -o -path "work/out/batch_1.*" | sort | xargs -I{} sh -c 'sha256sum {}; stat -c %Y {}')
f884e29d...  work/ctx/batch_1/context.md   (mtime 1785456412)
14d5fc56...  work/ctx/batch_1/manifest.json (mtime 1785456412)
2e278da7...  work/ctx/batch_1/source.jsonl  (mtime 1785456412)
304c36cc...  work/out/batch_1.check.json    (mtime 1785456455)
792dbe21...  work/out/batch_1.draft.jsonl   (mtime 1785456455)
e3debebb...  work/out/batch_1.pass.json     (mtime 1785456455)

$ uv run pytest -q
........................................................................ [ 68%]
.................................                                        [100%]
105 passed in 2.61s

$ after=$(同上)
（六行 sha256+mtime 与 before 逐字节相同）

$ [ "$before" = "$after" ] && echo "CONFIRMED: byte- and mtime-identical"
CONFIRMED: byte- and mtime-identical
```

**结论**：三轮独立复现（含一轮精确复刻 brief 描述的"哈希匹配的 pass.json 已就位"场景）均确认——`uv run pytest -q` 跑完后，`work/ctx/batch_1/*` 与 `work/out/batch_1.*` 文件的内容与 mtime **零变化**。`test_e2e_dryrun.py` 已完全 hermetic。

**环境说明（不影响上述结论，但如实记录）**：会话中途 `work/out/`、`work/recall/`、`work/setup-baseline.txt`、`work/setup-pytest.log`、`work/ctx/batch_70` 一度整体消失——事后在 `.superpowers/sdd/.../progress.md` 的 `e1074fc` 提交（非本次会话所作，Claude-Session 同名但另一进程）里找到解释：控制器自己也独立做了一轮"清空 work/ → build_context batch 1 → 记 sha256 → 跑 pytest → 再记 → 指纹完全相同"的核验，清空动作是它做的，不是我的命令或 pytest 造成的（我的代码里没有任何删除 `work/` 内容的逻辑，`build_context.py`/`check_batch.py` 都只创建/覆写）。上面第三轮验证是在此次清空之后、我重新手工搭出危险场景后独立做的，结论不受影响。

---

## 渲染后 context.md 前缀样例片段

### 样例 A —— `--batch 30 --profile api-A --jp-fallback`（跨章不过滤，能看到 marker 消歧互斥分支）

```
〔未译|【きくちゃん】「いーや、してないよ」〕
〔未译|【アヤノ】「うーん、そうだよね……」〕
> 【讲述指针回溯至 s1s_35_sel，本次选第 1 项】
> 重讲：指针回到 s1s_35_sel，本次改选第 1 项。
### 【场景】約束を思い出せない
〔未译|……とは思ったものの……うーむ。〕
〔未译|なんだろう、なにかあったような気がするんだけどなあ……うーん。〕
〔未译|教科書のページをパラパラと捲りながらアヤノは考える。〕
〔未译|【クラスメイト】「アヤノ、なにさっきから一人でうなってんの？」〕
...
```
这正是 CLAUDE.md 强调要防的场景：`s1s_35_sel` 是一个三选一节点，"約束を思い出せない"（想不起约定）与其兄弟分支"約束をしている"（有约定）互斥；改动前两段译文会被直接拼接、模型读来像是先后发生的事，改动后 marker 明确标出"这是重讲/改选了另一项"。

### 样例 B —— `--batch 70 --profile cc --jp-fallback`（chapter 过滤生效，marker 干净地夹在本章 unit 之间）

```
### 【场景】昼休みの廊下
〔未译|アヤノは何をするでもなく、廊下の窓から外の景色を眺めていた。〕
〔未译|風が少し吹いているのか、木々は葉を揺らしていた。〕
〔未译|【アヤノ】「……アイツもホント、ズル賢いよね」〕
...
> 【讲述指针移至 s3s_20_sel】
> 讲述从 s3s_20_sel 继续。
### 【场景】選択：階段のウワサ
### 【场景】選択：興味深いウワサ
...
> 【讲述指针回溯至 s3s_50_sel，本次选第 1 项】
> 重讲：指针回到 s3s_50_sel，本次改选第 1 项。
### 【场景】選択：ウワサとは
```
前缀第一行直接是场景标题（不再有任何 marker 悬在最前面）——这是"marker 需要 `started`"这条取舍的直接效果：改动前（不设 `started` 门槛）这个位置会先出现 **34 条、58 行**、来自更早章节（被 chapter 过滤掉正文的 s1s/s2s）、前后都没有正文的孤立 marker 墙，此处附实测对比：

| | headers | marker 行数 | 前缀首行 |
|---|---|---|---|
| 不设 `started` 门槛 | 9 | 68（34 条） | `> 【讲述指针回溯至 s1s_35_sel...】`（悬空） |
| 设 `started` 门槛（已落地） | 9 | 10（5 条） | `### 【场景】昼休みの廊下`（正文） |

---

## 改了哪些文件

生产代码：
- `/home/user/Zndnovel/tools/pipelib.py`
- `/home/user/Zndnovel/tools/build_context.py`
- `/home/user/Zndnovel/tools/resolve.py`
- `/home/user/Zndnovel/tools/check_timeline.py`
- `/home/user/Zndnovel/tools/gen_plan.py`

配置注释（数据取值未动）：
- `/home/user/Zndnovel/config/route_plan.yaml`
- `/home/user/Zndnovel/config/gates.yaml`

测试：
- `/home/user/Zndnovel/tests/test_pipelib.py`
- `/home/user/Zndnovel/tests/test_e2e_dryrun.py`
- `/home/user/Zndnovel/tests/test_build_context.py`
- `/home/user/Zndnovel/tests/test_gen_plan.py`
- `/home/user/Zndnovel/tests/test_resolve.py`
- `/home/user/Zndnovel/tests/test_check_timeline.py`

未碰（已核实）：`data/`、`lua_scripts/`、`png/`、`skeleton/`、`glossary/`、`prompts/`、`docs/`、`tools/recall.py`；`config/route_plan.yaml` 的移动指令取值、`config/gates.yaml` 的门控取值。

## Commits

```
629614a fix: pipelib 支持 ZND_DATA/ZND_WORK 覆盖，e2e 测试改为 hermetic
10c6f02 feat: context 前缀渲染 timeline 结构（场景标题与回溯标记）
303d146 fix: resolve 对混合 id 类型的排序
85541c3 docs: 订正 route_plan/gates 两处说反的注释，check_timeline 补 None 守卫
f9c7ce6 docs: 最终修复轮完成报告入库
5e242ca docs: 订正 gates.yaml 里同一类说反的分支注释（补修轮，见文末）
```
（`git log --oneline` 起点 `7513ed2`；均直提交到 `claude/cloud-setup-session-a32ocv`，未建分支、未 push。）

---

## 自评审

**完整性**：brief 的 1 条 Critical、2 条 Important、2 处注释、3 处 Minor 全部改到；两处 park 项（`chapter` 语义、`recall.py`）逐行 diff 核实零改动。

**质量**：
- 命名：`resolved`（第一遍解析结果）、`_unit_heading`（小标题回退链）、`work_root`/`glossary_version`——含义与用途对应。
- 渲染样式：用真实数据（批次 30、70）双向验证过，不是纸面设计；发现字面实现在 cc/api-B profile 下会产出一堵孤立 marker 墙后主动加了 `started` 门槛并留痕说明。
- 不变量：`--baseline` 不影响前缀这条用真有结构内容的批次钉死，不再是"两段空前缀凑巧相等"。

**纪律**：
- YAGNI：没有为不需要的场景加参数（如 `build()` 没加从未被调用方用到的显式 `work=` 形参，而是复用既有 `repo` 语义做区分）。
- 范围：`build_context.py` 的 `work_root` 分支与 `_render_prefix` 的 `started` 门槛都超出了 brief 字面枚举的步骤——前者是使 Critical 1 真正生效的必要延伸（已实测证明"不改就崩"，非"锦上添花"），后者是 brief 明确邀请我对渲染样式表态的那一项、且有真实数据支撑；两处都已在上文单独成段说明依据、影响面与"如需改回字面实现该怎么改"，没有静默扩大范围。
- 禁改文件：逐条 `git diff` 核实。

**测试**：10 条新测试全部先跑过 RED（真的删掉/还原产码那一行触发），再确认 GREEN；`test_e2e_dryrun.py` 的 hermetic 化本身也在"改回 `work_root = repo/"work"`" 下验证过会崩给 RED。全程 `uv run pytest -q` 无告警输出。

## 遗留顾虑

1. **`_render_prefix` 的 `started` 门槛是设计取舍，不是字面还原 brief 措辞**——已用真实数据（批次 70：不设门槛会产出 34 条/58 行的孤立 marker 墙）支撑，且已用专门的判别性断言（"标记零"不该出现）钉死这条边界，但这确实偏离了 brief 给的字面例子（"markers 必须出现"没有显式条件）。若你认为应该严格按字面实现、不加这道门槛，告诉我即可，是几行的改动（去掉 `started` 变量与两处判断）。
2. **`build_context.py` 的 `work_root` 分支超出 brief 逐字枚举的步骤**——但没有它 Critical 1 的验收标准（e2e 测试 hermetic）根本无法满足，已用实测（单独设 `ZND_WORK` 而不改 `build_context.py`，产物仍进真实树）证明其必要性，细节见 Critical 1 一节。
3. ~~**顺带发现但未处理**~~ **已在补修轮修复**——`config/gates.yaml:3-4` 的注释与 `route_plan.yaml:83` 同一类说反，控制器核实后要求一并订正，见文末《补修轮》一节。
4. **环境层面的观察，非我方问题**：会话中途 `work/` 下与本次任务无关的旧文件（`work/recall/`、`work/setup-*.{txt,log}`、之前跑过的 `work/ctx/batch_70`）自行消失，后确认是控制器自己独立做核验时"清空 work/"所致（见验收清单第 6 节说明），不是本次改动或 pytest 造成，已在报告里如实记录以免误导后续排查。

---

## 补修轮：`config/gates.yaml:3-4` 同一类说反注释

**背景**：控制器核实报告"遗留顾虑 3"，确认 `config/gates.yaml:3-4`（"锚在 s2s_40 而非 s2s_10"那段注释里"s2s_10 首讲无卡31 → 跳过日常段 → s2s_20..."一句）与已订正的 `route_plan.yaml:83` 属同一类说反，判定必须一并合并前修（在"数据即规范"的仓库里，注释把分支说反比代码里同样的错更危险，这正是最终评审判定"必须合并前修"的那一类）。

**依据**（控制器核实并给出，与我最初做 `route_plan.yaml:83` 时核实的 `dag.json` 结果一致）：
```
s2s_10 seq = [{'card_gate': 31, 'held': True}, {'goto': 's2s_60'}, {'goto': 's2s_20'}]
```
`card_gate` 判真（持卡）时**不 skip**，正常吸收其后紧跟的第一个 `goto`——持卡 31 才跳到 `s2s_60`（跳过日常段）；不持卡时 `skip` 掉那条 `goto`，落到第二个 `goto s2s_20` → `s2s_20`（同样无 `play`，不产生 unit）→ `s2s_40`「また、いつもの生活」→ `s2s_50` GAMEOVER。

**改法**（`config/gates.yaml:1-5`）：

改前：
```
# 锚在 s2s_40 而非 s2s_10——s2s_10 自身只有 card_gate/goto，无 play/subcall，dag 里
# 不产生 unit，门控会因 first_pos 恒为 None 而落空（Task 5 评审 Finding 2）。s2s_40
# 「また、いつもの生活」是本路线第 1 个真正产生 unit 的 s2 场景（s2s_10 首讲无卡31 →
# 跳过日常段 → s2s_20 同样无 play → s2s_40 → s2s_50 GAMEOVER，见 route_plan.yaml）。
```

改后：
```
# 锚在 s2s_40 而非 s2s_10——s2s_10 自身只有 card_gate/goto，无 play/subcall，dag 里
# 不产生 unit，门控会因 first_pos 恒为 None 而落空（Task 5 评审 Finding 2）。s2s_40
# 「また、いつもの生活」是本路线第 1 个真正产生 unit 的 s2 场景（持卡31 → 跳过日常段
# 直奔 s2s_60；无卡31 → s2s_20 → s2s_40「また、いつもの生活」→ s2s_50 GAMEOVER，
# 见 route_plan.yaml）。
```
第 1-2 行（"锚在 s2s_40 而非 s2s_10"的理由本身，即 `first_pos` 恒为 None 那部分）未变，只重写了第 3-4 行里的因果链，口径与 `route_plan.yaml:83` 保持一致。只改注释文字，门控取值（`unit_state`/`requires_cards`）、文件里其余 7 个门控条目一字未动——已用 `yaml.safe_load` 逐条比对全部 8 个门控条目（含 `s2s_40`/`s3s_10`/`s5s_20`/`s7f-10`/`s8s_10`/`e1s_10`/`e2s_10`/`s3fc-10`）与改动前完全一致确认。

**验证**：
```
$ uv run python tools/check_timeline.py
OK   （exit=0）

$ uv run pytest -q
........................................................................ [ 68%]
.................................                                        [100%]
105 passed in 2.45s   （纯注释改动，与补修前测试数一致，无回归，符合预期）
```

**Commit**：`5e242ca docs: 订正 gates.yaml 里同一类说反的分支注释`（单独一个 commit，未与其他改动混在一起）。

---

（完）
