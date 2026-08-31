# 反编译语料基座迁移（2026-08-31）

`lua_scripts/` 的来源从旧 pyluadec 产物换成 `~/pyluadec-refactor/corpus/final/`。
执行工具 `tools/migrate_base.py`（可重跑，缺省只演练）。上游迁移指南见
`~/pyluadec-refactor/docs/runbooks/zndnovel-naming-migration.md`。

## 为什么换：字节码保真度实测

`luac -s` 剥掉 debug 段，但**不剥** Proto 头的 `linedefined`/`lastlinedefined`
（记的是函数在源文件里的行号）。换基座后打印结构变了、行号自然不同，字节码却应当
一样。`tools/luac_norm.py` 把这两个字段归零后逐字节比对——这是本次迁移的判据：

| 基座 | 重编译后逐字节同一 | 长度同一 | **行号归零后同一** |
|---|---|---|---|
| 新 `corpus/final` | 1/229 | **229/229** | **229/229** |
| 旧 `lua_scripts`（迁移前） | 0/229 | 94/229 | **0/229** |

即：**新基座是原始游戏字节码的忠实还原，旧基座一个文件都还原不回去**。
复验命令：

```bash
for f in ~/pyluadec-refactor/corpus/final/*.lua; do
  ~/pyluadec-refactor/build/luac_sz4 -s -o /tmp/cmp/$(basename $f) $f; done
uv run python tools/luac_norm.py /tmp/cmp build/databin/script
```

两处旧基座失真的具体样本：

- `snr_s2_10_s`：`scene_s2s_190_sel_5` 与 `_11` 各被多输出一份（旧版把 if/else 两支
  各写一遍，新版用 `elseif` 合并）——这也是 extra 轨从 829 掉到 827 的全部原因。
- `snr_s4_10_s`：探索地图完成判定，旧版把多键合取塌缩成单寄存器比较 `if v63 == 2`
  （项目曾手工近似修补），新版原生还原出 `l1_2.class == 2 and l1_2.corridor == 3 and
  …` 的完整合取，两处 comSelectMap 都对。**旧的手工补丁不得回搬。**
- `snr_common` id=1：旧版丢失了字符串拼接（只剩 `v1`），新版还原出 `"■デバッグ：" .. msg`。

## 迁移处理的四类耦合

1. **行号不是稳定锚**。`data/ledger*.jsonl` 整体重生成；extra 轨 634 个 `文件:行号`
   键随之失效（另 195 个 `plotTitle:N` 与行号无关，不受影响）。
2. **译文重挂键**。实测 `(file, kind, jp) → zh` 唯一无冲突（791 组 0 冲突），故按内容
   分组、组内按出现顺序 1:1 配对搬迁。旧基座 2 条冗余键无新对应，直接丢弃——同组其它
   键携带同一译文，无译文损失。结果：`forward_extra.jsonl` 1019 → 1017 行，
   新 extra 覆盖 **827/827**。
3. **`literal=false` 的 8 行**（zh 存的是整个 lua 表达式而非字符串内容）：新基座局部名
   变了（`g4→k`、`i0→l1_3`、`v7→l1_8`），直接搬会引用到不存在的变量。7 条原样透传的
   直接改用新表达式；id=22 是真译文，按 token 对齐推导重命名后改写。6 条修订以
   `reason=review` 追加进 `patches.jsonl`（append-only，不动 forward.jsonl）。
4. **下游补丁重放**：`snr_common.lua` 的中文字体行（槽 0）自动重放；
   `snr_s4_10_s.lua` 的手工修复**不重放**（见上）。

`tr_line` 标记（新基座不带）由 `add_tr_line_markers()` 机械重生成，规则＝
「含非 ASCII 字符串字面量、非 vms 行、排除 snr_story_main/snr_common」。该规则先在
**旧基座上验证**：678/678 全中、0 漏标，只多标 2 行（`savedataTitle(…, "")` 那两处，
其第一参确实可译且在 extra 轨里有键，属旧基座漏标）。现为 164 文件 / 680 条。

## 验收结果

- `tools/build_ledger.py --check`：OK
- vms：16749 条，ID 集合与旧基座**完全一致**（键是消息 ID，存在于字节码常量里，不受
  基座影响）；译文覆盖 16749/16749
- extra：827 条，译文覆盖 827/827
- 全链路：`inject_lua` → `luac_sz4` → `build_disc` → PPSSPP 引导，绘本场景
  `s3fc-90` 正常渲染中文，ERROR 日志 0 条

## 方法学边界

本次证明的是「新基座 ⇒ 原始字节码」方向的严格等价。反方向——旧基座除字体补丁外是否
还藏有别的有意逻辑编辑——**无法由字节码比对断言**（旧基座 229/229 都有 code 数组差异，
寄存器层噪声会掩盖潜在的分支改写）。若要确认，须走 git 历史逐 commit 审阅
`lua_scripts/`。已知的两处（字体、s4 地图）都已按上文处理。
