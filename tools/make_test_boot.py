#!/usr/bin/env -S uv run python
"""生成测试引导脚本，替换封包内 script/snr_mainmenu.lua 成员。

原理：`snr_common.main()` 做完全部初始化（双字体 fontLoad、常驻图层、SE、IPL
演出、runAutoLoad）后 `run(script/snr_mainmenu)`。把那个成员换成我们的脚本，
即可在完整初始化的环境里直接跑测试代码——不动 config.bootScript、不动
snr_common，回滚只需重新注入原成员。

两种模式：
  font   字体/ruby 探针：用 fontPrint 逐槽画样本串、用 msg 走正文管线画 ruby，
         每页停一帧等外部截图。回答 CLAUDE.md 悬置的两个问题——ruby 用哪个字体槽、
         该槽有没有带声调的拉丁元音。
  scene  跳场景：预置卡片/进度后直入指定章节场景（O(1) 抵达任意待验场景）。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_SRC = REPO / "build" / "testboot"
INJECT = REPO / "build" / "inject" / "script"
LUAC = REPO.parent / "pyluadec-refactor" / "build" / "luac_sz4"
#: 引导交接语句：snr_common.main() 末尾把控制权交给主菜单的那一行。
BOOT_HANDOFF = 'run(cGetFileName("script", "snr_mainmenu"))'
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

RUBY_TEMPLATE = '''-- 自动生成（tools/make_test_boot.py）：ruby 居中对齐测量（一页一变体）
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

FONT_TEMPLATE = '''-- 自动生成（tools/make_test_boot.py）：字体/ruby 探针
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

CUTIN_TEMPLATE = '''-- 自动生成（tools/make_test_boot.py）：章节首尾 cutin 一次过目
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

MAINMENU_TEMPLATE = '''-- 自动生成（tools/make_test_boot.py）：全解锁真主菜单（人工上手用）
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
    systemSave.storyLineSkip = true
    systemSave.messageReadColor = true
    run(cGetFileName("script", "snr_mainmenu"))
    quit()
end
'''

CHOICES_TEMPLATE = '''-- 自动生成（tools/make_test_boot.py）：全部选择肢按钮串联过目
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

MAP_TEMPLATE = '''-- 自动生成（tools/make_test_boot.py）：探索地图选点界面串联
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

CARD_TEMPLATE = '''-- 自动生成（tools/make_test_boot.py）：直入卡片谜题 crd_{card}
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

SCENE_TEMPLATE = '''-- 自动生成（tools/make_test_boot.py）：跳场景 {scene}
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


# snr_common.main() 的 IPL 开场：4 屏 logo 各 淡入120帧 + keyWait180 + 淡出120帧，
# 合计约 28 秒，每轮测试都要白等。四个图层进块前后都是 alpha 0（5000-5006 行已
# layerAlpha(…,0)），故整块删除不改变末态，只是不播演出。仅测试盘用。
IPL_BLOCK_HEAD = "    layerMoveAlpha(0, 100, 120)\n"
IPL_BLOCK_TAIL = "    layerMoveAlpha(3, 0, 120)\n    wait(120)\n"


def strip_ipl(text: str) -> tuple[str, bool]:
    i = text.find(IPL_BLOCK_HEAD)
    j = text.find(IPL_BLOCK_TAIL)
    if i < 0 or j < 0 or j < i:
        return text, False
    return text[:i] + text[j + len(IPL_BLOCK_TAIL):], True


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


def card_scene(card: int) -> str:
    """卡号 → 它所属的场景 ID（snr_common 的 sceneId2aCard 反查）。"""
    import re as _re
    txt = (REPO / "lua_scripts" / "snr_common.lua").read_text(encoding="utf-8")
    for m in _re.finditer(r'sceneId2aCard\.(\w+) = (\d+)', txt):
        if int(m.group(2)) == card and m.group(1) != "keyword":
            return m.group(1)
    return ""


def short_circuit_card(card: int) -> tuple[str, int]:
    """把卡脚本里的递卡调用换成正确答案，返回 (改后源码, 替换次数)。"""
    src = (REPO / "build" / "inject_src" / f"snr_crd_{card}.lua").read_text(encoding="utf-8")
    return src.replace(SELECT_CALL, str(card_answer(card))), src.count(SELECT_CALL)


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
    chap, mode = scene[:2], scene[2]
    suffix = mode
    if len(scene) > 3 and scene[3] in "abc" and mode == "f":
        suffix = mode + scene[3]
    return f"snr_{chap}_10_{suffix}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="font", choices=(
        "font", "scene", "ruby", "card", "cutin", "mainmenu", "choices", "map"))
    ap.add_argument("--card", type=int, help="card 模式的卡号（答案自 data/dag.json 取）")
    ap.add_argument("--scene", default="s1s_20", help="scene 模式的目标场景 ID")
    ap.add_argument("--no-cards", action="store_true", help="scene 模式不预置全卡")
    ap.add_argument("--hold", type=int, default=180, help="font 模式每页停留帧数")
    ap.add_argument("--no-fast-boot", action="store_true",
                    help="保留 IPL 开场演出（默认剥掉，省约 28 秒/轮）")
    args = ap.parse_args()

    if args.mode == "mainmenu":
        src = MAINMENU_TEMPLATE.format(route=story_route())
        print("[testboot] 全解锁主菜单（195 卡 + startMenuState=2 + 预置记忆路线）")
    elif args.mode == "choices":
        calls = scan_calls(DLG_CALL)
        pages = "".join(CHOICES_PAGE.format(tag=t, args=a, bg=CHOICE_BG)
                        for t, a in calls)
        src = CHOICES_TEMPLATE.format(pages=pages, n=len(calls))
        print(f"[testboot] 串起 {len(calls)} 组选择肢按钮")
    elif args.mode == "map":
        calls = scan_calls(MAP_CALL)
        pages = "".join(MAP_PAGE.format(tag=t, args=a) for t, a in calls)
        src = MAP_TEMPLATE.format(pages=pages, n=len(calls))
        print(f"[testboot] 串起 {len(calls)} 处探索地图")
    elif args.mode == "cutin":
        cuts = scan_cutins()
        def _bg_args(bg):
            if not bg:
                return '""'
            kind, nm = bg
            call = f'cGetFileName("{kind}", "{nm}")'
            # ⚠ 一律走 event 层：实测 layerLoad(layerName.bg1, 路径) **不显示**
            # （bg1 在引擎里是 layerCopy 的目标层，不吃直接的文件加载），
            # 两个探针里凡走 bg1 的底都渲成黑屏。
            return call

        pages = "".join(
            CUTIN_PAGE.format(name=n, x=x, y=y, r=r, hold=args.hold,
                              ev=_bg_args(bg))
            for n, x, y, r, bg in cuts)
        src = CUTIN_TEMPLATE.format(pages=pages)
        n_cg = sum(1 for c in cuts if c[4])
        print(f"[testboot] 扫到 {len(cuts)} 张章节 cutin（{n_cg} 张叠在 CG 上，"
              f"{len(cuts) - n_cg} 张在黑底上）")
    elif args.mode == "card":
        if not args.card:
            sys.exit("--mode card 需要 --card N")
        src = CARD_TEMPLATE.format(card=args.card, scene=card_scene(args.card))
    elif args.mode == "ruby":
        pages = []
        for i, (label, ruby) in enumerate(RUBY_VARIANTS):
            # 底字前不加任何前缀，保证每页底字起点一致（可跨页比较注音偏移）
            pages.append(f'    msg({9100 + i}, "<记忆,{ruby}>")')
        src = RUBY_TEMPLATE.format(pages="\n".join(pages))
    elif args.mode == "font":
        pages = []
        for i, (label, text) in enumerate(FONT_PAGES):
            esc = text.replace("\\", "\\\\").replace('"', '\\"')
            pages.append(f'    msg({9000 + i}, "[{label}] {esc}")')
        src = FONT_TEMPLATE.format(pages="\n".join(pages), hold=args.hold)
    else:
        src = SCENE_TEMPLATE.format(scene=args.scene, script=scene_to_script(args.scene),
                                    hold=-1 if args.no_cards else 1)

    OUT_SRC.mkdir(parents=True, exist_ok=True)
    INJECT.mkdir(parents=True, exist_ok=True)

    def emit(name: str, text: str) -> None:
        lua = OUT_SRC / name
        lua.write_text(text, encoding="utf-8")
        dst = INJECT / name
        proc = subprocess.run([str(LUAC), "-s", "-o", str(dst), str(lua)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            sys.exit(f"luac 失败 {name}: {proc.stderr}")
        print(f"[testboot] {name} -> {dst}")

    # 测试脚本作为**新成员** script/snr_test.lua 注入，并把 snr_common 引导末尾的
    # `run(snr_mainmenu)` 改指它。早先的做法是直接顶替 snr_mainmenu 成员，那样就
    # 没法再跑真菜单了——而主菜单本身正是要测的对象之一。
    emit("snr_test.lua", src)

    if args.mode == "card":
        patched, n = short_circuit_card(args.card)
        if not n:
            sys.exit(f"snr_crd_{args.card} 里找不到 {SELECT_CALL}，无法短路递卡")
        emit(f"snr_crd_{args.card}.lua", patched)
        print(f"[testboot] 递卡短路 {n} 处 → 答案卡 {card_answer(args.card)}"
              f"，场景 {card_scene(args.card) or '(未知)'}")

    # ⚠ 两个分支都必须重写 snr_common：--no-fast-boot 若只是「不写」，上一轮剥过 IPL 的
    # 字节码会留在 build/inject/script 里，开场并不会恢复（2026-08-31 实测踩到）。
    common = REPO / "build" / "inject_src" / "snr_common.lua"
    if not common.exists():
        sys.exit(f"缺 {common}（先跑 tools/inject_lua.py）")
    text = common.read_text(encoding="utf-8")
    if not args.no_fast_boot:
        text, ok = strip_ipl(text)
        if not ok:
            sys.exit("未能定位 IPL 开场块——snr_common 结构变了，检查 IPL_BLOCK_* 锚点")
        print("[testboot] 已剥离 IPL 开场（约省 28 秒/轮）")
    else:
        print("[testboot] 保留 IPL 开场")
    # 引导末尾改指测试脚本。全文有 8 处 run(snr_mainmenu)，只有 main() 里那一处
    # （最后一处）是引导交接，其余是暂停菜单的返回；只能换那一处，否则从暂停菜单
    # 回主菜单也会掉进测试脚本。
    if text.count(BOOT_HANDOFF) < 1:
        sys.exit("未找到引导交接语句，snr_common 结构变了")
    head, sep, tail = text.rpartition(BOOT_HANDOFF)
    text = head + BOOT_HANDOFF.replace("snr_mainmenu", "snr_test") + tail
    emit("snr_common.lua", text)

    print(f"[testboot] 模式 {args.mode}"
          + (f" scene={args.scene}" if args.mode == "scene" else ""))
    print("[testboot] 接着跑: uv run python tools/build_disc.py --stage stage,pack,disc")


if __name__ == "__main__":
    main()
