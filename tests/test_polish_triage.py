"""tools/polish_triage.py：四桶分流决策中枢的单测。

夹具复用真实上游模块（brief 补充信息第 2 条建议）：`polish_setup.setup()`
造 frozen/、`polish_ingest.ingest()` 灌真候选、`polish_check.gate()` 跑真
机械闸——比手搓文件更可靠，也顺带把"Task 6 应先于 Task 7 跑"这条现实
流水线顺序在夹具里如实还原。

主夹具 `mini`（单 SEG "segX"，两批）：
  batch 1：非锁定 10/11/12/14 + 锁定 13（anchor）——通道 chA。
    - 10：候选与 opus 逐字相同（bucket 1）。
    - 11：大改写（edit=26，远超 autoclear_limit=4）——K=1 时唯一挤进桶 2 的。
    - 12：中等改动（edit=7，同样超出 autoclear_limit，但幅度小于 11）——
      K=1 时被 11 挤到桶 3。
    - 14：极小改动（edit=2 ≤ autoclear_limit=4）——留给自动清关测试用。
    - 13：锁定 id。**正常 ingest 会判死锁定 id 出稿，候选文件里本不该
      出现它**——这里绕开 ingest 直接往 `candidates.chA.jsonl` 追加一行，
      制造"理论上不该发生、但万一发生了"的场景，专门验证 `triage()`
      自己的兜底再判死（bucket 0），而不是依赖上游已经挡住。
  batch 2：非锁定 15——通道 "amplify"（edit=1，同样是"小改"体量，专门
    用来验证"channel=='amplify' 恒不 autoclear"这条硬规则不受配置影响）。

`mini` 固件把 `CFG["K"]` monkeypatch 到 1（brief 给的 4 个测试函数签名只
接受 `mini` 一个参数，K=1 这件事必须在 `mini` 固件内部完成，不能要求测试
函数自己再传一个 `monkeypatch`；`pytest.fixture` 允许 `mini` 依赖
`monkeypatch` 这另一个固件，对测试函数调用方完全透明，且自动在测试结束
时还原，不会污染其他测试模块）。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_check as pcheck
from tools import polish_ingest as pi
from tools import polish_setup as ps
from tools import polish_triage as pt
from tools.pipelib import append_jsonl, dumps, read_jsonl, write_jsonl
from tools.polishlib import jp_tail

LABEL = "segX"

JP = {
    10: "アヤノは静かに微笑んだ。",
    11: "教室の時計が動いていることに気づいた。",
    12: "廊下の奥から足音が聞こえた。",
    13: "これは锚点的な台词だよ。",
    14: "ユカリは眼鏡を押し上げた。",
    15: "千秋は黒板の時計を見上げた。",
}
OPUS = {
    10: "彩野静静地微笑着。",
    11: "我注意到教室里的时钟还在走动。",
    12: "走廊尽头传来了脚步声。",
    13: "这是锚点台词哦。",
    14: "由加里推了推眼镜。",
    15: "千秋抬头看向黑板上的时钟。",
}
CAND_CHA = {
    10: OPUS[10],                                      # 零改动 -> 桶1
    11: "教室里弥漫着令人窒息的寂静,仿佛连时间都为之停滞了一般。",  # 大改（edit=26）
    12: "走廊尽头忽然传来一阵奇怪的脚步声。",                   # 中改（edit=7）
    14: "由加里扶了扶眼镜。",                              # 小改（edit=2）
}
CAND_AMPLIFY = {
    15: "千秋抬起头看向黑板上的时钟。",                        # 小改（edit=1）
}


def _build_mini(tmp_path):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids_b1 = [10, 11, 12, 13, 14]
    ids_b2 = [15]

    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": LABEL, "lane": "main", "batches": [1, 2],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": ids_b1, "seqs": [1],
         "jp_chars": len(ids_b1), "chapter": "s2s", "cut_reason": "budget"},
        {"batch": 2, "lane": "main", "ids": ids_b2, "seqs": [2],
         "jp_chars": len(ids_b2), "chapter": "s2s", "cut_reason": "budget"},
    ])

    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([
        {"chapter": "global", "items": [
            {"id": 13, "jp": JP[13], "zh": OPUS[13], "recall": "测试锚点"},
        ]},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 六条细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

    all_ids = ids_b1 + ids_b2
    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", [
        {"id": i, "jp": JP[i], "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
        for i in all_ids
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": OPUS[i], "batch": (1 if i in ids_b1 else 2),
         "backend": "cc", "model": "m", "ctx": "x", "glossary_v": 1, "ts": "t"}
        for i in all_ids
    ])
    write_jsonl(opus_data / "patches.jsonl", [])

    d = ps.setup(LABEL, opus_data, repo=repo)
    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-1"},
        {"session": 2, "batches": [2], "prompt_hash": "hash-2"},
    ]), encoding="utf-8")

    raw_cha = d / "raw" / "chA"
    raw_cha.mkdir(parents=True)
    lines = [dumps({"id": i, "jp_tail": jp_tail(JP[i]), "zh": CAND_CHA[i],
                     "score": 90, "note": "", "adjudicate": False})
             for i in (10, 11, 12, 14)]
    (raw_cha / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = pi.ingest(LABEL, "chA", 1, repo=repo)
    assert r["ok"], f"chA ingest 失败：{r}"

    raw_amp = d / "raw" / "amplify"
    raw_amp.mkdir(parents=True)
    (raw_amp / "b2.out").write_text(
        dumps({"id": 15, "jp_tail": jp_tail(JP[15]), "zh": CAND_AMPLIFY[15],
               "score": 90, "note": "", "adjudicate": False}) + "\n",
        encoding="utf-8")
    r = pi.ingest(LABEL, "amplify", 2, repo=repo)
    assert r["ok"], f"amplify ingest 失败：{r}"

    # 锁定 id 13：绕开 ingest（它会判死锁定 id 出稿）直接注入一行，制造
    # "理论上不该出现、但万一出现了"的场景，专测 triage() 自己的兜底。
    append_jsonl(d / "candidates.chA.jsonl", [{
        "id": 13, "channel": "chA", "batch": 1, "prompt_hash": "hash-1",
        "jp_hash": "x", "opus_hash": "x", "zh": "这是绕开 ingest 直接注入的候选。",
        "score": 50, "note": "", "adjudicate": False,
        "jp_tail": jp_tail(JP[13]), "ts": "t-inject",
    }])

    # 机械闸：现实流水线里 Task 6 先于 Task 7 跑，夹具照实还原。用真实文本，
    # 默认全绿（JP/OPUS/CAND 都不含【】/ruby/marks，glossary 传空表）。
    pcheck.gate(LABEL, "chA", repo=repo)
    pcheck.gate(LABEL, "amplify", repo=repo)

    def enable_autoclear(channel):
        p = d / "channel_state.json"
        state = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        state[channel] = {"autoclear": True}
        p.write_text(dumps(state), encoding="utf-8")

    def make_gate_hard(id, channel="chA"):
        p = d / f"gates.{channel}.json"
        gates = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        gates[str(id)] = {"hard": [{"id": id, "rule": "R9-test", "msg": "人为注入测试用 hard"}],
                           "warn": []}
        p.write_text(dumps(gates), encoding="utf-8")

    return SimpleNamespace(root=repo, d=d, label=LABEL,
                            enable_autoclear=enable_autoclear,
                            make_gate_hard=make_gate_hard)


@pytest.fixture
def mini(tmp_path, monkeypatch):
    monkeypatch.setitem(pt.CFG, "K", 1)
    return _build_mini(tmp_path)


def by_id(t, id, ch=None):
    rows = t["rows"] if isinstance(t, dict) else t
    matches = [r for r in rows if r["id"] == id and (ch is None or r["channel"] == ch)]
    assert matches, f"未找到 id={id} channel={ch} 的候选行；rows={rows}"
    assert len(matches) == 1, f"id={id} channel={ch} 匹配到不止一行：{matches}"
    return matches[0]


# ---- brief Step 1 核心断言（逐字照抄 brief 给的 4 个测试） ----

def test_buckets(mini):
    t = pt.triage(LABEL, repo=mini.root)
    assert by_id(t, 10)["bucket"] == 1
    assert by_id(t, 11)["bucket"] == 2
    assert by_id(t, 12)["bucket"] == 3
    assert by_id(t, 13)["bucket"] == 0


def test_autoclear_requires_gate_green_and_right(mini):
    mini.enable_autoclear("chA")
    t = pt.triage(LABEL, repo=mini.root)
    assert by_id(t, 14)["autoclear"]
    mini.make_gate_hard(14)
    assert not by_id(pt.triage(LABEL, repo=mini.root), 14)["autoclear"]


def test_amplify_never_autoclears(mini):
    mini.enable_autoclear("amplify")
    assert not by_id(pt.triage(LABEL, repo=mini.root), 15, ch="amplify")["autoclear"]


def test_deterministic_sampling(mini):
    assert pt.triage(LABEL, repo=mini.root) == pt.triage(LABEL, repo=mini.root)


# ---- 保守缺省：channel_state.json 缺失/该 channel 不在里面 → 自动清关关闭 ----

def test_autoclear_off_by_default_when_channel_state_missing(mini):
    """不调用 enable_autoclear：id14 小改+gates 绿，但没有任何 channel_state.json
    ——自动清关权必须是关闭的（保守缺省，brief 明文要求的额外变异对象）。"""
    assert not (mini.d / "channel_state.json").exists()
    t = pt.triage(LABEL, repo=mini.root)
    assert not by_id(t, 14)["autoclear"]


def test_autoclear_off_when_channel_absent_from_state_file(mini):
    """channel_state.json 存在，但只登记了别的通道——同样视为关闭。"""
    (mini.d / "channel_state.json").write_text(
        dumps({"someOtherChannel": {"autoclear": True}}), encoding="utf-8")
    t = pt.triage(LABEL, repo=mini.root)
    assert not by_id(t, 14)["autoclear"]


# ---- gates 文件整体缺失（该通道从未跑过 Task 6）→ 同样视为不可自动清关 ----

def test_missing_gates_file_blocks_autoclear(mini):
    """新增一个通道 chC，灌进和 chA 一样的小改候选，但**不跑** `polish_check.
    gate()`——即 gates.chC.json 根本不存在。即使开了自动清关权，缺少机械闸
    证据本身就该保守地拒绝自动清关（与 channel_state 缺失同一保守缺省哲学，
    见 `load_gates()` docstring）。"""
    raw_chc = mini.d / "raw" / "chC"
    raw_chc.mkdir(parents=True)
    lines = [dumps({"id": i, "jp_tail": jp_tail(JP[i]), "zh": CAND_CHA[i],
                     "score": 90, "note": "", "adjudicate": False})
             for i in (10, 11, 12, 14)]
    (raw_chc / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = pi.ingest(LABEL, "chC", 1, repo=mini.root)
    assert r["ok"]
    assert not (mini.d / "gates.chC.json").exists()

    mini.enable_autoclear("chC")
    t = pt.triage(LABEL, repo=mini.root)
    assert not by_id(t, 14, ch="chC")["autoclear"]


# ---- 结构性钉死"抽样只用种子化 Random，不碰全局未播种 random"（变异③）----

def test_sampling_never_touches_global_random(mini, monkeypatch):
    """把模块级 `random.random` 打成一炸就抛的桩：triage() 若真的调用了它
    （而不是用种子化的 `random.Random(seed)` 实例的 `.random()` 方法）就会
    在此炸出来。比 brief 给的 `test_deterministic_sampling` 更可靠——那条
    用当前夹具只有 1 个自动清关候选，未播种随机数两次刚好给出不同结果的
    概率只有约 18%（两次独立 [0,1) 抽样落在阈值两侧的概率），不是可靠的
    把关手段；这条把同一件事变成结构性、100% 确定的检验。"""
    import random as random_module
    mini.enable_autoclear("chA")

    def _boom(*a, **k):
        raise AssertionError("triage() 不应调用全局未播种的 random.random()")

    monkeypatch.setattr(random_module, "random", _boom)
    pt.triage(LABEL, repo=mini.root)  # 不应抛出


# ---- K 配额排序：显式请裁优先于改动幅度（变异②）----

def _build_mini_priority(tmp_path, label="segP"):
    """独立小夹具：id 20（小改，adjudicate=True）vs id 21（大改，adjudicate=
    False），K=1。正确实现下 20 应该赢（显式请裁优先级最高，压过纯粹的
    改动幅度排序），这是唯一能在"配额排序丢显式请裁优先"这个变异下真正
    转红的测试。"""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids = [20, 21]
    jp = {20: "彩野は本を閉じた。", 21: "教室の外で风が吹いていた。"}
    opus = {20: "彩野合上了书本。", 21: "教室外面刮着风。"}
    cand = {
        20: "彩野轻轻合上了书本。",  # 小改
        21: "窗外的风忽然变得猛烈起来,吹得窗帘哗哗作响,仿佛预示着什么。",  # 大改写
    }

    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": label, "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": ids, "seqs": [1], "jp_chars": len(ids),
         "chapter": "s2s", "cut_reason": "budget"},
    ])
    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([
        {"chapter": "global", "items": []},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 六条细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", [
        {"id": i, "jp": jp[i], "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"} for i in ids
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": opus[i], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"} for i in ids
    ])
    write_jsonl(opus_data / "patches.jsonl", [])

    d = ps.setup(label, opus_data, repo=repo)
    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-p"},
    ]), encoding="utf-8")

    raw_dir = d / "raw" / "chB"
    raw_dir.mkdir(parents=True)
    lines = [dumps({"id": 20, "jp_tail": jp_tail(jp[20]), "zh": cand[20],
                     "score": 90, "note": "", "adjudicate": True}),
              dumps({"id": 21, "jp_tail": jp_tail(jp[21]), "zh": cand[21],
                     "score": 90, "note": "", "adjudicate": False})]
    (raw_dir / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = pi.ingest(label, "chB", 1, repo=repo)
    assert r["ok"]
    pcheck.gate(label, "chB", repo=repo)

    return SimpleNamespace(root=repo, d=d, label=label)


def test_adjudicate_priority_beats_edit_magnitude_under_quota(tmp_path, monkeypatch):
    monkeypatch.setitem(pt.CFG, "K", 1)
    m = _build_mini_priority(tmp_path)
    t = pt.triage(m.label, repo=m.root)
    assert by_id(t, 20)["bucket"] == 2   # 显式请裁，尽管改动幅度小
    assert by_id(t, 21)["bucket"] == 3   # 改动幅度更大，但没有显式请裁，让位


# ---- id 级 all-or-nothing：同一 id 跨通道，只要有一个通道不达标就整体不清关 ----

def _build_mini_mixed_channels(tmp_path, label="segM"):
    """id 30 同时被 chX（小改，autoclear 之外条件都满足）与 chY（大改）
    提交候选。两个通道的自动清关权都打开、gates 都干净——只有"小改"那
    一行单独看够格，但 all-or-nothing 规则要求同 id 全部通道行都够格才
    整体摘出，所以两行都不应该被 autoclear。"""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids = [30]
    jp = {30: "由加里は窓の外を见ていた。"}
    opus = {30: "由加里望着窗外。"}
    cand_small = "由加里静静望着窗外。"     # chX：小改
    cand_big = "由加里久久凝望着窗外那片阴沉的天空,一言不发。"  # chY：大改

    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": label, "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": ids, "seqs": [1], "jp_chars": len(ids),
         "chapter": "s2s", "cut_reason": "budget"},
    ])
    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([
        {"chapter": "global", "items": []},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 六条细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", [
        {"id": 30, "jp": jp[30], "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": 30, "chapter": "s2s", "kind": "story"}
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": 30, "zh": opus[30], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"}
    ])
    write_jsonl(opus_data / "patches.jsonl", [])

    d = ps.setup(label, opus_data, repo=repo)
    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-m"},
    ]), encoding="utf-8")

    for ch, zh in (("chX", cand_small), ("chY", cand_big)):
        raw_dir = d / "raw" / ch
        raw_dir.mkdir(parents=True)
        (raw_dir / "b1.out").write_text(
            dumps({"id": 30, "jp_tail": jp_tail(jp[30]), "zh": zh,
                   "score": 90, "note": "", "adjudicate": False}) + "\n",
            encoding="utf-8")
        r = pi.ingest(label, ch, 1, repo=repo)
        assert r["ok"]
        pcheck.gate(label, ch, repo=repo)

    p = d / "channel_state.json"
    p.write_text(dumps({"chX": {"autoclear": True}, "chY": {"autoclear": True}}),
                 encoding="utf-8")

    return SimpleNamespace(root=repo, d=d, label=label)


def test_partial_channel_eligibility_blocks_whole_id_autoclear(tmp_path):
    m = _build_mini_mixed_channels(tmp_path)
    t = pt.triage(m.label, repo=m.root)
    assert not by_id(t, 30, ch="chX")["autoclear"]
    assert not by_id(t, 30, ch="chY")["autoclear"]
    # 既然没被自动清关摘走，两行应该落在同一个桶里——同 id 并排裁决。
    assert by_id(t, 30, ch="chX")["bucket"] == by_id(t, 30, ch="chY")["bucket"]


# ---- 落盘结构 ----

def test_triage_json_matches_return_value(mini):
    result = pt.triage(LABEL, repo=mini.root)
    on_disk = json.loads((mini.d / "triage.json").read_text(encoding="utf-8"))
    assert on_disk == result


def test_queue_md_content_and_sample_blinding(mini):
    mini.enable_autoclear("chA")
    pt.triage(LABEL, repo=mini.root)
    text = (mini.d / "queue.md").read_text(encoding="utf-8")
    # 队列里应包含桶 2 的 id=11（K=1 时唯一入选者），带 jp/opus/候选正文。
    assert f"id 11" in text
    assert JP[11] in text
    assert OPUS[11] in text
    assert CAND_CHA[11] in text
    # 抽检不泄露：queue.md 全文不应出现"抽检"/"sample"/"sampled" 这类字样。
    assert "抽检" not in text
    assert "sample" not in text.lower()


# ---- 评审 Important 修复：抽检必须受 K 帽约束，桶 2 总量恒 <= K ----

def _build_mini_overload(tmp_path, label, n_autoclear=50, n_real=20):
    """K 很小、自动清关候选远超预算的放大场景（评审用真实规模复现的对抗
    输入）：`n_autoclear` 个"小改"候选（autoclear 四项条件全部满足）+
    `n_real` 个"大改写"真实候选（有实质改动、需要人裁），单通道 chBig、
    单批。用来验证"桶 2 实际总量（抽检 + 排位）恒 <= K"这条不变量，以及
    K 很小时不崩溃、不产生负配额、不让某一类永远拿不到名额。

    id 分两段（100.. 给小改、500.. 给大改），jp/opus 模板里都嵌入 id 本身，
    保证任意两个 id 的 opus 文本不会逐字相同——不触发 `polish_ingest` 的
    错位侦测（那条判据要求"zh 与本批另一 id 的 opus 逐字相同"）。"""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    autoclear_ids = list(range(100, 100 + n_autoclear))
    real_ids = list(range(500, 500 + n_real))
    ids = autoclear_ids + real_ids

    jp = {i: f"测试原文第{i}句テスト。" for i in ids}
    opus = {i: f"这是第{i}句的现行译文内容示例。" for i in ids}
    cand = {}
    for i in autoclear_ids:
        cand[i] = opus[i] + "呢"  # 小改：只插入 1 个字，edit=1，远低于 autoclear_limit 的下限 4
    for i in real_ids:
        cand[i] = (f"经过大幅重写的第{i}句译文,语序与用词都发生了根本性"
                    "变化,读起来完全是另一种味道,需要人认真斟酌。")  # 大改写

    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": label, "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": ids, "seqs": [1], "jp_chars": len(ids),
         "chapter": "s2s", "cut_reason": "budget"},
    ])
    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([
        {"chapter": "global", "items": []},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 六条细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", [
        {"id": i, "jp": jp[i], "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"} for i in ids
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": opus[i], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"} for i in ids
    ])
    write_jsonl(opus_data / "patches.jsonl", [])

    d = ps.setup(label, opus_data, repo=repo)
    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-big"},
    ]), encoding="utf-8")

    raw_dir = d / "raw" / "chBig"
    raw_dir.mkdir(parents=True)
    lines = [dumps({"id": i, "jp_tail": jp_tail(jp[i]), "zh": cand[i],
                     "score": 90, "note": "", "adjudicate": False}) for i in ids]
    (raw_dir / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = pi.ingest(label, "chBig", 1, repo=repo)
    assert r["ok"], f"chBig ingest 失败：{r}"
    pcheck.gate(label, "chBig", repo=repo)

    (d / "channel_state.json").write_text(
        dumps({"chBig": {"autoclear": True}}), encoding="utf-8")

    return SimpleNamespace(root=repo, d=d, label=label,
                            autoclear_ids=autoclear_ids, real_ids=real_ids)


def test_bucket2_total_never_exceeds_K(tmp_path, monkeypatch):
    """评审 Important 复现的原始场景：50 个自动清关候选 + 20 个真实大改
    候选，K=2、sample_rate=0.5——修复前桶 2 实际总量会冲到约 30（远超
    K=2），20 条真实大改候选被全部挤到桶 3。修复后必须 <= K，且真实候选
    没有被完全挤没（体现"最小配额"裁定：K=2 时 rank_floor=1）。"""
    monkeypatch.setitem(pt.CFG, "K", 2)
    monkeypatch.setitem(pt.CFG, "sample_rate", 0.5)
    m = _build_mini_overload(tmp_path, "segBig1", n_autoclear=50, n_real=20)
    t = pt.triage(m.label, repo=m.root)
    bucket2_ids = {r["id"] for r in t["rows"] if r["bucket"] == 2}
    assert len(bucket2_ids) <= 2
    assert bucket2_ids & set(m.real_ids), \
        "真实大改候选不应该被自动清关候选完全挤出桶 2（最小配额裁定）"


def test_sample_drop_reported_in_meta_and_stderr(tmp_path, monkeypatch, capsys):
    """抽检覆盖率被压缩必须"响"：`triage.json` 的 `meta` 字段与 stderr
    告警都要出现，不能只是悄悄砍掉抽中的样本。"""
    monkeypatch.setitem(pt.CFG, "K", 2)
    monkeypatch.setitem(pt.CFG, "sample_rate", 0.5)
    m = _build_mini_overload(tmp_path, "segBig2", n_autoclear=50, n_real=20)
    t = pt.triage(m.label, repo=m.root)
    meta = t["meta"]
    assert meta["K"] == 2
    assert meta["sample_rate_configured"] == 0.5
    assert meta["autoclear_eligible_total"] == 50
    assert meta["sampled_dropped"] > 0
    assert meta["sampled_count"] + meta["sampled_dropped"] > meta["sampled_count"]
    assert meta["sample_rate_effective"] is not None
    assert meta["sample_rate_effective"] < meta["sample_rate_configured"]

    err = capsys.readouterr().err
    assert "压缩" in err
    assert str(meta["sampled_dropped"]) in err

    # 落盘的 triage.json 与内存返回值一致（meta 字段也在内）。
    on_disk = json.loads((m.d / "triage.json").read_text(encoding="utf-8"))
    assert on_disk["meta"] == meta


@pytest.mark.parametrize("k", [0, 1, 2])
def test_small_K_boundaries_no_crash_no_overflow(tmp_path, monkeypatch, k):
    """K 很小的边界（0/1/2）：不崩溃、不产生负配额、桶 2 总量恒 <= K。"""
    monkeypatch.setitem(pt.CFG, "K", k)
    monkeypatch.setitem(pt.CFG, "sample_rate", 0.5)
    m = _build_mini_overload(tmp_path, f"segBoundary{k}", n_autoclear=10, n_real=10)
    t = pt.triage(m.label, repo=m.root)
    bucket2_ids = {r["id"] for r in t["rows"] if r["bucket"] == 2}
    assert len(bucket2_ids) <= k
    assert t["meta"]["K"] == k
    assert t["meta"]["sampled_count"] <= k


def test_k1_favors_real_candidates_over_sample_on_tie(tmp_path, monkeypatch):
    """K=1 是"两类都想要唯一名额"的最极端情形——按本任务的裁定（ceil 配
    整数除法，真实编辑风险优先于二阶抽检审计），这唯一的名额应该给真实
    大改候选，不是抽检样本；抽检率设 100% 确保抽检"很想要"这个名额。"""
    monkeypatch.setitem(pt.CFG, "K", 1)
    monkeypatch.setitem(pt.CFG, "sample_rate", 1.0)
    m = _build_mini_overload(tmp_path, "segK1", n_autoclear=10, n_real=10)
    t = pt.triage(m.label, repo=m.root)
    bucket2_ids = {r["id"] for r in t["rows"] if r["bucket"] == 2}
    assert len(bucket2_ids) == 1
    assert bucket2_ids <= set(m.real_ids)
    assert t["meta"]["sampled_count"] == 0
    assert t["meta"]["sampled_dropped"] == 10


# ---- CLI ----

def test_cli_smoke(mini, capsys):
    rc = pt.main(["--seg", LABEL, "--repo", str(mini.root)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "triage" in out
    assert (mini.d / "triage.json").exists()
    assert (mini.d / "queue.md").exists()
