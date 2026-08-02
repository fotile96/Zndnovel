"""彩野测试（P3 spec §5）：让从未见过原文的外部模型扮演「只靠梗概续听故事的读者」，
只喂 压缩前缀（skeleton/cards.zh.yaml 卡组梗概＝游戏自身的『あらすじ』机制）＋
本段中文译文（零日文原文），回答剧情理解题；答错处＝译文或压缩丢了信息，且丢的
恰是真实玩家会丢的。判分由第二次 API 调用完成。advisory 工具：恒 exit 0，
结论供段末人工验收参考。--dry-run 只组装统计、零 API 调用。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import yaml

from tools.pipelib import REPO, read_jsonl
from tools.resolve import resolve_map
from tools.api_client import chat

READER_SYS = ("你在听人讲一个故事。你只知道两部分信息：①此前剧情的卡片梗概；"
              "②最新一段正文。只根据给定文本回答问题，文本里没有的就答「不知道」，"
              "不要编造，不要使用任何文本之外的知识。用中文简答，两三句以内。")
JUDGE_SYS = ("你是判分员。根据【问题】【标准答案】【受试回答】判定：对／部分对／错。"
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


def main(argv=None, *, transport=None, api_key=None, ledger_path=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", required=True)
    ap.add_argument("--qa", required=True)
    ap.add_argument("--lane-dir", required=True)
    ap.add_argument("--repo", default=None, help="仅测试用：覆盖仓库根")
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    repo = Path(a.repo) if a.repo else REPO
    ctx, missing = assemble_context(a.segment, Path(a.lane_dir), repo=repo)
    qa = yaml.safe_load(Path(a.qa).read_text(encoding="utf-8"))
    if a.dry_run:
        print(f"segment={a.segment} 上下文 {len(ctx)} 字符 缺译 {missing} 行 题数 {len(qa)}")
        return 0
    kw = dict(transport=transport, api_key=api_key, ledger_path=ledger_path)
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
        rows.append((q, ans["content"], verdict["content"]))
    out = Path(a.out) if a.out else repo / "work" / "out" / f"ayano-{a.segment}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# 彩野测试报告 · {a.segment}（{len(rows)} 题）", ""]
    if missing:
        lines.append(f"> ⚠ 本段**缺译 {missing} 行**（段未译完，结论仅供参考）。")
        lines.append("")
    for q, ans, verdict in rows:
        lines += [f"## {q['id']}：{q['question']}",
                  f"- 信息点：{q.get('info_point', '-')}",
                  f"- 标准答案：{q['reference']}",
                  f"- 受试回答：{ans}",
                  f"- **判分：{verdict}**", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已写 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
