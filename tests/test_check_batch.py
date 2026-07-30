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
