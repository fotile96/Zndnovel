from tools.check_batch import check

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
