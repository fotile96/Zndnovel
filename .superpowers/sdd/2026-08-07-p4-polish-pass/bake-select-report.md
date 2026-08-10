# `png/select/` 烤字第四块：**渲染**（2026-08-10）

> 范围：本轮做**实际渲染**（上一轮 `select-survey-report.md`/`select_layout_spec.md`
> 只做了测绘 + 解析器 + 日文核验，明确没有渲染）。工具：`tools/bake_select.py`（新）。
> 测试：`tests/test_bake_select.py`（新，28 条）。产物：`build/select_zh/`（268 张按钮 PNG
> + `_compare.png` + `_cellzoom.png` + `_size_ab.png` + `manifest.json`）。

## 一、覆盖率：独立复算，134/134，与上一轮缓存结论一致但走的是不同的实现路径

任务要求"自己重算一遍，不要信任 `build/_select_coverage.json`"。`tools/bake_select.py::
compute_coverage()` 完全不读那个文件，从三层源头各自重新加载并合并：

| 层 | 来源 | 复算结果 |
|---|---|---:|
| 1 | `data/select_buttons_zh.jsonl`（92 条按钮级映射，逐张读图确认） | 覆盖 92 个不同按钮 |
| 2 | `data/select_options_zh.jsonl`（61 条选项级映射） | 覆盖 69 个按钮（**69/69 与第 1 层完全重叠**，zh/jp 逐条比对 0 处不一致——已用 `compute_coverage()` 内置断言钉住，若未来两份文件不同步会直接报错，不会被吞掉） |
| 3 | `build/select_option_map.json`（推导 jp）经 `build/select_ink_verify.json` 的 `status=="match"` 过滤，再查 `data/extra_translated.jsonl` / `build/extra_derived.jsonl`（仅 `confidence=="exact"`）取 zh | 覆盖剩余 42 个按钮，**0 个冲突、0 个查无译文** |

**134 个真实按钮（`png/select/` 里 250×26 的 268 张文件，独立用 PIL 重新枚举去重，不是读缓存数字）
全部覆盖，`missing == []`。** 复算数字与 `docs/ops/bake-decisions.md` 交办时给出的
`build/_select_coverage.json`（134 covered / 0 missing）一致，但这次是从三份原始数据文件
各自重新加载、重新合并、重新校验一致性后独立得出的，不是复用同一份缓存。

`compute_coverage()` 是 `run()` 的强制前置步骤：`missing` 非空会直接 `raise
RuntimeError`（三处变异测试之一验证了这条闸真的有牙，见第五节 M3）。

## 二、文字区矩形的确定方式

对 `sel_s1s_35_sel_a_off.png` 做逐行/逐列像素扫描（不是抄测绘文档的数字，重新量了一遍）：

- **边框是 3px 整边框**（不是 1px 发丝线）：`y∈{0,1,2}` 与 `y∈{23,24,25}` 整行、
  `x∈{0,1,2}` 与 `x∈{247,248,249}` 整列都是边框双环色，与内部纯色填充判然两分
  （`test_border_frame_is_3px_all_sides_real_asset` 钉住四边）。
- **内部纯色区** `x∈[3,246], y∈[3,22]`：off=`(0,0,0,129)`，on=`(235,164,128,255)`，
  与上一轮测绘结论一致。
- **共享透明图标缺口** `x∈[5,10], y∈[5,6]`（跨全部按钮字节级相同，上一轮已证）落在内部
  纯色区**之内**，但落在本轮选定的 `TEXT_BOX` **之外**——不需要任何特判代码，像素保全闸
  自动保护它（`test_shared_icon_notch_is_transparent_and_outside_text_box` 直接验证）。
- **`TEXT_BOX = (15, 3, 235, 23)`**：以上一轮测绘的实测墨迹中心 `(124.5, 12.5)` 为中心，
  半宽取 `min(124.5-15, 246-124.5)=109.5` 后取整为 110，得宽度 220px——与上一轮
  `build/select_layout_spec.md` 给出的"220px 可用宽度"建议吻合（本轮是从测绘结论反推出这
  个具体矩形，不是凭空另选一个数）。这个矩形**同时是**渲染定位框和像素保全闸的覆盖矩形
  （同 `tools/bake_scene.py` 的既有约定）。

## 三、字号取值与依据：真实渲染墨迹判据，不是字符数估算

`tools/bake_scene.py` 的溢出判据是"字符数 × 字体前进量"的 textlength 估算（不含描边）；
本轮认为 `select/` 的 `TEXT_BOX` 相对文本长度的余量比 `scene/` 紧得多（尤其是
`s6s_110` 那 6 条），改用**真实渲染墨迹（含描边）**的像素测量作为唯一权威判据
（`measure_ink_extent()`，padded-canvas 技法防止 PIL 静默裁剪掉超界像素，同
`bake_scene.measure_vertical_extent` 的思路但双轴通用化）。

**测量过程**（对全部 134 条真实译文逐条实测，非抽样）：

| 候选字号 | 横向溢出（134 条中） | 纵向溢出 |
|---:|---:|---:|
| 24px | 6（全部 s6s_110） | 133 |
| 22px | 6（全部 s6s_110） | 132 |
| 20px | 6（全部 s6s_110） | 116 |
| 19px | 6（全部 s6s_110） | 27 |
| 18px | 6（全部 s6s_110） | 14 |
| **17px** | **0** | **0** |
| 16px | 0 | 0 |

**17px 是零溢出的最大全局字号**——18px 下纵向溢出的 14 条是普通中文短语（`TEXT_BOX`
高度只有 20px，字号一大就顶到边），横向溢出的 6 条全部是 `s6s_110`。

**最终选定两档级联 `[18, 17]`**（大号优先，逐格回落），而不是直接全局 17px：114/134
按钮在 18px 下已零溢出，能享受更大字号；20/134（含全部 6 条 s6s_110）回落到 17px，回落
在 CLI/`manifest.json`/`_cellzoom.png`（`[FALLBACK]` 标签）三处可见，没有一条是静默的。
`build_render_plan()` 独立复算：`hard_failures == []`（134 条全部至少在 17px 命中），
`fallbacks` 精确是这 20 条。

**`_size_ab.png`**（任务点名要求的字号对照产物）：对 9 个手选难例（最短"去"、最长常规
译文"选择：字条的内容"、标点样例"多半吧……"、全部 6 条 s6s_110）左右并排展示
"17px 级联下限（零回落风险）" vs "实际发货级联结果（多数 18px，按需回落 17px）"，供人
决定是否接受这个级联，还是想要更保守的全局 17px。

## 四、描边颜色：运行时从真实素材实测，非硬编码

`STROKE_BY_VARIANT` 不是写死的 RGB 常量，而是 `measure_ink_colors()` 在模块导入时对 6 张
真实按钮（`STROKE_SAMPLE_BUTTONS`）的 `TEXT_BOX` 区域做像素频次统计，取"不透明且不等于
该态背景填充色"里出现频次最高的颜色作为描边色（描边像素比纯白填充像素多，因为细笔画的
边缘像素多于内部——6 个样本一致验证）：

- **off 描边** 实测 `(84, 88, 142, 255)`——蓝分量(142) > 红分量(84)，"偏蓝"成立。
- **on 描边** 实测 `(212, 96, 88, 255)`——红分量(212) > 蓝分量(88)，"偏红"成立。
- **填充色两态都是纯白** `(255,255,255,255)`，用断言钉死（`_load_variant_colors()` 内的
  `assert`）。

测试只钉"定性方向"（`b>r`/`r>b`），不钉具体 RGB——具体数值本就该来自实测而不是被测试
反过来钉死成"永远不能变"的魔法数字；若未来素材改版导致实测值漂移，测试仍会用同一套算法
重新测出新值并通过，只有当"偏蓝/偏红"这个定性结论本身不成立时才会报警。

## 五、`s6s_110` 半角片假名：如实渲染给定 zh，实测零溢出，未做隐式半角转换

`data/select_options_zh.jsonl` 里这 6 条的 note 记载：**原图**为压宽度用了半角片假名，
建议重制时"照旧用半角/窄形片假名"；但该文件里**实际存的 zh 字段是标准全角 Unicode 片假名**
（U+30xx 区，逐字符 codepoint 核对确认，非半角 U+FF61-FF9F 区）。

本轮**按 jsonl 给定的字面 zh 原样渲染**，不做任何隐式半角替换或字体子集探测（用什么字形
渲染这类"半角片假名"完全取决于霞鹜文楷是否含 U+FF61-FF9F 区字形，这件事本仓库未验证，
贸然替换风险更高）。真实渲染墨迹测量结果：

- 18px：横向实测溢出（`x1 > TEXT_BOX[2]`）——**这条"会溢出"的判断来自像素测量，不是
  估算**（`test_measure_ink_extent_uses_real_rendered_pixels_not_char_count` 用这条真实
  文本直接验证 18px 下越界、17px 下不越界）。
- 17px：横向/纵向均在 `TEXT_BOX` 内，**零溢出**，且不是贴着边界——`_cellzoom.png`/
  `_compare.png` 里肉眼可见有余量。

**结论：按现方案（级联 [18,17]，s6s_110 走 17px 分支）零溢出，无需用户裁决即可发货。**
若未来想让这 6 条也享受 18px（例如验证清楚半角片假名字形可用后专门收窄这几个按钮的渲染
宽度），是一个可选的后续优化方向，本轮不视为阻塞项，仅记录在此供参考。

## 六、变异红绿实况（三组，均用 Edit 应用/复原，未使用任何 git 回滚命令）

| # | 变异 | 操作 | 结果 |
|---|---|---|---|
| M1 | 像素保全闸被关闭 | `find_outside_box_diffs()` 硬编码返回 `[]` | **真红**：`test_find_outside_box_diffs_detects_change_outside_box` 失败（`AssertionError: assert (0, 0) in []`） |
| M2 | 溢出检查被绕过 | `_fits()` 硬编码返回 `(True, {...})` | **真红**：7 个测试失败，包括已知回落集合校验、硬失败构造用例、CLI 输出校验，`pixel-preservation violations` 从 0 跳到 38（因为被绕过的溢出检查放行了本该回落的字号，导致真实渲染墨迹越出 `TEXT_BOX` 反过来触发了保全闸） |
| M3 | 覆盖率缺失的硬停被关闭 | `run()` 里删掉 `if missing: raise` 那段 | **真红**：`test_run_refuses_to_bake_when_coverage_incomplete` 失败（`DID NOT RAISE RuntimeError`） |

三组变异应用后均立即用 Edit 还原，还原后单独重跑 `tests/test_bake_select.py` 确认恢复
28/28 绿色。M2 的失败连带效应（保全闸被"意外"触发）说明这两道闸不是互相独立、各自摆设的
两条线——溢出检查失守会真实污染最终像素，保全闸能接住这个次生故障，是防御纵深在起作用的
直接证据。

## 七、渲染结果与测试

- `build/select_zh/`：268 张按钮 PNG（134 按钮 × on/off）+ `_compare.png` + `_cellzoom.png`
  + `_size_ab.png` + `manifest.json`。
- `manifest.json` 摘要：`num_buttons=134`、`overflow=[]`（0 硬失败）、
  `pixel_preservation_violations=[]`（0 违规）、`fallbacks` 长度 20（字号 114:18px /
  20:17px）、`stroke_colors`/`fill_colors` 两态各自记录实测值、`coverage_evidence` 记录
  三层覆盖的完整拆解数字。
- 全量 `uv run pytest -q`：变异实验结束、还原代码后重跑，**1067 passed**（基线 1039 +
  本轮新增 28，无回归）。

## 八、需要用户裁决的事项

无阻塞项。可选跟进（不影响本轮交付）：

1. **字号级联 `[18,17]` vs 更保守的全局 17px**：`_size_ab.png`/`_cellzoom.png` 已生成
   供人复核；本轮已按级联方案渲染发货，如需改用其它字号组合可直接调整
   `tools/bake_select.py::FONT_SIZE_CASCADE` 重跑。
2. **`s6s_110` 半角片假名字形**：现状（渲染给定的全角 zh，17px 零溢出）已满足硬约束，
   若未来想验证霞鹜文楷是否含半角片假名字形以便让这 6 条也升到 18px，是一个独立的
   小优化，不影响本轮交付。
3. **10 张异形资源（`sel_voice1/2_sel_a`、`sel_map_*`）与 22 张孤儿按钮**：本轮任务
   范围明确排除，沿用 `select-survey-report.md` 第五节"需要用户裁决"的既有记录，本轮
   未新增处理也未新增结论。

## 相关文件路径

- `/Users/fotile96/Zndnovel/tools/bake_select.py`（渲染工具，新）
- `/Users/fotile96/Zndnovel/tests/test_bake_select.py`（测试，新，28 条）
- `/Users/fotile96/Zndnovel/build/select_zh/`（渲染产物，268 张 PNG + 3 张复核图 + manifest）
- `/Users/fotile96/Zndnovel/build/select_layout_spec.md`（上一轮版面测绘，本轮引用/复核）
- `/Users/fotile96/Zndnovel/.superpowers/sdd/2026-08-07-p4-polish-pass/select-survey-report.md`（上一轮测绘+解析器报告）
