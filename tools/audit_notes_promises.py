"""手记「承诺-履行」审计（spec §4）。

审的是**决策的执行**而非文本质量：手记里记着大量显式翻译决定（「照原样保留」
「须逐字一致」「不消歧」「已按 X 统一」），从来没有人回头查过它们是否真被
执行——甚至可能在后续批次被无意识违反。机器校验器结构上做不到这件事。

**只审硬承诺，不审软倾向**（spec §4.2）：「建议」「宜」「可考虑」本来就没许诺
执行，审它会制造大量伪违约，把真违约淹掉——与本项目反复吃过亏的「噪声掩盖
信号」是同一种失败。

**「无法判断」是一等公民**（spec §4.4）：模型输出解析失败、或轮次/输出被截断
（`stopped_reason != "finished"`），一律不得坍缩成「这条提案没有硬承诺」——
两者在下游看来必须可区分，否则报告顶部的「无法判断占比」这项可信度指标就是
假的。见 `extract_promises` 返回值里的 `parse_ok`/`stopped_reason`/`ok`。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.agent_loop import run_with_tools

# 行内、非跨换行：提案是逐行罗列的「- id ...」，跨行会把下一条无关的行号吞进来。
ID_RE = re.compile(r"\bid[ \t]*([0-9０-９、,， \t]+)")
NUM_RE = re.compile(r"[0-9]+")
_Z2H_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

PROMISE_SYS = """你在审计一份翻译项目的译者手记。你的任务**只有一个**：从提案正文里
找出**已经作出的硬承诺**，不要找建议。

算硬承诺的（举例）：「本批已按 X 统一」「照原样保留待判」「须逐字一致」「此处保留
歧义」「不消歧」「已按上述译法统一」——它们描述的是**已经决定并执行的事**。

**不算**硬承诺的：「建议」「宜」「可考虑」「请一并裁决」「拟」——这些只是倾向，没有
许诺执行。把它们当承诺会制造伪违约。

只输出 JSON，不要任何其他文字：
{"promises": [{"kind": "一句话概括承诺类型", "ids": [涉及的消息 id], "quote": "提案里的原话"}]}
找不到硬承诺就输出 {"promises": []}。
若该承诺不针对具体消息 id（如通则声明），"ids" 请显式给 []，不要省略该字段。"""


def prewire_ids(proposal):
    """从提案正文里抽出显式写明的 id（提案格式如 `- id 7327、7329、7332`）。

    只在单行内抽取（`ID_RE` 不含换行符），并把全角数字归一化为半角后再解析，
    避免把下一行缩进延续行的数字吞进来、或把 `７３２９` 这类全角写法静默丢弃。
    """
    ids = []
    for m in ID_RE.finditer(proposal.get("body", "")):
        normalized = m.group(1).translate(_Z2H_DIGITS)
        ids += [int(x) for x in NUM_RE.findall(normalized)]
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _ask_json(runner, messages, **kw):
    """跑一轮并尝试把结果解析成 dict。

    返回 `(data, res, parse_ok)`。解析失败（非 JSON，或 JSON 合法但顶层不是
    object）时 `data={}`、`parse_ok=False`——**调用方必须把 `parse_ok=False`
    当成「没读懂」，不得当成「确认无承诺」**，两者在返回值里必须可区分。
    这里本身不做留痕/落盘；留痕由调用方基于 `parse_ok` 决定如何处理。
    """
    fn = runner or run_with_tools
    res = fn(messages, **kw)
    text = (res.get("content") or "").strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except Exception:
        return {}, res, False
    if not isinstance(data, dict):
        return {}, res, False
    return data, res, True


def _quote_found(quote, body):
    """`quote` 是否能在提案正文里找到（去空白后子串匹配）。

    宽松校验：只用于留痕，不据此丢弃承诺——模型可能对原话做了省略号截断或
    标点归一化，这种「合理省略」不应该被机械闸误伤。
    """
    if not quote:
        return False
    norm = lambda s: re.sub(r"\s+", "", s)
    return norm(quote) in norm(body)


def _clean_model_ids(raw):
    """清洗模型给出的 `ids` 字段。

    返回 `(ids, invalid)`：合法项（整数，或纯数字字符串如 `"007"`）转 int 保留
    原始出现顺序去重；非法项（`bool`——`isinstance(True, int)` 为真但这里显式
    排除、非数字字符串、浮点数等）**明确丢弃**并记入 `invalid`，不静默转换成
    看似合法的 id（例如过去 `True` 会被转成虚构的 id `1`）。
    """
    ids, invalid, seen = [], [], set()
    for i in raw:
        ok = (isinstance(i, int) and not isinstance(i, bool)) or \
             (isinstance(i, str) and i.isdigit())
        if not ok:
            invalid.append(i)
            continue
        v = int(i)
        if v not in seen:
            seen.add(v)
            ids.append(v)
    return ids, invalid


def extract_promises(proposal, *, runner=None):
    """步骤 1（无工具）：从单条提案抽硬承诺。

    返回 dict，供下游（T5）区分三态：
    - `promises`: 抽出的承诺列表，每项：
      - `kind`: 一句话概括承诺类型
      - `ids`: 该承诺涉及的消息 id——模型显式给出（哪怕是空列表 `[]`，代表
        「本承诺不针对具体 id」）就用模型的，**不会**被提案级 `prewire_ids`
        覆盖；模型未给出该字段时才回退到 `prewire_ids(proposal)`。
      - `ids_source`: `"model"` 或 `"prewire"`，标明上面 `ids` 的来源。
      - `prewire_ids`: 提案级、正文里显式写明的 id（始终提供，供下游在怀疑
        `ids_source == "model"` 判断有误时自行回退——是否回退由 T5 决定，
        这里不做不可逆的合并）。
      - `ids_invalid`: 模型 `ids` 字段里被丢弃的非法项（留痕，非空即说明模型
        输出有杂质）。
      - `quote` / `quote_verified`：见 `_quote_found`。
    - `parse_ok`: 模型输出是否被成功解析为 JSON object（见 `_ask_json`）。
    - `stopped_reason`: 透传自 `run_with_tools`，`"finished"|"max_rounds"|"incomplete"`。
    - `ok`: `parse_ok and stopped_reason == "finished"` 的便捷汇总——**只有
      `ok is True` 时，`promises == []` 才能读作「确认无承诺」**；`ok is
      False` 时（解析失败，或轮次/输出被截断）无论 `promises` 是什么都应计入
      「无法判断」，不得当成 clean 计数。
    """
    body = (f"【提案标题】{proposal['title']}\n【提案正文】\n{proposal['body']}\n"
            f"【正文里显式写明的 id】{prewire_ids(proposal)}")
    data, res, parse_ok = _ask_json(
        runner, [{"role": "system", "content": PROMISE_SYS},
                 {"role": "user", "content": body}],
        purpose=f"audit-promise-extract:{proposal['chapter']}"
                f":b{proposal['batch']}:#{proposal['num']}")
    stopped_reason = res.get("stopped_reason", "finished")

    out = []
    for p in (data.get("promises") or []):
        raw_ids = p.get("ids")
        if isinstance(raw_ids, list):
            model_ids, invalid = _clean_model_ids(raw_ids)
            ids_source = "model"
        else:
            model_ids, invalid = None, []
            ids_source = "prewire"
        pre = prewire_ids(proposal)
        out.append({
            "kind": p.get("kind", ""),
            "ids": model_ids if ids_source == "model" else pre,
            "ids_source": ids_source,
            "prewire_ids": pre,
            "ids_invalid": invalid,
            "quote": p.get("quote", ""),
            "quote_verified": _quote_found(p.get("quote", ""), proposal.get("body", "")),
        })

    return {
        "promises": out,
        "parse_ok": parse_ok,
        "stopped_reason": stopped_reason,
        "ok": parse_ok and stopped_reason == "finished",
    }
