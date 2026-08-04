import json

from tools.check_batch import (
    check, main as check_batch_main, _max_line_width, _strip_ruby,
)
from tools.pipelib import write_jsonl

SRC = [
    {"id": 1, "jp": "【彩野】「うん、<前向性健忘,ぜんこうせいけんぼう>だよ」"},
    {"id": 2, "jp": "○_nそこには≪きみ≫がいた。_r間違いなく。"},
]
OK = [
    {"id": 1, "zh": "【彩野】「嗯，是<前向性健忘,顺行性遗忘>哦」"},
    {"id": 2, "zh": "○_n那里有≪你≫。_r毫无疑问。"},
]

def test_clean_draft_passes():
    r = check(SRC, OK, speakers={"彩野": "彩野"}, glossary={})
    assert r["hard"] == [] and r["warn"] == []

def test_id_set_mismatch_is_hard():
    r = check(SRC, OK[:1], speakers=None, glossary=None)
    assert any(v["rule"] == "R1" for v in r["hard"])

def test_broken_ruby_is_hard():
    bad = [dict(OK[0], zh="【彩野】「嗯，<前向性健忘顺行」"), OK[1]]
    r = check(SRC, bad, speakers=None, glossary=None)
    assert any(v["rule"] == "R2a" for v in r["hard"])

def test_speaker_map_mismatch_is_hard():
    bad = [dict(OK[0], zh="【绫乃】「嗯」<a,b>"), OK[1]]
    r = check(SRC, bad, speakers={"彩野": "彩野"}, glossary=None)
    assert any(v["rule"] == "R2b" for v in r["hard"])

def test_lost_marks_is_hard():
    bad = [OK[0], dict(OK[1], zh="○_n那里有你。_r毫无疑问。")]
    r = check(SRC, bad, speakers=None, glossary=None)
    assert any(v["rule"] == "R2c" for v in r["hard"])

def test_linebreak_diff_and_width_are_warn():
    bad = [OK[0], dict(OK[1], zh="○那里有≪你≫。毫无疑问。" + "长" * 40)]
    r = check(SRC, bad, speakers=None, glossary=None)
    rules = {v["rule"] for v in r["warn"]}
    assert "W1" in rules and "W3" in rules and r["hard"] == []

def test_glossary_miss_is_warn():
    r = check(SRC, OK, speakers=None, glossary={"前向性健忘": "顺行性健忘症"})
    assert any(v["rule"] == "W2" for v in r["warn"])


# ---- P1c 硬化：R2b 结构检查恒执行 + 装饰括号剥离映射 ----
# 缺陷背景：原实现把「结构对齐」放在 `elif`（仅 speakers 为空时可达），而
# speakers.json 恒存在 → 生产中该分支永不执行：原文无【】而译文擅自加说话人
# 完全不拦（全书 7131 行旁白），原文说话人未在表中时译文丢【】也不拦。

NARR_SRC = [{"id": 9, "jp": "遠くから『帰りの歌』が聞こえてきた。"}]


def test_hallucinated_speaker_on_narration_is_hard():
    """原文无【】，译文擅自加说话人前缀 → R2b（speakers 存在时也必须拦）。"""
    bad = [{"id": 9, "zh": "【直哉】「远处传来了『回家的歌谣』」"}]
    r = check(NARR_SRC, bad, speakers={"彩野": "彩野"}, glossary=None)
    assert any(v["rule"] == "R2b" for v in r["hard"])


def test_dropped_speaker_of_unmapped_name_is_hard():
    """原文说话人不在 speakers 表中（如 ＊＊＊），译文丢了【】→ 仍须 R2b。"""
    src = [{"id": 10, "jp": "【＊＊＊】行けよ。直哉。"}]
    bad = [{"id": 10, "zh": "去吧。直哉。"}]
    r = check(src, bad, speakers={"彩野": "彩野"}, glossary=None)
    assert any(v["rule"] == "R2b" for v in r["hard"])


def test_decorated_speaker_maps_through_decoration():
    """【≪ユウイチ≫】：剥掉 ≪≫ 后按表映射，装饰须原样保留 → 合法译文放行。"""
    src = [{"id": 11, "jp": "【≪ユウイチ≫】「俺は、アヤノの事が、好きだ」"}]
    ok = [{"id": 11, "zh": "【≪ユウイチ≫】「我，喜欢アヤノ。」"}]
    r = check(src, ok, speakers={"ユウイチ": "ユウイチ"}, glossary=None)
    assert r["hard"] == []


def test_decorated_speaker_wrong_name_is_hard():
    """装饰内的名字译错 → R2b（此前 ≦…≧ 类说话人 457 行完全不检查）。"""
    src = [{"id": 12, "jp": "【≦教師≧】「おはよう」"}]
    bad = [{"id": 12, "zh": "【≦老师们≧】「早上好」"}]
    r = check(src, bad, speakers={"教師": "教师"}, glossary=None)
    assert any(v["rule"] == "R2b" for v in r["hard"])


def test_decorated_speaker_lost_decoration_is_hard():
    """装饰被吃掉（【≦教師≧】→【教师】）→ R2b。"""
    src = [{"id": 13, "jp": "【≦教師≧】「おはよう」"}]
    bad = [{"id": 13, "zh": "【教师】「早上好」"}]
    r = check(src, bad, speakers={"教師": "教师"}, glossary=None)
    assert any(v["rule"] == "R2b" for v in r["hard"])


# ---- Hotfix D 缺陷 2：main() 的 --lane-dir（车道术语快照，与
# detect_collapse.py 的 --lane-dir 同名同义）----

LANE_SRC = [{"id": 501, "jp": "【彩野】「＠车道试验术语＠だいじょうぶ」"}]
LANE_DRAFT = [{"id": 501, "zh": "【彩野】「没关系」"}]

ROOT_SRC = [{"id": 601, "jp": "コックリさんをやってみよう。"}]
ROOT_DRAFT_MISS = [{"id": 601, "zh": "试试看那个仪式吧。"}]  # 未用仓库根定译「钱仙」


def _write_batch(work_dir, batch, src_rows, draft_rows):
    write_jsonl(work_dir / "ctx" / f"batch_{batch}" / "source.jsonl", src_rows)
    write_jsonl(work_dir / "out" / f"batch_{batch}.draft.jsonl", draft_rows)


def test_lane_dir_glossary_drives_w2(tmp_path, monkeypatch):
    """--lane-dir 指向的目录里有一个仓库根词表压根没有的术语定译：W2 必须按
    车道词表判定（触发），证明真的在读 <lane-dir>/glossary/active.json。"""
    work = tmp_path / "work"
    _write_batch(work, 1, LANE_SRC, LANE_DRAFT)
    monkeypatch.setattr("tools.check_batch.WORK", work)
    lane = tmp_path / "lane"
    (lane / "glossary").mkdir(parents=True)
    (lane / "glossary" / "active.json").write_text(
        json.dumps({"＠车道试验术语＠": "车道定译"}, ensure_ascii=False),
        encoding="utf-8")
    check_batch_main(["--batch", "1", "--lane-dir", str(lane)])
    result = json.loads((work / "out" / "batch_1.check.json").read_text(encoding="utf-8"))
    assert any(v["rule"] == "W2" for v in result["warn"]), result


def test_no_lane_dir_reads_repo_root_glossary(tmp_path, monkeypatch):
    """回归闸：不给 --lane-dir 时行为与改动前逐字一致——仍读仓库根
    glossary/active.json（用仓库根真实词表里确有的「コックリさん→钱仙」条目
    造判别力：草稿没按这个定译，必须触发 W2）。"""
    work = tmp_path / "work"
    _write_batch(work, 1, ROOT_SRC, ROOT_DRAFT_MISS)
    monkeypatch.setattr("tools.check_batch.WORK", work)
    check_batch_main(["--batch", "1"])
    result = json.loads((work / "out" / "batch_1.check.json").read_text(encoding="utf-8"))
    assert any(v["rule"] == "W2" for v in result["warn"]), result


def test_lane_dir_does_not_fall_back_to_repo_root(tmp_path, monkeypatch):
    """给了 --lane-dir 时不应再混用仓库根词表：车道目录没有 glossary/ 时，
    speakers/glossary 都应为 None（读不到就是读不到，不静默退回仓库根）。"""
    work = tmp_path / "work"
    _write_batch(work, 1, ROOT_SRC, ROOT_DRAFT_MISS)
    monkeypatch.setattr("tools.check_batch.WORK", work)
    empty_lane = tmp_path / "empty-lane"
    empty_lane.mkdir()
    check_batch_main(["--batch", "1", "--lane-dir", str(empty_lane)])
    result = json.loads((work / "out" / "batch_1.check.json").read_text(encoding="utf-8"))
    assert not any(v["rule"] == "W2" for v in result["warn"]), result


# ---- Task 8：W4 复现句族内逐字一致（顾问级）----
# 背景：glossary/style.md 把「复现句族内逐字一致」明写为不放宽的边界，却是该
# 文件里唯一一条没有机器兜底的硬规则——实测长对话/逐批两种模式在 5 组 jp 逐字
# 相同的句子上给出不同中文，其中 2 组两种模式都错，说明是系统性漏网。W4 归
# warn 不归 hard：同一句日文在不同语境下偶有正当的不同处理，且本项目吃过
# 「谓词过严制造噪声淹没真信号」的亏。
#
# 全部命中/不命中用例走合成数据（不把活的生产译文钉进测试）。

from tools.check_batch import build_sibling_index

SIB_LEDGER = [
    {"id": 100, "jp": "【彩野】「おかえり」"},
    {"id": 200, "jp": "【彩野】「おかえり」"},     # 100 的兄弟
    {"id": 300, "jp": "【彩野】「おかえりっ」"},   # 只差一字 → 不同族
    {"id": 400, "jp": "夕焼けが見えた。"},        # 未译，不入族
]


def _sib(zh_map):
    return build_sibling_index(SIB_LEDGER, zh_map)


def test_w4_same_jp_different_zh_is_warn_with_sibling_id_and_zh():
    """jp 逐字相同、zh 不同 → W4，且消息必须写明兄弟行 id 与它的 zh。"""
    sib = _sib({200: "【彩野】「你回来了」"})
    r = check([{"id": 100, "jp": "【彩野】「おかえり」"}],
              [{"id": 100, "zh": "【彩野】「欢迎回来」"}],
              speakers=None, glossary=None, siblings=sib)
    hits = [v for v in r["warn"] if v["rule"] == "W4"]
    assert len(hits) == 1 and r["hard"] == []
    assert "200" in hits[0]["msg"] and "你回来了" in hits[0]["msg"]


def test_w4_same_jp_same_zh_is_clean():
    sib = _sib({200: "【彩野】「欢迎回来」"})
    r = check([{"id": 100, "jp": "【彩野】「おかえり」"}],
              [{"id": 100, "zh": "【彩野】「欢迎回来」"}],
              speakers=None, glossary=None, siblings=sib)
    assert not any(v["rule"] == "W4" for v in r["warn"])


def test_w4_one_char_different_jp_is_not_a_family():
    """jp 差一字即不同族：不得因「像」而报（谓词过严会淹没真信号）。"""
    sib = _sib({300: "【彩野】「你回来啦」"})
    r = check([{"id": 100, "jp": "【彩野】「おかえり」"}],
              [{"id": 100, "zh": "【彩野】「欢迎回来」"}],
              speakers=None, glossary=None, siblings=sib)
    assert not any(v["rule"] == "W4" for v in r["warn"])


def test_w4_catches_duplicates_inside_the_same_batch():
    """同一 jp 在本批出现两次、译法不同 → 两行都报（兄弟尚未进 forward）。"""
    sib = _sib({})
    r = check([{"id": 100, "jp": "【彩野】「おかえり」"},
               {"id": 200, "jp": "【彩野】「おかえり」"}],
              [{"id": 100, "zh": "【彩野】「欢迎回来」"},
               {"id": 200, "zh": "【彩野】「你回来了」"}],
              speakers=None, glossary=None, siblings=sib)
    hits = [v for v in r["warn"] if v["rule"] == "W4"]
    assert {v["id"] for v in hits} == {100, 200}
    assert "200" in next(v for v in hits if v["id"] == 100)["msg"]


def test_w4_silent_when_sibling_untranslated():
    """兄弟行还没译 → 无从比较，不报。"""
    sib = _sib({})  # 200 未译
    r = check([{"id": 100, "jp": "【彩野】「おかえり」"}],
              [{"id": 100, "zh": "【彩野】「欢迎回来」"}],
              speakers=None, glossary=None, siblings=sib)
    assert not any(v["rule"] == "W4" for v in r["warn"])


def test_w4_own_stale_forward_zh_is_not_a_sibling():
    """本批 id 在车道里已有旧译文时，新草稿不得与自己的旧版本互报。"""
    sib = _sib({100: "【彩野】「旧译文」", 200: "【彩野】「欢迎回来」"})
    r = check([{"id": 100, "jp": "【彩野】「おかえり」"}],
              [{"id": 100, "zh": "【彩野】「欢迎回来」"}],
              speakers=None, glossary=None, siblings=sib)
    assert not any(v["rule"] == "W4" for v in r["warn"])


def test_w4_absent_siblings_arg_keeps_old_behaviour():
    """不传 siblings（既有调用方）→ 完全不判 W4，行为逐字不变。"""
    r = check([{"id": 100, "jp": "【彩野】「おかえり」"}],
              [{"id": 100, "zh": "【彩野】「欢迎回来」"}],
              speakers=None, glossary=None)
    assert r["warn"] == [] and r["hard"] == []


def test_w4_real_lane_structure(tmp_path):
    """真实车道上的结构性自检（不钉具体数字——本项目吃过「测试钉住活的生产
    数据、因无关原因变红」的亏，见 test_saturation.py 同类改造）。只断言恒真
    结构 + 非空性：族索引读得出来、异译族 ⊆ 多成员族 ⊆ 全部族，且多成员族
    非空（否则这条测试就是「恒绿的安全闸」，什么都没验）。"""
    from tools.check_batch import load_siblings
    from tools.pipelib import REPO
    idx = load_siblings(REPO / "pilot" / "lanes" / "opus")
    assert idx is not None
    fam = {jp: v for jp, v in idx.items() if len(v) > 1}
    bad = {jp: v for jp, v in fam.items() if len({z for _, z in v}) > 1}
    assert 0 < len(fam) <= len(idx)
    assert len(bad) <= len(fam)


def test_w4_disabled_is_announced_not_silent(tmp_path, monkeypatch, capsys):
    """W4 未启用时必须**显式播报**，不得与「跑了没报」同形。

    没有这条播报，「闸没跑」和「闸跑了没报」都打 `warn=0`，人眼无从分辨——
    正是本项目反复吃亏的恒绿闸形态。本测试钉住播报本身，防它在日后重构里
    悄悄消失、把问题原样带回来。
    """
    work = tmp_path / "work"
    (work / "ctx" / "batch_1").mkdir(parents=True)
    (work / "out").mkdir(parents=True)
    (work / "ctx" / "batch_1" / "source.jsonl").write_text(
        '{"id": 1, "jp": "【彩野】「おかえり」"}\n', encoding="utf-8")
    (work / "out" / "batch_1.draft.jsonl").write_text(
        '{"id": 1, "zh": "【彩野】「欢迎回来」"}\n', encoding="utf-8")
    monkeypatch.setattr("tools.check_batch.WORK", work)
    # 车道根指向一个没有 data/ 的空目录 → load_siblings 返回 None
    empty = tmp_path / "nolane"
    empty.mkdir()
    assert check_batch_main(["--batch", "1", "--lane-dir", str(empty)]) == 0
    out = capsys.readouterr().out
    assert "W4 未启用" in out, "W4 未启用时必须播报，否则与「跑了没报」不可区分"
    assert "未被检查" in out


# ---- W3 行宽按屏幕实际占位算：ruby 注音不占宽 ----
# 缺陷背景：`_max_line_width` 直接对原始串计宽，把 `<A,B>` 整段算进去。
# 引擎只在 A 正上方以小字号渲染 B，行宽只占 A。后果双向：zh 一加注音 W3
# 必然虚高误报（译者消警最省事的办法就是删注音），jp 侧 38 处原生 ruby 同样
# 被撑大分母、把真超宽的译文放过去。

def test_strip_ruby_keeps_base_drops_reading():
    assert _strip_ruby("<囔,nāng>") == "囔"
    assert _strip_ruby("【彩野】「<囔,nāng><囔,nāng>」") == "【彩野】「囔囔」"


def test_width_counts_only_ruby_base():
    """任务书给的四个实测值，逐个钉死（右侧为屏幕实际占位）。"""
    assert _max_line_width("囔") == 2
    assert _max_line_width("<囔,nāng>") == 2
    assert _max_line_width("【彩野】「囔囔」") == 16
    assert _max_line_width("【彩野】「<囔,nāng><囔,nāng>」") == 16


def test_width_handles_fullwidth_latin_ruby_base():
    """真实语料里存在全角拉丁前半段：Ｔｒｕｅ(8)+半角空格(1)+Ｃｏｌｏｒ(12)-…"""
    assert _max_line_width("<Ｔｒｕｅ Ｃｏｌｏｒ,トゥルー カラー>") == 19


def test_width_does_not_eat_stray_angle_brackets():
    """孤立/畸形的 `<` `>` 在屏幕上确实占位，不得被当作 ruby 标记吃掉。"""
    assert _max_line_width("a<b") == 3          # 无逗号无闭合
    assert _max_line_width("5 > 3") == 5        # 纯不等号
    assert _max_line_width("<a,b,c>") == 7      # 两个逗号 → 非良构，按字面计


def test_width_strips_ruby_before_splitting_breaks():
    """顺序钉死：先剥 ruby 再按 _n/_r 切。

    断行码落在 ruby 标记内部是两种顺序唯一的分歧点。先切 → `<漢字,か` /
    `な>` 两段废片按字面计宽（4→ 虚高至 7）；先剥 → ruby 作原子标记参数
    处理，得 `漢字` = 4。
    """
    assert _max_line_width("<漢字,か_nな>") == 4


def test_zh_ruby_does_not_false_trigger_w3():
    """zh 侧：同一句加了汉语拼音注音，不得因此报 W3。"""
    src = [{"id": 1, "jp": "【彩野】「うん、<前向性健忘,ぜんこうせいけんぼう>だよ」"}]
    with_ruby = [{"id": 1, "zh": "【彩野】「嗯，是<前向性健忘,shùn xíng xìng yí wàng>哦」"}]
    no_ruby = [{"id": 1, "zh": "【彩野】「嗯，是前向性健忘哦」"}]
    r_ruby = check(src, with_ruby, speakers=None, glossary=None)
    r_plain = check(src, no_ruby, speakers=None, glossary=None)
    assert not any(v["rule"] == "W3" for v in r_ruby["warn"]), \
        "加注音不得触发 W3，否则消警的最省事办法就是删注音"
    assert not any(v["rule"] == "W3" for v in r_plain["warn"])


def test_jp_ruby_no_longer_inflates_threshold():
    """jp 侧：原文 ruby 撑大的分母曾把真超宽译文放过去，现在必须报。

    jp 屏幕宽 32（含 ruby 字面则虚高到 55）；zh 宽 40：
    真阈值 32*1.15=36.8 → 超；虚高阈值 55*1.15=63.25 → 曾被放过。
    """
    src = [{"id": 1, "jp": "【彩野】「うん、<前向性健忘,ぜんこうせいけんぼう>だよ」"}]
    wide = [{"id": 1, "zh": "长" * 20}]
    assert _max_line_width(src[0]["jp"]) == 32 and _max_line_width(wide[0]["zh"]) == 40
    r = check(src, wide, speakers=None, glossary=None)
    assert any(v["rule"] == "W3" for v in r["warn"]), \
        "jp 侧 ruby 不得撑大分母、把真超宽译文放过去"
