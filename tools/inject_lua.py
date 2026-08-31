#!/usr/bin/env -S uv run python
"""译文注入：lua_scripts 原文源 + 定稿译文 → build/inject_src/*.lua → luac_sz4 → 字节码。

锚定方式与 tools/build_ledger.py **共用同一组正则**（直接 import，杜绝口径漂移）：
按 (file, line) 定位、在行内就地替换字符串参数，行号不变 → extra 轨的
`文件:行号` 键不漂移，同一份 ledger 可反复使用。

三层数据：
  vms 正文   data/ledger.jsonl        × resolve_map(forward, patches)  → 按 id
  extra 轨   data/ledger_extra.jsonl  × forward_extra.jsonl            → 按 key
  literal=false 的 8 行：zh 存的是整个 lua 表达式，整参数替换而非包引号。

编译器：pyluadec-refactor 的 build/luac_sz4——序列化宽度补丁（size_t=4）版
vanilla Lua 5.1.5，在 arm64 宿主上直接产 PSP ABI 字节码（头 1B4C756151000104040408 00）。
路径可用 SNDL_LUAC 覆盖。原包字节码是 stripped，故一律 -s。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.build_ledger import (  # noqa: E402
    CARD_MSG_RE, PLOT_TITLE_RE, SAVEDATA_RE, SCENE_TITLE_RE, TR_LINE_RE, VMS_RE,
)
from tools.pipelib import read_jsonl  # noqa: E402
from tools.resolve import resolve_map  # noqa: E402

SRC = REPO / "lua_scripts"
OUT_SRC = REPO / "build" / "inject_src"
OUT_BC = REPO / "build" / "inject" / "script"
LANE = REPO / "pilot" / "lanes" / "opus" / "data"
LUAC = Path(os.environ.get("SNDL_LUAC", Path.home() / "pyluadec-refactor" / "build" / "luac_sz4"))
PSP_LUAC_HEADER = bytes.fromhex("1b4c75615100010404040800")


def lua_quote(s: str) -> str:
    """把译文包成 lua 双引号字符串。译文里的 \\ 与 " 必须转义，否则编译报错或截断。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def load_translations() -> tuple[dict[int, str], dict[str, str]]:
    zh = resolve_map(read_jsonl(LANE / "forward.jsonl"), read_jsonl(LANE / "patches.jsonl"))
    extra: dict[str, str] = {}
    for row in read_jsonl(LANE / "forward_extra.jsonl"):
        extra[row["key"]] = row["zh"]          # append-only：同 key 后行覆盖前行
    return zh, extra


def inject_text(stem: str, text: str, vms_rows: dict[int, dict],
                zh: dict[int, str], extra: dict[str, str], stats: dict) -> str:
    """就地替换一份 lua 源里的全部可译字符串。行数与行号严格不变。"""
    out_lines = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        m_tr = TR_LINE_RE.search(raw)
        code, comment = (raw[:m_tr.start()], raw[m_tr.start():]) if m_tr else (raw, "")
        lead = code[:len(code) - len(code.lstrip())]
        body = code.strip()
        trail = code[len(lead) + len(body):]

        if body:
            body = _inject_body(stem, lineno, body, vms_rows, zh, extra, stats)
        out_lines.append(lead + body + trail + comment)
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else "")


def _replace_span(body: str, start: int, end: int, new: str) -> str:
    return body[:start] + new + body[end:]


def _inject_body(stem: str, lineno: int, body: str, vms_rows: dict[int, dict],
                 zh: dict[int, str], extra: dict[str, str], stats: dict) -> str:
    # ---- vms 正文（按 ledger 的 (file,line) 锚定，双向核对 id 一致）----
    m = VMS_RE.search(body)
    if m:
        row = vms_rows.get(lineno)
        if row is None:
            stats["vms_unledgered"] += 1
        elif row["id"] != int(m.group(1)):
            raise SystemExit(f"{stem}:{lineno} ledger id={row['id']} 与源 id={m.group(1)} 不符"
                             f"——lua_scripts 与 data/ledger.jsonl 不同步，先跑 build_ledger.py")
        else:
            text_zh = zh.get(row["id"])
            if text_zh is None:
                stats["vms_missing"] += 1
            else:
                new = lua_quote(text_zh) if row["literal"] else text_zh
                stats["vms"] += 1
                return _replace_span(body, m.start(3), m.end(3), new)
        return body

    # ---- extra 四类：优先级与 build_ledger.parse_extra 的 elif 链完全一致 ----
    if m := PLOT_TITLE_RE.match(body):
        return _sub_extra(body, m, 2, f"plotTitle:{m.group(1)}", extra, stats)
    if m := SAVEDATA_RE.search(body):
        for i in (2, 1):  # 从右往左替换，保住左侧 span
            body = _sub_extra(body, m, i, f"{stem}:{lineno}:{i}", extra, stats,
                              allow_empty=True)
            m = SAVEDATA_RE.search(body)  # 左参替换后右参 span 已失效，重新匹配
        return body
    if m := CARD_MSG_RE.search(body):
        return _sub_extra(body, m, 1, f"{stem}:{lineno}", extra, stats)
    if m := SCENE_TITLE_RE.search(body):
        return _sub_extra(body, m, 1, f"{stem}:{lineno}", extra, stats)
    return body


def _sub_extra(body: str, m, group: int, key: str, extra: dict[str, str],
               stats: dict, allow_empty: bool = False) -> str:
    text_zh = extra.get(key)
    if text_zh is None or (text_zh == "" and not allow_empty):
        stats["extra_missing"] += 1
        return body
    if text_zh == "":
        return body  # savedataTitle 第二参裁定不译，原样留空
    if '"' in text_zh or "\\" in text_zh:
        raise SystemExit(f"extra {key} 含引号/反斜杠，需人工处理: {text_zh!r}")
    stats["extra"] += 1
    return _replace_span(body, m.start(group), m.end(group), text_zh)


def compile_bytecode(src_dir: Path, out_dir: Path) -> int:
    if not LUAC.exists():
        sys.exit(f"缺 32 位 luac: {LUAC}（pyluadec-refactor ./scripts/build_native.sh，"
                 f"或设 SNDL_LUAC）")
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(src_dir.glob("*.lua")):
        dst = out_dir / f.name
        proc = subprocess.run([str(LUAC), "-s", "-o", str(dst), str(f)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            sys.exit(f"luac 失败 {f.name}: {proc.stderr.strip()}")
        if dst.read_bytes()[:12] != PSP_LUAC_HEADER:
            sys.exit(f"{dst.name} 头非 PSP ABI（luac 宽度不对）")
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-compile", action="store_true", help="只产改写后的 lua 源")
    ap.add_argument("--only", help="逗号分隔的文件 stem，仅注入这些（调试用）")
    args = ap.parse_args()

    zh, extra = load_translations()
    print(f"[inject] 译文 vms={len(zh)} extra={len(extra)}")

    by_file: dict[str, dict[int, dict]] = {}
    for row in read_jsonl(REPO / "data" / "ledger.jsonl"):
        by_file.setdefault(row["file"], {})[row["line"]] = row

    only = set(args.only.split(",")) if args.only else None
    if OUT_SRC.exists():
        shutil.rmtree(OUT_SRC)
    OUT_SRC.mkdir(parents=True)
    stats = dict(vms=0, vms_missing=0, vms_unledgered=0, extra=0, extra_missing=0)
    for f in sorted(SRC.glob("*.lua")):
        stem = f.stem
        text = f.read_text(encoding="utf-8")
        if only is None or stem in only:
            text = inject_text(stem, text, by_file.get(stem, {}), zh, extra, stats)
        (OUT_SRC / f.name).write_text(text, encoding="utf-8")
    print(f"[inject] vms 替换 {stats['vms']}（缺译 {stats['vms_missing']}，"
          f"账本外 {stats['vms_unledgered']}）；extra 替换 {stats['extra']}"
          f"（缺译/留空 {stats['extra_missing']}）")

    if not args.no_compile:
        n = compile_bytecode(OUT_SRC, OUT_BC)
        print(f"[inject] 编译 {n} 个字节码 → {OUT_BC}")


if __name__ == "__main__":
    main()
