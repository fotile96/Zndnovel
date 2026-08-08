"""extra 轨 829 条落盘：derive_extra.py 的机械派生（536 条）+ 人工裁定译文
（data/extra_translated.jsonl，覆盖 285 条 scene_title + 8 条 savedata，共 293 条经
去重后 243 行）→ pilot/lanes/opus/data/forward_extra.jsonl（append-only，主键 key）。

为什么另开 forward_extra.jsonl 而不并进 forward.jsonl（用户裁定）：ledger_extra.jsonl
本来就与 ledger.jsonl 分开（key 是字符串如 "plotTitle:1"，不是整数 id），
resolve.resolve_map 与 main/ambient 车道的机械闸都假定 id 是整数，混进 forward.jsonl
会让这些下游对字符串 key 行为未定义（恒绿风险）。另开一条平行的 append-only 线，
保持与 ledger_extra 的既有分工对称。

四类 kind 的落盘来源：
  plot_title（195） derive_extra 精确匹配 cards.zh，全部 confidence=exact。
  scene_title（454）169 条 derive_extra 精确匹配冻结卡名；285 条查
                     data/extra_translated.jsonl——那是已经过 fable 复核 + 用户逐条
                     裁定的最终稿，**不可再生**（丢了要重新走一遍复核与裁定），
                     本工具只读它，绝不再次模型翻译或改写其内容。
  card_msg（172）   derive_extra 模板 + 槽位解析，全部 confidence=template。
  savedata（8）     5 条查 data/extra_translated.jsonl；3 条空串——空串本身就是
                     data/extra_translated.jsonl 里 jp=="" 那一条的裁定结果
                     （style.md v14：3 条空串标题裁定不译，原样留空），不是
                     「没查到」，source 要能体现这一区别（reviewed-empty vs
                     model+review）。

用法：
    uv run python tools/land_extra.py            # 校验 + 落盘
    uv run python tools/land_extra.py --check     # 只校验，不写文件
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.build_context import glossary_version
from tools.derive_extra import build_card_indexes, derive_row, load_yaml_rows
from tools.pipelib import REPO, append_jsonl, read_jsonl

LEDGER_EXTRA = REPO / "pilot/lanes/opus/data/ledger_extra.jsonl"
CARDS_JP = REPO / "skeleton/cards.jp.yaml"
CARDS_ZH = REPO / "skeleton/cards.zh.yaml"
TRANSLATED = REPO / "data/extra_translated.jsonl"
FORWARD_EXTRA = REPO / "pilot/lanes/opus/data/forward_extra.jsonl"


# ---------------------------------------------------------------------------
# 纯函数层：只吃/吐 Python 数据结构，不碰文件系统——单测与变异都打在这一层。
# ---------------------------------------------------------------------------

def load_translated_by_jp(rows):
    """把 data/extra_translated.jsonl 的行列表按 jp 建字典。jp 唯一性在此校验——
    这是「人工裁定成果」的完整性前提，一旦不唯一，按 jp 查表就会取到不确定的哪一条
    （对应任务要求的"倒查能力"：查表结果必须是确定的，不能悄悄取到重复项里的任意一个）。
    """
    by_jp = {}
    dup = []
    for r in rows:
        if r["jp"] in by_jp:
            dup.append(r["jp"])
        by_jp[r["jp"]] = r
    if dup:
        raise ValueError(f"data/extra_translated.jsonl 内 jp 有重复，取值不确定：{dup}")
    return by_jp


def assemble_rows(ledger_rows, jp_by_card, zh_by_card, title_to_cards,
                   translated_by_jp, glossary_v, ts):
    """对全部 829 条 ledger_extra 行逐条组装 forward_extra 行。

    derive_extra 能机械派生的（plot_title/scene_title 精确匹配、card_msg 模板）
    直接采用其结果；派生不出的（scene_title 的 285 条、savedata 的 8 条，含 3 条
    合法空串）查 translated_by_jp——查不到就当场报错，绝不允许静默产出空 zh 冒充
    「已译」（本项目文化：静默写错比报错更坏，查不到本该让整个落盘失败，而不是
    留一行没人注意到的假空译文）。

    ⚠ 对 jp=="" 一视同仁地走同一条查表路径，不做任何 `if not row["jp"]:` 式的提前
    return/continue——那正是"把空串当成缺失跳过"的经典退化写法，此处逐行 append，
    最后再断言长度，双保险。
    """
    idx = {"jp_by_card": jp_by_card, "zh_by_card": zh_by_card, "title_to_cards": title_to_cards}
    out = []
    for row in ledger_rows:
        derived, _anomaly = derive_row(row, idx)
        if derived["confidence"] != "none":
            zh, source = derived["zh"], derived["source"]
        else:
            if row["jp"] not in translated_by_jp:
                raise ValueError(
                    f"key={row['key']!r} kind={row['kind']!r} jp={row['jp']!r}："
                    f"derive_extra 派生不出，data/extra_translated.jsonl 里也查不到——"
                    f"不允许静默产出，需人工核实")
            t = translated_by_jp[row["jp"]]
            zh = t["zh"]
            if row["jp"] == "":
                source = ("reviewed-empty:data/extra_translated.jsonl"
                          "（style.md v14：savedata 空串标题经复核裁定不译，原样留空）")
            else:
                source = "model+review:data/extra_translated.jsonl"
        out.append({
            "key": row["key"],
            "kind": row["kind"],
            "zh": zh,
            "source": source,
            "glossary_v": glossary_v,
            "ts": ts,
        })
    if len(out) != len(ledger_rows):
        raise AssertionError(
            f"严禁静默丢行：组装出 {len(out)} 行，ledger 有 {len(ledger_rows)} 行")
    return out


def validate_forward_extra(rows, ledger_rows):
    """落盘前后都要跑的硬校验：行数、key 集合、无重复、source 全部非空。
    通过返回 True；任何一项不满足都 raise（不是返回 False——让调用方无法假装没看见）。
    """
    ledger_keys = [r["key"] for r in ledger_rows]
    ledger_key_set = set(ledger_keys)
    if len(ledger_keys) != len(ledger_key_set):
        raise AssertionError("ledger_extra.jsonl 自身就有重复 key，这是上游问题，先修那边")

    if len(rows) != len(ledger_rows):
        raise AssertionError(f"行数不符：rows={len(rows)} ledger={len(ledger_rows)}")

    row_keys = [r["key"] for r in rows]
    row_key_set = set(row_keys)
    if len(row_keys) != len(row_key_set):
        seen, dup = set(), set()
        for k in row_keys:
            if k in seen:
                dup.add(k)
            seen.add(k)
        raise AssertionError(f"rows 内部有重复 key（{len(dup)} 个），如 {sorted(dup)[:10]}")

    if row_key_set != ledger_key_set:
        missing = ledger_key_set - row_key_set
        extra = row_key_set - ledger_key_set
        raise AssertionError(
            f"key 集合与 ledger_extra 不一致："
            f"缺 {len(missing)} 个（如 {sorted(missing)[:5]}），"
            f"多 {len(extra)} 个（如 {sorted(extra)[:5]}）")

    no_source = [r["key"] for r in rows if not r.get("source")]
    if no_source:
        raise AssertionError(f"以下 key 缺 source：{no_source[:10]}")

    return True


# ---------------------------------------------------------------------------
# 落盘（I/O 层）
# ---------------------------------------------------------------------------

def land(rows, path=None):
    """append-only 落盘。若目标文件已存在且与本次 rows 有重叠 key，拒绝写入——
    本函数只保证绝不会把已落盘的行覆盖成新行；重复 key 一律拒绝，逼着调用方显式
    决定修订怎么处理（新记录、不同 key 后缀等），而不是本函数替它做主。
    落盘后立即回读校验，确认 append_jsonl 按预期写入（防"以为写了其实没写全"）。
    """
    path = Path(path or FORWARD_EXTRA)
    existing = read_jsonl(path) if path.exists() else []
    existing_keys = {r["key"] for r in existing}
    new_keys = {r["key"] for r in rows}
    dup = existing_keys & new_keys
    if dup:
        raise ValueError(
            f"append-only 冲突：{path} 里已有 {len(dup)} 个 key 与本次落盘重叠"
            f"（如 {sorted(dup)[:5]}）——拒绝覆写。若这是有意修订，请自行决定"
            f"追加策略，不要用本函数覆盖首次落盘")
    append_jsonl(path, rows)

    after = read_jsonl(path)
    after_new = after[len(existing):]
    if [r["key"] for r in after_new] != [r["key"] for r in rows]:
        raise RuntimeError(f"落盘后回读与预期不符——{path} 未按预期写入，需人工核查")
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", default=str(LEDGER_EXTRA))
    ap.add_argument("--cards-jp", default=str(CARDS_JP))
    ap.add_argument("--cards-zh", default=str(CARDS_ZH))
    ap.add_argument("--translated", default=str(TRANSLATED))
    ap.add_argument("--out", default=str(FORWARD_EXTRA))
    ap.add_argument("--check", action="store_true", help="只校验，不落盘")
    ap.add_argument("--ts", help="覆盖时间戳（测试用；省略则用当前 UTC 时间，精确到秒）")
    args = ap.parse_args(argv)

    ledger_rows = read_jsonl(args.ledger)
    cards_jp_rows = load_yaml_rows(args.cards_jp)
    cards_zh_rows = load_yaml_rows(args.cards_zh)
    jp_by_card, zh_by_card, title_to_cards = build_card_indexes(cards_jp_rows, cards_zh_rows)
    translated_by_jp = load_translated_by_jp(read_jsonl(args.translated))

    gv = glossary_version(REPO)
    ts = args.ts or datetime.now(timezone.utc).isoformat(timespec="seconds")

    rows = assemble_rows(ledger_rows, jp_by_card, zh_by_card, title_to_cards,
                          translated_by_jp, gv, ts)
    validate_forward_extra(rows, ledger_rows)
    print(f"校验通过：{len(rows)} 行，key 集合与 ledger_extra 完全一致，无重复，"
          f"source 全部非空。glossary_v={gv}", file=sys.stderr)

    if args.check:
        print("--check 模式：不落盘。", file=sys.stderr)
        return 0

    out_path = land(rows, args.out)
    landed = read_jsonl(out_path)
    validate_forward_extra(landed, ledger_rows)
    print(f"已落盘 {out_path}（{len(landed)} 行），落盘后回读校验通过。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
