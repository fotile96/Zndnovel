"""tools/polish_amplify.py：裁决意图归纳 + 放大扫描装配的单测。

夹具复用真实上游模块（与 test_polish_triage.py/test_polish_commit.py 同一
惯例）：`polish_setup.setup()` 造 frozen/、`polish_ingest.ingest()` 灌真
候选、`polish_check.gate()` 跑真机械闸、`polish_triage.triage()` 产出真
`triage.json`——只有 `decisions.jsonl`（人工裁决面）是本模块手写的固件
（同 Task 8 的既定理由：当前流程里它是人工在 queue.md 上裁决后手工
append 的，没有代码生成它）。

单 SEG "segAmp"，两批（batch1: ids 10/11/12/13/14/15，batch2: id 20），
通道 "chA"：
  - 10：anchors.yaml 命中的锚点 id → 锁定，桶 0（不出稿）。
  - 11：候选与 opus 逐字相同 → 桶 1（零改动）。
  - 12：大改写（edit=26，远超 autoclear_limit=4）→ K=3 时排位第一 → 桶 2。
    夹具默认给它一条 decisions.jsonl 记录：verdict=edit，reason_code=语序。
  - 13：中改（edit=7）→ K=3 时排位第三 → 桶 2。
    decisions 记录：verdict=keep_opus，reason_code=过度归化。
  - 14：小改（edit=2 ≤ autoclear_limit=4）→ 开 chA 自动清关权 + sample_rate
    强制压到 0（确定性：sampled 恒 False）→ autoclear 桶 3（"已清关但不
    是 opus"这一支）。
  - 15：小改但仍超过 autoclear_limit（edit=5 > 4，实测见下方脚本核实，
    不是拍脑袋数字）→ 进入排位竞争，K=3 时排位第四（编辑距离最小）→
    落到桶 3（"真实改动但因配额落选，默认仍是 opus"这一支）——这是
    本任务变异自检③要抓的"漏掉桶 3 全文"典型案例。
  - 20（batch2）：中改（edit=12）→ K=3 时排位第二 → 桶 2。
    decisions 记录：verdict=adopt，reason_code=语序（与 12 同码，凑成
    "3 条 decisions，两码"）。

`K=3`、`channel_state.chA.autoclear=True`、`sample_rate=0.0` 均在 mini 固件
内通过 monkeypatch `tools.polishlib.CFG` 临时改写、`finally` 里还原——同
`test_polish_triage.py`/`test_polish_commit.py` 的既定手法。
"""
import hashlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_amplify as amp
from tools import polish_check as pcheck
from tools import polish_ingest as pi
from tools import polish_setup as ps
from tools import polish_triage as pt
from tools.pipelib import dumps, read_jsonl, write_jsonl
from tools.polishlib import jp_tail

LABEL = "segAmp"

JP = {
    10: "アヤノは静かに微笑んだ。",
    11: "彩野は静かにうなずいた。",
    12: "教室の時計が動いていることに気づいた。",
    13: "廊下の奥から足音が聞こえた。",
    14: "ユカリは眼鏡を押し上げた。",
    15: "彩野はいつもの笑顔を見せた。",
    20: "千秋は黒板の時計を見上げた。",
}
OPUS = {
    10: "彩野静静地微笑着。",
    11: "彩野静静地点了点头。",
    12: "我注意到教室里的时钟还在走动。",
    13: "走廊尽头传来了脚步声。",
    14: "由加里推了推眼镜。",
    15: "彩野露出了熟悉的微笑。",
    20: "千秋抬头看向黑板上的时钟。",
}
CAND_CHA = {
    11: OPUS[11],                                                     # 零改动 -> 桶1
    12: "教室里弥漫着令人窒息的寂静，仿佛连时间都为之停滞了一般。",       # 大改 edit=26 -> 桶2
    13: "走廊尽头忽然传来一阵奇怪的脚步声。",                            # 中改 edit=7  -> 桶2
    14: "由加里扶了扶眼镜。",                                           # 小改 edit=2  -> autoclear 桶3
    15: "彩野忽然浮现出了熟悉的微笑呢。",                               # 小改 edit=5  -> 排位落选桶3
    20: "千秋抬起头，望向了那口停摆在原地的挂钟。",                       # 中改 edit=12 -> 桶2
}

EDIT_TS_12 = "2026-08-01T00:00:00+00:00"
KEEP_TS_13 = "2026-08-01T00:05:00+00:00"
ADOPT_TS_20 = "2026-08-01T00:10:00+00:00"


def _build_mini(tmp_path, *, decisions=None):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids_b1 = [10, 11, 12, 13, 14, 15]
    ids_b2 = [20]
    all_ids = ids_b1 + ids_b2

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
            {"id": 10, "jp": JP[10], "zh": OPUS[10], "recall": "测试锚点"},
        ]},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 六条细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

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
        {"session": 1, "batches": [1, 2], "prompt_hash": "hash-1"},
    ]), encoding="utf-8")

    raw_cha = d / "raw" / "chA"
    raw_cha.mkdir(parents=True)
    lines_b1 = [dumps({"id": i, "jp_tail": jp_tail(JP[i]), "zh": CAND_CHA[i],
                        "score": 90, "note": "", "adjudicate": False})
                for i in (11, 12, 13, 14, 15)]
    (raw_cha / "b1.out").write_text("\n".join(lines_b1) + "\n", encoding="utf-8")
    lines_b2 = [dumps({"id": 20, "jp_tail": jp_tail(JP[20]), "zh": CAND_CHA[20],
                        "score": 90, "note": "", "adjudicate": False})]
    (raw_cha / "b2.out").write_text("\n".join(lines_b2) + "\n", encoding="utf-8")

    assert pi.ingest(LABEL, "chA", 1, repo=repo)["ok"]
    assert pi.ingest(LABEL, "chA", 2, repo=repo)["ok"]

    pcheck.gate(LABEL, "chA", repo=repo)

    p = d / "channel_state.json"
    p.write_text(dumps({"chA": {"autoclear": True}}), encoding="utf-8")

    import tools.polishlib as polishlib
    old_k, old_rate = polishlib.CFG["K"], polishlib.CFG["sample_rate"]
    polishlib.CFG["K"] = 3
    polishlib.CFG["sample_rate"] = 0.0
    try:
        pt.triage(LABEL, repo=repo)
    finally:
        polishlib.CFG["K"] = old_k
        polishlib.CFG["sample_rate"] = old_rate

    if decisions is None:
        decisions = [
            {"id": 12, "verdict": "edit", "chosen_channel": "chA",
             "edited_zh": "人工改写：教室弥漫着令人窒息的死寂，仿佛连时间都停了下来。",
             "reason_code": "语序", "ts": EDIT_TS_12},
            {"id": 13, "verdict": "keep_opus", "chosen_channel": "chA",
             "edited_zh": None, "reason_code": "过度归化", "ts": KEEP_TS_13},
            {"id": 20, "verdict": "adopt", "chosen_channel": "chA",
             "edited_zh": None, "reason_code": "语序", "ts": ADOPT_TS_20},
        ]
    write_jsonl(d / "decisions.jsonl", decisions)

    return SimpleNamespace(root=repo, d=d, label=LABEL)


@pytest.fixture
def mini(tmp_path):
    return _build_mini(tmp_path)


def _triage_bucket_ids(d, bucket):
    triage = json.loads((d / "triage.json").read_text(encoding="utf-8"))
    return {r["id"] for r in triage["rows"] if r["bucket"] == bucket}


# ---- 夹具自检：先确认桶分布符合设计意图，后面的测试才站得住脚 ----

def test_fixture_bucket_layout(mini):
    assert _triage_bucket_ids(mini.d, 1) == {11}
    assert _triage_bucket_ids(mini.d, 2) == {12, 13, 20}
    assert _triage_bucket_ids(mini.d, 3) == {14, 15}


# ---- brief Step 1：digest 含分布表与代表例 ----

def test_digest_distribution_table(mini):
    text = amp.digest(LABEL, repo=mini.root)
    assert "| 语序 | 2 | 66.7% |" in text
    assert "| 过度归化 | 1 | 33.3% |" in text


def test_digest_representative_examples(mini):
    text = amp.digest(LABEL, repo=mini.root)
    # id 12（edit）：JP/opus/候选/最终 zh（=edited_zh）/裁决语（合成）全部出现
    assert JP[12] in text
    assert OPUS[12] in text
    assert CAND_CHA[12] in text
    assert "人工改写：教室弥漫着令人窒息的死寂" in text
    assert "语序" in text
    # id 13（keep_opus）：最终 zh 应为 opus 原译，不是候选
    assert OPUS[13] in text
    assert "过度归化" in text
    # id 20（adopt）：最终 zh 应为候选原文
    assert CAND_CHA[20] in text


def test_digest_appends_not_overwrites_rulings(mini):
    before = (mini.d / "frozen" / "rulings.md").read_text(encoding="utf-8")
    amp.digest(LABEL, repo=mini.root)
    after_1 = (mini.d / "frozen" / "rulings.md").read_text(encoding="utf-8")
    assert after_1.startswith(before)
    assert len(after_1) > len(before)
    amp.digest(LABEL, repo=mini.root)
    after_2 = (mini.d / "frozen" / "rulings.md").read_text(encoding="utf-8")
    assert after_2.startswith(after_1)
    assert len(after_2) > len(after_1)  # 第二次调用继续追加，不覆盖


# ---- 设计点 1：verdict="auto" 决策不计入人裁意图分布 ----

def test_auto_verdict_excluded_from_digest(tmp_path):
    decisions = [
        {"id": 12, "verdict": "edit", "chosen_channel": "chA",
         "edited_zh": "人工改写：教室弥漫着令人窒息的死寂，仿佛连时间都停了下来。",
         "reason_code": "语序", "ts": EDIT_TS_12},
        {"id": 13, "verdict": "keep_opus", "chosen_channel": "chA",
         "edited_zh": None, "reason_code": "过度归化", "ts": KEEP_TS_13},
        {"id": 20, "verdict": "adopt", "chosen_channel": "chA",
         "edited_zh": None, "reason_code": "语序", "ts": ADOPT_TS_20},
        # polish_commit.commit() 铸造的自动清关记录：不是人的判断，不应计入
        {"id": 14, "verdict": "auto", "chosen_channel": "chA", "edited_zh": None,
         "zh": CAND_CHA[14], "reason_code": "autoclear",
         "candidate_ts": "x", "prompt_hash": "hash-1", "ts": "2026-08-01T00:20:00+00:00"},
    ]
    mini = _build_mini(tmp_path, decisions=decisions)
    text = amp.digest(LABEL, repo=mini.root)
    assert "autoclear" not in text
    # 总计数仍是 3（人工裁决），不是 4
    assert "人工裁决 3 条" in text
    assert "| 语序 | 2 | 66.7% |" in text
    assert "| 过度归化 | 1 | 33.3% |" in text


# ---- scan_prompt：四桶全景（含桶 3 落选句全文）+ 轮数闸 ----

def test_scan_prompt_includes_bucket3_full_text(mini):
    text = amp.scan_prompt(LABEL, repo=mini.root)
    # 桶 3 两个案例的候选全文必须逐字出现（本任务存在的理由）
    assert CAND_CHA[14] in text
    assert CAND_CHA[15] in text
    assert JP[15] in text
    assert OPUS[15] in text
    # 桶 2/桶 1 也应出现在全景里
    assert CAND_CHA[12] in text
    assert OPUS[11] in text
    # 纪要与输出契约都应嵌入
    assert "原因码分布" in text
    assert "channel" in text.lower() or "raw/amplify" in text
    assert "raw/amplify/b1.out" in text
    assert "raw/amplify/b2.out" in text
    # 锁定 id 不应作为可改行出现在契约体里（不校验全文没有数字 10，只校验
    # 有锁定小节且候选体里没有把它当普通行）
    assert "锁定 id" in text


def test_scan_prompt_has_no_duplicate_or_skipped_chapter_numbers(mini):
    """评审 Finding C（Task 11 第二轮修复）：`scan_prompt()` 此前自己维护一套
    顶层编号（"## 零、本轮说明"→"一、裁决意图纪要"→"二、全 SEG 四桶结果全景"→
    "三、锁定 id 清单"→"四、术语/风格/口调/锚点"→"五、输出契约"），而"四、
    术语..."节内又整段复用 `_render_anchors()`，后者硬编码"## 三、锚点行"——
    与本文档自己的"三、锁定 id 清单"撞号。这与评审报的 Finding A 是同一个
    根因（复用 `build_context._render_anchors` 带进一个自带编号的标题），
    只是发生在 `polish_amplify.py` 而非 `polish_context.py`。修法与 Finding A
    保持一致（同一批人读的两份 prompt，风格不分叉）：本函数自己的顶层标题
    一律不编号，`_render_anchors()` 的产出经共享 helper
    `polishlib.demote_anchors_heading()` 降级为"### 锚点行"。"""
    text = amp.scan_prompt(LABEL, repo=mini.root)
    assert "## 三、" not in text
    assert "### 锚点行" in text
    for numeral in "零一二三四五六七八九十":
        assert f"## {numeral}、" not in text


def test_scan_prompt_has_no_stale_numbered_cross_references(mini):
    """评审 Finding A 在 `polish_context.py` 暴露的教训——标题去编号后，正文
    散文里引用旧编号的字符串必须跟着改，否则指向一个不存在的编号。
    `AMPLIFY_PREAMBLE` 原文有两处这类引用（"见下方"一、裁决意图纪要""、
    ""二、全 SEG 四桶结果全景"里"），随标题一并去了编号。用同一个通用正则
    扫全文，不满足于只测已知出过问题的那两处。"""
    text = amp.scan_prompt(LABEL, repo=mini.root)
    stale = re.findall(r"「[一二三四五六七八九十]+、[^」]*」", text)
    stale += re.findall(r'"[一二三四五六七八九十]+、[^"]*"', text)
    assert stale == [], f"发现指向带编号旧标题的散文引用：{stale}"


def test_scan_prompt_round_gate_blocks_second_call(mini):
    text1 = amp.scan_prompt(LABEL, repo=mini.root)
    assert isinstance(text1, str) and text1
    with pytest.raises(amp.AmplifyRoundLimitError):
        amp.scan_prompt(LABEL, repo=mini.root)


def test_scan_prompt_writes_marker_only_after_success(mini):
    rulings_before = (mini.d / "frozen" / "rulings.md").read_text(encoding="utf-8")
    assert not amp.AMPLIFY_MARKER_RE.search(rulings_before)
    amp.scan_prompt(LABEL, repo=mini.root)
    rulings_after = (mini.d / "frozen" / "rulings.md").read_text(encoding="utf-8")
    assert len(amp.AMPLIFY_MARKER_RE.findall(rulings_after)) == 1


# ---- CLI ----

def test_cli_digest(mini, capsys):
    rc = amp.main(["--seg", LABEL, "--digest", "--repo", str(mini.root)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "原因码分布" in out


def test_cli_scan_prompt_writes_out_file(mini, tmp_path):
    out_path = tmp_path / "amplify_prompt.md"
    rc = amp.main(["--seg", LABEL, "--scan-prompt", "--out", str(out_path),
                   "--repo", str(mini.root)])
    assert rc == 0
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert CAND_CHA[15] in text


def test_cli_scan_prompt_second_call_rejected(mini, capsys):
    rc1 = amp.main(["--seg", LABEL, "--scan-prompt", "--repo", str(mini.root)])
    assert rc1 == 0
    capsys.readouterr()
    rc2 = amp.main(["--seg", LABEL, "--scan-prompt", "--repo", str(mini.root)])
    assert rc2 == 1
    err = capsys.readouterr().err
    assert "轮次配额" in err or "拒绝" in err


# ---- 评审 Finding A：单个原因码 >3 条 edit 裁决时，第 4/5 条也必须出现 ----

WIDE_LABEL = "segWideCode"
WIDE_IDS = [100, 101, 102, 103, 104]
WIDE_JP = {i: f"第{i}句测试原文テキスト独立且不重复" for i in WIDE_IDS}
WIDE_OPUS = {i: f"第{i}句测试译文原样" for i in WIDE_IDS}
# 每条都是真实改动（远超 autoclear_limit=4），且各不相同，方便逐条断言。
WIDE_CAND = {i: f"第{i}句测试译文的候选改写版本，篇幅明显更长一些以确保编辑距离足够大"
             for i in WIDE_IDS}
WIDE_EDITED_ZH = {i: f"人工改写第{i}条：这是评审组裁决后确认的最终译文，与候选和 opus 都不同"
                  for i in WIDE_IDS}


def _build_wide_code_mini(tmp_path):
    """5 个 id，全部 verdict=edit、reason_code=语序——同一原因码下的裁决数
    超过 digest 代表例的"每码 ≤3 条"上限，专门验证 scan_prompt() 的桶 2
    全景渲染不受这个上限约束（评审 Finding A）。"""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": WIDE_LABEL, "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": WIDE_IDS, "seqs": [1],
         "jp_chars": len(WIDE_IDS), "chapter": "s2s", "cut_reason": "budget"},
    ])
    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([]), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 六条细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", [
        {"id": i, "jp": WIDE_JP[i], "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
        for i in WIDE_IDS
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": WIDE_OPUS[i], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"} for i in WIDE_IDS
    ])
    write_jsonl(opus_data / "patches.jsonl", [])

    d = ps.setup(WIDE_LABEL, opus_data, repo=repo)
    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-wide-1"},
    ]), encoding="utf-8")

    raw_cha = d / "raw" / "chA"
    raw_cha.mkdir(parents=True)
    lines = [dumps({"id": i, "jp_tail": jp_tail(WIDE_JP[i]), "zh": WIDE_CAND[i],
                     "score": 90, "note": "", "adjudicate": False}) for i in WIDE_IDS]
    (raw_cha / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert pi.ingest(WIDE_LABEL, "chA", 1, repo=repo)["ok"]
    pcheck.gate(WIDE_LABEL, "chA", repo=repo)
    pt.triage(WIDE_LABEL, repo=repo)  # 默认 K=150，5 条全部落桶 2

    write_jsonl(d / "decisions.jsonl", [
        {"id": i, "verdict": "edit", "chosen_channel": "chA",
         "edited_zh": WIDE_EDITED_ZH[i], "reason_code": "语序",
         "ts": f"2026-08-01T00:{i % 60:02d}:00+00:00"}
        for i in WIDE_IDS
    ])
    return SimpleNamespace(root=repo, d=d, label=WIDE_LABEL)


def test_scan_prompt_shows_final_zh_beyond_top3_examples(tmp_path):
    wide = _build_wide_code_mini(tmp_path)
    assert _triage_bucket_ids(wide.d, 2) == set(WIDE_IDS)

    text = amp.scan_prompt(WIDE_LABEL, repo=wide.root)
    # digest 的代表例最多只展示 3 条——只断言这 3 条不够，必须全部 5 条都在。
    for i in WIDE_IDS:
        assert WIDE_EDITED_ZH[i] in text, f"id {i} 的最终 zh 缺失于 scan_prompt 输出"


# ---- 评审 Finding B：amplify 候选的 prompt_hash 必须等于本次 scan_prompt
#      文本自身的哈希，不能借用普通通道那次会话的哈希 ----

def test_amplify_ingest_prompt_hash_matches_scan_prompt_not_normal_channel(mini):
    text = amp.scan_prompt(LABEL, repo=mini.root)
    expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    plan = json.loads((mini.d / "plan.json").read_text(encoding="utf-8"))
    amplify_records = [r for r in plan if r.get("channel") == "amplify"]
    assert len(amplify_records) == 1
    assert amplify_records[0]["prompt_hash"] == expected_hash
    assert set(amplify_records[0]["batches"]) == {1, 2}

    raw_amp = mini.d / "raw" / "amplify"
    raw_amp.mkdir(parents=True)
    lines_b1 = [dumps({"id": i, "jp_tail": jp_tail(JP[i]), "zh": CAND_CHA.get(i, OPUS[i]),
                        "score": 90, "note": "", "adjudicate": False})
                for i in (11, 12, 13, 14, 15)]
    (raw_amp / "b1.out").write_text("\n".join(lines_b1) + "\n", encoding="utf-8")
    lines_b2 = [dumps({"id": 20, "jp_tail": jp_tail(JP[20]), "zh": CAND_CHA[20],
                        "score": 90, "note": "", "adjudicate": False})]
    (raw_amp / "b2.out").write_text("\n".join(lines_b2) + "\n", encoding="utf-8")

    assert pi.ingest(LABEL, "amplify", 1, repo=mini.root)["ok"]
    assert pi.ingest(LABEL, "amplify", 2, repo=mini.root)["ok"]

    cands = read_jsonl(mini.d / "candidates.amplify.jsonl")
    assert cands
    for c in cands:
        assert c["prompt_hash"] == expected_hash
        assert c["prompt_hash"] != "hash-1"  # 不是 chA 那次普通会话的哈希
