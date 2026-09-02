#!/usr/bin/env -S uv run python
"""测试盘层生成器：产测试专用的层文件，不再直接写字节码。

原理不变：`snr_common.main()` 做完全部初始化（双字体 fontLoad、常驻图层、SE、IPL
演出、runAutoLoad）后 `run(script/snr_mainmenu)`；测试脚本作为**新增成员**
`script/snr_test.lua` 注入，并把这句引导交接改指向它，即可在完整初始化的环境里
直接跑测试代码。但引导交接的改写、IPL 开场的剥离，现在是 `layers/overlays/` 下
两个静态 test 层的事（`boot-handoff.toml`、`strip-ipl.toml`，Task 4 已产）——本工具
只管测试脚本本身与（card 模式的）递卡短路叠加层，不再碰 snr_common、不再编译
字节码、不再直接写封包成员树。

`generate(mode, out_dir, **opts) -> dict` 是唯一对外接口，产物：
  out_dir/scripts/snr_test.lua              测试引导脚本（新增成员 script/snr_test.lua）
  out_dir/overlays/card-short-circuit.toml  仅 card 模式：把递卡调用换成正确答案
落到 out_dir（CLI 缺省 build/test/generated/），由 build_disc 在静态 test 层之后
按文件名序施加（Task 8 接线）。返回值另带 `warnings`（已知会让产物在测试盘上
表现异常的告警，缺省空列表）。每次调用都会先清空 out_dir 下 scripts/、overlays/
两个子目录再写入，调用后磁盘内容与返回值严格一致，不会有上一轮的残留。

八种模式（--mode）：
  font     字体/ruby 探针：用 fontPrint 逐槽画样本串、用 msg 走正文管线画 ruby，
           每页停一帧等外部截图。回答 CLAUDE.md 悬置的两个问题——ruby 用哪个字体槽、
           该槽有没有带声调的拉丁元音。
  ruby     ruby 居中对齐测量：固定底字「记忆」，一页一种注音变体，跨页比较偏移。
  scene    跳场景：预置卡片/进度后直入指定章节场景（O(1) 抵达任意待验场景）。
  card     直入卡片谜题 crd_N，并产递卡短路叠加层，QA 不必在卡表里翻页找答案。
  cutin    章节首尾 cutin 一次过目：几何取自真实调用点的动画终态。
  mainmenu 全解锁真主菜单：195 卡全持有 + startMenuState=2，人工验收用。
  choices  全部 comDlgSelectItem 选择肢按钮串联过目。
  map      全部 comSelectMap 探索地图选点串联过目。
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    # 直接跑本脚本（uv run python tools/testboot.py）时 sys.path[0] 是 tools/
    # 而不是仓库根，_injected_source() 的 `from tools import inject_lua` 会
    # ModuleNotFoundError——补上仓库根，与 tools/layers.py 同一惯例。
    sys.path.insert(0, str(REPO))
#: 层生成器产物目录（CLI 缺省）；由 build_disc 在静态 test 层之后按文件名序施加。
OUT_DIR = REPO / "build" / "test" / "generated"
#: 选择肢串联时铺的底（教室，明暗中性，便于看清 on/off 两态按钮）
CHOICE_BG = "bg_1_a_0"

# 探针样本：(标签, 文本)。文本走 msg() 正文管线，故 ruby/控制码按引擎语义解释。
FONT_PAGES = [
    ("汉字与标点", "常用汉字：的一是了我不人在他有这个上们来到时大地为子中你说生国年着"
                   "_n标点：，。！？；：「」『』（）【】…—～"),
    ("拼音声调元音", "阴平：āēīōūǖ_n阳平：áéíóúǘ_n上声：ǎěǐǒǔǚ_n去声：àèìòùǜ_n其他：üńňǹ"),
    # 注音样本一律用**语料内**汉字：字库按语料裁剪，语料外的字必然空白
    ("ruby-拼音", "注音：<记忆,jì yì>与<彩野,cǎi yě>_n单字：<雹,báo>_n语料外字（应空白）：饕餮"),
    # ruby 居中对齐测量：同一底字、同一行首 x，只换注音串形态。
    # 猜想（用户提出）：native stub 按全角宽度估算 ruby 宽度来居中，半角拼音因此偏移。
    ("ruby-对齐A", "<记忆,jì yì>_n<记忆,きおく>_n<记忆,ｊｉｙｉ>_n<记忆, jì yì>"),
    ("ruby-对齐B", "<记忆,  jì yì>_n<记忆,   jì yì>_n<记忆,    jì yì>_n<记忆,jìyì>"),
    ("ruby-原作日文", "<前向性健忘,ぜんこうせいけんぼう>_n<話,はなし>を<紡,つむ>ぐ"),
    ("ruby-全角拉丁", "<Ｔｒｕｅ Ｃｏｌｏｒ,トゥルー カラー>_n<ＳｈｅｅｐＭａｎ,シープ・マン>"),
    ("控制码与记号", "≪强调≫ ≦特殊≧ 【说话人】「引用」_n○场景说明 ■系统通知"),
    ("行宽-40 全角", "四十个全角字符行宽测试一二三四五六七八九十一二三四五六七八九十"
                     "一二三四五六七八九十一二三四五六七八"),
    ("行宽-三行", "第一行：这是一句长度中等的中文对白，用来观察换行位置。"
                  "_n第二行：接着再写一句同样长度的中文对白继续观察。"
                  "_n第三行：最后一句，看看第三行会不会溢出消息窗下缘。"),
]

# ruby 居中对齐测量：一页一个变体，底字固定「记忆」且行首位置固定，
# 故各页注音簇可直接比较。native stub 的居中算法在 C 侧不可见，只能实测反推。
RUBY_VARIANTS = [
    ("四声-a", "āáǎà"),
    ("四声-i", "īíǐì"),
    ("四声-u", "ūúǔù"),
    ("实用样例", "jìyì"),
    ("数字调号", "ji4yi4"),
    ("无声调", "jiyi"),
    ("全角假名基准", "きおく"),
]

RUBY_TEMPLATE = '''-- 自动生成（tools/testboot.py）：ruby 居中对齐测量（一页一变体）
main = function()
    layerCopy(layerName.bg1, layerName.titleBG)
    switchScreen(0, "", 0)
    advPart(true)
    logEnable(true)
{pages}
    advPart(false)
    quit()
end
'''

FONT_TEMPLATE = '''-- 自动生成（tools/testboot.py）：字体/ruby 探针
-- 替换 script/snr_mainmenu.lua；snr_common.main() 初始化完毕后进入这里。
local probeFontSlots = function()
    -- 直接走 fontPrint（不经 cHan2Zen），逐槽验字形覆盖。
    -- 槽 0 = fontLoad(0,…) 的中文字体；槽 1 = fontLoad(1,…)，ruby/小字号候选。
    fontClear()
    fontPrint(0, 16, 24, 16777215, 255, "slot0 汉字 nǐ hǎo āáǎà ǖǘǚǜ 【】≪≫○■")
    fontPrint(1, 16, 56, 16777215, 255, "slot1 汉字 nǐ hǎo āáǎà ǖǘǚǜ 【】≪≫○■")
    fontPrint(0, 16, 88, 16777215, 255, "slot0 かなカナ 漢字 ABCabc 0123")
    fontPrint(1, 16, 120, 16777215, 255, "slot1 かなカナ 漢字 ABCabc 0123")
    fontPrint(0, 16, 152, 16777215, 255, "slot0 简体：记忆团体现关纯为长门")
    fontPrint(1, 16, 184, 16777215, 255, "slot1 简体：记忆团体现关纯为长门")
    switchScreen(0, "", 0)
    wait({hold})
    fontClear()
end

main = function()
    local v0
    probeFontSlots()
    -- 正文管线（msg）——ruby 与控制码只在这条路上被解释
    layerCopy(layerName.bg1, layerName.titleBG)
    switchScreen(0, "", 0)
    advPart(true)
    logEnable(true)
{pages}
    advPart(false)
    quit()
end
'''

CUTIN_TEMPLATE = '''-- 自动生成（tools/testboot.py）：章节首尾 cutin 一次过目
-- 每张按其**真实调用点的几何**摆放（位置/旋转取动画结束后的静止态），
-- 故能看出中文文案在原位置下会不会被屏幕边缘切掉。
main = function()
    layerLoad(layerName.bg1, "")
    fontClear()
{pages}
    quit()
end
'''

CUTIN_PAGE = '''    layerLoad(layerName.event, {ev})
    layerLoad(layerName.pose1, cGetFileName("cutin", "{name}"))
    layerPosition(layerName.pose1, {x}, {y})
    layerRotate(layerName.pose1, {r}, {r}, {r})
    layerAlpha(layerName.pose1, 100)
    cfontPrint(0, 8, 8, 16777215, 255, "{name}  @{x},{y}")
    switchScreen(0, "", 0)
    wait({hold})
    fontClear()
    layerLoad(layerName.pose1, "")
'''

MAINMENU_TEMPLATE = '''-- 自动生成（tools/testboot.py）：全解锁真主菜单（人工上手用）
-- 把决定菜单形态的进度全部拉满后交给**真正的** snr_mainmenu，
-- 于是四种形态里最全的那种、以及文库/回想/音乐/画廊/セクション7 全部可见可进。
main = function()
    local i0
    cardIDFlag = true
    for i0 = 1, 195 do
        gameSave.myCard[i0].hold = 1
    end
    gameSave.startMenuState = 2
    gameSave.tutorial.firstStory = 1
    gameSave.tutorial.firstFragmentBegin = 1
    gameSave.tutorial.firstFragment = 1
    gameSave.ayanoTime = 0
    cInitStoryRoute()
    -- 记忆路线预置：Story/Fragment 两个模式的时间轴要有内容，
    -- 否则进去是空的，看不到缩略图与场景名条。场景 ID 取自 data/dag.json。
    local route = {{{route}}}
    for i0 = 1, #route do
        gameSave.storyRoute[i0].sceneId = route[i0]
        gameSave.storyRoute[i0].ayanoTime = i0 * 3
    end
    -- ⚠ 不要在这里动 systemSave：那些字段是**数字**不是布尔。
    -- 2026-09-01 实测——曾写 systemSave.messageReadColor = true，而 snr_common:2569
    -- 用它做算术 `layerClip(…, messageReadColor * 17, …)`，进 option 画面即
    -- 「attempt to perform arithmetic on a boolean」当场卡死（日志表现为
    -- sceAudioOutputPannedBlocking channel not reserved 无限刷屏）。
    -- 何况这两个字段跟「解锁」无关，本就不该设。设置项交给 option 画面自己去改。
    run(cGetFileName("script", "snr_mainmenu"))
    quit()
end
'''

CHOICES_TEMPLATE = '''-- 自动生成（tools/testboot.py）：全部选择肢按钮串联过目
-- 逐个复现 lua 里的 comDlgSelectItem 调用（参数逐字照搬），**丢弃返回值**——
-- 选什么都不影响，按完就出下一组。这样一遍就能看完全部 {n} 组按钮的中文烤图。
main = function()
    local ret
    advPart(false)
{pages}
    quit()
end
'''

CHOICES_PAGE = '''    layerLoad(layerName.event, cGetFileName("bg", "{bg}"))
    layerLoad(layerName.pose1, "")
    switchScreen(0, "", 0)
    fontClear()
    cfontPrint(0, 6, 4, 16777215, 255, "{tag}")
    ret = comDlgSelectItem({args})
    fontClear()
'''

MAP_TEMPLATE = '''-- 自动生成（tools/testboot.py）：探索地图选点界面串联
-- comSelectMap 的调用同样逐字照搬、丢弃返回值。全库共 {n} 处，地点集合各不相同。
main = function()
    local ret
    advPart(false)
{pages}
    quit()
end
'''

MAP_PAGE = '''    fontClear()
    cfontPrint(0, 6, 4, 16777215, 255, "{tag}")
    ret = comSelectMap({args})
    fontClear()
'''

CARD_TEMPLATE = '''-- 自动生成（tools/testboot.py）：直入卡片谜题 crd_{card}
-- 预置全卡持有 + 目标卡号，绕过 fragment 时间轴直接跑卡脚本。
main = function()
    local i0
    cardIDFlag = true
    for i0 = 1, 195 do
        gameSave.myCard[i0].hold = 1
    end
    gameSave.startMenuState = 2
    gameSave.tutorial.firstStory = 1
    gameSave.tutorial.firstFragmentBegin = 1
    gameSave.tutorial.firstFragment = 1
    gameSave.ayanoTime = 0
    cInitStoryRoute()
    gameSave.fragmentDoCardId = {card}
    gameSave.fragmentDoSceneId = "{scene}"
    run(cGetFileName("script", "snr_crd_{card}"))
    quit()
end
'''

SCENE_TEMPLATE = '''-- 自动生成（tools/testboot.py）：跳场景 {scene}
-- 替换 script/snr_mainmenu.lua；预置进度后直入目标章节脚本。
main = function()
    local i0
    cardIDFlag = true
    for i0 = 1, 195 do
        gameSave.myCard[i0].hold = {hold}
    end
    gameSave.startMenuState = 2
    gameSave.tutorial.firstStory = 1
    gameSave.tutorial.firstFragmentBegin = 1
    gameSave.tutorial.firstFragment = 1
    gameSave.ayanoTime = 0
    cInitStoryRoute()
    doScriptScene = "{scene}"
    run(cGetFileName("script", "{script}"))
    quit()
end
'''


# 递卡短路：卡片谜题要玩家从持有卡里挑出正确卡才推进剧情。QA 时不想用按键在卡表里
# 翻页，就把 `oCard.selectCardObj()` 直接换成 data/dag.json 里记录的正确答案——
# 那份答案是 build_dag 从 `oCard.selectCardObj()` 接收变量的卡号比较里抽出来的，
# 与脚本自身同源。仅测试盘用。
SELECT_CALL = "oCard.selectCardObj()"


def card_answer(card: int) -> int:
    import json
    dag = json.loads((REPO / "data" / "dag.json").read_text(encoding="utf-8"))
    info = dag["crds"].get(str(card)) or {}
    ans = info.get("answers") or []
    if not ans:
        sys.exit(f"crd_{card} 在 dag.json 里没有 answers（可能是关键词卡 stub）")
    return ans[0]


def _dag_answers(card: int) -> list[int]:
    """dag.json 记录的、这张卡全部 `oCard.selectCardObj()` 比较对象的去重集合
    （build_dag.parse_crd_answers 的产出：按数值排序，不含调用点在文件里的先后
    次序、也不含重复）。`card_answer()` 只取其中最小的一个当**唯一**替换值；
    本函数把完整集合暴露出来，给「这张卡是不是多步骤、每步要交不同卡」的判断用
    （见 generate() 里对多答案卡的告警）。
    """
    import json
    dag = json.loads((REPO / "data" / "dag.json").read_text(encoding="utf-8"))
    return (dag["crds"].get(str(card)) or {}).get("answers") or []


def card_scene(card: int) -> str:
    """卡号 → 它所属的场景 ID（snr_common 的 sceneId2aCard 反查）。"""
    import re as _re
    txt = (REPO / "lua_scripts" / "snr_common.lua").read_text(encoding="utf-8")
    for m in _re.finditer(r'sceneId2aCard\.(\w+) = (\d+)', txt):
        if int(m.group(2)) == card and m.group(1) != "keyword":
            return m.group(1)
    return ""


def _injected_source(stem: str) -> str:
    """给定 lua 文件 stem（不带 .lua），返回**译文注入后**的源码（内存，不落盘）。

    tools/layers.py 模块 docstring 定的核心约束：叠加层在译文注入之后施加，锚点
    只准是代码文本。递卡短路的 target 恰恰是可能挤满 vms() 对白的卡脚本（crd_103
    这类大谜题一个文件十几处对白），构建时刻 find_all() 真正扫的是**这份**注入后
    的文本，不是 lua_scripts/ 的日文原文——`oCard.selectCardObj()` 本身不是可译
    字符串，两者在这个具体调用上「理应」不受译文影响，但「理应」不是「保证」；
    唯一让 count 必然对得上构建时真实命中数的做法，是这里就地产出同一份源，别处
    不再假定它跟基座原文等价。

    复用 tools.inject_lua 已经在跑、已被信赖的按 (file,line) 替换逻辑，只对单个
    文件现算——不像 tools.layers._injected_sources() 那样把整棵基座都注入一遍
    （那是给 `check --compare-compiled` 用的，需要全量比对；这里只要一个文件）。
    """
    from tools import inject_lua
    from tools.pipelib import read_jsonl

    src_path = REPO / "lua_scripts" / f"{stem}.lua"
    if not src_path.exists():
        sys.exit(f"缺 {src_path}")
    zh, extra = inject_lua.load_translations()
    ledger_rows = read_jsonl(REPO / "data" / "ledger.jsonl")
    rows = {r["line"]: r for r in ledger_rows if r["file"] == stem}
    stats = dict(vms=0, vms_missing=0, vms_unledgered=0, extra=0, extra_missing=0,
                 ruby_merged=0)
    return inject_lua.inject_text(stem, src_path.read_text(encoding="utf-8"),
                                  rows, zh, extra, stats)


def short_circuit_card(card: int) -> tuple[str, int]:
    """把卡脚本里的递卡调用换成正确答案，返回 (改后源码, 替换次数)。

    源取 `_injected_source`（译文注入后），不再读 `build/inject_src`——那是
    inject_lua.py 收缩为纯注入之前（Task 5）的旧默认输出位置，如今已不存在。
    """
    src = _injected_source(f"snr_crd_{card}")
    return src.replace(SELECT_CALL, str(card_answer(card))), src.count(SELECT_CALL)


def _count_select_calls(card: int) -> int:
    """card-short-circuit 叠加层的 `count`：与 `short_circuit_card` 数的必须是
    同一份源（译文注入后），故直接复用它的计数，不另起一份独立实现——两处各数
    一遍，将来译文管线一旦改变这份源的字面内容，就可能悄悄分叉出两个不同的数。
    """
    _, n = short_circuit_card(card)
    return n


# 章节首尾 cutin 的真实几何：从 lua 调用点现场提取，不写死——脚本改了这里自动跟上。
CUTIN_CALL = re.compile(r'cGetFileName\("cutin", "(cut_[se]_\w+)"\)')
CUTIN_POS = re.compile(r'layerPosition\(layerName\.pose1,\s*(-?\d+),\s*(-?\d+)')
CUTIN_MPOS = re.compile(r'layerMovePosition\(layerName\.pose1,\s*(-?\d+),\s*(-?\d+)')
CUTIN_ROT = re.compile(r'layerRotate\(layerName\.pose1,\s*(-?\d+)')
CUTIN_BG = re.compile(r'layerLoad\(layerName\.(?:event|bg1|bg2|bg3),\s*'
                      r'cGetFileName\("(event|bg|sysgim)", "(\w+)"\)\)')
CUTIN_FADE = re.compile(r'comEffect(?:FadeOut|WhiteOut|YellowIn|BlackOut)\(')


def scan_cutins() -> list[tuple]:
    """扫全部章节脚本，返回 [(图名, x, y, rot, 底)]，取**动画结束后的静止态**。

    章首 cut_s_*：从 (x, 242) 滑到 (x, 232) 并淡入 → 取 movePosition 的终点。
    章末 cut_e_*：在 (x, 10) 带 rot=10 淡入、再转回 0 → 取 rot=0。
    x 逐图不同（实测 150/190/250/255/270/350），中文文案宽度变了就可能被屏幕边缘
    切掉——这正是要一次过目的原因。同一张图多处调用时取首个（实测各处几何一致）。
    """
    seen: dict[str, tuple] = {}
    for f in sorted((REPO / "lua_scripts").glob("*.lua")):
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = CUTIN_CALL.search(line)
            if not m or m.group(1) in seen:
                continue
            win = "\n".join(lines[i:i + 14])
            mp, p, r = (CUTIN_MPOS.search(win), CUTIN_POS.search(win),
                        CUTIN_ROT.search(win))
            src = mp or p
            if not src:
                continue
            # 往回找当时铺的底：**先遇到淡出就说明画面已清空，底是黑的**。
            # 少这一条会把已被淡黑的 CG 误当成背景——实测 10 张章末 cutin 全在
            # 黑底上（前一场景先 comEffectFadeOut），13 张章首才真叠在 CG 上。
            bg = None
            for j in range(i - 1, max(0, i - 40), -1):
                if CUTIN_FADE.search(lines[j]):
                    break
                b = CUTIN_BG.search(lines[j])
                if b:
                    bg = (b.group(1), b.group(2))
                    break
            seen[m.group(1)] = (m.group(1), int(src.group(1)), int(src.group(2)),
                                0 if r else 0, bg)
    return [seen[k] for k in sorted(seen)]


# 选择肢与地图：逐字照搬调用参数（实测 79 处 comDlgSelectItem 全是字面量参数）。
DLG_CALL = re.compile(r'comDlgSelectItem\((.*)\)\s*$')
MAP_CALL = re.compile(r'comSelectMap\((.*)\)\s*$')
TRLINE = re.compile(r"\s*--\s*tr_line:\d+\s*$")


def scan_calls(pat: re.Pattern) -> list[tuple[str, str]]:
    """扫全部 lua，返回 [(来源标签, 参数原文)]，按文件名+行号排序。"""
    out = []
    for f in sorted((REPO / "lua_scripts").glob("*.lua")):
        for i, raw in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = pat.search(TRLINE.sub("", raw).strip())
            if m:
                out.append((f"{f.stem[4:]}:{i}", m.group(1)))
    return out


def story_route(n: int = 16) -> str:
    """取前 n 个 s1/s2 章故事场景 ID，给主菜单模式当预置记忆路线。"""
    import json
    dag = json.loads((REPO / "data" / "dag.json").read_text(encoding="utf-8"))
    ids = [k for k in dag["scene_meta"] if k.startswith(("s1s_", "s2s_"))]
    ids.sort(key=lambda k: (k[:3], int(re.sub(r"\D", "", k[4:]) or 0)))
    return ", ".join(f'"{k}"' for k in ids[:n])


def scene_to_script(scene: str) -> str:
    """场景 ID → 章节脚本名（comSectionUID2ScriptFileName 的规则）。"""
    if scene.startswith("fin-"):
        return "snr_finale"  # 谢幕章：编外 id，不合 UID 解析约定（刻意，不进路线）
    chap, mode = scene[:2], scene[2]
    suffix = mode
    if len(scene) > 3 and scene[3] in "abc" and mode == "f":
        suffix = mode + scene[3]
    return f"snr_{chap}_10_{suffix}"


_MODES = ("font", "scene", "ruby", "card", "cutin", "mainmenu", "choices", "map")


def _render_mode(mode: str, *, scene: str = "s1s_20", card: int | None = None,
                 hold: int = 180, no_cards: bool = False) -> str:
    """按模式渲染 `scripts/snr_test.lua` 的源码。原 main() 里的 if/elif 链搬到这里，
    返回值取代模块级变量；未知模式硬失败——没有 argparse 的 choices= 替它把关了。
    """
    if mode == "mainmenu":
        print("[testboot] 全解锁主菜单（195 卡 + startMenuState=2 + 预置记忆路线）")
        return MAINMENU_TEMPLATE.format(route=story_route())
    if mode == "choices":
        calls = scan_calls(DLG_CALL)
        pages = "".join(CHOICES_PAGE.format(tag=t, args=a, bg=CHOICE_BG)
                        for t, a in calls)
        print(f"[testboot] 串起 {len(calls)} 组选择肢按钮")
        return CHOICES_TEMPLATE.format(pages=pages, n=len(calls))
    if mode == "map":
        calls = scan_calls(MAP_CALL)
        pages = "".join(MAP_PAGE.format(tag=t, args=a) for t, a in calls)
        print(f"[testboot] 串起 {len(calls)} 处探索地图")
        return MAP_TEMPLATE.format(pages=pages, n=len(calls))
    if mode == "cutin":
        cuts = scan_cutins()

        def _bg_args(bg):
            if not bg:
                return '""'
            kind, nm = bg
            # ⚠ 一律走 event 层：实测 layerLoad(layerName.bg1, 路径) **不显示**
            # （bg1 在引擎里是 layerCopy 的目标层，不吃直接的文件加载），
            # 两个探针里凡走 bg1 的底都渲成黑屏。
            return f'cGetFileName("{kind}", "{nm}")'

        pages = "".join(
            CUTIN_PAGE.format(name=n, x=x, y=y, r=r, hold=hold, ev=_bg_args(bg))
            for n, x, y, r, bg in cuts)
        n_cg = sum(1 for c in cuts if c[4])
        print(f"[testboot] 扫到 {len(cuts)} 张章节 cutin（{n_cg} 张叠在 CG 上，"
              f"{len(cuts) - n_cg} 张在黑底上）")
        return CUTIN_TEMPLATE.format(pages=pages)
    if mode == "card":
        if not card:
            sys.exit("card 模式需要 card 参数（CLI: --card N）")
        return CARD_TEMPLATE.format(card=card, scene=card_scene(card))
    if mode == "ruby":
        pages = []
        for i, (label, ruby) in enumerate(RUBY_VARIANTS):
            # 底字前不加任何前缀，保证每页底字起点一致（可跨页比较注音偏移）
            pages.append(f'    msg({9100 + i}, "<记忆,{ruby}>")')
        return RUBY_TEMPLATE.format(pages="\n".join(pages))
    if mode == "font":
        pages = []
        for i, (label, text) in enumerate(FONT_PAGES):
            esc = text.replace("\\", "\\\\").replace('"', '\\"')
            pages.append(f'    msg({9000 + i}, "[{label}] {esc}")')
        return FONT_TEMPLATE.format(pages="\n".join(pages), hold=hold)
    if mode == "scene":
        return SCENE_TEMPLATE.format(scene=scene, script=scene_to_script(scene),
                                     hold=-1 if no_cards else 1)
    sys.exit(f"未知模式 {mode!r}（可选 {', '.join(_MODES)}）")


def generate(mode: str, out_dir: Path, **opts) -> dict:
    """产测试层：scripts/snr_test.lua + 需要时的参数化叠加层。

    产物落 out_dir（CLI 缺省 build/test/generated/），由 build_disc 在静态 test 层
    之后按文件名序施加。返回 {"scripts": [...], "overlays": [...], "warnings": [...]}
    ——前两者是相对 out_dir 的路径；warnings 是已知会让产物在测试盘上表现异常的
    告警（目前只有 card 模式的多步骤大谜题一种来源），缺省空列表，供调用方（测试、
    build_disc）核对产出、也让未来的调用方能以结构化方式感知"这份产物是打了折扣
    的"，不必解析 print() 或截获 stdout。

    ⚠ 契约：每次调用都会先清空 out_dir 下**本工具拥有**的两个子目录
    （scripts/、overlays/——不碰 out_dir 里其他内容）再写入，因此调用后这两个
    子目录的磁盘实况与返回值严格一致，不会有上一轮遗留的文件。这不是可有可无的
    整洁：旧架构靠 emitted.json 记账 + 按名逐个还原做到这一点，2026-09-01 就因为
    某个模式没被账本记全、没被还原到，把 mainmenu 模式误跑成了上一轮遗留的 cutin
    探针。新架构没有账本，改用更简单也更彻底的"每次整个子目录重来"。

    ⚠ 守卫：`out_dir` 必须在仓库的 `build/` 之下，否则拒绝——判归属只看目录名
    （`scripts`/`overlays`）不看路径来源，而 `layers/scripts/`、`layers/overlays/`
    与本工具产物目录同构同名，装着手写、入库的层文件（`snr_finale.lua` 等）。
    调用方一旦传错 out_dir（比如手滑传成 `layers/` 而非 `build/test/generated/`），
    上面那条"先清空再写"的契约会当场把它们静默删掉。2026-09-02 review 指出
    "今日无调用方会踩，但 Task 8 正是要接第一个真实调用方"——这里就是那道闸。
    """
    out_dir = Path(out_dir).resolve()
    build_root = (REPO / "build").resolve()
    if not out_dir.is_relative_to(build_root):
        sys.exit(f"generate() 的 out_dir 必须在 {build_root} 之下，收到 {out_dir}——"
                 f"本函数会清空 out_dir/scripts 与 out_dir/overlays，传错目录可能"
                 f"静默删掉 layers/scripts、layers/overlays 里手写入库的层文件")

    # 先做完全部会 sys.exit 的校验与计算，一个字节都不碰磁盘；确认没有校验失败后
    # 才在下面一次性清空+写入——不让"清空了一半、写到一半就失败"的中间态出现。
    src = _render_mode(mode, **opts)          # 未知 mode / 缺 card 在这里已 sys.exit
    result = {"scripts": ["scripts/snr_test.lua"], "overlays": [], "warnings": []}
    overlay_text = None

    if mode == "card":
        card = opts["card"]                  # _render_mode 已确认非空，这里必然存在
        answer = card_answer(card)
        count = _count_select_calls(card)
        if not count:
            sys.exit(f"snr_crd_{card} 里找不到 {SELECT_CALL}，无法短路递卡")
        # ⚠ 已知限制（非本次生成器化引入，重构前的工具就是这个行为）：多步骤大
        # 谜题（crd_103『選択：ノート』、crd_104『True Color』等 23 张）每处
        # oCard.selectCardObj() 要交不同的卡，但下面只产一条 op、一个 with——
        # 全部 count 处会被统一换成同一张卡，第一步之外的每个 while 循环永远等
        # 不到匹配，测试盘会卡死而不是报错。按 dag.json 的答案去重集合探测这种
        # 情况并提醒，但不拦——`--mode card --card 103` 仍是这个工具的验收样例
        # （tests/test_testboot.py），拦下会连累它一起炸。真正的修法要按调用点
        # 顺序拆成多条 occurrence= 专属 op，dag.json 目前不含调用点顺序，留作
        # 后续任务。
        n_answers = len(_dag_answers(card))
        multi_step = count > 1 and n_answers > 1
        warn = ""
        if multi_step:
            msg = (f"crd_{card} 是多步骤谜题：{count} 处递卡对应 {n_answers} 个"
                  f"不同答案 {_dag_answers(card)}，短路只填得了第一步的 {answer}，"
                  f"之后每一步都会卡死。QA 请手动过牌，不要用这份 overlay。")
            result["warnings"].append(msg)
            warn = f"\n⚠ {msg}"
            print(f"[testboot] ⚠ {msg}")
        overlay_text = f'''target  = "snr_crd_{card}.lua"
profile = "test"
why     = """递卡短路：卡片谜题要玩家从持有卡里挑出正确卡才推进剧情，QA 时不想
翻页找答案。把 `{SELECT_CALL}` 换成 data/dag.json 记录的正确答案卡 {answer}——
那份答案是 build_dag 从同一个调用的比较对象里抽出来的，与脚本自身同源。
count 数的是**译文注入后**的源（见 _injected_source 的 docstring），不是
lua_scripts/ 的日文原文：叠加层在译文注入之后施加，这份源才是构建时真正要
过 find_all() 校验的那份。仅测试盘用。{warn}
"""

[[ops]]
op    = "replace"
count = {count}
find  = "{SELECT_CALL}"
with  = "{answer}"
'''

    # 校验全过，从这里开始才真正碰磁盘：先清空本工具拥有的两个子目录，
    # 再一次性写完本次产物——磁盘从此刻起只经过"旧的没了、新的写齐"这一次跳变，
    # 不会停在两者之间。
    shutil.rmtree(out_dir / "scripts", ignore_errors=True)
    shutil.rmtree(out_dir / "overlays", ignore_errors=True)
    (out_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (out_dir / "scripts" / "snr_test.lua").write_text(src, encoding="utf-8")
    if overlay_text is not None:
        (out_dir / "overlays").mkdir(parents=True, exist_ok=True)
        (out_dir / "overlays" / "card-short-circuit.toml").write_text(
            overlay_text, encoding="utf-8")
        result["overlays"].append("overlays/card-short-circuit.toml")
        print(f"[testboot] 递卡短路 {count} 处 → 答案卡 {answer}"
              f"，场景 {card_scene(card) or '(未知)'}")

    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="font", choices=_MODES)
    ap.add_argument("--card", type=int, help="card 模式的卡号（答案自 data/dag.json 取）")
    ap.add_argument("--scene", default="s1s_20", help="scene 模式的目标场景 ID")
    ap.add_argument("--no-cards", action="store_true", help="scene 模式不预置全卡")
    ap.add_argument("--hold", type=int, default=180, help="font/cutin 模式每页停留帧数")
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="层文件输出目录")
    args = ap.parse_args()

    result = generate(args.mode, args.out, scene=args.scene, card=args.card,
                      hold=args.hold, no_cards=args.no_cards)
    print(f"[testboot] 模式 {args.mode} -> {args.out}")
    for rel in result["scripts"] + result["overlays"]:
        print(f"[testboot]   {rel}")


if __name__ == "__main__":
    main()
