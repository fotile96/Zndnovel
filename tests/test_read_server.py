"""`tools/read_server.py`（通读 Web UI）的测试。

重点在三件**会静默出错**的事上：
1. 行序必须是 `timeline.jsonl` 的路线序，不是 id 序——弄错了页面照样渲染，
   只是读起来是乱的，人不容易察觉；
2. `timeline` 没覆盖到的行必须仍然出现（附录单元），否则"从头到尾显示所有行"
   是假的，而缺的那几十行也不会有任何报错；
3. 本工具**只读**——任何写路径都是缺陷（它读的是生产车道）。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import write_jsonl
from tools.read_server import APPENDIX_SEQ, Reader, make_handler


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


# ---- 5. 只读 ----

def test_handler_exposes_no_write_endpoint(tmp_path):
    """本工具读的是生产车道，任何 POST 端点都是缺陷。"""
    H = make_handler(Reader(repo=_mini(tmp_path)))
    assert not hasattr(H, "do_POST")
    assert not hasattr(H, "do_PUT")
    assert not hasattr(H, "do_DELETE")


def test_reader_writes_nothing(tmp_path):
    """构造 + 取全部载荷 + 搜索，跑完仓库里不能多出或改动任何文件。"""
    repo = _mini(tmp_path)
    before = {p: p.read_bytes() for p in sorted(repo.rglob("*")) if p.is_file()}
    r = Reader(repo=repo)
    r.outline_payload()
    for u in r.units:
        r.unit_payload(u["seq"])
    r.search("首译")
    r.locate(11)
    after = {p: p.read_bytes() for p in sorted(repo.rglob("*")) if p.is_file()}
    assert after == before, "通读工具写了文件"


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
