#!/usr/bin/env python3
"""Summarize each snr_crd_N.lua: stub/puzzle type, required cards, accepted
answer cards, granted cards, launched section scripts, oCard.show messages.

Usage:
    python3 tools/extract_crd.py > analysis/crd_summary.txt

Interpretation of fields:
    STUB        9-10 line script that only shows 「≪入手済みカード≫」(keyword /
                synopsis cards obtained elsewhere, e.g. by listening in Story mode)
    req         cards whose absence triggers oCard.mesNot (prerequisites)
    answersCmp  card ids compared against the player's hand-in (0/1 are loop
                control constants; the real answers are the ids >= 2)
    gets        myCard[...] granted on success (fragmentDoCardId = this card)
    runs        section scripts launched (chapter-final cards run the _f chapter)
    MSG         oCard.show acquisition message (translatable text)
"""
import re, os, glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(REPO, "lua_scripts")

def summarize(path):
    n = int(re.search(r'snr_crd_(\d+)\.lua', path).group(1))
    text = open(path, encoding="utf-8").read()
    lines = text.count("\n") + 1
    vms_count = len(re.findall(r'vms\(', text))
    stub = vms_count <= 2 and lines < 15
    req = sorted(set(int(x) for x in re.findall(r'gameSave\.myCard\[(\d+)\]\.hold == -1', text)))
    ans = sorted(set(int(x) for x in re.findall(r'if v\d+ == (\d+) then', text)))
    gets = re.findall(r'gameSave\.myCard\[(\d+|gameSave\.fragmentDoCardId)\]\.hold = 1', text)
    shows = re.findall(r'oCard\.show\([^,]+, "([^"]+)"\)', text)
    runs = sorted(set(re.findall(r'run\(cGetFileName\("scriptc?", "(snr_[a-z0-9_]+)"\)\)', text)) - {"snr_fragment_main", "snr_mainmenu"})
    sel = len(re.findall(r'selectCardObj|selectCardNotCancelObj', text))
    parts = [f"crd_{n}: {lines}L vms={vms_count}"]
    if stub: parts.append("STUB(既得カード表示のみ)")
    if req: parts.append(f"req={req}")
    if sel: parts.append(f"cardSelects={sel}")
    if ans: parts.append(f"answersCmp={ans}")
    if gets: parts.append(f"gets={gets}")
    if runs: parts.append(f"runs={runs}")
    for s in shows:
        parts.append(f"MSG:{s}")
    return n, "  ".join(parts)

if __name__ == "__main__":
    rows = sorted(summarize(f) for f in glob.glob(f"{SCRIPT_DIR}/snr_crd_*.lua"))
    for n, s in rows:
        print(s)
