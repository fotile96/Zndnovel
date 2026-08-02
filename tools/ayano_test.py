"""彩野测试（P3 spec §5）：让从未见过原文的外部模型扮演「只靠梗概续听故事的读者」，
只喂 压缩前缀（skeleton/cards.zh.yaml 卡组梗概＝游戏自身的『あらすじ』机制）＋
本段中文译文（零日文原文），回答剧情理解题；答错处＝译文或压缩丢了信息，且丢的
恰是真实玩家会丢的。判分由第二次 API 调用完成。advisory 工具：恒 exit 0，
结论供段末人工验收参考。--dry-run 只组装统计、零 API 调用。"""
import re
import sys
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


# 机械分诊（task-10 复评采纳）：判分是**答案层**评分，对「可被字符串检索答对」的
# 题天然失效——受试者在上下文里定位到一段可逐字复制的跨度、照抄就能得分，根本不
# 需要理解推理链（seg1-s2 的 q4 就是实例：它抄了「赝品的做工完全没有问题，原因在
# 于原作」，CoT 里却写着「需确认」）。
# 分诊**不改判分语义**，只在判「对」的行上追加一个可复现的存疑信号，供人工复核。
# 为什么不把 CoT 直接喂给判分员：推理链里的「需确认/大概/？」是模型常规对冲话术，
# 真读懂了也常出现，用它扣分会推高误报率，还让分数挂钩一个不稳定的私有产物。
#
# 两个阈值都用 seg1-s2 的**真实产出**标定过（离线复算，见 task-10 报告复评附录）：
#   · 裸问号 `？/?` 从标记表里**去掉**了：复评给的原始清单含它，但实测 q1 那条
#     「读懂了、复述得干净」的 CoT 里逐句引用了译文对白（「嗯？有什么安排吗？」）
#     照样命中——本作是视觉小说，上下文里问号遍地，留着它等于每条都打标，信号
#     直接归零。留下的是**真正的对冲措辞**。
#   · 逐字重合门槛定在 12：实测 q1（自己的话复述）最长重合 7 字，q4（已知的
#     「照抄得分但没读懂」实例）最长重合 12 字（「赝品的做工完全没有问题，」）。
#     取 12 能抓住 q4 且不误伤 q1。样本只有 2 条，**将来跑更多段后应重新标定**；
#     好在这标记是 advisory（只提示人看一眼、不改分），误报成本仅一次人工扫视。
HESITATION_MARKERS = ("需确认", "不确定", "猜", "大概", "应该是")
VERBATIM_MIN = 12
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


def _verdict_head(verdict: str) -> str:
    """判分行格式契约是「判定|一句话依据」，取判定部分。

    格式完全由 JUDGE_SYS 提示词约束，模型随时可能漂移（`**对**|…`、`判定：对|…`、
    全角竖线、只回两个字）。此前用「切分后**恰等于**『对』」做判据，任何一种漂移
    都会让分诊标记**静默归零**——一个不报警的失效（终审 M3）。故这里把常见装饰
    （粗体星号、前缀标签、空白）一并剥掉，并认全角竖线。"""
    head = re.split(r"[|｜]", verdict, maxsplit=1)[0]
    head = head.replace("*", "").replace("＊", "").strip()
    head = re.sub(r"^[^：:]{0,10}[：:]\s*", "", head).strip()
    return head


def is_correct(verdict: str) -> bool:
    """判分是否为「对」。用 startswith 而非全等：判定词后面常挂标点/补语
    （「对。」「对（措辞不同）」），全等匹配会把它们当成非「对」。
    注意「对」是「部分对」「不对」的子串——必须判**开头**，不能用 in。"""
    return _verdict_head(verdict).startswith("对")


def triage(verdict: str, answer: str, cot: str, ctx: str) -> str:
    """判「对」的行做机械分诊，返回警示串（无信号则空串）。只用已到手的数据，
    零额外 API 成本。"""
    if not is_correct(verdict):
        return ""
    signals = []
    hits = [m for m in HESITATION_MARKERS if m in cot]
    if hits:
        signals.append(f"CoT 含犹豫标记 {'/'.join(hits)}")
    span = _longest_verbatim_span(answer, ctx)
    if span >= VERBATIM_MIN:
        signals.append(f"回答与上下文有 {span} 字逐字重合")
    if not signals:
        return ""
    return "⚠ 存疑：可能照抄未理解（" + "；".join(signals) + "）"


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
                     triage(verdict["content"], ans["content"], cot, ctx)))
    out = Path(a.out) if a.out else repo / "work" / "out" / f"ayano-{a.segment}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# 彩野测试报告 · {a.segment}（{len(rows)} 题）", ""]
    if missing:
        lines.append(f"> ⚠ 本段**缺译 {missing} 行**（段未译完，结论仅供参考）。")
        lines.append("")
    for q, ans, verdict, cot, flag in rows:
        lines += [f"## {q['id']}：{q['question']}",
                  f"- 信息点：{q.get('info_point', '-')}",
                  f"- 标准答案：{q['reference']}",
                  f"- 受试回答：{ans}",
                  # CoT 摘要是本工具判「真读出来 vs 猜」的关键证据：受试者若在推理里
                  # 引用了给定文本的具体句子，说明信息确实从译文传达到了；若它在
                  # 凭常识/剧情套路补全，摘要里一眼可见。
                  f"- CoT 摘要：{_cot_excerpt(cot)}",
                  f"- **判分：{verdict}**"]
        if flag:
            lines.append(f"- **{flag}**")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已写 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
