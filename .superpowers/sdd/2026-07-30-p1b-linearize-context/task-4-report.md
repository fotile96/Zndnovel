# Task 4: check_timeline 校验器 - 报告

## 实现摘要

实现了独立的 timeline 校验器 `tools/check_timeline.py`，包含三组断言：
- **A 覆盖检查**：验证 narrative id 恰好出现一次，ambient id 零次，无未知 id
- **B CRD 合法性检查**：验证每个 card unit 的 req⊆此前 held，及路线前缀规则
- **C 门控表检查**：验证 `config/gates.yaml` 中的门控约束在首次出现前满足

## 文件清单

### 新建
- `tools/check_timeline.py` - 校验器实现 + CLI main()
- `tests/test_check_timeline.py` - 四个测试用例
- `config/gates.yaml` - 初始门控配置（8 条规则）

### 修改
无

## TDD 循环过程

### RED 阶段
```bash
$ uv run pytest tests/test_check_timeline.py -v
ERROR collecting tests/test_check_timeline.py
ModuleNotFoundError: No module named 'tools.check_timeline'
```
✅ 符合预期（测试文件创建后，实现文件不存在导致导入失败）

### GREEN 阶段
```bash
$ uv run pytest tests/test_check_timeline.py -v
tests/test_check_timeline.py::test_clean_timeline_passes PASSED          [ 25%]
tests/test_check_timeline.py::test_missing_and_duplicate_ids_detected PASSED [ 50%]
tests/test_check_timeline.py::test_gate_violation_detected PASSED        [ 75%]
tests/test_check_timeline.py::test_crd_req_violation_detected PASSED     [100%]

============================== 4 passed in 0.04s ===============================
```
✅ 所有测试通过

### 全套回归检查
```bash
$ uv run pytest -q
...........................................................              [100%]
59 passed in 2.47s
```
✅ 无回归（55→59，增加的 4 个是本任务新增测试）

## 实现要点

1. **ID 覆盖验证（A）**
   - 统计 timeline 中每个 unit 的 ids 出现次数
   - 检测重复、缺失、未知 id
   - 错误消息包含关键词「缺失」「重复」「未知」

2. **CRD 合法性验证（B）**
   - 维护 `held` 集合（已做卡）与 `route` 列表（场景序列）
   - 对每个 card unit，验证 req 集合是否被 held 包含
   - 对非 `_sel` 卡，检查前缀路线中所有场景是否已做卡
   - 从 DAG 的 `scene_meta` 提取获得卡片的事件
   - 错误消息包含关键词「req」

3. **门控表验证（C）**
   - 对每条 gate 规则，找到该 unit_state 首次出现位置
   - 重新计算该位置前的 held 集合
   - 检查 requires_cards 中是否有缺失卡
   - 错误消息包含关键词「门控」

4. **CLI 接口**
   - `main()` 读取 `data/timeline.jsonl`、`data/dag.json`、`data/scene2card.json`、`config/gates.yaml`
   - 支持标准流：全部错误列表或"OK"
   - 返回码：0 通过，1 失败

## 代码质量检查

- ✅ 风格一致：沿用 `build_dag.py` / `gen_timeline.py` 的导入与格式约定
- ✅ 错误消息准确：包含 brief 要求的中文关键词（缺失/重复/门控/req）
- ✅ 无超额建设：实现恰好满足 brief 需求
- ✅ 测试覆盖：
  - `test_clean_timeline_passes` - 正常 timeline 通过
  - `test_missing_and_duplicate_ids_detected` - ID 覆盖检查
  - `test_gate_violation_detected` - 门控约束检查
  - `test_crd_req_violation_detected` - CRD req 检查
- ✅ 输出干净：无告警，无冗余消息

## 与其他组件的交互

- **Expander**（Task 2/3）：时间轴生产者，本校验器作为消费者验证其输出
- **DAG** 与 **LEDGER**：基础数据依赖，由 Task 1 提供
- **gates.yaml**：配置驱动，Task 5（编路线）可增补新规则

## 提交信息

```
Commit: 426c885
Message: feat: check_timeline 覆盖/crd/门控三组断言
Files: 
  - tools/check_timeline.py (119 lines)
  - tests/test_check_timeline.py (32 lines)
  - config/gates.yaml (8 rows)
```

## 自评审

### 完整性 ✅
- 三组断言全部实现
- 四个测试用例覆盖正常与异常路径
- 初始 gates.yaml 按 CLAUDE.md 章节门控填充

### 质量 ✅
- 代码风格与既有代码一致
- 错误消息清晰并包含诊断信息
- 逻辑清晰可维护

### 纪律 ✅
- 严格按 brief 照抄（已删除指定的空转循环）
- TDD 循环完整：写测试→RED→实现→GREEN→提交
- 无新增依赖

### 测试 ✅
- 4/4 新增测试通过
- 全套 59 passed，无回归
- 输出干净无告警

## 遗留问题或顾虑

无。实现完整，测试全绿。CLI 的 `main()` 虽依赖 Task 5 的输出数据，但按 brief 要求只需代码就位。

## 后续用途

本校验器是 Task 5（路线编写）的验证回路：每条新路线（timeline）生成后即刻运行 check_timeline 验证三组断言，确保翻译工具链的上游数据完整性。
