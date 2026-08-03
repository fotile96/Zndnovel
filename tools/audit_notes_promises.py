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

# 区间分隔符全谱：语料实测只出现半角连字号 `-` 与 en dash `–`（`grep` 提案正文
# 得 14 处，另有 36 处在 `## batch` 标题行里、被 `parse_notes` 跳过），但手记是
# 人手写的、随时可能冒出全角减号/波浪号，故一次把常见写法全收进来——漏一种
# 就等于把整族承诺静默截成首个 id（缺陷 1 的原始形态）。
RANGE_DASHES = "-–—―‐‑‒−~〜～ー－ｰ"
_D = re.escape(RANGE_DASHES)
# 行内、非跨换行：提案是逐行罗列的「- id ...」，跨行会把下一条无关的行号吞进来。
ID_RE = re.compile(rf"\bid[ \t]*([0-9０-９、,， \t{_D}]+)")
# 单个 id 或一段区间；`finditer` 依次消费，天然保持正文里的出现顺序，且区间的
# 两个端点不会被当成两个孤立 id 重复计入。
_TOKEN_RE = re.compile(rf"([0-9]+)(?:[ \t]*[{_D}][ \t]*([0-9]+))?")
NUM_RE = re.compile(r"[0-9]+")
_Z2H_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

# 单条提案展开后的 id 总数上限。超限**截断并留痕**（`prewire_ids_detail` 的
# `notes`），绝不静默丢弃——本项目反复吃过「静默丢弃」的亏。
PREWIRE_ID_LIMIT = 100
# 单个区间的物化上限：`id 1–99999999` 这类笔误若照直展开会把进程拖死。跨度
# 超限的区间不展开、只保留两端并留痕（语料实测最大跨度 72，离这条线很远）。
MAX_RANGE_SPAN = 10000

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


def prewire_ids_detail(proposal, *, limit=PREWIRE_ID_LIMIT):
    """从提案正文里抽出显式写明的 id，**区间写法照实展开**。

    提案格式实况有两类：逐个罗列（`- id 7327、7329、7332`）与区间
    （`- id 17050–17121 等`）。过去 `ID_RE` 的字符类不含破折号，区间只截到
    首个 id——于是「19 个标签整族统一落笔」这种承诺，核对时材料里只有 1 行，
    模型只能判「无法判断」。**那是工具制造的假「无法判断」，不是语料证据
    不足**，会直接毒化报告顶部的可信度指标。

    只在单行内抽取（`ID_RE` 不含换行符），并把全角数字归一化为半角后再解析，
    避免把下一行缩进延续行的数字吞进来、或把 `７３２９` 这类全角写法静默丢弃。

    返回 `{"ids", "notes", "truncated", "dropped"}`：
    - `ids`: 去重后按正文出现顺序排列，长度 ≤ `limit`。
    - `notes`: 留痕字符串列表（超上限截断、区间起止倒置、跨度过大拒绝展开）。
      **凡是有 id 没被纳入 `ids`，这里必有一条对应的记录**——不允许静默丢弃。
    - `truncated` / `dropped`: 是否触发上限、被挡在外面的 id 个数。
    """
    seen, out, notes = set(), [], []
    dropped = 0
    for m in ID_RE.finditer(proposal.get("body", "")):
        normalized = m.group(1).translate(_Z2H_DIGITS)
        for t in _TOKEN_RE.finditer(normalized):
            a = int(t.group(1))
            if t.group(2) is None:
                candidates = (a,)
            else:
                b = int(t.group(2))
                if b < a:
                    # 起止倒置多半是笔误；照 range(a, b+1) 展开会得到空集，
                    # 等于把两个写明的 id 一起吞掉——保留两端并留痕。
                    notes.append(f"区间 {a}{RANGE_DASHES[0]}{b} 起止倒置，未展开，只保留两端")
                    candidates = (a, b)
                elif b - a + 1 > MAX_RANGE_SPAN:
                    notes.append(f"区间 {a}{RANGE_DASHES[0]}{b} 跨度 {b - a + 1} 超过 "
                                 f"{MAX_RANGE_SPAN}，拒绝展开，只保留两端")
                    candidates = (a, b)
                else:
                    candidates = range(a, b + 1)
            for v in candidates:
                if v in seen:
                    continue
                if len(out) >= limit:
                    dropped += 1
                    continue
                seen.add(v)
                out.append(v)
    if dropped:
        notes.append(f"正文 id 展开后超过上限 {limit}，已截断：保留前 {len(out)} 个，"
                     f"另有 {dropped} 个未纳入（不是没抽到，是被上限挡下）")
    return {"ids": out, "notes": notes, "truncated": bool(dropped), "dropped": dropped}


def prewire_ids(proposal, *, limit=PREWIRE_ID_LIMIT):
    """`prewire_ids_detail` 的便捷形式，只取 `ids`（留痕见 detail 版）。"""
    return prewire_ids_detail(proposal, limit=limit)["ids"]


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


def _rounds_kw(max_rounds):
    """把 `--max-rounds` 折成传给 `run_with_tools` 的 kwargs。

    `None` → **不传**，保持 `run_with_tools` 自己的默认（6）不变——默认行为
    不因为多了这个参数而改变。
    """
    return {} if max_rounds is None else {"max_rounds": max_rounds}


def extract_promises(proposal, *, runner=None, max_rounds=None):
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
      - `prewire_note`: `prewire_ids_detail` 的留痕（区间截断/倒置等），空串
        表示无异常；`render_report` 会把非空值印进报告。
      - `quote` / `quote_verified`：见 `_quote_found`。
    - `parse_ok`: 模型输出是否被成功解析为 JSON object（见 `_ask_json`）。
    - `stopped_reason`: 透传自 `run_with_tools`，`"finished"|"max_rounds"|"incomplete"`。
    - `ok`: `parse_ok and stopped_reason == "finished"` 的便捷汇总——**只有
      `ok is True` 时，`promises == []` 才能读作「确认无承诺」**；`ok is
      False` 时（解析失败，或轮次/输出被截断）无论 `promises` 是什么都应计入
      「无法判断」，不得当成 clean 计数。
    """
    detail = prewire_ids_detail(proposal)
    pre = detail["ids"]
    prewire_note = "；".join(detail["notes"])
    body = (f"【提案标题】{proposal['title']}\n【提案正文】\n{proposal['body']}\n"
            f"【正文里显式写明的 id】{pre}"
            + (f"\n【id 抽取留痕】{prewire_note}" if prewire_note else ""))
    data, res, parse_ok = _ask_json(
        runner, [{"role": "system", "content": PROMISE_SYS},
                 {"role": "user", "content": body}],
        purpose=f"audit-promise-extract:{proposal['chapter']}"
                f":b{proposal['batch']}:#{proposal['num']}",
        **_rounds_kw(max_rounds))
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
        out.append({
            "kind": p.get("kind", ""),
            "ids": model_ids if ids_source == "model" else pre,
            "ids_source": ids_source,
            "prewire_ids": pre,
            "ids_invalid": invalid,
            "prewire_note": prewire_note,
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

给你的材料是：承诺原话、**该承诺所在提案的完整正文**、以及相关行的日文原文与
现行中文译文。承诺的具体内容常常不在那句原话里，而在正文后面的表格/清单/逐条
对照表里——判定前务必读完正文。若正文标注了「已截断」，说明你看到的不是全文，
这种情况下若截断部分正是判据所在，请判「无法判断」并说明。

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

# 拼进核对提示的提案正文长度上限（字符）。语料实测提案正文中位数约 400 字符、
# 最长约 4k，故这条线在正常情形下不开火；它挡的是异常长的提案把单次请求撑爆。
PROPOSAL_BODY_LIMIT = 6000


def _clip_body(body, limit=PROPOSAL_BODY_LIMIT):
    """按字符数截断提案正文，**超限时显式标注**而不是无声截掉。

    静默截断在这里格外阴险：模型会拿着半截表格照常给出「已履行」，而报告里
    没有任何痕迹说明它其实没看到后半段。标注之后，`VERIFY_SYS` 明确要求模型
    在判据落在截断段时改判「无法判断」，人也能在 sidecar 里查到这一条。
    """
    body = body or ""
    if len(body) <= limit:
        return body, False
    return (body[:limit] +
            f"\n\n［⚠ 提案正文过长已截断：原 {len(body)} 字符，此处仅含前 {limit} 字符］",
            True)


def _forced_cannot_tell(promise, reason):
    """构造一条强制降级的「无法判断」结果（T5 brief §1/§2）。

    供 `verify_promise` 内部的机械闸早退（取材异常、材料为空）与
    `main()`/`rerun_gated()` 里对单条 promise 处理异常的兜底共用同一形状，
    保证无论在哪个环节被拦下，下游（`render_report`）看到的结果结构都一致：
    不会因为字段缺失而在统计/展示时被跳过或误判。**两类调用方的 `reason`
    文案不同**（机械闸带 `GATE_MARK`、异常兜底带 `EXC_MARK`，见二者定义处
    的说明）——本函数只管结果形状，不替调用方决定文案，语义上的「主动判定
    vs 崩溃兜底」区分完全由调用方传入的 `reason` 承载。
    """
    return {
        "verdict": "无法判断",
        "evidence_ids": [],
        "evidence_ids_invalid": [],
        "reason": reason,
        "used_tools": False,
        "reasoning_text": "",
        "body_truncated": False,
        "quote_verified": promise.get("quote_verified"),
        "ids_invalid": promise.get("ids_invalid") or [],
    }


def verify_promise(promise, proposal, *, lane_dir=None, runner=None, max_rounds=None):
    """步骤 2：预拼为主、工具兜底。

    `max_rounds`：透传给 `run_with_tools` 的轮次预算，`None` 即沿用它自己的
    默认（6）。**提高它只是给模型更多预算，五条机械闸的语义一分不变**——
    （3 条在本函数主体：stopped_reason/tool_errors/工具未调用；2 条是预拼
    路径的早退闸——见下方「预拼路径的两条早退闸」；总数见 `is_gated` 附近
    的核对，`--rerun-gates` 帮助文本与本处口径必须一致）
    首轮全量审计里 110 条「无法判断」中有 48 条的 reason 是
    `stopped_reason=max_rounds`，那是预算耗尽而非证据不足，混进「无法判断
    占比」这项可信度指标里会让它高估语料的问题、低估工具的可调空间。正确的
    处置是把预算调大后**定点重跑**（`--rerun-from`），而不是放松闸。

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

    **预拼路径的两条早退闸**（T5 复评 §2）：预拼路径的取材（`call_tool`）
    不经过 `run_with_tools` 内部的 try/except，机械闸②（`tool_errors`）对
    它不生效；这里补两条独立检查，**都在调用模型之前短路返回**（既堵住
    漏洞，也省下一次注定判不出东西的真实 API 调用——全量真跑按次计费）：
    - 取材本身抛异常（`_ledger()`/`_zh()` 文件缺失等系统性故障）：强制
      「无法判断」，口径与机械闸②一致。
    - 取材成功但取回的行**全部**没有译文（`zh` 为空/None）：材料不足以
      判定任何履行情况，同样强制「无法判断」。**只在全空时开火**——部分
      行有译文、部分没有是正常情形（该批可能只译了一部分），不得据此误伤
      （见 `test_gate4_partial_empty_zh_does_not_fire`）。
    """
    ids = promise.get("ids") or []
    tool_fallback_path = not ids
    if ids:
        try:
            lines = call_tool("get_lines", {"ids": ids}, lane_dir=lane_dir)["lines"]
        except Exception as e:
            return _forced_cannot_tell(
                promise,
                f"机械闸：预拼取材阶段失败（{type(e).__name__}: {e}），"
                f"模型未被调用")
        if all(not (r.get("zh") or "").strip() for r in lines):
            return _forced_cannot_tell(
                promise,
                "机械闸：预拼取回的行全部没有译文（zh 为空/None），"
                "材料不足以判定履行情况，模型未被调用")
        ctx = "\n".join(
            f"id {r['id']}（{r['chapter']}）\n  原文：{r['jp']}\n  译文：{r['zh']}"
            for r in lines)
        kw = {}
    else:
        ctx = "（提案未写明 id，请用工具自行查找相关行）"
        kw = {"tool_names": TOOL_NAMES, "lane_dir": lane_dir}
    # 缺陷 2：提案正文过去根本不传，于是「承诺内容住在正文里」（表格、清单、
    # 逐条对照表）的一律核不了——模型看得见 quote 那句「本批落笔如下」，却看
    # 不见后面那张 19 行的译法表，判「无法判断」既正确又诚实，但那份不确定
    # 完全是我们自己造成的。
    body_text, body_truncated = _clip_body(proposal.get("body", ""))
    user = (f"【承诺】{promise.get('kind')}：{promise.get('quote')}\n"
            f"【出处】{proposal['chapter']} b{proposal['batch']} #{proposal['num']}"
            f" —— {proposal['title']}\n"
            f"【提案正文】\n{body_text}\n"
            f"【相关行】\n{ctx}")
    data, res, parse_ok = _ask_json(
        runner, [{"role": "system", "content": VERIFY_SYS},
                 {"role": "user", "content": user}],
        purpose=f"audit-promise-verify:{proposal['chapter']}"
                f":b{proposal['batch']}:#{proposal['num']}",
        **kw, **_rounds_kw(max_rounds))

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
    elif tool_fallback_path and not tool_calls:
        gate = "机械闸：开了工具但模型一次都没调用，判断可能是凭空作答"
    if gate:
        verdict = "无法判断"
        reason = gate

    # 缺陷 3：过去这里用 `isinstance(i, int)` 过滤，会**静默丢弃**字符串型 id
    # （模型给 `"7327"` 很常见），而抽取阶段的 `_clean_model_ids` 明明接受纯
    # 数字字符串——同一个模块对同一种数据两套口径，结果是报告印出「依据行：
    # （无）」而模型的 reason 里明明点了行号。这里复用同一个清洗函数统一口径，
    # 非法项照样留痕（`evidence_ids_invalid`）而不是无声消失。
    raw_ev = data.get("evidence_ids") or []
    if not isinstance(raw_ev, list):
        raw_ev = [raw_ev]
    evidence_ids, evidence_invalid = _clean_model_ids(raw_ev)

    return {
        "verdict": verdict,
        "evidence_ids": evidence_ids,
        "evidence_ids_invalid": evidence_invalid,
        "reason": reason,
        "used_tools": tool_fallback_path or bool(tool_calls),
        "reasoning_text": res.get("reasoning_text", ""),
        "body_truncated": body_truncated,
        # 决策（brief §4）：quote_verified/ids_invalid 不用于改变 verdict——
        # 它们是提案抽取阶段的留痕信号，不代表履行核对本身出了问题；这里
        # 原样透传，交给 render_report 在报告里作为「留痕不改判」的提示项，
        # 见 render_report 的处理。
        "quote_verified": promise.get("quote_verified"),
        "ids_invalid": promise.get("ids_invalid") or [],
    }


ORDER = {"未履行": 0, "无法判断": 1, "已履行": 2}

# 「未履行」的人工分类模板（Task 9，spec §4.5）：四类判据各一句话，供抽核
# 的人照着填。**机器不做归类**——审计模型刚下完「未履行」判定，再让它自我
# 质疑是否过严，等于同一口气里既下判定又推翻判定，不可靠；这里只把机械可
# 得的证据（车道 `patches.jsonl` 回改记录）摆出来，分类判断留给人。
CLASSIFICATION_TEMPLATE = """## 人工分类清单模板（抽核时逐条填写，机器不做归类）

「未履行」实际混着四类性质不同的情形，抽核时请对每条选定其一：

- **真违约**：译文没有落实手记声称已做的事——需要改译文。
- **比对过严**：模型字面匹配过死，其实已满足承诺（如趋向补语/近义替换已
  蕴含承诺内容）——无需改动，是误报。
- **手记过时**：该承诺已被后续 glossary 版本裁定取代，译文才是对的——
  该改的是手记而非译文。下方若某条依据行带⚠标注（回改车道 recall 记录），
  是这一类的机械线索（前提：手记写于该裁定之前）。
- **措辞过宽**：手记写「一律」但实指某句族，非真正通则——酌情澄清手记
  措辞，译文不必因此改动。

"""


def load_patches(lane_dir):
    """读车道 `<lane_dir>/data/patches.jsonl`（回改车道，spec §4.5）。

    返回 `{id: [patch, ...]}`；`lane_dir` 为 `None`（调用方未要求做这项核对）
    或文件不存在时返回 `None`。**调用方必须把 `None` 与「检查过、无命中」的
    空字典区分开**——`render_report` 据此决定是否显式播报「未检查」，同
    `check_batch.load_siblings` 的「W4 未启用」纪律（不静默假装检查过）。
    单条 patch 记录形如 `{"id": 7576, "zh": "...", "reason": "review|recall|polish",
    "glossary_v": 8, "ts": "..."}`；同一 id 可能有多条记录，全部保留。
    """
    if lane_dir is None:
        return None
    path = Path(lane_dir) / "data" / "patches.jsonl"
    if not path.exists():
        return None
    idx = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        idx.setdefault(row.get("id"), []).append(row)
    return idx


def _patch_annotations(evidence_ids, patches):
    """对一条「未履行」结果的依据行，呈现车道回改车道的机械证据（不改判）。

    命中 `reason=recall`：该行曾因术语裁定被正式召回——若手记写于裁定之前，
    这条「未履行」可能是「手记过时」而非译文违约。
    命中 `reason=review`：该发现已有 review 回改——本条可能已被处理，构成
    闭环。
    `reason=polish` 等其他值不在这两类标注范围内，不生成标注（既不是
    「过时」也不是「已处理」的机械信号）。
    """
    out = []
    for i in evidence_ids or []:
        for patch in patches.get(i, []):
            v = patch.get("glossary_v")
            if patch.get("reason") == "recall":
                out.append(f"- ⚠ 依据行 {i} 曾因术语裁定被召回（glossary_v={v}）——"
                           f"若本手记写于该裁定之前，此条属「手记过时」而非译文违约")
            elif patch.get("reason") == "review":
                out.append(f"- ✅ 依据行 {i} 已有 review 回改（glossary_v={v}）——"
                           f"本条可能已被处理")
    return out


def render_report(results, extraction_failures=None, lane_dir=None):
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

    `lane_dir`（Task 9，spec §4.5）：车道根，用于读 `<lane_dir>/data/
    patches.jsonl` 交叉核对「未履行」条目的依据行是否被回改车道覆盖过。
    `None`（默认，向后兼容旧调用方式）＝不做这项核对，不呈现任何相关标注、
    也不播报——调用方没要求，不是「查过没查到」。传了 `lane_dir` 但文件
    不存在，则**显式播报**未检查（不静默假装检查过，见 `check_batch.py`
    里 W4 未启用时的做法，同一纪律）。只呈现证据，**不据此改判 verdict、
    不自动归类**——分类判断留给人（见 `CLASSIFICATION_TEMPLATE`）。
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
             f"该比例本身是可信度指标，偏高说明材料或判据不足", "",
             CLASSIFICATION_TEMPLATE]

    patches = load_patches(lane_dir)
    if lane_dir is not None and patches is None:
        lines.append(f"⚠ 回改车道证据核对未执行：`{Path(lane_dir) / 'data' / 'patches.jsonl'}` "
                     f"不存在，下面「未履行」条目**未与回改车道交叉核对**（本次报告不含"
                     f"「手记过时」/「已处理」标注，不代表核对过、无命中）")
        lines.append("")

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
        if r.get("evidence_ids_invalid"):
            lines.append(f"- ⚠ 模型给出的依据行含非法项已丢弃：{r['evidence_ids_invalid']}")
        if pr.get("prewire_note"):
            lines.append(f"- ⚠ id 抽取留痕：{pr['prewire_note']}")
        if r.get("body_truncated"):
            lines.append("- ⚠ 提案正文过长，送模型时已截断（判据若落在截断段，"
                         "该条判定不可尽信）")
        if r["verdict"] == "未履行" and patches:
            lines += _patch_annotations(r.get("evidence_ids"), patches)
        lines.append("")
    return "\n".join(lines)


def _append_jsonl(path, obj):
    """把一条结果原子性地追加进增量落盘 sidecar（T5 brief §1(b)）。

    每条记录各自 open/write/close，不依赖跨迭代保持同一个文件句柄——即使
    进程在写完这一条之后的下一次迭代中途被杀（未预见的异常、被信号杀死
    等 try/except 也接不住的情形），本条已经落盘的记录不会因为缓冲区未
    flush 而丢失。
    """
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# --- 定点重跑（rerun）：只重验上一轮被机械闸拦下/核对阶段异常崩溃的条目 ----
#
# 全量重跑一章 s3s 要 2 小时 48 分，而待重验的只有几十条；更重要的是全量重跑
# 会把上一轮**判出来的结论**一并丢掉重来（既多花钱，又让两轮不可比）。定点重跑
# 读上一轮的 sidecar，只对选中的条目再调一次模型，其余条目原样搬运。

# 五条机械闸（`verify_promise` 内 3 条主体闸 + 预拼路径 2 条早退闸）留下的
# reason 都形如「机械闸：stopped_reason=max_rounds，结论不完整」。这里按
# **字面**匹配，与 `verify_promise` 里生成这些字符串的那 5 行是一对多；
# 改其一必须回来核对 `GATE_MARK` 是否仍然覆盖。
GATE_MARK = "机械闸"
BUDGET_MARK = "max_rounds"

# 复评（T10）：`main()`/`rerun_gated()` 对 `verify_promise` 抛出的未预见异常
# 用 `_forced_cannot_tell` 兜底时，reason 唯独**不带** `GATE_MARK`——这不是
# 疏漏该补上前缀，而是有意为之：机械闸是「模型给出结论、但结构性证据不足，
# 主动把它降级」；异常兜底是「核对流程本身崩溃，压根没跑出结论」，两者性质
# 不同，硬套同一个前缀等于把「崩溃」谎报成「主动判定」（复评原话：不是静默
# 丢弃，是可见但打不动——这条修复要解决的正是「打不动」，不能顺手再把标注
# 也搞错）。但两者又都属于「系统/流程问题，值得重跑」而非「模型看过材料后
# 认为证据不足」——一次真实的 `TimeoutError` 就是最典型的样本，重试大概率
# 就好——所以 `is_gated(gates="all")` 要把两者都选中。
# `EXC_MARK` 是这条判据的锚点：`main()` 里的「核对阶段异常：...」与
# `rerun_gated()` 里的「重跑核对阶段异常：...」都以此为公共子串（后者是前者
# 前面加了「重跑」两个字，`in` 匹配天然兼容）。改任一处异常兜底的文案，必须
# 确保 `EXC_MARK` 仍是其子串，否则该条目会从「all」里静默漏选——重演本次
# 要修的这同一种缺陷。
EXC_MARK = "核对阶段异常"


def load_sidecar(path):
    """读回上一轮 sidecar，返回 `(results, extraction_failures)`。

    非法行（截断的最后一行等）**跳过并留痕到 stderr**，不静默吞掉也不让整个
    重跑因为一行坏 JSON 而拒绝启动——sidecar 本来就是「进程可能中途死亡」的
    产物，末行半截是可预期的。
    """
    results, fails = [], []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception as e:
            print(f"⚠ sidecar 第 {n} 行无法解析，已跳过：{e}", file=sys.stderr)
            continue
        data = row.get("data")
        if row.get("type") == "result":
            results.append(data)
        elif row.get("type") == "extraction_failure":
            fails.append(data)
        else:
            print(f"⚠ sidecar 第 {n} 行 type={row.get('type')!r} 未知，已跳过",
                  file=sys.stderr)
    return results, fails


def is_gated(row, *, gates="max_rounds"):
    """这一条是否是「被机械闸拦下 / 核对阶段异常崩溃」而非「证据不足」。

    `gates="max_rounds"`（默认）只选轮次预算耗尽的那一族——它们是**工具的**
    问题，调大预算就可能收敛；`gates="all"` 放宽到**所有非语料原因**的
    「无法判断」：五条机械闸全部（`verify_promise` 主体 3 条——工具报错、
    开了工具没调用、stopped_reason 未 finished；预拼路径 2 条早退闸——取材
    失败、全无译文）**加上**核对阶段异常兜底（`EXC_MARK`，见其定义处的
    说明）。异常兜底不是机械闸的主动判定而是流程崩溃，语义上不归入
    `GATE_MARK`，但同样值得重跑——`gates="all"` 把两者并列选中，正是本次
    修复要打通的路径（复评样本：一条 `TimeoutError` 曾经连 `gates="all"`
    都捞不到）。
    模型自己判出的「无法判断」永远不入选：那是证据不足，重跑无非再花一次钱。
    """
    if (row or {}).get("verdict") != "无法判断":
        return False
    reason = row.get("reason") or ""
    is_gate = GATE_MARK in reason
    is_exc = EXC_MARK in reason
    if not is_gate and not is_exc:
        return False
    if gates == "all":
        return True
    # max_rounds：维持只选轮次预算耗尽——异常兜底与「工具报错」等其它机械闸
    # 一样，不是预算问题，默认档不选。
    return is_gate and BUDGET_MARK in reason


def rerun_gated(results, *, lane_dir=None, max_rounds=None, gates="max_rounds",
                verify=None, on_result=None):
    """重验选中的条目，返回 `(merged, reran)`。

    **合并不丢条目**：`merged` 与 `results` 等长、同序，未选中的条目原样搬运
    （连同 `proposal`/`promise`），选中的用新结果替换并补回 `proposal`/`promise`。
    单条重验抛异常照旧降级成一条可见的「无法判断」（`_forced_cannot_tell`），
    不允许因为重跑而让一条已存在的记录凭空消失。
    `on_result(row)` 每产出一条（含原样搬运的）调用一次，供调用方增量落盘。
    """
    fn = verify or verify_promise
    merged, reran = [], 0
    for row in results:
        if is_gated(row, gates=gates):
            pr, prop = row.get("promise") or {}, row.get("proposal") or {}
            try:
                new = fn(pr, prop, lane_dir=lane_dir, max_rounds=max_rounds)
            except Exception as e:
                # 异常兜底：reason 含 `EXC_MARK`（"核对阶段异常"）而非
                # `GATE_MARK`——改这行文案前先看 `EXC_MARK` 定义处的说明。
                new = _forced_cannot_tell(
                    pr, f"重跑核对阶段异常：{type(e).__name__}: {e}")
            new.update({"proposal": prop, "promise": pr,
                        "rerun_of": row.get("verdict"),
                        "rerun_prev_reason": row.get("reason")})
            row = new
            reran += 1
        merged.append(row)
        if on_result:
            on_result(row)
    return merged, reran


def _main_rerun(a, lane):
    """`--rerun-from` 分支：读旧 sidecar → 定点重验 → 合并 → 新报告 + 新 sidecar。

    **原 sidecar 绝不被覆盖**：`main()` 每次开跑都会把 `--out` 同名的 `.jsonl`
    截断成空文件，若 `--out` 指回上一轮那份，原始证据在第一行写入之前就已经
    没了（控制器今天是先手工备份才敢重跑）。这里在动任何文件之前先比对绝对
    路径，撞上就拒绝执行——不靠人记得换文件名。
    """
    src = Path(a.rerun_from)
    out = Path(a.out)
    sidecar = out.with_suffix(".jsonl")
    if not src.exists():
        raise SystemExit(f"拒绝执行：--rerun-from 指定的 sidecar 不存在：{src}")
    if src.resolve() == sidecar.resolve():
        raise SystemExit(
            f"拒绝执行：--out 推出的新 sidecar（{sidecar}）就是 --rerun-from 那份"
            f"（{src}）。\n本次运行开跑就会把它截断，上一轮的原始证据将永久丢失。\n"
            f"请给 --out 换一个文件名（如 {out.with_name(out.stem + '-rerun' + out.suffix)}）。")

    results, extraction_failures = load_sidecar(src)
    n_gated = sum(1 for r in results if is_gated(r, gates=a.rerun_gates))
    out.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text("", encoding="utf-8")
    for f in extraction_failures:
        _append_jsonl(sidecar, {"type": "extraction_failure", "data": f})

    merged, reran = rerun_gated(
        results, lane_dir=lane, max_rounds=a.max_rounds, gates=a.rerun_gates,
        on_result=lambda r: _append_jsonl(sidecar, {"type": "result", "data": r}))
    assert len(merged) == len(results)  # 合并不丢条目（护栏，非防御性编程）
    flipped = sum(1 for r in merged if r.get("rerun_of") and r["verdict"] != "无法判断")

    out.write_text(render_report(merged, extraction_failures, lane_dir=lane), encoding="utf-8")
    print(f"定点重跑完成 → {out}（源 {src}：{len(results)} 条结果 / "
          f"{len(extraction_failures)} 条抽取失败；命中闸 {n_gated} 条，"
          f"实重验 {reran} 条，其中 {flipped} 条这次判出了结论；"
          f"新增量结果见 {sidecar}，原 sidecar 未改动）")
    return 0


def main(argv=None):
    """入口：抽取 → 核对 → 报告，附**逐条异常隔离**与**增量落盘**。

    这两条是 T5 复评发现的洞（brief §1）：`verify_promise`（或抽取阶段）
    对任意一条 promise/提案抛出未捕获异常，过去会让整个 `main()` 崩溃——
    `render_report` 从未被调用，报告文件根本不存在，连前面已经算出、
    已经花钱调用过 API 的结果也一起从存在中消失。修法：
    (a) 每条提案的抽取、每条 promise 的核对各自套 try/except；失败变成一条
        可见的「无法判断」结果（`_forced_cannot_tell`／抽取失败列表），
        reason 里带上异常类型与消息，不允许被静默吞掉或计入「已履行」。
    (b) 每算出一条结果/一条抽取失败，立刻 `_append_jsonl` 写进与 `--out`
        同名的 `.jsonl` sidecar——真实发生且已计费的调用不能因为进程后面
        才发生的意外而在结论侧凭空消失（`data/api_ledger.jsonl` 记的是
        调用账，这个 sidecar 记的是结论账）。sidecar 在每次运行开始时清空，
        避免跨运行的行混在一起。
    """
    import argparse
    from tools.cluster_notes import parse_notes
    ap = argparse.ArgumentParser(description="手记「承诺-履行」审计")
    ap.add_argument("--lane-dir", default="pilot/lanes/opus")
    ap.add_argument("--chapter", default=None, help="只审某一章，省略则全部")
    ap.add_argument("--limit", type=int, default=0, help="只审前 N 条提案（0=不限）")
    ap.add_argument("--out", default="work/out/audit-notes-promises.md")
    ap.add_argument("--max-rounds", type=int, default=None,
                    help="透传给 run_with_tools 的轮次预算（省略=沿用其默认 6）。"
                         "调大只是给模型更多预算，机械闸语义不变")
    ap.add_argument("--rerun-from", default=None, metavar="SIDECAR.jsonl",
                    help="定点重跑：读上一轮的 sidecar，只重验被机械闸拦下的条目，"
                         "其余原样搬运；不重新解析手记，不覆盖原 sidecar")
    ap.add_argument("--rerun-gates", choices=["max_rounds", "all"],
                    default="max_rounds",
                    help="重跑选谁：max_rounds=只选轮次预算耗尽的（默认）；"
                         "all=五条机械闸 + 核对阶段异常兜底 全选"
                         "（即所有非语料原因的无法判断）")
    a = ap.parse_args(argv)
    lane = Path(a.lane_dir)

    if a.rerun_from:
        return _main_rerun(a, lane)

    props = []
    for p in sorted((lane / "data" / "notes").glob("*.md")):
        if a.chapter and p.stem != a.chapter:
            continue
        props += parse_notes(p.read_text(encoding="utf-8"), p.stem)
    if a.limit:
        props = props[:a.limit]

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sidecar = out.with_suffix(".jsonl")
    sidecar.write_text("", encoding="utf-8")

    results, extraction_failures = [], []
    for prop in props:
        try:
            extracted = extract_promises(prop, max_rounds=a.max_rounds)
        except Exception as e:
            # (a) 抽取阶段异常隔离：这一条提案没读懂，但不能拖垮整个循环。
            failure = {"proposal": prop,
                       "reason": f"抽取阶段异常：{type(e).__name__}: {e}"}
            extraction_failures.append(failure)
            _append_jsonl(sidecar, {"type": "extraction_failure", "data": failure})
            continue
        if not extracted["ok"]:
            # 抽取阶段没读懂——不能当成「确认无承诺」一笔带过（brief §3）。
            failure = {
                "proposal": prop,
                "reason": f"parse_ok={extracted['parse_ok']} "
                          f"stopped_reason={extracted['stopped_reason']}",
            }
            extraction_failures.append(failure)
            _append_jsonl(sidecar, {"type": "extraction_failure", "data": failure})
            continue
        for pr in extracted["promises"]:
            try:
                r = verify_promise(pr, prop, lane_dir=lane,
                                   max_rounds=a.max_rounds)
            except Exception as e:
                # (a) 核对阶段异常隔离：单条 promise 处理失败必须变成一条
                # 可见结果、归入「无法判断」侧，绝不能静默消失或被误计入
                # 「已履行」，也绝不能让异常继续往上冒杀掉整个循环——这正是
                # 复评复现的场景（第 2 条提案的 verify_promise 抛异常导致
                # rc=None、报告不存在、连第 1 条已算出的结果都一起没了）。
                # T10 复评：reason 含 `EXC_MARK`（"核对阶段异常"）而非
                # `GATE_MARK`——这不是疏漏，改这行文案前先看 `EXC_MARK`
                # 定义处的说明，否则这条又会从 `is_gated` 的可重跑集合里
                # 静默漏选。
                r = _forced_cannot_tell(
                    pr, f"核对阶段异常：{type(e).__name__}: {e}")
            r.update({"proposal": prop, "promise": pr})
            results.append(r)
            # (b) 增量落盘：这一条已经花掉的调用（若走了模型）产出的结论
            # 立刻写盘，不等全循环跑完才落地。
            _append_jsonl(sidecar, {"type": "result", "data": r})

    out.write_text(render_report(results, extraction_failures, lane_dir=lane), encoding="utf-8")
    print(f"审计报告已写 {out}（{len(props)} 条提案 → {len(results)} 条硬承诺，"
          f"{len(extraction_failures)} 条提案抽取阶段失败未被审到；"
          f"增量结果见 {sidecar}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
