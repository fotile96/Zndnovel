# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目目标

对 PSP 视觉小说《セカンドノベル 〜彼女の夏、15分の記憶〜》（2010，日本一ソフトウェア）做**中文本地化**。本仓库包含反编译后的全部游戏流程脚本（`lua_scripts/`，229 个 lua）与图片资源（`png/`，约 2100 张，由原 .gim 转换而来）。

最终要开发的工具链：借助 1M 级长上下文 LLM（gemini、deepseek 等）翻译游戏文本。核心思路——**正确重建游戏剧情 DAG，对任意待翻译文本单元，把"从新游戏开局游玩到该位置"沿途出现的全部文本按出现顺序拼成长 prompt**（或对前缀做适当 compact），让 LLM 掌握人物关系与故事进程后再翻译。注意：本作游戏机制本身就是"给 15 分钟记忆的人讲故事 + 用『あらすじ』（梗概）压缩已讲内容"，与工具的 context/compact 思路同构，很多设计可以直接借鉴游戏内规则。

当前仓库尚无构建/测试体系（纯数据 + 未来工具代码）。git 仅一个初始 commit。

## 仓库文件构成

```
lua_scripts/                    229 个文件，共 3.6MB
  config.lua                    引导配置：bootScript = snr_common.lua
  snr_lib.lua                   调试启动菜单（SEC7F/PROLOGUE/STORY/DEBUG）
  snr_common.lua                5113 行核心库：全局状态、195 卡片表、UI 对象、引擎封装
  snr_mainmenu.lua              标题菜单（5 种形态，随进度解锁；第 5 形态=卡 144 后的谢幕直达）
  snr_story_main.lua            Story 模式中枢（记忆路线时间轴 UI）
  snr_fragment_main.lua         Fragment 模式中枢（同一时间轴，选场景做卡）
  snr_memory.lua                回想模式（重放各章 _f 剧本）
  snr_novel.lua / snr_music.lua / snr_graphic.lua   文库/音乐/CG 画廊（纯图片 UI，无剧情文本）
  snr_s{0..8}_10_{s,f,fa,fb,fc}.lua、snr_e{1,2}_10_{s,f}.lua   章节剧本，共 23 个（见下）
  snr_crd_{0..195}.lua          196 个卡片（fragment 谜题）剧本
png/
  bg/81 card/197 cutin/73 effect/65 event/121 graphic/18 music/4
  novel/993 plot/4 pose/212 scene/4 select/278 sysgim/103
tools/                          分析提取脚本（可复跑，路径相对仓库）
  extract_dag.py                章节调度器 → 场景 DAG 文本
  extract_text.py               lua → 纯剧情文本摘要（vms 行）
  extract_crd.py                卡片谜题结构一览
  databin.py                    DATA.BIN 资源包 list/unpack/pack/verify（pack 容器 + nislzs 解压；
                                回封一律 raw 存储、严格保持原封包成员顺序、幂等，格式详见其 docstring）
  gimcodec.py                   GIM 纹理编解码 decode/encode/verify-pngdir/verify-identity（index4/8+RGBA8888、
                                swizzle、多帧、大端老版全支持；编码走模板回填=只换像素与色板 payload，
                                未改图逐字节还原；已对全部 2153 张与 png/ 双向全量验证）
  at3p.py                       ATRAC3+ 曲目 encode/inspect/verify（本作 SOUND.BIN 同款 RIFF 头、必带 smpl；
                                编码器 build_atracdenc.sh + atracdenc-744.patch；原 99 成员名单 data/sound_members.json）
  umdiso.py                     UMD ISO list/extract/replace/verify——**就地替换不重建**（通用刻录工具
                                会 Joliet 改名/重排 LBA，造成模拟器好好的、实机黑屏）；恒等替换逐字节还原，
                                变尺寸时平移尾部并更新 PVD/path table/目录记录三类扇区号引用
analysis/                       上述脚本的产物归档（lua 变动后重跑，详见其 README.md）
  dag_all.txt                   全 23 章调度器场景图快照（DAG 权威参照）
  crd_summary.txt               196 个卡片谜题：前置卡/答案卡/触发章节/提示语
  text_digest/*.txt             228 份纯文本摘要（17995 行，覆盖全部 16749 条 vms）
skeleton/                       翻译骨架（git tag skeleton-v1 冻结）：cards.jp/（197 卡转写）+ cards.zh/（196 卡中文定稿）
                                + 合并版 cards.{jp,zh}.yaml + anchors.yaml（120 条伏笔锚点定译）
glossary/                       术语层：glossary.v1..vN.yaml（append-only，最高版为现行）+ active.json + speakers.json
                                + style.md（风格与润色尺度）+ voices/ 7 份角色口调表
layers/                         本地化改动层（基座只读，一切改动落在这里）：manifest.toml（清单：
                                基座/账本/车道/编译器路径、overlays 施加顺序、编外脚本、gim 面映射、
                                字体成员、[sound] 新曲）+ vms_ids.toml（id 区段登记）+ overlays/*.toml（叠加操作，
                                锚点=代码文本）+ scripts/*.lua（编外新增整篇脚本，如 snr_finale.lua）
                                + audio/*.at3（新曲编码定稿，进 SOUND.BIN；源 PCM 在 assets/audio/ 不入库）
guide/                          面向玩家的中文攻略（Typst）：chapters/ 手写正文 + generated/（由 tools/build_guide.py
                                从 cards.zh / dag.json / 选项烤字定译生成：定译字典、附录表、选卡界面格位 swatch）
                                + dist/second-novel-guide-zh.pdf 成品。卡名/选项名经模板断言必须命中定译；
                                每个 story-box 带 from/pick 机读路线，tools/guide_route_check.py 按引擎规则
                                （时间轴截断/沙漏/做卡前缀）重放全书，走不通拒绝出盘（2026-09-19 玩家反馈 5 处后加）。
                                ⚠ 攻略里不提 encore/谢幕章（用户裁定，留作惊喜）。runbook：docs/ops/guide-runbook.md
pyproject.toml + uv.lock                      uv 项目定义（Python ≥3.12，不钉精确版；deps: pillow/pyyaml）
```

**翻译骨架已冻结**（`git tag skeleton-v1`，2026-07-30）：正文翻译轨的定译基准 = `skeleton/anchors.yaml`（锚点句一律逐字沿用其 zh）+ `skeleton/cards.zh/`（卡面梗概定稿，亦是前缀 compact 的『あらすじ』语料）；术语取 `glossary/` 最高版本号与 `active.json`，风格与润色尺度见 `glossary/style.md`。骨架文件此后视同只读，改动须走新 glossary 版本 + 召回令。

这些 lua 是反编译产物。**2026-08-31 已换基座**：来源从旧 pyluadec 产物改为 `~/pyluadec-refactor/corpus/final/`（`tools/migrate_base.py` 执行，迁移依据与验收见 `docs/ops/decompiler-base-migration-2026-08-31.md`）。新基座**每个文件重编译后与游戏原始字节码逐字节相同**（229/229，仅 `linedefined/lastlinedefined` 行号字段不同——`tools/luac_norm.py` 归零后比对可复验）；旧基座 0/229。

**`lua_scripts/` 是只读纯净基座，与原始字节码逐字节等价**（`luac_norm` 229/229，由
`tests/test_base_fidelity.py` 钉住）；**一切本地化改动是 `layers/` 下的层，绝不直接改基座**。
层如何装配、四类改动各自的落点与命令、加一个新层的完整走查，见 `docs/ops/disc-pipeline.md`。

当前形态与约定：（1）局部名是 `l<depth>_<reg>` 型（如 `l1_2`），**不再是 v0/p0**；顶层函数名（`scene_*`、`card_*`）与旧基座逐名相同，是跨基座唯一稳定锚；（2）`snr_common.lua` 里两个字体槽在基座上仍是原版 `pgf/tsukuminpro_e_{17,09}.pgf`（基座纯净，不含字体补丁）——两槽的中文化都不在源里，由 `layers/overlays/fonts.toml` 这一个层统一改写为 `pgf/LXGWWenKai-Regular{,-09}.pgf`（`tools/inject_lua.py` 现在只做纯译文注入，不碰字体行）；（3）164 个文件带 `-- tr_line:N` 注释，标记"嵌在结构调用里的可译文本"（场景标题、`oCard.show` 提示语等），由 `migrate_base.py` 的 `add_tr_line_markers()` 机械重生成，规则已对旧基座验证 678/678 复现。**修改脚本时保持这些约定**；`vms()` 的消息编号绝对不要改动（见下）。

⚠ **行号不是稳定锚**：`data/ledger*.jsonl` 的 `line` 字段与 extra 轨的 `文件:行号` 键都随基座变化，换基座必须整体重生成并重挂译文（迁移脚本已代劳；重挂靠 `(file, kind, jp)→zh` 唯一映射，实测 791 组 0 冲突）。

## 引擎与脚本体系（PSP）

- 启动链：`config.lua` → `snr_common.lua` 的 `main()`（加载常驻图层/SE/双字体，播放 IPL 标志）→ `snr_mainmenu`。脚本间用 `run(cGetFileName("script", name)); quit()` 整体切换，每个脚本的入口都是 `main()`。
- 资源寻径 `cGetFileName(type, name)`：bg/card/cutin/effect/event/plot/pose/scene/select/sysgim → `.gim` 图；bgm/loop/mus → `.at3`；se → `.vag`；script → `.lua`。语音 `playVoice("voice/<ID>.at3")`。OP 动画 `playMovie("movie/op.mp4")`。
- 引擎原语（C 侧）：`msg(id, text)`、`fontPrint`、`layerLoad/Copy/Clip/Position/Move*/Alpha/Blend/Anime`、`switchScreen`、`pressButton("UP/DOWN/LEFT/RIGHT/CIRCLE/CROSS/TRIANGLE/SQUARE/L/R")`、`playBGM/SE/Voice`、`savedataTitle(标题, 章节名)`、`runListSave/Load`（手动存档）、`runAutoSave/Load`（系统数据）、`advPart`（ADV 窗口开关）、`logEnable`（backlog）、`functionButton("SQUARE", ...)`（呼出暂停菜单）。
- 全局状态：
  - `gameSave.storyRoute[1..99]`：{sceneId, ayanoTime 累计值}——**记忆路线**，Story 模式讲过的场景序列（本体存档核心）。
  - `gameSave.myCard[1..195].hold`：卡片持有（-1 未持有 / 1 持有）。
  - `gameSave.ayanoTime`：0–100 沙漏；`gameSave.sceneId/sceneName/sectionName`；`fragmentDoSceneId/fragmentDoCardId`（本次做卡目标）；`tutorial.*`；`startMenuState`（0 新开局→1 序章毕→2 全菜单）。
  - `systemSave`：消息速度/已读染色/音量/各角色语音开关（Naoya/Ayano/Yuichi/Yukari/Chiaki/Sakura/Other）/`cgFlag`（event 图即 CG 收集）/`memoryFlag`（回想解锁）/`novelGetFlag`/`bookMark`/`storyLineSkip`。

### 文本调用与标记（翻译工具的解析对象）

对白/旁白统一走 `vms(消息ID, 语音ID, "文本")`（snr_common 定义：播语音 + `msg`）。**消息 ID 全局唯一**（1..17220，共 16749 个静态调用；另有 `oCard.show` 动态用 18000+卡号），用于已读标记，是翻译数据库的天然主键。语音 ID 为 `"NAO05930"` 这类（无语音 = `NONVOICE`，有语音不进 backlog = `NORECORD`）。

文本内标记（必须原样保留/正确迁移）：
- `【名字】「…」` 说话人前缀；旁白无前缀；`○` 开头 = 场景说明式旁白（幕间描述）；`■` = 系统通知（【■おしらせ】等）。
- `_n` 换行、`_r` 另一种断行（两者混用，语义按引擎处理，勿删）。
- `<漢字,かな>` = ruby 注音，如 `<前向性健忘,ぜんこうせいけんぼう>`。**渲染实况（用户补充的引擎事实）**：半角尖括号内以一个半角逗号断开，native stub 解释后在文本框内以正常字号显示前半段，并在其**正上方**（占用与上一行文字之间的 padding）以小字号渲染后半段。全库 38 处，其中 8 处的前半段是**全角拉丁**（`<Ｔｒｕｅ Ｃｏｌｏｒ,トゥルー カラー>`、`<ＳｈｅｅｐＭａｎ,シープ・マン>`、`<Ｓｔｏｒｙ,ストーリー>` 等）。
  - **中文化可借该机制做汉语拼音注音**（给生僻字加注，比打括号精巧）：写成 `<汉字,pīn yīn>` 形式。
  - ⚠ **两个前提尚未实测，落地前须游戏内验证**：①ruby 那一层用的是哪个字体——`main()` 里 `fontLoad(0,"pgf/LXGWWenKai-Regular.pgf")` 是中文字体、`fontLoad(1,"pgf/tsukuminpro_e_09.pgf")` 是日文小字号字体，而 ruby 是小字号渲染，字体归属在 C 侧 stub 内、**本仓库看不到**；②该字体是否含带声调的拉丁元音（`ā á ǎ à`）。`pgf/` 与 stub 均不在本仓库。**2026-09-04 静态逆向已答**：①ruby 走字体槽 1（`fontLoad(1,…)`），正文走槽 0，槽 1 除 ruby 外无人用；②声调元音 30 个已由 `build_font.ALWAYS` 进字集、`tools/pgf_inspect.py` 可核（1:1 像素辨识度仍待实机目检）。ruby 语法/落点公式/负坐标裁剪/字体头 ascender 影响见 `docs/ops/eboot-kinsoku-research-2026-09-04.md` §6。
  - ✅ **已确认不受 `cHan2Zen` 影响**：该函数只被 `cfontPrint` 调用（UI 层），正文对白走 `vms()`→`msg()` 的 C 侧原语，**不经过全角强制转换**——故正文里的半角拼音不会被转成全角。
- `≪…≫`、`≦…≧` 强调/特殊语气括号；e2s 中 `【≦教師≧】` 这类说话人名也带 ≦≧。
- `cHan2Zen()` 会把半角英数强制转全角后再 `fontPrint`——UI 层文字（卡片标题等）按全角渲染；中文化时注意此函数与字库覆盖。

语音 ID 前缀 ↔ 角色：NAO=直哉、AYA=彩野/アヤノ、YUI=ユウイチ、YUK=由加里/ユカリ、CHI=千秋/（附身时说サクラ台词）、SAK=サクラ/雪乃、HAH=彩野母、MAS=酒吧マスター、OYA=大叔系男配（现任教师/雪乃生父等）、MOA=女配（护士/监视员等）。

## 游戏系统（两种模式 + 卡片经济）

**框架设定**：主角直哉在教室里听彩野讲『物語』。彩野的专注/记忆只能维持约 15 分钟 = `ayanoTime` 0→100 沙漏。每讲完一个场景 `comSectionStoryEnd(sceneId, sceneName, cost)`：把场景追加进 `storyRoute` 并加 cost（普通场景 20–25，重要场景 100，部分 0）。**若该场景的卡片已持有则 cost 不再计入**（`comSectionStoryChkAyanoTime` 只在未持卡时加时）。满 100 = Time over，彩野忘记一切，必须去 Fragment 模式做『あらすじ』卡。

**Story 模式**（snr_story_main）：把 `storyRoute` 显示为横向缩略图时间轴（L/R 跳到最近的未持卡场景）。选中某点 → `ayanoTime` 回滚到该点、`cClearNumStoryRoute` 截断其后路线、`doScriptScene=场景ID` 进对应章节脚本重讲。持卡场景进入时 `comDlgStorylineSkip` 询问跳过（跳过即 0 耗时拿到结尾的关键词卡）。

**Fragment 模式**（snr_fragment_main）：同一时间轴上选场景 → 运行 `snr_crd_<卡号>.lua`（卡号 = `sceneId2aCard[sceneId]`）。**顺序约束**：普通场景做卡前，其路线前缀上所有非 `_sel` 场景必须已持卡（`oCard.mesNotStoryLine`：「あらすじは物語の先頭から順番に作成する必要があります」）；`_sel` 选择卡不受此限。做卡成功后 `comAyanoTimeRefresh` 从路线中扣除该场景耗时，并提示「彩野に対して『あらすじ』で物語を説明できるようになりました」。

**卡片谜题**（crd 脚本套路）：`comSectionCardStart` → 前置卡检查（缺卡 `mesNot`）→ 剧情引入（这里是**现实层框架剧情文本**，直哉与彩野在教室对话）→ `oCard.selectCardObj()` 让玩家从持有卡中递卡，比对目标卡号（错卡 `mesNG`，随机 3 种反应）→ resolve 剧情 → `myCard[fragmentDoCardId].hold = 1` + `oCard.show(卡面, "『…』のあらすじを作成しました。")`。

**卡片分类**（`plotTitle[1..195]` 是卡名总表，`cardSort` 是图鉴排序）：
- 场景卡/选择卡：对应 storyRoute 场景，fragment 做卡获得。选择卡做成后，Story 重讲该 `_sel` 场景才显示全部选项（未持卡时只有默认项）——**分支解锁机制**。
- 关键词卡（95–97/105–107/109/114–117/119–132 等，如 コックリさん、ハンバーガー、黒板の上の時計）：Story 听完对应场景自动入手（场景结尾闭包 `myCard[N].hold=1`），做卡时当"素材/证据"用。crd 脚本为 9 行 stub（只显示「≪入手済みカード≫」）。
- 章节梗概卡 133–144 + 145（いつかきみがみるお話。）：完成各章 `_f` 框架剧本时授予；持有后可整章跳过（如 s1s_40：持卡 133 直接 RUN s2）并解锁回想/文库/音乐。
- 日记卡 178–191、93、195：crd_177（サクラさん）向彩野上交全部章节梗概后一次性解锁——重构佐倉雪乃的日记，开启第 5 章。
- 特殊大谜题：crd_103『選択：ノート』需卡 133–139+145+146+192；crd_104『True Color』需全部 14 张日记卡；各章终卡（30/61/89/91/94/110/118/162/175/176/193）需多张本章卡并 `run` 对应 `_f` 章。

**探索场景**（『探索：…』）：`comSelectMap` 学校地图选点（美術室/音楽室/保健室/職員室/中庭/校庭/教室/屋上/廊下/図書室），每点有 1–3 段小剧情（dispatcher 内局部函数），彩野有随机到场语音（comSectionMapmoveAyanoIn）。

**其他模式**：memory=按章重放 `_f` 剧本（memoryFlag 门控）；novel=5 本页图小说（页数 112/159/119/119/452）；music/graphic=画廊。主菜单在 `startMenuState==2` 且持卡 140 后出现「セクション7」直达项。

## 章节结构与剧情 DAG

场景 ID 规则：`s1s_20`、`s3s_580_sel`（`_sel`=选择场景）、`s1f-10`、`s3fa-10`、`sof_10`、`e1s_10`。`comSectionUID2ScriptFileName`：前 2 字符=章，第 3 字符=模式 → 脚本文件 `snr_<章>_10_<模式>`。每个章节脚本尾部 `main()` 是 `doScriptScene` 状态机 = **DAG 的权威定义**：`scene_X(id, "标题")` 演出 → 赋值下一场景；`comDlgSelectItem` 分支（选项=png/select 图）；`comSectionStoryCheckRoute("X")` 按本轮是否讲过 X 分支；`myCard[N].hold` 门控跨章跳转。

- `_s` 剧本（9 个）= **故事层**（彩野向直哉讲述的 5 年前的故事，主角是故事内人物）。
- `_f` 剧本（14 个）= **现实层**（直哉视角的当下），由各章终卡 crd 触发一次，此后进回想。
- 章节流与跨章跳转（默认通关顺序 1→2→3A/3B→4A/4B→5→6→7→8→EX1→EX2）：
  - s0f 序章（现实层，PROLOGUE 菜单直入）→ 得卡 1。
  - s1：s1s_35_sel 三选（约束/想不起/没约）；s1s_150 按是否讲过 s1s_110 分歧；s1s_260_sel 选「声の主」→ **RUN s5**（サクラ日记章，需先有日记卡）；正常线到 s1s_330 完结。有 2 个 GAMEOVER 支线。
  - s2：s2s_10 持卡 31 跳过日常段；ナゾトキ 多层选择迷宫（答对/答错影响后续 s2s_260_sel 的选项集）；周末去处（プール/プラネタリウム）伏笔；s2s_390 检查 (s2s_170∧s2s_300∧s2s_350) 决定夜晚成立与否，否则 GAMEOVER。
  - s3：楼梯怪谈线；s3s_50_sel 选「興味深いウワサ」→ **RUN s6**；s3s_300_sel 第 3 项（需卡 135）→ **RUN s4**；s3s_620 持卡 138 出现 s3s_641_sel（且选项 2 需本轮讲过 s4s_40）→ 3A 完（ユウイチとキス）或 3B 完（キスしない）。
  - s4（ユウイチ视点开始）：s4s_30_sel 选「私じゃない」→ 回 **s3s_340**；s4s_70 持卡 142 → s4s_100_sel「先生を受け入れる」→ **RUN e1**（由加里章）；s4s_490_sel 持卡 141 出现第 3 项「彩野を元の姿に戻す」→ **RUN s8**；正常线 4A 完（消えたサクラ）/4B 完（サクラを待つ）。
  - s5（サクラの日記，日期体：9/13→2/13 + アヤノの返信 9/25、10/30）：多处「发作」选择，选错 GAMEOVER；s5s_680 持卡 143 出现「もうしばらく待つ」→ **RUN e2**。
  - s6：サクラからの手紙 → 図書室 → 『True Color』（s6s_150_sel 需卡 103 大谜题解锁）→ 中庭の雪完结。多 GAMEOVER。
  - s7：**无 `_s`**，只有 s7f（主菜单直入）＝现实层高潮章（重演坠楼日）+ 第一次 staff roll。
  - s8：s8s 仅 5 场（僕の言葉→フェンスの向こう側→誰も見たことのない夕焼け）；s8f=黎明结局 + 五年后 + 第二次 staff roll。
  - 谢幕章（encore，2026-09-02 本地化新增·编外）：canonical 源在 `layers/scripts/snr_finale.lua`
    ——编外脚本刻意不入 `lua_scripts/`（那是只读基座，混入中文正文会打破基座与原始字节码的
    逐字节等价）；由 `layers/manifest.toml` 的 `[[scripts]]` 登记，`build_disc.py` 的 `lua`
    阶段经 `tools/layers.py::build_final_sources` 装配为新成员 `script/snr_finale.lua`。场景
    fin-10..50（2026-09-22 v3 加 fin-35『讲述者们』：千秋以 fin-20 说书体转述七张谢幕卡的
    【所思所想】，卡面挂 mini 位；文稿与决定记录 `docs/finale/draft-finale-v3.md`），主菜单
    encore 项直达（卡 144 门控，`snr_mainmenu` 第 5 形态，改动落在
    `layers/overlays/encore-menu.toml`），**绝不进 storyRoute**；vms 17300–17481（v2，冻结）
    + 17600–17799（v3：fin-35 17600–17700、fin-40 新行 17720–17746、fin-50 新行 17760–17763）
    + 卡消息 18201–18207（登记见 `layers/vms_ids.toml`）。谢幕卡 crd_201..207 与菜单图
    title_14_a 经 `layers/manifest.toml` 的 `[gim].new` 表进包（模板 crd_1_a/title_13_a）。
    **fin-40 文化祭的客人＝DeepSeek 拟人鲸少女**（用户 2026-09-21 定，代表全部 AI 朋友；
    对白核心段用户执笔）：CG 新成员 `event/eve_74_z`（源 `docs/finale/assets/eve_74_z.src.png`，
    `tools/bake_finale_event.py` 降采样+预量化 256 色，模板 eve_74_x），客人到场时同层溶解，
    e2f_340 仍用原图；画廊叠加层 `finale-gallery-cg` 把 eve_74 格扩成双变体。**翻卡段 BGM**
    `bgm/bgm_fin_1`（用户自供 `bgm_5_x` remix 3:21，整曲循环、裁到 3:16、−21 LUFS；前 1:20 8bit、
    1:29 起吉他）走 `[sound]` 管线（下文「新增音频」），fin-30 只加轻量延时不为读速兜底。
    谢幕卡面与 `docs/finale/cards/*.md` 的原话不改（七卡「统稿零改字」纪律），转述可以换比方。
    **fin-0『递笔』动笔音效**（2026-09-23）：沿 e2 写手层语法「翻页 se_101 → 按笔芯 se_51」（crd_2「カチカチ、と
    ペンの芯をのばし」同款；本作无写字沙沙声：se_46 转笔、se_71 撕纸、se_48/se_69 门、se_30 卡片滑入、se_79 出拳），
    `tools/emu/drives/se_probe.py` 开 DumpAudio 录音后按参照 SE 包络互相关核对。
    **题名 logo 双态**（2026-09-11）：fin-50 跑完置 `systemSave.finaleReadFlag = true` 并
    `autoSystemSave(0)`（缺省 false 由 `layers/overlays/finale-read-flag.toml` 写进 snr_common 的
    systemSave 字面表；旧系统数据缺键取 nil 即 false，零迁移）；主菜单 `title-logo-zh` 层据此把
    logo 从日文 `title_01_a` 换成中文 `sysgim/title_01_c`（新成员，模板 title_01_a，同 405×89，
    绘制期直载工作层；源图 `docs/finale/assets/title_01_c.src.png` → `tools/bake_finale_title.py`
    预乘 alpha 降采样 → `build/finale_title/`，量化 MSE≈28 超告警阈但复合到标题底图后 MSE 11.8、
    最大通道差 26，目检不可辨）。⚠ **入库的 src 已是配色后处理过的成品**（2026-09-12，
    生成式源图比日文原版更深更浓蓝：按 title_01_a 做 Oklab 明度/浓度/色相校准，大标题明度
    中位数 0.394→0.502、浓度 0.136→0.091，对齐原版的 0.506/0.091；只改 RGB，alpha 与字形
    几何逐像素未动）——**不要再对它跑一次调色**，调色脚本是一次性的，不在本仓库。
    故事层 s8f/e2f 结尾的 title_01_a 落版刻意未动。端到端驾驶 `tools/emu/drives/title_logo.py`。
    实施与验证台账：docs/ops/finale-stage-impl-2026-09-02.md（已被 docs/ops/disc-pipeline.md
    取代为现行命令面，历史记录仍有效）。
  - e1s：ユカリ第一人称一本道（回忆 25 连场）；e1f 仅 1 场。
  - e2s：千秋（多年后）的调查——**只有对方半边的电话/拜访独白**（老教师/筑紫(きくちゃん)/护士/雪乃生父/酒吧老板/彩野母）；e2f：雪乃弥留之际"编纂"的if 幸福线（标题回收章）。
- GAMEOVER/COMPLETE/TIMEOVER 都进 `comStorySceneEnd` 三选单（回 Story/去 Fragment/回菜单）。
- 强制事件：fragment_main 开头若持卡 136 且无卡 145 → 强制播 s3fc（彩野母入院 + 天台发现日记与绘本）。

## 剧情核心（翻译前必读的世界观真相）

**双层叙事**：现实层（现在，8 月盂兰盆）——23 岁的直哉回乡，陪护 17 岁起患重度**前向性健忘**（顺行性遗忘，海马体等受损，新记忆只保 15 分钟，手帐第一页：『私は17歳の頃から先の新しい記憶をすることができない→１５分で記憶は消える→重要な事はこの手帳に書いておくこと！』）的同级生彩野；她在旧教室里断续讲一个"夏天的学校故事"，直哉发明名片背面写『あらすじ』的卡片系统帮她跨越 15 分钟继续讲。故事层——她讲的『物語』即『True Color』：女生徒アヤノ与男子生徒ユウイチ的夏日校园故事（怪谈、占卜、コックリさん、绝对灵验的オマジナイ）。片假名【アヤノ】【ユカリ】=故事内角色，汉字【彩野】【由加里】=现实人物，**翻译必须保留这一区分**（建议中文同样用两套写法）。

**5 年前的真相**（s7f 全盘揭示）：彩野幼时离家出走被困学校天台一夜，父亲清晨背她回家哼着『帰りの歌』（=《浜千鳥》，黄昏放送曲），她把朝阳当成"谁也没见过的夕焼け"——此即绘本『いつか きみが みる お話。』（全平假名童谣体，妖怪ナハメ的追逐故事，s3fc_90 内嵌全文；献词"给已故的父亲和你"）。高中时彩野与青梅竹马ユウイチ疏远、失眠住院，结识长期住院的佐倉雪乃（サクラ）；**探病的其实是直哉，雪乃却误认成ユウイチ**，于是两人合写的『True Color』里，以"探病少年"为原型的男主被命名为ユウイチ——**故事里的ユウイチ其实是直哉**。雪乃（疑似受问题处方药影响，医院以"病死"处理并赔偿封口）2 月死去，死前托妹妹千秋 9/13 寄出两封"来自死者"的信（给ユウイチ：天台可见夕焼け的秘密；给彩野：等待的指示），并让她在校庭按下录着自己歌声的播放器——想以"绝对灵验的魔法"促成故事的 happy end（ユウイチ天台告白）。但因原型错位，当日ユウイチ先去图书室与由加里相拥（e1 章：天台抽烟"不良教师"×装病翘课"不良少年"的秘密羁绊，ユウイチ曾向她告白），彩野目击后崩溃冲上天台，ユウイチ追去告白（『俺は、アヤノの事が好きだ』，且早有觉悟）坠楼身亡；服强效安眠药的彩野随后追随跳下，重伤失忆。彩野中途已察觉雪乃的误认，为不让直哉背负"扮演ユウイチ告白"的结局，把「不许告诉直哉真相」写进手帐（因失忆，该规则永不可破），并生成了否定 happy end 的 3B/4B 黑暗分支。
**现实层结局**：直哉集齐全部梗概后重演那一天（由加里配合重现图书室相拥、千秋播放『お姉ちゃん.mp3』、直哉以ユウイチ身份在围栏外告白）；彩野坠落瞬间被他一把抓住（呼应序章"这次要紧紧抓住她的手"；「腕」译法 v6 起按语境取「手/手臂」，复现句族以 skeleton/anchors.yaml 为准）救回；黎明众人唱着浜千鳥送她回家——她的『物語』完结，从此不再游荡到学校（s8f）。五年后：直哉成为母校教师，高中生千秋在天台"变成"姐姐完成告别；直哉把写上逗号的『True Color，』笔记本交给千秋——**续写的故事=第二部小说=セカンドノベル**（三重题意：雪乃弥留编纂的 if 幸福线 e2f / 文化祭展位名 / 千秋要写的续篇）。e2s 里多年后的千秋独自查访当年真相（药害、封口、目击者筑紫），黑暗底流收束。

人物速查：直哉（NAO，现实主角，暗恋彩野）；彩野（AYA，失忆者，爱的是ユウイチ→而故事里她写的"ユウイチ"原型是直哉）；ユウイチ（YUI，5 年前坠亡，生前在酒吧寄存威士忌托老板转交成年直哉）；由加里（YUK，国语/古文教师，至今仍在校）；佐倉雪乃=サクラ（SAK，千秋之姐，体弱住院，True Color 共作者）；千秋（CHI，雪乃之妹，序章校庭的神秘小女孩=5 年来遵守姐姐嘱托等待；渣生父监护）；きくちゃん=筑紫（田径部同学，坠楼目击者）；彩野母（HAH）；酒吧マスター（MAS，店 10 年后改回 BAR）；水尾澄等仅出现于 novel 页图小说。关键道具/母题：手帳、名片卡片、消しゴム（刻名オマジナイ）、黒板の上の時計（停在 0 时）、帰りの歌/浜千鳥、アラザン银珠巧克力与草莓甜甜圈（直哉↔雪乃↔千秋的暗号）、指輪、ネックレス、ドーナツ。

## 文本载体清单（翻译工作量地图）

1. **脚本内文本**（主体）：16749 条 `vms`（全局唯一 ID 1..17220）+ `savedataTitle`/`plotTitle[1..195]`/场景标题参数/`oCard.show` 提示语（tr_line 已标记一部分）。提取正则：`vms\((\d+), "([A-Z0-9]+|NONVOICE|NORECORD)", "(.*)"\)`；场景归属按所在 `scene_*` 函数 + 各章 main() 调度器。
2. **图片烤字**（需图像重制）：
   - `select/` 278 张：全部选项按钮文字（`sel_<场景>_<a/b/c>_{on,off}`）+ 地图点名。
   - `card/` 197 张卡面：**含完整梗概正文段落**（标题+正文+セクション栏），是隐藏叙事语料，必须逐张翻译重排。
   - `plot/` 4 张缩略图集（60 卡/张，82×48 格）与 `scene/` 4 张场景名条集（145×15 格，3 列）：标题烤字。
   - `sysgim/` 103 张：标题 logo（title_01_a）、菜单项（title_02..13）、暂停菜单（sys_20_c）、各确认对话框（sys_5_*、sys_12/13_*）、卡片模式 UI（sys_11_*）、选项画面（sys_21..24_*）。**开机链第五卡 `IPL03`**（2026-09-21 新增成员：汉化组署名＋献词，`tools/bake_boot_dedication.py` 纯排版生成，`layers/overlays/boot-dedication.toml` 插在 `snr_common.main()` 的版权页之后、自动存档告知之前；署名只写文字**不画 ∀**——组名是 Anthropic 的 A 转 180° 的梗，画出来即破；bake-decisions Y17）。
   - ~~`novel/` 993 张~~ ❌ **已出本项目范围**（用户 2026-08-30 裁定，不烤、不立项）。玩家侧说明已就位（2026-09-21）：章节 1 读完的原作 novel 介绍之后接八条【■汉化说明】、文库入口一次性两条（`layers/overlays/novel-notice-{s1f,entry}.toml`，vms 17500–17511，守卫键 `systemSave.novelNoticeSeen`；docs/ops/novel-notice-2026-09-21.md）。存档记录：5 本竖排小说整页渲染，**存储时顺时针旋转 90°**（PSP 横持阅读），novel05 长达 452 页。作为剧情参考读图时仍需先旋转（见「常用操作」）。
   - `music/` `graphic/` 画廊框文字；`bg/` 少量含字（黑板板书等）；`event/` CG 个别含字。
3. **音频**（不在本仓库）：voice/*.at3 按 ID 对应 vms；无字幕外文本。

## 剧情 DAG 组装规则（给翻译工具）

把"新开局→当前文本"的上下文序列定义为玩家实际经历顺序，可按以下规则机械重建：
1. 序：s0f 全部 → s1s_10 → s1s_20（首次 100 耗时演出）→ 教程 crd_0 → crd_2 → OP。
2. 之后是 Story/Fragment 交替：Story 按各章 dispatcher 推进 `storyRoute`；Time over/主动切换后，Fragment 按**路线前缀顺序**为每个场景插入对应 `snr_crd_N` 文本（做卡剧情=现实层），再回 Story 从断点续讲。跨章跳转与分支解锁按上文门控条件展开。
3. `_f` 章文本在各章终卡 crd 之后插入；s3fc 在得卡 136 后强制插入；s7f 在卡 140 后经主菜单进入；e1/e2 分别经 s4s_100_sel（需卡 142）与 s5s_680（需卡 143）进入——即 **EX 章的上下文前缀天然包含全部 1–8 章**。
4. 同一场景重讲（换分支）时，之前的讲述也在"经历"里——工具可将已做卡场景以其**卡面梗概文本**替代全文（与游戏内『あらすじ』语义一致），实现前缀 compact。
5. 探索场景各地点小节、ナゾトキ 选择迷宫等 dispatcher 内嵌段落，按局部函数调用顺序展开。
6. e2s 的单边对话、s7f 的卡片逐张递交段，强依赖全局剧情知识，应放在上下文最完整时再翻。

术语/名字一致性表（工具应内置 glossary 强约束）：あらすじ、物語/お話、カード、手帳、記憶ルート、フラグメント、セクション、帰りの歌（浜千鳥）、誰も見たことのない夕焼け、オマジナイ、ナゾトキ、ウワサ、コックリさん、お化け階段、ナハメ、True Color（保留英文）、いつか きみが みる お話。、セカンドノベル、前向性/逆向性健忘、エピソード記憶/手続き記憶、片假名角色名 vs 汉字角色名两套写法。

## 开发规约

- **环境**：uv 管理的项目 venv。新会话先 `uv sync`；跑脚本 `uv run python ...`；加依赖 `uv add <pkg>`。`pyproject.toml`/`uv.lock` 入库，`.venv/` 已 gitignore。**只设下限 `>=3.12` 且不入 `.python-version`**：钉死精确版会让云端环境（Ubuntu 24.04 自带 3.12）必须联网下载托管解释器，且 root 建环境／非 root 跑会话的归属问题随之而来；3.12/3.13/3.14 全测已验证等价。`tools/extract_*.py` 保持纯 stdlib（系统 python3 也能直接跑）。LLM API key 走 `.env`（已 gitignore）或环境变量，绝不入库。
- **原始资产只读**：`lua_scripts/`、`png/` 不就地修改。注入/回写类输出先落 `build/`（gitignore）；确需改原件时走分支，游戏内验证后再合并。
- **层纪律**：新增本地化文本 → 建叠加层（`layers/overlays/*.toml`）+ 在 `layers/vms_ids.toml`
  登记 id 段；改谢幕章 → 改 `layers/scripts/snr_finale.lua`；要测试捷径（跳 IPL、直入场景、
  全解锁主菜单等）→ `build_disc.py --profile test --mode …`；改引擎行为（禁则表、ruby 算式等
  EBOOT 二进制）→ `layers/eboot/<名>.toml` 字节补丁层 + `manifest.toml` 的 `[eboot].order`
  登记（源 `assets/EBOOT.dec.elf` 是 PPSSPP dump 的解密 EBOOT，指纹钉在 manifest；
  `tools/eboot_patch.py`；研究/改引擎的完整走法与陷阱见 `docs/ops/eboot-hacking-runbook.md`）；
  新增音频 → `tools/at3p.py encode` 产 `layers/audio/<名>.at3` + `manifest.toml` 的 `[[sound.tracks]]`
  登记（成员名/两侧 sha256/循环起点/裁尾/响度；原 99 成员不改不撞名），`build_disc` 的 `sound`
  阶段装进 SOUND.BIN，`tools/emu/drives/bgm_probe.py` 听回绕；永远不要手改 `lua_scripts/`。
  加层后先 `tools/layers.py check` 过闸再出盘，完整走查见 `docs/ops/disc-pipeline.md`。
- **analysis/ 同步**：改动 lua 的 commit 必须同时重跑 `tools/extract_*.py` 并包含产物更新，保证 analysis/ 永远可信。
- **分支（轻量制）**：主分支 `main`，日常改动（工具代码/文档/analysis 再生成/翻译数据积累）直接提交。三类操作强制开分支：①改写 lua_scripts//png/ 原件 ②大规模批量替换/迁移 ③实验性重构或 prompt 策略试验。命名 `feat/` `fix/` `data/` `exp/`，验证后 merge 即删分支。
- **commit**：Claude 在每个自洽工作单元完成并自检通过后直接本地提交，无需逐次确认；一个逻辑变更一个 commit，工具代码与翻译数据分开提交。**push 仅在用户明示时执行**；如建远端必须 private（仓库含版权游戏素材，不得公开）。
- **message 规范**：`type: 中文摘要`，type ∈ feat / fix / docs / data / analysis / chore / refactor。示例：`data: s1 章译文初稿入库`、`analysis: lua 变更后重跑提取产物`。
- **SDD 工作台**：`.superpowers/sdd/<plan>/` 被插件自忽略（其脚本每次运行都会把该目录 .gitignore 重写为 `*`，改它无用）。其中 `*.md`（progress.md 台账、task-N-brief/report、hotfix 简报/报告）是不可再生的执行状态与证据，**入库携带**：新文件 `git add -f` 一次，已跟踪后随就近 commit 正常提交；`review-*.diff` 评审包可由 git 历史一键再生，保持忽略。

## 云端环境（Claude Code web cloud environment）

以下描述以 2026-07-30 首次实测为准，证据见 `docs/ops/cloud-acceptance-2026-07-30.md`（云端容器销毁后不可复现，故入库）。

**云端会话开场第一件事：手动执行 `bash .claude/cloud-setup.sh --mode session`。** 它不会被自动调用（原因见下），而它是环境自检与基线报告的唯一入口。

- **仓库级 `.claude/settings.json` 在云端整体不被采纳**：`hooks` / `enabledPlugins` / `extraKnownMarketplaces` / `permissions` 四项**全部失效**（该项目 `hasTrustDialogAccepted=false`；`permissions.allow` 也纯属装饰，放行实际来自 `IS_SANDBOX=yes`）。其中 `enabledPlugins`/`extraKnownMarketplaces` 两项已由 `cloud-setup.sh` §1.6 在 **setup 时点**装进用户级 `~/.claude/` 来兑现——**superpowers/mattpocock 在云端可用**（2026-07-30 实测：清单里 14 条 `superpowers:` skill、`Skill(superpowers:executing-plans)` 正常解析、插件自带的 SessionStart hook 正常派生）。`hooks`/`permissions` 两项仍无解——**注意区分**：派生的是插件自带的**用户级** hook，仓库级 hook 依旧不派生。该文件仍保留，因为本地会话有效。
- **`SKIP_PLUGIN_MARKETPLACE=true` 只短路 marketplace 解析（获取/更新），不挡「加载已落盘且已 enable 的插件」**——这正是上面那条解法能成立的原因。该 flag 由控制面随 startup context 递入，容器内改不动（`--mode session` 里它照样是 `true`，插件照样挂载）。
- **真正生效的是账户级配置**：`CLAUDE_CODE_SYNC_SKILLS=1` 会把 claude.ai 账户下的自定义 skill 同步进 `~/.claude/skills/`，云端另有自带的 `~/.claude/launcher-settings.json`（含其自己的 SessionStart/Stop hook）。仓库 CLAUDE.md 本身**确实生效**。故「不继承本机 `~/.claude`」只在文件系统意义上成立，账户级 skill 是会到位的。
- **技能有两个可能载体，`cloud-setup.sh` 都会探测并打进报告**：`~/.claude/skills/`（账户同步的独立 skill）与 `~/.claude/plugins/cache/<市场>/<插件>/<版本>/`（插件形态，本机即如此）。两者皆空才告警。注意 `~/.claude/plugins/data/` 只是每插件的运行时目录（本机为空目录），**不能**当作「插件已装」的判据。报告同时打印 `SKIP_PLUGIN_MARKETPLACE` 与 `CLAUDE_CODE_SYNC_SKILLS` 的实际取值。
- `.claude/cloud-ui-setup.sh`——**粘贴到 claude.ai/code 环境设置的 “Setup script” 字段**（该字段不在仓库里，本文件只是版本化副本）。刻意写得极薄且稳定：改它会触发整机快照重建，而改下面那个不会。它自己把 PWD/HOME/USER 等上下文写进 `/var/log/claude-cloud-setup.log`（打 stdout 会丢，首次验收即如此）。
- `.claude/cloud-setup.sh`——真逻辑，幂等。首次建环境由 UI 脚本以 `--mode setup` 调用，之后每次会话手动以 `--mode session` 执行。内容：`uv sync --locked`（漂移则回退并告警）、探测 `~/.claude` 实况、建 `work/ctx work/out`、冒烟（`build_ledger`/`build_dag --check` + pytest + 系统 python3 编译 `extract_*.py`）、浅克隆/无 tag 告警、**SDD 证据保全**告警（`.superpowers/sdd/` 下未 `git add -f` 的 `*.md` 会随环境销毁而永久丢失）、写基线报告。报告首行自述 `--mode` 与时间——**「`work/setup-baseline.txt` 存在」不等于 session 跑过**，它可能是建环境时留下的。
- **脚本永远 `exit 0`**：UI setup 脚本非零退出会让整个环境创建失败，而其日志位置无官方文档；故一切问题降级为告警写进报告，绝不由冒烟结果决定退出码（红测试恰恰可能正是云端会话要去修的东西）。
- **克隆是浅克隆且不带 tag**：`git rev-list --count HEAD` 约 50，`skeleton-v1` 冻结点在云端**不存在**；凡以它为基准的核对须先 `git fetch --tags origin`（要全史再 `--unshallow`）。
- 镜像实况：Ubuntu 24.04，**会话本身也是 root**；默认 `python3` 是 **3.11**，3.12/3.13 以 `python3.1x` 并存，uv 就地选 3.12、零下载（故 `tools/extract_*.py` 的「系统 python3 直接可跑」真实门槛是 **3.11 兼容**）。无 `gh`。网络：PyPI/`api.github.com`/`raw.githubusercontent.com` 通，git 走本地 proxy 重写，但 **github.com 网页抓取被拒**（400/403）。
- 约束速记（官方文档）：setup 以 root 跑、约 5 分钟预算、只在首次建环境时执行一次、其后整机文件系统被快照复用（装的包留存，进程不留存）；环境变量在 UI 配置且**明文可见，不要放 API key**（本项目工具链全离线，无需任何密钥）。
- **UI 配的环境变量到不了 setup，只到会话**（2026-07-30 探针实测）：平台自带的 20 个变量（含 `SKIP_PLUGIN_MARKETPLACE`/`CLAUDE_CODE_SYNC_SKILLS`）走 startup context，在引导层就位，setup 与会话都看得到；**UI 里自定义的变量走另一条通道**，由 `environment-manager` 在派生 `claude` 进程时才注入，`--mode setup` 的进程链上完全没有。故 **`cloud-setup.sh` 的 setup 分支不得依赖任何 UI 环境变量**。

## 常用操作（现阶段）

- 三件套分析产物已归档在 `analysis/`（DAG 快照 / 卡片谜题表 / 全量文本摘要），lua 改动后用 `tools/extract_{dag,crd,text}.py` 重跑（前两个输出到 stdout，text 直接写 `analysis/text_digest/`）。查剧情/查结构**优先读 analysis/ 而不是原始 lua**。
- 消息窗排版校验：`uv run python tools/msg_layout_check.py --profile release`（按引擎规则逐字模拟每条 msg 文本：425 px×4 行像素模型、拉丁真实步进、禁则表、ruby 公式、500 B 缓冲；`--show <id>` 看单条版面；`latin-split` 告警 = 拉丁串被自动折行掰开，需手工 `_r` 或改写）。`layers.py check` 与 `build_disc.py` 的 `lua` 阶段已内置，release 有错误即拒绝。
- 通读全书定稿：`uv run python tools/read_server.py` 开 Web UI（逐行摊开原文/首译/修订史/批注，人读）；`uv run python tools/export_read.py` 导出 `work/out/read.md`（约 40 万字符，每条译文一行、无原文与批注，喂给长上下文模型一次读完）。两者共用同一条路线序。
- 数场景/文本量：`grep -c '^scene_' lua_scripts/snr_s1_10_s.lua`；`grep -c 'vms(' lua_scripts/*.lua`。
- 手工核对某章调度器：读文件末尾的 `main = function()`（`doScriptScene` 状态机）。
- 解包/回封游戏资源包：`python3 tools/databin.py unpack assets/DATA.BIN build/databin`、`pack build/databin build/DATA.new.BIN`（`assets/` 为本机 gitignore 资产，不入库；回封无压缩，顺序按 manifest.jsonl 行序 = 原封包序）。
- 产实机盘：先 `uv run python tools/layers.py check --profile release` 过闸（秒级，不产盘），
  再 `uv run python tools/build_disc.py`（缺省 `--profile release --stage all`，跑到 `iso` 止）
  → `build/dist/game_zh.iso`（就地替换 `assets/orig.iso` 里的 DATA.BIN；发布断言不过拒绝出盘）；
  单独用工具则 `python3 tools/umdiso.py replace <原iso> <新iso> /PSP_GAME/USRDIR/DATA.BIN <新DATA.BIN>`，
  改完必 `verify --against <原iso>` 看差异区间。剖面/层/阶段全貌见 `docs/ops/disc-pipeline.md`。
- 读 novel 页图前先旋转：`python3 -c "from PIL import Image; Image.open(p).rotate(-90, expand=True).save(out)"`。
- 图片均为 PSP 480×272 逻辑分辨率素材；改图（烤字 png）进游戏 = 量化到模板色板容量后
  `uv run python tools/gimcodec.py encode <原包同名模板.gim> <烤字.png> <out.gim>`，再经 databin.py 回封。
  索引图色板 16/256 色（RGBA8888），量化损耗需在烤字 QA 时目检。

## 已知坑与注意事项

- `vms` 消息 ID 关联已读标记与语音，翻译只替换第三参数字符串；`_n/_r/<漢字,かな>/≪≫/≦≧/【】/○/■` 控制码原样保留。
- 文本行宽：`cBrStr` 按 24 字符硬折行（卡名用）；消息窗排版由引擎处理，但过长中文行仍可能溢出，需实测。
- **PGF 头部 ascender 决定 ruby/正文落点，由 `build_font.patch_pgf_header` 自己写、测试钉住（17px→16、9px→9）**：引擎按 `y + (ascender>>6) − top + 1` 摆字形。2026-09-19 事故——`/tmp/pgftool/ttf_pgf` 被重编后丢了头部补丁，ascender 回到上游写死的 15.83，ruby 下沉 6 px 压进正文（绘本拼音）。ttf_pgf 二进制从此只管字形，头部量度与它的版本无关；改字体产物参数记得动 `build_font.RECIPE` 戳。
- **e2f 4838–4847 的字幕与配音是两套台词**（有意演出，全库唯一）：`≪≫` 内是雪乃写的故事，配音（NAO+CHI）念的是直哉
  坦白自己不是ユウイチ的另一段对话。中文版按用户裁定（2026-09-21）在同一消息里 `_r` 换行后用 `「」` 补出配音内容，
  `check_edit` 的「」计数警告对这十行是已知放行；转写与清点见 docs/ops/e2f-voice-text-divergence-2026-09-21.md。
- s7f 引用的给彩野的信文（『放課後、校庭で待っていて』）与 s5f_80 实物信（『屋上で待っていて。サクラ』）字面不同——原作即如此，翻译时保持各自原样，不要"修复"。
- sceneId2aCard 表中大量 `sceneId2aCard.keyword = N` 是反编译噪声（键重复覆盖），仅真实场景键有效。
- 反编译代码有冗余（重复 `layerCopy`、未用变量 g3/i3 等），修改时最小触碰。
- 主线术语的既有官方英文（Prologue/Story/Fragment/library/memory 等菜单词）在图片里成对出现（英+日）。⚠ 2026-09-01 裁定 E22 已定稿为**只留英文大词、小注只擦不写**（7px 注芯下中文糊成一团），encore 项同族处理。
- **层号 200 以下不能常驻**（2026-09-02 实测）：`cInitGame→cInitLayer` 清掉 <200 的层，"86–199 无人使用"实为"无人能用"；常驻区 201–255 已满。需要新图的场合走"绘制期同步 layerLoad 直载工作层"（encore 菜单图即此做法）。
- **DATA.BIN 可新增成员**：按名排序位插入（引擎二分查找），build_disc.stage_stage 已内建；script/card/sysgim/pgf/event 五面实测通过。BGM 不在 DATA.BIN 而在 **SOUND.BIN**（同款 pack 容器，99 成员；引擎只吃 ATRAC3+ 且文件必须带 `smpl` 块，缺了 `sceAtracSetLoopNum` 就失败、线程静默退出——**曲子放不出来不报错**，成员缺席同样静默）；新曲走 `[sound]` 管线（`docs/superpowers/specs/2026-09-17-encore-bgm-injection-design.md`），2026-09-22 首曲 bgm_fin_1 模拟器实测起播与整曲回绕。
- **存档 = Pluto 序列化整个 `mainThread` 协程**（2026-09-05 逆向 EBOOT，`docs/ops/eboot-savedata-research-2026-09-05.md`）：`runListSave()` 只置标志并 yield，引擎随后用 Pluto 把 `gameSave` 表（容量 30720 B）和挂起中的章节脚本协程——**含正在运行脚本的整棵 Proto 树，即整份字节码**——写进一个 406120 B 的 bss 存档结构，线程 blob 定长 **327680 B**，写入回调**无边界检查**，超容量即溢出砸坏后续字段与别的全局（"中日双语翻倍 vms 后大章节存档崩溃"的根因；原版 s1s 章已占 78%，中文版 71%）。`build_disc.py` 的 members 阶段用 `tools/pluto_size.py` 按字节码估算把关（release 超容量拒绝出盘；容量从层推导）；实测用 `tools/emu/drives/save_probe.py`，存→读往返用 `save_roundtrip.py`。**扩容层 `layers/eboot/savebuf.toml`**（把结构搬到 bss 新尾部、线程区 +256 KiB；`tools/eboot_relscan.py move-plan` 生成，测试重推对账）现只在 test 剖面生效，已在 PPSSPP 上用翻倍 s1s 完成红/绿与往返验证；要上发布盘改 profile 即可，代价是与旧布局存档不兼容、内存少 716 KB。**IDB 里 bss 对象的地址比链接时 VA 高 0x6DA40**（IDA 重定位 bug），运行时 = IDA 地址 − 0x6DA40 + 0x08804000，代码/rodata 不受影响（runbook §1）。
- **消息窗排版是引擎侧定宽网格**（2026-09-04 逆向 EBOOT 得出）：原版每个 UTF-8 字符恒占 17 px 一格、25 格/行、26 px 行距、4 行/页，第 5 行起静默不画；正文缓冲与 backlog 每槽 500 字节且 `sprintf` 无界；行头/行末禁则靠 .rodata 两条 UTF-8 表（VA 0x663E0 / 0x66462）做 `strstr`，只收日文标点——中文 `，…：）` 会落行首，`（` 会落行尾（`layers/eboot/kinsoku.toml` 已换成中文表）。**2026-09-12 起 `layers/eboot/msgcol-px.toml` 把列计数改成像素**：汉字仍 17 px 一格（无 ASCII 的文本版面逐像素不变），拉丁字母按 17px 字体真实步进（比例宽，"Ayano" 85→48 px），ruby 先画 base 取真实宽再居中；卡名的全角拉丁是 Lua 侧 `cHan2Zen` 造成的，由 `layers/overlays/cardname-halfwidth.toml` 去掉。校验器 `msg_layout_check.py` 同步为像素模型，步进表 `data/font_advances_17.json`（改 17px 字体后 `tools/pgf_inspect.py export-advances` 重生成，测试钉住）。规则全貌见 `docs/ops/eboot-kinsoku-research-2026-09-04.md` §3/§9。**打 EBOOT 补丁的三条硬规矩**（编码一律用 `tools/mips_asm.py`，先拿纯净段往返验证，范式 `tools/msgcol_px.py`）：Allegrex 没有整数 `mul`（SPECIAL2 只有 halt），用 sll/addu 拼；字形推进 `advanceH>>6` 截断成整数像素，ruby/拼音的步进只能取整数 px（§7.4）；换掉带重定位条目的字（jal/j、lui/addiu 对）必须同时把该条目改成 R_MIPS_NONE，否则装载器照样往新指令里加基址（§7.5，实测砸过 s4）。
