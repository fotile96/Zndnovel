# Task 1 报告：领域只读工具层 `tools/agent_tools.py`

## 做了什么

按 `task-1-brief.md` 逐字实现，未做任何偏离：

1. **Step 1**：写 `tests/test_agent_tools.py`（7 条测试，brief 原文逐字写入）。
2. **Step 2**：`uv run pytest tests/test_agent_tools.py -v` → `ModuleNotFoundError: No module named 'tools.agent_tools'`，确认按预期失败。
3. **Step 3**：写 `tools/agent_tools.py`（brief 原文逐字写入）：四个只读函数 `get_lines`/`search_lines`/`get_note_proposal`/`get_anchor`，`ToolSpec` namedtuple 注册表 `TOOLS`，`tool_schemas()`（Responses API function 形状），`call_tool(name, args, lane_dir=None)` 分发（未注册名字抛 `KeyError`），CLI `main()` 用 `print` 输出 JSON，全程不含 `write_text(`/`open(`/`write_jsonl(`/`mkdir(`/`unlink(`。
4. **Step 4**：`uv run pytest tests/test_agent_tools.py -v` → **7 passed**。
5. **Step 5**：真实数据冒烟（见下）。
6. **Step 6**：`uv run pytest -q` → **361 passed**；`git add tools/agent_tools.py tests/test_agent_tools.py`（只加这两个文件，未碰 `.superpowers/sdd/2026-08-02-p3-seg2-s3/progress.md` 的未提交改动）；commit。

## Step 5 实际输出

### 命令 1：`get_lines --args '{"ids":[9441,9460,9483]}' --lane-dir pilot/lanes/opus`

```json
{
  "lines": [
    {"id": 9441, "jp": "【アヤノ】「ううん！ そんなこと、全然っ！ だって、私だって人の事言えるほど――」",
     "chapter": "s2s",
     "zh": "【アヤノ】「哪有！ 那种事，完全没有的！ 因为，我自己也没到能说别人的地步――」"},
    {"id": 9460, "jp": "【アヤノ】「ううん！ そんなこと、全然っ！ だって、私だって人のこと言えるほど――」",
     "chapter": "s2s",
     "zh": "【アヤノ】「哪有！ 那种事，完全没有的！ 因为，我自己也没到能说别人的地步――」"},
    {"id": 9483, "jp": "【アヤノ】「ううん！ そんなこと、全然っ！ だって、私だって人の事言えるほど――」",
     "chapter": "s2s",
     "zh": "【アヤノ】「哪有！ 那种事，完全没有的！ 因为，我自己也没到能说别人的地步――」"}
  ]
}
```

**冒烟结论：显示出 jp 差异**——9441/9483 为「人の事」，9460 为「人のこと」，而三行 `zh` 完全相同（一字不差）。工具如实透传了 ledger 里的书写差异，未做任何归一化，正是这条工具存在的价值：让下游（人或模型）能一眼看到被现行译文抹平的原文差异。

### 命令 2：`get_anchor --args '{"id":8478}'`

```json
{
  "is_anchor": true,
  "chapter": "s1s",
  "jp": "【サクラ】「約束、まもってくれないんだ。彩野さん」",
  "zh": "【サクラ】「约定，原来是不肯为我遵守呀。彩野同学」",
  "recall": "★汉字呼名装置（v7 补锚，与 s6s 15775 成对）：サクラ 全库 696 条 SAK 语音行里**仅 2 处**用汉字「彩野さん」……"
}
```

`is_anchor: true`，与 brief 预期一致（8478 是 v7 补的サクラ汉字呼名锚点）。

### 命令 3：`schemas | head -20`

```json
[
  {
    "type": "function",
    "name": "get_lines",
    "description": "取若干 id 的日文原文与现行中文译文（缺行返回 null）",
    "parameters": {
      "type": "object",
      "properties": {
        "ids": {
          "type": "array",
          "items": {"type": "integer"},
          "description": "要取的消息 id 列表"
        }
      },
      "required": ["ids"]
```

形状符合预期（Responses API function 形状 = MCP tool 形状）。

## 偏差与处理

无偏差。brief 给出的测试代码、实现代码、CLI 命令均逐字/逐条照办，全部一次通过，未做任何调整。

## 自查结论

- 7/7 新测试通过；全量 361/361 通过（较基线 354 增 7，与 brief 预期一致）。
- `test_module_has_no_write_operations` 通过，且人工复核 `tools/agent_tools.py` 全文确认无 `write_text(`/`open(`/`write_jsonl(`/`mkdir(`/`unlink(` 子串——只读约束成立。
- 真实数据冒烟三条命令输出与 brief 预期完全吻合，尤其第一条清楚复现了 9441/9460/9483 的 `人の事`/`人のこと` 书写差异（zh 完全相同），验证工具正确接上了 `data/ledger.jsonl` 与车道 `forward.jsonl` 数据源。
- 未 `git add -A`；只暂存并提交了 brief 指定的两个文件；`.superpowers/sdd/2026-08-02-p3-seg2-s3/progress.md` 的未提交改动（另一会话所有）保持原样未动。
- 未新增依赖（`yaml` 为既有 pyproject 依赖 pyyaml）；未发任何真实 API 请求。
