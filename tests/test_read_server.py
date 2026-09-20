"""`tools/read_server.py`（通读 Web UI）的测试。

重点在三件**会静默出错**的事上：
1. 行序必须是 `timeline.jsonl` 的路线序，不是 id 序——弄错了页面照样渲染，
   只是读起来是乱的，人不容易察觉；
2. `timeline` 没覆盖到的行必须仍然出现（附录单元），否则"从头到尾显示所有行"
   是假的，而缺的那几十行也不会有任何报错；
3. 写只准落一处草稿——它读的是**生产车道**，任何直接写生产的路径都是缺陷。
"""
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import append_jsonl, read_jsonl, write_jsonl
from tools.read_server import (APPENDIX_SEQ, Reader, append_edit, check_edit,
                               load_edits, make_handler)


def _mini(tmp_path):
    """一个最小替身仓库：4 行叙述 + 1 行 ambient，路线序刻意与 id 序相反。"""
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    lane = repo / "pilot" / "lanes" / "opus" / "data"
    lane.mkdir(parents=True)
    (repo / "pilot" / "polish" / "segA").mkdir(parents=True)

    write_jsonl(repo / "data" / "ledger.jsonl", [
        {"id": 10, "jp": "アヤノは笑った。", "voice": "NONVOICE", "file": "f1",
         "func": "scene_a", "chapter": "s1s", "kind": "narrative", "line": 1},
        {"id": 11, "jp": "【彩野】「うん」", "voice": "AYA001", "file": "f1",
         "func": "scene_a", "chapter": "s1s", "kind": "narrative", "line": 2},
        {"id": 20, "jp": "夜になった。", "voice": "NONVOICE", "file": "f2",
         "func": "scene_b", "chapter": "s2s", "kind": "narrative", "line": 1},
        {"id": 21, "jp": "……でも。", "voice": "NONVOICE", "file": "f2",
         "func": "scene_b", "chapter": "s2s", "kind": "narrative", "line": 2},
        {"id": 99, "jp": "【■おしらせ】", "voice": "NONVOICE", "file": "sys",
         "func": "sys", "chapter": "sys", "kind": "ambient", "line": 1},
    ])
    # 路线序：先 scene_b（20/21），再 marker，再 scene_a（10/11）——与 id 序相反
    write_jsonl(repo / "data" / "timeline.jsonl", [
        {"seq": 1, "type": "unit", "unit_kind": "scene", "src": "f2",
         "state": "s2s_10", "title": "夜", "ids": [20, 21]},
        {"seq": 2, "type": "marker", "text": "【讲述指针回溯至 s1s_10】", "recap": "重讲。"},
        {"seq": 3, "type": "unit", "unit_kind": "scene", "src": "f1",
         "state": "s1s_10", "title": "昼", "ids": [10, 11]},
    ])
    write_jsonl(lane / "forward.jsonl", [
        {"id": i, "zh": f"首译{i}", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t0"} for i in (10, 11, 20, 21, 99)
    ])
    write_jsonl(lane / "patches.jsonl", [
        {"id": 11, "zh": "改一次", "reason": "recall", "glossary_v": 2, "ts": "t1"},
        {"id": 11, "zh": "改两次", "reason": "polish", "glossary_v": 3, "ts": "t2",
         "prov": {"channel": "chA", "seg": "segA"}},
    ])
    write_jsonl(repo / "pilot" / "polish" / "segA" / "decisions.jsonl", [
        {"id": 11, "verdict": "adopt", "chosen_channel": "chA", "edited_zh": None,
         "reason_code": "语序", "note": "这条是人裁批注", "ts": "t2"},
    ])
    return repo


@pytest.fixture
def reader(tmp_path):
    return Reader(repo=_mini(tmp_path))


# ---- 1. 路线序 ----

def test_units_follow_route_order_not_id_order(reader):
    """替身仓库刻意把路线序做成与 id 序相反——目录必须按路线走。"""
    seqs = [u["seq"] for u in reader.units]
    assert seqs == [1, 2, 3, APPENDIX_SEQ]
    assert reader.unit_payload(1)["title"] == "夜"      # id 20/21 在前
    assert reader.unit_payload(3)["title"] == "昼"      # id 10/11 在后
    assert [l["id"] for l in reader.unit_payload(1)["lines"]] == [20, 21]


def test_marker_units_are_kept_in_place(reader):
    """`type=marker` 的路线标记没有文本，但它是路线叙事的一部分，必须留在序里。"""
    mk = reader.by_seq[2]
    assert mk["type"] == "marker" and mk["n_lines"] == 0
    assert "回溯" in mk["text"]


def test_prev_next_chain_covers_whole_route(reader):
    """顺着 next_seq 从头走到尾，要能走遍全部单元——通读靠的就是这条链。"""
    seq, walked = reader.units[0]["seq"], []
    while seq is not None:
        walked.append(seq)
        seq = reader.unit_payload(seq)["next_seq"]
    assert walked == [u["seq"] for u in reader.units]
    assert reader.unit_payload(reader.units[0]["seq"])["prev_seq"] is None


# ---- 2. 一行都不能少 ----

def test_appendix_holds_lines_the_route_misses(reader):
    """ambient 行不在任何演出单元里，必须挂进附录——否则缺行且无任何报错。"""
    ap = reader.unit_payload(APPENDIX_SEQ)
    assert [l["id"] for l in ap["lines"]] == [99]
    assert ap["unit_kind"] == "appendix"


def test_total_lines_equals_ledger(reader):
    o = reader.outline_payload()
    assert o["total_lines"] == o["ledger_lines"] == 5


# ---- 3. 每行的层次 ----

def test_line_carries_current_text_and_full_history(reader):
    ln = [l for l in reader.unit_payload(3)["lines"] if l["id"] == 11][0]
    assert ln["zh"] == "改两次", "现行译文＝forward+patches 的 resolve 结果"
    assert ln["first_zh"] == "首译11"
    assert ln["revised"] is True
    assert [h["zh"] for h in ln["history"]] == ["改一次", "改两次"]
    # prev 串成链：每一步都说得清"从哪一版改到哪一版"
    assert [h["prev"] for h in ln["history"]] == ["首译11", "改一次"]
    assert ln["history"][1]["prov"]["channel"] == "chA"


def test_line_carries_human_decision_notes(reader):
    ln = [l for l in reader.unit_payload(3)["lines"] if l["id"] == 11][0]
    assert len(ln["decisions"]) == 1
    d = ln["decisions"][0]
    assert d["seg"] == "segA" and d["verdict"] == "adopt"
    assert d["note"] == "这条是人裁批注"


def test_untouched_line_has_no_history(reader):
    ln = [l for l in reader.unit_payload(3)["lines"] if l["id"] == 10][0]
    assert ln["revised"] is False and ln["history"] == [] and ln["decisions"] == []


# ---- 4. 搜索与跳转 ----

def test_search_matches_both_sides_and_reports_where(reader):
    assert reader.search("夜になった")["hits"][0]["where"] == "原文"
    assert reader.search("改两次")["hits"][0]["where"] == "译文"
    assert reader.search("")["hits"] == []


def test_search_truncation_is_declared_not_silent(reader):
    """命中超上限要**明说截断了**——静默截断会让人以为搜全了。"""
    r = reader.search("首译", limit=1)
    assert len(r["hits"]) == 1 and r["truncated"] is True


def test_locate_maps_id_to_its_unit(reader):
    assert reader.locate(20) == 1
    assert reader.locate(10) == 3
    assert reader.locate(12345) is None


# ---- 5. 写只准落一处草稿，永不碰生产 ----

def test_only_write_endpoint_is_edit(tmp_path):
    """写路径只有 POST /api/edit 一个；没有 PUT/DELETE。"""
    H = make_handler(Reader(repo=_mini(tmp_path)))
    assert hasattr(H, "do_POST")
    assert not hasattr(H, "do_PUT")
    assert not hasattr(H, "do_DELETE")
    code, body = _post(H, "/api/nope", {"id": 11, "zh": "x"})
    assert code == 404, "除 /api/edit 外不得接受任何 POST"


def test_reading_writes_nothing(tmp_path):
    """只读的那些动作，跑完仓库里不能多出或改动任何文件。"""
    repo = _mini(tmp_path)
    before = {p: p.read_bytes() for p in sorted(repo.rglob("*")) if p.is_file()}
    r = Reader(repo=repo)
    r.outline_payload()
    for u in r.units:
        r.unit_payload(u["seq"])
    r.search("首译")
    r.locate(11)
    r.pending_payload()
    after = {p: p.read_bytes() for p in sorted(repo.rglob("*")) if p.is_file()}
    assert after == before, "只读路径写了文件"


def test_edit_touches_only_the_draft(tmp_path):
    """落一条修改：**只**多出草稿文件，生产车道与 data/ 逐字节不变。"""
    repo = _mini(tmp_path)
    before = {p: p.read_bytes() for p in sorted(repo.rglob("*")) if p.is_file()}
    r = Reader(repo=repo)
    r.record_edit({"id": 11, "zh": "人工改的", "note": "理由"})
    after = {p: p.read_bytes() for p in sorted(repo.rglob("*")) if p.is_file()}
    new_files = set(after) - set(before)
    assert len(new_files) == 1
    assert next(iter(new_files)).name.endswith(".draft.jsonl")
    assert {p: v for p, v in after.items() if p in before} == before, "生产文件被动了"


def test_append_edit_refuses_non_draft_path(tmp_path):
    """唯一写盘函数的名字断言——放在真正 open 的那一层。"""
    with pytest.raises(AssertionError, match="拒绝写非草稿文件"):
        append_edit(tmp_path / "patches.jsonl", {"id": 1, "zh": "x"})


def test_edits_are_append_only_last_wins(tmp_path):
    repo = _mini(tmp_path)
    r = Reader(repo=repo)
    r.record_edit({"id": 11, "zh": "第一版"})
    r.record_edit({"id": 11, "zh": "第二版"})
    assert len(read_jsonl(r.edits_path)) == 2, "改判要追加，不许改写旧行"
    assert load_edits(r.edits_path)[11]["zh"] == "第二版"
    ln = [l for l in Reader(repo=repo).unit_payload(3)["lines"] if l["id"] == 11][0]
    assert ln["pending"]["zh"] == "第二版"


def test_pending_flags_stale_when_lane_moved_under_it(tmp_path):
    """草稿记的"改动前文本"与车道现值对不上 → 标 stale，清关前要重看。"""
    repo = _mini(tmp_path)
    r = Reader(repo=repo)
    r.record_edit({"id": 11, "zh": "人工改的"})
    assert r._pending_payload(11, "", r.current[11])["stale"] is False
    # 模拟别处又改了这一行
    lane = repo / "pilot" / "lanes" / "opus" / "data"
    append_jsonl(lane / "patches.jsonl",
                 [{"id": 11, "zh": "别处又改了", "reason": "review",
                   "glossary_v": 9, "ts": "t9"}])
    r2 = Reader(repo=repo)
    assert r2.unit_payload(3)["lines"][1]["pending"]["stale"] is True


def test_record_edit_rejects_unknown_id_and_non_string(tmp_path):
    r = Reader(repo=_mini(tmp_path))
    with pytest.raises(ValueError, match="ledger"):
        r.record_edit({"id": 99999, "zh": "x"})
    with pytest.raises(ValueError, match="字符串"):
        r.record_edit({"id": 11, "zh": None})


def test_edit_is_saved_raw_not_cleaned(tmp_path):
    """原样保存——**警告归警告，不许替人清洗**。"""
    r = Reader(repo=_mini(tmp_path))
    out = r.record_edit({"id": 11, "zh": "  带首尾空白的  \n"})
    assert out["record"]["zh"] == "  带首尾空白的  \n"
    assert any("首尾" in w for w in out["warnings"])


# ---- 5b. 机械体检（每条都对应一次真实翻过的车）----

@pytest.mark.parametrize("jp,old,new,frag", [
    ("あ。", "啊。", "啊。\n", "首尾"),
    ("あ_nい", "啊_n哦", "啊哦", "_n"),
    ("【彩野】「あ」", "【彩野】「啊」", "编【彩野】「啊」", "不在行首"),        # 14987 实测
    ("彩野は笑う。", "彩野笑了。", "彩野『笑』了。", "卡名"),                   # 2810 实测
    ("あ。", "啊。", "小千秋说的。", "小千秋"),
    ("あ。", "啊。", "小Sakura说的。", "小Sakura"),                            # v23 全族废止
    ("あ。", "啊。", "小Chiaki说的。", "小Chiaki"),
    ("あ。", "啊。", "小雪乃说的。", "小雪乃"),
    ("あ。", "<啊,a>。", "啊。", "ruby"),
    ("あ。", "啊。", "<啊,a。", "不成对"),
])
def test_check_edit_catches(jp, old, new, frag):
    assert any(frag in w for w in check_edit(jp, old, new)), check_edit(jp, old, new)


def test_check_edit_allows_added_quote_marks_that_are_not_card_shell():
    """SEG-4 已裁定 `参ったなあ` 处可以有意新增 `「」`——`「」` 不在卡名壳之列，
    警告文案里不该扯上卡名。"""
    w = check_edit("参ったなあ、というと", "说了句真拿你没办法", "说了句「真拿你没办法」")
    assert w and all("卡名" not in x for x in w)


def test_check_edit_does_not_flag_kikuchan_nickname():
    """`小菊`（きくちゃん）是谐音绰号译名、冻结卡 129 标题，v23 明确豁免——
    它长得像「小＋名」，但不是 ちゃん 后缀族，报出来就是伪报。"""
    assert check_edit("きくちゃんに聞いた。", "问了小菊。", "去问了小菊。") == []


def test_check_edit_quiet_on_a_clean_edit():
    assert check_edit("【彩野】「あ、そう」", "【彩野】「啊，这样」",
                      "【彩野】「啊，是这样」") == []


# ---- 6. HTTP 端点 ----

def _call(handler_cls, path):
    """不起真服务，直接驱动 handler 的路由分支（同 test_adjudicate_server 的做法）。"""
    class Fake(handler_cls):
        def __init__(self):
            self.path = path
            self.command = "GET"
            self.sent = {}
            self.wfile = self
            self._buf = b""

        def write(self, b):
            self._buf += b

        def send_response(self, code):
            self.sent["code"] = code

        def send_header(self, k, v):
            self.sent.setdefault("headers", {})[k] = v

        def end_headers(self):
            pass
    f = Fake()
    f.do_GET()
    return f.sent.get("code"), (json.loads(f._buf) if f._buf.startswith(b"{") else f._buf)


def _post(handler_cls, path, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    class Fake(handler_cls):
        def __init__(self):
            self.path = path
            self.command = "POST"
            self.headers = {"Content-Length": str(len(body))}
            self.rfile = io.BytesIO(body)
            self.sent = {}
            self.wfile = self
            self._buf = b""

        def write(self, b):
            self._buf += b

        def send_response(self, code):
            self.sent["code"] = code

        def send_header(self, k, v):
            self.sent.setdefault("headers", {})[k] = v

        def end_headers(self):
            pass
    f = Fake()
    f.do_POST()
    return f.sent.get("code"), json.loads(f._buf)


def test_http_edit_endpoint(tmp_path):
    r = Reader(repo=_mini(tmp_path))
    H = make_handler(r)
    code, body = _post(H, "/api/edit", {"id": 11, "zh": "从 HTTP 改的", "note": "n"})
    assert code == 200 and body["ok"] is True
    assert load_edits(r.edits_path)[11]["zh"] == "从 HTTP 改的"
    code, body = _post(H, "/api/edit", {"id": 99999, "zh": "x"})
    assert code == 400

    code, body = _call(H, "/api/pending")
    assert code == 200 and body["total"] == 1 and body["rows"][0]["id"] == 11


def test_http_routes(tmp_path):
    H = make_handler(Reader(repo=_mini(tmp_path)))
    code, body = _call(H, "/api/outline")
    assert code == 200 and body["total_lines"] == 5

    code, body = _call(H, "/api/unit?seq=1")
    assert code == 200 and [l["id"] for l in body["lines"]] == [20, 21]

    code, body = _call(H, "/api/unit?seq=999")
    assert code == 404

    code, body = _call(H, "/api/unit?seq=abc")
    assert code == 400

    code, body = _call(H, "/api/locate?id=20")
    assert code == 200 and body["seq"] == 1

    code, body = _call(H, "/api/search?q=%E5%A4%9C")
    assert code == 200 and body["hits"]

    code, body = _call(H, "/api/nope")
    assert code == 404


def test_static_files_exist():
    """三个静态件缺一个，页面就是白屏且只有 500——在这里先钉住。"""
    ui = Path(__file__).resolve().parent.parent / "tools" / "read_ui"
    for name in ("index.html", "app.css", "app.js"):
        assert (ui / name).exists(), f"缺 {name}"


# ---- 7. v19 C1 片假名→罗马音的机械改名：默认折叠，但不得静默丢弃 ----
# 全库 8737 步修订里有 4825 步（55%）只干了这一件事。通读时它们会把真正值得看的
# 改动淹掉，所以前端默认折叠——但**必须仍然计数、仍然可展开**，藏起来不算数就
# 成了假的修订史。判据刻意保守：一步里只要有一处变化不能由改名表解释，整步照常显示。

from tools.read_server import is_c1_rename  # noqa: E402


@pytest.mark.parametrize("prev,zh", [
    ("【ユウイチ】「来来来」", "【Yuichi】「来来来」"),
    ("我轻轻地抓住了ユウイチ的胸口。", "我轻轻地抓住了Yuichi的胸口。"),
    ("アヤノ和サクラ两个人。", "Ayano和Sakura两个人。"),
    ("【アヤ……ノ】", "【Aya……no】"),                     # 断名：音节切分也要认得出
    ("彩野さんはユカリ先生に", "彩野さんはYukari先生に"),
])
def test_pure_rename_is_detected(prev, zh):
    assert is_c1_rename(prev, zh) is True


@pytest.mark.parametrize("prev,zh", [
    # 改名之外还动了别的——全库实测的真实案例，一步都不许藏
    ("那个アヤノ啊", "那个彩野啊"),                          # 故事层滑到现实层
    ("ユウイチ一如往常地上学", "他平时上下学那条"),          # 改成代词 + 改写
    ("我是片假名拼出的", "我用的是另一种写法"),              # 元话语位改写
    ("小千秋说的话", "千秋说的话"),                          # C2，不是 C1
    ("只凭现在的情报", "只凭现在的信息"),                    # 术语，不是 C1
    ("【ユウイチ】「来来来」", "【Yuichi】「来来来吧」"),     # 改名 + 加字
])
def test_mixed_change_is_never_hidden(prev, zh):
    assert is_c1_rename(prev, zh) is False


def test_no_change_is_not_a_rename():
    assert is_c1_rename("一样的", "一样的") is False
    assert is_c1_rename("", "Yuichi") is False


def test_history_marks_and_counts_c1_steps(tmp_path):
    """`c1_rename` 逐步打标、`c1_hidden` 给出总数——前端据此折叠而不是丢弃。"""
    repo = _mini(tmp_path)
    lane = repo / "pilot" / "lanes" / "opus" / "data"
    write_jsonl(lane / "forward.jsonl", [
        {"id": i, "zh": ("【ユウイチ】「唔」" if i == 10 else f"首译{i}"), "batch": 1,
         "backend": "cc", "model": "m", "ctx": "x", "glossary_v": 1, "ts": "t0"}
        for i in (10, 11, 20, 21, 99)
    ])
    write_jsonl(lane / "patches.jsonl", [
        {"id": 10, "zh": "【Yuichi】「唔」", "reason": "recall", "glossary_v": 19, "ts": "t1"},
        {"id": 10, "zh": "【Yuichi】「唔——」", "reason": "polish", "glossary_v": 19, "ts": "t2"},
    ])
    ln = Reader(repo=repo)._line_payload(10)
    assert [h["c1_rename"] for h in ln["history"]] == [True, False]
    assert ln["c1_hidden"] == 1
    assert len(ln["history"]) == 2, "折叠的那一步仍要留在 history 里，只是打了标"


# ---- 7b. 纯机械改名的行：列表页降级，不算"已改动" ----
# 折叠修订史只解决了展开之后的事；列表页的琥珀底 + ● 仍认 `revised = 有 patch`，
# 于是全库 7817 个"已改动"里有 3863 行（49%）除了 C1 罗马音化什么都没挨过，
# 「只看修订」筛出来一半是噪音。`mech_only` 把这批行降级——但只降级显示，
# `revised` 与 `history` 都不改写，展开照样看得到那几步。

def _c1_repo(tmp_path):
    """把替身仓库改造成 C1 场景：
    10 = 只有一步 C1 改名；20 = C1 之后又真改了一刀；21 = 只有 C1，但另有人裁记录。"""
    repo = _mini(tmp_path)
    lane = repo / "pilot" / "lanes" / "opus" / "data"
    write_jsonl(lane / "forward.jsonl", [
        {"id": i, "zh": ("【ユウイチ】「唔」" if i in (10, 20, 21) else f"首译{i}"),
         "batch": 1, "backend": "cc", "model": "m", "ctx": "x",
         "glossary_v": 1, "ts": "t0"} for i in (10, 11, 20, 21, 99)
    ])
    write_jsonl(lane / "patches.jsonl", [
        {"id": 10, "zh": "【Yuichi】「唔」", "reason": "recall", "glossary_v": 19, "ts": "t1"},
        {"id": 20, "zh": "【Yuichi】「唔」", "reason": "recall", "glossary_v": 19, "ts": "t1"},
        {"id": 20, "zh": "【Yuichi】「唔——」", "reason": "polish", "glossary_v": 20, "ts": "t2"},
        {"id": 21, "zh": "【Yuichi】「唔」", "reason": "recall", "glossary_v": 19, "ts": "t1"},
    ])
    write_jsonl(repo / "pilot" / "polish" / "segA" / "decisions.jsonl", [
        {"id": 21, "verdict": "keep", "chosen_channel": None, "reason_code": "维持",
         "note": "看过了，维持原译", "ts": "t3"},
    ])
    return Reader(repo=repo)


def test_pure_c1_line_is_demoted_but_history_intact(tmp_path):
    ln = _c1_repo(tmp_path)._line_payload(10)
    assert ln["mech_only"] is True, "全部改动只是 C1 机械改名，列表页不该当作已改动"
    assert ln["revised"] is True, "改过就是改过——事实不改写，只改显示"
    assert len(ln["history"]) == 1 and ln["c1_hidden"] == 1


def test_real_revision_after_c1_is_not_demoted(tmp_path):
    """C1 之后又真改了一刀——一步实质改动就足以让整行留在"已改动"里。"""
    ln = _c1_repo(tmp_path)._line_payload(20)
    assert ln["mech_only"] is False and ln["revised"] is True


def test_human_decision_keeps_a_c1_only_line_marked(tmp_path):
    """有人裁记录＝有人在这行停下来看过，哪怕文本只挨了机械改名也不降级。"""
    ln = _c1_repo(tmp_path)._line_payload(21)
    assert ln["decisions"] and ln["mech_only"] is False


def test_untouched_line_is_not_mech_only(reader):
    """没有 patch 的行不能因为"没有非 C1 步"被判成机械改名——`all([])` 为真的坑。"""
    ln = reader._line_payload(10)
    assert ln["revised"] is False and ln["mech_only"] is False


@pytest.mark.parametrize("jp,old,new,frag", [
    # 原文没有说话人、译文却凭空多出一个——只比旧译会漏掉这一种（6060 实测）
    ("……なんてね。", "……开玩笑的。", "编【直哉】「骗你的」", "有无与原文不符"),
    # 反过来：原文有说话人、译文把它删了
    ("【彩野】「あ」", "【彩野】「啊」", "啊", "有无与原文不符"),
    # 两边都"有"、名字也没变，只有位置能看出来（14987 实测的那一种）
    ("【彩野】「あ」", "【彩野】「啊」", "编【彩野】「啊」", "不在行首"),
    # 名字被改了
    ("【彩野】「あ」", "【彩野】「啊」", "【直哉】「啊」", "前缀变了"),
])
def test_check_edit_speaker_presence_is_checked_against_jp(jp, old, new, frag):
    assert any(frag in w for w in check_edit(jp, old, new)), check_edit(jp, old, new)


def test_committed_rows_are_not_pending(tmp_path):
    """清关完的行不再算"未清关"：Reader 读草稿时对着 committed.json 过滤
    （2026-09-21 之前清关完的 99 条在 UI 里照样显示为待办）。同 id 后来又改了一条
    未清关的，则那条照常待办。"""
    repo = _mini(tmp_path)
    r = Reader(repo=repo)
    r.record_edit({"id": 11, "zh": "第一版"})
    ts1 = load_edits(r.edits_path)[11]["ts"]
    r.edits_path.with_name("opus.committed.json").write_text(
        json.dumps({"committed": [{"id": 11, "ts": ts1}]}), encoding="utf-8")
    r2 = Reader(repo=repo)
    assert r2.pending_payload()["total"] == 0
    assert r2._pending_payload(11, "", r2.current[11]) is None
    # 同一秒内再改一条会与上一条同 (id, ts)，故显式给一个更晚的 ts
    append_edit(r2.edits_path, {"id": 11, "zh": "第二版", "note": "", "base_zh": "",
                                "jp": "", "lane": "pilot/lanes/opus", "ts": "9999-01-01T00:00:00+00:00"})
    r3 = Reader(repo=repo)
    assert r3.pending_payload()["total"] == 1 and r3.edits[11]["zh"] == "第二版"
