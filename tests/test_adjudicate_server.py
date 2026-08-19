"""tools/adjudicate_server.py：P5 逐条裁决 Web UI 服务端的单测。

覆盖规格（docs/ops/p5-adjudicate-ui-spec.md）§6 点名的五项：
①队列计算（changed / adjudicate / alts 三种进队理由 + noop 不进队）
②阅读顺序排序 ③草稿读写与改判取最后一条 ④漂移标记 ⑤HTTP 端点基本响应。

**替身仓库的 id 是刻意"乱序"的**：阅读顺序 [7, 30, 10, 20, 5, 40] 与 id 数值序
完全不同，且分两批——只要有人把队列排序退化回 `sorted(ids)`，②立刻红。同理，
额外塞了一条 `lane="extra"` 的批：它不属于正文阅读流，混进来会污染前文上下文，
所以必须被 `reading_order()` 滤掉。

id 7 **不在段内**（只在 data/ledger.jsonl 与车道 forward.jsonl 里），专门验证
"跨段边界的前文上下文"这条路径：jp 走全局 ledger、zh 走车道 resolve，缺一就
会在段首几行显示空白。
"""
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import adjudicate_server as A
from tools.pipelib import dumps, write_jsonl

SEG = "p5segT"

JP = {7: "ゆうべの雨はもう上がっていた。", 30: "彼女は窓の外を見ていた。",
      10: "教室は静かだった。", 20: "時計は止まったままだ。",
      5: "夏の匂いがした。", 40: "僕は名刺の裏に書いた。"}
FROZEN = {30: "她望着窗外。", 10: "教室里很安静。", 20: "时钟依旧停着。",
          5: "有夏天的味道。", 40: "我写在名片背面。"}
LANE = {**FROZEN, 7: "昨夜的雨已经停了。"}


def _cand(cid, ch, zh, **kw):
    row = {"id": cid, "channel": ch, "batch": 1, "zh": zh, "score": 70, "note": "",
           "adjudicate": False, "alts": [], "noop": False, "ts": "2026-08-19T00:00:00+00:00"}
    row.update(kw)
    return row


@pytest.fixture
def repo(tmp_path):
    """最小替身仓库。数据面刻意只放本工具真的会读的那几个文件，缺一个就该炸。"""
    (tmp_path / "data").mkdir()
    write_jsonl(tmp_path / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": [7, 30, 10, 20]},
        {"batch": 2, "lane": "main", "ids": [5, 40]},
        {"batch": 3, "lane": "extra", "ids": [999]},     # 非正文流，必须被滤掉
    ])
    write_jsonl(tmp_path / "data" / "ledger.jsonl",
                [{"id": i, "jp": t} for i, t in JP.items()] + [{"id": 999, "jp": "画像焼き"}])

    lane = tmp_path / "pilot" / "lanes" / "opus" / "data"
    lane.mkdir(parents=True)
    write_jsonl(lane / "forward.jsonl", [{"id": i, "zh": t} for i, t in LANE.items()])
    # id 20 在冻结之后被车道补丁改过 → 漂移
    write_jsonl(lane / "patches.jsonl", [{"id": 20, "zh": "时钟还停在那里。"}])

    d = tmp_path / "pilot" / "polish" / SEG
    (d / "frozen").mkdir(parents=True)
    write_jsonl(d / "frozen" / "source.jsonl",
                [{"id": i, "jp": JP[i], "batch": 1 if i in (30, 10, 20) else 2}
                 for i in (30, 10, 20, 5, 40)])
    write_jsonl(d / "frozen" / "opus.jsonl", [{"id": i, "zh": t} for i, t in FROZEN.items()])
    (d / "frozen" / "locked.json").write_text(dumps(
        {"ids": [5], "hard_ids": [], "soft_ids": [5], "why": {"5": "锚点行"}}), encoding="utf-8")

    write_jsonl(d / "candidates.chA.jsonl", [
        _cand(30, "chA", "她一直望着窗外。"),                       # changed → 进队
        _cand(10, "chA", FROZEN[10], noop=True),                    # 零改动，无话 → 不进队
        _cand(20, "chA", FROZEN[20], adjudicate=True, noop=True,
              note="没改，但这句和 7 的时态呼应存疑"),               # adjudicate → 进队
        _cand(5, "chA", FROZEN[5], noop=True,
              alts=[{"zh": "闻到了夏天的气味。", "note": "更口语"}]),  # alts → 进队
        _cand(40, "chA", "我把它写在名片背面。"),                    # 旧行：有改动
        _cand(40, "chA", FROZEN[40], noop=True),                    # 新行：零改动（后行覆盖前行）
    ])
    write_jsonl(d / "candidates.chB.jsonl", [
        _cand(10, "chB", FROZEN[10], noop=True),
        _cand(40, "chB", "我写在了名片的背面。", score=88),          # changed → 进队
    ])
    (d / "lane_drift.json").write_text(dumps(
        {"lane": "pilot/lanes/opus", "drifted": 1,
         "findings": [{"id": 20, "frozen_zh": FROZEN[20], "current_zh": "时钟还停在那里。"}]}),
        encoding="utf-8")
    return tmp_path


@pytest.fixture
def model(repo):
    return A.Adjudication(SEG, repo=repo, context_before=30, context_after=2)


# ---------------------------------------------------------------- ①队列计算
def test_queue_membership_and_reasons(model):
    ids = [it["id"] for it in model.queue]
    assert ids == [30, 20, 5, 40], "10 两个通道都零改动无话可说，不该进队列"
    by = {it["id"]: it for it in model.queue}
    assert by[30]["reasons"] == ["changed"]
    assert by[20]["reasons"] == ["adjudicate"], "零改动 + 请裁必须进队列（P4 D3 教训）"
    assert by[5]["reasons"] == ["alts"], "主候选没改但给了备选，同样要让人看见"
    assert by[40]["reasons"] == ["changed"]


def test_last_candidate_row_wins(model):
    """候选文件 append-only：同 id 取最后一条。chA 对 40 的最后一行是零改动，
    所以 40 的提案通道只剩 chB——若实现取了第一条，这里会变成两个通道。"""
    by = {it["id"]: it for it in model.queue}
    assert by[40]["channels"] == ["chB"]
    assert by[40]["n_proposals"] == 1 and by[40]["n_covered"] == 2
    assert [p["channel"] for p in model.item_payload(40)["proposals"]] == ["chA", "chB"]


def test_collapsible_and_alts_payload(model):
    p = {x["channel"]: x for x in model.item_payload(5)["proposals"]}["chA"]
    assert p["same_as_current"] and not p["collapsible"], "有备选就不该被折叠掉"
    assert p["alts"] == [{"zh": "闻到了夏天的气味。", "note": "更口语"}]
    # 20 的 chA 零改动但带 note + 请裁 → 同样不折叠（折叠会把批注一起藏掉）
    q = {x["channel"]: x for x in model.item_payload(20)["proposals"]}["chA"]
    assert q["adjudicate"] and not q["collapsible"]


# ---------------------------------------------------------------- ②阅读顺序
def test_reading_order_not_numeric(model):
    ids = [it["id"] for it in model.queue]
    assert ids == [30, 20, 5, 40]
    assert ids != sorted(ids), "队列若按 id 数值序排，上下文对读就失效了"
    assert model.order == [7, 30, 10, 20, 5, 40], "extra 车道的批必须被滤掉"


def test_context_rows_follow_reading_order(model):
    ctx = model.item_payload(20)["context"]
    assert [r["id"] for r in ctx] == [7, 30, 10, 20, 5, 40]   # 前文 3 行 + 当前 + 后文 2 行
    cur = [r for r in ctx if r["current"]]
    assert len(cur) == 1 and cur[0]["id"] == 20
    # 段外的 id 7：jp 来自全局 ledger、zh 来自车道 resolve，两侧都不该是空
    row7 = ctx[0]
    assert row7["id"] == 7 and row7["jp"] == JP[7] and row7["zh"] == LANE[7]


def test_context_window_size(repo):
    m = A.Adjudication(SEG, repo=repo, context_before=2, context_after=1)
    assert [r["id"] for r in m.item_payload(20)["context"]] == [30, 10, 20, 5]


# ---------------------------------------------------------------- ③草稿读写
def test_draft_write_read_and_rejudge(model):
    p = model.draft_path
    assert p.name == "decisions.draft.jsonl"
    assert not p.exists()
    model.record({"id": 30, "verdict": "adopt", "chosen_channel": "chA", "reason_code": "语序"})
    # 改判：追加新行，不重写旧行
    weird = "  这条再行讨论_n（给主控：与 5 的锚点句互文，先别落）  "
    model.record({"id": 30, "verdict": "edit", "edited_zh": weird})
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "改判必须是追加，不能改写已有行"
    assert json.loads(lines[0])["verdict"] == "adopt"
    dec = model.decisions()
    assert dec[30]["verdict"] == "edit" and dec[30]["edited_zh"] == weird, "原样保存：不 trim、不清洗"
    assert model.queue_payload()["done"] == 1
    assert {it["id"]: it["verdict"] for it in model.queue_payload()["items"]}[30] == "edit"


def test_only_draft_file_is_written(model):
    model.record({"id": 30, "verdict": "keep"})
    names = {p.name for p in model.seg_dir.iterdir() if p.is_file()}
    assert "decisions.draft.jsonl" in names
    assert not (names & {"decisions.jsonl", "patches.jsonl", "triage.json", "queue.md"}), \
        "本服务只准写草稿文件"
    # 唯一写口 append_draft() 拒绝任何别的文件名（且不留下文件）
    with pytest.raises(AssertionError):
        A.append_draft(model.seg_dir / "decisions.jsonl", {"id": 30, "verdict": "keep"})
    assert not (model.seg_dir / "decisions.jsonl").exists()


def test_record_validation(model):
    for bad in ({"id": 30, "verdict": "keep_opus"},          # 生产用的取值，草稿面不认
                {"id": 30, "verdict": "adopt"},               # 缺 chosen_channel
                {"id": 30, "verdict": "adopt_alt", "chosen_channel": "chA"},   # 缺 chosen_alt
                {"id": 30, "verdict": "edit"},                # 缺 edited_zh
                {"id": "30", "verdict": "keep"}):             # id 不是整数
        with pytest.raises(ValueError):
            model.record(bad)
    assert not model.draft_path.exists()
    # 空字符串是合法的手工编辑内容（不做内容校验，只要求是字符串）
    assert model.record({"id": 30, "verdict": "edit", "edited_zh": ""})["edited_zh"] == ""


def test_next_undecided_walks_queue(model):
    assert model.next_undecided() == 30
    model.record({"id": 30, "verdict": "keep"})
    assert model.next_undecided(30) == 20
    for i in (20, 5, 40):
        model.record({"id": i, "verdict": "keep"})
    assert model.next_undecided(40) is None


# ---------------------------------------------------------------- ④漂移标记
def test_drift_from_lane_drift_and_compare(model):
    assert set(model.drift) == {20}
    assert model.drift[20]["source"] == "both", "现算与 lane_drift.json 都指认 → both"
    it = model.item_payload(20)
    assert it["zh_frozen"] == FROZEN[20] and it["zh_current"] == "时钟还停在那里。"
    assert it["drift"]["frozen"] != it["drift"]["current"]
    assert [x["drift"] for x in model.queue_payload()["items"] if x["id"] == 20] == [True]
    assert model.queue_payload()["drifted"] == 1


def test_drift_self_compare_when_no_lane_drift_file(repo):
    (repo / "pilot" / "polish" / SEG / "lane_drift.json").unlink()
    m = A.Adjudication(SEG, repo=repo)
    assert set(m.drift) == {20} and m.drift[20]["source"] == "compare"


def test_drift_union_keeps_documented_finding(repo):
    """lane_drift.json 说漂移、现算说没漂移（车道又改回去了）：并集保留，
    并标 source=lane_drift.json——宁可多显示一条能被人一眼看穿的旧警告，
    也不漏掉一条正式体检结论。"""
    p = repo / "pilot" / "polish" / SEG / "lane_drift.json"
    p.write_text(dumps({"findings": [{"id": 30, "frozen_zh": FROZEN[30],
                                      "current_zh": FROZEN[30]}]}), encoding="utf-8")
    m = A.Adjudication(SEG, repo=repo)
    assert set(m.drift) == {20, 30}
    assert m.drift[30]["source"] == "lane_drift.json" and m.drift[20]["source"] == "compare"


def test_soft_lock_surfaces(model):
    assert [x["soft"] for x in model.queue_payload()["items"] if x["id"] == 5] == [True]
    assert model.item_payload(5)["lock_why"] == "锚点行"


# ---------------------------------------------------------------- ⑤HTTP 端点
@pytest.fixture
def server(model):
    httpd = A.Server(("127.0.0.1", 0), A.make_handler(model))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()
    t.join(timeout=5)


def _get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.read().decode("utf-8")


def _post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def test_http_index_and_static(server):
    code, body = _get(server + "/")
    assert code == 200 and "P5 逐条裁决" in body and "/app.js" in body
    for path, needle in (("/app.js", "fillEditor"), ("/app.css", ".lines")):
        code, body = _get(server + path)
        assert code == 200 and needle in body


def test_http_queue_and_item(server):
    code, body = _get(server + "/api/queue")
    q = json.loads(body)
    assert code == 200 and q["seg"] == SEG and q["channels"] == ["chA", "chB"]
    assert [it["id"] for it in q["items"]] == [30, 20, 5, 40]
    assert q["total"] == 4 and q["done"] == 0 and q["draft_path"].endswith("decisions.draft.jsonl")

    code, body = _get(server + "/api/item?id=30")
    it = json.loads(body)
    assert code == 200 and it["jp"] == JP[30] and it["zh_current"] == LANE[30]
    assert [p["channel"] for p in it["proposals"]] == ["chA"]
    assert it["context"][0]["id"] == 7 and any(r["current"] for r in it["context"])


def test_http_errors(server):
    for path, code in (("/api/item?id=10", 404),     # 不在队列里
                       ("/api/item?id=zzz", 400),
                       ("/nope", 404)):
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(server + path)
        assert e.value.code == code
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(server + "/api/decide", {"id": 30, "verdict": "nonsense"})
    assert e.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(server + "/api/nope", {})
    assert e.value.code == 404


def test_http_decide_appends_and_advances(server, model):
    code, res = _post(server + "/api/decide",
                      {"id": 30, "verdict": "adopt", "chosen_channel": "chA", "reason_code": "语序"})
    assert code == 200 and res["ok"] and res["record"]["chosen_channel"] == "chA"
    assert res["next_undecided"] == 20, "裁完自动指向队列中下一条未处理项"

    code, res = _post(server + "/api/decide",
                      {"id": 5, "verdict": "adopt_alt", "chosen_channel": "chA", "chosen_alt": 1})
    assert res["record"]["chosen_alt"] == 1 and res["record"]["edited_zh"] is None

    rows = [json.loads(l) for l in model.draft_path.read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in rows] == [30, 5]
    code, body = _get(server + "/api/queue")
    assert json.loads(body)["done"] == 2


def test_state_restores_from_draft_after_restart(repo, model):
    """关服务重启：已处理状态必须从草稿文件恢复（规格 §7.3）。"""
    model.record({"id": 20, "verdict": "keep"})
    fresh = A.Adjudication(SEG, repo=repo)            # 全新实例＝重启后的服务
    assert {it["id"]: it["verdict"] for it in fresh.queue_payload()["items"]}[20] == "keep"
    assert fresh.queue_payload()["done"] == 1
    assert fresh.next_undecided() == 30
