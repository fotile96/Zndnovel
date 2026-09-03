# 谢幕章主菜单直达入口——机制测绘与改动方案 v1

> 任务：给 `snr_finale.lua`（入口场景 `fin-10`）加一个仿「セクション７」的主菜单直达项。
> 代码基座 = `/Users/fotile96/pyluadec-refactor/corpus/final/`（下文行号均指该基座，
> 2026-08-31 实测；迁移事项见 pyluadec-refactor `docs/runbooks/zndnovel-naming-migration.md`）。
> 本文将 stage-design-v1 §1 中「主菜单直达＝高成本、不推荐」的估计**收敛为实测成本**：
> lua 两文件约 8 处改动 + 新图 1 张，光标/按键代码零改动（机制是枚举驱动的，见 §1.3）。

> **勘误（2026-09-02 实施后）**：§2.2 的"层 198 常驻"方案已证伪——`cInitGame→cInitLayer`
> 会清掉 200 以下的层（§7 所谓"86–199 全库无人使用"实为"无人能用"）。落地定案：
> title_14_a 在 `l0_4` 卡 144 分支里**绘制期同步 layerLoad 直载工作层**，snr_common
> 零改动，§6.8 的常驻层记账作废。小注按 2026-09-01 裁定 E22 整体不烤（§5 的小注段
> 作废）。其余按本方案逐字落地并模拟器验证，见 docs/ops/finale-stage-impl-2026-09-02.md。
>
> **追记（2026-09-02 管线规范化）**：本节 §2.1/2.2 描述的 8 处手工改动，实现已成
> `layers/overlays/encore-menu.toml`（叠加层，锚点=代码文本，施加于装配期而非手改
> `lua_scripts/`）；`snr_finale.lua` 的 canonical 源同期迁至 `layers/scripts/snr_finale.lua`。
> 命令面现行说明见 `docs/ops/disc-pipeline.md`。

## 0. 结论速览

- **可行**。菜单项/光标/分发全部由「枚举表 `l0_1`（名→序号）+ 图键表 `layerKey*`（序号→图）」
  驱动，加一项＝加表项 + 一个坐标分支 + 一个 CIRCLE 分支；UP/DOWN/CROSS/子菜单逻辑不用碰。
- **门控 = `gameSave.myCard[144].hold == 1`**，与 section7 的卡 140 门控完全同构，足够且无误触（§4）。
- **新图 1 张**：`sysgim/title_14_a`（双态叠放，约 100×68）。大词推荐 **`encore`**（全小写）——
  六个字形全部能从既有 title 图等大拼接，零字体匹配风险；小注 `- 谢幕 -` 走现行
  `bake_sysgim_title` 管线（§5）。
- **最大风险**：主列从 5 项挤到 6 项的版面（§6.1，已按 27px 间距做过合成 mock，属可行区间，
  但最终坐标须游戏内目测微调）；以及新 .gim/新 .lua 的封包链路（与 stage-design 首测清单共担）。

## 1. 主菜单机制实况（snr_mainmenu.lua）

### 1.1 四种形态与数据结构（L1、L89–216）

配置全部在 L1 的 `l0_0`：

| 键 | 内容 |
|---|---|
| `layerNumber` | `{bg=0, logo=1, menu=2}`——菜单项画在工作层 `menu+序号`＝3..13 |
| `layerKey0..3` | 四形态的图键表（序号→`title_XX_a`），**顺序即枚举序号** |
| `layerWidth/layerHeight` | 每张图的宽高表（供裁半用；⚠ title_06 记 59 实图 60、title_13 记 67 实图 68，原作笔误，裁半出 .5 无碍） |

四形态（绘制函数 `l0_4`，L78–216；每分支先设枚举 `l0_1` 再循环摆图）：

| 形态 | 条件 | 枚举 `l0_1` | 图键表 |
|---|---|---|---|
| 0 新开局 | `startMenuState==0`（L89） | prologue,library,option,load,novel,scene,cg,music | layerKey0（8 项） |
| 1 序章毕 | `==1`（L116） | story,library,option,save,load,novel…music | layerKey1（9 项） |
| 2 全菜单 | `==2` 且卡140 未持（L145,147） | story,fragment,library,option,save,load,novel…music | layerKey2（10 项） |
| 2+ 直达 | `==2` 且 `myCard[140].hold==1`（L177–210） | story,fragment,**section7**,library,option,save,load,novel…music | layerKey3（11 项） |

图↔项对照（全部 png/sysgim/）：title_02=Prologue、03=Story、04=Fragment、**13=Section 7**、
05=library、06=option、07=save、08=load、09=novel、10=scene(回想)、11=cg、12=music。
另 `systemSave.libFlag/novelFlag/musicFlag` 控 library 及子项可见性（L2–10、L212–214）；
形态 2 强制 `libFlag=true`（L2–4），故形态 2 的光标代码没有 library 跳过逻辑——新分支同样不需要。

### 1.2 菜单项怎么画：单图双态 + 裁半

每张 `title_XX_a` 上下叠两个状态：**上半＝暗态**（淡紫英文大词），**下半＝亮态**（饱和蓝
发光大词 + 青色小注，如 title_13 下半的『- セクション7 -』）。绘制：

- 常驻层：snr_common L717 `layerName.title_01..13_a = 212..224`，开机 `main()` L4010–4022
  `comLayerLoadFalse` 全部预载（隐藏常驻，跨 `run()` 存活）。
- `l0_4` 里 `layerCopy(menu+i, layerName[layerKey[i]])` 拷到工作层，再裁半：
  `l0_2`（L69）＝裁上半（暗态），`l0_3`（L73）＝裁下半（亮态），裁参取自 layerWidth/Height 表。
  裁剪在原位渲染（选中态不位移——游戏实况可证）。初始高亮第 1 项（L209）。
- 形态 2+140 的主列坐标（L182–191）：story(210,110)、fragment(190,145)、section7(194,180)、
  library(205,208)、option(215,241)；side：save(48,145)、load(330,142)；子列 novel(353,185)、
  scene(335,207)、cg(340,223)、music(352,243)。⚠ 对比无 140 形态（story 120/fragment 160），
  **section7 出现时原作自己就把主列上移压缩**（35px 间距）——挤入第 6 项是同一手法的延续。

### 1.3 光标与分发：枚举驱动，无硬编码项名遍历

主循环（`main`，L249；形态 2+140 的循环 L780–955）。状态变量：`l1_0` 当前项、`l1_1` 前一项、
`l1_3` 是否已展开 library 子列。主列（`l1_3==false`）：

- UP：`l1_0 > option`（即在 save/load 上）→ 跳 story；否则 `max(story, l1_0-1)`（L782–792）。
- DOWN：在 save/load 上 → 跳 fragment；否则 `min(option, l1_0+1)`（L793–803）。
- LEFT → save、RIGHT → load（L804–817）。
- CIRCLE（L818–869）：按 `l1_0 == l0_1.<项>` 分发。**section7 完整链路（L832–837）**：
  `cInitGame(); switchScreen(0,"",60); doScriptScene = "s7f-10"; run(cGetFileName("script","snr_s7_10_f")); quit()`。
  library 分支展开子列（L838–858，**⚠ 此处循环上界硬编码 `for l1_7 = 1, 11`，L845**——
  其他形态都用 `#layerKey*`，唯独这里写死，加项必改）。
- 子列（`l1_3==true`）：UP/DOWN 在 `l0_1.novel..l0_1.music` 间钳位（L871–896），CIRCLE 进
  各画廊脚本，CROSS 收合回 library（L924–944）。循环尾统一重画亮暗态（L946–952）。

**关键性质**：UP/DOWN 钳位、子列边界、隐藏阈值（`if l0_1.novel <= i then layerVisible(false)`）
全部引用枚举字段而非常数。**只要新项插在 section7 与 library 之间、保持
「story..option 连续、save/load 随后、novel..music 收尾」的序号次序，光标代码一行不用改**；
分发链里 `l1_0 == l0_1.finale` 在 finale 不存在（nil）时恒 false，共享循环天然安全。

### 1.4 启动链与存档可见性

snr_common `main()` L4097–4109：开机 `runAutoLoad()` 恢复 gameSave/systemSave → 进 snr_mainmenu
（debagFlag 时先 snr_lib）。即标题画面看到的 myCard 是**自动存档**的：e2f 完结授卡后紧跟
`autoSystemSave(0)`（→`runAutoSave`，snr_common L2997），卡 144 即时落盘，重启即见菜单项。

## 2. 改动清单（逐文件逐处）

### 2.1 `snr_mainmenu.lua`（6 处）

1. **L1 `l0_0` 表**：追加
   `layerKey4 = {"title_03_a","title_04_a","title_13_a","title_14_a","title_05_a","title_06_a","title_07_a","title_08_a","title_09_a","title_10_a","title_11_a","title_12_a"}`；
   `layerWidth.title_14_a = <实宽>`、`layerHeight.title_14_a = <实高，取偶数>`（按成图填，见 §5）。
2. **`l0_4` 的卡 140-else 分支（L177–210）**：嵌套卡 144 判定。
   - 先设 `l0_0.layerKeyCur = l0_0.layerKey3`（既有 11 项布局块原样保留）；
   - `if gameSave.myCard[144].hold == 1 then` 改用
     `l0_1 = {story=1, fragment=2, section7=3, finale=4, library=5, option=6, save=7, load=8, novel=9, scene=10, cg=11, music=12}`、
     `l0_0.layerKeyCur = l0_0.layerKey4`，并复制一份摆图循环（12 项坐标见下表）。
     照原作「每形态整块复制」的风格做块级复制即可；嫌重可换成坐标查表 + 单循环（口味题）。
   - L209 初始高亮的 `layerKey3[1]` → `layerKeyCur[1]`。

   12 项布局建议（27px 间距，按 480×272 合成 mock 验证过挤而不叠；±2px 留给游戏内目测）：

   | 项 | 坐标 | 说明 |
   |---|---|---|
   | story | (210,104) | 原 110，上移 6（logo 底缘 y≈99，仍留 5px） |
   | fragment | (190,131) | 原 145 |
   | section7 | (194,158) | 原 180 |
   | **finale** | (252−宽/2, 185) | 主列墨迹中轴 x≈252 |
   | library | (205,212) | 原 208，下移 4，给 finale 亮态小注让位 |
   | option | (215,241) | 不动（下缘已贴屏底） |
   | save/load/novel/scene/cg/music | 原坐标 | 不动 |

3. **CIRCLE 分发（L837 后插入）**：
   ```lua
   elseif l1_0 == l0_1.finale then
       cInitGame()
       switchScreen(0, "", 60)
       doScriptScene = "fin-10"
       run(cGetFileName("script", "snr_finale"))
       quit()
   ```
   （`cGetFileName("script","snr_finale")` → `script/snr_finale.lua`，纯字符串拼接，无注册表。）
4. **L845 硬编码上界**：`for l1_7 = 1, 11, 1` → `for l1_7 = 1, #l0_0.layerKeyCur, 1`。
5. **共享循环里 6 处 `l0_0.layerKey3` → `l0_0.layerKeyCur`**：L866–867、L941–942、L947–948。
6. （审校项，非改动）确认卡 140-false 分支（L147–176、L609–778）未触碰。

### 2.2 `snr_common.lua`（2 处）

7. **L717 `layerName`**：加 `title_14_a = 198`。层号空间实测：201–203 已用（ADV 窗/光标/auto
   图标）、204–255 全满、backLayerName 占 261–299、**100 与 199 被 story/fragment_main 临时
   layerCopy 抢用**；86–99 与 101–198 全库无人使用，取 198（紧邻既有常驻区，好记）。
8. **L4022 后**：加 `comLayerLoadFalse(layerName.title_14_a, cGetFileName("sysgim", "title_14_a"))`。
   ⚠ 此文件另有待重放的中文字体补丁（迁移指南 §4），两笔改动同文件，合并时对齐。

### 2.3 `snr_finale.lua`（对新脚本的两条约束，非本案改动）

- `main()` 状态机接受 `doScriptScene == "fin-10"` 入口（stage-design §2 已如此设计）。
- **绝不调用 `comSectionStoryEnd` / 不写 `gameSave.storyRoute`**：`comSectionUID2ScriptFileName`
  （snr_common L1984）按「前 2 字符=章」解析，`"fin-10"` 会解成不存在的 `snr_fi_10_n`。
  全库唯一调用点是 snr_story_main L454，仅作用于 storyRoute 元素——f 章全员（s7f/s8f/e2f
  实测 0 次 storyEnd/savedataTitle/functionButton 调用）不进路线，照抄 s8f 结构即天然安全。

## 3. 与既有入链方案的关系

stage-design §1 方案 A（e2f 完结后自动接谢幕）与本入口**互补共存**：自动接＝首次观看，
菜单项＝此后任意重看（语义同 section7：菜单进入即整章重放，完结重授卡幂等，最后
`run(snr_mainmenu)` 回标题，s7f L 尾部同款）。若只做菜单入口不做自动接，玩家通关 e2f 回
标题后见新项出现，亦成立。二者共享同一门控卡。

## 4. 门控结论：`gameSave.myCard[144].hold == 1`，足够且无误触

证据链（全库 grep 实测）：

1. **唯一授予点** `snr_e2_10_f.lua` L1948–1950（`e2f-complete` 分支）：162/144/114 三卡同点授予，
   紧跟 `autoSystemSave(0)` 即时落盘——比 section7 门控卡 140 的授予（s6f L524，不带即时存）更稳。
2. **回想重放不授卡**：`e2f-complete` 分支开头 `if memoryFlag == true then run(snr_memory)` 先于
   授卡（L1943–1946），重看 e2f 不会点亮菜单项。
3. **fragment 侧无旁路**：`snr_crd_144.lua` 是 4 行关键词卡 stub，`comSectionCardEnd` 只做清屏
   不写 hold；`sceneId2aCard.keyword = 144` 是反编译噪声键（CLAUDE.md 已裁定），无真实场景映射。
4. **蕴含关系**：144 ⟸ e2f ⟸ 卡143 ⟸ e1 ⟸ 卡142 ⟸ s8f ⟸ 卡141 ⟸ s7f ⟸ 卡140——正常流程中
   144 必伴随 140，新项嵌在卡 140-else 分支内不会失联；万一异常存档 144∧¬140，项只是不显示（fail-safe）。
5. **调试友好**：snr_lib 的 SEC7F 项一键 `myCard[1..195].hold=1` + `startMenuState=2`（L60–76），
   谢幕项随之可测，无需改 snr_lib（可选加直达）。

**备选 flag 评估**：`systemSave.memoryFlag.snr_e2_10_f`（mainmenu L66–68 由卡 144 派生）是
系统存档级、一旦置位跨周目黏着——门控会在新开局的另一份 gameSave 上"漏亮"，且语义是
"回想解锁"不是"本存档已通关"，**弃**。`startMenuState` 加第 3 值改动面与存档语义太大，**弃**。
不必 `144∧162∧114` 三卡合验：同点授予，无信息增量。**三卡中取 144**（章节梗概卡，语义
=「e2f 的『あらすじ』已入手」）最贴题。

## 5. 新图 `title_14_a`：规格与制作面

**规格**（对照 title_13_a 实测）：双态上下叠放；参考 117×68、上半暗态词芯 h21、下半亮态
词芯 h21 + 青色小注芯 h10（title_13 下半：词 y[35,55]、注 y[56,65] x[47,114]）。新图建议
**宽 ≈100、高 68（偶数，裁半无 .5）**，状态分界线 y=34；layerWidth/Height 表按实图填。

**大词文案（版面依据的建议）**：主列第二字号组（section7/library/option，词芯 21px）里，
小写字形库＝`Section 7`+`library`+`option` 的并集。候选：

- **推荐 `encore`**：e,n,c,o,r,e 六字形**全部**在 21px 库内（e/c/o/n←Section 7，r←library），
  两态皆可等大剪贴拼接，零新字体渲染、零风格断裂；全小写与 library/option 体例一致；
  语义（终演后的返场）与"第三次 Staff Roll 的谢幕演出"贴合。
- 备选 `Finale`：语义最直白，但全库 21px 字形无 F/f（仅 Fragment 有 27px 大写 F），须缩放或
  按字体新渲，有匹配风险；`Staff Roll` 同样缺 f。若用户愿走字体重渲路线再议。
- 不建议中文大词：全局体例是「英文大词 + 中文小注」（CLAUDE.md、data/sysgim_title_text.jsonl 12 行全如此）。

**小注**：`- 谢幕 -`（与 `- 序章 -` 同长度级；section7 的既定译法是 `- 章节 7 -`，谢幕非章节，
不套「章节」格式）。

**制作管线**（tools/ 实测能力）：`bake_sysgim_title.py` 是 `bake_para_glow` 的 Spec 消费者，
能力＝**遮旧注、按收敛发光模型渲新注**（`mask_mode="glow_footprint"`、`core_anchor`），
**不能无中生有整张菜单图**。顺产路线两步：

1. **底图拼接**（一次性小脚本或手工）：从 title_13/05/06 两个半区各剪 `encore` 六字形
   等大拼出上下两态；下半再原样移植 title_13 的小注条（`- セクション7 -`，x[47,115) y[56,65]）
   作**捐赠注**占位。产物＝`title_14_a` 日文态源图（存 docs/finale/ 或 assets/，勿入只读的 png/sysgim）。
2. **烤注**：`data/sysgim_title_text.jsonl` 加一行
   `{"file":"title_14_a","row":0,"box":[<捐赠注实测盒>],"jp":"- セクション7 -","zh":"- 谢幕 -"}`
   （jp 必须转写捐赠注墨迹，管线有行数互校），Spec 的 src 指向新源图目录跑一遍——遮盖、
   发光收敛、字号锚定各闸全部复用。产物落 `build/sysgim_title_zh/title_14_a.png`。

**出图后**：PNG→GIM 回转（工具不在仓库）+ 封包为 `sysgim/title_14_a.gim`——与谢幕章
`script/snr_finale.lua`、七张卡面同属"新增文件进包"链路（stage-design 首测清单第 2 项扩围）。

## 6. 风险清单

1. **版面挤压（最大）**：主列 6 项 27px 间距，亮态小注与下一项词顶的重叠量 ≈6px，与原作
   section7→library 的既有重叠（5.5px）同级；story 与 logo 间隙从 11px 缩到 5px。合成 mock
   判断可行，但**必须游戏内目测定稿**，坐标全部集中在 §2.1-2 一处，调参零风险。
2. **L845 硬编码 11**：唯一的非枚举驱动点，漏改则 library 展开时第 12 项（music）不参与
   渐隐/显隐。已列入改动清单第 4 条。
3. **存档兼容：零风险**。myCard[1..195] 表结构未动、无新 gameSave/systemSave 字段；旧档
   （已持 144 者）加载即见新项；改版存档回原版游戏亦可读（原版菜单只是不认识卡 144 的含义）。
4. **四形态表现**：形态 0/1/2-无140 三路代码零触碰、行为逐字节不变；形态 2+140-无144 走
   `layerKeyCur=layerKey3`，与今日行为一致（分发链的 finale 比较恒 false）；仅 2+140+144 走新布局。
5. **与 section7 共存布局**：见 §2.1 表——section7 项保留原图原序，仅 y 上移 22px；两直达项
   相邻（158/185），语义上"重演坠楼日"与"谢幕"相邻亦通顺。
6. **裁半渲染假设**：`layerClip` 裁下半后在原位显示——由原作四形态高亮行为反证成立，但新图
   首测时仍以肉眼确认两态同位（若引擎按裁剪偏移绘制，原作高亮早就跳位了）。
7. **`"fin-10"` 命名**：不符合 `comSectionUID2ScriptFileName` 的「章+模式」解析约定，安全的
   前提是谢幕章永不进 storyRoute（§2.3）。若未来想要回想注册等更深集成，届时评估改用
   合规 id（如 `s9f-10`/文件 `snr_s9_10_f`）的成本。
8. **常驻层 198**：全库唯一失察面是未来新脚本再抢 101–199 段临时层；在 CLAUDE.md 或迁移
   台账记一笔「198 已被 title_14_a 常驻占用」即可。
9. **封包链路**：新 .gim/.lua 进包未实测（云端/本地均无工具），与 stage-design 首测清单
   共同验证；PSP 内存增量（1 张 ~100×68 调色板 gim 常驻）可忽略。

## 7. 方案分级

**最小可行版**（一次分支落地）：§2.1 六处 + §2.2 两处 + `title_14_a` 一张（encore 拼接 +
捐赠注烤字）。谢幕项仅在「形态 2 ∧ 卡140 ∧ 卡144」出现，其余形态零变化。改 lua_scripts/
原件属强制开分支项（CLAUDE.md 规约），游戏内验证 §6.1/6.6 后合并。

**完整版**（最小版之上，各自独立可选）：
- `bake_sysgim_title.py` 正式收编 title_14 数据行与源图目录（而非一次性旁路脚本），
  换字体评估时 13 张同管线再烤；
- snr_lib DEBUG 加谢幕直达（省去每次全卡跳板）；
- 可选 `cut_s_fin` 场景名条与谢幕寄语板（stage-design §2/§4 已列）；
- 回想模式注册（memoryNumber 表 + memoryFlag.snr_finale + 缩略图）——届时重新评估
  §6.7 的场景 id 命名。

—— 完 ——
