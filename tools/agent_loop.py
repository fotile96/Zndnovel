"""有界工具循环：模型要调工具就代它调，把结果回灌进下一轮，轮次有硬上限。

**为什么敢自建**：工具面（tools/agent_tools.py）全只读，唯一的写操作（写报告）
由任务层执行、不经过模型。所以循环跑飞的最坏后果是报告不完整，而不是仓库被
改坏（spec §1.2）。

**到顶不静默**：`max_rounds` 用尽时返回 `stopped_reason="max_rounds"`，调用方
必须能看出「这次是被截断的」——静默截断会让下游把半截结论当完整结论。

**「被截断」不止一种**。三条路径的实测归宿（离线探针，见 task-3-report 修正一节）：
  · `response.incomplete`（输出打满 max_output_tokens）——`chat()` **正常返回**、
    usage 齐全、台账行与正常调用完全同形，唯一线索是新增的 `status` 键。
    → `stopped_reason="incomplete"`。**这条曾被漏掉**：半截结论会一路当成完整结论。
  · 流在终止事件前中断（StreamAborted / 网络类）——异常**穿透**本模块（下面的
    `except` 只包住单个工具执行，不包 `chat()`），本来就是大声失败，无需处理。
  · 轮次用尽 → `stopped_reason="max_rounds"`。
故消费侧的契约是：**只有 `finished` 才算完整，其余一律存疑**。

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
from tools.api_client import chat, ledger_token
from tools.agent_tools import TOOLS, call_tool, tool_schemas

DEFAULT_MAX_ROUNDS = 6
RESULT_SUMMARY_CHARS = 2000


def _summarize(obj):
    s = json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= RESULT_SUMMARY_CHARS else s[:RESULT_SUMMARY_CHARS] + "…（已截断）"


def run_with_tools(messages, *, tool_names=None, max_rounds=DEFAULT_MAX_ROUNDS,
                   lane_dir=None, **chat_kw) -> dict:
    """带工具的多轮对话。`tool_names` 省略即不给工具（退化为单轮 chat）。

    返回 `{content, rounds, tool_calls, tool_errors, stopped_reason, reasoning_text,
    prompt_tokens, completion_tokens, tokens_estimated}`。
    `stopped_reason ∈ {"finished", "incomplete", "max_rounds"}`——**只有 `finished`
    才算完整**，其余两值都意味着结论可能是半截的（理由见模块 docstring）。
    `tool_errors` 是**工具执行**失败的次数（不含模型给了非法参数那类）：它非 0 就说明
    模型看到的是错误文本而不是数据，纵使它照样自信作答；消费侧应据此存疑，不必去
    grep `result_summary` 的字符串。
    """
    names = list(tool_names or [])
    unknown = [n for n in names if n not in TOOLS]
    if unknown:
        raise SystemExit(f"未注册的工具名：{unknown}")
    schemas = [s for s in tool_schemas() if s["name"] in names]
    convo = list(messages)
    tool_calls, rounds, tool_errors = [], 0, 0
    last = {"content": "", "reasoning_text": "", "prompt_tokens": 0, "completion_tokens": 0}
    pin = pout = 0
    tokens_estimated = False

    def _finish(reason):
        return {"content": last.get("content", ""), "rounds": rounds,
                "tool_calls": tool_calls, "tool_errors": tool_errors,
                "stopped_reason": reason,
                "reasoning_text": last.get("reasoning_text", ""),
                "prompt_tokens": pin, "completion_tokens": pout,
                "tokens_estimated": tokens_estimated}

    while rounds < max_rounds:
        rounds += 1
        kw = dict(chat_kw)
        if schemas:
            kw["tools"] = schemas
            kw["allowed_tool_names"] = set(TOOLS)
        last = chat(convo, **kw)
        # 累加走 ledger_token 而不是 `or 0`：远端没下发 usage 时 chat() 返回的是
        # **-1 哨兵**（「不知道」，不是 0），`or 0` 挡不住它，直接相加会把总数**减**掉
        # ——一个静默的低估，行数越多越错（api_client.ledger_token 的 docstring 警告
        # 过的正是这条，本模块起初原样重犯了）。取不到就跳过该轮并置 tokens_estimated。
        for key, acc in (("prompt_tokens", "pin"), ("completion_tokens", "pout")):
            v = ledger_token(last, key)
            if v is None:
                tokens_estimated = True
            elif acc == "pin":
                pin += v
            else:
                pout += v
        fcs = last.get("function_calls") or []
        if not fcs:
            # `.get()` 而非 `[...]`：不带 status 键的调用方/桩照样按 finished 走。
            return _finish("incomplete" if last.get("status") == "response.incomplete"
                           else "finished")
        # 代模型执行工具，把结果作为一条 user 轮次回灌（不依赖 function_call_output
        # 的特定线格式——用纯文本回灌在任何兼容层上都成立，代价是少一点结构化）。
        convo = convo + [{"role": "assistant", "content": last.get("content", "") or "（调用工具）"}]
        for fc in fcs:
            name = fc.get("name")
            raw = fc.get("arguments") or "{}"
            # 解析与执行**分开 try**：两者是性质完全不同的故障。参数非法是模型的问题
            # （回灌错误让它改正是对的）；工具执行失败往往是**系统性故障**（lane_dir
            # 传错、anchors.yaml 缺失、ledger 读不到），把它降级成一条 error 文本喂回去，
            # 模型会拿着「查不到」继续自信作答，而 loop 照样报 finished。合成一块 try
            # 时这两者不可区分——故分别打 kind，并只对后者计入 tool_errors。
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except Exception as exc:
                args = {"_raw": raw}
                summary = _summarize({"error": f"{type(exc).__name__}: {exc}",
                                      "kind": "bad_arguments"})
            else:
                try:
                    summary = _summarize(call_tool(name, args, lane_dir=lane_dir))
                except Exception as exc:
                    tool_errors += 1
                    summary = _summarize({"error": f"{type(exc).__name__}: {exc}",
                                          "kind": "tool_error"})
            tool_calls.append({"name": name, "args": args, "result_summary": summary})
            convo = convo + [{"role": "user",
                              "content": f"工具 {name} 的返回：\n{summary}"}]
    return _finish("max_rounds")


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
          f"tools={[c['name'] for c in out['tool_calls']]} "
          f"tool_errors={out['tool_errors']}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
