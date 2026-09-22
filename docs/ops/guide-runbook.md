# 中文攻略（guide/）生成 runbook

`guide/` 是给中文玩家看的全流程攻略，Typst 排版，成品 `guide/dist/second-novel-guide-zh.pdf` 入库。
流程骨架来自 makapy 的『プレイ日記＆攻略』连载（2010-08，15 篇），分歧条件、门控卡、探索完成
条件与章节 5 的递卡序列按 `data/dag.json` 与 lua 调度器核对补齐。**卡名与选项文字以烤字定译为准**，
不是独立翻译：卡名取 `skeleton/cards.zh.yaml`，选项取 `tools/bake_select.compute_coverage()`
（与 `png/select/` 烤字用的同一个解析器）。

流程正文必须过 `tools/guide_route_check.py` 的引擎模拟（见「路线校验」）。

刻意不写的内容：**encore／谢幕章一字不提**（用户 2026-09-11 裁定：留给中文玩家的小惊喜），
编外卡 196+ 也不入附录——`tools/build_guide.py::load_cards` 直接跳过 `card >= 196`。
**Sakura 的真名「佐仓雪乃／雪乃」也不写**（用户 2026-09-22 裁定）：游戏到章节 5 的现实层才揭晓，攻略
通篇用 Sakura。两条都由 `tests/test_guide.py` 的 `test_no_encore_mention` / `test_no_real_name_spoiler` 守着。

## 一条命令

```bash
uv run python tools/build_guide.py            # gen + pdf → guide/dist/second-novel-guide-zh.pdf
uv run python tools/build_guide.py check      # 无漂移 + 可编译（tests/test_guide.py 调的就是它）
```

依赖：`typst`（`brew install typst`，本机 0.15）、系统装有 Noto CJK SC 或 PingFang/Songti、
`uv sync` 过的 venv（pyyaml；选项解析还要 pillow）。`pdfinfo`/`pdftoppm` 可选，只用于报页数与目检。

## 目录布局

```
guide/
  main.typ                 封面 / 目录 / include 顺序 / 附录编号
  template.typ             版式 + 攻略构件：card() opt() scn() cn() route-box make-cards tip-box warn-box
  chapters/00..10-*.typ    手写正文（阅读须知、序章+章1、章2、章3A、章4、章3B+强制事件、章5、章6、章7+8、EX、完全收集）
  appendix/cards.typ       附录 A：195 张卡（读 generated/cards-table.typ）
  appendix/options.typ     附录 B：134 个选项按钮（读 generated/options-table.typ）
  generated/               gen 产物，入库但勿手改：data.typ（定译字典+格位）、cards-table.typ、options-table.typ、
                           options.json（选项快照）、cells/cNNN.png（195 格 swatch）、card-grid.png（网格总览）
  dist/                    成品 PDF
```

## 定译断言：名字写错 = 编译失败

正文引用卡名/选项名/场景名一律走模板函数：

| 写法 | 渲染 | 断言来源 |
|---|---|---|
| `#card("放学后的约定")` | 『放学后的约定』＋格位色块＋「3行15列」 | `card-titles`（cards.zh title_zh）、`card-pos` |
| `#card("天台", id: 85)` | 同上，同名卡用 id 指定 | 同上 |
| `#card("x", pos: false)` | 只出卡名 | 同上 |
| `#opt("约好了")` | 「约好了」 | `option-texts`（选项烤字 zh） |
| `#scn("游戏结束")` | 〈游戏结束〉 | `scene-titles`（extra 轨 + 卡名覆盖） |
| `#cn(30)` | （卡30） | 无断言，纯排版 |

名字不在集合里 typst 直接报 `未知卡名 …`。定译改了（新 glossary 版本召回卡名）→ 重跑 `gen`，
再编译，报错的地方就是要改的正文。同名卡（『探索：放学后的学校』20/74、『天台』85/119）字典
只留第一个卡号，正文**必须**用 `id:` 指定（`make-cards` 行的第三个元素也是 id）。

## 选卡界面格位（用户 2026-09-11 提出的痛点）

递卡时的选卡界面是 15 列 × 13 行的**固定**网格，槽位顺序 = `snr_common.lua` 的
`cardSort[pos][1] = card`，与持卡情况无关（未持有的格子空白）。像素几何移植自
`oCard.cardModeSet`：`x = (col-1)*30 + {13,17,21}`（每 5 列一组、组间留缝）、`y = row*16+30`、
格 26×15；每格的画面从 `png/sysgim/sys_11_b`（普通）/`sys_11_c`（光标下，亮色）同坐标裁切。

`gen` 据此产出：
- `generated/cells/cNNN.png`：每张卡那一格的亮色版（4× 最近邻放大、白底合成），`card()` 内联；
- `generated/card-grid.png`：全网格总览（3×，叠卡号、行列号），第 1 章「在选卡界面找到一张卡」引用。

改了 `cardSort` 或 sys_11 图（不太可能）→ 重跑 `gen`；`tests/test_guide.py` 只钉 .typ 文本，
不比对 PNG 字节。

### 不要在 `#card(...)` 后面紧跟半角括号

Typst 把紧跟的 `(`/`[` 当参数表；全角括号安全。`#route-box[#story][ … ]` 的正文参数必须用 `[ ]`，
`{ }` 会报 `missing argument: body`。

## 加一章 / 改流程

1. 改 `guide/chapters/NN-*.typ`，需要新章就加文件并在 `main.typ` 的 include 列表登记。
2. 每段流程按「`#story-box`：场景 → 选项 → 场景 …」＋「`#frag-box`：make-cards 表」成对写；
   Game Over 用 `#gameover`，章节完成用 `#complete`。**一律用 `story-box`/`frag-box` 这两个
   别名，不要直接调 `route-box`**：`story-box` 会把格位标注关掉（故事模式只是听、不递卡，
   标了反而碍眼——用户 2026-09-14 裁定），走 `route-box` 就丢了这个行为。
3. 递卡顺序**以 crd 脚本里 `oCard.selectCardObj` 之后的比较顺序为准**（`data/dag.json` 的
   `answers` 是集合、无序——2026-09-12 首版正是因此写反了 4 处）。`build_guide.check_hand_order()`
   把**每个要递卡的谜题**（103 个：80 单卡 + 23 多卡）的 make-cards 行与脚本逐张比对，
   `pdf`/`check`/`tests/test_guide.py` 都跑它，对不上拒绝出盘。写正文时先跑
   `uv run python -c "import sys; sys.path.insert(0,'tools'); import build_guide; print(build_guide.expected_hand_order()[35])"` 看期望序列。

   ⚠ **卡 1 不是哨兵**（2026-09-13 用户反馈 crd_30 漏掉第一张）：识别答案卡只能靠**绑定
   `oCard.selectCardObj()` 的返回变量**，绝不能用「卡号 > 1」去筛。错卡计数器确实会跟 0/1 比，
   但那是另一个变量，绑定后根本进不来；而卡 1『有个女孩子来学校的故事』是 crd_2/30/108 的
   真答案。这条错误约定当时同时存在于三处（`build_dag.parse_crd_answers` 的 `- {0,1}`、
   本工具的 `> 1`、`extract_crd.py` 的 docstring），已一并修正，回归测试见
   `tests/test_guide.py::test_card1_is_a_real_answer`。校验只覆盖 make-cards 行——**散文式
   写递卡会逃过检查**（crd_2 当初即如此），要递卡就写成 make-cards 表。
4. **每个 `#story-box` 必须带机读路线** `from:`（时间轴上重讲的场景 id）与 `pick:`（沿途依次选的
   选项定译），`tools/guide_route_check.py` 会按引擎规则把全书的故事/片段交替重放一遍（见下节
   「路线校验」）。写正文前先用它当神谕：`--trace` 逐步打印沙漏与时间轴，确定这一轮到底讲到哪。
5. `uv run python tools/build_guide.py` 出盘，`pdftoppm -png -r 60 -f N -l N` 抽两页看版式。
6. 提交：工具/模板改动与正文改动分开 commit，`dist/*.pdf` 随正文 commit 一起更新。

## 路线校验：正文写的流程必须按引擎真能走通（2026-09-19）

玩家反馈 5 处错误（章节 1 两条支线压成一轮做卡、『有谁在呼唤』已被截出时间轴、章节 2 做卡顺序
违反前缀要求、『选择：谜题』后还得再讲一轮、章节 3 耗时 100 的选择场景第一次根本选不了），
根因都不在 `data/dag.json`（其状态图、耗时、门控与 lua 一致），而在**正文是照博客手写的，没有
按引擎状态机核过**：typst 断言只管名字对不对，`check_hand_order` 只管一张卡内递卡顺序，谁都
不管「这一轮到底讲到哪」「做卡时场景还在不在时间轴上」。

`tools/guide_route_check.py` 补的就是这一层。它直接解析 `lua_scripts/snr_*_10_*.lua` 的调度器
（if/elseif/while 语句树 + 场景函数的自带耗时/授卡/GameOver/可跳过）——刻意**不**用 dag.json 的
`seq`（扁平事件流，丢了嵌套条件），也不另立一份手维护的 DAG（会漂）。模拟的引擎规则：

- 故事模式选时间轴上某点重讲：ayanoTime 回到该点**开讲前**，该点及其后路线截断（`cClearNumStoryRoute`）。
- 场景结束 `comSectionStoryEnd`：先追加路线，再在**未持该场景卡**时加耗时；≥100 立即 Time over 终止脚本，
  选择场景的选项在其后才弹出——所以未持卡的耗时 100 选择场景第一次讲完就 Time over。
- 片段模式做非 `_sel` 卡：场景在当前路线上，且其前所有非 `_sel` 场景已持卡；`_sel` 卡只要在路线上。
  做成后其后各点 ayanoTime 扣掉该场景耗时（`comAyanoTimeRefresh`）。
- 做卡：req 全持有；答案按 `expected_hand_order`；终卡 run `_f` 授章节梗概卡。持 136 未持 145 进片段模式先得 145。
- 章节 5 的日记场景一开始就全部持卡，每场都问跳不跳：跳过 `s5s_140` 没有去中庭的选择、跳过 `s5s_320`
  直接 Game Over（`s5s_380`）、跳过 `s5s_580` 拿不到三张关键词卡——正文用 `noskip:` 标出。
- 探索地图、谜题按「照攻略做完」处理（循环体跳过）；谜题未持选择卡时用 pick `"谜题答对"`/`"谜题答错"` 指定结果。

正文侧约定（`guide/template.typ`）：`#story-box(from: "s1s_35_sel", pick: ("没有约",), noskip: ())[…]`；
表格化叙述用不渲染的 `#route(from:, pick:, noskip:)`；主菜单直入的现实层用 `#route(event: "s7f")`；
`#frag-box` 的 make-cards 行按序就是做卡步骤。校验项：from 场景在时间轴上、pick 在当时可选且不多不少、
正文 `#card()` 提到的场景卡按序出现在本轮讲到的场景里、`#timeover/#gameover/#complete` 标注与模拟一致、
每张要做的卡在时间轴上且前缀/前置/答案齐备。`build_guide.py check/pdf` 与 `tests/test_guide.py::test_route_feasible`
都跑它，不通过拒绝出盘。

事实速记（模拟器算出、与玩家反馈一致）：教程后第一轮四个 25 的场景在『想起约定』就 Time over；章节 2 的两个
Game Over 互为前置，要来回走三趟；章节 3、4 每轮起点必须是 0 才不重走探索——首版起点 25 的来历与修法见下节。

### 沙漏用完处紧接 Game Over 的轮次必须标 `#deadend`（2026-09-20）

攻略里常见「沙漏在场景 X 用完 → 做卡 → 换分支」，但玩家不知道 X 后面还有没有剧情。校验器对每个
Time over 收尾的轮次跑探针 `Sim.probe_deadend`：假定 X 的卡已持有、从 X 重讲、不给任何选项，若结果是
GAME OVER 且路线只多回 X 自己，就是死胡同——正文必须写 `#deadend`（模板里的固定灰字说明：做完卡
回来接着讲只会问一次跳过、随即 Game Over、没有新剧情）；反之标了 `#deadend` 而探针说不是，也报错。
弹出选择、再次 Time over（后面还有未持卡场景）、章节完成都不算死胡同。全书现有 4 处：
『天台』(85)、『天台的人影』、『抓住手臂』、『Sakura的来信』。

### 别把做不了的选择卡留在路线前缀上（2026-09-20）

每轮重讲的沙漏起点 = 时间轴上该点之前**所有未持卡场景**的耗时之和。`_sel` 选择卡不受
「按顺序做卡」约束，但它的前置卡若要到很后面才有（『选择：颇有意思的传闻』要『章节 5 梗概』），
它就会一直挂在前缀上，之后每一轮都先白付它的 25。首版章节 3 在『选择：楼梯的传闻』选「不知道」
就是这样把它留下的，结果章节 3、4 每轮起点 25，两段探索（`s4s_210_sel`、`s4s_450_sel`）的 25
正好落在 100 上，探索成了时间轴末点，只能从它重讲、地图再走一遍。改选「告诉我」绕开后起点归 0，
两段探索各只走一遍，章节 3/4 还各省 3 轮；章节 6 从 `s1s_35_sel` 重建路线时再经过那一幕做卡。

判断「探索要不要重走」没有通用公式，逐处看三件事：①探索卡的前置卡是不是探索**之后**的场景
（`s1s_200_sel` 的前置在探索结尾自动入手，天然一遍）；②从本轮起点到那个后继场景的未持卡耗时
之和是否 ≤ 100（等于 100 也行——场景先进路线再判 Time over）；③前缀上有没有能提前做掉、
或干脆绕开的场景把起点压低。`guide_route_check.py --trace` 里每轮的「重讲，沙漏回到 N」
就是起点，N > 0 时先查前缀里是谁。

## 数据源变了怎么办

- `skeleton/cards.zh.yaml` 或选项译文变 → `gen` 重生成 generated/，`check` 会报 DRIFT 直到重生成并提交。
- `data/dag.json` 变（换基座后 `tools/build_dag.py` 重跑）→ 附录 A 的前置卡/递卡列随之变；
  正文里的流程要人工对照 `analysis/dag_all.txt` 复核。
- `build/` 被清空 → `compute_coverage()` 缺派生产物时自动退回 `generated/options.json` 快照并
  在 stderr 告警；要刷新快照先跑 `uv run python tools/bake_select.py` 系列产出 `build/select_*`。
