"""tools/zh_wrap.py — 共用中文折行模块（词边界感知 + 禁则 + 全局最优 DP）。

覆盖用户实测点出的坏例（卡56「回荡在走廊的声音」被贪心断成「…的声」/
「音」——词从中间拆开，末行还留孤字）与四条变异目标（词边界惩罚被去掉、
孤字重罚被去掉、禁则退化、超 max_lines 静默截断）——每条都要求：真实存在
一个输入，正确实现给出好结果，而"被阉割"的实现会给出可观测的坏结果。
"""
from tools.zh_wrap import (
    ELLIPSIS,
    KINSOKU_RELAX_PENALTY,
    LINE_END_FORBIDDEN,
    LINE_START_FORBIDDEN,
    ORPHAN_LINE_PENALTY,
    WORD_BREAK_PENALTY,
    _ascii_digit_hard_positions,
    _jieba_word_internal_positions,
    wrap,
)


# ---------------------------------------------------------------------------
# 1. 用户实测坏例：卡56「回荡在走廊的声音」
# ---------------------------------------------------------------------------

def test_card56_example_keeps_word_together_and_avoids_orphan():
    """这是本模块存在的直接原因：贪心算法把"声音"这个词从中间拆开
    （"…的声"/"音"），末行还留了个孤字。新算法必须把"声音"整个放到同一
    行——不是恰好撞对，是词边界感知的直接结果。"""
    text = "回荡在走廊的声音"
    lines, info = wrap(text, max_width=24, max_lines=2)
    assert "".join(lines) == text  # 没丢字
    assert not info["truncated"]
    assert info["word_breaks"] == []  # 没有断在任何词内部
    assert info["orphan_lines"] == []  # 没有孤字行
    # "声音"必须完整落在同一行
    assert any("声音" in line for line in lines)


def test_card56_example_with_real_pixel_measurer():
    """同一个坏例，但用 bake_plot 实际使用的像素字体 measurer（而不是默认
    的字符宽度 measurer）——证明修复对真实渲染路径同样成立，不是显示宽度
    这个简化模型的巧合。"""
    from PIL import Image, ImageDraw, ImageFont
    import tools.bake_plot as bp

    font = ImageFont.truetype(bp.FONT_PATH, bp.FONT_SIZE)
    probe = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(probe)
    measurer = lambda s: d.textlength(s, font=font)

    lines, truncated = bp.wrap_title("回荡在走廊的声音", font)
    assert not truncated
    assert any("声音" in line for line in lines)
    assert all(len(line) != 1 for line in lines)


# ---------------------------------------------------------------------------
# 2. 变异目标 1：词边界惩罚被去掉 -> 必须真红
# ---------------------------------------------------------------------------

def test_mutation_word_break_penalty_removed_is_detected(monkeypatch):
    """如果 WORD_BREAK_PENALTY 被削成 0（『词边界感知』名存实亡），DP 会
    在宽度允许时随手切开"声音"这样的词——max_width=15 时"选择：声音的主
    人"（总宽16，8字）最均衡的断点恰好落在"声"/"音"之间（8/8），没有词
    边界惩罚时 DP 会选它；有惩罚时 DP 必须绕开，改选"选择："/"声音的主
    人"（6/10，比切开词的方案更"不均衡"但没有词内断点）。直接对模块常量
    打补丁（真实的"惩罚被削弱"变异，不是手工模拟的旁路逻辑），证明阉割版
    确实会切开"声音"——证明这条测试真的有牙。"""
    import tools.zh_wrap as zw
    text = "选择：声音的主人"
    lines, info = zw.wrap(text, max_width=15, max_lines=2)
    assert info["word_breaks"] == []
    assert any("声音" in line for line in lines)

    monkeypatch.setattr(zw, "WORD_BREAK_PENALTY", 0)
    degraded_lines, _ = zw.wrap(text, max_width=15, max_lines=2)
    assert not any("声音" in line for line in degraded_lines), (
        "退化版（WORD_BREAK_PENALTY=0）预期会切开'声音'——如果它也没切开，"
        "说明这个测试样本选得不够刁钻，测不出惩罚被移除的差异")


# ---------------------------------------------------------------------------
# 3. 变异目标 2：孤字重罚被去掉 -> 必须真红
# ---------------------------------------------------------------------------

def test_mutation_orphan_penalty_removed_is_detected(monkeypatch):
    """孤字重罚一旦被削为0，DP 可能选出一个只留1个字的行（不限于末行——见
    下面这个真实语料例子：孤字出现在首行）。取自 skeleton/cards.zh.yaml
    正文的真实短句"在图书室读"，max_width=8 时 jieba 把"图书室"识别成一个
    词，唯二不切开这个词的断点（"在"|"图书室读" 和 "在图书室"|"读"）双双
    是孤字方案；唯一的非孤字方案"在图"|"书室读"要切开"图书室"（付
    WORD_BREAK_PENALTY）。这正好实测验证了模块 docstring 里"孤字必须比词
    内断点重罚"这条优先级（test_penalty_weight_ordering_matches_
    documented_priority 钉死了 ORPHAN_LINE_PENALTY > WORD_BREAK_PENALTY）：
    正常权重下 DP 宁可切开一个词也要避开孤字；ORPHAN_LINE_PENALTY 被削为0
    后，两个孤字方案（各自只在宽度不均衡上略输于切词方案）反而变得更
    便宜，DP 会改选孤字。"""
    import tools.zh_wrap as zw
    text = "在图书室读"
    lines, info = zw.wrap(text, max_width=8, max_lines=2)
    assert info["orphan_lines"] == [], f"lines={lines}"
    assert lines == ["在图", "书室读"]
    assert info["word_breaks"] == [(0, 2)]  # 宁可切词也不留孤字

    monkeypatch.setattr(zw, "ORPHAN_LINE_PENALTY", 0)
    degraded_lines, degraded_info = zw.wrap(text, max_width=8, max_lines=2)
    assert degraded_info["orphan_lines"] != [], (
        "退化版（ORPHAN_LINE_PENALTY=0）预期会选出一个孤字行——如果没有，"
        "说明这个测试样本选得不够刁钻，测不出孤字重罚被移除的差异")
    assert degraded_lines == ["在", "图书室读"]


# ---------------------------------------------------------------------------
# 4. 变异目标 3：禁则退化 -> 必须真红
# ---------------------------------------------------------------------------

def test_kinsoku_forbidden_char_never_starts_a_line():
    """行首不能是收尾类标点——构造一个"最均衡断点"恰好落在标点前的文本，
    确认 DP 会绕开它。"""
    text = "已经很晚了，快回家吧"  # 在"，"前后断都接近均衡
    lines, info = wrap(text, max_width=19, max_lines=2)
    for line in lines[1:]:
        assert line[0] not in LINE_START_FORBIDDEN, f"line {line!r} starts with forbidden punct"
    assert not info["kinsoku_relaxed"]


def test_kinsoku_forbidden_char_never_ends_a_line():
    """行尾不能是起始类标点。"""
    text = "他说「你先走」我随后就到"
    lines, info = wrap(text, max_width=20, max_lines=2)
    for line in lines[:-1]:
        assert line[-1] not in LINE_END_FORBIDDEN, f"line {line!r} ends with forbidden punct"


def test_mutation_kinsoku_degraded_is_detected(monkeypatch):
    """如果禁则被降级成"不检查"（_kinsoku_block 恒返回 False），DP 会在
    标点前后选一个更均衡但违规的断点——"已经很晚了，快回家吧"（10字，总宽
    20）在 max_width=19 时最均衡的断点恰好是正中间（第5字后，10/10），而
    那正好是"，"前——违反"行首不能是收尾类标点"。直接对 _kinsoku_block 打
    补丁（真实的"禁则检查被拿掉"变异），证明退化版确实会选中这个违规断
    点——证明这条测试有牙。"""
    import tools.zh_wrap as zw
    text = "已经很晚了，快回家吧"
    lines, _ = zw.wrap(text, max_width=19, max_lines=2)
    assert not any(ln and ln[0] in LINE_START_FORBIDDEN for ln in lines[1:])

    monkeypatch.setattr(zw, "_kinsoku_block", lambda text, j: False)
    degraded_lines, _ = zw.wrap(text, max_width=19, max_lines=2)
    violations = [ln for ln in degraded_lines[1:] if ln and ln[0] in LINE_START_FORBIDDEN]
    assert violations, ("退化版（禁则检查被拿掉）预期产生至少一个违规断点"
                         "——如果没有，说明样本选得不够刁钻")


# ---------------------------------------------------------------------------
# 5. 变异目标 4：超 max_lines 静默截断 -> 必须真红
# ---------------------------------------------------------------------------

def test_overflow_is_reported_not_silently_truncated():
    long_text = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"
    lines, info = wrap(long_text, max_width=24, max_lines=2)
    assert info["truncated"] is True
    assert info["dropped"] != ""
    assert lines[-1].endswith(ELLIPSIS)
    # 丢弃的原文 + 保留的原文（去掉省略号）拼起来必须等于原文的某个后缀
    # 切片关系：不能丢完全不相关的内容。
    kept = "".join(lines).replace(ELLIPSIS, "")
    assert (kept + info["dropped"]) == long_text or long_text.startswith(kept)


def test_mutation_silent_truncation_is_detected(monkeypatch):
    """如果 wrap() 被改成"排不下就默默截断、不报 truncated"（比如
    _greedy_truncate 的调用方忘了把它返回的 truncated 接进 info），这条
    测试必须真红：直接把 _greedy_truncate 打补丁成"确实丢字，但谎报
    truncated=False"，证明"调用方必须依赖 info['truncated']，不能自己拿
    ELLIPSIS 存在与否去猜"这件事是真的有必要——阉割版制造出了一个
    "看起来没截断、实际丢了17个字"的输出。"""
    import tools.zh_wrap as zw
    long_text = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"
    lines, info = zw.wrap(long_text, max_width=24, max_lines=2)
    assert info["truncated"] is True
    assert info["dropped"] != ""
    assert lines[-1].endswith(ELLIPSIS)

    real_greedy_truncate = zw._greedy_truncate

    def lying_greedy_truncate(*args, **kwargs):
        lines_, truncated_, dropped_ = real_greedy_truncate(*args, **kwargs)
        return lines_, False, ""  # 谎报"没有截断"，但 lines_ 依旧是截断过的

    monkeypatch.setattr(zw, "_greedy_truncate", lying_greedy_truncate)
    degraded_lines, degraded_info = zw.wrap(long_text, max_width=24, max_lines=2)
    assert degraded_info["truncated"] is False  # 阉割版谎报"没截断"
    # 但内容确实丢了：拼接结果不等于原文，且没有省略号可以事后补救发现。
    assert "".join(degraded_lines) != long_text
    total_kept_chars = sum(len(l.replace(ELLIPSIS, "")) for l in degraded_lines)
    assert total_kept_chars < len(long_text), (
        "退化版预期确实丢字——如果没丢，说明样本没有触发截断路径")


def test_max_lines_none_never_truncates():
    """max_lines=None（不限行数）时，退让链的截断步骤永远不会触发——不限
    行数总能排下任意文本。"""
    long_text = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥" * 3
    lines, info = wrap(long_text, max_width=24, max_lines=None)
    assert info["truncated"] is False
    assert "".join(lines) == long_text


# ---------------------------------------------------------------------------
# 6. 基础正确性：宽度感知、ASCII/数字原子性、losslessness
# ---------------------------------------------------------------------------

def test_default_measurer_uses_display_width():
    # "AB" 半角=1+1=2 display width；"你" 全角=2。max_width=2 应该允许两个
    # 半角字母同行，但一个全角字就得单独占一行。
    lines, info = wrap("AB你", max_width=2, max_lines=2)
    assert "".join(lines) == "AB你"
    assert not info["truncated"]


def test_ascii_digit_run_never_split_even_under_pressure():
    text = "サクラ的日记：10月3日"
    lines, info = wrap(text, max_width=24, max_lines=3)
    assert not info["truncated"]
    full = "".join(lines)
    assert "10" in full
    assert any("10" in line for line in lines)


def test_ascii_digit_hard_positions_boundary_convention():
    """位置约定回归钉子：'10' 在 pos=7 起长度2，内部唯一合法断点是 j=8
    （切在'1'和'0'之间），不是 j=7。这条测试直接钉死这个之前踩过的
    off-by-one。"""
    text = "サクラ的日记：10月3日"
    assert text[7] == "1" and text[8] == "0"
    assert _ascii_digit_hard_positions(text) == {8}


def test_kana_run_never_split_even_though_jieba_cannot_see_it():
    """回归钉子：jieba 是中文分词器，对连续假名会退化成逐字符切分（见
    zh-wrap-report.md 的对照实验）——"ユウイチ"被 jieba.cut 拆成4个独立
    单字，词内断点罚分对假名人名完全不起保护作用。这是 zh_wrap 开发过程
    中用真实语料（卡12"选择：ユウイチ的答卷"）发现的真实回归：初版实现
    只保护了 ASCII/数字串，把"ユウイチ"断成"ユウ"/"イチ"。_kana_hard_
    positions 补上了这个硬约束，与 jieba 是否识别无关。"""
    import jieba
    from tools.zh_wrap import _kana_hard_positions

    text = "选择：ユウイチ的答卷"
    # 先钉死"jieba 对假名无感"这件事本身，证明这条防线不是多余的。
    tokens = list(jieba.cut(text, HMM=False))
    assert tokens.count("ユ") == 1 and "ユウイチ" not in tokens, (
        "如果 jieba 某天开始把'ユウイチ'识别成一个词，这个测试的前提假设"
        "就不成立了，需要重新评估 _kana_hard_positions 是否还有必要")

    assert text[3:7] == "ユウイチ"
    assert _kana_hard_positions(text) == {4, 5, 6}

    lines, info = wrap(text, max_width=15, max_lines=2)
    assert any("ユウイチ" in line for line in lines), f"name split across lines: {lines}"


def test_jieba_word_internal_positions_boundary_convention():
    """同上，钉死 jieba 词边界的下标约定：'声音'在 pos=3 起长度2，内部
    唯一合法断点是 j=4。"""
    text = "选择：声音的主人"
    assert text[3] == "声" and text[4] == "音"
    positions = _jieba_word_internal_positions(text)
    assert 4 in positions
    assert 3 not in positions


def test_wrap_never_loses_or_reorders_characters_when_not_truncated():
    """无损性：只要没有截断，拼接结果必须逐字符等于原文（顺序也不能变）。
    这是"折行只改断点、不改内容"的核心保证。"""
    samples = [
        "回荡在走廊的声音", "选择：声音的主人", "サクラ的日记：10月3日",
        "早晨，男学生(ユウイチ)和女学生(アヤノ)并肩走在上学的路上。",
        "他说「你先走」我随后就到。",
    ]
    for text in samples:
        lines, info = wrap(text, max_width=24, max_lines=None)
        assert not info["truncated"]
        assert "".join(lines) == text, f"lost/reordered chars for {text!r}"


def test_empty_text_returns_single_empty_line():
    lines, info = wrap("", max_width=24, max_lines=2)
    assert lines == [""]
    assert info["truncated"] is False


def test_single_char_line_always_allowed_even_if_wider_than_max_width():
    """单字符行永远放行（哪怕比 max_width 还宽）——否则一个字形巨宽的字符
    会让 DP 无解。"""
    lines, info = wrap("字", max_width=1, max_lines=1)
    assert lines == ["字"]
    assert not info["truncated"]


# ---------------------------------------------------------------------------
# 7. 全局最优 vs 贪心：DP 必须找到比贪心更好的解（不是巧合）
# ---------------------------------------------------------------------------

def test_dp_finds_better_partition_than_naive_greedy_fill():
    """贪心"能塞就塞"在卡56坏例上的行为是"回荡在走廊的声"/"音"——用真实
    的贪心重新实现一遍（不依赖 bake_plot 里已经被替换掉的旧算法），确认
    新 DP 结果的总代价确实更低，不是随便换了个断点。用 bake_plot 实际的
    像素字体 measurer（MAX_TEXT_W=76px）复现——这个坏例在字符数意义的
    display_width 下其实一行就装得下（16<=24），只有在真实字体像素宽度
    下（80px>76px）才会被迫换行，这正是当初问题被发现的场景。"""
    from PIL import Image, ImageDraw, ImageFont
    import tools.bake_plot as bp

    font = ImageFont.truetype(bp.FONT_PATH, bp.FONT_SIZE)
    probe = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(probe)
    measurer = lambda s: d.textlength(s, font=font)
    max_width = bp.MAX_TEXT_W

    def naive_greedy(text, max_width, max_lines):
        lines = []
        cur = ""
        i = 0
        while i < len(text) and len(lines) < max_lines - 1:
            trial = cur + text[i]
            if measurer(trial) > max_width and cur:
                lines.append(cur)
                cur = text[i]
            else:
                cur = trial
            i += 1
        lines.append(cur + text[i:])
        return lines

    text = "回荡在走廊的声音"
    greedy_lines = naive_greedy(text, max_width, 2)
    assert greedy_lines == ["回荡在走廊的声", "音"]  # 复现坏例

    dp_lines, info = wrap(text, max_width=max_width, max_lines=2, measurer=measurer)
    assert dp_lines != greedy_lines
    assert len(dp_lines[-1]) > 1  # 至少不再是孤字
    assert any("声音" in line for line in dp_lines)


# ---------------------------------------------------------------------------
# 8. jieba 不可用时优雅退化（仍保留禁则/孤字/均衡，只是没有词边界）
# ---------------------------------------------------------------------------

def test_use_jieba_false_still_respects_kinsoku_and_orphan():
    text = "已经很晚了，快回家吧"
    lines, info = wrap(text, max_width=20, max_lines=2, use_jieba=False)
    assert info["used_jieba"] is False
    for line in lines[1:]:
        assert line[0] not in LINE_START_FORBIDDEN
    assert info["orphan_lines"] == [] or all(len(l) == 1 for l in
                                              [lines[i] for i in info["orphan_lines"]])


def test_penalty_weight_ordering_matches_documented_priority():
    """惩罚权重的相对大小必须严格保序（禁则退让 > 孤字 > 词内断点）——这是
    模块 docstring 里"退让顺序"的可执行版本，防止未来有人改权重时破坏这个
    优先级却没人注意到。"""
    assert KINSOKU_RELAX_PENALTY > ORPHAN_LINE_PENALTY > WORD_BREAK_PENALTY > 0
