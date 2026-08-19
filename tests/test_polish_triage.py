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
    (repo / "glossary" / "polish.md").write_text("# 语感细则", encoding="utf-8")
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
    # id 13 同时落一条内容相同的 patch，使它在新的硬锁/软锁分类下仍归为
    # **硬锁**（patched 优先于 anchor）——保留本文件既有测试对"锁定 id 一律
    # 判死"的假设不变；软锁专属行为见下方 `_build_mini_soft_lock` 夹具。
    write_jsonl(opus_data / "patches.jsonl", [
        {"id": 13, "zh": OPUS[13], "reason": "review", "glossary_v": 1, "ts": "t"},
    ])

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
        gates = (json.loads(p.read_text(encoding="utf-8")) if p.exists()
                 else {"checked_ids": [], "findings": {}})
        gates["findings"][str(id)] = {
            "hard": [{"id": id, "rule": "R9-test", "msg": "人为注入测试用 hard"}],
            "warn": []}
        p.write_text(dumps(gates), encoding="utf-8")

    def make_gate_warn(id, rule, channel="chA"):
        """注入一条 warn（不带 hard）——用于验证"哪些 warn 阻断自动清关"。"""
        p = d / f"gates.{channel}.json"
        gates = (json.loads(p.read_text(encoding="utf-8")) if p.exists()
                 else {"checked_ids": [], "findings": {}})
        entry = gates["findings"].setdefault(str(id), {"hard": [], "warn": []})
        entry["warn"].append({"id": id, "rule": rule, "msg": f"人为注入测试用 {rule}"})
        p.write_text(dumps(gates), encoding="utf-8")

    def drop_from_checked(id, channel="chA"):
        """把某 id 从 gates 的 checked_ids 里摘掉，模拟"gate 跑过之后又入仓了
        这个 id 的新候选、但没重跑 gate"的陈旧 gates 状态（最终评审 C1）。"""
        p = d / f"gates.{channel}.json"
        gates = json.loads(p.read_text(encoding="utf-8"))
        gates["checked_ids"] = [i for i in gates["checked_ids"] if i != id]
        p.write_text(dumps(gates), encoding="utf-8")

    return SimpleNamespace(root=repo, d=d, label=LABEL,
                            enable_autoclear=enable_autoclear,
                            make_gate_hard=make_gate_hard,
                            make_gate_warn=make_gate_warn,
                            drop_from_checked=drop_from_checked)


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
    (repo / "glossary" / "polish.md").write_text("# 语感细则", encoding="utf-8")
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
    (repo / "glossary" / "polish.md").write_text("# 语感细则", encoding="utf-8")
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


# ---- 2026-08-07 用户裁定：锚点行从硬锁改软锁——强制进队列、不被 K 挤出、永不自动清关 ----

def _build_mini_soft_lock(tmp_path, label="segSoft"):
    """单批 3 个 id：40（普通，大改，用来占满 K）、41（软锁＝纯 anchor，
    小改+adjudicate=true，gates 干净，channel 自动清关权开启——若"软锁永不
    自动清关"这条规则被删掉，它会满足全部四项 autoclear 条件）、42（普通，
    小改，gates 干净，autoclear 权开启——用来确认软锁强制占位不会误伤
    正常自动清关候选）。"""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids = [40, 41, 42]
    jp = {40: "教室の窓が风で鸣った。", 41: "これは锚点的な台词だよ2。",
          42: "由加里が本を片付けた。"}
    opus = {40: "教室的窗户被风吹得响了。", 41: "这是锚点台词哦2。",
            42: "由加里收拾了书本。"}
    cand = {
        40: "教室的窗户在风中剧烈震颤,发出令人不安的响声,久久不散。",  # 大改
        41: "这是锚点台词哦2改。",   # 软锁小改
        42: opus[42] + "呢",         # 普通小改（edit=1，远小于 autoclear_limit=4）
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
        {"chapter": "global", "items": [
            {"id": 41, "jp": jp[41], "zh": opus[41], "recall": "软锁测试锚点"},
        ]},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 语感细则", encoding="utf-8")
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
    locked = json.loads((d / "frozen" / "locked.json").read_text(encoding="utf-8"))
    assert locked["soft_ids"] == [41] and locked["hard_ids"] == []

    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-soft"},
    ]), encoding="utf-8")

    raw_dir = d / "raw" / "chS"
    raw_dir.mkdir(parents=True)
    lines = [dumps({"id": 40, "jp_tail": jp_tail(jp[40]), "zh": cand[40],
                     "score": 90, "note": "", "adjudicate": False}),
              dumps({"id": 41, "jp_tail": jp_tail(jp[41]), "zh": cand[41],
                     "score": 90, "note": "斟酌后觉得这里更顺", "adjudicate": True}),
              dumps({"id": 42, "jp_tail": jp_tail(jp[42]), "zh": cand[42],
                     "score": 90, "note": "", "adjudicate": False})]
    (raw_dir / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = pi.ingest(label, "chS", 1, repo=repo)
    assert r["ok"], f"ingest 失败：{r}"
    pcheck.gate(label, "chS", repo=repo)

    (d / "channel_state.json").write_text(
        dumps({"chS": {"autoclear": True}}), encoding="utf-8")

    return SimpleNamespace(root=repo, d=d, label=label, jp=jp, opus=opus, cand=cand)


def test_soft_lock_edit_forced_into_queue_never_autoclears(tmp_path, monkeypatch):
    """id 41 是软锁+小改+gates 干净+通道自动清关权开启——若没有"软锁永不
    自动清关"这条专门规则，它满足全部四项普通 autoclear 条件，本该被判
    `autoclear=True`。这条测试直接钉死：无论普通条件多满足，软锁改动
    永远 `autoclear=False`、`bucket=2`。"""
    monkeypatch.setitem(pt.CFG, "K", 150)   # 充足预算，排除"被 K 挤到桶3"的解释
    m = _build_mini_soft_lock(tmp_path)
    t = pt.triage(m.label, repo=m.root)
    row41 = by_id(t, 41, ch="chS")
    assert row41["bucket"] == 2
    assert row41["autoclear"] is False
    assert row41["sampled"] is False


def test_soft_lock_edit_not_squeezed_out_by_zero_K(tmp_path, monkeypatch):
    """K=0（人工预算完全耗尽）——普通改动候选（id 40）理应进不了桶 2，但
    软锁改动（id 41）必须依然强制进队列，不被 K 挤出。这是"软锁不被 K
    挤出"这条规则唯一能在"K 帽已经收紧到 0"这个极端下被验证到的场景。"""
    monkeypatch.setitem(pt.CFG, "K", 0)
    m = _build_mini_soft_lock(tmp_path)
    t = pt.triage(m.label, repo=m.root)
    assert by_id(t, 41, ch="chS")["bucket"] == 2
    assert by_id(t, 40, ch="chS")["bucket"] == 3   # 普通大改，K=0 时挤不进队列
    assert t["meta"]["forced_soft_count"] == 1
    assert t["meta"]["forced_soft_over_budget"] is True  # n_forced(1) > K(0)


def test_soft_lock_unchanged_gets_bucket1_no_special_treatment(tmp_path, monkeypatch):
    """软锁 id 若 zh 逐字等于 opus（没改），正常走桶 1，没有任何特殊标记
    ——spec 原话"无特殊待遇"。"""
    monkeypatch.setitem(pt.CFG, "K", 150)
    m = _build_mini_soft_lock(tmp_path)
    # 改造：把 41 的候选替换成"没改"（zh 逐字等于 opus）。
    p = m.d / "candidates.chS.jsonl"
    rows = read_jsonl(p)
    for r in rows:
        if r["id"] == 41:
            r["zh"] = m.opus[41]
            r["adjudicate"] = False
    write_jsonl(p, rows)
    t = pt.triage(m.label, repo=m.root)
    assert by_id(t, 41, ch="chS")["bucket"] == 1


def test_soft_lock_forced_does_not_starve_normal_autoclear(tmp_path, monkeypatch):
    """软锁强制占位只该占用 K 名额，不该额外污染普通候选自己的 autoclear
    资格判定——id 42（普通小改，gates 干净，autoclear 权开启）依然应该被
    正常自动清关。"""
    monkeypatch.setitem(pt.CFG, "K", 150)
    m = _build_mini_soft_lock(tmp_path)
    t = pt.triage(m.label, repo=m.root)
    assert by_id(t, 42, ch="chS")["autoclear"] is True


def test_soft_lock_queue_md_labels_forced_reason(tmp_path, monkeypatch):
    m = _build_mini_soft_lock(tmp_path)
    monkeypatch.setitem(pt.CFG, "K", 150)
    pt.triage(m.label, repo=m.root)
    text = (m.d / "queue.md").read_text(encoding="utf-8")
    assert "id 41" in text
    assert "软锁改动" in text
    assert "不受 K 名额影响" in text


# ---- SEG-0 D3 修复：adjudicate=true 的候选无论有无改动都必须强制进队列 ----
# （pilot/polish/seg0-s0-s1/channel_feedback.md D3 节：17002/7963 两例被
#  静默丢进桶 1，靠人工发现才手工捞回——这里钉死机制层面的保证，不再靠人）

def _build_mini_adjudicate_forced(tmp_path, label="segAdj"):
    """单批 4 个 id，单通道 chZ：
    50（对照组：零改动，`adjudicate=False`——正常走桶 1，不受本次修复影响）；
    51（D3 原始场景：零改动，但 `adjudicate=True`——通道原样照抄 opus，只在
      note 里提问"我不改，但请你裁"。旧实现会被 `zh==opus` 分支拦下直接
      丢进桶 1，本次修复要求它无论如何都进桶 2）；
    52（D3 的隐藏镜像面：有改动，`adjudicate=True`，但改动幅度极小
      （edit=2 ≤ autoclear_limit=4）、gates 干净、通道自动清关权开启——
      若不做本次修复，它会满足 `_eligible` 的全部四项条件，被 autoclear
      判定为"安全小改"直接清关掉，同样不会出现在 queue.md 里，只是触发
      路径与 51 不同）；
    53（对照组：有改动，`adjudicate=False`，同样是小改+gates 干净+自动
      清关权开启——用来确认"adjudicate 强制进队列"这条新规则不会误伤
      正常的自动清关候选，即 52 被拦下不代表 autoclear 机制本身坏了）。
    """
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids = [50, 51, 52, 53]
    jp = {50: "彩野は时计を见た。", 51: "終了しました。",
          52: "これは小さな改动のテストだよ。", 53: "由加里は本を闭じた。"}
    opus = {50: "彩野看了看时钟。", 51: "已完结。",
            52: "这是一个小改动的测试哦。", 53: "由加里合上了书本。"}
    cand = {
        50: opus[50],                    # 零改动，adjudicate=False -> 桶1
        51: opus[51],                    # 零改动，adjudicate=True（D3 原始场景）
        52: opus[52] + "呢",              # 小改（edit=1），adjudicate=True（D3 镜像面）
        53: opus[53] + "呢",              # 小改（edit=1），adjudicate=False（对照组）
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
    (repo / "glossary" / "polish.md").write_text("# 语感细则", encoding="utf-8")
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
        {"session": 1, "batches": [1], "prompt_hash": "hash-adj"},
    ]), encoding="utf-8")

    raw_dir = d / "raw" / "chZ"
    raw_dir.mkdir(parents=True)
    lines = [
        dumps({"id": 50, "jp_tail": jp_tail(jp[50]), "zh": cand[50],
               "score": 90, "note": "", "adjudicate": False}),
        dumps({"id": 51, "jp_tail": jp_tail(jp[51]), "zh": cand[51],
               "score": 90, "note": "我不改，但请你裁：跨段术语一致性存疑",
               "adjudicate": True}),
        dumps({"id": 52, "jp_tail": jp_tail(jp[52]), "zh": cand[52],
               "score": 90, "note": "小改但吃不准，请裁", "adjudicate": True}),
        dumps({"id": 53, "jp_tail": jp_tail(jp[53]), "zh": cand[53],
               "score": 90, "note": "", "adjudicate": False}),
    ]
    (raw_dir / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = pi.ingest(label, "chZ", 1, repo=repo)
    assert r["ok"], f"ingest 失败：{r}"
    pcheck.gate(label, "chZ", repo=repo)

    (d / "channel_state.json").write_text(
        dumps({"chZ": {"autoclear": True}}), encoding="utf-8")

    return SimpleNamespace(root=repo, d=d, label=label, jp=jp, opus=opus, cand=cand)


def test_adjudicate_zero_edit_forced_into_queue_not_bucket1(tmp_path, monkeypatch):
    """D3 原始场景：51 零改动但 `adjudicate=True`——必须落桶 2，不能被
    `zh==opus` 分支拦下丢进桶 1。50（零改动+adjudicate=False）作为对照，
    仍然正常走桶 1——本次修复不改变"真的没什么好说"的候选的命运。"""
    monkeypatch.setitem(pt.CFG, "K", 150)
    m = _build_mini_adjudicate_forced(tmp_path)
    t = pt.triage(m.label, repo=m.root)
    assert by_id(t, 51, ch="chZ")["bucket"] == 2
    assert by_id(t, 51, ch="chZ")["autoclear"] is False
    assert by_id(t, 50, ch="chZ")["bucket"] == 1


def test_adjudicate_small_edit_never_autoclears(tmp_path, monkeypatch):
    """D3 的隐藏镜像面：52（小改+adjudicate=True，gates 干净，自动清关权
    开启）满足全部四项普通 autoclear 条件，若"adjudicate 强制进队列"这
    条规则被删掉或被限定成"只管零改动"，它会被判 autoclear=True 直接
    清关掉——这条测试钉死"无论有没有改动"这几个字，不是只堵了 D3 报告里
    明确点名的那一个子场景。53（小改+adjudicate=False，其余条件相同）
    作为对照，必须正常被 autoclear，证明这条新规则没有连带破坏正常的
    自动清关机制。"""
    monkeypatch.setitem(pt.CFG, "K", 150)
    m = _build_mini_adjudicate_forced(tmp_path)
    t = pt.triage(m.label, repo=m.root)
    assert by_id(t, 52, ch="chZ")["bucket"] == 2
    assert by_id(t, 52, ch="chZ")["autoclear"] is False
    assert by_id(t, 52, ch="chZ")["sampled"] is False
    assert by_id(t, 53, ch="chZ")["autoclear"] is True


def test_adjudicate_forced_not_squeezed_out_by_zero_K(tmp_path, monkeypatch):
    """K=0（人工预算完全耗尽）——请裁强制项与软锁强制项同等待遇，必须依然
    不被 K 挤出。"""
    monkeypatch.setitem(pt.CFG, "K", 0)
    m = _build_mini_adjudicate_forced(tmp_path)
    t = pt.triage(m.label, repo=m.root)
    assert by_id(t, 51, ch="chZ")["bucket"] == 2
    assert by_id(t, 52, ch="chZ")["bucket"] == 2
    assert t["meta"]["forced_adjudicate_count"] == 2
    assert t["meta"]["forced_total_count"] == 2
    assert t["meta"]["forced_total_over_budget"] is True


def test_adjudicate_queue_md_marks_unchanged_row_not_empty_looking(tmp_path, monkeypatch):
    """queue.md 呈现要求：零改动+请裁的行不能看着像空记录——id 级"进入
    队列原因"要显式写"未改动"，且该通道那一行末尾要有明确的"未改动"标记。
    52（有改动+请裁）走"显式请裁"一档、不应被打上"未改动"标记，用来确认
    这条呈现规则不是无差别地扣在所有 forced_adjudicate 行头上。"""
    monkeypatch.setitem(pt.CFG, "K", 150)
    m = _build_mini_adjudicate_forced(tmp_path)
    pt.triage(m.label, repo=m.root)
    text = (m.d / "queue.md").read_text(encoding="utf-8")

    import re
    block51 = re.search(r"## id 51\n.*?(?=\n## id |\Z)", text, re.S).group(0)
    assert "请裁·未改动" in block51
    assert "不是空记录" in block51
    assert "[本通道未改动，与 opus 逐字相同]" in block51

    block52 = re.search(r"## id 52\n.*?(?=\n## id |\Z)", text, re.S).group(0)
    assert "显式请裁" in block52
    assert "未改动" not in block52.split("进入队列原因")[1].split("\n")[0]


def test_meta_forced_adjudicate_fields_present(tmp_path, monkeypatch):
    monkeypatch.setitem(pt.CFG, "K", 150)
    m = _build_mini_adjudicate_forced(tmp_path)
    t = pt.triage(m.label, repo=m.root)
    assert t["meta"]["forced_adjudicate_count"] == 2   # id 51、52
    assert t["meta"]["forced_soft_count"] == 0          # 本夹具无软锁 id
    assert t["meta"]["forced_total_count"] == 2
    assert t["meta"]["forced_total_over_budget"] is False


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

    # jp 刻意写得比 zh 长：现实语料里日文（含假名）几乎总比中译占宽，
    # `check_batch` 的 W3 判据（zh 显示宽 > jp 显示宽 ×1.15）因此在真实
    # SEG-1 的 1996 行现行译文上只命中 5 行（0.3%）。初版夹具的 zh 反比
    # jp 长，会让**每一条**小改候选都挂上 W3 warn——而 W3 现在参与自动
    # 清关前置（最终评审 C2），那样整个夹具就一个 autoclear 候选都产不出，
    # 测不到它本来要测的 K 帽不变量。这是夹具脱离现实，不是判据过严。
    jp = {i: f"これは第{i}番目のテスト用サンプル原文であります。" for i in ids}
    opus = {i: f"这是第{i}句的现行译文。" for i in ids}
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
    (repo / "glossary" / "polish.md").write_text("# 语感细则", encoding="utf-8")
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


# ---- 最终评审 C1：陈旧 gates（id 不在 checked_ids 里）＝没有证据，不许免检 ----

def test_stale_gates_id_not_checked_blocks_autoclear(mini):
    """gate 跑过之后又入仓了新候选、**没重跑 gate** → 该 id 不许自动清关。

    评审实测的原始复现：b1 入仓后跑 gate，再入仓 b2（`【アヤノ】`→`【ユカリ】`
    的真 hard 违规，edit=3 小改），不重跑 gate 就 triage —— 新 id 在旧
    `gates.json` 里查无此人，初版据此判"干净"→ `autoclear=True`，
    `polish_commit` dry-run 已把它列入写入计划；事后补跑 gate 才报 R2b hard。
    `load_gates` 在**文件**层已经做到"没有证据就不放行"，id 层此前没有同等
    待遇。这里用 `drop_from_checked` 精确重建那个状态。
    """
    mini.enable_autoclear("chA")
    assert by_id(pt.triage(LABEL, repo=mini.root), 14)["autoclear"]  # 前提：本来能清关
    mini.drop_from_checked(14)
    assert not by_id(pt.triage(LABEL, repo=mini.root), 14)["autoclear"]


def test_stale_gates_end_to_end_new_candidate_not_autocleared(mini):
    """端到端版本（不手工改 gates 文件）：跑完 gate 之后再 append 一条**新
    id** 的候选，不重跑 gate —— 那个 id 必须进人裁，不得自动清关。"""
    # 夹具里 id 15 另有一条 amplify 候选，而 amplify 恒不 eligible，会通过
    # "id 级 all-or-nothing" 把整个 id 15 拦下——那是另一条规则，会掩盖本
    # 测试要验的东西。先把 amplify 通道整个撤掉，让 id 15 成为纯 chA 的 id。
    (mini.d / "candidates.amplify.jsonl").unlink()
    (mini.d / "gates.amplify.json").unlink()
    mini.enable_autoclear("chA")
    pcheck.gate(LABEL, "chA", repo=mini.root)          # 此刻 checked_ids 不含 15
    append_jsonl(mini.d / "candidates.chA.jsonl", [{
        "id": 15, "channel": "chA", "batch": 2, "prompt_hash": "hash-2",
        "jp_hash": "x", "opus_hash": "x", "zh": "千秋抬起头看向黑板上的时钟。",
        "score": 95, "note": "", "adjudicate": False,
        "jp_tail": jp_tail(JP[15]), "ts": "t-late",
    }])
    assert not by_id(pt.triage(LABEL, repo=mini.root), 15, ch="chA")["autoclear"]
    # 补跑 gate（把它纳入 checked_ids）之后才恢复资格——证明拦的是"没查过"，
    # 不是把这个 id 永久打死。
    pcheck.gate(LABEL, "chA", repo=mini.root)
    assert by_id(pt.triage(LABEL, repo=mini.root), 15, ch="chA")["autoclear"]


def test_legacy_gates_format_blocks_autoclear_and_warns(mini, capsys):
    """旧格式（无 `checked_ids` 的裸字典）→ 一律不许自动清关 + stderr 播报。

    把旧文件当成"全部检查过"就等于把 C1 这个洞原样保留；当成"空集"则最坏
    情况只是多排一轮人裁，且操作者会被告知去重跑 gate。"""
    mini.enable_autoclear("chA")
    p = mini.d / "gates.chA.json"
    new = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(dumps(new["findings"]), encoding="utf-8")   # 退回旧格式
    t = pt.triage(LABEL, repo=mini.root)
    assert not by_id(t, 14)["autoclear"]
    err = capsys.readouterr().err
    assert "旧格式" in err and "polish_check" in err


# ---- 最终评审 C2 后半：W3 行宽 warn 参与自动清关前置 ----

def test_w3_warn_blocks_autoclear(mini):
    """W3（显示行宽超限）是唯一一条对应**真实游戏内故障**的 warn——中文比
    日文占宽，溢出玩家一眼看得见。它此前在整条 P4 流水线上零消费者（连同
    `gates.json` 里其余 warn），于是"会溢出的小改"照样免检入库。"""
    mini.enable_autoclear("chA")
    assert by_id(pt.triage(LABEL, repo=mini.root), 14)["autoclear"]
    mini.make_gate_warn(14, "W3")
    assert not by_id(pt.triage(LABEL, repo=mini.root), 14)["autoclear"]


@pytest.mark.parametrize("rule", ["W1", "W2", "W4"])
def test_other_warns_do_not_block_autoclear(mini, rule):
    """W1/W2/W4 保持不阻断——判据过宽会用伪报淹没真信号。

    W1 是 jp↔zh 断行数差的粗略提示（真正的控制码保全由 P4-CTL 硬规则接管）、
    W2 是术语提示、W4 在候选级根本不跑（挪到 `polish_check.w4_full` 的清关后
    全段复检）。把它们一并当成阻断条件会让自动清关这条通道形同虚设，而它们
    各自都有更合适的归口。这条参数化测试就是那个取舍的落盘证据。
    """
    mini.enable_autoclear("chA")
    mini.make_gate_warn(14, rule)
    assert by_id(pt.triage(LABEL, repo=mini.root), 14)["autoclear"]


# --- P5 契约 v2：alts 渲染与 noop 透传 ---

def test_queue_md_renders_alts(mini):
    """带 alts 的候选进队列时，queue.md 在主候选下缩进列出编号备选
    （编号即 polish_commit 采纳动作 adopt_alt:N 的 N）。"""
    append_jsonl(mini.d / "candidates.chA.jsonl", [{
        "id": 12, "channel": "chA", "batch": 1, "prompt_hash": "hash-1",
        "jp_hash": "x", "opus_hash": "x", "zh": "改后的主候选",
        "score": 55, "note": "两可", "adjudicate": True,
        "jp_tail": jp_tail(JP[12]), "ts": "t2",
        "alts": [{"zh": "备选甲", "note": "更口语"}, {"zh": "备选乙", "note": ""}],
    }])
    pt.triage(LABEL, repo=mini.root)
    q = (mini.d / "queue.md").read_text(encoding="utf-8")
    assert "备选1：备选甲（批注：更口语）" in q
    assert "备选2：备选乙" in q


def test_triage_rows_carry_noop(mini):
    """candidates 的 noop 标记透传进 triage 返回行（评估侧消费）；
    旧候选无该键时默认 False。"""
    append_jsonl(mini.d / "candidates.chA.jsonl", [{
        "id": 14, "channel": "chA", "batch": 1, "prompt_hash": "hash-1",
        "jp_hash": "x", "opus_hash": "x", "zh": OPUS[14],
        "score": 95, "note": "", "adjudicate": False,
        "jp_tail": jp_tail(JP[14]), "ts": "t2", "noop": True,
    }])
    r = pt.triage(LABEL, repo=mini.root)
    row14 = next(x for x in r["rows"] if x["id"] == 14 and x["channel"] == "chA")
    assert row14["noop"] is True
    # id 11 是真实改动行（大改），ingest 判 noop=False；id 10 照抄行由
    # ingest 判 noop=True（T46 行为，顺带在此回归覆盖）。
    row11 = next(x for x in r["rows"] if x["id"] == 11 and x["channel"] == "chA")
    assert row11["noop"] is False
    row10 = next(x for x in r["rows"] if x["id"] == 10 and x["channel"] == "chA")
    assert row10["noop"] is True


def test_queue_md_warns_on_lane_drift(mini):
    """queue.md 必须在做决定的地方警示漂移行，并给出车道最新文本。"""
    (mini.d / "lane_drift.json").write_text(dumps({
        "lane": "x", "drifted": 1,
        "findings": [{"id": 11, "frozen_zh": OPUS[11],
                      "current_zh": "冻结之后车道改成的新译文", "proposals": []}],
    }), encoding="utf-8")
    pt.triage(LABEL, repo=mini.root)
    q = (mini.d / "queue.md").read_text(encoding="utf-8")
    assert "冻结后车道已更新" in q
    assert "冻结之后车道改成的新译文" in q
    assert "个 id 在冻结之后车道又更新过" in q


def test_queue_md_no_drift_section_when_file_absent(mini):
    pt.triage(LABEL, repo=mini.root)
    q = (mini.d / "queue.md").read_text(encoding="utf-8")
    assert "冻结后车道已更新" not in q
