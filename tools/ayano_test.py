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


def assemble_context(label: str, lane_dir: Path, repo: Path = REPO):
    segs = yaml.safe_load((repo / "config" / "segments.yaml").read_text(encoding="utf-8"))
    hit = next((s for s in segs if s["label"] == label), None)
    if hit is None:
        raise SystemExit(f"未知段 label：{label}")
    lo, hi = hit["batches"]
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
    cards = yaml.safe_load((repo / "skeleton" / "cards.zh.yaml").read_text(encoding="utf-8"))
    prefix = "\n\n".join(f"【卡{c['card']}·{c.get('title_zh', '')}】\n{c.get('body_zh', '')}"
                         for c in cards)
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
