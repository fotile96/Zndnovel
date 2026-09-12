#!/usr/bin/env python3
"""Summarize each snr_crd_N.lua: stub/puzzle type, required cards, accepted
answer cards, granted cards, launched section scripts, oCard.show messages.

Usage:
    python3 tools/extract_crd.py > analysis/crd_summary.txt

Interpretation of fields:
    STUB        9-10 line script that only shows 「≪入手済みカード≫」(keyword /
                synopsis cards obtained elsewhere, e.g. by listening in Story mode)
    req         cards whose absence triggers oCard.mesNot (prerequisites)
    answersCmp  card ids compared against the player's hand-in, as matched by a
                loose regex that also picks up the wrong-card counter's 0/1.
                ⚠ Do NOT read this as "ids >= 2 are the real answers" (the claim
                this line used to make): card 1『ある子が学校にくる物語』IS a real
                answer for crd_2/30/108. Telling them apart needs the binding of
                oCard.selectCardObj()'s return variable, which this loose pass does
                not do -- see tools/build_dag.py::parse_crd_answers (membership) and
                tools/build_guide.py::expected_hand_order (membership + order).
    gets        myCard[...] granted on success (fragmentDoCardId = this card)
    runs        section scripts launched (chapter-final cards run the _f chapter)
    MSG         oCard.show acquisition message (translatable text)
"""
import re, os, glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(REPO, "lua_scripts")

# Decompiler local-name shapes: current base emits l<depth>_<reg> / u<n>;
# older bases used v<n>/p<n>. Accept all so the comparison scan stays anchored
# on "a local compared against a card id", never on one base's naming scheme.
LOCAL_NAME = r'(?:l\d+_\d+|u\d+|v\d+|p\d+)'

CARD_IDX = r'(\d+|gameSave\.fragmentDoCardId)'
GET_DIRECT = re.compile(r'gameSave\.myCard\[' + CARD_IDX + r'\]\.hold = 1')
GET_ALIAS_BIND = re.compile(
    r'^(?:local\s+)?(' + LOCAL_NAME + r')\s*=\s*gameSave\.myCard\[' + CARD_IDX + r'\]\s*$')
GET_ALIAS_SET = re.compile(r'^(' + LOCAL_NAME + r')\.hold = 1\s*$')

def collect_gets(text):
    """Card ids granted, in document order.

    The base sometimes binds the card row to a local first
    (`local l1_0 = gameSave.myCard[...]` / `l1_0.hold = 1`), so a plain
    `myCard[..].hold = 1` scan under-reports; resolve the alias too.
    """
    gets, alias = [], {}
    for ln in text.splitlines():
        s = ln.strip()
        m = GET_ALIAS_BIND.match(s)
        if m:
            alias[m.group(1)] = m.group(2)
            continue
        m = GET_DIRECT.search(s)
        if m:
            gets.append(m.group(1))
            continue
        m = GET_ALIAS_SET.match(s)
        if m and m.group(1) in alias:
            gets.append(alias[m.group(1)])
    return gets

def summarize(path):
    n = int(re.search(r'snr_crd_(\d+)\.lua', path).group(1))
    text = open(path, encoding="utf-8").read()
    lines = text.count("\n") + 1
    vms_count = len(re.findall(r'vms\(', text))
    stub = vms_count <= 2 and lines < 15
    req = sorted(set(int(x) for x in re.findall(r'gameSave\.myCard\[(\d+)\]\.hold == -1', text)))
    ans = sorted(set(int(x) for x in re.findall(r'if ' + LOCAL_NAME + r' == (\d+) then', text)))
    gets = collect_gets(text)
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
