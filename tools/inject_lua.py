#!/usr/bin/env -S uv run python
"""译文注入：lua_scripts 纯净基座 + 定稿译文 → 注入后的 lua 源（文件名→文本）。

锚定方式与 tools/build_ledger.py **共用同一组正则**（直接 import，杜绝口径漂移）：
按 (file, line) 定位、在行内就地替换字符串参数，行号不变 → extra 轨的
`文件:行号` 键不漂移，同一份 ledger 可反复使用。

三层数据：
  vms 正文   data/ledger.jsonl        × resolve_map(forward, patches)  → 按 id
  extra 轨   data/ledger_extra.jsonl  × forward_extra.jsonl            → 按 key
  literal=false 的 8 行：zh 存的是整个 lua 表达式，整参数替换而非包引号。

本模块只做纯注入：`inject_tree`/`inject_text` 不写盘、不编译、不依赖全局状态，
是纯函数，好测。字体槽改写归 layers/overlays/fonts.toml；编译字节码与出盘归
tools/build_disc.py；车道目录不再在本文件写死，随 layers/manifest.toml 的
[lane].dir 走（`tools.layers.load_manifest()`）。命令行仅供调试，产物不直接出货。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.build_ledger import (  # noqa: E402
    PLOT_TITLE_RE, SAVEDATA_RE, SIMPLE_EXTRA, TR_LINE_RE, VMS_RE,
)
from tools.layers import load_manifest  # noqa: E402
from tools.latin_wrap import fix_latin_splits  # noqa: E402
from tools.pipelib import read_jsonl  # noqa: E402
from tools.resolve import resolve_map  # noqa: E402

SRC = REPO / "lua_scripts"
DEFAULT_OUT = REPO / "build" / "release" / "lua" / "injected"


# 紧邻的两组 ruby（中间一个字符都没有）。注意 `[^<>,]` 保证不会跨过别的标记。
ADJACENT_RUBY = re.compile(r"<([^<>,]+),([^<>,]+)><([^<>,]+),([^<>,]+)>")


def merge_adjacent_ruby(text: str) -> tuple[str, int]:
    """把紧邻的多组单字注音合并成一组。

    为什么必须合（2026-08-31 游戏内实测）：ruby 由 C 侧 stub **逐组独立居中**，
    而拼音比它标注的那个汉字宽得多——单个汉字 17px，`hú` 之类却要 18~27px。
    于是 `<胡,hú><萝,luó><卜,bo>` 三组各自居中时相互重叠，糊成一团。合成
    `<胡萝卜,húluóbo>` 后整串对着整个词居中，组内不再打架。
    音节间不补空格：合写本来就是拼音词式拼写的规范写法（胡萝卜 = húluóbo）。
    （2026-09-04 起引擎已改：空格按 5 px 推进且计入居中估算，见 layers/eboot/ruby-p5.toml，
    "空格让整串左偏"的旧理由不再成立，但合写仍是规范写法，规则不变。）
    只合并**字面紧邻**的组：`<哐,kuāng>当 <哐,kuāng>当` 中间隔着字，不动。
    """
    n = 0
    while True:
        merged, k = ADJACENT_RUBY.subn(
            lambda m: f"<{m.group(1)}{m.group(3)},{m.group(2)}{m.group(4)}>", text)
        if not k:
            return merged, n
        text, n = merged, n + k


def lua_quote(s: str) -> str:
    """把译文包成 lua 双引号字符串。译文里的 \\ 与 " 必须转义，否则编译报错或截断。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def load_translations() -> tuple[dict[int, str], dict[str, str]]:
    """读车道当前生效译文。车道目录来自 layers/manifest.toml 的 [lane].dir，
    不再是本文件写死的 LANE 常量：车道路径此前在 inject_lua / build_font /
    migrate_base 三处硬编码，本函数是第一处收口，另两处不在本次瘦身范围。
    """
    lane = REPO / load_manifest()["lane"]["dir"]
    zh = resolve_map(read_jsonl(lane / "forward.jsonl"), read_jsonl(lane / "patches.jsonl"))
    extra: dict[str, str] = {}
    for row in read_jsonl(lane / "forward_extra.jsonl"):
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
                if row["literal"]:
                    text_zh, merged = merge_adjacent_ruby(text_zh)
                    stats["ruby_merged"] += merged
                    text_zh, n_wrap = fix_latin_splits(text_zh, strategy=stats.get("_latin_strategy", "a"))
                    stats["latin_wrapped"] = stats.get("latin_wrapped", 0) + n_wrap
                new = lua_quote(text_zh) if row["literal"] else text_zh
                stats["vms"] += 1
                return _replace_span(body, m.start(3), m.end(3), new)
        return body

    # ---- extra：两个特例 + 共用的 SIMPLE_EXTRA 表 ----
    # ⚠ 表是**直接 import 的同一个对象**，不是照抄一份。这里曾与 build_ledger 各写
    # 一条 elif 链，结果 build_ledger 那边加了识别规则、这边没加，就会静默漏译。
    if m := PLOT_TITLE_RE.match(body):
        return _sub_extra(body, m, 2, f"plotTitle:{m.group(1)}", extra, stats)
    if m := SAVEDATA_RE.search(body):
        for i in (2, 1):  # 从右往左替换，保住左侧 span
            body = _sub_extra(body, m, i, f"{stem}:{lineno}:{i}", extra, stats,
                              allow_empty=True)
            m = SAVEDATA_RE.search(body)  # 左参替换后右参 span 已失效，重新匹配
        return body
    for _kind, rx in SIMPLE_EXTRA:
        if m := rx.search(body):
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
    text_zh, n_wrap = fix_latin_splits(text_zh, strategy=stats.get("_latin_strategy", "a"))
    stats["latin_wrapped"] = stats.get("latin_wrapped", 0) + n_wrap
    stats["extra"] += 1
    return _replace_span(body, m.start(group), m.end(group), text_zh)


def inject_tree(base_dir: Path, ledger_rows: list[dict], zh: dict[int, str],
                extra: dict[str, str], latin_strategy: str = "a") -> tuple[dict[str, str], dict]:
    """注入整棵基座，返回 (文件名→注入后源, 统计)。行数与行号严格不变。

    ⚠ 不做字体改写、不编译、不写盘——那些分别是 layers/overlays/fonts.toml 与
    build_disc 的职责。本函数是纯函数，好测。
    """
    by_file: dict[str, dict[int, dict]] = {}
    for row in ledger_rows:
        by_file.setdefault(row["file"], {})[row["line"]] = row
    stats = dict(vms=0, vms_missing=0, vms_unledgered=0, extra=0, extra_missing=0,
                 ruby_merged=0, latin_wrapped=0, _latin_strategy=latin_strategy)
    out: dict[str, str] = {}
    for f in sorted(Path(base_dir).glob("*.lua")):
        out[f.name] = inject_text(f.stem, f.read_text(encoding="utf-8"),
                                  by_file.get(f.stem, {}), zh, extra, stats)
    return out, stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help=f"注入后 lua 源写到这里（调试用；发布链路走 layers/ + "
                         f"build_disc），默认 {DEFAULT_OUT}")
    ap.add_argument("--only", help="逗号分隔的文件 stem，只把这些写盘"
                                   "（调试用；统计仍覆盖全部文件）")
    args = ap.parse_args()

    zh, extra = load_translations()
    print(f"[inject] 译文 vms={len(zh)} extra={len(extra)}")

    ledger_rows = read_jsonl(REPO / "data" / "ledger.jsonl")
    out, stats = inject_tree(SRC, ledger_rows, zh, extra)

    only = set(args.only.split(",")) if args.only else None
    args.out.mkdir(parents=True, exist_ok=True)
    n = 0
    for name, text in out.items():
        if only is not None and Path(name).stem not in only:
            continue
        (args.out / name).write_text(text, encoding="utf-8")
        n += 1

    print(f"[inject] vms 替换 {stats['vms']}（缺译 {stats['vms_missing']}，"
          f"账本外 {stats['vms_unledgered']}）；extra 替换 {stats['extra']}"
          f"（缺译/留空 {stats['extra_missing']}）；ruby 合并 {stats['ruby_merged']} 次")
    print(f"[inject] 写出 {n}/{len(out)} 个文件 → {args.out}")


if __name__ == "__main__":
    main()
