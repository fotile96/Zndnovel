"""手记「承诺-履行」审计（spec §4）。

审的是**决策的执行**而非文本质量：手记里记着大量显式翻译决定（「照原样保留」
「须逐字一致」「不消歧」「已按 X 统一」），从来没有人回头查过它们是否真被
执行——甚至可能在后续批次被无意识违反。机器校验器结构上做不到这件事。

**只审硬承诺，不审软倾向**（spec §4.2）：「建议」「宜」「可考虑」本来就没许诺
执行，审它会制造大量伪违约，把真违约淹掉——与本项目反复吃过亏的「噪声掩盖
信号」是同一种失败。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.agent_loop import run_with_tools

ID_RE = re.compile(r"\bid\s*([0-9０-９、,，\s]+)")
NUM_RE = re.compile(r"[0-9]+")

PROMISE_SYS = """你在审计一份翻译项目的译者手记。你的任务**只有一个**：从提案正文里
找出**已经作出的硬承诺**，不要找建议。

算硬承诺的（举例）：「本批已按 X 统一」「照原样保留待判」「须逐字一致」「此处保留
歧义」「不消歧」「已按上述译法统一」——它们描述的是**已经决定并执行的事**。

**不算**硬承诺的：「建议」「宜」「可考虑」「请一并裁决」「拟」——这些只是倾向，没有
许诺执行。把它们当承诺会制造伪违约。

只输出 JSON，不要任何其他文字：
{"promises": [{"kind": "一句话概括承诺类型", "ids": [涉及的消息 id], "quote": "提案里的原话"}]}
找不到硬承诺就输出 {"promises": []}。"""


def prewire_ids(proposal):
    """从提案正文里抽出显式写明的 id（提案格式如 `- id 7327、7329、7332`）。"""
    ids = []
    for m in ID_RE.finditer(proposal.get("body", "")):
        ids += [int(x) for x in NUM_RE.findall(m.group(1))]
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _ask_json(runner, messages, **kw):
    """跑一轮并把结果解析成 dict；非 JSON 视为空结果并留痕，不让整轮审计崩掉。"""
    fn = runner or run_with_tools
    res = fn(messages, **kw)
    text = (res.get("content") or "").strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(text), res
    except Exception:
        return {}, res


def _quote_found(quote, body):
    """`quote` 是否能在提案正文里找到（去空白后子串匹配）。

    宽松校验：只用于留痕，不据此丢弃承诺——模型可能对原话做了省略号截断或
    标点归一化，这种「合理省略」不应该被机械闸误伤。
    """
    if not quote:
        return False
    norm = lambda s: re.sub(r"\s+", "", s)
    return norm(quote) in norm(body)


def extract_promises(proposal, *, runner=None):
    """步骤 1（无工具）：从单条提案抽硬承诺。

    每项额外带 `quote_verified: bool`——`quote` 字段是否能在提案正文里找到
    （去空白后子串匹配）。找不到不丢弃该承诺，只留痕，供步骤 2/报告环节
    据此降权或标注「引用未核实」。
    """
    body = (f"【提案标题】{proposal['title']}\n【提案正文】\n{proposal['body']}\n"
            f"【正文里显式写明的 id】{prewire_ids(proposal)}")
    data, _ = _ask_json(runner, [{"role": "system", "content": PROMISE_SYS},
                                 {"role": "user", "content": body}],
                        purpose=f"audit-promise-extract:{proposal['chapter']}"
                                f":b{proposal['batch']}:#{proposal['num']}")
    out = []
    for p in (data.get("promises") or []):
        ids = [int(i) for i in (p.get("ids") or []) if str(i).isdigit() or isinstance(i, int)]
        quote = p.get("quote", "")
        out.append({"kind": p.get("kind", ""), "ids": ids or prewire_ids(proposal),
                    "quote": quote,
                    "quote_verified": _quote_found(quote, proposal.get("body", ""))})
    return out
