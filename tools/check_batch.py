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


def check(source_rows, draft_rows, speakers=None, glossary=None) -> dict:
    hard, warn = [], []
    src = {r["id"]: r for r in source_rows}
    drf = {r["id"]: r for r in draft_rows}
    if set(src) != set(drf) or len(draft_rows) != len(drf):
        hard.append({"id": 0, "rule": "R1",
                     "msg": f"id 集合不一致 src={len(src)} draft={len(drf)}"})
        return {"hard": hard, "warn": warn}
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
    return {"hard": hard, "warn": warn}


def main(argv=None):
    import argparse, json
    from tools.pipelib import REPO
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    args = ap.parse_args(argv)
    n = args.batch
    source = read_jsonl(WORK / "ctx" / f"batch_{n}" / "source.jsonl")
    draft_path = WORK / "out" / f"batch_{n}.draft.jsonl"
    draft = read_jsonl(draft_path)
    speakers = glossary = None
    sp, gl = REPO / "glossary" / "speakers.json", REPO / "glossary" / "active.json"
    if sp.exists():
        speakers = json.loads(sp.read_text(encoding="utf-8"))
    if gl.exists():
        glossary = json.loads(gl.read_text(encoding="utf-8"))
    result = check(source, draft, speakers, glossary)
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
