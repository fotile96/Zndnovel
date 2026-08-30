# 烤字工程交接（2026-08-30 第三轮）——sysgim 收口，下一批 cutin/tut_*

> 接 `bake-handoff-2026-08-29b.md`（其 §1–§7 全部有效）。本文件只记 8-30 当天的
> 收尾状态与下一步。**新 session 从「下一批」一节开工即可。**

## 1. 当前状态（HEAD = c05f3aa 一线）

- **`png/sysgim/` 61 张全部收口**：`build/sysgim_note_zh/` 六张
  （sys_2_a/3_a、sys_12_a/b/c、sys_1_i）于 8-30 完成并经四轮用户反馈迭代定稿。
- tests **1548 passed**；结构校验（保留层意外改动 0 / 擦除区外越界 0）全绿；
  四道闸绿。
- 工作树只有三项与烤字无关的既存改动（.claude/settings.json、
  data/api_ledger.jsonl、pilot/read-edits/opus.draft.jsonl）。

## 2. sysgim_note 面的关键机制（新面照抄这套）

- 工具：`tools/bake_sysgim_note.py`＝`bake_para_glow.Spec` 第 5 份；
  遮盖规划器 `tools/bake_mask.py::plan_geo`；数据 `data/sysgim_note_text.jsonl`
  （逐行：box/jp/zh/align/bg/r_old/geo）。
- **遮盖判据＝几何足迹**（逐保留层一个保守半径），protect＝到该层字芯的
  欧氏距离 < r。不要走「强度上界/连续曲线」的路——e1ea395 与 E11′ 两轮
  实测都证明其失败模式在危险侧（详见 bake-decisions E8/E11′）。
- 行级参数（数据行覆盖 geo）：`bg`（按行采样的底色 ARGB）、`r_old`（该行
  擦除半径：原位替换的行小 r=2.5–3，旧行原位无新字的行大 r=6 全清）、
  `line_ratio`（渐变墨/黑带底色下需调）、`fill_soft`（修字芯+模糊的软晕
  填充，慎用——四版对照见 E20h/E20f）、`core_ratio_hi`（字心 plateau 色，
  白字 0.95；棕/渐变墨不用——会把墨色提成白热）、`align`（left/center/
  ref_center/ref_right）。
- 白芯判据的**无彩色约束**（max−min≤60，E20i）：彩色晕的亮像素
  (150,255,150) 族会冒充白芯——不加这条，晕场会被字芯判据吞掉。
- keep_red_glow（保留层红晕场原地保留）带距离闸 `red_death`，且只对
  确认是「保留层晕」的组开——行1 棕橙晕 (200,80,60) 会过色相测试，
  须用到该层芯的距离闸住（'>' 形 artifact 的教训，E20i）。

## 3. 已知残留（用户已知，非阻塞）

- `sys_1_i` 行3 下缘：拉普斯拉对红晕硬边的固有平滑带（宽约 2px，
  α73–89 vs 原 164，1:1 不可见）。要彻底消除需方向性重建，另立项。
- `sys_2_a`/`3_a` 行1 右侧的淡晕残留（'>' 已基本消除，剩均匀淡场）。

## 4. 待用户裁的

1. **sysgim_note 面的字体**：霞鹜文楷（现线）vs 思源黑体 Medium
   （`build/sysgim_note_zh__shs-med`，覆盖率更接近原文）。A/B 并排图
   用户已看过思源两版；采哪套 affects 整个面（六张重烤即可）。
2. 全局字体待裁项（bake-progress「等你裁的」）不变。

## 5. 下一批：`cutin/tut_*` 16 张

- 全工程剩余文本量最大、版面最复杂：段落正文压在游戏截图上。
- 入手：`bake_para_glow` 已有 Spec 机制，新增一份 Spec（照
  `bake_sysgim_note.py` 的样子）；量环/遮盖参数逐张实测后落数据。
- 先测绘（照 E 类的做法：逐张版面、晕半径、底色、行带），再定
  mask_mode（截图底大概率要 `photo` 拉普斯拉重建或 region=ink）。

## 6. 方法教训（本轮新增，接 29b 的 §5）

17. **盒的每条边都要对齐真墨迹**：盒缘切掉墨迹首/尾行 → 字号/左缘
    系统性偏移（sys_12_a 尾「ー」、行1 顶行两例）。
18. **白芯判据必须带无彩色约束**：彩色晕的亮像素 (150,255,150) 族会
    冒充白芯（min≥150 恰好过），把晕场卷进擦除区（12c 回归根因）。
19. **保留组盒优先于盒归属**：组件先查保留组盒，再查墨盒——顺序反了
    会把保留层的环当墨（E20b）。
20. **擦除填充的 alpha/颜色不要二值**：晕场上平填透明=透明带、平填
    底色=灰雾板、拉普拉斯大区域=向暗坍缩；字芯小region+拉普斯拉
    （晕场保留）或 fill_soft（修字芯+模糊）按版面选（E20f/E20h）。
21. **行级参数**（bg/r_old/line_ratio/fill_soft/core_ratio_hi）是
    多层版面的常态，geo 级只做缺省——同图异底的行各要各的值。
