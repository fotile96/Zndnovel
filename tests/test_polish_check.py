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
    (repo / "glossary" / "polish.md").write_text("# 语感细则", encoding="utf-8")
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
    # LOCKED（13）同时落一条内容相同的 patch，使它在硬锁/软锁分类下仍归为
    # **硬锁**（2026-08-07 裁定：patched 优先于 anchor）——保留本文件"锁定
    # id 不出稿"的既有假设，本文件不测软锁专属行为（那已在
    # test_polish_{ingest,triage,context}.py 覆盖）。
    write_jsonl(opus_data / "patches.jsonl", [
        {"id": LOCKED, "zh": DEFAULT_ZH[LOCKED], "reason": "review",
         "glossary_v": 1, "ts": "t"},
    ])

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

def test_all_green_candidates_empty_findings_but_checked_ids_recorded(mini):
    """全绿候选 → `findings` 空，但 `checked_ids` 必须如实列出被检查过的 id。

    「findings 为空」与「checked_ids 为空」是两件完全不同的事：前者是"查过、
    干净"，后者是"没查过"。初版落盘只有前者那一层，下游无从区分，造成陈旧
    gates ＝ 恒绿闸（最终评审 C1）。这条断言把两者同时钉住。
    """
    gates = pcheck.gate(mini.label, mini.channel, repo=mini.root)
    assert gates["findings"] == {}
    assert gates["checked_ids"] == sorted(NON_LOCKED)
    on_disk = json.loads((mini.d / f"gates.{mini.channel}.json").read_text(encoding="utf-8"))
    assert on_disk == {"checked_ids": sorted(NON_LOCKED), "findings": {}}


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
    findings = gates["findings"]
    assert 12 in findings
    rules = {v["rule"] for v in findings[12]["hard"]}
    assert "R2b" in rules
    all_rules = {v["rule"] for g in findings.values() for v in g["hard"] + g["warn"]}
    assert "R1" not in all_rules


def test_line_width_overflow_is_warn(tmp_path):
    """候选行宽爆 → W3 warn，且该 id 不带 hard。"""
    long_zh = "○_n那里有≪你≫。" + "长" * 40 + "_r毫无疑问。"
    m = _build_mini(tmp_path, zh_overrides={11: long_zh})
    gates = pcheck.gate(m.label, m.channel, repo=m.root)
    findings = gates["findings"]
    assert 11 in findings
    assert findings[11]["hard"] == []
    rules = {v["rule"] for v in findings[11]["warn"]}
    assert "W3" in rules


# ---- 落盘结构 ----

def test_gates_json_matches_return_value(tmp_path):
    m = _build_mini(tmp_path, zh_overrides={12: "今天天气真好啊"})
    gates = pcheck.gate(m.label, m.channel, repo=m.root)
    on_disk = json.loads((m.d / f"gates.{m.channel}.json").read_text(encoding="utf-8"))
    # JSON 对象键只能是字符串；返回值 findings 里是 int 键，落盘后是 str 键。
    assert on_disk["findings"] == {str(k): v for k, v in gates["findings"].items()}
    assert set(on_disk["findings"].keys()) == {"12"}
    # checked_ids 覆盖全部三个非锁定 id——包括两个全绿的（它们不在 findings 里）。
    assert on_disk["checked_ids"] == sorted(NON_LOCKED)


def test_no_candidates_file_returns_empty(mini):
    """该通道从未入仓过任何东西：channel 不存在 candidates 文件 → 视为零
    候选，不报错，照常落盘一份空 gates 文件。"""
    gates = pcheck.gate(mini.label, "never-ingested-channel", repo=mini.root)
    assert gates == {"checked_ids": [], "findings": {}}
    assert (mini.d / "gates.never-ingested-channel.json").exists()


# ---- 同 id 多条候选：取最后一条 ----

def test_multiple_candidates_same_id_last_wins(mini):
    """amplify 等场景可能向同一份 candidates.<channel>.jsonl 继续 append 同一
    id 的新一行——gate() 必须按"最后一条"判定，不是第一条、也不是合并两条。"""
    # 先确认初始（干净）状态下 12 不在问题字典里。
    gates0 = pcheck.gate(mini.label, mini.channel, repo=mini.root)
    assert 12 not in gates0["findings"]

    # 追加一条 id=12 的新候选，内容带 R2b 违规（丢说话人）。
    append_jsonl(mini.d / f"candidates.{mini.channel}.jsonl", [{
        "id": 12, "channel": mini.channel, "batch": 1, "prompt_hash": "hash-1",
        "jp_hash": "x", "opus_hash": "x", "zh": "今天天气真好啊",
        "score": 50, "note": "amplify 轮次", "adjudicate": False,
        "jp_tail": jp_tail(JP[12]), "ts": "t2",
    }])
    gates1 = pcheck.gate(mini.label, mini.channel, repo=mini.root)
    assert 12 in gates1["findings"]
    assert "R2b" in {v["rule"] for v in gates1["findings"][12]["hard"]}

    # 再追加一条把 12 改回干净内容——gate() 应重新判定为绿（不是"曾经红过
    # 就一直红"）。
    append_jsonl(mini.d / f"candidates.{mini.channel}.jsonl", [{
        "id": 12, "channel": mini.channel, "batch": 1, "prompt_hash": "hash-1",
        "jp_hash": "x", "opus_hash": "x", "zh": DEFAULT_ZH[12],
        "score": 95, "note": "修正", "adjudicate": False,
        "jp_tail": jp_tail(JP[12]), "ts": "t3",
    }])
    gates2 = pcheck.gate(mini.label, mini.channel, repo=mini.root)
    assert 12 not in gates2["findings"]


# ---- 候选里混入不属于这个 SEG 的 id（防御性） ----

def test_stray_candidate_id_skipped_not_crashed(mini, capsys):
    append_jsonl(mini.d / f"candidates.{mini.channel}.jsonl", [{
        "id": 999999, "channel": mini.channel, "batch": 1, "prompt_hash": "hash-1",
        "jp_hash": "x", "opus_hash": "x", "zh": "不知道哪来的",
        "score": 10, "note": "", "adjudicate": False, "jp_tail": "?", "ts": "t",
    }])
    gates = pcheck.gate(mini.label, mini.channel, repo=mini.root)
    assert 999999 not in gates["findings"]
    assert 999999 not in gates["checked_ids"]
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
    assert 12 in gates["findings"]
    msgs = [v["msg"] for v in gates["findings"][12]["hard"] if v["rule"] == "R2b"]
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
    rules12 = {v["rule"] for v in gates["findings"].get(12, {"hard": []})["hard"]}
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


# ---- P4-CTL：控制码计数保全（vs opus 现行译文）——最终评审 C2 ----

def test_ctl_drop_n_is_hard(tmp_path):
    """删掉一个 `_n` 必须是 hard。

    这是最终评审 C2 实测复现的形态："纯控制码删除"是**最像安全小改**的东西
    ——`polish_triage._content_edit()` 先 `strip_ctl()` 再算距离，删光 `_n`
    得到 edit=0，比任何真实润色都"安全"；`check_batch` 那边 `_n/_r` 只有
    W1 一条软规则、阈值还是「差 ≥2」，删一个连 warn 都不响。于是候选一路
    直通自动清关。`_n` 决定消息窗断行，丢了就是游戏内溢出。
    """
    m = _build_mini(tmp_path, zh_overrides={11: "○那里有≪你≫。_r毫无疑问。"})
    findings = pcheck.gate(m.label, m.channel, repo=m.root)["findings"]
    assert 11 in findings
    rules = {v["rule"] for v in findings[11]["hard"]}
    assert "P4-CTL" in rules, "删掉 _n 必须落在 hard 里——warn 在 P4 流水线上零消费者"
    msgs = [v["msg"] for v in findings[11]["hard"] if v["rule"] == "P4-CTL"]
    assert any("_n" in msg for msg in msgs)


def test_ctl_swap_n_for_r_is_hard(tmp_path):
    """`_n`→`_r` 对换：总数不变、单项计数变——分开数才抓得住。

    这条专门钉死"两个计数器分开数，不合并成总数"这个选择：合并成总数的
    实现在这个输入下**恒绿**（1+1 == 1+1），而 `_n`/`_r` 是引擎里两种不同
    的断行语义，对换是实打实的控制码篡改（prompt 任务说明第 4 条明令禁止）。
    """
    m = _build_mini(tmp_path, zh_overrides={11: "○_r那里有≪你≫。_r毫无疑问。"})
    findings = pcheck.gate(m.label, m.channel, repo=m.root)["findings"]
    hard = [v for v in findings.get(11, {"hard": []})["hard"] if v["rule"] == "P4-CTL"]
    assert hard, "`_n`→`_r` 对换必须被抓住（合并成总数的实现在这里会恒绿）"
    assert {"_n", "_r"} <= {tok for v in hard for tok in ("_n", "_r") if tok in v["msg"]}


def test_ctl_position_move_is_allowed(tmp_path):
    """只挪位置、计数不变 → 不报（判据故意只卡计数，见模块 docstring）。

    润色改了中文字数之后前后挪一两个字的断行点是正当排版动作；卡位置会让
    几乎每条真实润色都变红，一周内这条闸就会被当噪音无视——那是"恒绿闸的
    镜像形态"（伪报淹没真信号）。位置挪动的真实风险是某行变得过长，那是
    W3 的管辖面，且 W3 已被列入自动清关前置。
    """
    m = _build_mini(tmp_path, zh_overrides={11: "○那里有≪你≫。_n毫无疑问，_r真的。"})
    findings = pcheck.gate(m.label, m.channel, repo=m.root)["findings"]
    rules = {v["rule"] for v in findings.get(11, {"hard": []})["hard"]}
    assert "P4-CTL" not in rules


def test_ruby_drop_is_hard(tmp_path):
    """整个 ruby 注音被删 → hard。R2a 只管"写出来的 ruby 良不良构"，
    **整组被删掉它一声不吭**——这是与 `_n/_r` 完全同型的静默丢失。"""
    m = _build_mini(tmp_path, zh_overrides={10: "【彩野】「嗯，是顺行性遗忘哦」"})
    findings = pcheck.gate(m.label, m.channel, repo=m.root)["findings"]
    hard = [v for v in findings.get(10, {"hard": []})["hard"] if v["rule"] == "P4-CTL"]
    assert hard and "ruby" in hard[0]["msg"]


def test_ctl_unchanged_candidates_stay_green(tmp_path):
    """反向锁：夹具默认候选（逐字等于 opus）一条 P4-CTL 都不该有——判据
    不能宽到把"什么都没改"也报出来。"""
    m = _build_mini(tmp_path)
    findings = pcheck.gate(m.label, m.channel, repo=m.root)["findings"]
    assert not [v for g in findings.values() for v in g["hard"] if v["rule"] == "P4-CTL"]


def test_ctl_violations_unit():
    """`ctl_violations()` 的直接单测：三项各自独立报、报文带 opus/候选计数。"""
    v = pcheck.ctl_violations(1, "甲_n乙", "甲_n乙_n丙")
    assert len(v) == 1 and v[0]["rule"] == "P4-CTL" and "opus 2 个，候选 1 个" in v[0]["msg"]
    assert pcheck.ctl_violations(1, "甲_n乙", "甲_n乙") == []
    # 非字符串 zh（ingest 已判死，这里是兜底）：opus 里的控制码全部报出来。
    assert len(pcheck.ctl_violations(1, None, "甲_n乙_r<漢,かん>")) == 3


# ---- 清关后全段 W4 复检（最终评审 C3）----

def _build_lane(tmp_path, ledger, current):
    """造一个最小的生产车道（`<lane>/data/{ledger,forward}.jsonl`）——
    `check_batch.load_siblings()` 与 `w4_full()` 都按这个布局读。"""
    lane = tmp_path / "lane"
    (lane / "data").mkdir(parents=True)
    write_jsonl(lane / "data" / "ledger.jsonl", [
        {"id": i, "jp": jp, "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
        for i, jp in ledger.items()])
    write_jsonl(lane / "data" / "forward.jsonl", [
        {"id": i, "zh": zh, "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"} for i, zh in current.items()])
    return lane


def test_w4_full_reports_sibling_divergence(mini, tmp_path):
    """润色只改了复现句族里的一条 → 全段 W4 复检必须报出来。

    spec §8 点名这是"真实风险"，而候选级机械闸恒传 `siblings=None`（W4 在
    那一层完全不跑），runbook 原来指向的 `check_batch.py --batch N` 在 P4
    语境下根本跑不起来（读 P3 的 `work/ctx/batch_N/`，早已不存在；即便重建
    读的也是 P3 首译稿而非清关后现行译文）——最终评审 C3：W4 在 P4 全程从
    未跑过。
    """
    # id 10 与库外的 id 900 是同一 jp 的复现句族；10 被润色改过，900 没改。
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: JP[10]},
        current={10: "【彩野】「嗯，是<前向性健忘,顺行性遗忘>啦」", 11: DEFAULT_ZH[11],
                 12: DEFAULT_ZH[12], 13: DEFAULT_ZH[13], 900: DEFAULT_ZH[10]})
    findings = pcheck.w4_full(mini.label, lane, repo=mini.root)
    assert [v["id"] for v in findings] == [10]
    assert "900" in findings[0]["msg"]
    on_disk = json.loads((mini.d / "w4_full.json").read_text(encoding="utf-8"))
    assert on_disk["findings"] == findings


def test_w4_full_msg_lists_every_member_no_truncation():
    """`_w4_full_msg()` 与 P3 钉死面 `check_batch._w4_msg()`（按文本去重、
    截断到 3 种 + "共 N 种异译"摘要）刻意不同——全段收敛检查要求逐个列出，
    5 个互不相同的译法一个都不能少。"""
    others = [(i, f"译法{i}") for i in range(1, 6)]
    msg = pcheck._w4_full_msg(others, id2label={1: "segA"})
    for i in range(1, 6):
        assert f"id={i}" in msg
    assert "共 5 个其他成员" in msg
    assert "id=1@segA" in msg
    assert "id=2@未知段" in msg   # 不在 id2label 里 -> 未知段，不是被吞掉


# ---- D4 修复：finding 报出全族成员，不是只报一个（SEG-0 实测：7894 的句族
# 有三个成员 7894/9186/11407，旧代码按文本去重只报出 9186，11407 要等下
# 一轮重跑才暴露）----

def test_w4_full_reports_all_members_not_just_one(mini, tmp_path):
    """id 900 与 901 的旧译文**字面相同**——这正是 D4 的复现条件：
    `check_batch._w4_msg()` 按 `zh` 文本去重，会把 900/901 只留一个代表；
    `w4_full()` 必须把两个都点出来，且 `siblings` 结构化字段本身也要能
    查到（不能只藏在 `msg` 字符串里）。"""
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13],
                900: JP[10], 901: JP[10]},
        current={10: "【彩野】「嗯，是<前向性健忘,顺行性遗忘>啦」", 11: DEFAULT_ZH[11],
                 12: DEFAULT_ZH[12], 13: DEFAULT_ZH[13],
                 900: DEFAULT_ZH[10], 901: DEFAULT_ZH[10]})
    findings = pcheck.w4_full(mini.label, lane, repo=mini.root)
    assert [v["id"] for v in findings] == [10]
    f = findings[0]

    sibling_ids = {s["id"] for s in f["siblings"]}
    assert sibling_ids == {900, 901}
    zh_by_id = {s["id"]: s["zh"] for s in f["siblings"]}
    assert zh_by_id[900] == zh_by_id[901] == DEFAULT_ZH[10]
    assert "900" in f["msg"] and "901" in f["msg"]

    on_disk = json.loads((mini.d / "w4_full.json").read_text(encoding="utf-8"))
    assert on_disk["findings"] == findings


def test_w4_full_siblings_report_segment_label(mini, tmp_path):
    """`siblings` 里每个成员标注"所属段"——经 `forward.jsonl` 的 `batch`
    号落进 `config/segments.yaml` 的 `batches` 区间解出。runbook D4 表格
    此前靠人工交叉核对才填出"伙伴所在段"这一列，现在应由机器直接给出。"""
    (mini.root / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": "segX", "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
        {"seg": 2, "label": "segY", "lane": "main", "batches": [2, 2],
         "chapters": ["s3s"], "jp_chars": 1, "review_focus": "测试段2"},
    ], allow_unicode=True), encoding="utf-8")

    lane = tmp_path / "lane_cross_seg"
    (lane / "data").mkdir(parents=True)
    write_jsonl(lane / "data" / "ledger.jsonl", [
        {"id": i, "jp": jp, "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
        for i, jp in {10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13],
                      900: JP[10]}.items()])
    write_jsonl(lane / "data" / "forward.jsonl", [
        {"id": 10, "zh": "【彩野】「嗯，是<前向性健忘,顺行性遗忘>啦」", "batch": 1,
         "backend": "cc", "model": "m", "ctx": "x", "glossary_v": 1, "ts": "t"},
        {"id": 11, "zh": DEFAULT_ZH[11], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"},
        {"id": 12, "zh": DEFAULT_ZH[12], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"},
        {"id": 13, "zh": DEFAULT_ZH[13], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"},
        # 900 属于 segY（batch=2）——跨段兄弟行，与 runbook D4 表里
        # "seg2-s3(b66/b67)"/"seg5-s6-s7f(b152)" 这类越段伙伴同一形态。
        {"id": 900, "zh": DEFAULT_ZH[10], "batch": 2, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"},
    ])

    findings = pcheck.w4_full(mini.label, lane, repo=mini.root)
    f = findings[0]
    assert f["siblings"] == [{"id": 900, "zh": DEFAULT_ZH[10], "seg": "segY"}]
    assert "900@segY" in f["msg"]


def test_w4_full_siblings_seg_unknown_when_batch_out_of_range(mini, tmp_path):
    """所属段解不出来（batch 号不落在任何已知段的区间里）时标"未知段"，
    不是报错、也不是悄悄漏掉这个成员——顾问级标注缺失不影响告警本身。"""
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: JP[10]},
        current={10: "【彩野】「嗯，是<前向性健忘,顺行性遗忘>啦」", 11: DEFAULT_ZH[11],
                 12: DEFAULT_ZH[12], 13: DEFAULT_ZH[13], 900: DEFAULT_ZH[10]})
    fwd = read_jsonl(lane / "data" / "forward.jsonl")
    for r in fwd:
        if r["id"] == 900:
            r["batch"] = 999   # mini 的 segments.yaml 只覆盖 batch=1
    write_jsonl(lane / "data" / "forward.jsonl", fwd)

    findings = pcheck.w4_full(mini.label, lane, repo=mini.root)
    assert findings[0]["siblings"][0]["seg"] is None
    assert "未知段" in findings[0]["msg"]


def test_w4_full_green_when_family_consistent(mini, tmp_path):
    lane = _build_lane(
        tmp_path,
        ledger={i: JP[i] for i in (10, 11, 12, 13)} | {900: JP[10]},
        current={i: DEFAULT_ZH[i] for i in (10, 11, 12, 13)} | {900: DEFAULT_ZH[10]})
    assert pcheck.w4_full(mini.label, lane, repo=mini.root) == []


def test_w4_full_refuses_to_fake_green_without_index(mini, tmp_path):
    """车道 data 建不出兄弟索引时**抛异常**，绝不返回空清单冒充绿——
    "闸没跑"必须与"闸跑了没报"可区分（`check_batch.main()` 同一条告诫）。"""
    empty_lane = tmp_path / "empty_lane"
    (empty_lane / "data").mkdir(parents=True)
    with pytest.raises(pcheck.W4NotAvailable):
        pcheck.w4_full(mini.label, empty_lane, repo=mini.root)


def test_cli_w4_full(mini, tmp_path, capsys):
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: JP[10]},
        current={10: "【彩野】「嗯，是<前向性健忘,顺行性遗忘>啦」", 11: DEFAULT_ZH[11],
                 12: DEFAULT_ZH[12], 13: DEFAULT_ZH[13], 900: DEFAULT_ZH[10]})
    rc = pcheck.main(["--seg", mini.label, "--w4-full", "--lane-dir", str(lane),
                      "--repo", str(mini.root)])
    assert rc == 0
    cap = capsys.readouterr()
    assert "1 处" in cap.out
    assert "id 10" in cap.err


def test_cli_w4_full_unavailable_is_rc2(mini, tmp_path, capsys):
    """索引建不起来 → rc=2（"没能检查"与"检查通过"在退出码上就可区分）。"""
    empty_lane = tmp_path / "empty_lane"
    (empty_lane / "data").mkdir(parents=True)
    rc = pcheck.main(["--seg", mini.label, "--w4-full", "--lane-dir", str(empty_lane),
                      "--repo", str(mini.root)])
    assert rc == 2
    assert "未能执行" in capsys.readouterr().err


# ---- W4 的记号盲区补扫：`bare_full()`（SEG-7 冻结时立项）----
#
# 生产实据：`4843`【≦ユウイチ≧】≪…≫ 与 `15010`【ユウイチ】「…」引号里的字
# 一个不差，SEG-4 的润色 patch 只改了 15010 一侧，W4 全程没响——族键是 jp
# **整行**，记号壳一换就不成族。

_SHELL_JP = "【≦彩野≧】≪うん、<前向性健忘,ぜんこうせいけんぼう>だよ≫"
_SHELL_ZH = "【≦彩野≧】≪嗯，是<前向性健忘,顺行性遗忘>啦≫"


def test_bare_text_strips_speaker_and_outer_quotes_only():
    """剥壳只剥说话人前缀与**最外**一层引号；内层『…』是正文的一部分。

    内层不能剥：本作用『…』标记「物語」「ドーナツの人」这类被引用的名目，
    剥掉会把两个真正不同的句子并成一族（`14988`「ドーナツを『つくって』、
    頭に投げて」vs `4821`「ドーナツを頭に投げて」正是这种关系）。
    """
    assert pcheck.bare_text("【彩野】「今日はいい天気だね」") == "今日はいい天気だね"
    assert pcheck.bare_text("【≦彩野≧】≪今日はいい天気だね≫") == "今日はいい天気だね"
    assert pcheck.bare_text("【千秋】「『物語』だよ」") == "『物語』だよ"
    assert pcheck.bare_text("地の文はそのまま。") == "地の文はそのまま。"


def test_bare_full_catches_what_w4_cannot_see(mini, tmp_path):
    """★ 本模块存在的全部理由：记号壳不同、正文相同、译文分歧 —— W4 **不报**，
    bare_full **报**。两条断言缺一不可：只断言"bare 报了"无法证明这不是在
    重复 W4 已经覆盖的东西。"""
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: _SHELL_JP},
        current={10: DEFAULT_ZH[10], 11: DEFAULT_ZH[11], 12: DEFAULT_ZH[12],
                 13: DEFAULT_ZH[13], 900: _SHELL_ZH})

    assert pcheck.w4_full(mini.label, lane, repo=mini.root) == []   # W4 的盲区

    findings = pcheck.bare_full(mini.label, lane, repo=mini.root)
    assert [v["id"] for v in findings] == [10]
    assert findings[0]["rule"] == "BARE"
    assert [s["id"] for s in findings[0]["siblings"]] == [900]
    assert findings[0]["bare_jp"] == pcheck.bare_text(JP[10])
    on_disk = json.loads((mini.d / "bare_full.json").read_text(encoding="utf-8"))
    assert on_disk["findings"] == findings
    assert on_disk["min_len"] == pcheck.BARE_MIN_LEN


def test_bare_full_does_not_duplicate_w4(mini, tmp_path):
    """原始 jp 已全同的族是 W4 的管辖面 —— bare_full 显式排除，不重复告警。
    同一份数据下 W4 必须报，证明这不是"两边都没查"。"""
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: JP[10]},
        current={10: DEFAULT_ZH[10], 11: DEFAULT_ZH[11], 12: DEFAULT_ZH[12],
                 13: DEFAULT_ZH[13], 900: "【彩野】「嗯，是<前向性健忘,顺行性遗忘>啦」"})
    assert pcheck.bare_full(mini.label, lane, repo=mini.root) == []
    assert [v["id"] for v in pcheck.w4_full(mini.label, lane, repo=mini.root)] == [10]


def test_bare_full_green_when_shells_differ_but_text_agrees(mini, tmp_path):
    """壳不同、正文相同、**译文剥壳后也相同** → 不报。

    这是反向锁：判据若宽到把"壳不同"本身当问题，e2f 整章都会变红——那正是
    伪报淹没真信号的形态。
    """
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: _SHELL_JP},
        current={10: DEFAULT_ZH[10], 11: DEFAULT_ZH[11], 12: DEFAULT_ZH[12],
                 13: DEFAULT_ZH[13],
                 900: "【≦彩野≧】≪嗯，是<前向性健忘,顺行性遗忘>哦≫"})
    assert pcheck.bare_full(mini.label, lane, repo=mini.root) == []


def test_bare_full_min_len_gate_is_live(mini, tmp_path):
    """长度门槛必须是**活的**：短句默认被挡（短应答的异译本来就正当），
    把门槛降下来同一份数据必须报出来。

    只断言"短句不报"是不够的——那与"这段代码根本没跑"无法区分。
    """
    short_jp, short_shell = "【彩野】「うん」", "【≦彩野≧】≪うん≫"
    lane = _build_lane(
        tmp_path,
        ledger={10: short_jp, 11: JP[11], 12: JP[12], 13: JP[13], 900: short_shell},
        current={10: "【彩野】「嗯」", 11: DEFAULT_ZH[11], 12: DEFAULT_ZH[12],
                 13: DEFAULT_ZH[13], 900: "【≦彩野≧】≪对≫"})
    assert pcheck.bare_full(mini.label, lane, repo=mini.root) == []
    assert [v["id"] for v in
            pcheck.bare_full(mini.label, lane, repo=mini.root, min_len=1)] == [10]


def test_bare_full_reports_segment_label_of_siblings(mini, tmp_path):
    """伙伴要标所属段——「这一边在已定稿段」是"改哪一边"的第一判据。"""
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: _SHELL_JP},
        current={10: DEFAULT_ZH[10], 11: DEFAULT_ZH[11], 12: DEFAULT_ZH[12],
                 13: DEFAULT_ZH[13], 900: _SHELL_ZH})
    f = pcheck.bare_full(mini.label, lane, repo=mini.root)[0]
    assert f["siblings"][0]["seg"] == "segX"
    assert "900@segX" in f["msg"]


def test_bare_full_refuses_to_fake_green_without_index(mini, tmp_path):
    """车道 data 建不出索引 → 抛异常，绝不返回空清单冒充绿。"""
    empty_lane = tmp_path / "empty_lane_bare"
    (empty_lane / "data").mkdir(parents=True)
    with pytest.raises(pcheck.W4NotAvailable):
        pcheck.bare_full(mini.label, empty_lane, repo=mini.root)


def test_cli_bare_full(mini, tmp_path, capsys):
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: _SHELL_JP},
        current={10: DEFAULT_ZH[10], 11: DEFAULT_ZH[11], 12: DEFAULT_ZH[12],
                 13: DEFAULT_ZH[13], 900: _SHELL_ZH})
    rc = pcheck.main(["--seg", mini.label, "--bare-full", "--lane-dir", str(lane),
                      "--repo", str(mini.root)])
    assert rc == 0
    cap = capsys.readouterr()
    assert "3 处" not in cap.out and "1 处" in cap.out
    assert "id 10" in cap.err


def test_cli_bare_full_unavailable_is_rc2(mini, tmp_path, capsys):
    empty_lane = tmp_path / "empty_lane_bare_cli"
    (empty_lane / "data").mkdir(parents=True)
    rc = pcheck.main(["--seg", mini.label, "--bare-full", "--lane-dir",
                      str(empty_lane), "--repo", str(mini.root)])
    assert rc == 2
    assert "未能执行" in capsys.readouterr().err


# --- P5 工装：人改孪生传播扫描（human_twin_scan） ---

def _write_decisions(mini, rows):
    write_jsonl(mini.d / "decisions.jsonl", rows)


def test_human_twin_scan_reports_unsynced_jp_twin(mini, tmp_path):
    """人工 edit 过的行，jp 全等孪生停在旧形 → 报出（方向：孪生未同步）。"""
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: JP[10]},
        current={10: "【彩野】「人裁后的新译文」", 11: DEFAULT_ZH[11],
                 12: DEFAULT_ZH[12], 13: DEFAULT_ZH[13], 900: DEFAULT_ZH[10]})
    _write_decisions(mini, [
        {"id": 10, "verdict": "edit", "chosen_channel": "chA",
         "edited_zh": "【彩野】「人裁后的新译文」", "reason_code": "口调", "ts": "t1"},
    ])
    findings = pcheck.human_twin_scan(mini.label, lane, repo=mini.root)
    assert [v["id"] for v in findings] == [10]
    assert findings[0]["rule"] == "HT"
    assert [t["id"] for t in findings[0]["twins"]] == [900]
    assert findings[0]["twins"][0]["face"] == "jp"
    on_disk = json.loads((mini.d / "human_twins.json").read_text(encoding="utf-8"))
    assert on_disk["findings"] == findings
    assert on_disk["human_ids"] == [10]


def test_human_twin_scan_green_when_twin_synced(mini, tmp_path):
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: JP[10]},
        current={10: "【彩野】「人裁后的新译文」", 11: DEFAULT_ZH[11],
                 12: DEFAULT_ZH[12], 13: DEFAULT_ZH[13],
                 900: "【彩野】「人裁后的新译文」"})
    _write_decisions(mini, [
        {"id": 10, "verdict": "edit", "chosen_channel": "chA",
         "edited_zh": "【彩野】「人裁后的新译文」", "reason_code": "口调", "ts": "t1"},
    ])
    assert pcheck.human_twin_scan(mini.label, lane, repo=mini.root) == []


def test_human_twin_scan_bare_face_and_review_round(mini, tmp_path):
    """复核轮（同 id 二次裁决）也算人工面；剥壳孪生（换壳同句）同样在扫描面
    ——15758/15832 型分叉再加 e2f 换壳，两个盲区一次覆盖。"""
    shell_jp = "【≦彩野≧】≪うん、<前向性健忘,ぜんこうせいけんぼう>だよ≫"
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: shell_jp},
        current={10: "【彩野】「嗯，是<前向性健忘,顺行性遗忘>啦」", 11: DEFAULT_ZH[11],
                 12: DEFAULT_ZH[12], 13: DEFAULT_ZH[13],
                 900: "【≦彩野≧】≪嗯，是<前向性健忘,顺行性遗忘>哦≫"})
    _write_decisions(mini, [
        {"id": 10, "verdict": "adopt", "chosen_channel": "chA",
         "edited_zh": None, "reason_code": "其他", "ts": "t1"},
        {"id": 10, "verdict": "edit", "chosen_channel": "chA",
         "edited_zh": "【彩野】「嗯，是<前向性健忘,顺行性遗忘>啦」",
         "reason_code": "口调", "ts": "t2"},
    ])
    findings = pcheck.human_twin_scan(mini.label, lane, repo=mini.root)
    assert [v["id"] for v in findings] == [10]
    assert [(t["id"], t["face"]) for t in findings[0]["twins"]] == [(900, "bare")]


def test_human_twin_scan_ignores_machine_only_rows(mini, tmp_path):
    """只有单条机裁 adopt（无 edit、无复核轮）的行不属于人工面——不扫。"""
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: JP[10]},
        current={10: "【彩野】「机裁采纳的译文」", 11: DEFAULT_ZH[11],
                 12: DEFAULT_ZH[12], 13: DEFAULT_ZH[13], 900: DEFAULT_ZH[10]})
    _write_decisions(mini, [
        {"id": 10, "verdict": "adopt", "chosen_channel": "chA",
         "edited_zh": None, "reason_code": "其他", "ts": "t1"},
    ])
    assert pcheck.human_twin_scan(mini.label, lane, repo=mini.root) == []


def test_human_twin_scan_unavailable_without_decisions(mini, tmp_path):
    lane = _build_lane(tmp_path, ledger={10: JP[10]}, current={10: DEFAULT_ZH[10]})
    with pytest.raises(pcheck.W4NotAvailable):
        pcheck.human_twin_scan(mini.label, lane, repo=mini.root)


def test_cli_human_twins(mini, tmp_path, capsys):
    lane = _build_lane(
        tmp_path,
        ledger={10: JP[10], 11: JP[11], 12: JP[12], 13: JP[13], 900: JP[10]},
        current={10: "【彩野】「人裁后的新译文」", 11: DEFAULT_ZH[11],
                 12: DEFAULT_ZH[12], 13: DEFAULT_ZH[13], 900: DEFAULT_ZH[10]})
    _write_decisions(mini, [
        {"id": 10, "verdict": "edit", "chosen_channel": "chA",
         "edited_zh": "【彩野】「人裁后的新译文」", "reason_code": "口调", "ts": "t1"},
    ])
    rc = pcheck.main(["--seg", mini.label, "--human-twins",
                       "--lane-dir", str(lane), "--repo", str(mini.root)])
    assert rc == 0
    out = capsys.readouterr()
    assert "孪生未同步 1 处" in out.out


# --- P5 工装：冻结面漂移体检（lane_drift） ---

def test_lane_drift_reports_post_freeze_changes(mini, tmp_path):
    """冻结后车道又改过的行报出，并带上该 id 的候选提案（真风险面）。"""
    lane = _build_lane(tmp_path, ledger={i: JP[i] for i in JP},
                        current={**DEFAULT_ZH, 10: "冻结之后被改成的新译文"})
    findings = pcheck.lane_drift(mini.label, lane, repo=mini.root)
    assert [v["id"] for v in findings] == [10]
    assert findings[0]["current_zh"] == "冻结之后被改成的新译文"
    assert findings[0]["frozen_zh"] == DEFAULT_ZH[10]
    # 该 id 上确有候选（mini 夹具已入仓 chA 候选）→ proposals 非空
    assert [p["channel"] for p in findings[0]["proposals"]] == ["chA"]
    on_disk = json.loads((mini.d / "lane_drift.json").read_text(encoding="utf-8"))
    assert on_disk["drifted"] == 1


def test_lane_drift_green_when_lane_matches_freeze(mini, tmp_path):
    lane = _build_lane(tmp_path, ledger={i: JP[i] for i in JP}, current=dict(DEFAULT_ZH))
    assert pcheck.lane_drift(mini.label, lane, repo=mini.root) == []


def test_lane_drift_unavailable_without_freeze(tmp_path):
    lane = _build_lane(tmp_path, ledger={10: JP[10]}, current={10: DEFAULT_ZH[10]})
    with pytest.raises(pcheck.W4NotAvailable):
        pcheck.lane_drift("no-such-seg", lane, repo=tmp_path / "repo")


def test_cli_lane_drift(mini, tmp_path, capsys):
    lane = _build_lane(tmp_path, ledger={i: JP[i] for i in JP},
                        current={**DEFAULT_ZH, 10: "冻结之后被改成的新译文"})
    rc = pcheck.main(["--seg", mini.label, "--lane-drift",
                       "--lane-dir", str(lane), "--repo", str(mini.root)])
    assert rc == 0
    out = capsys.readouterr()
    assert "冻结后车道已变 1 行" in out.out
    assert "裁决须按现行文本重判" in out.err


# --- W5：『』保真（P5 追加） ---

def test_quote_drift_unit_cases():
    """三类：没动（绿）/ 删掉译者补的引号回到原文（绿）/ 删掉原文自带的（报）。"""
    # 没动
    assert pcheck.quote_drift(1, "それは『落書き』だ", "那是『涂鸦』", "那是『涂鸦』") == []
    # 译者多补的引号被删回原文一致（p5seg0 #6268 型）——合法
    assert pcheck.quote_drift(2, "キオクを眺める", "眺望着记忆", "眺望着『记忆』") == []
    # 原文自带的引号被删（p5seg0 #6542 型）——报
    v = pcheck.quote_drift(3, "それは『落書き』だ", "那是涂鸦", "那是『涂鸦』")
    assert len(v) == 1 and v[0]["rule"] == "W5"
    # 凭空加引号且原文没有——报
    v2 = pcheck.quote_drift(4, "落書きだ", "那是『涂鸦』", "那是涂鸦")
    assert len(v2) == 1


def test_gate_reports_w5_as_warn(mini):
    """W5 走 warn 不走 hard——正当删除存在，不阻断流水线。"""
    append_jsonl(mini.d / "candidates.chA.jsonl", [{
        "id": 12, "channel": "chA", "batch": 1, "prompt_hash": "h",
        "jp_hash": "x", "opus_hash": "x",
        "zh": "删掉了原文自带引号的候选", "score": 60, "note": "", "adjudicate": False,
        "jp_tail": jp_tail(JP[12]), "ts": "t-w5",
    }])
    # 让 frozen 的 jp/opus 都含一对『』，候选不含 → W5 命中
    fz = mini.d / "frozen"
    src = [dict(r) for r in read_jsonl(fz / "source.jsonl")]
    for r in src:
        if r["id"] == 12: r["jp"] = "これは『落書き』だ"
    write_jsonl(fz / "source.jsonl", src)
    op = [dict(r) for r in read_jsonl(fz / "opus.jsonl")]
    for r in op:
        if r["id"] == 12: r["zh"] = "这是『涂鸦』"
    write_jsonl(fz / "opus.jsonl", op)
    g = pcheck.gate(mini.label, "chA", repo=mini.root)
    f12 = g["findings"].get(12, {"hard": [], "warn": []})
    assert "W5" in [w["rule"] for w in f12["warn"]]   # W3 行宽同时命中，不排斥
    assert f12["hard"] == []
