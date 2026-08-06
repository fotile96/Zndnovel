"""tools/polish_check.py：保税仓机械闸的单测。

夹具用 `polish_setup.setup()` 造真正的 `frozen/`，再用 `polish_ingest.ingest()`
把手造的 raw 灌进真正的 `candidates.<channel>.jsonl`——`check_batch.check()`
本身已有独立测试（`tests/test_check_batch.py`）覆盖 R2a/R2b/R2c/W1/W2/W3 各
条闸的判定逻辑，本文件只测"薄封装"这一层：id 集裁剪、gates.json 落盘结构、
CLI，不重复造 check_batch 已经测过的判据边界案例。

夹具设计：单批（batch 1），非锁定 id 10/11/12，锁定 id 13（anchor）——锁定 id
存在的意义正是制造"frozen/source.jsonl 的 id 集合 ⊋ candidates 的 id 集合"
这个自然场景，用来验证裁剪逻辑（不裁剪会让 check() 只吐一条 R1 就放弃）。
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
from tools.pipelib import append_jsonl, dumps, read_jsonl, write_jsonl
from tools.polishlib import jp_tail

JP = {
    10: "【彩野】「うん、<前向性健忘,ぜんこうせいけんぼう>だよ」",
    11: "○_nそこには≪きみ≫がいた。_r間違いなく。",
    12: "【彩野】「今日はいい天気だね」",
    13: "【彩野】「これは锚点的な台词だよ」",
}
DEFAULT_ZH = {
    10: "【彩野】「嗯，是<前向性健忘,顺行性遗忘>哦」",
    11: "○_n那里有≪你≫。_r毫无疑问。",
    12: "【彩野】「今天天气真好啊」",
    13: "【彩野】「这是锚点台词哦」",
}
NON_LOCKED = [10, 11, 12]
LOCKED = 13


def _build_mini(tmp_path, zh_overrides=None, label="segX", channel="chA",
                 speakers=None):
    """造一个单批（batch 1）的 SEG：非锁定 10/11/12 + 锁定 13。ingest 一次
    raw（内容按 DEFAULT_ZH 叠加 zh_overrides），产出真正的
    candidates.<channel>.jsonl。

    `glossary/speakers.json` 现在是 `polish_setup._copy_glossary()` 的必需
    拷贝源（评审修复轮回填），仓库根必须始终存在这份文件，`ps.setup()`
    才不会 `FileNotFoundError`——`speakers` 参数控制它的内容（默认空字典，
    等价于"没有名字映射，只查结构"），`setup()` 会把它原样拷进
    `frozen/glossary/speakers.json`，`gate()` 因此默认就能读到冻结面的这
    份表（frozen-only，见模块 docstring）。"""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids = NON_LOCKED + [LOCKED]
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
            {"id": LOCKED, "jp": JP[LOCKED], "zh": DEFAULT_ZH[LOCKED], "recall": "测试锚点"},
        ]},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text(
        json.dumps({}, ensure_ascii=False), encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 六条细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text(
        json.dumps(speakers if speakers is not None else {}, ensure_ascii=False),
        encoding="utf-8")

    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", [
        {"id": i, "jp": JP[i], "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
        for i in ids
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": DEFAULT_ZH[i], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"}
        for i in ids
    ])
    write_jsonl(opus_data / "patches.jsonl", [])

    d = ps.setup(label, opus_data, repo=repo)
    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-1"},
    ]), encoding="utf-8")

    zh = dict(DEFAULT_ZH)
    if zh_overrides:
        zh.update(zh_overrides)

    raw_dir = d / "raw" / channel
    raw_dir.mkdir(parents=True)
    lines = [dumps({"id": i, "jp_tail": jp_tail(JP[i]), "zh": zh[i],
                    "score": 90, "note": "", "adjudicate": False})
             for i in NON_LOCKED]
    (raw_dir / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")

    r = pi.ingest(label, channel, 1, repo=repo)
    assert r["ok"], f"夹具本身的 ingest 失败：{r}"

    return SimpleNamespace(root=repo, d=d, label=label, channel=channel)


@pytest.fixture
def mini(tmp_path):
    return _build_mini(tmp_path)


# ---- brief Step 1 核心断言 ----

def test_all_green_candidates_empty_gates(mini):
    """全绿候选 → 空字典，且落盘的 gates.json 也是空对象。"""
    gates = pcheck.gate(mini.label, mini.channel, repo=mini.root)
    assert gates == {}
    on_disk = json.loads((mini.d / f"gates.{mini.channel}.json").read_text(encoding="utf-8"))
    assert on_disk == {}


def test_missing_speaker_prefix_is_hard(tmp_path):
    """候选丢【】说话人 → gate 报 R2b hard。

    这条用例同时是"id 集裁剪"的回归锁：id=12 是非锁定 id，frozen/source
    还含锁定 id=13（不在候选里）。若 gate() 忘记按候选 id 集裁剪
    source_rows，check() 会在两个 id 集合不相等时立刻返回一条孤零零的 R1
    （id=0）就放弃——12 的 R2b 根本不会出现。断言明确排除 R1、明确要求
    R2b 挂在真实 id=12 上，能同时抓住"裁剪被拿掉"这种恒绿闸形态。
    """
    m = _build_mini(tmp_path, zh_overrides={12: "今天天气真好啊"})  # 丢了【彩野】
    gates = pcheck.gate(m.label, m.channel, repo=m.root)
    assert 12 in gates
    rules = {v["rule"] for v in gates[12]["hard"]}
    assert "R2b" in rules
    all_rules = {v["rule"] for g in gates.values() for v in g["hard"] + g["warn"]}
    assert "R1" not in all_rules


def test_line_width_overflow_is_warn(tmp_path):
    """候选行宽爆 → W3 warn，且该 id 不带 hard。"""
    long_zh = "○_n那里有≪你≫。" + "长" * 40 + "_r毫无疑问。"
    m = _build_mini(tmp_path, zh_overrides={11: long_zh})
    gates = pcheck.gate(m.label, m.channel, repo=m.root)
    assert 11 in gates
    assert gates[11]["hard"] == []
    rules = {v["rule"] for v in gates[11]["warn"]}
    assert "W3" in rules


# ---- 落盘结构 ----

def test_gates_json_matches_return_value(tmp_path):
    m = _build_mini(tmp_path, zh_overrides={12: "今天天气真好啊"})
    gates = pcheck.gate(m.label, m.channel, repo=m.root)
    on_disk = json.loads((m.d / f"gates.{m.channel}.json").read_text(encoding="utf-8"))
    # JSON 对象键只能是字符串；返回值里是 int 键，落盘后是 str 键，内容一致。
    assert on_disk == {str(k): v for k, v in gates.items()}
    assert set(on_disk.keys()) == {"12"}


def test_no_candidates_file_returns_empty(mini):
    """该通道从未入仓过任何东西：channel 不存在 candidates 文件 → 视为零
    候选，不报错，照常落盘一份空 gates 文件。"""
    gates = pcheck.gate(mini.label, "never-ingested-channel", repo=mini.root)
    assert gates == {}
    assert (mini.d / "gates.never-ingested-channel.json").exists()


# ---- 同 id 多条候选：取最后一条 ----

def test_multiple_candidates_same_id_last_wins(mini):
    """amplify 等场景可能向同一份 candidates.<channel>.jsonl 继续 append 同一
    id 的新一行——gate() 必须按"最后一条"判定，不是第一条、也不是合并两条。"""
    # 先确认初始（干净）状态下 12 不在问题字典里。
    gates0 = pcheck.gate(mini.label, mini.channel, repo=mini.root)
    assert 12 not in gates0

    # 追加一条 id=12 的新候选，内容带 R2b 违规（丢说话人）。
    append_jsonl(mini.d / f"candidates.{mini.channel}.jsonl", [{
        "id": 12, "channel": mini.channel, "batch": 1, "prompt_hash": "hash-1",
        "jp_hash": "x", "opus_hash": "x", "zh": "今天天气真好啊",
        "score": 50, "note": "amplify 轮次", "adjudicate": False,
        "jp_tail": jp_tail(JP[12]), "ts": "t2",
    }])
    gates1 = pcheck.gate(mini.label, mini.channel, repo=mini.root)
    assert 12 in gates1
    assert "R2b" in {v["rule"] for v in gates1[12]["hard"]}

    # 再追加一条把 12 改回干净内容——gate() 应重新判定为绿（不是"曾经红过
    # 就一直红"）。
    append_jsonl(mini.d / f"candidates.{mini.channel}.jsonl", [{
        "id": 12, "channel": mini.channel, "batch": 1, "prompt_hash": "hash-1",
        "jp_hash": "x", "opus_hash": "x", "zh": DEFAULT_ZH[12],
        "score": 95, "note": "修正", "adjudicate": False,
        "jp_tail": jp_tail(JP[12]), "ts": "t3",
    }])
    gates2 = pcheck.gate(mini.label, mini.channel, repo=mini.root)
    assert 12 not in gates2


# ---- 候选里混入不属于这个 SEG 的 id（防御性） ----

def test_stray_candidate_id_skipped_not_crashed(mini, capsys):
    append_jsonl(mini.d / f"candidates.{mini.channel}.jsonl", [{
        "id": 999999, "channel": mini.channel, "batch": 1, "prompt_hash": "hash-1",
        "jp_hash": "x", "opus_hash": "x", "zh": "不知道哪来的",
        "score": 10, "note": "", "adjudicate": False, "jp_tail": "?", "ts": "t",
    }])
    gates = pcheck.gate(mini.label, mini.channel, repo=mini.root)
    assert 999999 not in gates
    err = capsys.readouterr().err
    assert "999999" in err


# ---- speakers 取法：frozen-only，无回落（评审修复轮定案） ----

def test_speakers_read_from_frozen_copy(tmp_path):
    """正路：`polish_setup._copy_glossary()` 现在会把 speakers.json 拷进
    frozen/glossary/（评审修复轮回填），gate() 从这份冻结面读表、名字映射
    分支生效——用一个"名字映射错误"的候选验证 R2b 确实触发了（不是恰好
    走了"表未覆盖=不查名字"的宽松分支）。"""
    speakers = {"彩野": "彩野"}
    m = _build_mini(tmp_path, speakers=speakers,
                     zh_overrides={12: "【绫乃】「今天天气真好啊」"})
    assert (m.d / "frozen" / "glossary" / "speakers.json").exists()
    gates = pcheck.gate(m.label, m.channel, repo=m.root)
    assert 12 in gates
    msgs = [v["msg"] for v in gates[12]["hard"] if v["rule"] == "R2b"]
    assert any("彩野" in msg for msg in msgs)


def test_speakers_frozen_only_no_fallback_to_repo_root(tmp_path):
    """R2b 的名字映射只认冻结面，绝不回落读活仓库——评审 finding 的回归锁。

    构造刻意制造"若发生回落就会被抓包"的对抗场景：frozen 里没有
    speakers.json（模拟该 SEG 冻结时点确实没有这张表，或缺口尚未回填的
    历史状态——手动删掉冻结面里已拷贝的那份），而仓库根有一份内容不同、
    且**会导致误判**的表。候选的说话人前缀与原文不同（【绫乃】vs 原文
    【彩野】），但两边结构上都带着【】，不会触发结构型 R2b；只有"读到了
    仓库根那份表、按名字映射比对"才会额外触发名字映射型 R2b。

    断言：gate() 的结论只能是"没有 speakers 表，只查结构"这一种——12 不
    应带任何 R2b。这条断言在"回落"代码路径被误改回来时必须真正转红（见
    变异④）。
    """
    speakers = {"彩野": "彩野"}
    m = _build_mini(tmp_path, speakers=speakers,
                     zh_overrides={12: "【绫乃】「今天天气真好啊」"})
    # 模拟 frozen 里没有这张表：手动删掉冻结面已拷贝的副本。
    (m.d / "frozen" / "glossary" / "speakers.json").unlink()
    # 仓库根这份还在（_build_mini 写入时的内容），若发生回落就会被读到。
    assert (m.root / "glossary" / "speakers.json").exists()

    gates = pcheck.gate(m.label, m.channel, repo=m.root)
    rules12 = {v["rule"] for v in gates.get(12, {"hard": []})["hard"]}
    assert "R2b" not in rules12


# ---- CLI ----

def test_cli_writes_gates_and_reports_counts(mini, capsys):
    rc = pcheck.main(["--seg", mini.label, "--channel", mini.channel,
                       "--repo", str(mini.root)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "hard 0" in out
    assert (mini.d / f"gates.{mini.channel}.json").exists()


def test_cli_reports_hard_count(tmp_path, capsys):
    m = _build_mini(tmp_path, zh_overrides={12: "今天天气真好啊"})
    rc = pcheck.main(["--seg", m.label, "--channel", m.channel, "--repo", str(m.root)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "hard 1" in out
