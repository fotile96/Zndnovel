# 整分支评审后单次 fix 波 —— 执行报告

日期：2026-09-03　分支：`feat/finale-stage`　提交：`9939b1d`

范围：整分支评审（Ready to merge: With fixes，0 Critical / 4 Important / 12 Minor）
点出的 4 条 Important，加同批次并入的 Minor 散文漂移（评审 triage 明确列为「同
属删了代码没改调用方注释这一反复模式」的几处）。评审记录见
`.superpowers/sdd/2026-09-02-disc-layers-pipeline/progress.md` 尾部三条 Ruling
（本报告未改动该文件——它已由评审过程写好，不属于本次改动范围）。

---

## Must-fix 1 —— tests/test_build_disc.py 两个 local_assets 测试补 DIST/ORIG_ISO monkeypatch

**问题**：`test_stage_iso_catches_data_bin_packed_from_a_different_stage_tree` 与
`test_stage_iso_catches_members_compiled_from_stale_lua_final` 只 `monkeypatch.setattr(bd, "BASE", mini)`，
`bd.DIST`（`build/dist/`）与 `bd.ORIG_ISO`（`assets/orig.iso`）仍指向本机真实路径。
今天 `stage_iso` 在指纹核对处提前 `SystemExit`，测试摸不到发布代码；一旦那道守卫
回归，测试会真的把 9 字节玩具包 splice 进真实 ISO 的拷贝写到
`build/dist/game_zh.iso`，销毁发布产物——而这本该是"保护"发布产物的测试。

**改动**：两个测试各加
```python
monkeypatch.setattr(bd, "DIST", tmp_path / "dist")
monkeypatch.setattr(bd, "ORIG_ISO", tmp_path / "nonexistent.iso")
```
（各带一行注释说明理由），与已有的第三个 sibling 测试（`test_stage_pack_does_not_publish_to_dist`
附近那条完整重定向的写法）看齐。

**覆盖测试**：
- `tests/test_build_disc.py::test_stage_iso_catches_data_bin_packed_from_a_different_stage_tree`
- `tests/test_build_disc.py::test_stage_iso_catches_members_compiled_from_stale_lua_final`
（两条都带 `local_assets` 标记，需真 `luac_sz4`，本机存在，跑真断言逻辑，非 skip）

```
$ uv run pytest tests/test_build_disc.py -k "stage_iso_catches" -q
..                                                                       [100%]
2 passed in 0.11s
```

---

## Must-fix 2 —— tools/layers.py::check_ids 补扫叠加层

**问题**：设计 §6.3 要求叠加层 `with`/`text` 字段里的 id 与脚本文本同等对待，但
`check_ids` 只遍历 `manifest["scripts"]`，叠加层引入的 `vms(`/`msg(` 调用完全不检查
——评审构造了一个插 `vms(1, ...)` 的 release 叠加层，`check` 照样放行。

**改动**（`tools/layers.py`）：
- `check_ids` 在脚本循环之后新增叠加层循环：对 `manifest["overlays"]["order"]` 里
  每个层，`load_overlay` 读入，把每个 `op` 的 `with`/`text` 字段拼成一段 blob；
  `collect_ids(blob)` 为空则跳过（不含 id 的层无需登记）；否则用
  `owner = f"overlays/{name}.toml"` 走 `_check_ids_of`，与脚本文本走同一套
  两两不交 / 撞账本 / 全局唯一判定。
- 更新了 `check_ids` 的 docstring，明确两类来源与登记规则。

**为什么对现有四层是 no-op**：`fonts.toml`（改 `fontLoad` 路径字符串）、
`encore-menu.toml`（改布局表与 CIRCLE 分发，text/with 里全是 Lua 结构代码，无
`vms(`/`msg(` 调用）、`strip-ipl.toml`（`delete_span`，无 with/text）、
`boot-handoff.toml`（`replace` 的 with 是 `run(...)` 调用，非 vms/msg）——四层
`with`/`text` 字段里都没有一处 `vms(`/`msg(` 数字调用，`collect_ids` 全部返回空集，
新增的扫描分支对它们直接 `continue`，不触发任何登记要求。

**验证是 no-op**：
```
$ uv run python tools/layers.py check --profile release
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 全部层命中 ✓
$ uv run python tools/layers.py check --profile test
[layers] test: 施加 4 层（fonts, encore-menu, strip-ipl, boot-handoff），新增成员 1
[layers] 全部层命中 ✓
```
两条命令改动前后行为逐字相同（施加层数、新增成员数、"全部层命中"均未变）。

**Must-fix 2 明确要求的证据 —— 新检查拒绝未登记叠加层 id、放行真实四层**：
就地 monkeypatch `load_overlay`，往 `strip-ipl.toml` 的 ops 里追加一条含
`vms(1, ...)` 的操作（只在内存里，不改任何磁盘文件），再跑一遍真实 `check_ids`：
```
$ uv run python -c "
from tools.layers import load_manifest, check_ids, LAYERS
import tools.layers as L

man = load_manifest()
orig = L.load_overlay
def poisoned(path):
    ov = orig(path)
    if path.name == 'strip-ipl.toml':
        ov = dict(ov)
        ov['ops'] = list(ov['ops']) + [
            {'op': 'insert_after', 'anchor': 'x', 'text': 'vms(1, \"NONVOICE\", \"poison\")\n'}]
    return ov
L.load_overlay = poisoned
try:
    check_ids(man, LAYERS, ledger_ids=set())
    print('UNEXPECTED: not caught')
except SystemExit as e:
    print('EXPECTED FAILURE:', e)
finally:
    L.load_overlay = orig

check_ids(man, LAYERS, ledger_ids=set())
print('real four overlays: check_ids passed (no-op confirmed)')
"
EXPECTED FAILURE: overlays/strip-ipl.toml 没有在 layers/vms_ids.toml 登记 id 区段

real four overlays: check_ids passed (no-op confirmed)
```
（这是复现评审自己的故障注入手法：评审报告称"插入 `vms(1, ...)` 的 release 叠加层
通过检查"——上面证明同样的注入现在会被 `check_ids` 硬失败拒绝，而真实四层不受影响。）

**新增单元测试**（`tests/test_layers.py`，基于既有 `_mk_layers` 夹具）：
- `test_check_ids_rejects_unregistered_id_inside_overlay_text` —— 叠加层
  `insert_before` 的 `text` 里塞 `vms(500, ...)`，没登记 `overlays/alpha.toml`，
  拒绝且报错文本点名该 owner。
- `test_check_ids_rejects_overlay_id_colliding_with_ledger` —— 登记了区段
  `[100,200]`，`with` 里 `vms(150, ...)` 落在段内但与账本冲突（`ledger_ids={150}`），
  拒绝。
- `test_check_ids_accepts_registered_in_range_overlay_id` —— 登记了区段，
  `text` 里 `vms(150, ...)` 落在段内、不撞账本，放行。
- `test_check_ids_overlay_without_ids_needs_no_registry_entry` —— 默认
  `ALPHA_OVERLAY`（`find="a"`/`with="b"`，无 id）不登记也放行，对照现行四层的实况。

```
$ uv run pytest tests/test_layers.py -k check_ids -q
............                                                             [100%]
12 passed in 0.04s
```

**文档**：`docs/ops/disc-pipeline.md` 原 125-131 行左右「⚠ 现状缺口」段落改写为
正面说明——`check_ids` 现在同时扫描脚本与叠加层，登记键
`f"overlays/{层名}.toml"`，不含 id 的层无需登记；仍建议给引入新 id 的层补一条
真语料测试，但拦截本身不再依赖它。「故障排查」一节的"id 撞号"条目同步去掉了
对"上文第 3 步缺口"的引用（那条缺口已不存在），并把"没有登记 id 区段"加入
错误文本枚举。

---

## Must-fix 3 —— tools/build_disc.py::stage_members 烤字面缺失静默跳过

**问题**：`[gim].replace`/`[gim].new` 两处循环，`build/<face>/` 目录不存在时只
`log(...跳过整面)` 并继续；`release_assertions` 看不到这个缺失——它比对的是
`new_members.json`，而这份记录正是在"跳过整面"之后才写出的，缺失成员根本不会
进入期望集合。缺整面烤字（例如卡面全没烤）的 release 盘能一路通过全部发布闸。

**改动**（`tools/build_disc.py`）：抽出 `_require_bake_face(ctx, root, src_dir) -> bool`：
- `root.is_dir()` 为真：返回 `False`（正常处理该面）。
- release 剖面缺失：`die()`，消息点名 `<src_dir>/`、指引去候选 `tools/bake_*.py`
  源码里搜 `out_dir("<src_dir>")` 定位具体脚本，并显式写明"release 剖面"。
  `die()` 内部 `sys.exit`，函数不会返回到调用方的 `continue`。
- test 剖面缺失：`log()` 告警（消息含"test 剖面"字样）+ 返回 `True`，调用方
  `continue` 跳过整面——保留局部走查的合法性。

两处循环体分别改成 `if _require_bake_face(ctx, root, src_dir): continue`。

**为什么用抽出的辅助函数做单测，而不是跑真实 `stage_members`**：`stage_members`
依赖真实 `build/databin`、真实 `lua/final` 编译产物（需要 `luac_sz4`）与真实烤字
输出目录结构，是本仓库既有测试里 `local_assets` 标记的范畴（走真实资产才有意义）。
决策点本身——"目录缺失时 release 该死、test 该告警跳过"——与那些真实资产无关，
纯粹是 `ctx.profile` 分支逻辑，抽出后可以完全不碰磁盘上的真实产物做单测，覆盖
"该函数被抽出来之后，构造 tmp_path 下一个确定不存在的目录、两种 profile 分别验证行为"
这条不变量，比等一整条 `stage_members` 流水线更聚焦、更快。

**覆盖测试**（`tests/test_build_disc.py`，新增 3 条，均不依赖真实资产/luac）：
- `test_require_bake_face_dies_on_release_when_face_dir_missing` —— release
  剖面 + 不存在的目录 → `SystemExit`，消息含 `card_zh` 与 `release`。
- `test_require_bake_face_logs_and_skips_on_test_profile` —— test 剖面 + 同样
  缺失的目录 → 返回 `True`，`capsys` 捕获的日志含 `card_zh` 与 `test`。
- `test_require_bake_face_returns_false_when_dir_exists` —— 目录存在时两个
  剖面都返回 `False`（正面对照）。

```
$ uv run pytest tests/test_build_disc.py -k require_bake_face -q
...                                                                      [100%]
3 passed in 0.65s (含全套 tests/test_build_disc.py -q 一并跑通，见下方总表)
```

**文档**：`docs/ops/disc-pipeline.md`：
- 新增闸表格行「烤字面完整性（`_require_bake_face`）| `members` 阶段 | release
  剖面下 face 目录整个不存在——硬失败……」。
- 原 189-195 行左右「成员集合不符」条目拆成两条：
  一条保留「封包树有未声明的成员」（与本次改动无关，原样保留）；
  另一条新写「烤字面整个缺失」，订正掉旧文档"到 iso 阶段发布断言才被追认为
  『缺声明的成员』"这个不存在的旧行为描述，改为准确描述——`members` 阶段的
  `_require_bake_face` 直接 `die()`，走不到 `iso` 阶段；test 剖面仍允许局部缺失。

---

## Must-fix 4 —— tools/migrate_base.py:16 docstring 反向指令

**问题**：模块 docstring「必须处理的耦合」第 3 条仍写「snr_common.lua 的中文
字体行（fontLoad 槽 0）要在新基座上重打」——`FONT_PATCH` 常量与相关重放逻辑
已在本分支删除，字体两槽的改写权已完整移交 `layers/overlays/fonts.toml`；照
旧文档字面操作会把已迁移出的纯净基座重新弄脏。

**改动**：重写该条为「下游补丁不重放」——明确 `FONT_PATCH` 已删、两槽只有
`layers/overlays/fonts.toml` 这一个改写来源、在构建期而非迁移期施加、基座
永远保持迁移出的原始文本；并说明若手滑把字体行直接改进 `lua_scripts/`，
`--check` 会因为该文件与"语料 + tr_line 标记"不再逐字节相同而报"基座不纯净"
失败（真实断言路径，非空话——见下方 `migrate_base.py --check` 通过记录，
以及第 176-182 行 `--check` 的实现：逐文件 `add_tr_line_markers` 重生成后
与 `lua_scripts/` 原样比对）。

```
$ uv run python tools/migrate_base.py --check
[migrate] 新基座 229 文件 / 现有 229 文件
[migrate] 基座纯净 ✓（229 文件 == 语料 + tr_line 标记）
```

---

## 散文漂移（同批次收口）

| 位置 | 旧描述 | 新描述 |
|---|---|---|
| `tools/layers.py` `_injected_sources` docstring（~473-495） | "刻意不叠 `FONT_SLOT1_FROM/TO`" —— 把已删除的代码当作活代码在描述"故意绕开" | 改述真实不变量：`inject_tree()` 不触碰任何一条 `fontLoad` 行（槽 0、槽 1 皆不碰），两槽改写权完整属于 `fonts.toml`；若 inject_tree 改过其中一行，fonts 层锚点会命中 0 次、count 断言硬失败 |
| `tests/test_layers_corpus.py`（~105-126） | 测试名 `test_injected_sources_translates_and_skips_old_font_patch`，docstring 同样描述"刻意不重放槽 1 补丁" | 改名为 `test_injected_sources_translates_and_leaves_font_lines_untouched`；docstring 同步改述；断言从只查槽 1 一行扩到槽 0、槽 1 两行都完整保留在注入结果里 |
| `tools/emu/playthrough.py`（~9-10） | 用法示例 `--disc build/game` / `build/game_orig` | 改成 `--disc build/release/game`（对应 `--out build/emu/release`）与 `--disc build/test/game`（对应 `--out build/emu/test`），与剖面拆分后的真实产物路径一致（`build_disc.py::stage_disc` 写 `ctx.root / "game"`，`ctx.root` = `build/<profile>`） |
| `tools/emu/drives/release_iso.py` 第 5 行 docstring | "00 帧在 IPL/告知屏" | 订正为：`wait_game` 的 35 秒静置已经放过完整 IPL 四屏与告知，00 帧落地时已是标题画面；顺带说明文件名 `00_ipl.png` 是历史遗留、与实况不符（未改文件名，只订正文档） |
| `tools/layers.py`（~545-546，`_compare_compiled` docstring 里对 `build_final_sources` 的引用） | "见该函数第 441-442 行" —— 会随文件改动漂移 | 改成直接引用条件文本本身：`if spec.get("profile", "release") == "test" and profile != "test": continue`，不再依赖行号 |

---

## 验证总表

```
$ uv run pytest tests/test_layers.py tests/test_layers_corpus.py tests/test_build_disc.py -q
........................................................................ [ 94%]
....                                                                     [100%]
76 passed in 1.51s

$ uv run pytest -q -m "not emu"
........................................................................ [  4%]
...(省略中间进度行)...
1773 passed, 3 skipped, 6 deselected in 305.89s (0:05:05)

$ uv run python tools/layers.py check --profile release
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 全部层命中 ✓          # exit 0

$ uv run python tools/layers.py check --profile test
[layers] test: 施加 4 层（fonts, encore-menu, strip-ipl, boot-handoff），新增成员 1
[layers] 全部层命中 ✓          # exit 0

$ uv run python tools/layers.py check --profile release --compare-compiled /tmp/layers_baseline/script
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 逐字节比对：230/230 相同          # exit 0；未覆盖/未修改 /tmp/layers_baseline/

$ uv run python tools/migrate_base.py --check
[migrate] 新基座 229 文件 / 现有 229 文件
[migrate] 基座纯净 ✓（229 文件 == 语料 + tr_line 标记）          # exit 0
```

## 改动文件清单（本次 commit `9939b1d` 携带的全部 9 个文件）

- `docs/ops/disc-pipeline.md`
- `tests/test_build_disc.py`
- `tests/test_layers.py`
- `tests/test_layers_corpus.py`
- `tools/build_disc.py`
- `tools/emu/drives/release_iso.py`
- `tools/emu/playthrough.py`
- `tools/layers.py`
- `tools/migrate_base.py`

未 stage、未提交（按任务要求排除，均为进入本任务前已存在的未提交改动，非本次
产生）：`.claude/settings.json`、`data/api_ledger.jsonl`、`data/event_op_text.jsonl`、
`pilot/read-edits/opus.draft.jsonl`、`tools/bake_event_op.py`。另有
`.superpowers/sdd/2026-09-02-disc-layers-pipeline/progress.md` 本次会话中也
处于已修改状态（评审记录，非本次改动写入），同样未被本次 commit 触碰。

## 关注点 / 后续

- `_require_bake_face` 里"先跑生成该目录的 tools/bake_*.py"这句指引没有给出
  精确的 `src_dir → 具体脚本` 一一映射（例如 `sysgim` 面同时有
  `bake_sysgim_outline.py`/`bake_sysgim_glow.py` 两个候选写入同一 `out_dir("sysgim")`，
  哪个是"现役"取决于当次调用哪个脚本，不是静态可从文件名推出的 1:1 关系）；
  消息改成指引"在候选脚本源码里搜 `out_dir("<face>")`"而非断言唯一脚本名，
  避免给出可能错误的具体工具名。这是刻意的保守选择，不是遗漏。
- 评审 triage 明确标为"不进本波、留作 follow-up"的项（去重四组重复助手、
  `_OP_KEYS` 校验、字体成员名交叉校验、gim 缓存测试、provenance 兜底改
  unknown 等，以及 spec 本身的四条意见）未处理，按评审与本任务范围保持一致，
  留在 `progress.md` 台账供下次会话直接开工。
