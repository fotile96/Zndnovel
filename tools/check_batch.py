"""批次校验：硬规则挡入库，软规则进报告。spec §7。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import WORK, read_jsonl, sha256_file, display_width, dumps

RUBY_RE = re.compile(r'<[^<>,]+,[^<>,]+>')
SPEAKER_RE = re.compile(r'^【([^】]+)】')
MARKS = "≪≫≦≧○■"
BREAK_RE = re.compile(r'_n|_r')
DECOS = (("≪", "≫"), ("≦", "≧"))


def _split_deco(name: str):
    """拆出说话人名的装饰括号：【≪ユウイチ≫】→ ("≪", "ユウイチ", "≫")。"""
    for o, c in DECOS:
        if name.startswith(o) and name.endswith(c) and len(name) > 2:
            return o, name[1:-1], c
    return "", name, ""


def _expected_speaker(name: str, speakers: dict):
    """源说话人 → 期望的译文说话人（装饰括号原样保留）。
    表中无此名（＊＊＊、系统标签等）返回 None：只能校验结构，无从校验名字。"""
    o, bare, c = _split_deco(name)
    want = speakers.get(bare)
    return None if want is None else o + want + c


def _ruby_ok(s: str) -> bool:
    rest = RUBY_RE.sub("", s)
    return "<" not in rest and ">" not in rest


def _max_line_width(s: str) -> int:
    return max(display_width(seg) for seg in BREAK_RE.split(s)) if s else 0


def build_sibling_index(ledger_rows, zh_map) -> dict:
    """复现句族索引：jp 逐字相同的**已译**行聚成一族 → {jp: [(id, zh), ...]}。

    全库一次性构建（ledger 16749 行 / 已译 8816 行），行循环内 O(1) 查表——
    不要退化成「每行扫一遍全库」。ledger 的 jp 已含【说话人】前缀，故「jp 逐字
    相同」自动蕴含说话人相同。未译行（zh_map 无此 id）不入族：无从比较。
    """
    idx = {}
    for r in ledger_rows:
        zh = zh_map.get(r["id"])
        if zh is not None:
            idx.setdefault(r["jp"], []).append((r["id"], zh))
    return idx


def _w4_msg(others) -> str:
    """兄弟行异译 → 可操作消息：写明兄弟 id 与其 zh，让人一眼判断该改哪边。"""
    seen, shown = set(), []
    for sid, szh in others:
        if szh not in seen:
            seen.add(szh)
            shown.append(f"id={sid} 作「{szh}」")
    msg = "；".join(shown[:3])
    if len(shown) > 3:
        msg += f"；…共 {len(shown)} 种异译"
    return f"复现句族内不一致（同一 jp 另有译法）：{msg}"


def check(source_rows, draft_rows, speakers=None, glossary=None,
          siblings=None) -> dict:
    hard, warn = [], []
    src = {r["id"]: r for r in source_rows}
    drf = {r["id"]: r for r in draft_rows}
    if set(src) != set(drf) or len(draft_rows) != len(drf):
        hard.append({"id": 0, "rule": "R1",
                     "msg": f"id 集合不一致 src={len(src)} draft={len(drf)}"})
        return {"hard": hard, "warn": warn}
    # 本批草稿并入族索引：既让批内同 jp 重复互为兄弟，也让本批 id 的新译文
    # 顶掉车道里同 id 的旧译文（避免拿自己的历史版本当兄弟自我报警）。
    sib = None
    if siblings is not None:
        sib = dict(siblings)
        for i, s in src.items():
            kept = [p for p in sib.get(s["jp"], []) if p[0] != i]
            sib[s["jp"]] = kept + [(i, drf[i]["zh"])]
    for i, s in src.items():
        jp, zh = s["jp"], drf[i]["zh"]
        if not _ruby_ok(zh):
            hard.append({"id": i, "rule": "R2a", "msg": "ruby 不良构"})
        # 结构对齐恒查（原文有【】译文必须有、原文无【】译文不得擅自加）；
        # 名字映射只在 speakers 表覆盖该说话人时附加校验。
        sm, dm = SPEAKER_RE.match(jp), SPEAKER_RE.match(zh)
        if bool(sm) != bool(dm):
            hard.append({"id": i, "rule": "R2b", "msg": "【】说话人结构不对齐"})
        elif sm and speakers:
            want = _expected_speaker(sm.group(1), speakers)
            if want is not None and dm.group(1) != want:
                hard.append({"id": i, "rule": "R2b",
                             "msg": f"说话人应为【{want}】"})
        for ch in MARKS:
            if ch in jp and ch not in zh:
                hard.append({"id": i, "rule": "R2c", "msg": f"丢失符号 {ch}"})
        # 阈值 >=2：计划测试以断行差 2 触发 W1（计划散文「>2」系笔误）
        if abs(len(BREAK_RE.findall(jp)) - len(BREAK_RE.findall(zh))) >= 2:
            warn.append({"id": i, "rule": "W1", "msg": "_n/_r 数量差>2"})
        if glossary:
            for term, tr in glossary.items():
                if term in jp and tr not in zh:
                    warn.append({"id": i, "rule": "W2",
                                 "msg": f"「{term}」未按定译「{tr}」"})
        if _max_line_width(zh) > max(10, _max_line_width(jp) * 1.15):
            warn.append({"id": i, "rule": "W3", "msg": "显示行宽超限"})
        # W4 复现句族内逐字一致（style.md 唯一一条此前无机器兜底的硬规则）。
        # 顾问级：同一句日文在不同语境下偶有正当的不同处理，不阻断流水线。
        if sib is not None:
            others = [(sid, szh) for sid, szh in sib.get(jp, [])
                      if sid != i and szh != zh]
            if others:
                warn.append({"id": i, "rule": "W4", "msg": _w4_msg(others)})
    return {"hard": hard, "warn": warn}


def load_siblings(root):
    """从 <root>/data/ 读 ledger.jsonl + forward.jsonl/patches.jsonl（patch 优先）
    建族索引。三者缺 ledger 或全无译文时返回 None（W4 静默不判，不伪造绿）。"""
    from tools.resolve import resolve_map
    data = Path(root) / "data"
    ledger_p = data / "ledger.jsonl"
    if not ledger_p.exists():
        return None
    fwd = read_jsonl(data / "forward.jsonl") if (data / "forward.jsonl").exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    if not fwd and not pat:
        return None
    return build_sibling_index(read_jsonl(ledger_p), resolve_map(fwd, pat))


def main(argv=None):
    import argparse, json
    from tools.pipelib import REPO
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--lane-dir", default=None,
                    help="车道根（与 detect_collapse.py 同名同义）；指定时从 "
                         "<lane-dir>/glossary/ 读 speakers.json 与 active.json、"
                         "从 <lane-dir>/data/ 读 ledger/forward/patches 供 W4 "
                         "复现句族比对，省略时读仓库根（与之前行为一致）")
    args = ap.parse_args(argv)
    n = args.batch
    source = read_jsonl(WORK / "ctx" / f"batch_{n}" / "source.jsonl")
    draft_path = WORK / "out" / f"batch_{n}.draft.jsonl"
    draft = read_jsonl(draft_path)
    speakers = glossary = None
    groot = Path(args.lane_dir) if args.lane_dir else REPO
    sp, gl = groot / "glossary" / "speakers.json", groot / "glossary" / "active.json"
    if sp.exists():
        speakers = json.loads(sp.read_text(encoding="utf-8"))
    if gl.exists():
        glossary = json.loads(gl.read_text(encoding="utf-8"))
    result = check(source, draft, speakers, glossary,
                   siblings=load_siblings(groot))
    (WORK / "out").mkdir(parents=True, exist_ok=True)
    (WORK / "out" / f"batch_{n}.check.json").write_text(
        dumps(result), encoding="utf-8")
    if not result["hard"]:
        (WORK / "out" / f"batch_{n}.pass.json").write_text(
            dumps({"sha256": sha256_file(draft_path)}), encoding="utf-8")
        print(f"batch_{n}: PASS  warn={len(result['warn'])}")
        return 0
    print(f"batch_{n}: FAIL  hard={len(result['hard'])}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
