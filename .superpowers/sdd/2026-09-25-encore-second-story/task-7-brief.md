### Task 7: 发布出盘与文档

**Files:**
- Modify: `CLAUDE.md`（谢幕章一节追加子条）
- Modify: `docs/ops/disc-pipeline.md`（id 段落一处）
- Modify: `docs/finale/draft-encore2-v0.md`（落地记录）
- 产物：`build/dist/game_zh.iso`、`build/dist/game_zh_ios.iso`

- [ ] **Step 1: 全量测试与过闸**

Run: `uv run pytest -q` 然后 `uv run python tools/layers.py check --profile release`
Expected: 全部 passed；check 零错误零告警。

- [ ] **Step 2: 出盘与开机链冒烟**

Run: `uv run python tools/build_disc.py` 然后 `uv run python tools/emu/drives/release_iso.py`
Expected：release 各道断言全过，`build/dist/game_zh.iso` 与 `game_zh_ios.iso` 同出（iOS 盘需要 `assets/fw/{libmp4,mp4msv}.dec.prx`，缺了会在开跑前失败——按 `docs/ops/movie-playback-ppsspp-2026-09-24.md` 补）；release_iso 三帧是原版开机链与初始形态标题，ERROR 0 或 1 条 ILLEGAL_THID。

- [ ] **Step 3: 文档**

3a. `CLAUDE.md` 谢幕章那一条（`- 谢幕章（encore，2026-09-02 本地化新增·编外）`）的末尾「取代为现行命令面，历史记录仍有效）。」之后追加一个同缩进的子段落：

```
    **第二个故事『远方的朋友』（2026-09-25，用户执笔）**：fin-60..90（还笔／储藏间／全屏窗口／模拟器）。
    读过第一个故事（`finaleReadFlag`）之后再点 encore，先出序章 s0f 同款『声』选择画面（`finChooseStory`：
    新成员 `event/eve_0_j` 提示「你的声音是——」、`eve_0_k` 脚注、`select/sel_fin1/2_sel_a_{on,off}` 光晕按钮，
    `tools/bake_finale_voice.py`），选二进第二个故事；旧系统数据缺键直入 fin-0。三位 AI 少女 CG
    `event/eve_47_{f,d,g}`（母本 eve_47_x＝彩野伏案改写『物語』；源 `docs/finale/assets/eve_47_*.src.png`，
    `bake_finale_event.py` 清单化），fin-80 依次同层溶解接替彩野的座位，画廊 eve_47 格四变体；纸箱特写复用
    `cutin/cut_62`（s5f_80 语法）；BGM `bgm/bgm_fin_2`（用户第二支 bgm_5_x remix，整曲循环不裁尾，−21 LUFS）；
    vms 17800–17999；读完不置旗标、不写系统数据。测试捷径 `build_disc.py --profile test --mode mainmenu --finale-read`，
    驾驶 `tools/emu/drives/finale_choice.py`。文稿与决定记录 `docs/finale/draft-encore2-v0.md`。
```

3b. `docs/ops/disc-pipeline.md` 第 163 行附近「谢幕章 17300–17481」改为「谢幕章 17300–17481、17600–17799、17800–17999」。

3c. `docs/finale/draft-encore2-v0.md` 首段引用块末尾追加一行（日期填实施当天）：

```
> **<YYYY-MM-DD> 已落地**：脚本 `layers/scripts/snr_finale.lua` 按本稿实施（finChooseStory + fin-60..90），六张选择画面图、
> 三张少女 CG、`bgm_fin_2` 进包；模拟器 `finale_scene.py`（fin-70/fin-80）、`finale_choice.py`（三跑）、`bgm_probe.py`
> 回绕、`save_roundtrip.py`（fin-80）全部通过；release 出盘断言全过。实施计划 `docs/superpowers/plans/2026-09-25-encore-second-story.md`。
```

- [ ] **Step 4: 提交**

```bash
git add CLAUDE.md docs/ops/disc-pipeline.md docs/finale/draft-encore2-v0.md
git commit -m "docs: 谢幕第二段『远方的朋友』落地——CLAUDE.md 增补、id 段落、工作稿落地记录

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
