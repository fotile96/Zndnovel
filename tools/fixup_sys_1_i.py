"""Post-bake fixup for sys_1_i: remove glow-tail and old-text residuals.

The bake pipeline for sys_1_i produces two types of artifacts:

1. **New text glow tail**: The glyph is rendered on a transparent canvas,
   producing nearly-black low-alpha pixels (R<10, alpha 54-119) that win
   the _merge_farther compositing comparison against the correct panel bg
   (0,0,0,127) because they're "farther from bg" in premultiplied L1
   distance. Visible as a diagonal '>' band to the right of row 0 text.

2. **Old text gray residual**: Old Japanese text glow beyond d_old >= r_old
   (=6) isn't erased. Shows as gray (R=G=B, 3-34) pixels in the area
   below the Chinese text where the old third line was.

Fix: replace all such pixels with panel bg (0,0,0,127).
Only touches pixels that the bake pipeline already modified (differ from
the original source PNG); original-identical pixels are never changed.
Safe zones left untouched: border (y>=62), edges (x>=188).

Run after bake_sysgim_note.py:
    uv run python tools/fixup_sys_1_i.py
"""

from pathlib import Path
from PIL import Image

SRC = Path("png/sysgim/sys_1_i.png")
BAKED = Path("build/sysgim_note_zh/sys_1_i.png")
PANEL_BG = (0, 0, 0, 127)
BORDER_Y = 62
EDGE_X = 188


def fixup(path: Path = BAKED, src: Path = SRC) -> int:
    img = Image.open(path).convert("RGBA")
    orig = Image.open(src).convert("RGBA")
    px = img.load()
    op = orig.load()
    w, h = img.size
    count = 0

    for y in range(5, BORDER_Y):
        for x in range(min(EDGE_X, w)):
            r, g, b, a = px[x, y]
            if (r, g, b, a) == PANEL_BG:
                continue
            if px[x, y] == op[x, y]:
                continue

            if a == 0:
                px[x, y] = PANEL_BG
                count += 1
                continue

            is_warm = r > 12 and g < r and b < r and (r - max(g, b)) > 5
            if is_warm:
                continue

            spread = max(r, g, b) - min(r, g, b)

            if r < 10 and g < 5 and b < 5 and a < 125:
                px[x, y] = PANEL_BG
                count += 1
            elif spread < 15 and r < 50 and a < 145:
                px[x, y] = PANEL_BG
                count += 1

    img.save(path)
    return count


if __name__ == "__main__":
    if not BAKED.exists():
        raise SystemExit(f"{BAKED} not found -- run bake_sysgim_note.py first")
    n = fixup()
    print(f"fixup_sys_1_i: {n} pixels -> panel bg in {BAKED}")
