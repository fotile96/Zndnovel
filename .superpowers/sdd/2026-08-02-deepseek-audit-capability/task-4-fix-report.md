# DS-T4 复评修复报告

范围：`tools/audit_notes_promises.py`、`tests/test_audit_notes_promises.py`。
基线 HEAD `0866a1d`，`uv run pytest -q` 385 passed；修复后 392 passed
（新增 7 条覆盖，无删除、无 xfail）。

## 新的 `extract_promises` 返回值形状（T5 请照此消费）

```python
def extract_promises(proposal, *, runner=None) -> dict:
    ...
```

返回：

```python
{
    "promises": [
        {
            "kind": str,            # 承诺类型一句话概括
            "ids": list[int],       # 该承诺涉及的消息 id：见下方 ids_source
            "ids_source": "model" | "prewire",
            "prewire_ids": list[int],  # 提案级、正文里显式写明的 id（始终提供）
            "ids_invalid": list,    # 模型 ids 字段里被丢弃的非法项（留痕）
            "quote": str,
            "quote_verified": bool,
        },
        ...
    ],
    "parse_ok": bool,        # 模型输出是否被成功解析为 JSON object
    "stopped_reason": "finished" | "max_rounds" | "incomplete",  # 透传自 run_with_tools
    "ok": bool,              # parse_ok and stopped_reason == "finished"
}
```

**T5 的三态判据**：
- 有承诺：`ok is True and promises` 非空。
- 确认无承诺：`ok is True and promises == []`。
- 没读懂（计入报告「无法判断」桶，不得计入 clean）：`ok is False`——无论
  `promises` 是什么，此时都不可信。

`ids` 字段规则：模型显式给出该字段（哪怕是空列表 `[]`，代表「本承诺不针对
具体 id」）就用模型的，`ids_source="model"`；模型完全没给该 key 才回退到
`prewire_ids(proposal)`，`ids_source="prewire"`。两种来源都不做不可逆合并，
`prewire_ids` 字段始终额外提供，T5 若怀疑 `ids_source=="model"` 的空列表判断
有误，可自行决定是否回退——决定权在 T5，不在这一层。

## 逐条处置

1. **解析失败坍缩进「无承诺」（阻断级）**——已修。`_ask_json` 现返回三元组
   `(data, res, parse_ok)`；顶层 JSON 非 object 也算解析失败。`extract_promises`
   把 `parse_ok` 与 `run_with_tools` 的 `stopped_reason` 一并透传，并给出
   `ok` 便捷汇总。docstring 删除了原先「并留痕」这句凭空承诺（原实现根本
   没有留痕机制），改为如实描述现在的行为。补测试
   `test_malformed_model_output_is_distinguishable_from_confirmed_no_promise`
   直接断言「解析失败」与「确认无承诺」两条路径 `promises` 字面相等但 `ok`
   不同，外加两条分别覆盖 `stopped_reason in {max_rounds, incomplete}` 不被
   当 clean 的测试。

2. **`ids or prewire_ids(proposal)` 跨子句污染（应修）**——已修。模型显式给出
   `ids`（含 `[]`）不再被 `or prewire_ids(...)` 回退覆盖；只有该 key 完全缺失
   才回退，并标 `ids_source`。`prewire_ids` 同时作为独立字段保留，供 T5 事后
   核对/回退，本层不做不可逆合并。补测试
   `test_explicit_empty_model_ids_is_not_overridden_by_prewire`（两子句提案，
   一条带 id、一条通则声明返回 `ids: []`，断言后者仍是 `[]` 而非被接上前一条
   的 id）与 `test_model_omitting_ids_field_falls_back_to_prewire`（key 缺失
   时才回退）。

3. **三处边角**——已修：
   - `ID_RE` 改为不跨换行（字符类里的 `\s` 换成 `[ \t]`），补测试
     `test_prewire_ids_does_not_cross_newline` 验证缩进延续行不再被吞并。
   - 全角数字改为归一化后解析（`str.maketrans` 全角转半角，再跑 `NUM_RE`），
     不再静默丢弃；补测试 `test_prewire_ids_normalizes_fullwidth_digits`。
   - 新增 `_clean_model_ids`：显式排除 `bool`（`isinstance(True, int)` 为真
     但不再被当合法 id），非法项收进 `ids_invalid` 留痕而非丢弃后无声无息；
     补测试 `test_invalid_id_items_are_dropped_not_silently_coerced` 验证
     `True` 不再被转成虚构 id `1`，`"007"` 仍合法转 `7`。

## 顾虑

- T5 尚未编写，本次是按 brief 授权自由定的返回值形状；`ids_source`/
  `prewire_ids`/`ids_invalid` 这几个字段名是我的命名选择，T5 编写时如需要
  不同粒度（例如把 `ids_invalid` 展开成结构化原因）现在改代价还很低。
  一旦 T5 落地并有真实消费方，字段形状建议就此稳定，避免二次改签名。
- `_ask_json` 与 `extract_promises` 的 docstring 已尽量如实描述行为，但没有
  引入任何落盘/持久化的留痕机制——「留痕」目前仅体现为返回值里的
  `parse_ok`/`ids_invalid`/`quote_verified` 这几个可被下游读取的字段，并非
  日志或文件。如果后续需要跨次运行审计留痕（例如统计解析失败率），需要
  在调用方（未来的批量跑批脚本）单独加。
- 本次修复未触碰 `pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg2-s3/`、
  `docs/superpowers/plans/translate-seg*.md`、`progress.md`；`git status` 显示
  两份 `progress.md` 有非本次改动的未提交改动（另一会话所留），本次
  `git add` 严格只包含 `tools/audit_notes_promises.py`、
  `tests/test_audit_notes_promises.py` 与本报告文件。
