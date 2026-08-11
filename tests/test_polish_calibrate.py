"""tools/polish_calibrate.py：通道准入小考单测。

夹具复用真实上游模块（与 `tests/test_polish_triage.py` 同一策略）：
`polish_setup.setup()` 造该 SEG 的 `frozen/` + `manifest.json`（校准抽样的
种子来源）。全局「opus 车道」金标池落在 `pilot/lanes/opus/data/`——与
`polish_setup.setup()` 的 `opus_data` 参数指向**同一个目录**，这不是偷懒，
是生产环境的实况：那个目录本来就同时承担"该 SEG 的翻译来源"与"整个项目
的裁决历史"两个角色。

金标 id 1..10 里，id 5 刻意设计成三轮修订
（`recall`→`review`→`polish`，现行值来自最后一条**非** review/recall 理由
的 `polish` patch）——这是钉死"金标现行值 = resolve() 之后的最新值，不是
最后一条 reason∈{review,recall} 的行"这条规则的关键夹具，直接对应
brief 追加的变异自检③。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_calibrate as pc
from tools import polish_setup as ps
from tools import polish_triage as pt
from tools.pipelib import dumps, read_jsonl, write_jsonl

LABEL = "segCalib"

GOLD_JP = {i: f"金标第{i}句原文。" for i in range(1, 11)}
GOLD_CUR_ZH = {
    1: "金标现行译文一。", 2: "金标现行译文二。", 3: "金标现行译文三。",
    4: "金标现行译文四。",
    5: "金标现行译文五——最终版（polish 覆盖）。",
    6: "金标现行译文六。", 7: "金标现行译文七。", 8: "金标现行译文八。",
    9: "金标现行译文九。",
    10: "长句" * 25,  # 50 字长句：唯一一条 autoclear_limit>minor_edit 的
                        # 金标，专门留给三档分类测试撑开 minor 区间。
}
GOLD_STALE_ZH_5 = "金标译文五——早期 review 版（已被推翻，不该被当成现行值）。"
GOLD_EARLIEST_ZH_5 = "金标译文五——最早 recall 版。"

NORM_IDS = list(range(21, 31))   # 10 个陪考句，取自该 SEG 自己的 frozen source
LOCKED_ID = 31                    # 锚点锁定 id，验证陪考句排除锁定 id


def _build_mini(tmp_path):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    all_local_ids = NORM_IDS + [LOCKED_ID]

    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": LABEL, "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": len(all_local_ids), "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": all_local_ids, "seqs": [1],
         "jp_chars": len(all_local_ids), "chapter": "s2s", "cut_reason": "budget"},
    ])

    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([
        {"chapter": "global", "items": [
            {"id": LOCKED_ID, "jp": f"第{LOCKED_ID}句", "zh": "锁定定译", "recall": "测试锚点"},
        ]},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 语感细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

    # opus 车道 data：同时是 (a) polish_setup.setup() 的 opus_data 来源
    # （提供陪考 id 的 jp/现行译文），和 (b) 本模块 _gold_pool() 的金标历史
    # 来源（金标 id 的 patches）——生产环境正是同一目录，见模块 docstring。
    opus_data = repo / "pilot" / "lanes" / "opus" / "data"
    (opus_data / "notes").mkdir(parents=True)

    ledger_rows = (
        [{"id": i, "jp": GOLD_JP[i], "voice": "NONVOICE", "file": "f", "func": "f",
          "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
         for i in range(1, 11)]
        + [{"id": i, "jp": f"第{i}句原文", "voice": "NONVOICE", "file": "f", "func": "f",
            "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
           for i in all_local_ids]
    )
    write_jsonl(opus_data / "ledger.jsonl", ledger_rows)

    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": ("锁定定译" if i == LOCKED_ID else f"陪考初译{i}"),
         "batch": 1, "backend": "cc", "model": "m", "ctx": "x", "glossary_v": 1, "ts": "t"}
        for i in all_local_ids
    ])

    write_jsonl(opus_data / "patches.jsonl", [
        {"id": 1, "zh": GOLD_CUR_ZH[1], "reason": "review", "glossary_v": 1, "ts": "t1"},
        {"id": 2, "zh": GOLD_CUR_ZH[2], "reason": "recall", "glossary_v": 1, "ts": "t1"},
        {"id": 3, "zh": GOLD_CUR_ZH[3], "reason": "review", "glossary_v": 1, "ts": "t1"},
        {"id": 4, "zh": GOLD_CUR_ZH[4], "reason": "recall", "glossary_v": 1, "ts": "t1"},
        # id 5：三轮修订。现行值必须取最后一条（reason=polish，非金标理由），
        # 不能取中间那条 reason=review 的行（GOLD_STALE_ZH_5）。
        {"id": 5, "zh": GOLD_EARLIEST_ZH_5, "reason": "recall", "glossary_v": 1, "ts": "t1"},
        {"id": 5, "zh": GOLD_STALE_ZH_5, "reason": "review", "glossary_v": 2, "ts": "t2"},
        {"id": 5, "zh": GOLD_CUR_ZH[5], "reason": "polish", "glossary_v": 3, "ts": "t3"},
        {"id": 6, "zh": GOLD_CUR_ZH[6], "reason": "review", "glossary_v": 1, "ts": "t1"},
        {"id": 7, "zh": GOLD_CUR_ZH[7], "reason": "recall", "glossary_v": 1, "ts": "t1"},
        {"id": 8, "zh": GOLD_CUR_ZH[8], "reason": "review", "glossary_v": 1, "ts": "t1"},
        {"id": 9, "zh": GOLD_CUR_ZH[9], "reason": "recall", "glossary_v": 1, "ts": "t1"},
        {"id": 10, "zh": GOLD_CUR_ZH[10], "reason": "review", "glossary_v": 1, "ts": "t1"},
    ])

    d = ps.setup(LABEL, opus_data, repo=repo)
    return SimpleNamespace(root=repo, d=d, label=LABEL)


@pytest.fixture
def mini(tmp_path):
    return _build_mini(tmp_path)


def _write_raw(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(dumps(r) for r in rows) + "\n", encoding="utf-8")


# ---- brief Step 1 核心断言：make() 产出 + truth 绝不进 batch 内容 ----

def test_make_produces_mixed_batch_and_truth(mini):
    p = pc.make(LABEL, n_gold=10, n_norm=10, repo=mini.root)
    assert p == mini.d / "calib" / f"{LABEL}.batch.jsonl"

    rows = read_jsonl(p)
    assert len(rows) == 20
    ids = {r["id"] for r in rows}
    assert ids == set(range(1, 11)) | set(NORM_IDS)
    assert LOCKED_ID not in ids  # 锁定 id 绝不进正文行，同生产批规则

    truth_path = mini.d / "calib" / f"{LABEL}.truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    assert {int(k) for k in truth} == ids
    assert sum(1 for v in truth.values() if v["is_gold"]) == 10
    assert sum(1 for v in truth.values() if not v["is_gold"]) == 10

    # batch.jsonl 每行本身不该带 is_gold 之类的判卷信息
    for r in rows:
        assert "is_gold" not in r
        assert set(r) == {"id", "batch", "jp", "opus_zh"}

    # 更硬的检查：直接扫 batch 文件的原始字节，"truth"/"is_gold"/"gold" 这类
    # 判卷词汇一个都不该出现（不是靠自己写代码时的自我保证，是真的读文件）。
    raw_text = p.read_text(encoding="utf-8")
    for leak_word in ("is_gold", "truth", "gold"):
        assert leak_word not in raw_text.lower(), f"batch 文件疑似泄露判卷信息：{leak_word!r}"


def test_make_is_deterministic(mini):
    p1 = pc.make(LABEL, repo=mini.root)
    rows1 = read_jsonl(p1)
    truth1 = json.loads((mini.d / "calib" / f"{LABEL}.truth.json").read_text(encoding="utf-8"))

    p2 = pc.make(LABEL, repo=mini.root)
    rows2 = read_jsonl(p2)
    truth2 = json.loads((mini.d / "calib" / f"{LABEL}.truth.json").read_text(encoding="utf-8"))

    assert rows1 == rows2
    assert truth1 == truth2


def test_make_raises_when_pool_too_small(mini):
    with pytest.raises(ValueError):
        pc.make(LABEL, n_gold=999, n_norm=10, repo=mini.root)
    with pytest.raises(ValueError):
        pc.make(LABEL, n_gold=10, n_norm=999, repo=mini.root)


# ---- 变异自检③（brief 追加）：金标现行值必须来自 resolve()，不是某一条
#      reason∈{review,recall} 的 patch 行本身 ----

def test_gold_current_text_is_resolved_not_stale_review_row(mini):
    rows = read_jsonl(pc.make(LABEL, repo=mini.root))
    row5 = next(r for r in rows if r["id"] == 5)
    assert row5["opus_zh"] == GOLD_CUR_ZH[5]
    assert row5["opus_zh"] != GOLD_STALE_ZH_5
    assert row5["opus_zh"] != GOLD_EARLIEST_ZH_5


# ---- brief Step 1 核心断言：score() 三档 + pass/fail 阈值 ----

def test_score_all_unchanged_passes(mini):
    pc.make(LABEL, repo=mini.root)
    raw = mini.d / "raw" / "chTest" / "calib.out"
    _write_raw(raw, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:], "zh": GOLD_CUR_ZH[i],
         "score": 90, "note": "", "adjudicate": False}
        for i in range(1, 11)
    ])
    result = pc.score(LABEL, raw, "chTest", repo=mini.root)
    assert result["gold_unchanged"] == 10
    assert result["gold_minor"] == 0
    assert result["gold_substantive"] == 0
    assert result["pass"] is True
    assert "known_bias" in result and "非随机子集" in result["known_bias"]

    state = json.loads((mini.d / "channel_state.json").read_text(encoding="utf-8"))
    assert state == {"chTest": {"autoclear": True}}


def test_score_4_of_10_substantive_fails(mini):
    """brief 原文场景：金标 10 句中 4 句实质改写 → pass=False，channel_state
    关闭该通道自动清关权。"""
    pc.make(LABEL, repo=mini.root)
    garbled = "彻底改写成一句和原意毫无关系的新句子完全不同。"
    raw = mini.d / "raw" / "chBad" / "calib.out"
    _write_raw(raw, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:],
         "zh": (garbled if i in (1, 2, 3, 4) else GOLD_CUR_ZH[i]),
         "score": 90, "note": "", "adjudicate": False}
        for i in range(1, 11)
    ])
    result = pc.score(LABEL, raw, "chBad", repo=mini.root)
    assert result["gold_substantive"] == 4
    assert result["gold_unchanged"] == 6
    assert result["pass"] is False

    state = json.loads((mini.d / "channel_state.json").read_text(encoding="utf-8"))
    assert state["chBad"]["autoclear"] is False


def test_score_missing_gold_output_counts_as_substantive(mini):
    """模型漏输出某个金标 id（截断/跳过）不能悄悄不计分——按最坏情形算。"""
    pc.make(LABEL, repo=mini.root)
    raw = mini.d / "raw" / "chMiss" / "calib.out"
    _write_raw(raw, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:], "zh": GOLD_CUR_ZH[i],
         "score": 90, "note": "", "adjudicate": False}
        for i in range(2, 11)  # 漏掉 id=1
    ])
    result = pc.score(LABEL, raw, "chMiss", repo=mini.root)
    assert result["gold_substantive"] == 1
    assert result["gold_unchanged"] == 9


# ---- 2026-08-07 缺陷修复：pass 判定改用「静默推翻裁决」而不是改动幅度 ----

def test_changed_with_adjudicate_does_not_count_as_silent_override(mini):
    """通道把 3/10 条金标都改了，但全部显式 `adjudicate=true`——"改了但
    主动说了"不该被当成失败信号，`changed_silent` 必须是 0，pass 保持
    True（即使 `gold_substantive`/`gold_minor` 不是 0，那两个字段现在只是
    幅度展示，不再直接决定 pass）。"""
    pc.make(LABEL, repo=mini.root)
    raw = mini.d / "raw" / "chHonest" / "calib.out"
    _write_raw(raw, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:],
         "zh": (GOLD_CUR_ZH[i][:-1] + "改" if i in (1, 2, 3) else GOLD_CUR_ZH[i]),
         "score": 90, "note": "语感细则第1条更顺口" if i in (1, 2, 3) else "",
         "adjudicate": i in (1, 2, 3)}
        for i in range(1, 11)
    ])
    result = pc.score(LABEL, raw, "chHonest", repo=mini.root)
    assert result["changed_adjudicated"] == 3
    assert result["changed_silent"] == 0
    assert result["silent_override_rate"] == 0.0
    assert result["pass"] is True


def test_silent_override_fails_even_a_single_line(mini):
    """核心场景（实测复现的失败模式）：只**1** 条金标被静默改动（未
    `adjudicate`），其余 9 条逐字未动——旧判据（只看 substantive 占比）
    会认为这是"1/10 substantive 或更少，远低于 0.30 阈值"从而 pass=True；
    新判据必须因为这 1 条"静默推翻裁决"而 pass=False。这是本次修复要
    确保"该响的时候真的响"的核心测试，也是"改动未请裁不影响 pass"这个
    变异的直接对照。"""
    pc.make(LABEL, repo=mini.root)
    raw = mini.d / "raw" / "chSilent" / "calib.out"
    _write_raw(raw, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:],
         "zh": (GOLD_CUR_ZH[i][:-1] + "改" if i == 1 else GOLD_CUR_ZH[i]),
         "score": 90, "note": "", "adjudicate": False}
        for i in range(1, 11)
    ])
    result = pc.score(LABEL, raw, "chSilent", repo=mini.root)
    assert result["changed_silent"] == 1
    assert result["changed_adjudicated"] == 0
    assert result["silent_override_rate"] == 0.1
    assert result["pass"] is False   # 0.1 不小于阈值 0.10

    state = json.loads((mini.d / "channel_state.json").read_text(encoding="utf-8"))
    assert state["chSilent"]["autoclear"] is False


def test_mixed_channel_matches_real_incident_id5684_shape(mini):
    """按实测事故复现的比例形态（非字面复刻）：10 条金标里 2 条静默改动、
    1 条请裁改动、7 条未动——两条静默覆盖必须让 pass=False（fable-wf/
    ds-flash 实测都是这个数量级的静默覆盖比例）。"""
    pc.make(LABEL, repo=mini.root)
    raw = mini.d / "raw" / "chMixed" / "calib.out"
    rows = []
    for i in range(1, 11):
        if i in (1, 2):      # 静默改动
            rows.append({"id": i, "jp_tail": GOLD_JP[i][-8:],
                         "zh": GOLD_CUR_ZH[i][:-1] + "改", "score": 90,
                         "note": "", "adjudicate": False})
        elif i == 3:         # 请裁改动
            rows.append({"id": i, "jp_tail": GOLD_JP[i][-8:],
                         "zh": GOLD_CUR_ZH[i][:-1] + "问", "score": 90,
                         "note": "疑似原句可以更顺口，但不确定", "adjudicate": True})
        else:
            rows.append({"id": i, "jp_tail": GOLD_JP[i][-8:], "zh": GOLD_CUR_ZH[i],
                         "score": 90, "note": "", "adjudicate": False})
    _write_raw(raw, rows)
    result = pc.score(LABEL, raw, "chMixed", repo=mini.root)
    assert result["changed_silent"] == 2
    assert result["changed_adjudicated"] == 1
    assert result["gold_unchanged"] == 7
    assert result["pass"] is False


def test_details_field_reports_per_gold_row(mini):
    """结果里的逐条明细：操作者不用自己写脚本核算就能看清每条金标发生
    了什么（这次修复的直接诱因就是操作者自己写脚本核算才发现报告撒谎）。"""
    pc.make(LABEL, repo=mini.root)
    raw = mini.d / "raw" / "chDetail" / "calib.out"
    _write_raw(raw, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:],
         "zh": (GOLD_CUR_ZH[i][:-1] + "改" if i == 1 else GOLD_CUR_ZH[i]),
         "score": 90, "note": "", "adjudicate": (i == 1)}
        for i in range(2, 11)
    ] + [{"id": 1, "jp_tail": GOLD_JP[1][-8:], "zh": GOLD_CUR_ZH[1][:-1] + "改",
          "score": 90, "note": "试着改顺口一点", "adjudicate": True}])
    result = pc.score(LABEL, raw, "chDetail", repo=mini.root)
    assert len(result["details"]) == 10
    d1 = next(d for d in result["details"] if d["id"] == 1)
    assert d1["edit"] == 1 and d1["tier"] == "minor"
    assert d1["adjudicate"] is True
    assert d1["silent_override"] is False
    assert d1["missing_output"] is False
    d2 = next(d for d in result["details"] if d["id"] == 2)
    assert d2["edit"] == 0 and d2["tier"] == "unchanged"
    assert d2["silent_override"] is False


def test_missing_gold_output_marked_missing_and_silent_in_details(mini):
    pc.make(LABEL, repo=mini.root)
    raw = mini.d / "raw" / "chMiss2" / "calib.out"
    _write_raw(raw, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:], "zh": GOLD_CUR_ZH[i],
         "score": 90, "note": "", "adjudicate": False}
        for i in range(2, 11)
    ])
    result = pc.score(LABEL, raw, "chMiss2", repo=mini.root)
    d1 = next(d for d in result["details"] if d["id"] == 1)
    assert d1["missing_output"] is True
    assert d1["silent_override"] is True   # 漏交卷视为最坏情形，不给"已请裁"的信任状
    assert d1["adjudicate"] is False
    assert result["changed_silent"] == 1


def test_score_preserves_other_channels_in_state(mini):
    """score() 只更新自己这个 channel 的键，不覆盖文件里其它通道已有的条目。"""
    pc.make(LABEL, repo=mini.root)
    state_path = mini.d / "channel_state.json"
    state_path.write_text(dumps({"otherChannel": {"autoclear": True}}), encoding="utf-8")

    raw = mini.d / "raw" / "chTest" / "calib.out"
    _write_raw(raw, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:], "zh": GOLD_CUR_ZH[i],
         "score": 90, "note": "", "adjudicate": False}
        for i in range(1, 11)
    ])
    pc.score(LABEL, raw, "chTest", repo=mini.root)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["otherChannel"] == {"autoclear": True}
    assert state["chTest"] == {"autoclear": True}


# ---- 变异自检④（brief 追加）：channel_state.json 的结构必须是
#      Task 7 `polish_triage._channel_autoclear_power()` 认识的形状 ----

def test_channel_state_contract_matches_polish_triage_reader(mini):
    pc.make(LABEL, repo=mini.root)
    raw_ok = mini.d / "raw" / "chOk" / "calib.out"
    _write_raw(raw_ok, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:], "zh": GOLD_CUR_ZH[i],
         "score": 90, "note": "", "adjudicate": False}
        for i in range(1, 11)
    ])
    pc.score(LABEL, raw_ok, "chOk", repo=mini.root)

    garbled = "彻底改写成一句和原意毫无关系的新句子完全不同。"
    raw_bad = mini.d / "raw" / "chBad2" / "calib.out"
    _write_raw(raw_bad, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:],
         "zh": (garbled if i in (1, 2, 3, 4) else GOLD_CUR_ZH[i]),
         "score": 90, "note": "", "adjudicate": False}
        for i in range(1, 11)
    ])
    pc.score(LABEL, raw_bad, "chBad2", repo=mini.root)

    state = json.loads((mini.d / "channel_state.json").read_text(encoding="utf-8"))
    # 不是自己重新写一套解析逻辑自我验证——直接调用 Task 7 的真实读取函数。
    assert pt._channel_autoclear_power("chOk", state) is True
    assert pt._channel_autoclear_power("chBad2", state) is False
    # 从未考过试的通道：Task 7 的保守缺省必须是关闭。
    assert pt._channel_autoclear_power("chNeverCalibrated", state) is False


# ---- 2026-08-07 缺陷修复：三档分类必须只用 minor_edit 一个阈值，且
#      gold_unchanged 必须只计 edit==0（不再把"轻微改动"混进"未改动"）----

def test_gold_unchanged_only_counts_exact_match_not_edit_le_4(mini):
    """核心回归锁：这是 SEG-1 首次真实小考暴露的那个 bug 本身——`edit=1`
    的改写（1 个字）必须落进 `gold_minor`，绝不能被 `gold_unchanged` 吃掉。
    旧实现 `edit <= minor_edit` 当"未改动"正是这里会转红的地方。"""
    pc.make(LABEL, repo=mini.root)
    ref1 = GOLD_CUR_ZH[1]
    cand1 = ref1[:-1] + "改"   # 尾部换 1 字，edit_distance=1

    raw = mini.d / "raw" / "chOneEdit" / "calib.out"
    rows = [{"id": i, "jp_tail": GOLD_JP[i][-8:],
             "zh": (cand1 if i == 1 else GOLD_CUR_ZH[i]),
             "score": 90, "note": "", "adjudicate": (i == 1)}
            for i in range(1, 11)]
    _write_raw(raw, rows)

    result = pc.score(LABEL, raw, "chOneEdit", repo=mini.root)
    assert result["gold_unchanged"] == 9
    assert result["gold_minor"] == 1          # 不是 gold_unchanged=10
    assert result["gold_substantive"] == 0
    detail1 = next(d for d in result["details"] if d["id"] == 1)
    assert detail1["edit"] == 1 and detail1["tier"] == "minor"


def test_tier_boundary_uses_only_minor_edit_threshold(mini):
    """三档边界现在只看 `minor_edit`（=4）一个阈值，不再牵涉
    `autoclear_limit`：edit==4 落 minor，edit==5 落 substantive——即使
    id=10 的现行译文很长（`autoclear_limit(ref10)` 远大于 4），也不该
    再把它当成 minor/substantive 的分界。"""
    pc.make(LABEL, repo=mini.root)
    ref10 = GOLD_CUR_ZH[10]
    cand_edit4 = ref10[:-4] + "甲乙丙丁"    # edit=4
    cand_edit5 = ref10[:-5] + "甲乙丙丁戊"  # edit=5

    def _run(cand10):
        raw = mini.d / "raw" / "chBoundary" / "calib.out"
        rows = [{"id": i, "jp_tail": GOLD_JP[i][-8:], "zh": GOLD_CUR_ZH[i],
                 "score": 90, "note": "", "adjudicate": False}
                for i in range(1, 10)]
        rows.append({"id": 10, "jp_tail": GOLD_JP[10][-8:], "zh": cand10,
                     "score": 90, "note": "", "adjudicate": False})
        _write_raw(raw, rows)
        return pc.score(LABEL, raw, "chBoundary", repo=mini.root)

    r4 = _run(cand_edit4)
    assert r4["gold_minor"] == 1 and r4["gold_substantive"] == 0

    r5 = _run(cand_edit5)
    assert r5["gold_minor"] == 0 and r5["gold_substantive"] == 1


# ---- CLI 冒烟 ----

def test_cli_make_and_score(mini, capsys):
    rc = pc.main(["--seg", LABEL, "--make", "--repo", str(mini.root)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(mini.d / "calib" / f"{LABEL}.batch.jsonl")

    raw = mini.d / "raw" / "chCli" / "calib.out"
    _write_raw(raw, [
        {"id": i, "jp_tail": GOLD_JP[i][-8:], "zh": GOLD_CUR_ZH[i],
         "score": 90, "note": "", "adjudicate": False}
        for i in range(1, 11)
    ])
    rc = pc.main(["--seg", LABEL, "--score", "--channel", "chCli",
                  "--raw", str(raw), "--repo", str(mini.root)])
    assert rc == 0
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed["pass"] is True
