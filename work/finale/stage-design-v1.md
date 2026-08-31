# 谢幕章演出设计 v1（基于 s8f/e2f 实地调研）

> 调研面：snr_s8_10_f.lua 全文、snr_e2_10_f.lua（e2f_290/300/310/340/350/complete + main）、
> snr_common.lua（oCard.show / comSectionNonLabelBegin / memoryFlag）、snr_mainmenu.lua（section7 直达）、
> snr_memory.lua（回想注册结构）、snr_graphic.lua（CG 鉴赏表）；
> 图片实看：bg_7_b_0、eve_50_x/51_a/73_a/73_b/74_x、sys_1_a/e/f、cut_e_s8、卡面尺寸 212×148。

## 0. 总原则

1. **零新绘**：全部演出用既有 bg/event/cutin/sysgim ＋ 新烤卡面（201–207，自有 bake_card 管线）；
   唯一改图件＝eve_74 中文封面变体（用户走 gpt）。
2. **零 common 改动**：谢幕新脚本 `snr_finale.lua` 内联自己的开场函数
   （savedataTitle(场景名,『谢幕』) + advPart/logEnable/setConfigButton——comSectionNonLabelBegin
   的前缀表不认识新章，与其改表不如不用它）。
3. **结构全仿 s8f**：局部 `scene_fin_XX(scene_id, scene_title)` + 尾部 `main()` doScriptScene
   状态机 + 完结 `cInitGame(); run(snr_mainmenu); quit()`。
4. **一切演出词汇取自原作已有用例**（下表逐场标注出处），不发明新原语。

## 1. 挂点（入口）

**方案 A（推荐）：e2f 完结后自动接。**
`snr_e2_10_f.lua` main() 的 `e2f-complete` 分支，在 `autoSystemSave(0)` 之后改为：
`cInitGame(); doScriptScene = "fin-10"; run(cGetFileName("script","snr_finale")); quit()`
（替换原 `doScriptScene = "end"` 落链）。
- 改动面：e2f 尾部 3 行，走分支＋游戏内验证（规约）。
- 回想模式重放 e2f 时 `memoryFlag` 拦截发生在 complete 场景**之前**（原样保留），
  故谢幕只在真实通关触发，重放不受影响。✅已核对拦截位置。
- 时间线也正确：e2f 是全书末章，谢幕接在"承蒙您拿起本书"之后＝合上书再翻出一页。

**重看途径（二期可选）**：回想模式注册。结构已摸清——`snr_memory.lua` 的
`memoryNumber` 表加格 + `v0.doScriptScene.snr_finale = "fin-10"` 映射 +
`systemSave.memoryFlag["snr_finale"] = true` 写入点 + 回想界面缩略图
（memory_thumb 管线已有）。中成本，首版不做。
**不推荐**：主菜单直达（仿 section7 需动菜单图与光标布局，高成本）。

## 2. 场景分解（场景 id：fin-10 … fin-60）

### fin-10『放学后的天台』——场景 1 前半（对话）
| 要素 | 取用 | 出处 |
|---|---|---|
| BG | `bg_7_b_0`（晚霞天台——"谁都没见过的晚霞"色） | e2f_350 三连之一 |
| 千秋登场 | `eve_50_x` 短显 → 回 BG | s8f_90 同图同用法 |
| 对望中景 | `eve_51_a`（可选，在"仪式"行前后） | s8f_90 |
| BGM | `bgm_19_x`（五年后日常暖曲） | s8f_90/160 |
| 环境 | `loop_6`（夏末环境音） | s8f_80/90 |
| 名条 | 可选烤 `cut_s_fin`（场景名条，仿 cut_s_s82 飘入） | s8f_80 |

### fin-20『怪谈：放学后的讲述者』——千秋说书（故事层文体）
- 画面语法照 **e2f_290 传话游戏段**：`cStopBGMWrap()` 后纯环境音，教室空景静置，无立绘。
- BG：`bg_4_b_0`（放学后教室·夕）→ 讲到"再也没有人来过"切 `bg_4_c_0`（夜）→
  "装订好的书"回 `bg_4_b_0`。（bg_4 即 e2f_290 用的教室系。）
- **演出点子（零成本）**："卡片一张、一张地翻动"一带，用 `oCard.showMiniIn/Out`
  把两三张**既有旧卡**（如 crd_1、crd_133）在 mini 位快闪掠过——怪谈里"看不清人，
  只见卡片自己翻动"的画面化；SE 用翻卡音。
- "混进写错的卡"段：`comEffectFadeOut(30)` 一个极短暗转再回，做"停下来"的呼吸。

### fin-30『七张卡』——翻卡位（第三次 Staff Roll 的实体）
- 回 `bg_7_b_0`。千秋掏卡对白后，七连翻卡：
  `cLoadPlaySE(se_30)` + `oCard.show(cGetFileName("card","crd_20N_a"), "<反应行>")`
  ——原生演出：卡面自左滑入停在 (130,40)，文本框显示反应行（玩家按键期间卡面常驻），
  按键后滑出。**msg id 自动＝18000+卡号＝18201–18207**（18200 已被 crd_200 用过，紧邻安全）。
- 多行反应（卡 204 两行、卡 205 三行）：**不发明变体**——oCard.show 的 p1 放第一行，
  卡片滑出后用普通 vms 补余行（v1 文稿的行序不变，只是"卡在场/卡离场"的分配）。
- 空白卡：**不用 oCard.show**（不产生 18208）。用 layer 手演：空白卡模板 png
  滑入停住（抄 show 的前半实现，18 行），两条对白（普通 vms），滑出。
- BGM：全程无曲只留 loop_6；第七张（『下一段』）滑出后 `cStopLoopSeWrap()` 全静，
  静场里出空白卡——听觉上的"最后一张是空白的"。

### fin-40『文化祭』——戏中戏（场景 2）
- 引入：天台 BG 上千秋念稿两行 → `comEffectWhiteIn(120)` 切 `eve_74_x`
  （whiteIn 进入"她写的场景"，学 e2f_340 进 eve_73_b 的语法）。
- 对白段 eve_74_x 常驻（≦≧ 匿名标签沿 e2f 体例）。
- **点破帧**：`layerLoad(layerName.event, eve_74 中文封面变体)` + `switchScreen(0,"",60)`
  ——同层交叉溶解（原作标准换图语法），落在"是谁都没见过的晚霞"与"会介意吗"两行之间。
- BGM：`bgm_20_c`（e2f_340"Happy End 拜托"用曲——戏中戏的情感位同源）。
- "想起我们就好——！"后 `comEffectFadeOut(120)`。

### fin-50『第三个 Staff Roll』——收束（场景 3）
- 回 `bg_7_b_0`。三个 Staff Roll 问答 →"没有名字/声音"段（静场，无叠图——
  标题 logo 叠放语法留给 e2f_350 专用，不重复）。
- "那张卡，给你了"：空白卡再次 mini 位短显（道具呼应）。
- **蜻蜓行配 `eve_73_b`（晚霞版）**：`comEffectWhiteIn` 短显。选 _b 不选 _a 的理由：
  ①谢幕场景是傍晚，色调连续；②73_b 在 e2f 是"故事的最后想写成 Happy End……
  可以拜托你吗"的画面——谢幕重逢它＝那个请求已被兑现。（73_a 蓝天版 s8f 已用，
  两版就此都各归其位。）
- BGM：`bgm_20_b`——s8f 里千秋按下 PLAY、『姐姐.mp3』响起时的曲（浜千鸟 arrange，
  待听曲最终确认）。"回家的歌谣"收全篇。
- 末行"承蒙您读到这里，非常感谢。"＝普通 vms；其后可选一张**谢幕寄语板**
  （仿 sys_1_f 纸色板，sysgim 管线烤，非必须）。
- 完结流：`cStopBGMWrap(); comEffectFadeOut(300); autoSystemSave(0)` →
  `cInitGame(); run(snr_mainmenu); quit()`。

### fin-60（预留）
- 若日后做回想注册，此 id 段留给"从回想进入"的分流（无内容）。

## 3. 已知取舍（首版明确不做）

1. **谢幕卡不入卡片图鉴**：`myCard`/`plotTitle`/`cardSort` 全库按 1..195 设计，
   扩表牵动 common 与图鉴 UI，风险大于收益。卡只活在谢幕演出里——
   "讲述者们留下的卡片"本来就不属于彩野的卡册，语义反而更对。
2. **CG 鉴赏注册 eve_74 变体**（`cgNumber[8][7][2]` 一行 + cgFlag 联动）：
   一行成本但需查 cgFlag 写入机制，列为落地时顺手项，非阻塞。
3. 主菜单直达、回想注册：二期。

## 4. 新增资源清单

| 件 | 来源 | 状态 |
|---|---|---|
| crd_201..207_a.png（七张卡面） | bake_card 管线 + cards-bake.yaml | **可立即烤** |
| 空白卡 png | png/card 既有空白模板 | 已有（落地时确认文件名） |
| eve_74 中文封面变体 | 用户走 gpt 改图 | 待改 |
| cut_s_fin（场景名条）/ 谢幕寄语板 | cutin/sysgim 管线 | 可选 |
| snr_finale.lua | 新写（结构仿 s8f，约 300–400 行） | 待写 |
| snr_e2_10_f.lua 尾部 3 行 | 分支改动 | 待改 |

## 5. 落地首测清单（游戏内验证项）

1. **新 vms id 的已读染色/存档兼容**：正文用 17300–17499（紧贴既有上限 17220，
   最小越界）；卡片 18201–18207。已读位图在 C 侧、容量未知——首测第一优先。
2. `run(cGetFileName("script","snr_finale"))` 的封包链路（新 lua 进 script 打包）。
3. bgm_20_b / bgm_20_c 听曲确认。
4. e2f 改动后：真实通关触发谢幕✓、回想重放 e2f 不触发✓（拦截位已核，仍需实测）。
5. oCard.show 对 18201+ 的 msg id 无副作用（its string.gsub 解析对三位数卡号的行为——
   `18000+"201"` 的 lua 弦转数含隐式 tonumber，逻辑上成立，实测一次）。
