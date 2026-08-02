"""有界工具循环：模型要调工具就代它调，把结果回灌进下一轮，轮次有硬上限。

**为什么敢自建**：工具面（tools/agent_tools.py）全只读，唯一的写操作（写报告）
由任务层执行、不经过模型。所以循环跑飞的最坏后果是报告不完整，而不是仓库被
改坏（spec §1.2）。

**到顶不静默**：`max_rounds` 用尽时返回 `stopped_reason="max_rounds"`，调用方
必须能看出「这次是被截断的」——静默截断会让下游把半截结论当完整结论。

**回灌形状的取舍**：工具结果用**纯文本 user 轮次**回灌，而不是结构化的
`function_call_output` 项。Task 2 探针已确认 deepseek 的 function_call 线格式与
OpenAI Responses 惯例一致（`call_id`/`name`/`arguments` 为 JSON 字符串），结构化
续轮在协议层是可行的；但那要求 `chat()` 能接受预构建的 input items（把上一轮的
output items 原样回填），是更大的接口改动。纯文本方案不依赖任何兼容层细节，代价
是模型少一点结构提示。若实跑中观察到模型分不清工具结果与用户输入，那才是改用
结构化回灌的证据。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.api_client import chat
from tools.agent_tools import TOOLS, call_tool, tool_schemas

DEFAULT_MAX_ROUNDS = 6
RESULT_SUMMARY_CHARS = 2000


def _summarize(obj):
    s = json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= RESULT_SUMMARY_CHARS else s[:RESULT_SUMMARY_CHARS] + "…（已截断）"


def run_with_tools(messages, *, tool_names=None, max_rounds=DEFAULT_MAX_ROUNDS,
                   lane_dir=None, **chat_kw) -> dict:
    """带工具的多轮对话。`tool_names` 省略即不给工具（退化为单轮 chat）。"""
    names = list(tool_names or [])
    unknown = [n for n in names if n not in TOOLS]
    if unknown:
        raise SystemExit(f"未注册的工具名：{unknown}")
    schemas = [s for s in tool_schemas() if s["name"] in names]
    convo = list(messages)
    tool_calls, rounds = [], 0
    last = {"content": "", "reasoning_text": "", "prompt_tokens": 0, "completion_tokens": 0}
    pin = pout = 0
    while rounds < max_rounds:
        rounds += 1
        kw = dict(chat_kw)
        if schemas:
            kw["tools"] = schemas
            kw["allowed_tool_names"] = set(TOOLS)
        last = chat(convo, **kw)
        pin += last.get("prompt_tokens", 0) or 0
        pout += last.get("completion_tokens", 0) or 0
        fcs = last.get("function_calls") or []
        if not fcs:
            return {"content": last.get("content", ""), "rounds": rounds,
                    "tool_calls": tool_calls, "stopped_reason": "finished",
                    "reasoning_text": last.get("reasoning_text", ""),
                    "prompt_tokens": pin, "completion_tokens": pout}
        # 代模型执行工具，把结果作为一条 user 轮次回灌（不依赖 function_call_output
        # 的特定线格式——用纯文本回灌在任何兼容层上都成立，代价是少一点结构化）。
        convo = convo + [{"role": "assistant", "content": last.get("content", "") or "（调用工具）"}]
        for fc in fcs:
            name = fc.get("name")
            raw = fc.get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
                result = call_tool(name, args, lane_dir=lane_dir)
                summary = _summarize(result)
            except Exception as exc:
                args = {"_raw": raw}
                summary = _summarize({"error": f"{type(exc).__name__}: {exc}"})
            tool_calls.append({"name": name, "args": args, "result_summary": summary})
            convo = convo + [{"role": "user",
                              "content": f"工具 {name} 的返回：\n{summary}"}]
    return {"content": last.get("content", ""), "rounds": rounds,
            "tool_calls": tool_calls, "stopped_reason": "max_rounds",
            "reasoning_text": last.get("reasoning_text", ""),
            "prompt_tokens": pin, "completion_tokens": pout}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="带工具的一次性提问（调试用）")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--tools", default="", help="逗号分隔的工具名，空则不给工具")
    ap.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    ap.add_argument("--lane-dir", default=None)
    a = ap.parse_args(argv)
    names = [t for t in a.tools.split(",") if t]
    out = run_with_tools([{"role": "user", "content": a.prompt}], tool_names=names,
                         max_rounds=a.max_rounds, lane_dir=a.lane_dir,
                         purpose="agent-loop-cli")
    print(out["content"])
    print(f"\n[rounds={out['rounds']} stopped={out['stopped_reason']} "
          f"tools={[c['name'] for c in out['tool_calls']]}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
