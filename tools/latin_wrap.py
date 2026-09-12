#!/usr/bin/env python3
"""拉丁人名折行后处理：检测译文中会被引擎掰行的拉丁串，以两种策略修复。

策略 A（整词换行）：在拉丁串前插入 _r，把整个名字移到下一行。
策略 B（连字符断行）：在引擎会掰开的位置插入连字符 -，保持当前行排满。

用法（dry-run 模式，不改文件）：
    uv run python tools/latin_wrap.py --strategy a --dry-run
    uv run python tools/latin_wrap.py --strategy b --dry-run

注入管线挂载点：inject_lua.inject_text() 替换 vms 文本后、lua_quote 前调用
fix_latin_splits()；或独立跑 --apply 写回车道。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.msg_layout_check import (
    simulate, kinsoku_tables, ruby_pitch, advance, est, LINE_PX, Msg,
    LINES, BUF_BYTES
)

_ALNUM = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
_LATIN_WORD = re.compile(r'[A-Za-z][A-Za-z0-9]*')


def _body_start(text: str) -> int:
    if text.startswith("【"):
        j = text.find("】")
        return j + 1 if j >= 0 else 0
    return 0


def find_splits(text: str) -> list[dict]:
    """找出 text 中会被引擎掰行的拉丁串。返回 [{word, word_start, split_at, col_before}]。
    word_start/split_at 是相对原文（含 【名】）的字符索引。"""
    h, t = kinsoku_tables()
    lay = simulate(text, head=h, tail=t, pitch=ruby_pitch())
    if not any(f.code == "latin-split" for f in lay.findings):
        return []

    body_off = _body_start(text)
    body = text[body_off:]
    splits = []
    col = 0
    prev_ch = ""
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "_" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt == "n":
                i += 2; continue
            if nxt == "r":
                col = 0; prev_ch = ""; i += 2; continue
            i += 1; continue
        if ch == "<":
            end = body.find(">", i + 1)
            if end < 0: break
            parts = body[i + 1:end].split(",")
            base = parts[0]
            w = sum(advance(c) for c in base)
            col += w
            prev_ch = base[-1] if base else ""
            i = end + 1
            continue
        wrapped = False
        e = est(ch)
        if col + e > LINE_PX and ch not in set(h):
            if prev_ch in _ALNUM and ch in _ALNUM:
                word_m = None
                for m in _LATIN_WORD.finditer(body):
                    if m.start() <= i < m.end():
                        word_m = m
                        break
                if word_m:
                    splits.append({
                        "word": word_m.group(),
                        "word_start": body_off + word_m.start(),
                        "split_at": body_off + i,
                        "col_before": col,
                    })
            col = 0
            wrapped = True
        col += advance(ch)
        prev_ch = ch
        i += 1
    return splits


def fix_strategy_a(text: str, splits: list[dict]) -> str:
    """策略 A：在拉丁串前插 _r，整词换行。如果前面紧跟的是 CJK 字符（如 『），
    _r 插在 CJK 与拉丁串之间。"""
    if not splits:
        return text
    result = text
    offset = 0
    for sp in splits:
        pos = sp["word_start"] + offset
        result = result[:pos] + "_r" + result[pos:]
        offset += 2
    return result


def fix_strategy_b(text: str, splits: list[dict]) -> str:
    """策略 B：在掰行处插连字符 -。引擎会在行尾渲染 - 然后换行（- 在行头禁则表里会悬挂）。"""
    if not splits:
        return text
    result = text
    offset = 0
    for sp in splits:
        pos = sp["split_at"] + offset
        result = result[:pos] + "-" + result[pos:]
        offset += 1
    return result


def fix_latin_splits(text: str, strategy: str = "a") -> tuple[str, int]:
    """对一条 vms 文本做拉丁折行修复。返回 (修复后文本, 修复数)。"""
    splits = find_splits(text)
    if not splits:
        return text, 0
    if strategy == "a":
        fixed = fix_strategy_a(text, splits)
    elif strategy == "b":
        fixed = fix_strategy_b(text, splits)
    else:
        raise ValueError(f"未知策略 {strategy!r}")
    # Re-validate: the fix must not introduce page-overflow or other errors
    h, t = kinsoku_tables()
    lay = simulate(fixed, head=h, tail=t, pitch=ruby_pitch())
    errors = [f for f in lay.findings if f.level == "error"]
    if errors:
        return text, 0  # fix caused errors, revert
    return fixed, len(splits)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategy", choices=("a", "b"), default="a")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不改文件")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args(argv)

    from tools.inject_lua import load_translations
    zh, extra = load_translations()
    h, t = kinsoku_tables()
    P = ruby_pitch()
    total_fixed = 0
    for msg_id, text in sorted(zh.items()):
        splits = find_splits(text)
        if not splits:
            continue
        fixed, n = fix_latin_splits(text, args.strategy)
        if n == 0:
            print(f"  {msg_id}: 修复失败（会引入新错误），跳过")
            continue
        total_fixed += n
        if args.limit > 0:
            print(f"  {msg_id}: {splits[0]['word']} → ", end="")
            if args.strategy == "a":
                print(f"整词换行")
            else:
                print(f"连字符 {text[splits[0]['split_at'] - 1]}|{text[splits[0]['split_at']]}")
            # Show before/after
            lay_before = simulate(text, head=h, tail=t, pitch=P)
            lay_after = simulate(fixed, head=h, tail=t, pitch=P)
            print(f"    before: {lay_before.rows}")
            print(f"    after:  {lay_after.rows}")
            args.limit -= 1
    print(f"\n共 {total_fixed} 处修复（策略 {args.strategy}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
