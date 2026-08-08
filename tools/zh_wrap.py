"""tools/zh_wrap.py — 共用中文（含日文/ASCII混排）折行模块。

供烤字链路（当前 tools/bake_plot.py，未来 card/ 烤字）共用。取代此前
bake_plot.wrap_title 的纯贪心逐行填满算法——贪心的问题是它只顾"这一行还
塞不塞得下下一个字"，不管断点是否落在一个词的中间：用户实测点出的坏例是
卡56「回荡在走廊的声音」贪心断成「…的声」/「音」，把"声音"这个词从中间
拆开，还在末行留了个孤字。

## 设计

1. **宽度用显示宽度**，不是字符数——半角/全角分开算（复用
   tools/pipelib.display_width：全角/宽/中性算 2，半角算 1）。渲染场景可传
   入基于字体的 measurer（bake_plot.py 现在就是这么接的），measurer(s) 需
   返回字符串 s 的像素宽度。
2. **不贪心，用惩罚函数 + 全局最优（DP）**：候选断点是"两个相邻字符之间的
   位置"，对每一种合法的断点组合算总代价，取代价最小者——而不是贪心地
   "能塞就塞、塞不下才换行"。
3. **词边界**：可选接入 jieba 分词，把"断在一个词内部"标记为重罚（不是
   硬禁——见下方"为什么词内断点不是硬禁"）。ASCII/数字连续串（如
   "10月3日"里的"10"）始终硬禁内部断开，这是迁移自 bake_plot 原
   `_tokenize` 的既有保证，不因引入 jieba 而改变。**假名（平/片假名）
   连续串同样硬禁内部断开**——这不是迁移自旧行为（旧 `_tokenize` 对假名
   没有任何保护），是本模块开发过程中用真实语料（"ユウイチ"被 jieba 拆成
   4 个独立单字）发现的新增必要项，见 `_KANA_RE` 定义处的完整说明。
4. **禁则（既有行为，不得退化）**：行首不能是收尾类标点、行尾不能是起始类
   标点——这两条是硬约束，非法断点直接从候选集里剔除，不参与"代价比较"
   （不是"罚很多分"，是根本不出现在候选里）。
5. **孤字重罚**：任意一行只剩 1 个字符（不只是末行——贪心通常在末行留孤
   字，但没道理只防末行，非末行同样难看）都重罚。
6. **行长不均衡**：TeX 式，每行"未填满量"（max_width - 该行实际宽度）的
   平方和。这一项顺带把"用比必要更多的行数"变得不划算（把同样内容摊到更
   多行，平方和只会更大），所以 DP 自然会挑最少可行行数，不需要另设"行数
   惩罚"项。

## 为什么词内断点是"重罚"而不是"硬禁"

真正的硬禁只有两类：ASCII/数字串内部（迁移自既有 `_tokenize` 行为，全库
测试钉死过"10"不能被拆成"1"/"0"）、禁则标点。中文分词词边界如果也做成硬
禁，会有两个问题：① jieba 分词本身有歧义/噪音，把它的输出当"绝对不可违反
的物理约束"太武断；② 理论上可能出现"任何词边界断点都放不下 max_lines"的
文本，硬禁会导致无解。做成重罚（WORD_BREAK_PENALTY）就能保证 DP 总有解：
词边界优先遵守，但排不下的时候允许退让，而且退让与否是可观测的（见
info["word_breaks"]），不是"越权硬闯"。

## 禁则排不下时的退让链（绝不静默）

放不下 max_lines 时不允许静默截断。退让顺序：
  1. 正常 DP（禁则硬约束 + 词内断点重罚）。
  2. 若无解：禁则从"硬剔除候选"降级为"重罚候选"（KINSOKU_RELAX_PENALTY），
     重跑 DP。这一步永远绝不放松 ASCII/数字串硬禁。若这步救回了解，
     info["kinsoku_relaxed"]=True——调用方必须能看到这个退让发生过。
  3. 仍无解（文本本身在 max_lines*max_width 的画布里根本装不下，退让禁则
     也没用）：退回旧式"贪心填满前 max_lines-1 行、末行截断加省略号"，
     info["truncated"]=True，info["dropped"] 是被丢弃的原文子串。这一步
     绝不允许发生却不报——所有调用方都必须检查 info["truncated"]。
"""
import re

from tools.pipelib import display_width

try:
    import jieba as _jieba
    _HAS_JIEBA = True
except ImportError:  # pragma: no cover - jieba 是本模块声明的依赖，正常环境总在
    _jieba = None
    _HAS_JIEBA = False

ELLIPSIS = "…"

# 行首禁止出现的收尾/闭合类标点；行尾禁止出现的起始/开放类标点。
# 沿用 bake_plot 既有折行对这批标点的规避模式（见模块 docstring 与
# skeleton/cards.zh.yaml 现有折行的实测规避例：卡2"景"字不上第2行是因为
# 会让第2行以"，"开头）。
LINE_START_FORBIDDEN = set("。，、；：！？」』）】〉》…—·")
LINE_END_FORBIDDEN = set("「『（【〈《")

_ASCII_DIGIT_RE = re.compile(r"[A-Za-z0-9]+")

# 平假名/片假名（含长音符ー、片假名中点・、片假名语音扩展）连续串——本库
# 大量嵌入未翻译的日文人名/专名（ユウイチ、アヤノ、サクラ、ユカリ……见
# CLAUDE.md「片假名角色名 vs 汉字角色名两套写法」），这些名字必须整体保留
# 不可拆行。实测发现：jieba 是中文分词器，对连续假名会退化成逐字符 1-token
# 切分（见 zh-wrap-report.md「jieba 对照实验」一节），完全不提供任何词边界
# 保护——"ユウイチ"会被当成 4 个独立单字，词内断点罚分对它形同虚设。所以
# 假名连续串单独按 ASCII/数字串的同等力度处理：硬禁（不是重罚）内部断开，
# 不依赖 jieba 能否识别。
_KANA_RE = re.compile(r"[぀-ヿㇰ-ㇿ]+")

# ---------------------------------------------------------------------------
# 惩罚权重。全部是"元素级"整数代价，彼此的相对大小决定优先级，取值依据见
# 各常量注释与 .superpowers/sdd/2026-08-07-p4-polish-pass/zh-wrap-report.md。
# ---------------------------------------------------------------------------
WORD_BREAK_PENALTY = 5_000
# 依据：单行 26px(display_width≈24 时 TeX 欠满平方项)的理论最大值约为
# 24^2=576（一整行全空）；真实候选之间的欠满平方差通常在两位数到中间几
# 百的量级。5000 保证"哪怕牺牲掉全场最均衡的排布"也换不回一次词内断点，
# 但仍是有限数——DP 在真无处可退（见退让链步骤2/3）时还能选它，不会因为
# "硬禁"式的无穷大代价而导致无解。

ORPHAN_LINE_PENALTY = 20_000
# 依据：必须比 WORD_BREAK_PENALTY 更重——用户点名的坏例"声音"被拆成
# "…的声"/"音"同时触发了「词内断点」与「孤字」两个问题；如果孤字罚分比
# 词内断点还轻，DP 可能为了避免一次词内断点而制造一个孤字，本末倒置。

KINSOKU_RELAX_PENALTY = 1_000_000
# 依据：比前两项高两个数量级——这是退让链第2步专用的"万不得已"代价，
# 目的是让 DP 在别无选择时才会碰它，且一旦被使用必须在 info 里显式报出
# （见 wrap() 的 kinsoku_relaxed 字段），不是常规可选项。


def _default_measurer(s):
    return display_width(s)


def _ascii_digit_hard_positions(text):
    """返回 set：ASCII/数字连续串内部的断点位置——用与 `_kinsoku_block`/DP
    一致的边界下标约定（位置 j 表示 text[:j] 是这一行、text[j:] 是下一
    行，1<=j<=len(text)-1）。一个从 pos 起长度 L 的连续串，其内部合法边界
    是 {pos+1, ..., pos+L-1}（L-1 个）——注意不是 {pos, ..., pos+L-2}：
    L=2 的串（如"10"）只有一个内部边界 pos+1（切在"1"和"0"之间），不是
    pos（切在"10"前一个字符和"1"之间，那根本不在串内部）。这些位置永远不
    允许断行——既有行为的硬约束，不因引入 jieba 或任何其它改动而放松（见
    模块 docstring）。"""
    hard = set()
    for m in _ASCII_DIGIT_RE.finditer(text):
        for j in range(m.start() + 1, m.end()):
            hard.add(j)
    return hard


def _kana_hard_positions(text):
    """返回 set：假名（平/片假名）连续串内部的断点位置，边界下标约定同
    `_ascii_digit_hard_positions`。硬禁而非重罚——见 _KANA_RE 定义处的
    docstring：jieba 对连续假名退化成逐字切分，词内断点罚分对假名人名
    （ユウイチ/アヤノ/サクラ……）不起任何保护作用，必须单独硬保护。"""
    hard = set()
    for m in _KANA_RE.finditer(text):
        for j in range(m.start() + 1, m.end()):
            hard.add(j)
    return hard


def _jieba_word_internal_positions(text):
    """返回 set：jieba 分词结果中，"词内部"（非词边界）的断点位置，同样用
    _ascii_digit_hard_positions 文档所述的边界下标约定（j，非字符下标 i）。
    用 HMM=False（关闭隐马尔可夫新词发现）——卡名/正文都是短句，HMM 对短
    句误切风险更高且不可复现（依赖内置概率模型版本），关掉换取确定性。"""
    positions = set()
    if not _HAS_JIEBA:
        return positions
    pos = 0
    for tok in _jieba.cut(text, HMM=False):
        L = len(tok)
        for j in range(pos + 1, pos + L):
            positions.add(j)
        pos += L
    return positions


def _kinsoku_block(text, j):
    """位置 j（1<=j<=len(text)-1，行边界：text[:j] 是这一行，text[j:] 是
    下一行）是否违反禁则。"""
    return text[j] in LINE_START_FORBIDDEN or text[j - 1] in LINE_END_FORBIDDEN


def _compute_widths(text, measurer):
    n = len(text)
    w = [[0] * (n + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        for j in range(i + 1, n + 1):
            w[i][j] = measurer(text[i:j])
    return w


def _run_dp(text, widths, max_width, l_lo, l_hi, hard_positions,
            kinsoku_positions, word_penalty_positions):
    """核心 DP。hard_positions/kinsoku_positions 中的位置永远不能作为行
    边界（j in [1, n-1]）；word_penalty_positions 中的位置可以作为行边界，
    但要付 WORD_BREAK_PENALTY。

    返回 (best_lines, best_info_partial) 或 (None, None)（l_lo..l_hi 范围
    内无可行解）。"""
    n = len(text)
    INF = float("inf")
    # dp[l][j] = (cost, prev_i)
    dp = [[(INF, -1)] * (n + 1) for _ in range(l_hi + 1)]
    dp[0][0] = (0.0, -1)
    for l in range(1, l_hi + 1):
        for j in range(1, n + 1):
            if j < n and (j in hard_positions or j in kinsoku_positions):
                continue  # 这个位置根本不能是行边界
            best_cost, best_i = INF, -1
            for i in range(0, j):
                prev_cost, _ = dp[l - 1][i]
                if prev_cost == INF:
                    continue
                seg_len = j - i
                w = widths[i][j]
                if seg_len > 1 and w > max_width:
                    continue  # 硬性宽度约束（单字符行永远放行，见模块 docstring）
                penalty = (max_width - w) ** 2 if w <= max_width else 0.0
                if seg_len == 1:
                    penalty += ORPHAN_LINE_PENALTY
                if j < n and j in word_penalty_positions:
                    penalty += WORD_BREAK_PENALTY
                cost = prev_cost + penalty
                if cost < best_cost:
                    best_cost, best_i = cost, i
            dp[l][j] = (best_cost, best_i)

    best_l, best_cost = None, INF
    for l in range(max(l_lo, 1), l_hi + 1):
        cost, _ = dp[l][n]
        if cost < best_cost:
            best_cost, best_l = cost, l
    if best_l is None:
        return None, None

    # 回溯
    cuts = []
    j, l = n, best_l
    while l > 0:
        _, i = dp[l][j]
        cuts.append((i, j))
        j, l = i, l - 1
    cuts.reverse()
    lines = [text[i:j] for i, j in cuts]
    return lines, {"cost": best_cost, "cuts": cuts}


def _greedy_truncate(text, widths, max_width, max_lines, measurer):
    """退让链最后一步：旧式贪心填满 + 末行截断加省略号。前 max_lines-1 行
    正常贪心填满（不考虑词边界/孤字，只保证不超宽度），末行吸收剩余——吸
    收不下就从尾部裁到能放下 ELLIPSIS 为止。"""
    n = len(text)
    lines = []
    pos = 0
    for _ in range(max_lines - 1):
        if pos >= n:
            lines.append("")
            continue
        end = pos
        for k in range(pos + 1, n + 1):
            if widths[pos][k] <= max_width:
                end = k
            else:
                break
        if end == pos:
            end = pos + 1  # 单字符也超宽，仍必须前进，避免死循环
        lines.append(text[pos:end])
        pos = end

    remaining = text[pos:]
    last = ""
    k = 0
    for k in range(len(remaining)):
        trial = last + remaining[k]
        if measurer(trial) > max_width and last:
            break
        last = trial
    else:
        k = len(remaining)
    truncated = False
    dropped = ""
    if k < len(remaining):
        truncated = True
        dropped = remaining[k:]
        while last and measurer(last + ELLIPSIS) > max_width:
            dropped = last[-1] + dropped
            last = last[:-1]
        last = (last + ELLIPSIS) if last else ELLIPSIS
    lines.append(last)
    return lines, truncated, dropped


def wrap(text, max_width, max_lines=None, measurer=None, use_jieba=True):
    """把 text 折成若干行，每行 <= max_width（measurer 度量），全局最优
    （惩罚函数 DP，非贪心）。

    text 不应包含换行符——多段落文本（如卡面正文的 \\n\\n 段落分隔）由调
    用方按段落拆开、逐段调用后再用原分隔符拼回，本函数只处理单段连续文本
    （见模块 docstring 与 build/cards_rewrap_report.md 的段落处理说明）。

    Args:
      text: 待折行文本（单段，不含换行符）。
      max_width: 每行宽度上限（measurer 的度量单位）。
      max_lines: 行数上限；None = 不限（退让链的 truncate 步骤在此模式下
        永远不会触发——不限行数就总能排下）。
      measurer: text(str) -> 宽度(number)；默认 tools.pipelib.display_width
        （半角=1，全角=2）。渲染场景传入基于字体的像素度量。
      use_jieba: 是否用 jieba 分词标记词边界；jieba 不可用时自动退化为
        "无分词边界感知"（仍保留禁则与孤字/均衡惩罚），并在 info 里报告。

    Returns:
      (lines, info)。info 至少包含：
        truncated（bool，是否发生了退让链第3步的截断）、
        dropped（截断丢弃的原文子串，未截断为""）、
        kinsoku_relaxed（bool，是否发生了退让链第2步）、
        word_breaks（[(line_idx, 行内偏移)]，实际断在词内部的位置——正常
          情况应为空，非空说明退让链已经动用了 WORD_BREAK_PENALTY）、
        orphan_lines（[line_idx]，只有1个字符的行）、
        lines_used、max_lines、used_jieba、cost。
    """
    if measurer is None:
        measurer = _default_measurer
    if "\n" in text:
        raise ValueError("wrap() 只处理单段连续文本，不接受内嵌换行符——多段"
                          "落文本由调用方按段落拆分后逐段调用（见模块 docstring）")

    n = len(text)
    if n == 0:
        return [""], {
            "truncated": False, "dropped": "", "kinsoku_relaxed": False,
            "word_breaks": [], "orphan_lines": [], "lines_used": 1,
            "max_lines": max_lines, "used_jieba": False, "cost": 0.0,
        }

    widths = _compute_widths(text, measurer)
    hard_positions = _ascii_digit_hard_positions(text) | _kana_hard_positions(text)
    kinsoku_positions = {j for j in range(1, n) if _kinsoku_block(text, j)}
    used_jieba = use_jieba and _HAS_JIEBA
    word_internal_positions = _jieba_word_internal_positions(text) if used_jieba else set()
    word_penalty_positions = word_internal_positions

    total_width = widths[0][n]
    lower_bound = max(1, -(-total_width // max_width)) if max_width > 0 else n
    # 搜索窗口：没道理用比"理论最少行数"多很多的行数（均衡惩罚是凸的，行数
    # 越多总代价只会越高，见模块 docstring 第6条），给 6 行富余应付禁则/词
    # 边界导致的额外换行，同时把 DP 状态数摁在一个跟文本长度无关的小常数
    # 附近。
    l_hi_natural = lower_bound + 6
    if max_lines is None:
        l_lo, l_hi = 1, min(l_hi_natural, n)
    else:
        l_lo, l_hi = 1, min(max_lines, max(l_hi_natural, max_lines))
        l_hi = min(l_hi, n)
    l_hi = max(l_hi, 1)

    lines, meta = _run_dp(text, widths, max_width, l_lo, l_hi,
                           hard_positions, kinsoku_positions,
                           word_penalty_positions)
    kinsoku_relaxed = False
    if lines is None and max_lines is not None:
        # 退让链步骤2：禁则从硬剔除降级为重罚（KINSOKU_RELAX_PENALTY，与
        # WORD_BREAK_PENALTY 独立计价——见 _run_dp_kinsoku_relaxed）。
        # ASCII/数字硬禁（hard_positions）永不放松。
        lines, meta = _run_dp_kinsoku_relaxed(
            text, widths, max_width, max_lines, hard_positions,
            kinsoku_positions, word_penalty_positions)
        if lines is not None:
            kinsoku_relaxed = True

    truncated = False
    dropped = ""
    if lines is None:
        # 退让链步骤3：旧式贪心 + 截断。max_lines 一定不是 None（走到这里
        # 说明连"每个位置都允许断"都排不下，只有行数被限死才会发生）。
        lines, truncated, dropped = _greedy_truncate(
            text, widths, max_width, max_lines, measurer)

    word_breaks = []
    orphan_lines = []
    pos = 0
    for idx, line in enumerate(lines):
        if len(line) == 1:
            orphan_lines.append(idx)
        end = pos + len(line)
        if end < n and end in word_internal_positions:
            word_breaks.append((idx, end))
        pos = end

    info = {
        "truncated": truncated,
        "dropped": dropped,
        "kinsoku_relaxed": kinsoku_relaxed,
        "word_breaks": word_breaks,
        "orphan_lines": orphan_lines,
        "lines_used": len(lines),
        "max_lines": max_lines,
        "used_jieba": used_jieba,
        "cost": meta["cost"] if meta else None,
    }
    return lines, info


def _run_dp_kinsoku_relaxed(text, widths, max_width, max_lines,
                             hard_positions, kinsoku_positions,
                             word_penalty_positions):
    """退让链步骤2的精确版 DP：禁则位置allowed但付 KINSOKU_RELAX_PENALTY，
    词内断点仍付 WORD_BREAK_PENALTY，两者独立计价（不像 wrap() 里第一次
    尝试那样把两者混进同一个 penalty 集合）。"""
    n = len(text)
    INF = float("inf")
    dp = [[(INF, -1)] * (n + 1) for _ in range(max_lines + 1)]
    dp[0][0] = (0.0, -1)
    for l in range(1, max_lines + 1):
        for j in range(1, n + 1):
            if j < n and j in hard_positions:
                continue
            best_cost, best_i = INF, -1
            for i in range(0, j):
                prev_cost, _ = dp[l - 1][i]
                if prev_cost == INF:
                    continue
                seg_len = j - i
                w = widths[i][j]
                if seg_len > 1 and w > max_width:
                    continue
                penalty = (max_width - w) ** 2 if w <= max_width else 0.0
                if seg_len == 1:
                    penalty += ORPHAN_LINE_PENALTY
                if j < n and j in word_penalty_positions:
                    penalty += WORD_BREAK_PENALTY
                if j < n and j in kinsoku_positions:
                    penalty += KINSOKU_RELAX_PENALTY
                cost = prev_cost + penalty
                if cost < best_cost:
                    best_cost, best_i = cost, i
            dp[l][j] = (best_cost, best_i)
    best_l, best_cost = None, INF
    for l in range(1, max_lines + 1):
        cost, _ = dp[l][n]
        if cost < best_cost:
            best_cost, best_l = cost, l
    if best_l is None:
        return None, None
    cuts = []
    j, l = n, best_l
    while l > 0:
        _, i = dp[l][j]
        cuts.append((i, j))
        j, l = i, l - 1
    cuts.reverse()
    lines = [text[i:j] for i, j in cuts]
    return lines, {"cost": best_cost, "cuts": cuts}
