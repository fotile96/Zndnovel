#!/usr/bin/env python3
"""Dump story text (vms lines) with scene markers, one digest per lua file.

Usage:
    python3 tools/extract_text.py [lua files...]

Writes one <name>.txt per input into analysis/text_digest/ (default: all
lua_scripts/snr_*.lua). Digest format:
    ### scene_xxx / card_xxx / main     -- function boundary
    [VOICEID]text                       -- vms line (tag omitted for NONVOICE/NORECORD)
    **CARD-GET: ...                     -- oCard.show acquisition message
    == BEGIN <sceneId> 「title」        -- comSectionStoryBegin marker
Layer/audio staging calls are dropped; only narrative text survives.
"""
import re, sys, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(REPO, "lua_scripts")
OUT_DIR = os.path.join(REPO, "analysis", "text_digest")
os.makedirs(OUT_DIR, exist_ok=True)

def digest(path):
    name = os.path.basename(path).replace(".lua", "")
    out = []
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        # Function headers: the decompiler base emits `local NAME = function` for
        # 890 of them and bare `NAME = function` for the rest; accept both.
        m = re.match(r'(?:local\s+)?(scene_[A-Za-z0-9_]+|card_[A-Za-z0-9_]+|main) = function', s)
        if m:
            out.append(f"\n### {m.group(1)}")
            continue
        m = re.search(r'vms\(\d+, "([A-Z0-9]+|NONVOICE|NORECORD)", (.+)\)$', s)
        if m:
            txt = m.group(2)
            # strip trailing tr_line comment
            txt = re.sub(r'\)?\s*-- tr_line:\d+$', '', txt)
            txt = txt.strip()
            if txt.startswith('"') and txt.endswith('"'):
                txt = txt[1:-1]
            voice = m.group(1)
            tag = "" if voice in ("NONVOICE", "NORECORD") else f"[{voice}]"
            out.append(f"{tag}{txt}")
            continue
        m = re.search(r'oCard\.show\([^,]+, "(.+)"\)', s)
        if m:
            out.append(f"**CARD-GET: {m.group(1)}")
            continue
        m = re.search(r'comSectionStoryBegin\("([^"]+)", "([^"]+)"\)', s)
        if m:
            out.append(f"== BEGIN {m.group(1)} 「{m.group(2)}」")
    open(os.path.join(OUT_DIR, name + ".txt"), "w", encoding="utf-8").write("\n".join(out))
    return name, len(out)

if __name__ == "__main__":
    import glob
    files = sys.argv[1:] or sorted(glob.glob(f"{SCRIPT_DIR}/snr_*.lua"))
    total = 0
    for f in files:
        n, c = digest(f)
        total += c
        print(f"{n}: {c} lines")
    print("TOTAL:", total)
