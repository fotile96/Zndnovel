#!/usr/bin/env python3
"""烤字字体的统一取用口——**按面**可换。

在此之前字体有两套写法：sysgim 两个工具认 `ZND_UI_FONT`，plot/scene/card/select
四个把路径写死。于是「换个字体看看」在四个面上根本做不到。

**为什么要按面而不是一个全局变量。** 各面的字号档位差得很远：

| 面 | 字号 | 额外负担 |
|---|---|---|
| `select/` | 18/17px | 描边 |
| `sysgim/` | 12–17px | 描边、或字芯+距离场发光 |
| `scene/` | 11/10/9px | 无（15px 行高，垂直余量已用尽） |
| `card/` | 11/9/9px | 无（正文最紧的行只余 2px） |
| `plot/` | 定档 | 82×48 的格子 |

同一套字在 18px 和 9px 上不是一回事：霞鹜文楷 Regular 在 15px 以下笔干到不了一个
像素，整行发灰（sysgim 那边为此加了 `ZND_UI_FILL_GAIN=2.2` 的补偿）。所以合理的
终局多半是"大字号一套、小字号另一套"，而不是全库一套。

**用法。**

    # 全库换一套试
    ZND_UI_FONT=/path/to/Other.ttf uv run python tools/bake_card.py

    # 只给 card 换，其余仍用默认
    ZND_UI_FONT_CARD=/path/to/Other.ttf uv run python tools/bake_card.py

    # 各面分别指定
    ZND_UI_FONT=/path/to/Big.ttf ZND_UI_FONT_CARD=/path/to/Small.ttf ...

优先级：`ZND_UI_FONT_<面>` > `ZND_UI_FONT` > 随仓库分发的霞鹜文楷 Regular。

**字体集合（.ttc）用 `路径#N` 取其中一款**，环境变量与配置文件同一套解析：

    ZND_UI_FONT_CUTIN=/System/Library/Fonts/Supplemental/Songti.ttc#3 \
        uv run python tools/bake_cutin_title.py

集合**不带索引会被拒**，见 `_check_index` 处的说明——不是从严，是那种"看起来
正常"的错。


⚠ **换字体后测试会红**，这是对的：金标夹具里的墨迹尺寸、字号回落集、溢出判定全都是
对着默认字体实测出来的。换字评估应当看图与看 manifest，不是看测试绿不绿。

⚠ 换成 Bold 字形时 sysgim 两个工具的 `ZND_UI_FILL_GAIN` 要一并调回 1.0——增益是为
补 Regular 细笔调而加的，粗体上再叠只会把字腔糊死（裁决 Y6/Y14）。
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import ImageFont

REPO = Path(__file__).resolve().parent.parent

#: 随仓库分发（裁决 G1：25.6MB，入库以保证换机器即开即用；SIL OFL）。
BUNDLED = REPO / "third_party" / "LXGWWenKai-Regular.ttf"

#: 有字可换的五个面。**写成白名单**，好让打错的面名当场炸掉——
#: `ZND_UI_FONT_CARDS`（多个 s）若被默默忽略，人会以为"换了没效果"。
FACES = ("PLOT", "SCENE", "CARD", "SELECT", "SYSGIM", "EVENT", "CUTIN")


#: 持久配置：哪一面（必要时哪一张）最后用了哪套字。见该文件头部的优先级说明。
CONFIG = REPO / "config" / "bake_fonts.yaml"

_CONFIG_CACHE: dict | None = None


def _config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        if CONFIG.exists():
            import yaml
            _CONFIG_CACHE = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        else:
            _CONFIG_CACHE = {}
    return _CONFIG_CACHE


def _config_entry(face: str, sheet: str | None) -> dict:
    """配置里对这一面（必要时这一张）的条目；逐张优先于逐面，逐面优先于兜底。"""
    cfg = _config()
    faces = cfg.get("faces") or {}
    entry = faces.get(face.lower()) or {}
    if sheet:
        sheets = entry.get("sheets") or {}
        if sheet in sheets:
            merged = dict(entry)
            merged.pop("sheets", None)
            merged.update(sheets[sheet] or {})
            return merged
    if entry:
        out = dict(entry)
        out.pop("sheets", None)
        return out
    return dict(cfg.get("default") or {})


def _split_index(spec: str) -> tuple[str, int | None]:
    """把 `路径#N` 拆成路径与子字体索引；没写索引则第二项为 None。

    只认结尾的 `#<数字>`，故文件名里出现 `#` 不受影响（`a#b.ttf` 原样返回）。
    """
    head, sep, tail = spec.rpartition("#")
    if sep and tail.isdigit():
        return head, int(tail)
    return spec, None


def _num_faces(path: Path) -> int:
    """字体文件里装了几款。

    TTC 头是 `ttcf` + 版本(2+2) + numFonts(4)，12 字节读完即知——不必开字体，
    也就不必为此引入 fontTools。非集合（普通 ttf/otf）一律算 1 款。
    """
    with path.open("rb") as fh:
        head = fh.read(12)
    if head[:4] != b"ttcf":
        return 1
    return int.from_bytes(head[8:12], "big")


def _check_index(path: Path, idx: int | None) -> int:
    """把「写了/没写索引」判成确定的一款，或者报错。

    **集合不带索引必须报错，不能默认取第 0 款。** `Songti.ttc` 的第 0 款实测是
    Songti SC **Black**——集合里最重的一款，而不是常规字重。它不报错、不缺字，
    只是"比预期黑一圈"，于是你以为在评估宋体正文、看到的却是黑体级字重的宋。
    这与 `SourceHanSansSC-VF` 默认实例是 ExtraLight 是同一种失效形态
    （见 `DEFAULT_VF_INSTANCE`），处理也一样：当场炸掉，并列出可选范围。

    越界也自己判：Pillow 只会抛 `OSError: invalid argument`，看不出是索引的事。
    """
    n = _num_faces(path)
    if n == 1:
        if idx not in (None, 0):
            raise ValueError(
                f"{path.name} 不是字体集合（只有 1 款），无法取索引 {idx}——"
                f"`#N` 只对 .ttc 这类集合有意义"
            )
        return 0
    if idx is None:
        raise ValueError(
            f"{path.name} 是含 {n} 款子字体的集合，须写成 `路径#N` 指明取哪一款"
            f"（N=0..{n - 1}）——不指明会静默取第 0 款，而第 0 款未必是常规字重"
            f"（Songti.ttc 的第 0 款是 Black）"
        )
    if not 0 <= idx < n:
        raise ValueError(
            f"{path.name} 只有 {n} 款子字体（N=0..{n - 1}），索引 {idx} 越界")
    return idx


def _resolve_spec(face: str, sheet: str | None = None) -> tuple[Path, int]:
    """字体的完整取用结果：文件 + 子字体索引。`resolve`/`index` 都从这里取。

    优先级：`ZND_UI_FONT_<面>` > `ZND_UI_FONT` > 配置的逐张 > 逐面 > 兜底 > 随仓库
    分发的霞鹜文楷。环境变量胜出是刻意的——它是试验用的临时开关，配置文件是持久决定。

    路径不存在时抛 `FileNotFoundError` 而**不回落到默认字体**：悄悄回落意味着
    你以为在评估新字体，看到的却仍是霞鹜文楷——而两次输出的差别恰好是零，
    最像"这字体没救了"的那种零。
    """
    key = face.upper()
    if key not in FACES:
        raise ValueError(f"未知的烤字面 {face!r}；可用：{', '.join(FACES)}")

    for var in (f"ZND_UI_FONT_{key}", "ZND_UI_FONT"):
        val = os.environ.get(var)
        if not val:
            continue
        raw, idx = _split_index(val)
        p = Path(raw)
        if not p.exists():
            raise FileNotFoundError(f"{var} 指向的字体不存在：{p}")
        return p, _check_index(p, idx)

    cfg_font = _config_entry(face, sheet).get("font")
    if cfg_font:
        raw, idx = _split_index(str(cfg_font))
        p = Path(raw)
        if not p.is_absolute():
            p = REPO / p
        if not p.exists():
            raise FileNotFoundError(
                f"{CONFIG.name} 给 {face}"
                f"{'/' + sheet if sheet else ''} 指的字体不存在：{p}")
        return p, _check_index(p, idx)

    return BUNDLED, 0


def resolve(face: str, sheet: str | None = None) -> Path:
    """取某个面（必要时某一张）该用的字体**文件**路径（不含 `#N`）。

    优先级与报错见 `_resolve_spec`。集合选了哪一款用 `index()` 取——分成两个
    取用口是因为消费者里有 `FONT_PATH = str(resolve(...))` 这种要能直接 open 的。
    """
    return _resolve_spec(face, sheet)[0]


def index(face: str, sheet: str | None = None) -> int:
    """该面用集合里的第几款；非集合恒为 0。优先级同 `resolve`。"""
    return _resolve_spec(face, sheet)[1]


#: 变量字体在没有显式指定重量时用哪一档。
#:
#: **不用字体自己的默认实例**——`SourceHanSansSC-VF` 的默认实例是 ExtraLight(250)，
#: 那是权重轴的**最小值**而非设计者推荐的正文字重。裸调 `ImageFont.truetype()` 拿到
#: 的就是它，于是两千多张图会在发丝级字重下烤出来，与「霞鹜文楷太细」这个换字动机
#: 恰好相反。而它**看起来是正常的**：不报错、不缺字，只是整体更灰一点——正是最容易
#: 被误读成「这字体不行」的失效形态。
DEFAULT_VF_INSTANCE = "Regular"


def _variation_names(font) -> list[str]:
    """字体的命名实例；静态字体返回空表。"""
    try:
        return [n.decode("utf-8", "replace") if isinstance(n, bytes) else str(n)
                for n in font.get_variation_names()]
    except OSError:
        return []   # Pillow 对非变量字体抛 OSError


def weight(face: str, sheet: str | None = None) -> str | None:
    """该面（必要时该张）要求的重量；未指定返回 None。优先级同 `resolve`。"""
    key = face.upper()
    env = (os.environ.get(f"ZND_UI_FONT_WEIGHT_{key}")
           or os.environ.get("ZND_UI_FONT_WEIGHT"))
    if env:
        return env
    return _config_entry(face, sheet).get("weight")


def truetype(face: str, size: int, sheet: str | None = None):
    """取该面的字体对象，并把变量字体钉到确定的重量档上。

    优先级同路径：`ZND_UI_FONT_WEIGHT_<面>` > `ZND_UI_FONT_WEIGHT` >
    `DEFAULT_VF_INSTANCE`（仅当字体是变量字体时才有意义）。

    在**静态**字体上指定重量会抛 `ValueError` 而不是静默忽略：静默忽略意味着你以为
    在看 Bold、其实还是 Regular，而这正是拿来比较字重的场合，结论会整个反过来。
    """
    path, idx = _resolve_spec(face, sheet)
    font = ImageFont.truetype(str(path), size, index=idx)
    names = _variation_names(font)
    want = weight(face, sheet)

    if not names:
        if want:
            raise ValueError(
                f"{path.name} 不是变量字体，无法指定重量 {want!r}——"
                f"请改用该字重对应的独立字体文件"
            )
        return font

    want = want or DEFAULT_VF_INSTANCE
    if want not in names:
        raise ValueError(
            f"{path.name} 没有名为 {want!r} 的重量实例；可用：{', '.join(names)}"
        )
    font.set_variation_by_name(want)
    return font


def size_cascade(face: str, default: list[int]) -> list[int]:
    """该面的字号级联档位，可按面覆盖：`ZND_UI_SIZE_CASCADE_<面>` > `ZND_UI_SIZE_CASCADE`。

    **为什么这也得可配。** 各工具里的级联（select `[18,17]`、scene `[11,10,9]`）是当初
    对着霞鹜文楷逐格实测定下来的，**它是字体的函数**：思源黑体同 px 下字身更高，
    `select/` 134 个按钮里有 118 个在 17px 上就撞了文字框的下沿（框高仅 20px）。
    级联写死的话，换字体这件事在 `select/` 上直接做不成——工具会（正确地）拒绝
    静默截断，然后什么也烤不出来。

    档位只增不改语义：仍是从大到小逐档试，第一个不越界的胜出。

        ZND_UI_SIZE_CASCADE_SELECT=18,17,16,15 uv run python tools/bake_select.py
    """
    key = face.upper()
    if key not in FACES:
        raise ValueError(f"未知的烤字面 {face!r}；可用：{', '.join(FACES)}")
    raw = os.environ.get(f"ZND_UI_SIZE_CASCADE_{key}") or os.environ.get("ZND_UI_SIZE_CASCADE")
    if not raw:
        return list(default)
    try:
        sizes = [int(x) for x in raw.replace(" ", "").split(",") if x]
    except ValueError:
        raise ValueError(f"字号级联要写成逗号分隔的整数，收到 {raw!r}") from None
    if not sizes:
        raise ValueError("字号级联不能为空")
    if sizes != sorted(sizes, reverse=True):
        raise ValueError(f"字号级联须从大到小，收到 {sizes}——顺序错了会先试小档，结果全是小字")
    return sizes


def describe(face: str, sheet: str | None = None) -> str:
    """给报告用的一行自述：字体文件名 + 括号里那一档具体是什么。

    括号里放的是"同一个文件里到底取了哪一款"：变量字体是重量实例，集合是子字体
    自报的家族与样式。集合只写文件名等于没写——`Songti.ttc` 里有 8 款。
    """
    path, idx = _resolve_spec(face, sheet)
    font = ImageFont.truetype(str(path), 12, index=idx)
    label = path.name if _num_faces(path) == 1 else f"{path.name}#{idx}"
    names = _variation_names(font)
    if names:
        return f"{label}[{weight(face, sheet) or DEFAULT_VF_INSTANCE}]"
    if label != path.name:
        return f"{label}[{' '.join(font.getname())}]"
    return label
