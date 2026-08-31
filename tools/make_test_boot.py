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
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_SRC = REPO / "build" / "testboot"
INJECT = REPO / "build" / "inject" / "script"
LUAC = REPO.parent / "pyluadec-refactor" / "build" / "luac_sz4"

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
    ap.add_argument("--mode", choices=("font", "scene", "ruby"), default="font")
    ap.add_argument("--scene", default="s1s_20", help="scene 模式的目标场景 ID")
    ap.add_argument("--no-cards", action="store_true", help="scene 模式不预置全卡")
    ap.add_argument("--hold", type=int, default=180, help="font 模式每页停留帧数")
    ap.add_argument("--no-fast-boot", action="store_true",
                    help="保留 IPL 开场演出（默认剥掉，省约 28 秒/轮）")
    args = ap.parse_args()

    if args.mode == "ruby":
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

    emit("snr_mainmenu.lua", src)

    if not args.no_fast_boot:
        common = REPO / "build" / "inject_src" / "snr_common.lua"
        if not common.exists():
            sys.exit(f"缺 {common}（先跑 tools/inject_lua.py）")
        text, ok = strip_ipl(common.read_text(encoding="utf-8"))
        if not ok:
            sys.exit("未能定位 IPL 开场块——snr_common 结构变了，检查 IPL_BLOCK_* 锚点")
        emit("snr_common.lua", text)
        print("[testboot] 已剥离 IPL 开场（约省 28 秒/轮）")

    print(f"[testboot] 模式 {args.mode}"
          + (f" scene={args.scene}" if args.mode == "scene" else ""))
    print("[testboot] 接着跑: uv run python tools/build_disc.py --stage stage,pack,disc")


if __name__ == "__main__":
    main()
