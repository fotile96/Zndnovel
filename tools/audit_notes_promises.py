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
from tools.agent_tools import call_tool

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


VERIFY_SYS = """你在核对一条**已经作出的翻译承诺**是否真的被执行。

给你的材料是：承诺原话、以及相关行的日文原文与现行中文译文。

判定只能是三者之一：
- **已履行**：译文确实按承诺处理了
- **未履行**：译文与承诺矛盾
- **无法判断**：材料不足以判定

**「无法判断」是正当答案，不要为了给个结论而硬判。** 把不确定硬判成「已履行」
比不判更有害。

判定必须锚定**可复算的字面事实**——引用具体的行 id 与原文/译文内容。不要用
你的推理过程本身当依据。

只输出 JSON：{"verdict": "已履行|未履行|无法判断", "evidence_ids": [行 id], "reason": "一句话"}"""

TOOL_NAMES = ["get_lines", "search_lines", "get_anchor"]
VALID_VERDICTS = {"已履行", "未履行", "无法判断"}


def verify_promise(promise, proposal, *, lane_dir=None, runner=None):
    """步骤 2：预拼为主、工具兜底。

    **三条机械闸**（brief §2）：模型的结论在被采信前，先过三条能机械验证的
    检查；踩中任一条就强制把 `verdict` 降为「无法判断」——`VERIFY_SYS` 里
    「不要为了给个结论而硬判」只是劝导模型，靠不住，这里才是真正挡得住的
    关卡：
    1. `stopped_reason != "finished"` —— 推理被砍断（`max_rounds`/`incomplete`），
       结论可能是半截的。
    2. `tool_errors != 0` —— 工具执行本身失败（`lane_dir` 传错、数据缺失这类
       系统性故障），模型是拿着报错文本作答的。
    3. 走工具兜底（`ids` 为空）却一次都没调用工具——模型凭空作答，没看任何
       真实数据。**只在开了工具时生效**：预拼路径（`ids` 齐全）本来就不给
       工具，`tool_calls` 为空是正常状态，不得据此误伤（见
       `test_gate3_does_not_fire_when_ids_prewired_even_if_no_tool_calls`）。

    **决策（brief §4，`ids_source == "model"` 且 `ids == []` 这一路）**：这里
    只看 `promise["ids"]`，**不**回退到 `promise["prewire_ids"]`。T4 的抽取
    阶段已经刻意避免让「通则声明」类承诺被同一提案里其他子句的 id 污染（见
    `test_explicit_empty_model_ids_is_not_overridden_by_prewire`）；T5 若在
    这里再做一次回填，等于绕开 T4 定的边界，重新把跨子句的 id 接回来。空
    `ids` 因此照实走工具兜底，让模型自己确认/检索「这条承诺确实不针对
    具体行」。
    """
    ids = promise.get("ids") or []
    used_tools_path = not ids
    if ids:
        lines = call_tool("get_lines", {"ids": ids}, lane_dir=lane_dir)["lines"]
        ctx = "\n".join(
            f"id {r['id']}（{r['chapter']}）\n  原文：{r['jp']}\n  译文：{r['zh']}"
            for r in lines)
        kw = {}
    else:
        ctx = "（提案未写明 id，请用工具自行查找相关行）"
        kw = {"tool_names": TOOL_NAMES, "lane_dir": lane_dir}
    user = (f"【承诺】{promise.get('kind')}：{promise.get('quote')}\n"
            f"【出处】{proposal['chapter']} b{proposal['batch']} #{proposal['num']}"
            f" —— {proposal['title']}\n【相关行】\n{ctx}")
    data, res, parse_ok = _ask_json(
        runner, [{"role": "system", "content": VERIFY_SYS},
                 {"role": "user", "content": user}],
        purpose=f"audit-promise-verify:{proposal['chapter']}"
                f":b{proposal['batch']}:#{proposal['num']}",
        **kw)

    stopped_reason = res.get("stopped_reason", "finished")
    tool_errors = res.get("tool_errors", 0)
    tool_calls = res.get("tool_calls") or []

    verdict = data.get("verdict") if parse_ok else None
    reason = (data.get("reason") or "") if parse_ok else ""
    if verdict not in VALID_VERDICTS:
        verdict = "无法判断"
        reason = reason or "（模型未给出可解析的判定，或输出不是合法 JSON）"

    gate = None
    if stopped_reason != "finished":
        gate = f"机械闸：stopped_reason={stopped_reason}，结论不完整"
    elif tool_errors:
        gate = f"机械闸：tool_errors={tool_errors}，模型基于报错信息作答"
    elif used_tools_path and not tool_calls:
        gate = "机械闸：开了工具但模型一次都没调用，判断可能是凭空作答"
    if gate:
        verdict = "无法判断"
        reason = gate

    return {
        "verdict": verdict,
        "evidence_ids": [i for i in (data.get("evidence_ids") or []) if isinstance(i, int)],
        "reason": reason,
        "used_tools": used_tools_path or bool(tool_calls),
        "reasoning_text": res.get("reasoning_text", ""),
        # 决策（brief §4）：quote_verified/ids_invalid 不用于改变 verdict——
        # 它们是提案抽取阶段的留痕信号，不代表履行核对本身出了问题；这里
        # 原样透传，交给 render_report 在报告里作为「留痕不改判」的提示项，
        # 见 render_report 的处理。
        "quote_verified": promise.get("quote_verified"),
        "ids_invalid": promise.get("ids_invalid") or [],
    }


ORDER = {"未履行": 0, "无法判断": 1, "已履行": 2}


def render_report(results, extraction_failures=None):
    """步骤 3（无模型）：未履行优先，无法判断单列，顶部显示可信度指标。

    `extraction_failures`：抽取阶段 `not ok`（模型没读懂那条提案）的提案列表，
    每项 `{"proposal": <提案 dict>, "reason": <字符串>}`。

    **报告分母问题（brief §3，阻断级）**：抽取失败的提案产生零条承诺，若
    只统计 `results`（履行核对阶段的三态），这些提案会从统计里彻底消失，
    报告显得比实际干净——这与 Task 4 修的洞是同一个，只是上移到了提案层。
    这里的处置：**不**把抽取失败并入下面的「无法判断」三态统计（那统计的
    问题域是「对已读懂的承诺，证据是否够判」；抽取失败是另一件事——「这条
    提案压根没读懂，连有没有硬承诺都不知道」，两者混在一起会让读者分不清
    是哪个阶段出的问题），而是在报告最顶部单独给一行计数、并列出具体是
    哪些提案，做到「一眼看出有多少提案根本没被审到」，同时明确标注它们
    不计入已履行。
    """
    n = len(results)
    cnt = {v: sum(1 for r in results if r["verdict"] == v) for v in VALID_VERDICTS}
    pct = (cnt["无法判断"] * 100 // n) if n else 0
    fails = list(extraction_failures or [])

    lines = [f"# 手记「承诺-履行」审计报告（{n} 条硬承诺）", "",
             f"- **抽取失败提案 {len(fails)} 条** —— 模型没读懂对应提案，"
             f"零条承诺，不计入下面任何一项三态统计",
             f"- 未履行 **{cnt['未履行']}** ｜ 已履行 {cnt['已履行']} ｜ 无法判断 {cnt['无法判断']}",
             f"- **无法判断占比 {pct}%**（相对已成功抽取的 {n} 条硬承诺）—— "
             f"该比例本身是可信度指标，偏高说明材料或判据不足", ""]

    if fails:
        lines.append("## 抽取失败提案（未被审到）")
        for f in fails:
            p = f["proposal"]
            lines.append(f"- {p['chapter']} b{p['batch']} #{p['num']} · "
                         f"{p['title']} —— {f['reason']}")
        lines.append("")

    for r in sorted(results, key=lambda r: ORDER[r["verdict"]]):
        p, pr = r["proposal"], r["promise"]
        # quote_verified 只在**明确为 False**时才提示——缺该字段（旧数据/
        # 测试桩）不应被当成「核验失败」而误报警告。
        quote_note = "" if pr.get("quote_verified") is not False \
            else "（⚠ 未在提案正文中逐字核验到，留痕不代表承诺不存在）"
        lines += [f"## [{r['verdict']}] {p['chapter']} b{p['batch']} #{p['num']} · {pr.get('kind')}",
                  f"- 承诺原话：{pr.get('quote')}{quote_note}",
                  f"- 依据行：{r['evidence_ids'] or '（无）'}",
                  f"- 理由：{r['reason']}",
                  f"- 用了工具：{'是' if r['used_tools'] else '否'}"]
        if pr.get("ids_invalid"):
            lines.append(f"- ⚠ 模型给出的 id 含非法项已丢弃：{pr['ids_invalid']}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    import argparse
    from tools.cluster_notes import parse_notes
    ap = argparse.ArgumentParser(description="手记「承诺-履行」审计")
    ap.add_argument("--lane-dir", default="pilot/lanes/opus")
    ap.add_argument("--chapter", default=None, help="只审某一章，省略则全部")
    ap.add_argument("--limit", type=int, default=0, help="只审前 N 条提案（0=不限）")
    ap.add_argument("--out", default="work/out/audit-notes-promises.md")
    a = ap.parse_args(argv)
    lane = Path(a.lane_dir)
    props = []
    for p in sorted((lane / "data" / "notes").glob("*.md")):
        if a.chapter and p.stem != a.chapter:
            continue
        props += parse_notes(p.read_text(encoding="utf-8"), p.stem)
    if a.limit:
        props = props[:a.limit]

    results, extraction_failures = [], []
    for prop in props:
        extracted = extract_promises(prop)
        if not extracted["ok"]:
            # 抽取阶段没读懂——不能当成「确认无承诺」一笔带过（brief §3）。
            extraction_failures.append({
                "proposal": prop,
                "reason": f"parse_ok={extracted['parse_ok']} "
                          f"stopped_reason={extracted['stopped_reason']}",
            })
            continue
        for pr in extracted["promises"]:
            r = verify_promise(pr, prop, lane_dir=lane)
            r.update({"proposal": prop, "promise": pr})
            results.append(r)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(results, extraction_failures), encoding="utf-8")
    print(f"审计报告已写 {out}（{len(props)} 条提案 → {len(results)} 条硬承诺，"
          f"{len(extraction_failures)} 条提案抽取阶段失败未被审到）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
