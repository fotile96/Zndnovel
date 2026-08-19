"""tools/polish_ingest.py：唯一入仓口的单测。

mini 夹具复用 `tools/polish_setup.setup()` 造真正的 `frozen/` 快照（比手搓
目录更可靠，见 task-4/5 brief 的补充说明），只是按测试需要控制 raw/plan.json
内容。全部测试都显式传 `repo=` 隔离到 tmp_path，绝不触碰真实仓库的
`pilot/polish/`。

夹具设计：2 批。
- batch 1：ids 10/11/12（非锁定）+ 13（锁定，anchor）。
- batch 2：ids 20/21/22（非锁定）+ 23（锁定，anchor）。
两批各自的 raw/chA/b{N}.out 基线都是"3 行非锁定 id，逐字照抄 opus，不锁定
id 不出现"——即模型规规矩矩符合契约的形态。plan.json 记两个会话，批 1→会话
1，批 2→会话 2，prompt_hash 各异。
"""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_ingest as pi
from tools import polish_setup as ps
from tools.pipelib import dumps, read_jsonl, write_jsonl
from tools.polishlib import jp_tail


def _sha256_text(s):
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


BATCHES = {
    1: {"plain": [10, 11, 12], "locked": 13, "session_hash": "hash-session-1"},
    2: {"plain": [20, 21, 22], "locked": 23, "session_hash": "hash-session-2"},
}


def _build_mini(tmp_path, label="segX", channel="chA"):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": label, "lane": "main", "batches": [1, 2],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")

    all_ids = {}
    batch_rows = []
    for b, spec in BATCHES.items():
        ids = list(spec["plain"]) + [spec["locked"]]
        batch_rows.append({"batch": b, "lane": "main", "ids": ids, "seqs": [b],
                            "jp_chars": len(ids), "chapter": "s2s", "cut_reason": "budget"})
        for i in ids:
            all_ids[i] = b
    write_jsonl(repo / "data" / "batches.jsonl", batch_rows)

    jp = {i: f"第{i}句测试原文本体テキスト" for i in all_ids}
    zh = {i: f"第{i}句译文" for i in all_ids}

    anchor_items = [{"id": spec["locked"], "jp": jp[spec["locked"]], "zh": zh[spec["locked"]],
                     "recall": "测试锚点"} for spec in BATCHES.values()]
    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([
        {"chapter": "global", "items": anchor_items},
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
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
        for i in all_ids
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": zh[i], "batch": all_ids[i], "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"}
        for i in all_ids
    ])
    # 两个锁定 id（13/23）同时落一条内容相同的 patch，使它们在新的硬锁/
    # 软锁分类下仍归为**硬锁**（patched 优先于 anchor，见 polish_setup._
    # locked_payload）——保留本文件既有测试对"锁定 id 一律不得出稿"的假设，
    # 不因锚点行改软锁而大范围改写。软锁专属行为见本文件下方的
    # `_build_mini_soft_lock` 夹具与相关测试。
    write_jsonl(opus_data / "patches.jsonl", [
        {"id": spec["locked"], "zh": zh[spec["locked"]], "reason": "review",
         "glossary_v": 1, "ts": "t"}
        for spec in BATCHES.values()
    ])

    d = ps.setup(label, opus_data, repo=repo)

    (d / "plan.json").write_text(dumps([
        {"session": b, "batches": [b], "prompt_hash": spec["session_hash"]}
        for b, spec in BATCHES.items()
    ]), encoding="utf-8")

    raw_dir = d / "raw" / channel
    raw_dir.mkdir(parents=True)
    for b, spec in BATCHES.items():
        lines = [dumps({"id": i, "jp_tail": jp_tail(jp[i]), "zh": zh[i],
                         "score": 90, "note": "", "adjudicate": False})
                 for i in spec["plain"]]
        (raw_dir / f"b{b}.out").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _rows(batch):
        p = raw_dir / f"b{batch}.out"
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def _save(batch, rows):
        p = raw_dir / f"b{batch}.out"
        p.write_text("\n".join(dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")

    def corrupt_tail(id, batch=1):
        rows = _rows(batch)
        for r in rows:
            if r["id"] == id:
                r["jp_tail"] = "坏尾串XX"
        _save(batch, rows)

    def add_locked_line(id, batch=1):
        rows = _rows(batch)
        rows.append({"id": id, "jp_tail": jp_tail(jp[id]), "zh": zh[id],
                     "score": 50, "note": "", "adjudicate": False})
        _save(batch, rows)

    def add_foreign_line(id, batch=1):
        rows = _rows(batch)
        rows.append({"id": id, "jp_tail": "不存在的尾串", "zh": "不知道哪来的",
                     "score": 10, "note": "", "adjudicate": False})
        _save(batch, rows)

    def drop_line(id, batch=1):
        rows = [r for r in _rows(batch) if r["id"] != id]
        _save(batch, rows)

    def dup_line(id, batch=1):
        rows = _rows(batch)
        target = next(r for r in rows if r["id"] == id)
        rows.append(dict(target))
        _save(batch, rows)

    def corrupt_json(batch=1):
        p = raw_dir / f"b{batch}.out"
        lines = p.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0][:-3] + "###NOTJSON"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def rotate_zh(batch=1):
        """评审 Critical 复现：批内每一行的 zh 都挂成"下一个 id"的 opus——
        id/jp_tail 全部自洽（同一行机械复制），只有 zh 内容错位挂到了别的
        原文上。ids=[10,11,12] 时：10 拿 11 的译文、11 拿 12 的、12 拿 10 的。
        """
        ids = BATCHES[batch]["plain"]
        rotated = ids[1:] + ids[:1]
        rows = [{"id": i, "jp_tail": jp_tail(jp[i]), "zh": zh[other],
                 "score": 90, "note": "", "adjudicate": False}
                for i, other in zip(ids, rotated)]
        _save(batch, rows)

    def blank_zh(id, batch=1):
        rows = _rows(batch)
        for r in rows:
            if r["id"] == id:
                r["zh"] = ""
        _save(batch, rows)

    def missing_zh_field(id, batch=1):
        rows = _rows(batch)
        for r in rows:
            if r["id"] == id:
                del r["zh"]
        _save(batch, rows)

    def set_zh_raw(id, value, batch=1):
        """评审 Important 复现：把某行的 zh 换成任意非字符串 JSON 值
        （int/bool/list/…）——`dumps()` 对这些类型完全合法，模拟模型输出
        "合法 JSON 但 zh 不是字符串"这种畸形行。"""
        rows = _rows(batch)
        for r in rows:
            if r["id"] == id:
                r["zh"] = value
        _save(batch, rows)

    return SimpleNamespace(
        root=repo, d=d, label=label, channel=channel, jp=jp, zh=zh, raw_dir=raw_dir,
        corrupt_tail=corrupt_tail, add_locked_line=add_locked_line,
        add_foreign_line=add_foreign_line, drop_line=drop_line, dup_line=dup_line,
        corrupt_json=corrupt_json, rotate_zh=rotate_zh, blank_zh=blank_zh,
        missing_zh_field=missing_zh_field, set_zh_raw=set_zh_raw,
    )


def _build_mini_recurrence(tmp_path, label="segR", channel="chA"):
    """专用夹具：单批 5 个非锁定 id，10/14/15 是"复现句族"——jp 完全相同。
    用来验证错位侦测的"jp 不同"限定确实在起作用，覆盖两种子情形：

    - id=14：raw 里"没改"（zh 逐字等于自身 opus，也逐字等于 10 的 opus）。
      这条即使去掉"jp 不同"限定也会先被 Finding B 的"zh==自身 opus"收窄
      挡住——不专门测 mutation A，但仍是合法场景的回归覆盖。
    - id=15：raw 里"改了"——`zh` 被（正当地）改成与 10/14 一致的现行译文，
      但它自身的历史 opus（forward.jsonl）是另一句旧译文，即
      `zh(15) != opus(15)` 但 `zh(15) == opus(10)`。这是**真正**只靠
      "jp 相同"这条限定才能免于误判的场景——`zh==自身 opus` 的收窄在这里
      不生效（两者不相等），所以专门用来验证"jp 不同"限定本身有牙
      （mutation A：去掉这条限定后，id=15 必须被误杀）。
    """
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids = [10, 11, 12, 14, 15]
    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": label, "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": ids, "seqs": [1], "jp_chars": len(ids),
         "chapter": "s2s", "cut_reason": "budget"},
    ])

    same_jp = "重复出现的同一句テキスト"
    jp = {10: same_jp, 14: same_jp, 15: same_jp,
          11: "第11句独立原文テキスト", 12: "第12句独立原文テキスト"}
    # opus（forward.jsonl 现行译文）：10/14 一致；15 是历史遗留的旧译文
    # （与 10/14 不同——尚未被这个复现句族"统一口径"）。
    opus_zh = {10: "重复句译文", 14: "重复句译文", 15: "重复句旧译文",
               11: "第11句译文", 12: "第12句译文"}
    # raw（模型本次输出的 zh）：10/11/12/14 全部"没改"；15 被正当地改成
    # 与 10/14 一致的现行译文（合理的复现句族口径统一），因此
    # raw_zh[15] != opus_zh[15]，但等于 opus_zh[10]。
    raw_zh = dict(opus_zh)
    raw_zh[15] = opus_zh[10]

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
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
        for i in ids
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": opus_zh[i], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"}
        for i in ids
    ])
    write_jsonl(opus_data / "patches.jsonl", [])

    d = ps.setup(label, opus_data, repo=repo)
    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-recurrence"},
    ]), encoding="utf-8")

    raw_dir = d / "raw" / channel
    raw_dir.mkdir(parents=True)
    lines = [dumps({"id": i, "jp_tail": jp_tail(jp[i]), "zh": raw_zh[i],
                    "score": 95, "note": "", "adjudicate": False}) for i in ids]
    (raw_dir / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return SimpleNamespace(root=repo, d=d, label=label, channel=channel, jp=jp, zh=opus_zh)


def _build_mini_short_collision(tmp_path, label="segS", channel="chA"):
    """专用夹具：评审 Finding B 的真实语料复现——两个**不同** jp 的短促应答
    句，opus 恰好收敛到同一个 zh（如"「ん」"/"「うん」"都译成"「嗯」"）。
    这**不是**复现句族（jp 不同，不受 W4 管辖），而是评审读真实
    ledger.jsonl/forward.jsonl/patches.jsonl 统计出的确定性伪报源：全库
    527 对"zh 相同、jp 不同"，缩到同批内仍有 21 对/38 个 id/约 5% 的批。

    raw 里两行都"不改"（zh 各自等于自身 opus）——这正是契约里最常见、最
    正确的动作。收窄前的错位判据会把这两行双双误杀；收窄后必须两行都
    正常入仓。"""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids = [10, 16]
    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": label, "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": ids, "seqs": [1], "jp_chars": len(ids),
         "chapter": "s2s", "cut_reason": "budget"},
    ])

    # 两个不同的短促应答原文，opus 恰好收敛成同一句译文——评审实测的真实
    # 语料形态（「ん」/「うん」→「嗯」）。
    jp = {10: "「ん」", 16: "「うん」"}
    zh = {10: "「嗯」", 16: "「嗯」"}

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
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
        for i in ids
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": zh[i], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"}
        for i in ids
    ])
    write_jsonl(opus_data / "patches.jsonl", [])

    d = ps.setup(label, opus_data, repo=repo)
    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-short-collision"},
    ]), encoding="utf-8")

    raw_dir = d / "raw" / channel
    raw_dir.mkdir(parents=True)
    # 两行都"不改"：zh 逐字等于各自的 opus。
    lines = [dumps({"id": i, "jp_tail": jp_tail(jp[i]), "zh": zh[i],
                    "score": 95, "note": "", "adjudicate": False}) for i in ids]
    (raw_dir / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return SimpleNamespace(root=repo, d=d, label=label, channel=channel, jp=jp, zh=zh)


@pytest.fixture
def mini(tmp_path):
    return _build_mini(tmp_path)


# --- brief Step 1 核心断言 ---

def test_ingest_ok_and_receipt(mini):
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 3
    rows = read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
    assert len(rows) == 3
    row10 = next(x for x in rows if x["id"] == 10)
    assert row10["jp_hash"] == _sha256_text(mini.jp[10])
    assert row10["opus_hash"] == _sha256_text(mini.zh[10])
    assert row10["channel"] == mini.channel
    assert row10["batch"] == 1
    assert row10["prompt_hash"] == "hash-session-1"
    assert "ts" in row10 and row10["ts"]
    assert not (mini.d / f"discipline.{mini.channel}.json").exists()


def test_bad_tail_kills_line_not_batch(mini):
    mini.corrupt_tail(id=11)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 2
    assert r["dead"][0]["id"] == 11
    ids_in = {row["id"] for row in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")}
    assert ids_in == {10, 12}


def test_locked_id_killed_and_disciplined(mini):
    mini.add_locked_line(id=13)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 3
    assert 13 in [d["id"] for d in r["dead"]]
    disc = json.loads((mini.d / f"discipline.{mini.channel}.json").read_text(encoding="utf-8"))
    assert disc["locked_hits"] == 1
    ids_in = {row["id"] for row in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")}
    assert 13 not in ids_in


def test_incomplete_coverage_fails_whole_batch(mini):
    mini.drop_line(id=12)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert not r["ok"]
    assert r["added"] == 0 and r["dead"] == []
    assert not (mini.d / f"candidates.{mini.channel}.jsonl").exists()
    assert not (mini.d / f"ingested.{mini.channel}.json").exists()


def test_idempotent(mini):
    r1 = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    r2 = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r1["added"] == 3
    assert r2["ok"] and r2["added"] == 0
    rows = read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
    assert len(rows) == 3


# --- 补充：三个自行裁定的设计点 ---

def test_foreign_id_killed_not_batch(mini):
    """id 根本不属于这个 SEG 的任何 id——判死，不影响批完整性。"""
    mini.add_foreign_line(id=999999)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 3
    assert any(d["id"] == 999999 and "不在批内" in d["reason"] for d in r["dead"])


def test_duplicate_id_kills_both_lines_but_batch_still_ok(mini):
    """重复 id：两行全部判死（不猜测取哪一条），但该 id 仍算"出现过"，
    不触发整批失败——duplicate 是错位信号，不是截断信号。"""
    mini.dup_line(id=11)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"]
    assert r["added"] == 2  # 10, 12 存活；11 的两行全死
    dead_ids = [d["id"] for d in r["dead"]]
    assert dead_ids.count(11) == 2
    assert all("重复" in d["reason"] for d in r["dead"] if d["id"] == 11)
    ids_in = {row["id"] for row in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")}
    assert ids_in == {10, 12}


def test_malformed_json_line_fails_whole_batch(mini):
    """单行不是合法 JSON——整批失败，不是只杀那一行（覆盖完整性判据失效）。"""
    mini.corrupt_json(batch=1)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert not r["ok"]
    assert r["added"] == 0 and r["dead"] == []
    assert not (mini.d / f"candidates.{mini.channel}.jsonl").exists()
    assert not (mini.d / f"ingested.{mini.channel}.json").exists()


def test_missing_plan_entry_fails_whole_batch_explicitly(mini):
    """batch 在 plan.json 里查不到所属会话——显式整批失败，不是静默填空串。"""
    (mini.d / "plan.json").write_text(dumps([
        {"session": 2, "batches": [2], "prompt_hash": "hash-session-2"},
    ]), encoding="utf-8")
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert not r["ok"]
    assert "plan.json" in r["reason"]
    assert not (mini.d / f"candidates.{mini.channel}.jsonl").exists()


def test_raw_file_missing_fails_whole_batch(mini):
    r = pi.ingest(mini.label, "chZ", 1, repo=mini.root)
    assert not r["ok"]
    assert "raw 文件不存在" in r["reason"]
    assert not (mini.d / "candidates.chZ.jsonl").exists()


def test_failed_batch_does_not_block_retry(mini):
    """整批失败不记 ingested——修好 raw 后重跑同一批应能正常入仓（这正是
    「幂等标记只记成功批」这条设计的价值：失败可安全重试）。"""
    mini.drop_line(id=12)
    r1 = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert not r1["ok"]

    # 修复：重新写回一份完整的合法批（模拟重跑模型/人工修正后的 raw）
    p = mini.raw_dir / "b1.out"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows.append({"id": 12, "jp_tail": jp_tail(mini.jp[12]), "zh": mini.zh[12],
                 "score": 90, "note": "", "adjudicate": False})
    p.write_text("\n".join(dumps(r) for r in rows) + "\n", encoding="utf-8")

    r2 = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r2["ok"] and r2["added"] == 3


def test_discipline_accumulates_across_batches(mini):
    """discipline.<channel>.json 的 locked_hits 是跨批累积计数，不是每次
    覆盖重写。"""
    mini.add_locked_line(id=13, batch=1)
    pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    mini.add_locked_line(id=23, batch=2)
    pi.ingest(mini.label, mini.channel, 2, repo=mini.root)
    disc = json.loads((mini.d / f"discipline.{mini.channel}.json").read_text(encoding="utf-8"))
    assert disc["locked_hits"] == 2


# --- 2026-08-07 用户裁定：锚点行从硬锁改软锁 ---

def _build_mini_soft_lock(tmp_path, label="segSoft", channel="chA"):
    """专用夹具：单批 3 个 id——10（普通）、20（软锁＝纯 anchor，不带
    patch）、30（同上，第二个软锁 id，用于批完整性/多行场景）。"""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids = [10, 20, 30]
    jp = {10: "第10句原文テキスト", 20: "锚点第20句原文テキスト",
          30: "锚点第30句原文テキスト"}
    opus = {10: "第10句译文", 20: "锚点第20句定译", 30: "锚点第30句定译"}

    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": label, "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": ids, "seqs": [1], "jp_chars": len(ids),
         "chapter": "s2s", "cut_reason": "budget"},
    ])
    # 20/30 只进 anchors.yaml，不落任何 patch——纯软锁。
    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([
        {"chapter": "global", "items": [
            {"id": 20, "jp": jp[20], "zh": opus[20], "recall": "软锁测试锚点20"},
            {"id": 30, "jp": jp[30], "zh": opus[30], "recall": "软锁测试锚点30"},
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
    assert locked["hard_ids"] == [] and set(locked["soft_ids"]) == {20, 30}

    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-soft"},
    ]), encoding="utf-8")

    return SimpleNamespace(root=repo, d=d, label=label, channel=channel, jp=jp, opus=opus)


def _write_soft_raw(m, rows_by_id):
    """rows_by_id: {id: {"zh":..., "adjudicate":...}}——10 一律照抄 opus
    （非锁定 id 必须出现且规规矩矩），20/30 按调用方给定内容出稿。"""
    raw_dir = m.d / "raw" / m.channel
    raw_dir.mkdir(parents=True, exist_ok=True)
    ids = [10, 20, 30]
    lines = []
    for i in ids:
        spec = rows_by_id.get(i, {"zh": m.opus[i], "adjudicate": False})
        row = {"id": i, "jp_tail": jp_tail(m.jp[i]), "zh": spec["zh"],
               "score": 90, "note": spec.get("note", ""),
               "adjudicate": spec.get("adjudicate", False)}
        if "alts" in spec:
            row["alts"] = spec["alts"]
        lines.append(dumps(row))
    (raw_dir / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def mini_soft(tmp_path):
    return _build_mini_soft_lock(tmp_path)


def test_soft_lock_unchanged_survives_no_special_treatment(mini_soft):
    """软锁行若 zh 逐字等于 opus（不改），正常入仓，不算违规。"""
    _write_soft_raw(mini_soft, {20: {"zh": mini_soft.opus[20]},
                                 30: {"zh": mini_soft.opus[30]}})
    r = pi.ingest(mini_soft.label, mini_soft.channel, 1, repo=mini_soft.root)
    assert r["ok"] and r["added"] == 3 and r["dead"] == []
    ids_in = {row["id"] for row in read_jsonl(mini_soft.d / f"candidates.{mini_soft.channel}.jsonl")}
    assert ids_in == {10, 20, 30}
    assert not (mini_soft.d / f"discipline.{mini_soft.channel}.json").exists()


def test_soft_lock_changed_with_adjudicate_survives(mini_soft):
    """软锁行改动 + adjudicate=true → 正常入仓（后续由 polish_triage 强制
    摘进裁决队列，本模块只负责放行）。"""
    _write_soft_raw(mini_soft, {
        20: {"zh": "改写后的第20句", "adjudicate": True, "note": "语感细则第5条更顺口"},
        30: {"zh": mini_soft.opus[30]},
    })
    r = pi.ingest(mini_soft.label, mini_soft.channel, 1, repo=mini_soft.root)
    assert r["ok"] and r["added"] == 3 and r["dead"] == []
    rows = read_jsonl(mini_soft.d / f"candidates.{mini_soft.channel}.jsonl")
    row20 = next(x for x in rows if x["id"] == 20)
    assert row20["zh"] == "改写后的第20句"
    assert row20["adjudicate"] is True
    assert not (mini_soft.d / f"discipline.{mini_soft.channel}.json").exists()


def test_soft_lock_changed_without_adjudicate_killed(mini_soft):
    """软锁行改动但没带 adjudicate=true → 判死，计入 soft_lock_violations
    （对应变异：若判死逻辑被删掉，这条会转红——"锚点被静默改动"是最该响
    的失败模式）。"""
    _write_soft_raw(mini_soft, {
        20: {"zh": "偷偷改写的第20句", "adjudicate": False},
        30: {"zh": mini_soft.opus[30]},
    })
    r = pi.ingest(mini_soft.label, mini_soft.channel, 1, repo=mini_soft.root)
    assert r["ok"] and r["added"] == 2
    assert any(d["id"] == 20 and "adjudicate" in d["reason"] for d in r["dead"])
    ids_in = {row["id"] for row in read_jsonl(mini_soft.d / f"candidates.{mini_soft.channel}.jsonl")}
    assert 20 not in ids_in
    disc = json.loads((mini_soft.d / f"discipline.{mini_soft.channel}.json").read_text(encoding="utf-8"))
    assert disc["soft_lock_violations"] == 1
    assert disc.get("locked_hits", 0) == 0   # 不是硬锁违规，不该混进这个计数


def test_soft_lock_id_must_still_appear_in_output(mini_soft):
    """软锁 id 不在"硬锁不得出稿"的豁免范围里——批完整性检查现在也要求
    软锁 id 出现一行；完全不提这个 id（截断/模型误以为不用管）应判整批
    失败，不能悄悄放过。"""
    raw_dir = mini_soft.d / "raw" / mini_soft.channel
    raw_dir.mkdir(parents=True, exist_ok=True)
    lines = [dumps({"id": 10, "jp_tail": jp_tail(mini_soft.jp[10]), "zh": mini_soft.opus[10],
                     "score": 90, "note": "", "adjudicate": False}),
              dumps({"id": 30, "jp_tail": jp_tail(mini_soft.jp[30]), "zh": mini_soft.opus[30],
                     "score": 90, "note": "", "adjudicate": False})]
    # 故意漏掉 id=20（软锁）——这在旧语义下是"锁定 id 本不该出现，漏了正常"，
    # 新语义下必须判整批失败。
    (raw_dir / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = pi.ingest(mini_soft.label, mini_soft.channel, 1, repo=mini_soft.root)
    assert not r["ok"]
    assert "覆盖不完整" in r["reason"]
    assert not (mini_soft.d / f"candidates.{mini_soft.channel}.jsonl").exists()


def test_legacy_locked_json_without_hard_soft_keys_treats_all_as_hard(mini_soft, monkeypatch):
    """向后兼容：SEG 冻结面改版之前落盘的旧格式 `locked.json`（没有
    `hard_ids`/`soft_ids` 键）——退化为把 `ids` 整体当硬锁，`soft_ids` 空。
    不能因为读到旧格式就意外放行本来不该出稿的锚点行。"""
    locked_path = mini_soft.d / "frozen" / "locked.json"
    old_locked = json.loads(locked_path.read_text(encoding="utf-8"))
    legacy = {"ids": old_locked["ids"], "why": old_locked["why"]}  # 无 hard_ids/soft_ids
    locked_path.write_text(dumps(legacy), encoding="utf-8")

    _write_soft_raw(mini_soft, {20: {"zh": "改写后的第20句", "adjudicate": True}})
    r = pi.ingest(mini_soft.label, mini_soft.channel, 1, repo=mini_soft.root)
    assert r["ok"] and r["added"] == 1   # 只有 10 存活；20/30 都被当硬锁判死
    ids_in = {row["id"] for row in read_jsonl(mini_soft.d / f"candidates.{mini_soft.channel}.jsonl")}
    assert ids_in == {10}
    assert any(d["id"] == 20 and "硬锁" in d["reason"] for d in r["dead"])


# --- 评审 Critical 修复轮：zh↔jp 错位侦测 + 空 zh 判死 ---

@pytest.fixture
def mini_recurrence(tmp_path):
    return _build_mini_recurrence(tmp_path)


def test_misaligned_zh_rotation_all_dead(mini):
    """评审自己构造的对抗输入复现：三行 id/jp_tail 全部自洽（同一行机械
    复制，逐项核验全过），但 zh 内容整体轮转错位到"下一个 id"的 opus 上。
    三行必须全部判死，一行都不能入仓。"""
    mini.rotate_zh(batch=1)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"]  # 覆盖完整性没问题（三行都出现过），只是内容全部判死
    assert r["added"] == 0
    assert len(r["dead"]) == 3
    assert {d["id"] for d in r["dead"]} == {10, 11, 12}
    assert all("错位" in d["reason"] for d in r["dead"])
    # 整批仍算"成功"（覆盖完整、只是内容判死），append_jsonl 对空列表也会
    # touch 出文件（`pipelib.append_jsonl` 以 "a" 模式打开）——断言的是"零行
    # 候选"，不是"文件不存在"（那是整批失败分支才有的语义，这里不适用）。
    assert read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl") == []
    disc = json.loads((mini.d / f"discipline.{mini.channel}.json").read_text(encoding="utf-8"))
    assert disc["misaligned_hits"] == 3


def test_recurrence_family_not_misaligned(mini_recurrence):
    """比错位侦测本身更要紧的回归锁：复现句族（同一 jp 对应同一 zh 的多个
    不同 id）绝不能被错杀。id=14 的 zh 与 id=10 的 opus 逐字相同（且未改动
    自身 opus）——Finding B 的"zh==自身 opus"收窄即可放行。**id=15 是更严格
    的用例**：它的 zh 被正当改写成与 10/14 一致的译文，与自身历史 opus
    不同（`zh(15) != opus(15)`），只有靠"jp 相同"这条限定本身才能免于
    误判——这条用例专门用来在 mutation A（去掉"jp 不同"限定）下真正转红，
    不会被 Finding B 的收窄意外掩盖。"""
    r = pi.ingest(mini_recurrence.label, mini_recurrence.channel, 1, repo=mini_recurrence.root)
    assert r["ok"] and r["added"] == 5 and r["dead"] == []
    ids_in = {row["id"] for row in read_jsonl(
        mini_recurrence.d / f"candidates.{mini_recurrence.channel}.jsonl")}
    assert ids_in == {10, 11, 12, 14, 15}
    assert not (mini_recurrence.d / f"discipline.{mini_recurrence.channel}.json").exists()


def test_empty_zh_string_killed(mini):
    mini.blank_zh(id=11)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 2
    assert any(d["id"] == 11 and "空" in d["reason"] for d in r["dead"])


def test_missing_zh_field_killed(mini):
    mini.missing_zh_field(id=12)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 2
    assert any(d["id"] == 12 and "空" in d["reason"] for d in r["dead"])


# --- 复审第二轮：Finding A（非字符串 zh 崩溃）+ Finding B（收窄，防短句伪报）---

@pytest.fixture
def mini_short_collision(tmp_path):
    return _build_mini_short_collision(tmp_path)


def test_non_string_zh_killed_not_crashed(mini):
    """评审 Important 复现：`{"id":11, "zh":12345}`——合法 JSON 但 zh 不是
    字符串。修复前会在 `_norm()` 里 `.strip()` 一个 int 直接崩溃
    （AttributeError 穿透 ingest()）；修复后须回到"该行判死、其余行照常
    入仓"的既有契约，不抛异常。"""
    mini.set_zh_raw(id=11, value=12345)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 2
    assert any(d["id"] == 11 and "类型" in d["reason"] for d in r["dead"])
    ids_in = {row["id"] for row in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")}
    assert ids_in == {10, 12}


def test_non_string_zh_variants_all_killed_not_crashed(mini):
    """bool/list 两种非字符串变体同样只判死不崩溃（int 已在上一条覆盖）。"""
    mini.set_zh_raw(id=11, value=True)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 2
    assert any(d["id"] == 11 for d in r["dead"])


def test_cli_all_survives_non_string_zh_in_one_batch(mini):
    """还原评审描述的真正风险场景：CLI `--all` 扫多个批，其中一批混入
    非字符串 zh。修复前会让整个 `--all` 扫描中断；修复后应正常扫完全部
    批，只是那一行判死。"""
    mini.set_zh_raw(id=11, value=[1, 2, 3], batch=1)
    rc = pi.main(["--seg", mini.label, "--channel", mini.channel, "--all",
                  "--repo", str(mini.root)])
    assert rc == 0
    ids_in = {row["id"] for row in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")}
    assert ids_in == {10, 12, 20, 21, 22}  # 11 判死；批 2 完全不受影响


def test_short_response_collision_not_misaligned(mini_short_collision):
    """评审 Finding B 复现（真实语料统计出的确定性伪报源）：两个不同 jp 的
    短促应答句（「ん」/「うん」），opus 恰好都收敛成「嗯」。两行在 raw 里
    都"不改"（zh 各自等于自身 opus）——必须两行都正常入仓，一行都不许死，
    也不该产生任何 discipline 记录。"""
    r = pi.ingest(mini_short_collision.label, mini_short_collision.channel, 1,
                  repo=mini_short_collision.root)
    assert r["ok"] and r["added"] == 2 and r["dead"] == []
    ids_in = {row["id"] for row in read_jsonl(
        mini_short_collision.d / f"candidates.{mini_short_collision.channel}.jsonl")}
    assert ids_in == {10, 16}
    assert not (mini_short_collision.d / f"discipline.{mini_short_collision.channel}.json").exists()


# --- CLI ---

def test_cli_single_batch(mini, capsys):
    rc = pi.main(["--seg", mini.label, "--channel", mini.channel, "--batch", "1",
                  "--repo", str(mini.root)])
    assert rc == 0
    rows = read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
    assert len(rows) == 3


def test_cli_bad_batch_returns_nonzero(mini):
    mini.drop_line(id=12)
    rc = pi.main(["--seg", mini.label, "--channel", mini.channel, "--batch", "1",
                  "--repo", str(mini.root)])
    assert rc == 1


def test_cli_all_scans_raw_dir(mini):
    rc = pi.main(["--seg", mini.label, "--channel", mini.channel, "--all",
                  "--repo", str(mini.root)])
    assert rc == 0
    rows1 = read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
    ids = {r["id"] for r in rows1}
    assert ids == {10, 11, 12, 20, 21, 22}
    ingested = json.loads((mini.d / f"ingested.{mini.channel}.json").read_text(encoding="utf-8"))
    assert set(ingested["batches"]) == {1, 2}


# --- _find_prompt_hash：channel 参数（评审 Task 9 Finding B 追加） ---
#
# `mini` fixture 的 plan.json 本就是两条"没有 channel 字段"的存量记录
# （{"session": b, "batches": [b], "prompt_hash": spec["session_hash"]}），
# 不需要另造夹具——这正是"存量数据"该有的样子。

def test_find_prompt_hash_backward_compatible_without_channel_field(mini):
    """存量 plan.json（记录里没有 `channel` 字段）——不管调用方传不传
    `channel`、传的是什么 channel，行为都必须与加这个参数之前逐位一致：
    按批号匹配第一条记录。"""
    plan_path = mini.d / "plan.json"
    assert pi._find_prompt_hash(plan_path, 1) == "hash-session-1"
    assert pi._find_prompt_hash(plan_path, 1, channel="chA") == "hash-session-1"
    assert pi._find_prompt_hash(plan_path, 1, channel="amplify") == "hash-session-1"
    assert pi._find_prompt_hash(plan_path, 2, channel="anything-else") == "hash-session-2"


def test_find_prompt_hash_prefers_channel_tagged_record(mini):
    """新增一条 `channel="amplify"` 的专属记录、覆盖与既有 chA 会话相同的
    批号——`channel="amplify"` 的查询必须精确命中这条新记录，而不是被列表
    顺序更靠前的旧记录挡住；普通 channel 的查询完全不受这条新记录干扰。"""
    plan_path = mini.d / "plan.json"
    records = json.loads(plan_path.read_text(encoding="utf-8"))
    records.append({"session": 99, "batches": [1], "prompt_hash": "hash-amplify-specific",
                     "channel": "amplify"})
    plan_path.write_text(dumps(records), encoding="utf-8")

    assert pi._find_prompt_hash(plan_path, 1, channel="amplify") == "hash-amplify-specific"
    assert pi._find_prompt_hash(plan_path, 1, channel="chA") == "hash-session-1"
    assert pi._find_prompt_hash(plan_path, 1) == "hash-session-1"


# --- P5 契约 v2：alts（备选候选）与 noop 标记 ---

def _edit_raw(mini, batch, mutate):
    """通用 raw 编辑器：读该批 raw 行 → mutate(rows) 就地改 → 回写。"""
    p = mini.raw_dir / f"b{batch}.out"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    mutate(rows)
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return rows

def test_alt_struct_bad_unit():
    """轻量结构闸的单元行为：【】对齐两方向 + MARKS 丢失。"""
    assert pi._alt_struct_bad("【彩野】「うん」", "「嗯」") == "【】说话人结构不对齐"
    assert pi._alt_struct_bad("うん", "【彩野】「嗯」") == "【】说话人结构不对齐"
    assert pi._alt_struct_bad("○夕方の教室。", "夕方教室。") == "丢失符号 ○"
    assert pi._alt_struct_bad("【彩野】「うん」", "【彩野】「嗯」") is None


def test_alts_accepted_and_stored(mini):
    def mut(rows):
        rows[0]["zh"] = "改后的主候选"
        rows[0]["alts"] = [{"zh": "备选甲", "note": "更口语"}, {"zh": "备选乙"}]
    rows = _edit_raw(mini, 1, mut)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 3
    row = next(x for x in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
               if x["id"] == rows[0]["id"])
    assert row["alts"] == [{"zh": "备选甲", "note": "更口语"}, {"zh": "备选乙", "note": ""}]
    assert row["noop"] is False


def test_alts_too_many_kills_line(mini):
    def mut(rows):
        rows[0]["alts"] = [{"zh": f"备{k}"} for k in range(3)]
    _edit_raw(mini, 1, mut)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 2
    assert any("alts 字段非法" in d["reason"] for d in r["dead"])


def test_alts_bad_item_kills_line(mini):
    def mut(rows):
        rows[0]["alts"] = [{"zh": 123}]
    _edit_raw(mini, 1, mut)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 2
    assert any("alts 第 1 条非法" in d["reason"] for d in r["dead"])


def test_alt_duplicate_of_main_dropped_line_survives(mini):
    def mut(rows):
        rows[0]["alts"] = [{"zh": rows[0]["zh"]}]  # 与主候选逐字相同
    rows = _edit_raw(mini, 1, mut)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 3
    row = next(x for x in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
               if x["id"] == rows[0]["id"])
    assert row["alts"] == []


def test_alt_struct_violation_dropped_and_disciplined(mini):
    """jp 无【】而备选擅自加【】→ 该备选丢弃并计 discipline，主候选存活。"""
    def mut(rows):
        rows[0]["zh"] = "改后的主候选"
        rows[0]["alts"] = [{"zh": "【彩野】「擅自加了前缀」"}]
    rows = _edit_raw(mini, 1, mut)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 3
    row = next(x for x in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
               if x["id"] == rows[0]["id"])
    assert row["alts"] == []
    disc = json.loads((mini.d / f"discipline.{mini.channel}.json").read_text(encoding="utf-8"))
    assert disc["alt_struct_violations"] == 1


def test_noop_flag_set_on_unchanged_row(mini):
    """照抄且无备选 → noop=True；照抄但带备选 → noop=False（有提案）。"""
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"]
    rows = read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
    assert all(x["noop"] is True for x in rows)  # mini 的 raw 全是照抄


def test_noop_false_when_alts_present(mini):
    def mut(rows):
        rows[0]["alts"] = [{"zh": "备选改法", "note": "n"}]
    rows = _edit_raw(mini, 1, mut)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"]
    row = next(x for x in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
               if x["id"] == rows[0]["id"])
    assert row["noop"] is False and row["alts"]


def test_soft_lock_alts_without_adjudicate_killed(mini_soft):
    """软锁行主候选照抄、备选里藏改法、未请裁 → 判死（堵契约 v2 新开的口）。"""
    _write_soft_raw(mini_soft, {
        20: {"zh": mini_soft.opus[20], "alts": [{"zh": "藏在备选里的改法"}]},
        30: {"zh": mini_soft.opus[30]},
    })
    r = pi.ingest(mini_soft.label, mini_soft.channel, 1, repo=mini_soft.root)
    assert r["ok"] and r["added"] == 2
    assert any("备选候选（alts）视同改动" in d["reason"] for d in r["dead"])


def test_soft_lock_alts_with_adjudicate_survives(mini_soft):
    _write_soft_raw(mini_soft, {
        20: {"zh": mini_soft.opus[20], "alts": [{"zh": "备选改法"}], "adjudicate": True},
        30: {"zh": mini_soft.opus[30]},
    })
    r = pi.ingest(mini_soft.label, mini_soft.channel, 1, repo=mini_soft.root)
    assert r["ok"] and r["added"] == 3 and r["dead"] == []
