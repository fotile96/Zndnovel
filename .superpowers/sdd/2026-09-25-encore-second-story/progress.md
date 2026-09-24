# SDD ledger — plan: docs/superpowers/plans/2026-09-25-encore-second-story.md

Spec: docs/finale/draft-encore2-v0.md
Executor: inline（superpowers:executing-plans），会话模型 Claude Opus 5.5，2026-09-25 起

Setup: Ruling: 直接在 main 上提交、不开 worktree — CLAUDE.md「分支（轻量制）」只对改写基座原件／大规模迁移／实验性重构强制开分支，本计划全部落在 layers/ 与 tools/；assets/（本机 gitignore 资产：orig.iso、源 wav、编码器输入）只在主工作树 — cost if wrong: 事后把本计划的 commit 挪到分支（git branch + reset），无数据风险。
Setup: Ruling: commit 署名用 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`，不照抄计划里的 Fable 5.1 — 计划沿用了撰写它的会话的模型名，本会话实际执行模型是 Opus 5.5（system 署名指引）— cost if wrong: commit 署名差一个模型名。
Setup: note — 工作树里有他人未提交改动（.claude/settings.json、data/api_ledger.jsonl、data/event_op_text.jsonl、pilot/read-edits/opus.draft.jsonl、tools/bake_event_op.py、docs/lyrics/opening-zh-draft.md），一律不碰，只按路径 git add。

Pre-flight:
| producer → consumer | produces | consumes | finding |
|---|---|---|---|
| T1 → T4 | build/finale_event/eve_47_{f,d,g}.png（既有 [gim].new `finale_event` 面拾取非 `_` 开头 PNG） | Lua `cGetFileName("event", "eve_47_f/_d/_g")` | 一致 |
| T2 → T4 | `finale_voice` 面 eve_0_{j,k}（模板 eve_0_i.gim）、`finale_select` 面 sel_fin{1,2}_sel_a_{on,off}（模板 sel_voice1_sel_a_on.gim） | Lua `"sel_fin1_sel_a"`（comDlgSelectItem 自动补 `_on/_off`，snr_common L1295/1297 已核）；T4 测试断言两面 tuple | 一致 |
| T3 → T4 | SOUND.BIN `bgm/bgm_fin_2.at3`；manifest `loop_start = 0.0`、无 `trim_end` | Lua `cGetFileName("bgm", "bgm_fin_2")`；T4 测试断言 loop_start／trim_end | 一致 |
| T3 → T6 | `build/sound/work/bgm_fin_2.44k.wav` | bgm_probe `BGM_REF` | T3 实跑时核路径 |
| T4 → T5/T6 | doScriptScene `fin-60..90` | testboot `--scene fin-70/80`（`scene_to_script` 的 `fin-` 前缀 → snr_finale，testboot L474 已核） | 一致 |
| T5 → T6 | `build_disc.py --profile test --mode mainmenu --finale-read` | finale_choice 前置 | 一致 |
| spec ↔ T4 | spec D7／§2：bgm_fin_2「fin-70 末白闪同一拍起播」，fin-70 末 `comEffectWhiteOut(120)` | 计划：BGM 在 fin-80 开头起，`comEffectWhiteOut(60)` | 冲突 → Ruling 如下 |

Pre-flight: Ruling: fin-70 末白闪按 spec 写 `cLoadPlaySE(se_102)` → `cPlayBGMWrap(bgm_fin_2)` → `comEffectWhiteOut(120)` → `wait(120)`；fin-80 开头的 `cPlayBGMWrap` 照计划保留（场景自给；cPlayBGMWrap 按 nowPlayBgmFileName 去重，snr_common 已核，顺读时是空操作不重启）— 起播点是用户点过头的落位（D7「同一拍起播」），WhiteOut(120)＋wait(120) 也与 fin-0 收尾同款；计划把起播挪到白场峰值、白场减半，没有记载理由 — cost if wrong: BGM 早约 2 s 起、白场长 1 s，改两行。

Task 1: Ruling: compose_ab 里 `im.convert("RGB")` 改为 `im.convert("RGBA").convert("RGB")`（加一行注释）— 新测试首次覆盖 bake()，模板 eve_74_x.png 是带 transparency 字节的 P 图，直转 RGB 触发 PIL UserWarning（旧 main() 同样触发，只是没人测）；两种转法 RGB 值相同，QA 图 _ab_eve_74_z_2x.png 前后 sha256 一致已核 — cost if wrong: 无（只影响 QA 图，且像素相同）。
Task 1: 目检 — 三位少女 MEDIANCUT MSE 14.12/13.29/12.70（均低于 eve_74_z 先例 15.37；鲸客人 sha256 01301d83… 前后一致、方法 MEDIANCUT 15.37 不变）；3× 放大看左下日照地板有轻微色阶（256 色不抖动的固有代价，与 eve_74_z 同法），人物发丝/尾鳍/眼罩 Z/笔与橡皮细节清楚、平涂面无噪点。
Task 1: complete (commits 2f6da56..f795323, tests: uv run pytest tests/test_bake_finale_event.py -q → 6 passed in 1.24s)

Task 2: Ruling: 脚注 eve_0_k 的擦字改用新 helper `ev._toned_patch(img, src, box, feather)`（bake_eve_0_h 加可选 `patch_src`，bake_finale_voice 传 eve_0_g），计划的 `_interpolate_bg(…, feather)` 照写、照测但只作缺省路径 — 计划做法实跑后两端竖缝消失，但右端（旧字「…できます。」所在）仍有一块淡平涂：竖向插值把背景斜向光带抹平，不满足计划自己的验收「两端不得有竖缝或浅色块」；实测 eve_0_h≈0.556·eve_0_g（框外逐通道线性拟合残差均值 0.6–0.9、p99 ≤4.6），用压暗后的 eve_0_g 重建框内，3× 对比度下也看不出补底框；新增单测 `test_toned_patch_rebuilds_a_dimmed_background_from_its_clean_source` 先红后绿；eve_0_h/eve_0_i 缺省产物与改前逐像素一致（getbbox None）— cost if wrong: 多 ~40 行代码；回退只需去掉 patch_src 参数。
Task 2: Ruling: bake_finale_voice 缺省输出目录走 `bake_out.out_dir(FACE)`（认 ZND_BUILD_TAG），不照计划写死 `REPO / "build"` — 同计划的 bake_finale_event 与其余烤字工具都走 out_dir，换字体评估时标签目录才能配套；无标签时路径与计划相同 — cost if wrong: 无（无标签时行为一致）。
Task 2: Ruling: 测试里两处 `Image.open(原图).convert("RGB")` 改为 `.convert("RGBA").convert("RGB")` — 原图是带 tRNS 的 P 图，直转触发 PIL UserWarning；RGB 值相同，断言强度不变 — cost if wrong: 无。
Task 2: Ruling: 计划「layers.py check 零错误零告警」按「exit 0、错误 0、且本计划消息（17800–17999）不产生告警」执行 — 基线在任何改动之前就有 32 条告警（hang-deep 31、narrow-glyph 1，全在既有正文 snr_crd_*/snr_s1_10_s），与本计划无关；后续每次过闸核对告警数仍为 32 且无 178xx/179xx 条目 — cost if wrong: 若用户要求清零既有告警，那是另一项工作。
Task 2: 目检 — eve_0_j「你的声音是——」居中（w=136）；六张拼成真实画面三帧（提示／选 1／选 2）：标题带「」、21 字标题墨迹在 8..472 内、副题居中；eve_0_k 脚注两端无竖缝无浅色块（4× 与 3× 对比度对照老烤法）。
Task 2: complete (commits f795323..e4a3347, tests: uv run pytest tests/test_bake_finale_voice.py tests/test_bake_finale_event.py -q → 12 passed in 1.61s)

Task 3: 编码 — at3p encode：增益 −5.2 dB（源 −15.8 LUFS、峰值 −3.9 dBFS → −21.0 LUFS、−9.1 dBFS，未限幅），loop_start 0、无 trim_end，196.63 s／4234 帧，产物 sha256 d34f0f61…bcaf；inspect ✓（ch=2 frame=744 S=0）；verify ncc 0.9988；prepared_wav＝build/sound/work/bgm_fin_2.44k.wav（T6 的 BGM_REF 路径与计划一致）。反证：清单 sha256 改错一位 → `[sound] … sha256 与清单不符`、check exit 1，已复原。check 告警仍为基线 32。
Task 3: complete (commits e4a3347..1ce719a, tests: uv run python tools/layers.py check --profile release →     snr_s1_10_s 7596: 多字节字符 ['×'] 在 17 px 字体里是窄字形（[10] px）：会挤在一起)

Task 4: Ruling: 守门测试的两条计数（`systemSave.finaleReadFlag = true`、`autoSystemSave(0)` 各 1 次）改为只数非注释行 — 计划原样写 `fin.count(...)`，但既有 main() 第 607 行注释里就含「autoSystemSave(0)」，照抄会在实现正确时误报 2 次 — cost if wrong: 无（注释行本就不执行）。
Task 4: Ruling: 守门测试另加一条断言钉住 Pre-flight 裁定：fin-70 体内 `cPlayBGMWrap(bgm_fin_2)` 出现在 `comEffectWhiteOut(120)` 之前 — 让 D7「白闪同一拍起播」有测试兜底 — cost if wrong: 改落位时顺手改这条断言。
Task 4: 实施 — Lua 由计划 Task 4 的 5 个代码块程序化提取装入（非手抄），116 条 vms 与工作稿 §3 逐字比对 0 差异、无需转义；fin-70 收尾按 Pre-flight 裁定；luac -p 通过。corpus 20 passed；check exit 0，消息 17211→17327，告警仍为基线 32、无 178xx/179xx；--show 17831 第 2 行「AI 助手账号一键登出了」」；17927/17888/17896 均 2 行无掰断。build_disc release lua,font,members：9 张新 gim 编码（无撞名/无对应成员报错），最大损耗 sel_fin2_sel_a_on MSE 11.72（阈 15）；字集重建含 U+0393/22A2/03C6（lxgw17 有字形）；pluto：snr_finale 24.7%（HEAD 版 21.4%；计划写的「现 18.1%」是旧口径），<35%。
Task 4: note — 说话人名「女学生（寓言家 饰）」等 158 px，为全库最宽（此前最宽 ≦红背心的少女≧ 136 px）；名牌层 192×22、从 x=5 画，放得下；名牌底图视觉宽度留待 Task 6 截图目检。
Task 4: complete (commits 1ce719a..e35d07f, tests: uv run pytest tests/test_layers_corpus.py -q → 20 passed in 2.16s)

Task 5: 实施如计划（3a–3d、build_disc CLI＋mode_opts）。RED：finale_read TypeError（缺省测试本即通过，属回归护栏）；GREEN：test_testboot＋test_build_disc 47 passed。21 条 pytest 告警全部来自 test_build_disc 的量化测试（build_disc.py 用了 Pillow 弃用的 getdata），既有、与本改动无关。
Task 5: complete (commits e35d07f..87b9dbb, tests: uv run pytest tests/test_testboot.py tests/test_build_disc.py -q → 47 passed, 21 warnings in 0.90s)

Task 6: Ruling: finale_choice.py 在计划脚本上加「系统数据备份/恢复」：备份放 OUT 之外的 build/emu/finale_choice_system_backup/（parse() 每次清空 OUT，title_logo 式放在 OUT 里的备份中途崩溃就丢），残留未恢复的备份时拒绝开跑；FIN_PICK=0 时先挪开 NPJH50279SYSTEM — 模拟器里那份 9-22 的系统数据**已带 finaleReadFlag = true**（fin-80 直入跑完回主菜单是中文题名 title_01_c，实证），不挪开则 PICK=0 会弹选择画面、验不了「无旗标直入 fin-0」；无系统数据时 runAutoLoad 只读不弹框，systemSave 取字面表缺省 false — cost if wrong: PICK=0 验的是「旗标 false」而非「缺键 nil」，两者都走 `== true` 为假的同一分支（nil 形态另由 corpus 的 nil 安全测试钉住）。
Task 6: Ruling: finale_choice.py 按钮帧前的等待 6.0 s → 7.5 s，c_pick 前两种选法都等 1 s — 实测 switchScreen 阻塞，按钮约 12 s 才出，6.0 s 时只有脚注（首跑 b_buttons 无按钮、下键靠运气生效）；PICK=1 首跑 c_pick 紧贴 b_buttons 截到旧帧缓冲（对话框循环无闪烁逻辑，且进 fin-0 反而晚一拍，证明对话框没提前关）— cost if wrong: 驾驶多等 2.5 s。
Task 6: Ruling: save_roundtrip 加 `--patched`（计划漏写）— test 剖面施加 savebuf 扩容层（savebuf.toml profile="test"），不加则按旧布局地址读 size 字段、判据失真；工具文档示例即 `--patched` — cost if wrong: 无。
Task 6: 结果 — (2) fin-70 直入 70 帧：通学路 bg_20_a_0 → 房间 bg_25_a_0 → 黑场 → 储物柜间 bg_18_a_0 → 纸箱特写 cut_62 → 回房间 → 白场 → 白入 eve_47_x；ERROR 1（ILLEGAL_THID）。p037 字呈黑底描边＝逐字显示刚开始（首次载入 se_102 读盘推迟了起显；PICK=1 after_02 拍到逐字中途：已显示白字、未显示部分黑底描边），非缺陷。(3) fin-80 直入 90 帧：彩野 → 寓言家 → 大肥鱼（男学生插话 CG 不撤）→ 牛来吹（小用户插嘴不撤）→ 溶回彩野 → 淡出 → fin-90 房间两句 → 主菜单，无纸箱残留；ERROR 2（均 ILLEGAL_THID）；名牌「女学生（寓言家 饰）」完整（名牌底带是整条横幅）、Γ⊢φ 正常。bgm_probe PASS：first_ncc 0.992、wrap 196.5 s（曲长 196.6）、wrap_ncc 0.955、full_pass 0.991、无 E[Atrac]。(4) pick2：a 提示、b 两按钮＋脚注且默认亮第一项（Review Focus #2 实证）、c 亮第二项、after 进 fin-60「……啧啧」；pick1：b/c 亮第一项、after 进 fin-0「…………卧槽」；pick0（无系统数据、日文题名）：a/b/c 全是 fin-0 黑屏文字、无选择画面。三跑 ERROR 各 1（ILLEGAL_THID）；系统数据 sha256 跑前跑后一致（ac3ab73c…）。(5) save_roundtrip fin-80（--no-cards，--patched）：saved_ok/resumed_ok/poison_ok 全 true，mainThread 65310 B（release 容量 327680 内），读档后 CG 与那句一起恢复。模拟器 SAVEDATA 两份（GAME00 a9ad1d6f…、SYSTEM ac3ab73c…）跑前整体备份到 build/emu/_savedata_backup_t6/，存档往返写过后已原样恢复并核 sha256。
Task 6: complete (commits 87b9dbb..73f8cec, tests: uv run pytest tests/test_layers_corpus.py tests/test_testboot.py -q → 34 passed in 2.74s)

Task 7: 全量 pytest 首跑 1 failed / 2040 passed：test_font_advances::test_committed_table_matches_the_built_font。根因：17927 的 Γ、φ 进字集后重建的 lxgw17.pgf 多了两个非缺省步进（9、10 px；⊢ 恰为 17 px 不入表），入库步进表 data/font_advances_17.json 未跟上——Task 4 的排版校验因此一直按 17 px 估这两字（偏保守）。按 CLAUDE.md 用 `pgf_inspect export-advances` 重生成（+Γ 9、+φ 10），font 测试转绿。
Task 7: Ruling: 步进表更正后窄字形规则对 17927 报「['Γ','φ'] 会挤在一起」，处理为收窄规则——字母类（unicodedata category L*：希腊/西里尔/带附加符号的拉丁）不报，只报窄符号/标点（× “” · …）；新增 `test_narrow_glyph_skips_letters_they_are_proportional_like_latin`（先红后绿，且钉住 Γ×φ 里的 × 照报）— 实拍 p051 里按比例宽排的「Γ⊢φ」读作一个紧凑公式，模拟撑成 17 px 格则散成「Γ ⊢ φ」；字母按比例宽与 ASCII 拉丁同理（é 等多字节拉丁同样会被旧规则误报），不改用户定稿文字；全库告警回到基线 32（narrow-glyph 仍只有 s1s 7596 的 ×）— cost if wrong: 将来正文若出现本该全宽的字母类字符（极少见）不再被此规则提示。
