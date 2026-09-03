# Handoff：谢幕章（encore）演出实施与实机验证

> **状态（2026-09-02）**：待办 1–5 已完成（裁决：小注不烤、e2f 链入不做），模拟器
> 全清单绿、发布 ISO 已产出，**待实机抽验后合并**——执行台账与实机待办清单见
> `docs/ops/finale-stage-impl-2026-09-02.md`。

> 交接自谢幕章创作线（2026-08-31~09-01 的 fable session）。文本与设计已全部定稿，
> 本次任务是把它**做进游戏并跑通**。另一条 session 已完成相当可用的 e2e test 设施，
> 过程中应充分利用（见"先读什么"第 4 条）。

## 你要做什么（一句话）

把谢幕章 `snr_finale.lua`＋主菜单 encore 直达项＋七张谢幕卡面＋菜单图做进
DATA.BIN／ISO，在模拟器与实机上从主菜单进入、全章跑通回到主菜单，首测清单全绿。

## 先读什么（按序，读完再动手）

1. `CLAUDE.md`——**注意 2026-08-31 已换反编译基座**（corpus/final，重编译逐字节相同；
   局部名 `l<depth>_<reg>` 型；tr_line 由 migrate_base 重生成；inject_lua/databin/
   gimcodec/umdiso/build_disc 全链路工具已在）。
2. `docs/finale/` 五件套：
   - `draft-finale-v2.md`——**文稿定稿**（场景 0『递笔』~场景 5，锚点与有意变奏行内注）
   - `snr_finale.lua`——演出脚本初版（见下"待办 2"的校对要求）
   - `mainmenu-entry-plan.md`——主菜单直达的 8 处改动清单（基于 corpus/final 行号，
     含 L845 硬编码陷阱、层号 198 注册、坐标 mock）
   - `stage-design-v1.md`——逐场演出设计＋首测清单
   - `cards-bake.yaml` ＋ `cards/01-07`——七张卡的文案源与原文（各轨模型真实征集件）
3. `git log --oneline docs/finale tools/bake_finale_*` ——本线的全部提交脉络。
4. **e2e test 设施**：由另一 session 完成，本 handoff 作者未见其细节——
   先 `git log --oneline -30` ＋翻 `docs/ops/` 最新的 handoff/runbook 自查其用法，
   把它纳入你的每一步验证（尤其"新增成员进包"与"改 lua 重编译注入"两件事）。

## 已完成资产（勿重做）

| 资产 | 位置 | 状态 |
|---|---|---|
| 谢幕章文稿 v2 | docs/finale/draft-finale-v2.md | **定稿**（文字层改动须回到发起人） |
| 演出脚本 | layers/scripts/snr_finale.lua | 初版，未测 |
| 七张卡面 PNG | build/finale_cards/（`tools/bake_finale_cards.py` 一键再生） | 成品，零溢出 |
| 菜单图 title_14_a | docs/finale/assets/title_14_a.png（源）＋ build/finale_menu/（成品，`tools/bake_finale_menu.py` 再生） | 成品；**小注文案 pending，见待办 1** |
| 主菜单改动方案 | docs/finale/mainmenu-entry-plan.md | 方案定稿，未实施 |
| 谢幕感言 | docs/finale/acknowledgement.md | 文档版（发布包 readme 底稿候选） |

## 待办（建议顺序）

1. **小注文案定稿**（等发起人一句话）：『- 谢幕 -』在 8px 注芯下笔画粘连（谢 12 画
   幕 13 画，实测糊），当前工具已切『- 安可 -』版并烤出（A/B 对比图发起人已看过，
   encore 的中文即安可，语义互训）。发起人拍板后 commit `tools/bake_finale_menu.py`
   当前工作区改动（该文件现处未提交态，diff 即安可切换）。
2. **snr_finale.lua 校对与编译**：初版写于换基座前，引擎 API 调用全部取自旧基座对
   s8f/e2f 的阅读——顶层函数名是跨基座稳定锚，理应无碍，但须：
   ①逐个函数名/全局（`oCard.show/showMiniIn/Out`、`cPlayBGMWrap`、`comEffect*`、
   `finSectionBegin` 所内联的 `savedataTitle/advIsPart/advPart/logEnable/
   systemConfig.setConfigButton`、`layerName.bg1/event/pose1`、`ceroFlag`）在
   corpus/final 基座上确认存在且签名一致；②过 PSP lua 编译器（e2e 设施应有此环节）；
   ③局部命名风格可保持现状（新写文件，不受反编译命名约束）。
3. **主菜单 8 处改动实施**：照 mainmenu-entry-plan.md §2 逐处落地（snr_mainmenu 6 处
   ＋snr_common 2 处）。⚠ 改 `lua_scripts/` 原件**强制开分支**（CLAUDE.md 规约），
   建议本次全部实施类改动同一分支（如 `feat/finale-stage`）。
   注意：plan §5 的"library 21px 等大字库"已被证伪（x-height 9px vs 13px），但只影响
   已完成的图件制作，不影响 lua 改动清单；改动清单行号已抽查可信。
4. **资源进包**（头号技术验证项，先小步验证再批量）：
   - **DATA.BIN 能否新增成员**：`snr_finale.lua`、`crd_201..207_a.gim`、
     `title_14_a.gim` 都是**新文件**。databin.py 自述"严格保持原封包成员顺序"——
     新增成员是否在支持面？不支持则需扩工具或改用"占用未引用既有槽"策略。
     **这是全部落地的前置，最先验证。**
   - **GIM 编码**：`gimcodec.py encode` 是模板回填（"只换像素与色板 payload"）。
     卡面：用任一原卡 gim 作模板（同 212×148；查 index4/8——16 色板下渐变底会损，
     256 色应可，量化后**逐张目检**）。title_14_a：100×68 而 title_13 模板 117×68，
     **尺寸不同**——确认模板回填是否钉死尺寸；若钉死，最省路径是把 title_14_a 画布
     pad 到 117×68（透明右边条，layerWidth 表仍按实宽或版面调整，见 plan §2.1 表）。
   - eve_74_z（中文封面变体）：发起人 gpt 改图**未到货**，lua 内 TODO 占位（同图重载，
     流程无碍）。到货后 encode 进包＋换 `scene_fin_40` 内一行文件名，并顺手评估
     `snr_graphic.lua` 的 `cgNumber[8][7][2]` 注册（一行）。
5. **首测清单**（stage-design-v1.md §5 全文＋以下补充）：
   - **vms 17300–17481 与 18201–18207 的已读位图兼容**（第一优先；引擎 C 侧容量未知。
     若越界崩溃，正文 id 段可自由重划——17220 以内的空洞号也可考虑，但须先确认空洞
     真未使用；卡消息 18000+卡号由 oCard.show 机制生成，不可移，除非弃用 oCard.show）
   - `oCard.show` 对三位数卡号的字符串算术（`18000+"201"` 隐式 tonumber）实测一次
   - 主菜单 12 项版面游戏内目测定稿（坐标全在 plan §2.1 表，±2px 调参）
   - encore 亮暗态裁半同位、`- 安可 -` 小注实机可读性
   - bgm_20_b/20_c 听曲确认（20_b 预期＝浜千鸟 arrange）
   - e2f 回想重放不受影响（若实施了 e2f 链入——见下"可选项"）
6. **可选项**：e2f-complete 链入（plan §3 方案 A，3 行）——主菜单直达为主案，
   通关自动播谢幕是否也要，问发起人一句再做。

## 硬纪律（不可越）

- **文字层零改动**：draft-finale-v2 的正文、七张卡面文案是定稿（多模型征集件，
  逐字有主）。演出实现可调（wait 帧数、图层细节），**文本一个字都不改**；
  确有必要改（如实测溢出）→ 报发起人裁决。已知待确认：17311 行"给给"疑衍字，
  发起人未回，保持原样入包。
- `vms` 消息编号语义（CLAUDE.md）：谢幕新 id 一经实测定稿就冻结。
- `snr_finale.lua` **绝不**调用 `comSectionStoryEnd`／写 `gameSave.storyRoute`
  （`"fin-10"` 不合 UID 解析约定，不进路线即安全——plan §2.3）。
- 谢幕卡不入 myCard/图鉴（1..195 表结构不动，设计如此，非遗漏）。
- 层号 198 已被 title_14_a 常驻占用——落地后在 CLAUDE.md 或台账记一笔。

## 验收标准

实机（或模拟器全程＋实机抽验）：持卡 144 的存档 → 主菜单出现 encore 项（暗/亮态
正确、光标可达）→ 进入谢幕章 → 场景 0–5 全程无卡死无花屏、七张卡面清晰、BGM/SE
按设计触发 → 回到主菜单 → 旧档兼容（无 144 的档菜单照旧、原版游戏可读改版档）。
完成后：分支合并、CLAUDE.md 增补谢幕章条目、台账留档。
