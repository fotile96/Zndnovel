#!/usr/bin/env -S uv run python
"""换反编译语料基座：lua_scripts/ ← pyluadec-refactor 的 corpus/final/。

为什么换：新基座每个文件与游戏原始字节码 strip 后逐字节同一（229/229，形式化认证），
旧基座是 2025 年那版反编译器的产物，已知含冗余（例：snr_s2_10_s 把
`scene_s2s_190_sel_5/_11` 各多输出一份——旧版把 if/else 两支各写一遍，新版用 elseif
合并）。迁移指南见 pyluadec-refactor/docs/runbooks/zndnovel-naming-migration.md。

必须处理的耦合（本脚本全部代劳）：
  1. **行号不是稳定锚**。新旧打印结构不同，行号整体漂移 → data/ledger*.jsonl 必须
     整体重生成；extra 轨 634 个 `文件:行号` 键随之失效（另 195 个 `plotTitle:N` 与
     行号无关，不受影响）。
  2. **译文重挂键**。实测 (file, kind, jp) → zh 的映射**唯一无冲突**（791 组 0 冲突），
     故按内容分组、组内按出现顺序 1:1 配对即可无歧义搬迁；组内所有成员译文本就相同，
     配对顺序不影响结果。旧基座多出的冗余行没有新对应，直接丢弃并记账。
  3. **下游补丁不重放**。snr_common.lua 的中文字体行（fontLoad 槽 0、槽 1）**不在
     本脚本重放**——`FONT_PATCH` 常量已随「基座纯净化」（2026-09-02）一并删除，
     两个字体槽此后只有 `layers/overlays/fonts.toml` 这一个改写来源，在构建期
     （`layers` 阶段）施加，基座本身永远保持迁移出的原始文本。若有人手滑把这两行
     字体路径直接改进 `lua_scripts/`，`--check` 会因为该文件与「语料 + tr_line 标记」
     不再逐字节相同而报「基座不纯净」失败。snr_s4_10_s.lua 的选择地图手工修复同样
     **不需要**重放——新基座走认证重建已含等价修复。
  4. vms 轨不受影响：键是消息 ID（存在于字节码常量里），新旧完全一致（实测 16749=16749）。
"""
from __future__ import annotations

import argparse
import collections
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.build_ledger import build  # noqa: E402
from tools.pipelib import read_jsonl, write_jsonl  # noqa: E402
from tools.resolve import resolve_map  # noqa: E402

NEW_BASE = Path.home() / "pyluadec-refactor" / "corpus" / "final"
DEST = REPO / "lua_scripts"
LANE = REPO / "pilot" / "lanes" / "opus" / "data"
DATA = REPO / "data"

# 字体行重放已迁到 layers/overlays/fonts.toml（2026-09-02 起，基座纯净化）——
# snr_s4_10_s 的地图判定修复同理不在此列：新基座已含等价修复（迁移指南 §4）。


def content_key(row: dict) -> tuple:
    return (row["file"], row["kind"], row["jp"])


# lua 表达式里的「标识符」与「字符串字面量」——用于给 literal=false 的行推导变量重命名。
EXPR_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[A-Za-z_][\w.\[\]]*')


def _tokens(expr: str) -> list[str]:
    return EXPR_TOKEN.findall(expr)


def remap_expression(old_jp: str, new_jp: str, old_zh: str) -> tuple[str | None, str]:
    """把译文表达式里的旧局部名换成新基座的名字。

    literal=false 的 8 行里，zh 存的是**整个 lua 表达式**而非字符串内容（见
    build_ledger.parse_vms_lines 的 literal 判定）。新基座的残余局部名是
    `l<depth>_<reg>` 而非旧的 `v\\d+`/`i\\d+`/`g\\d+`，直接搬会引用到不存在的变量。

    做法：对齐 old_jp 与 new_jp 的 token 序列——字符串字面量必须逐一相同（字节码常量
    同一，这点有保证），差异只在标识符；由此得到重命名表，再作用到 old_zh 上。
    结构对不齐（新基座还原出了不同结构）时返回 None，交由调用方按「原样透传」处理。
    """
    to, tn = _tokens(old_jp), _tokens(new_jp)
    if len(to) != len(tn):
        return None, "token 数不同（结构变化）"
    rename: dict[str, str] = {}
    for a, b in zip(to, tn):
        if a.startswith('"') or b.startswith('"'):
            if a != b:
                return None, f"字符串常量不同: {a!r} vs {b!r}"
            continue
        if a != b:
            if rename.setdefault(a, b) != b:
                return None, f"同名标识符映射冲突: {a} → {rename[a]} / {b}"
    if not rename:
        return old_zh, "无需重命名"
    out = EXPR_TOKEN.sub(
        lambda m: m.group(0) if m.group(0).startswith('"')
        else rename.get(m.group(0), m.group(0)), old_zh)
    return out, "重命名 " + ", ".join(f"{k}→{v}" for k, v in rename.items())


# tr_line 标记的生成规则（复现自旧基座，见下）。
TR_LINE_RE = re.compile(r"\s*--\s*tr_line:\d+\s*$")
VMS_CALL_RE = re.compile(r"\bvms\(\d+,")
WIDE_STR_RE = re.compile(r'"[^"]*[^\x00-\x7F][^"]*"')   # 含非 ASCII 的字符串字面量
TR_EXCLUDE_FILES = {"snr_story_main", "snr_common"}


def should_mark(stem: str, code: str) -> bool:
    """该行是否该带 ` -- tr_line:N`：含全角字符串、非 vms 行、且不在排除文件里。

    规则复现自旧基座并**逐行校验通过**：678/678 全中、0 漏标，只多标 2 行
    （`savedataTitle("フラグメントモード", "")` 与 `savedataTitle("タイトル", "")`
    ——它们第一参确实是可译文本且在 extra 轨里有键，旧基座漏标了，多标是修正）。
    """
    if stem in TR_EXCLUDE_FILES or VMS_CALL_RE.search(code):
        return False
    return bool(WIDE_STR_RE.search(code))


def add_tr_line_markers(stem: str, text: str) -> tuple[str, int]:
    """给新基座重打 tr_line 标记（新产物不带，而 CLAUDE.md 要求保持这个约定）。"""
    out, n = [], 0
    for lineno, raw in enumerate(text.splitlines(), 1):
        code = TR_LINE_RE.sub("", raw)
        if should_mark(stem, code.strip()):
            out.append(f"{code.rstrip()} -- tr_line:{lineno}")
            n += 1
        else:
            out.append(code)
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), n


def build_key_map(old_extra: list[dict], new_extra: list[dict]) -> tuple[dict, list, list]:
    """老 extra 键 → 新 extra 键。按 (file,kind,jp) 分组、组内按 key 顺序 1:1 配对。

    组内配对顺序无关紧要：实测同组译文恒等（791 组 0 冲突），任何配对都给出同一结果。
    """
    def group(rows):
        g = collections.defaultdict(list)
        for r in rows:
            g[content_key(r)].append(r["key"])
        for v in g.values():
            v.sort(key=lambda k: (k.split(":")[0], _lineno(k)))
        return g

    go, gn = group(old_extra), group(new_extra)
    mapping, dropped, added = {}, [], []
    for k, olds in go.items():
        news = gn.get(k, [])
        for i, ok in enumerate(olds):
            if i < len(news):
                mapping[ok] = news[i]
            else:
                dropped.append((ok, k))
        for nk in news[len(olds):]:
            added.append((nk, k))
    for k, news in gn.items():
        if k not in go:
            added.extend((nk, k) for nk in news)
    return mapping, dropped, added


def _lineno(key: str) -> int:
    parts = key.split(":")
    for p in parts[1:]:
        if p.isdigit():
            return int(p)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=str(NEW_BASE), help="新语料目录")
    ap.add_argument("--apply", action="store_true", help="真正落盘（缺省只演练并报告）")
    ap.add_argument("--check", action="store_true",
                    help="只断言 lua_scripts == 语料 + tr_line 标记，不落盘")
    args = ap.parse_args()
    base = Path(args.base)
    if not base.is_dir():
        sys.exit(f"新语料目录不存在: {base}")

    src_files = sorted(base.glob("*.lua"))
    dst_files = sorted(DEST.glob("*.lua"))
    print(f"[migrate] 新基座 {len(src_files)} 文件 / 现有 {len(dst_files)} 文件")
    if {f.name for f in src_files} != {f.name for f in dst_files}:
        sys.exit("文件名集合不一致，拒绝迁移")

    if args.check:
        bad = []
        for f in src_files:
            text, _ = add_tr_line_markers(f.stem, f.read_text(encoding="utf-8"))
            if text != (DEST / f.name).read_text(encoding="utf-8"):
                bad.append(f.name)
        if bad:
            sys.exit(f"[migrate] 基座不纯净，{len(bad)} 个文件与「语料 + tr_line」不符：{bad[:5]}\n"
                     f"  本地化改动应当是 layers/ 下的层，不该直接改 lua_scripts/")
        print(f"[migrate] 基座纯净 ✓（{len(src_files)} 文件 == 语料 + tr_line 标记）")
        return

    # --- 对账：新旧账本 ---
    old_ledger = list(read_jsonl(DATA / "ledger.jsonl"))
    old_extra = list(read_jsonl(DATA / "ledger_extra.jsonl"))
    new_ledger, new_extra = build(base)

    old_ids = {r["id"] for r in old_ledger}
    new_ids = {r["id"] for r in new_ledger}
    print(f"[migrate] vms: 旧 {len(old_ids)} / 新 {len(new_ids)}；"
          f"仅旧有 {len(old_ids - new_ids)}，仅新有 {len(new_ids - old_ids)}")
    if old_ids != new_ids:
        sys.exit("vms 消息 ID 集合不一致——字节码常量应当同一，请先查明")
    jp_mismatch = [i for i in old_ids
                   if {r["jp"] for r in old_ledger if r["id"] == i}
                   != {r["jp"] for r in new_ledger if r["id"] == i}] if False else []
    old_jp = {r["id"]: r["jp"] for r in old_ledger}
    new_jp = {r["id"]: r["jp"] for r in new_ledger}
    jp_mismatch = [i for i in old_ids if old_jp[i] != new_jp[i]]
    print(f"[migrate] vms 原文逐条一致：{'是' if not jp_mismatch else f'否（{len(jp_mismatch)} 条不同）'}")
    for i in jp_mismatch[:5]:
        print(f"    id={i}\n      旧 {old_jp[i]!r}\n      新 {new_jp[i]!r}")

    print(f"[migrate] extra: 旧 {len(old_extra)} / 新 {len(new_extra)}")
    mapping, dropped, added = build_key_map(old_extra, new_extra)
    print(f"[migrate] extra 键映射 {len(mapping)}；旧多余 {len(dropped)}；新多出 {len(added)}")
    for k, c in dropped[:5]:
        print(f"    丢弃 {k}  ({c[1]} {c[2]!r})  ← 旧基座冗余行，同组其它键仍带同一译文")
    for k, c in added[:5]:
        print(f"    新增 {k}  ({c[1]} {c[2]!r})  ← 需确认是否有译文可挂")

    # --- 译文重挂键 ---
    fx_rows = list(read_jsonl(LANE / "forward_extra.jsonl"))
    remapped, orphan = [], []
    for row in fx_rows:
        nk = mapping.get(row["key"])
        if nk is None:
            if row["key"].startswith("plotTitle:"):
                remapped.append(row)          # 与行号无关，原样保留
            else:
                orphan.append(row)
            continue
        remapped.append({**row, "key": nk})
    print(f"[migrate] forward_extra: {len(fx_rows)} 行 → 重挂 {len(remapped)}，"
          f"无对应 {len(orphan)}")
    for r in orphan[:5]:
        print(f"    孤儿 {r['key']} {r.get('zh','')[:24]!r}")

    # 覆盖率：新 extra 里有多少键拿得到译文
    have = {r["key"] for r in remapped if r.get("zh")}
    miss = [r["key"] for r in new_extra if r["key"] not in have]
    print(f"[migrate] 新 extra 覆盖率 {len(new_extra) - len(miss)}/{len(new_extra)}"
          f"（缺 {len(miss)}）")
    for k in miss[:8]:
        row = next(r for r in new_extra if r["key"] == k)
        print(f"    缺译 {k} {row['kind']} {row['jp'][:20]!r}")

    # --- literal=false 的 8 行：zh 是整个表达式，局部名变了要跟着改 ---
    zh_map = resolve_map(read_jsonl(LANE / "forward.jsonl"),
                         read_jsonl(LANE / "patches.jsonl"))
    expr_patches = []
    for r in old_ledger:
        if r["literal"]:
            continue
        i = r["id"]
        old_z, new_j = zh_map.get(i), new_jp[i]
        if old_z is None:
            continue
        if old_z == r["jp"]:                     # 原样透传：直接采用新表达式
            if new_j != old_z:
                expr_patches.append((i, new_j, "透传，改用新基座表达式"))
            continue
        fixed, why = remap_expression(r["jp"], new_j, old_z)
        if fixed is None:
            print(f"[migrate] ⚠ id={i} 表达式无法自动重挂（{why}），需人工："
                  f"\n      旧jp {r['jp']}\n      新jp {new_j}\n      译文 {old_z}")
        elif fixed != old_z:
            expr_patches.append((i, fixed, why))
    print(f"[migrate] literal=false 表达式需改写 {len(expr_patches)} 条")
    for i, z, why in expr_patches:
        print(f"    id={i} [{why}] → {z}")

    if not args.apply:
        print("\n[migrate] 演练结束（加 --apply 落盘）")
        return

    marks = 0
    for f in src_files:
        text = f.read_text(encoding="utf-8")
        text, n = add_tr_line_markers(f.stem, text)
        marks += n
        (DEST / f.name).write_text(text, encoding="utf-8")
    print(f"[migrate] 重打 tr_line 标记 {marks} 条")
    # 标记是加在**落盘后**的文本上的，行号不变（就地追加注释），故账本仍按原文本生成
    write_jsonl(DATA / "ledger.jsonl", new_ledger)
    write_jsonl(DATA / "ledger_extra.jsonl", new_extra)
    write_jsonl(LANE / "forward_extra.jsonl", remapped)
    # literal=false 的表达式改写走修订轨（append-only），不动 forward.jsonl
    if expr_patches:
        from tools.add_patch import add as add_patch
        gv = max(int(m.group(1)) for m in
                 (re.match(r"glossary\.v(\d+)\.yaml", f.name)
                  for f in (REPO / "glossary").glob("glossary.v*.yaml")) if m)
        for i, z, why in expr_patches:
            # ⚠ 必须显式传 data=LANE：add() 的 data 缺省是仓库 data/，会在那里新建一个
            # patches.jsonl，而 resolve_map 读的是车道那份——修订静默失效。
            # 2026-08-31 首次执行踩过这个坑（id=22 在 comAyanoTimeRefresh 里真会跑，
            # 注入引用旧变量名的表达式会在做卡时报错）。
            add_patch(i, z, "review", gv, data=LANE, announce=False,
                      prov=f"migrate_base: {why}")
        print(f"[migrate] 追加 {len(expr_patches)} 条表达式修订到 patches.jsonl（glossary v{gv}）")
    print(f"[migrate] 已落盘：lua_scripts/{len(src_files)} 文件、data/ledger*.jsonl、"
          f"forward_extra.jsonl")


if __name__ == "__main__":
    main()
