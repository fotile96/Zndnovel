# Task 1 Report: dag.json 生成器

## 实现了什么

创建了结构化剧情图生成器，将Lua剧本的dispatcher解析成JSON格式的DAG数据结构：

1. **tools/build_dag.py** - 核心解析器
   - `parse_states(stem, text)` - 解析main()函数中的场景分支，提取play、goto、choice、run等事件
   - `parse_scene_meta(stem, text)` - 解析场景函数体，提取cost/gets/shows/gameover/complete元数据
   - `parse_crds(script_dir)` - 解析卡牌数据（crd），提取stub/req/answers/runs
   - `main()` - CLI入口，读取所有lua脚本文件，生成data/dag.json

2. **数据结构**
   - `states[sceneId]` - 场景节点及其事件序列
   - `scene_meta[func]` - 场景元数据
   - `crds[cid]` - 卡牌数据

## 测了什么与结果

### TDD证据

**RED - Step 2**
```
uv run pytest tests/test_build_dag.py -v
# 输出：
ERROR collecting tests/test_build_dag.py
E   ModuleNotFoundError: No module named 'tools.build_dag'
```

**GREEN - Step 4**  
```
uv run pytest tests/test_build_dag.py -v
# 输出：
tests/test_build_dag.py::test_states_capture_flow_in_order PASSED        [ 33%]
tests/test_build_dag.py::test_states_capture_gate_choice_run_subcall PASSED [ 66%]
tests/test_build_dag.py::test_scene_meta_costs_and_gets PASSED           [100%]
======================== 3 passed in 0.01s =========================
```

### Step 5 - 真实数据验证

**数据生成结果**
```
uv run python tools/build_dag.py
states=405 scene_meta=527 crds=196
```

**抽查验证通过**
- ✓ "s1s_20" 场景存在，title以"夏の朝"开头
- ✓ crds["2"]["req"] == [1]
- ✓ crds["30"]["runs"] == ["snr_s1_10_f"]
- ✓ {"card_gate": 133, "held": True} 在 s1s_40 序列中

**确定性检查**
```
uv run python tools/build_dag.py && git diff --stat data/dag.json
# 无输出 = 无变化 = 确定性验证通过
```

**全量回归测试**
```
uv run pytest -q
======================== 32 passed in 1.07s =========================
```

## 改动文件

- **tools/build_dag.py** (新建) - 核心解析器实现，194行
- **tests/test_build_dag.py** (新建) - 单元测试，3个测试用例
- **data/dag.json** (新建) - 生成的DAG数据，405个场景，527个元数据条目，196张卡牌

## 自审发现

### 修正的问题

在按照brief提供的实现编写后，发现parse_scene_meta在处理test fixture时失败，原因是：
- Test fixture使用`'''\`（反斜杠转义换行），导致字符串以"scene_x_20"开头，无前导换行
- 正则表达式`r'\n(scene_[\w]+) = function'`期望前导换行，导致首个scene不匹配

**修正方案**：在parse_scene_meta中对text预处理，添加前导换行：
```python
parts = re.split(r'\n(scene_[\w]+) = function', '\n' + text)  # 而非直接用text
```

这样处理：
- 不改变真实lua文件的解析逻辑（lua文件中scene定义前自然有换行）
- 支持test fixture这种简化的格式
- 简洁安全，无副作用

### 代码质量

✓ 遵循brief提供的接口签名和正则规则  
✓ 关键正则规则与extract_dag.py一致  
✓ 没有过度设计（YAGNI原则）  
✓ 变量名清晰（pend_choice、ev等）  
✓ 三层数据结构对应三类lua元素  

## 疑虑

无。实现符合需求，测试全通过，真实数据验证通过，确定性检查通过。

---

## 质量评审修复 (Round 1)

### 问题诊断

协调员发现 pend_choice 追踪存在陈旧问题：
- pend_choice 仅在新状态边界清零，被 goto 消费后不清零
- while 循环内的 if 块不清零 pend_choice
- 导致内部游戏逻辑的 if 条件（如 v51, v62）被误标为 choice

实证：data/dag.json 的 s2s_190_sel 中，嵌套谜题子流程复用 v51/v60/v61/v62，
产生 {"choice": 0, "goto": ...} 等无效标记（choice:0 不可能是真实 UI 选择）。

### 修复方案

1. **新增 SEL_ASSIGN_RE** 识别 `vNN = comDlgSelectItem(` 语句
2. **分两轮扫描**：
   - 第一轮：收集每个状态的 choice 变量（排除 while 循环内的变量）
   - 第二轮：仅当变量属于该状态 choice_vars 集合时才武装 pend_choice
3. **立即清零** pend_choice：被 goto 消费后直接设为 None
4. **排除内部变量**：while 循环内的 comDlgSelectItem 赋值被视为内部游戏逻辑，不算 choice 变量

### 覆盖测试

新增 4 个测试用例：

```bash
# 单元测试
test_internal_if_blocks_not_marked_choice
  验证内部变量 if 块（v51, v62 等）不生成 choice 标记

test_choice_cleared_after_consumption  
  验证 pend_choice 被 goto 消费后立即清零

# 回归测试
test_real_data_all_choices_valid
  遍历全数据，断言所有 choice 值 >= 1

test_real_data_s2s_190_sel_targets
  验证 s2s_190_sel 的 choice 目标恰好为 {s2s_208, s2s_209}，各仅一次
```

### 命令与输出

**单元测试结果（修复后）**：
```bash
$ uv run pytest tests/test_build_dag.py -v
tests/test_build_dag.py::test_states_capture_flow_in_order PASSED
tests/test_build_dag.py::test_states_capture_gate_choice_run_subcall PASSED
tests/test_build_dag.py::test_scene_meta_costs_and_gets PASSED
tests/test_build_dag.py::test_internal_if_blocks_not_marked_choice PASSED
tests/test_build_dag.py::test_choice_cleared_after_consumption PASSED
tests/test_build_dag.py::test_real_data_all_choices_valid PASSED
tests/test_build_dag.py::test_real_data_s2s_190_sel_targets PASSED
======================== 7 passed in 0.02s =========================
```

**全量回归测试**：
```bash
$ uv run pytest -q
................................ 36 passed in 1.09s
```

**确定性检查（双跑稳定）**：
```bash
$ md5sum data/dag.json
28dc488564df2c03f7054353dd2b9653  data/dag.json
$ uv run python tools/build_dag.py > /dev/null
$ md5sum data/dag.json
28dc488564df2c03f7054353dd2b9653  data/dag.json
```

### 改动汇总

修改了 build_dag.py：
- 添加 SEL_ASSIGN_RE 正则（第 17 行）
- 在 parse_states 开头添加第一轮扫描逻辑（26-40 行）
- 修改 CHOICE_RE 处理逻辑，仅当变量在 choice_vars 时设置 pend_choice（59-63 行）
- 在 goto 消费后立即清零 pend_choice（line 47）
- 为 SUBCALL_RE 守卫添加注释（line 70）
- 在 main() 输出 JSON 时添加末行换行（line 124）

data/dag.json 重新生成：
- 移除 8 处 spurious choice 标记（choice:0 和 choice:9/4/7/8）
- s2s_190_sel 的 choice:0 错误完全消除

### 审查结论

✓ 问题根因已消除（pend_choice 陈旧追踪）
✓ 修复符合评审要求（choice 变量正确识别、即时清零）
✓ 测试覆盖完整（内部变量、消费清零、真实数据验证）
✓ 结果正确性验证（choice 值 >= 1、s2s_190_sel 双路确定）
✓ 确定性保持（双跑 MD5 一致）
