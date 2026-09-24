### Task 3: 新曲 `bgm_fin_2` 编码进包

**Files:**
- Create: `layers/audio/bgm_fin_2.at3`
- Modify: `layers/manifest.toml`（`[[sound.tracks]]` 追加一条）

**Interfaces:**
- Consumes: `assets/audio/bgm_5_x_edit2.wav`（48 kHz 立体声 16 bit 3:16.60，−15.8 LUFS，无尾部静音；sha256 见 Global Constraints）；编码器 `build/atracdenc/build/src/atracdenc`
- Produces: SOUND.BIN 新成员 `bgm/bgm_fin_2.at3`，Lua 侧 `cPlayBGMWrap(cGetFileName("bgm", "bgm_fin_2"))`（Task 4）；`build/sound/work/bgm_fin_2.44k.wav`（Task 6 的 bgm_probe 参照）

- [ ] **Step 1: 确认前置**

Run: `ls build/atracdenc/build/src/atracdenc || bash tools/build_atracdenc.sh` 与 `shasum -a 256 assets/audio/bgm_5_x_edit2.wav`
Expected: 编码器存在；sha256 为 `ed9ae2e899cfbeb08e89f0f573e8178fe270c46a95b7d24fe85480b608941492`。

- [ ] **Step 2: 编码（整曲循环、起点 0、不裁尾、−21 LUFS）**

Run: `uv run python tools/at3p.py encode assets/audio/bgm_5_x_edit2.wav layers/audio/bgm_fin_2.at3 --loop-start 0 --lufs -21`
Expected: 打印增益约 −5.2 dB（源 −15.8 → −21）、smpl 循环 start=0、产物 sha256 一行；`build/sound/work/bgm_fin_2.44k.wav` 生成。

- [ ] **Step 3: 检视与对照**

Run: `uv run python tools/at3p.py inspect layers/audio/bgm_fin_2.at3` 与 `uv run python tools/at3p.py verify layers/audio/bgm_fin_2.at3 build/sound/work/bgm_fin_2.44k.wav`
Expected: inspect 通过固件规则（fmt ≥ 0x34、GUID、sr 44100、带 smpl）；verify 的包络互相关 ncc ≥ 0.9。

- [ ] **Step 4: 登记** `layers/manifest.toml` 在现有 `[[sound.tracks]]`（bgm_fin_1）之后追加

```toml
[[sound.tracks]]
member        = "bgm/bgm_fin_2.at3"          # cGetFileName("bgm", "bgm_fin_2")：谢幕第二段 fin-80『全屏窗口』
source        = "assets/audio/bgm_5_x_edit2.wav"  # 用户自供第二支 bgm_5_x remix（口哨配 8bit 鼓点，48 kHz 立体声 3:16.6），不入库
source_sha256 = "ed9ae2e899cfbeb08e89f0f573e8178fe270c46a95b7d24fe85480b608941492"
artifact      = "audio/bgm_fin_2.at3"        # layers/ 相对路径；发布字节的唯一真源，入库
sha256        = "<步骤 2 打印的产物 sha256，64 位十六进制>"
loop_start    = 0.0                          # 整曲循环——用户 2026-09-25 裁定不琢磨循环点
target_lufs   = -21.0                        # 源 −15.8 LUFS → 增益约 −5.2 dB；与 bgm_fin_1 同响度
```

（不写 `trim_end`：源无尾部静音，−50 dB 静音检测仅开头 0.42–0.78 s 一处凹陷。）

- [ ] **Step 5: 过闸**

Run: `uv run python tools/layers.py check --profile release`
Expected: `_check_sound` 通过（artifact 指纹＝清单 sha256、头部规则、不与原 99 成员撞名）。把 sha256 抄错会在这里报错。

- [ ] **Step 6: 提交**

```bash
git add layers/audio/bgm_fin_2.at3 layers/manifest.toml
git commit -m "data: 谢幕第二段 BGM bgm_fin_2 进包——用户第二支 bgm_5_x remix，整曲循环不裁尾，−21 LUFS

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

