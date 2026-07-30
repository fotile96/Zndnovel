# Hotfix A: build_ledger.py 函数归属改为嵌套栈追踪

## 背景与缺陷

`tools/build_ledger.py` 的 `parse_vms_lines` 用平面方式追踪"当前函数"：遇到 `X = function` 行就把 `func` 切换为 X，**函数结束时不回弹**。而语料的普遍结构是：

```lua
scene_s1s_10 = function(scene_id, scene_title)
    local v0, v1, v2
    v0 = function()          -- 内层闭包（可能为空、也可能装内容）
    end
    comSectionNonLabelBegin(scene_id, scene_title)
    vms(7296, "NONVOICE", "…")   -- ← 属于 scene_s1s_10，却被归给 v0
    ...
    v0()
end
```

后果：`data/ledger.jsonl` 中大量行 `func` 错误地记为 `v0` 等裸 vN 名（snr_s1_10_s 有 1234/1433 行；全库主要章节文件均受累）。下游 `tools/gen_timeline.py` 的 `_ids_for` 按 `(file, func)` 联结 dag.json 的 play/subcall 函数名（如 `scene_s1s_10`），联结为空，时间轴单元拿不到 vms id。

## 修复规格

只改 `tools/build_ledger.py` 的函数归属逻辑（`parse_vms_lines`），其余解析（VMS_RE/TR_LINE_RE/parse_extra/classify）不动。

**嵌套追踪**：维护一个栈，元素 `(name, indent)`：
- 行匹配 `FUNC_RE`（保持现有正则不变）时，push `(名字, 该行前导空白长度)`。
- 行匹配 `^(\s*)end\b` 且栈非空且 `len(前导空白) == 栈顶.indent` 时，pop。（反编译输出缩进机器级规整：函数定义行与其收束 `end` 同缩进；函数体内其他 `if/for/while` 块的 `end` 缩进严格更深，不会误弹。栈空时遇到 `end` 是文件级块，忽略。）

**归属规则**（vms 行的 `func` 字段）：从栈顶（最内层）向外找第一个**不匹配** `^v\d+$` 的名字；若全部匹配（全是裸 vN），取最外层名字；栈空则 `""`（维持现状）。注意 `v0.mesNot` 这类带点的名字不匹配 `^v\d+$`，按自身名字归属（snr_common 现有 v0.mesNot/v0.mesNG 等归属必须保持不变）。

## 测试（TDD，扩展 tests/ 下 P1a 已有的 build_ledger 测试文件；若无则新建 tests/test_build_ledger_func.py）

先写失败用例再修：

1. **父体回弹**：fixture 含上面的 `scene_x → v0 = function/end → vms` 结构，断言 vms 归 `scene_x`（当前实现会给 `v0`，测试先红）。
2. **闭包内 vms 穿透**：vms 在 `v0 = function()` 体内 → 仍归 `scene_x`（最近非裸 vN 祖先）。
3. **带点名字保留**：`v0.mesNot = function` 体内 vms → 归 `v0.mesNot`。
4. **弹栈后顶层复位**：函数 `end` 之后、下一个函数之前的顶层 vms → `func == ""`。

## 数据再生成与全库回归断言（写成一次性校验脚本跑给报告看，或并入测试）

1. `uv run python tools/build_ledger.py` 再生成 `data/ledger.jsonl` 与 `data/ledger_extra.jsonl`。
2. 与修复前（git HEAD 版本）逐行对比：
   - 行数不变（16750）、id 集合不变、每行 `jp/voice/file/literal/chapter` 字段逐字节不变——**只允许 `func`（及其牵连的 `kind`）变化**。
   - `kind` 分布预期**零变化**（NARRATIVE_FUNC_EXCEPTIONS 两函数无内闭包、AMBIENT_FUNC_EXCEPTIONS 为空、SYS_FILES 判定不依赖 func）。断言各 `(file, kind)` 计数与修复前完全一致；若有差异，停下来在报告里逐条列出，不要硬改。
   - `ledger_extra.jsonl` 字节级不变。
3. 修复后全库不应再有裸 vN 归属：`func` 匹配 `^v\d+$` 的行数应为 0；若非 0，逐个调查并在报告列明（不要为凑 0 而改规则）。
4. 确定性：连续跑两次 build，两次输出文件字节级相同。
5. 下游冒烟（Task 2 的验收补跑）：

```bash
uv run python - <<'EOF'
import json, sys; sys.path.insert(0, ".")
from tools.pipelib import read_jsonl
from tools.gen_timeline import Expander
dag = json.load(open("data/dag.json", encoding="utf-8"))
ex = Expander(dag, read_jsonl("data/ledger.jsonl"), {})
ex.story("s1s_10", choices={}, until="s1s_20")
units = [u for u in ex.timeline if u["type"] == "unit"]
assert [u["state"] for u in units] == ["s1s_10", "s1s_20"], units
assert all(u["ids"] for u in units), "s1s_10/20 都应有 vms 行"
print("smoke OK:", [(u["state"], len(u["ids"])) for u in units])
EOF
```

## 提交

工具修复 + 测试 + 数据再生成放一个 commit（同一逻辑变更）：

```bash
git add tools/build_ledger.py tests/ data/ledger.jsonl
git commit -m "fix: ledger 函数归属改为嵌套栈追踪，vms 回归所属场景函数"
```

（若 ledger_extra.jsonl 字节不变则无需 add。）
