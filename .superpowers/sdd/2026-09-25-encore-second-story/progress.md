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
