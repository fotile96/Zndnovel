# 中文攻略（guide/）生成 runbook

`guide/` 是给中文玩家看的全流程攻略，Typst 排版，成品 `guide/dist/second-novel-guide-zh.pdf` 入库。
流程骨架来自 makapy 的『プレイ日記＆攻略』连载（2010-08，15 篇），分歧条件、门控卡、探索完成
条件与章节 5 的递卡序列按 `data/dag.json` 与 lua 调度器核对补齐。**卡名与选项文字以烤字定译为准**，
不是独立翻译：卡名取 `skeleton/cards.zh.yaml`，选项取 `tools/bake_select.compute_coverage()`
（与 `png/select/` 烤字用的同一个解析器）。

刻意不写的内容：**encore／谢幕章一字不提**（用户 2026-09-11 裁定：留给中文玩家的小惊喜），
编外卡 196+ 也不入附录——`tools/build_guide.py::load_cards` 直接跳过 `card >= 196`。

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
2. 每段流程按「★故事模式：场景 → 选项 → 场景 …」＋「★片段模式：make-cards 表」成对写；
   Game Over 用 `#gameover`，章节完成用 `#complete`。
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
4. `uv run python tools/build_guide.py` 出盘，`pdftoppm -png -r 60 -f N -l N` 抽两页看版式。
5. 提交：工具/模板改动与正文改动分开 commit，`dist/*.pdf` 随正文 commit 一起更新。

## 数据源变了怎么办

- `skeleton/cards.zh.yaml` 或选项译文变 → `gen` 重生成 generated/，`check` 会报 DRIFT 直到重生成并提交。
- `data/dag.json` 变（换基座后 `tools/build_dag.py` 重跑）→ 附录 A 的前置卡/递卡列随之变；
  正文里的流程要人工对照 `analysis/dag_all.txt` 复核。
- `build/` 被清空 → `compute_coverage()` 缺派生产物时自动退回 `generated/options.json` 快照并
  在 stderr 告警；要刷新快照先跑 `uv run python tools/bake_select.py` 系列产出 `build/select_*`。
