"""彩野测试（P3 spec §5）：让从未见过原文的外部模型扮演「只靠梗概续听故事的读者」，
只喂 压缩前缀（skeleton/cards.zh.yaml 卡组梗概＝游戏自身的『あらすじ』机制）＋
本段中文译文（零日文原文），回答剧情理解题；答错处＝译文或压缩丢了信息，且丢的
恰是真实玩家会丢的。判分由第二次 API 调用完成。advisory 工具：恒 exit 0，
结论供段末人工验收参考。--dry-run 只组装统计、零 API 调用。"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import yaml

from tools.pipelib import REPO, read_jsonl
from tools.resolve import resolve_map
from tools.api_client import chat

READER_SYS = ("你在听人讲一个故事。你只知道两部分信息：①此前剧情的卡片梗概；"
              "②最新一段正文。只根据给定文本回答问题，文本里没有的就答「不知道」，"
              "不要编造，不要使用任何文本之外的知识。用中文作答：把问题涉及的每个点"
              "都完整答到，但只写要点本身，不要逐句复述或大段抄录原文。")
JUDGE_SYS = ("你是判分员。根据【问题】【标准答案】【受试回答】判定：对／部分对／错。"
             "判定标准：受试回答答出了标准答案里的主要事实点，即使措辞不同也判「对」；"
             "只答出部分主要事实点、或遗漏了次要细节，判「部分对」；关键事实错误、"
             "答非所问、或答「不知道」而标准答案本可从文本推出，判「错」。"
             "只输出一行，格式：判定|一句话依据。")

# P3（b36–339）开工前就已译完的章节白名单——这是唯一允许"确知早于全部段"的例外，
# 不是 fallback 默认值。config/segments.yaml 的 9 段 chapters 只覆盖 P3 范围内的
# 章节，s0f/s1s/s1f（对应 pilot/lanes/opus/data/batches.jsonl 的 b1–32，序章+第1章
# 故事层/现实层）早于 b36 就已入线，故 segments.yaml 里查不到它们——这与"查不到
# 章节=未知/无法判定"是两回事，必须显式列出来区分（P3 devwave1 task-7 复评 M1
# 修复：之前 `chapter_max_seg.get(ch, 0)` 的 fallback 把"查不到"和"确知最早"混为
# 一谈，若未来某个真正未知/晚期的章节短码意外没被 segments.yaml 收录，会被这条
# fallback 静默当作段 0 纳入前缀——方向反了）。任何不在这个白名单、也不在
# segments.yaml chapters 里的章节短码，一律按"未知→默认排除"处理。
PRE_P3_CHAPTERS = {"s0f", "s1s", "s1f"}


def _chapter_max_seg(segs) -> dict:
    """章节短码 → 该章节出现过的最晚段号。同一章节可能横跨多段（如 s3s 横跨
    seg2/seg4、s4s 横跨 seg3/seg6，剧情来回跳章的实况），保守取最晚——宁可让
    卡组前缀薄一点，也不把还没轮到的段落错纳成"此前"（P3 devwave1 task-7
    Critical 修复：反剧透闸）。这里只登记 segments.yaml 里实际出现过的章节；
    没出现的章节不在这个表里——是否"早于全部段"由 PRE_P3_CHAPTERS 白名单单独
    判定，不用这张表的 fallback 值（见 PRE_P3_CHAPTERS 注释）。"""
    out = {}
    for s in segs:
        for ch in s.get("chapters", []):
            out[ch] = max(out.get(ch, 0), s["seg"])
    return out


def assemble_context(label: str, lane_dir: Path, repo: Path = REPO):
    segs = yaml.safe_load((repo / "config" / "segments.yaml").read_text(encoding="utf-8"))
    hit = next((s for s in segs if s["label"] == label), None)
    if hit is None:
        raise SystemExit(f"未知段 label：{label}")
    lo, hi = hit["batches"]
    cur_seg = hit["seg"]
    data = Path(lane_dir) / "data"
    batches = {r["batch"]: r for r in read_jsonl(data / "batches.jsonl")}
    fwd = read_jsonl(data / "forward.jsonl") if (data / "forward.jsonl").exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    zh = resolve_map(fwd, pat)
    lines, missing = [], 0
    for n in range(lo, hi + 1):
        if n not in batches:
            continue
        for i in batches[n]["ids"]:
            if i in zh:
                lines.append(zh[i])
            else:
                missing += 1

    # 反剧透闸：卡组前缀只取「严格早于当前段」的卡——不是"当前段及之前"。
    # card_chapter.yaml 是 card→章节短码 的静态映射（推导过程见该文件头注释，
    # 不在运行时解析 lua）；查不到章节的卡默认排除（安全方向，见该文件说明）。
    chapter_max_seg = _chapter_max_seg(segs)
    card_chapter = yaml.safe_load(
        (repo / "config" / "card_chapter.yaml").read_text(encoding="utf-8")) or {}

    def is_before_cur_seg(card_num) -> bool:
        ch = card_chapter.get(card_num)
        if ch is None:
            return False  # 无法归章 → 默认排除
        if ch in chapter_max_seg:
            return chapter_max_seg[ch] < cur_seg
        # 章节没出现在 segments.yaml 任何段的 chapters 里：只有显式白名单里的
        # "确知早于全部段"章节才算通过，其余一律按"未知→默认排除"（安全方向，
        # 不再用 .get(ch, 0) 那种把"查不到"悄悄当"最早"的 fallback）。
        return ch in PRE_P3_CHAPTERS

    cards = yaml.safe_load((repo / "skeleton" / "cards.zh.yaml").read_text(encoding="utf-8"))
    prior_cards = [c for c in cards if is_before_cur_seg(c["card"])]
    prefix = "\n\n".join(f"【卡{c['card']}·{c.get('title_zh', '')}】\n{c.get('body_zh', '')}"
                         for c in prior_cards)
    ctx = ("＝＝ 此前剧情的卡片梗概 ＝＝\n\n" + prefix
           + "\n\n＝＝ 最新一段正文 ＝＝\n\n" + "\n".join(lines))
    return ctx, missing


# 报告里 CoT 摘要的截断长度。目的是「一眼看出受试者是从译文里读出来的还是猜的」
# ——开头这几百字通常就是它在定位/引用原文的过程，够判断了；全文动辄数千字，贴进
# 报告反而淹没作答与判分。
COT_EXCERPT_CHARS = 300


# CoT 遥测（原名「机械分诊」，2026-08-02 经 SEG-1 首次真实全跑（15 题）证伪后
# **降级**：不再输出任何自动判定，只保留测量值本身）。
#
# 原设计（task-10 复评采纳）：判分为「对」时，若 CoT 命中犹豫词、或回答与上下文
# 有 ≥12 字逐字重合，就打 `⚠ 存疑：可能照抄未理解`——意图是把一次人肉观察
# （seg1-s2 q4：判「对」但 CoT 写「需确认」，实为照抄未理解）固化成可复现信号。
#
# **证伪数据**（SEG-1，15 题）：打了 **10 个标记，全部落在「对」上**（对 10/13＝
# 77%），而两条「部分对」**零标记**——与判分员自己的疑虑**反相关**，无区分力。
# 构成：仅犹豫词 5（大概×4、需确认、应该是）、仅重合 3（13/15/17 字）、两者都有
# 2（12/19 字）。**致命的一条**：q4——分诊标记当初就是为它设计的——**本轮零
# 标记**：同一道题、更完整的上下文，标记反而消失。
#
# **根因**：标记键控在模型 **run-to-run 可变的私有推理文本**（reasoning_text）
# 上。这正是当初评审警告过的原则——「不该让分数挂钩一个不稳定的私有产物」——
# 被用在了判分上，却没用在标记自身。在 n=15 上重新标定也救不回来：AND 化（犹豫
# 词与重合都命中才打标）只剩 2 个标记，仍会漏掉 q4——问题在假设本身，不在阈值。
#
# 完整记录见 `.superpowers/sdd/2026-08-02-p3-devwave1/progress.md`（搜「机械
# 分诊标记不成立」）。**降级结论：判定去掉，测量留下**——下面两个常量此后只作为
# `cot_signals()` 报告行的原始测量口径使用，不再驱动任何自动判定、不再输出
# 「存疑」「可能」这类带结论的措辞。看到这份现成的犹豫词表/阈值，请不要凭直觉
# 把判定加回去——上面这组数字就是加回去会复现的失败模式。
HESITATION_MARKERS = ("需确认", "不确定", "猜", "大概", "应该是")
VERBATIM_MIN = 12                 # 逐字重合的测量下限：低于此值一律报「无」
VERBATIM_PROBE_MAX = 400          # 延伸探测上限，纯粹为了给成本封顶


def _strip_ws(s: str) -> str:
    return "".join(s.split())


def _longest_verbatim_span(answer: str, ctx: str) -> int:
    """受试回答里**逐字出现在上下文中**的最长连续跨度（去空白后按字符计）。

    先用 VERBATIM_MIN 长的窗口做廉价筛（绝大多数起点会被直接否掉），命中了再逐字
    延伸。上下文 3.5 万字符 × 回答几百字符，实测毫秒级。"""
    a, c = _strip_ws(answer), _strip_ws(ctx)
    n, best = len(a), 0
    if not a or not c:
        return 0
    for i in range(n):
        if n - i <= best or n - i < VERBATIM_MIN:
            break
        if a[i:i + VERBATIM_MIN] not in c:
            continue
        L = VERBATIM_MIN
        cap = min(VERBATIM_PROBE_MAX, n - i)
        while L < cap and a[i:i + L + 1] in c:
            L += 1
        best = max(best, L)
    return best


# 判定词表。匹配一律用 `startswith`，**在此前提下词表顺序无关**
# （`"部分对".startswith("对")` 为 False）——把顺序颠倒的变异全绿即证。
# 顺序只在有人把匹配改成 `in` 时才变成必需：那时「部分对」会命中「对」。
# 之所以把这段写下来，是因为初版注释断言「顺序反了会全判成对」，而那在当前实现里
# 是个**不存在的风险**；一条声称在防守、实际不防守的注释比没有注释更坏。
# 单改顺序、或单改 `in`，测试都仍绿；**两者同时改才红**（已实测）——长词在前是对
# `in` 化改写的冗余防护，保留。
VERDICT_WORDS = ("部分对", "对", "错")


def _verdict_head(verdict: str) -> str:
    """判分行格式契约是「判定|一句话依据」，取判定部分。

    格式完全由 JUDGE_SYS 提示词约束，模型随时可能漂移（`**对**|…`、`判定：对|…`、
    全角竖线、只回两个字）。此前用「切分后**恰等于**『对』」做判据，任何一种漂移
    都会让 `is_correct` **静默判错**——一个不报警的失效（终审 M3）。故这里把常见
    装饰（粗体星号、前缀标签、空白）一并剥掉，并认全角竖线。

    ⚠ 2026-08-05 又逮到一种：`判定|对|…`——模型把字面词「判定」当成了第一字段。
    只看第一字段就会得到「判定」，`is_correct` 随之静默判否（seg5 q3 实例，人眼读
    报告是「对」、机械口径是「不对」）。加固方式**不是**再补一条剥前缀的正则——那
    只会等下一种写法；改成**逐字段找已知判定词**，并让「一个都找不到」这件事
    可被上层区分（见 parse_verdict）。"""
    for field in re.split(r"[|｜]", verdict):
        head = field.replace("*", "").replace("＊", "").strip()
        head = re.sub(r"^[^：:]{0,10}[：:]\s*", "", head).strip()
        for w in VERDICT_WORDS:
            if head.startswith(w):
                return head
    return ""


def parse_verdict(verdict: str):
    """→ "对" / "部分对" / "错"；**解析不出来返回 None**。

    None 与「错」必须分开：前者是「这行判分没读懂」，后者是「判分员说答错了」。
    合并二者正是本函数上一版的失效形态——把格式漂移静默算成非「对」。"""
    head = _verdict_head(verdict)
    for w in VERDICT_WORDS:
        if head.startswith(w):
            return w
    return None


def is_correct(verdict: str) -> bool:
    """判分是否为「对」。注意「对」是「部分对」的后缀——必须先匹配长词。"""
    return parse_verdict(verdict) == "对"


def cot_signals(answer: str, cot: str, ctx: str) -> str:
    """本题的 CoT 遥测行内容：CoT 里出现的犹豫词、回答与上下文的最长逐字重合
    字数。这两个数字只是**测量值**，不是判定——不用「存疑」「可能」这类带结论
    的措辞，也不看判分是「对」「部分对」还是「错」，每一题都原样输出（判分与
    遥测是否有信号并无必然关系，见上方常量定义处的降级记录）。"""
    hits = [m for m in HESITATION_MARKERS if m in cot]
    hesitation = "、".join(hits) if hits else "无"
    span = _longest_verbatim_span(answer, ctx)
    verbatim = f"{span} 字" if span >= VERBATIM_MIN else "无"
    return f"犹豫词 {hesitation} ｜ 与上下文最长逐字重合 {verbatim}"


def load_qa(path, segment: str) -> list:
    """读题库并**校验它绑定的正是本段**（终审 I4）。

    题库与段零绑定时，拿 seg1 的题库跑 seg2–seg9 实测全部 rc=0 静默接受——而
    seg2 的卡组前缀恰好含 seg1 全部 6 张答案卡（41/44/45/46/58/134），受试模型
    一行译文不看、只读前缀卡即可全对，报告全绿被读成「本段译文没丢信息」。这
    正是 task-7 花两轮修掉的恒绿失效从另一个入口原样复活，故：题库顶层必须写
    `segment:`，不符即报错退出；顶层裸列表（无绑定的老式题库）同样拒收——
    「查不到绑定」不能当「绑定正确」，与 assemble_context 的未知即排除同向。"""
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if isinstance(doc, list):
        raise SystemExit(
            f"{path}：老式无绑定题库（顶层是裸列表）。请改成 "
            f"`segment: <段label>` + `questions:` 两层结构——题库不绑定段，"
            f"跨段误用会静默全绿。")
    if not isinstance(doc, dict) or "segment" not in doc or "questions" not in doc:
        raise SystemExit(f"{path}：题库结构须为 `segment:` + `questions:` 两个顶层键。")
    if doc["segment"] != segment:
        raise SystemExit(
            f"题库 {path} 绑定的是段 {doc['segment']!r}，与 --segment {segment!r} 不符。"
            f"别段的题库不能顶替：上一段的答案往往整张躺在本段的前缀卡里，"
            f"跑出来必是恒绿假信号。请为 {segment} 单独出题。")
    qs = doc["questions"] or []
    if not qs:
        raise SystemExit(f"{path}：questions 为空。")
    return qs


def _cot_excerpt(text: str, limit: int = COT_EXCERPT_CHARS) -> str:
    """CoT 摘要：压掉换行（报告里是单行列表项），超长截断并标注原始长度。"""
    if not text:
        return "（无 CoT：模型未返回 reasoning_text）"
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return f"{flat[:limit]}……（共 {len(flat)} 字，已截断）"


def main(argv=None, *, stream_transport=None, api_key=None, ledger_path=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", required=True)
    ap.add_argument("--qa", required=True)
    ap.add_argument("--lane-dir", required=True)
    ap.add_argument("--repo", default=None, help="仅测试用：覆盖仓库根")
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default=None, help="覆盖默认 provider 模型，如 deepseek-v4-flash")
    ap.add_argument("--timeout", type=int, default=None,
                    help="逐 chunk 静默超时（秒），透传给 api_client")
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--effort", default=None,
                    choices=["none", "minimal", "low", "medium", "high", "xhigh", "max"],
                    help="reasoning.effort，透传给 api_client（默认走其 DEFAULT_EFFORT）")
    a = ap.parse_args(argv)
    repo = Path(a.repo) if a.repo else REPO
    qa_path = Path(a.qa)
    if not qa_path.exists():
        # runbook §5 第 3 项 / handoff 段末清单第 3 项明文：题库由开发轨按段提供，
        # 不存在就跳过并记台账——不是失败，只是这段的题库还没产出。此前直接
        # FileNotFoundError 崩溃，与文档许诺的行为不符（M-park P3）。
        # rc 特意选一个既非 0（不能看起来像"跑完且全部通过"）也非其余错误路径
        # 常用的 1（缺 key/段不符等真失败）的值，段末台账脚本可用它单独识别
        # 「跳过」而不是与「成功」或「配置错误」混淆。
        print(f"!! 跳过：题库 {qa_path} 不存在——本段题库尚未产出，彩野测试跳过。"
              f"这不是失败：请把这次跳过原样记进段末台账（哪一段、期望路径），"
              f"待题库补齐后再补跑一次。")
        return 2
    qa = load_qa(a.qa, a.segment)          # 段绑定校验在组装上下文之前，错配尽早失败
    ctx, missing = assemble_context(a.segment, Path(a.lane_dir), repo=repo)
    if a.dry_run:
        print(f"segment={a.segment} 上下文 {len(ctx)} 字符 缺译 {missing} 行 题数 {len(qa)}")
        return 0
    kw = dict(stream_transport=stream_transport, api_key=api_key,
              ledger_path=ledger_path, model=a.model, timeout=a.timeout)
    if a.max_tokens is not None:
        kw["max_tokens"] = a.max_tokens
    if a.effort is not None:
        kw["effort"] = a.effort
    rows = []
    for q in qa:
        ans = chat([{"role": "system", "content": READER_SYS},
                    {"role": "user", "content": f"{ctx}\n\n＝＝ 问题 ＝＝\n{q['question']}"}],
                   purpose=f"ayano:{a.segment}:{q['id']}", **kw)
        verdict = chat([{"role": "system", "content": JUDGE_SYS},
                        {"role": "user", "content":
                         f"【问题】{q['question']}\n【标准答案】{q['reference']}\n"
                         f"【受试回答】{ans['content']}"}],
                       purpose=f"ayano-judge:{a.segment}:{q['id']}", **kw)
        cot = ans.get("reasoning_text", "")
        rows.append((q, ans["content"], verdict["content"], cot,
                     cot_signals(ans["content"], cot, ctx)))
    out = Path(a.out) if a.out else repo / "work" / "out" / f"ayano-{a.segment}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# 彩野测试报告 · {a.segment}（{len(rows)} 题）", ""]
    if missing:
        lines.append(f"> ⚠ 本段**缺译 {missing} 行**（段未译完，结论仅供参考）。")
        lines.append("")
    tally = Counter(parse_verdict(v) or "未能解析" for _, _, v, _, _ in rows)
    lines.append("> 判分合计："
                 + "／".join(f"{k} {tally[k]}" for k in ("对", "部分对", "错", "未能解析")
                             if tally.get(k)))
    lines.append("")
    unread = [q["id"] for q, _, v, _, _ in rows if parse_verdict(v) is None]
    if unread:
        # 「读不懂这行判分」必须与「判分说答错了」分开报。合并二者是本工具此前
        # 的失效形态：格式一漂移就被静默算成非「对」，而报告上看不出任何异常。
        lines += [f"> ⚠ **{len(unread)} 题的判分行未能解析出判定词**"
                  f"（{'、'.join(unread)}）——请人工读那几行的原文，"
                  f"**不要**把它们当成「错」计入统计。", ""]
    for q, ans, verdict, cot, signals in rows:
        lines += [f"## {q['id']}：{q['question']}",
                  f"- 信息点：{q.get('info_point', '-')}",
                  f"- 标准答案：{q['reference']}",
                  f"- 受试回答：{ans}",
                  # CoT 摘要是本工具判「真读出来 vs 猜」的关键证据：受试者若在推理里
                  # 引用了给定文本的具体句子，说明信息确实从译文传达到了；若它在
                  # 凭常识/剧情套路补全，摘要里一眼可见。
                  f"- CoT 摘要：{_cot_excerpt(cot)}",
                  # 原始测量值，不是判定——每一题都输出，不论下面的判分是什么
                  # （旧的「机械分诊」只在判「对」时触发，已证伪并降级，见上方
                  # cot_signals 与其上方常量定义处的记录）。
                  f"- CoT 信号：{signals}",
                  f"- **判分：{verdict}**"]
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已写 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
