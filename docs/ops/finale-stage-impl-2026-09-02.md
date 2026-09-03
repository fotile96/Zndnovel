# 谢幕章演出实施与模拟器验证台账（2026-09-02）

交接书 `docs/finale/handoff-stage-impl.md` 的执行记录。分支 `feat/finale-stage`，
共 6 个实施 commit（title_14_a 无小注定稿 → snr_finale 白入修正 → make_test_boot
fin- 支持 → build_disc 集成 → 主菜单 8 处 → 层 198 证伪回退）。
**模拟器全清单绿；待实机抽验后合并。**

## 发起人裁决（2026-09-01/02 本线落定）

1. **菜单小注：不要**。主菜单 12 项已定稿"只留英文大词"（裁定 E22），encore 同族
   处理；『- 安可 -』/『- 谢幕 -』A/B 作废，title_14_note.jsonl 删除。
2. **e2f 通关自动链入：不做**。主菜单直达为唯一入口，snr_e2_10_f 零改动
   （回想重放回归面随之消灭）。
3. 17311"给给"疑衍字维持原样入包（发起人未回，纪律照旧）。

## 落地形态

| 件 | 定案 |
|---|---|
| `snr_finale.lua` | canonical 源在 `docs/finale/`，**刻意不入 lua_scripts/**——build_ledger 会把中文正文当 jp 源收进账本，打破「缺译 0」闸。`build_disc.stage_lua` 编译进包＋源落 `build/inject_src`（发布闸逐字节核对与 make_test_boot 还原自动覆盖） |
| 新 gim 成员 | `build_disc` 新增 `NEW_GIM_SOURCES` 面：`build/finale_cards/`→`card/crd_201..207_a.gim`（模板 crd_1_a，212×148 index8/256，MSE 15.5–15.7 目检不可辨）、`build/finale_menu/`→`sysgim/title_14_a.gim`（模板 title_13_a，零损耗） |
| title_14_a | 117×68（=模板尺寸，gimcodec 回填钉死尺寸）、encore 双态字形移植、无小注；`tools/bake_finale_menu.py` 一键再生 |
| 主菜单 | 第 5 形态（startMenuState=2 ∧ 卡140 ∧ **卡144**）：12 项布局（story 104/fragment 131/section7 158/**finale 194,185**/library 212/option 241，27px 间距）；CIRCLE 分发 `doScriptScene="fin-10"; run(snr_finale)`；L845 硬编码 11 → `#l0_0.layerKeyCur`；共享循环 6 处 layerKey3→layerKeyCur。无 144 时 11 项原版面逐字保留 |
| vms id | 正文 **17300–17481**、卡消息 **18201–18207**（oCard.show 自动）。模拟器实测定稿，**自此冻结**（硬纪律） |
| 测试引导 | `make_test_boot.py` 支持 `--mode scene --scene fin-N` 直入谢幕任意场景 |

## 引擎实测新知（本轮代价换来的）

1. **层号 200 以下不能常驻**：`cInitGame→cInitLayer` 会清掉 <200 的层（原生常驻区
   201–255 幸存、行为反证清理边界在 200 附近）。plan §2.2 的"86–199 全库无人使用"
   实为"无人**能**用"——预载进 198 的图在进主菜单时已被清空。定案：encore 菜单图
   在 `l0_4` 卡 144 分支里**绘制期同步 layerLoad 直载工作层**（菜单每次进入重画，
   常驻无收益），snr_common 零触碰。
2. **DATA.BIN 新增成员完全可行**（本 handoff 头号验证项）：11 个新成员（7 卡+2 字体
   +1 lua+1 菜单图）按名排序位插入（`build_disc.stage_stage` bisect），script/card/
   sysgim 三个面引擎寻径、加载、渲染全部实测通过。
3. **BGM 不在 DATA.BIN**（manifest 无 bgm/ 前缀，在 SOUND.BIN），se/ 面只有 vag；
   谢幕引用的 bgm_19_x/20_b/20_c、loop_6 均为 s8f/e2f 同名曲，零打包工作。
4. oCard.show 的 `18000+"NNN"` 字符串算术对三位数卡号天然成立（原作 crd_133..200
   先例），18200 上邻接段安全。
5. 模拟器驱动纪律：文本推进键是 **CIRCLE**（日式确认位）；3 帧点按落在脚本 wait()
   窗口内会被整个错过（自动化按键要 ≥2.5s 间隔＋像素核验位置）；vram_screenshot
   会截到半合成帧（空帧/缺层帧是伪象，勿当 bug）。

## 验证矩阵（模拟器，PPSSPP master 软渲）

| 项 | 结果 |
|---|---|
| 新成员进包（script+card+sysgim） | ✓（fin-30 直入：17400 文本＋crd_201 卡面同屏） |
| vms 17300+/18201+ 显示与已读标记 | ✓ 全程零异常，通关后游戏功能正常（无内存踩踏迹象） |
| 12 项菜单版面/encore 亮暗态同位/光标可达 | ✓（plan 坐标原样定稿，未动 ±2px） |
| CIRCLE 进章 | ✓（两次独立实测） |
| library 子列展开/收合（12 项形态） | ✓ novel/memory/graphic/music 四项齐全（music 在列＝L845 修正生效证据） |
| 无 144 存档回归（11 项原版面） | ✓（144=-1 引导：无 encore、光标序正确、option 分发正常） |
| 全章 fin-0..50 跑通回主菜单 | ✓（马赛克带 p010–p180：递笔→天台→说书（旧卡 mini 快闪）→七卡→文化祭→蜻蜓 CG→长淡出→菜单） |
| 发布闸（无测试引导、script 逐字节=译文管线） | ✓ |
| 发布 ISO 引导（原版 IPL 全链） | ✓ 空档=形态 0 无 encore，新游戏可开 |

## 产物

- `build/dist/game_zh.iso` 642,512,896 B
  sha256 `fef0e66d6ac8c5607bf0abaa1f28a355bb702d4b9b01050463d5aa249132d1f6`
  （基线 assets/orig.iso 就地替换；DATA.BIN 9242 成员含 11 新增）
- 复现：`uv run python tools/bake_finale_cards.py && uv run python tools/bake_finale_menu.py
  && uv run python tools/build_disc.py --stage lua,gim,font,stage,pack,iso`

## 2026-09-03 复验：层化管线产出的盘（release / test 两剖面）

管线规范化（`docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md`）落地后，
`lua_scripts/` 已回到与原字节码等价的纯净基座，谢幕菜单入口、双字体行、测试引导
全部成了 `layers/` 下的层。新链路对迁移前手工改动的复现是逐字节的（脚本 230/230、
封包成员 0 差异），下面是游戏内的复验，驾驶脚本已收进 `tools/emu/drives/`（附 README）。

| 驾驭 | 引导对象 | 结果 |
|---|---|---|
| `menu.py` | test 盘（`--mode mainmenu`） | 12 项版面；encore 暗态→光标到位亮态；CIRCLE 进 fin-10，对白推进 |
| `library.py` | 同上 | library 子列 novel/memory/graphic/music 四项齐全，展开/收合正常（`#layerKeyCur` 修正生效） |
| `no_card144.py` | 同上，手改 `myCard[144].hold=-1` 后 `--stage members,stage,pack,disc` | 回到原版 11 项版面，无 encore；子列正常 |
| `finale_full.py` | test 盘 | 光标 5 步定位 encore；fin-10→50 五场画面依次出现，约 180 句处回主菜单，其后 CIRCLE 溢出进 Story（与 09-02 首跑形态相同） |
| `glyph.py` | test 盘（`--mode scene --scene fin-10`） | 09-02 曾缺的字形已渲染：p05「啥」、p11「颁…奖」；IPL 已剥，ERROR 0 |
| `release_iso.py` | `build/dist/game_zh.iso` 本体 | 原版 IPL 开机链；标题为初始三项 Prologue/load/option（flag 未预开）；序章题词中文烤图正常 |

- ERROR 日志：除 glyph 为 0 外，其余各 1 条 `ILLEGAL_THID=sceKernelWaitThreadEnd(0)`，
  与 08-31/09-01 记录的原盘同源 HLE 噪声一致。
- **剖面隔离实证**：三次 test 剖面构建期间 `build/dist/game_zh.iso` 未被触碰
  （sha256 `f5c5f1c5ad01…` 前后一致，与 09-02 热修后 ISO 相同）；本轮 `--stage iso`
  重新产出的 ISO 与之逐字节相同。发布断言通过：stage 树指纹与 DATA.BIN 对应同一次
  pack、成员集合恰为基座 + 11 声明新增、脚本与独立重编译产物逐字节相同、无测试引导成员。
- 与旧流程的差别：menu/library/no_card144/finale_full 四个驾驭**只能跑在 test 剖面**——
  它们依赖全解锁存档，而 release 盘干净无探针、开机即初始菜单；release 盘由 `release_iso.py`
  走原版开机链验证。旧流程靠往共用的 `build/game` 打补丁做到这点，正是本次改造要拆掉的耦合。
- `snr_finale.lua` 的 canonical 源已自 `docs/finale/` 移至 `layers/scripts/snr_finale.lua`
  （下文待办第 5 条的路径以此为准）。

## 待办（实机，发起人）

1. CFW 实机引导 game_zh.iso：持卡 144 档（可先模拟器通 e2f 或用调试菜单）→ 主菜单
   encore 出现/暗亮态/可达 → 全章跑通回菜单。
2. **bgm_20_b/20_c 听曲确认**（20_b 预期＝浜千鸟 arrange，模拟器无法代听）。
3. 版面实机目测终审（±2px 调参窗口仍在，坐标集中在 snr_mainmenu 卡 144 分支一处）。
4. 旧档兼容抽验（改版档回原版可读）。
5. 通过后：分支合并、CLAUDE.md 已随分支更新、eve_74_z 到货后换 fin-40 占位行
   （`docs/finale/snr_finale.lua` TODO 注释处）＋顺评 `snr_graphic` cgNumber[8][7][2] 注册。
