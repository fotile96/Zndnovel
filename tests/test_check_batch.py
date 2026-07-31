import json

from tools.check_batch import check, main as check_batch_main
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
