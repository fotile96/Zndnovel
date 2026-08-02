"""config/card_chapter.yaml 全量交叉校验（P3 devwave1 数据闸）。

card_chapter.yaml 的 196 条 card→章节短码 映射是手工推导的（见该文件头注释），
此前只有 8 个卡号（Critical 原始证据）被硬编码断言过，其余 188 条没有任何独立
守护——终审的变异测试证明把清单外的卡号改早（如 140: s6f → s1s）机检全绿不响。

本模块从**独立事实源**（不复用 tools/ayano_test.py 的任何逻辑）重新推导 196
条映射里能推导的部分，与 card_chapter.yaml 逐条比对：

  A) 157 张场景/选择卡：独立源 = data/scene2card.json（sceneId→card，流水线的
     独立产物）。章节短码 = sceneId 第一个下划线前的部分，"sof"→"s0f"（拼写不
     一致，CLAUDE.md 已记载）。
  B) 13 张章节梗概卡（133–145）：独立源 = lua_scripts/ 里 `myCard[N].hold = 1`
     的赋值语句所在文件——只认字面单个 `=` 的赋值，不认 `== 1`/`== -1` 的判断
     （判断行总以 `then` 收尾，赋值行没有）。文件名→章节短码按
     `snr_<章号>_10_<模式>.lua` → `<章号><模式>` 规则换算（CLAUDE.md
     `comSectionUID2ScriptFileName` 一致）。
  C) 25 张关键词卡：多数同 B 的赋值定位法，落在 `_s` 故事脚本里。其中 3 张
     （97/115/126）查无直接闭包，改用"侧生"路径：定位授予它们的
     `snr_crd_<主卡号>.lua`（crd 文件号即其主卡号，`comSectionCardStart` 套路），
     主卡号本身是 A 类场景卡，其章节已由 scene2card.json 独立验证——不直接信任
     card_chapter.yaml 自己的说法。
  D) 编外卡 200：唯一独立源是 `lua_scripts/snr_e2_10_f.lua` 内对
     `card("crd_200_a")` 的引用（EX2 章节完成时展示），已通过文件名规则换算得
     "e2f"。除此之外全仓库 lua_scripts/ 无第二处提及 200，无法做多源交叉，只能
     单源确认。

若 A+B+C+D 未能覆盖全部 196 条，缺口在报告/测试里显式列出，不静默通过。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import yaml

from tools.pipelib import REPO

LUA_DIR = REPO / "lua_scripts"

# `snr_<章号>_10_<模式>.lua` → 章节短码 `<章号><模式>`（CLAUDE.md
# comSectionUID2ScriptFileName 换算规则）。只匹配 23 个章节脚本，不吃 crd/其他。
_CHAPTER_FILE_RE = re.compile(r"^snr_(s\d|e\d)_10_(s|f|fa|fb|fc)\.lua$")

# `gameSave.myCard[N].hold = 1` 的赋值（单个 `=`）。刻意不匹配 `== 1`/`== -1`
# 判断行——那些行在本仓库风格里恒以 `then` 收尾，赋值行不会。
_HOLD_ASSIGN_RE = re.compile(r"gameSave\.myCard\[(\d+)\]\.hold\s*=\s*1\b")

KEYWORD_CARDS_INDIRECT = {97, 115, 126}  # 无直接闭包，须走 crd 主卡侧生路径


def _chapter_from_filename(fname: str):
    m = _CHAPTER_FILE_RE.match(fname)
    return None if m is None else m.group(1) + m.group(2)


def load_scene2card() -> dict:
    return json.loads((REPO / "data" / "scene2card.json").read_text(encoding="utf-8"))


def expected_scene_cards(scene2card: dict | None = None) -> dict:
    """A 类：157 张场景/选择卡的期望章节，键 = card 号。"""
    scene2card = scene2card if scene2card is not None else load_scene2card()
    out = {}
    for sid, card in scene2card.items():
        ch = sid.split("_")[0]
        if ch == "sof":
            ch = "s0f"  # sceneId 字面拼写与章节短码不一致（CLAUDE.md 已记载）
        out[card] = ch
    return out


def _scan_chapter_file_hold_assignments() -> dict:
    """扫描 23 个章节脚本，返回 card号 → 该文件推导出的章节短码（可能一张卡在
    多文件被赋值——正常代码不会，若出现记为冲突交给调用方处理）。"""
    out = {}
    for path in sorted(LUA_DIR.glob("snr_*_10_*.lua")):
        ch = _chapter_from_filename(path.name)
        if ch is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in _HOLD_ASSIGN_RE.finditer(text):
            card = int(m.group(1))
            out.setdefault(card, set()).add(ch)
    return out


def expected_chapter_summary_cards() -> dict:
    """B 类：133–145 这 13 张章节梗概卡的期望章节。"""
    hits = _scan_chapter_file_hold_assignments()
    return {c: sorted(chs)[0] for c, chs in hits.items() if 133 <= c <= 145}


def _scan_crd_side_effects() -> dict:
    """扫描 snr_crd_<N>.lua，返回 侧生关键词卡号 → 主卡号 N（`crd_<N>.lua`
    内对 `myCard[M].hold = 1` 的赋值，M != N 视为侧生副产物）。"""
    out = {}
    for path in sorted(LUA_DIR.glob("snr_crd_*.lua")):
        m = re.match(r"^snr_crd_(\d+)\.lua$", path.name)
        if m is None:
            continue
        primary = int(m.group(1))
        text = path.read_text(encoding="utf-8", errors="replace")
        for hm in _HOLD_ASSIGN_RE.finditer(text):
            card = int(hm.group(1))
            if card != primary:
                out.setdefault(card, set()).add(primary)
    return out


def expected_keyword_cards(scene2card: dict | None = None) -> dict:
    """C 类：25 张关键词卡的期望章节。22 张走章节脚本直接闭包（同 B 的扫描），
    3 张（97/115/126）走 crd 主卡侧生 + scene2card 独立换算主卡章节。"""
    scene_chapters = expected_scene_cards(scene2card)
    direct = _scan_chapter_file_hold_assignments()
    out = {}
    for c, chs in direct.items():
        if c in KEYWORD_CARDS_RANGE and c not in KEYWORD_CARDS_INDIRECT:
            out[c] = sorted(chs)[0]
    side = _scan_crd_side_effects()
    for c in KEYWORD_CARDS_INDIRECT:
        primaries = side.get(c)
        if not primaries:
            continue
        primary = sorted(primaries)[0]
        ch = scene_chapters.get(primary)
        if ch is not None:
            out[c] = ch
    return out


KEYWORD_CARDS_RANGE = {95, 96, 97} | {105, 106, 107} | {109} | set(range(114, 118)) | set(range(119, 133))


def expected_card_200() -> dict:
    """D 类：编外卡 200，唯一独立源 = 提及 `crd_200` 的那个章节脚本文件名。"""
    hits = []
    for path in sorted(LUA_DIR.glob("snr_*.lua")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "crd_200" in text or re.search(r"\bmyCard\[200\]", text):
            hits.append(path.name)
    if len(hits) != 1:
        return {}  # 无法单一定位，交给调用方报告为"无法独立验证"
    ch = _chapter_from_filename(hits[0])
    return {200: ch} if ch else {}


def build_expected_mapping():
    """汇总 A+B+C+D，返回 (expected: dict[int,str], sources: dict[int,str],
    unresolved: set[int])。sources 记录每个 card 号是靠哪一类独立源解出的，
    便于报告与断言分类覆盖数。unresolved 是 196 条里独立源没能覆盖到的卡号
    （如实上报，不臆造）。"""
    scene2card = load_scene2card()
    a = expected_scene_cards(scene2card)
    b = expected_chapter_summary_cards()
    c = expected_keyword_cards(scene2card)
    d = expected_card_200()

    expected, sources = {}, {}
    for tag, mapping in (("A_scene", a), ("B_chapter_summary", b),
                         ("C_keyword", c), ("D_card200", d)):
        for card, ch in mapping.items():
            expected[card] = ch
            sources[card] = tag
    return expected, sources


def crossval(card_chapter: dict):
    """拿一份 card→章节短码 映射（通常是 config/card_chapter.yaml 的内容，或其
    变异副本）跟独立源比对。返回 mismatch 描述列表（空=全部通过）。不修改传入
    的 dict，不读写 config/card_chapter.yaml 本身——调用方负责加载/变异/传入。"""
    expected, _sources = build_expected_mapping()
    mismatches = []
    for card, exp_ch in sorted(expected.items()):
        got = card_chapter.get(card)
        if got != exp_ch:
            mismatches.append(
                f"卡{card}：card_chapter.yaml 写 {got!r}，独立源推出 {exp_ch!r}")
    return mismatches


def main(argv=None):
    card_chapter = yaml.safe_load(
        (REPO / "config" / "card_chapter.yaml").read_text(encoding="utf-8")) or {}
    expected, sources = build_expected_mapping()
    all_cards = set(card_chapter)
    covered = set(expected)
    uncovered = all_cards - covered

    print(f"card_chapter.yaml 共 {len(all_cards)} 条")
    for tag in ("A_scene", "B_chapter_summary", "C_keyword", "D_card200"):
        n = sum(1 for c, t in sources.items() if t == tag)
        print(f"  {tag}: 独立源覆盖 {n} 条")
    print(f"  未覆盖（无独立源，如实列出）: {len(uncovered)} 条 -> {sorted(uncovered)}")

    mismatches = crossval(card_chapter)
    if mismatches:
        print(f"\n发现 {len(mismatches)} 处不一致：")
        for m in mismatches:
            print(f"  - {m}")
        return 1
    print("\n全部可独立验证的条目一致，未发现不一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
