"""tools/bake_finale_voice.py：谢幕『声』选择画面六张图——提示/脚注只改各自文字带，按钮墨迹不出画布，
暗态封顶、亮态带副题；擦框羽化只碰框边。"""
from PIL import Image, ImageChops

from tools import bake_event_voice as ev
from tools import bake_finale_voice as bfv


def test_jobs_are_the_six_members_with_agreed_punctuation():
    assert bfv.PROMPT[0] == "eve_0_j" and bfv.FOOTNOTE[0] == "eve_0_k"
    assert [b[0] for b in bfv.BUTTONS] == ["sel_fin1_sel_a", "sel_fin2_sel_a"]
    assert all(t.startswith("「") and t.endswith("」") for _n, t, _s in bfv.BUTTONS)      # D12：标题带引号
    assert not any(s.endswith("。") for _n, _t, s in bfv.BUTTONS)                          # 副题不加句号
    assert not bfv.FOOTNOTE[1].endswith("。") and bfv.PROMPT[1] == "你的声音是——"


def test_prompt_only_differs_from_eve_0_i_inside_its_band(tmp_path):
    bfv.bake_all(tmp_path)
    out = Image.open(tmp_path / bfv.FACE_EVENT / "eve_0_j.png").convert("RGB")
    base = Image.open(ev.EVENT_DIR / "eve_0_i.png").convert("RGBA").convert("RGB")   # 原图是带 tRNS 的 P 图
    assert out.size == (480, 272)
    bbox = ImageChops.difference(out, base).getbbox()
    lo, hi = ev.EVE_0_I_PATCH_Y
    assert bbox and bbox[1] >= lo - 12 and bbox[3] <= hi + 12, bbox   # 光晕尾巴（半径 3.5）允许溢出补底带几像素


def test_footnote_only_differs_from_eve_0_h_inside_its_box(tmp_path):
    bfv.bake_all(tmp_path)
    out = Image.open(tmp_path / bfv.FACE_EVENT / "eve_0_k.png").convert("RGB")
    base = Image.open(ev.EVENT_DIR / "eve_0_h.png").convert("RGBA").convert("RGB")   # 原图是带 tRNS 的 P 图
    x0, y0, x1, y1 = bfv.FOOTNOTE[2]
    bbox = ImageChops.difference(out, base).getbbox()
    assert bbox and bbox[0] >= x0 - 4 and bbox[1] >= y0 - 4 and bbox[2] <= x1 + 4 and bbox[3] <= y1 + 4, bbox


def test_buttons_are_480x82_ink_inside_off_capped_on_has_subtitle(tmp_path):
    bfv.bake_all(tmp_path)
    for name, _t, _s in bfv.BUTTONS:
        for variant in ("on", "off"):
            im = Image.open(tmp_path / bfv.FACE_SELECT / f"{name}_{variant}.png").convert("RGBA")
            assert im.size == (480, 82)
            bbox = im.getbbox()
            assert bbox and bbox[0] >= 8 and bbox[2] <= 472, (name, variant, bbox)     # 光晕不贴边
            amax = im.getchannel("A").getextrema()[1]
            if variant == "off":
                assert amax <= 170, (name, amax)                 # 暗态封顶（原图 ≈152）
            else:
                assert amax >= 240 and bbox[3] > 40, (name, amax, bbox)  # 亮态（核心经 0.3 px 微模糊仍近全不透明）且有副题行（y>36）


def test_feather_blends_only_the_box_edges():
    im = Image.new("RGBA", (40, 20), (100, 100, 100, 255))
    for x in range(10, 30):
        for y in range(6, 14):
            im.putpixel((x, y), (250, 250, 250, 255))       # 框内一块要被擦掉的"字"
    hard = ev._interpolate_bg(im, (10, 6, 30, 14), 0)
    soft = ev._interpolate_bg(im, (10, 6, 30, 14), 4)
    assert hard.getpixel((10, 10))[0] == 100                # 无羽化：框内全由上下锚行插值
    assert 100 < soft.getpixel((10, 10))[0] < 250           # 羽化：框边像素混入原像素
    assert soft.getpixel((20, 10))[0] == 100                # 框心不受影响
    assert ev._interpolate_bg(im, (10, 6, 30, 14)).tobytes() == hard.tobytes()   # 缺省 feather=0 与旧行为一致


def test_toned_patch_rebuilds_a_dimmed_background_from_its_clean_source():
    """eve_0_h ≈ 0.556·eve_0_g（同一张 CG 统一压暗）：框外逐通道拟合 a·src+b，框内用映射后的无字底图重建——
    斜向纹理照样还原，不像竖向插值那样把光带抹成平块。"""
    src = Image.new("RGBA", (60, 30))
    img = Image.new("RGBA", (60, 30))
    for x in range(60):
        for y in range(30):
            px = ((x * 4 + y * 3) % 256, (x * 2 + 40) % 256, (y * 7 + x) % 256, 255)   # 斜向纹理
            src.putpixel((x, y), px)
            img.putpixel((x, y), tuple(v // 2 + 10 for v in px[:3]) + (255,))
    for x in range(20, 40):
        for y in range(10, 20):
            img.putpixel((x, y), (250, 250, 250, 255))       # 框内的"字"
    out = ev._toned_patch(img, src, (18, 8, 42, 22))
    for x in range(18, 42):
        for y in range(8, 22):
            want = tuple(v // 2 + 10 for v in src.getpixel((x, y))[:3])
            got = out.getpixel((x, y))[:3]
            assert all(abs(a - b) <= 1 for a, b in zip(got, want)), ((x, y), got, want)
    assert out.getpixel((5, 5)) == img.getpixel((5, 5))     # 框外不动
