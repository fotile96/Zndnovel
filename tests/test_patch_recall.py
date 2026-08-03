import json
from tools.add_patch import add
from tools.recall import find
from tools.pipelib import write_jsonl, read_jsonl

def test_add_patch_appends(tmp_path):
    d = tmp_path; (d / "data").mkdir()
    add(5, "新译", "review", 4, ts="t", data=d / "data")
    add(5, "更新译", "review", 4, ts="t2", data=d / "data")
    rows = read_jsonl(d / "data" / "patches.jsonl")
    assert [r["zh"] for r in rows] == ["新译", "更新译"]

# ---------------------------------------------------------------------------
# 车道模式护栏（2026-08-02 生产事故）：4 条回改被静默写进主仓 data/patches.jsonl，
# 命令零报错、退出码 0，生产车道一条都没生效。缺省路径在车道模式下几乎总是错的，
# 且写错完全静默——本项目的原则是「静默写错比报错更坏」。
# ---------------------------------------------------------------------------

def _fake_repo_with_lane(tmp_path, monkeypatch, *, lanes=("opus",)):
    """造一个含 pilot/lanes/<lane>/data/ 的假仓库，并把 add_patch 的 REPO/DATA
    指过去（DATA 指主仓 data/，即事故里被误写的那个目录）。"""
    import tools.add_patch as A
    for name in lanes:
        (tmp_path / "pilot" / "lanes" / name / "data").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(A, "REPO", tmp_path)
    monkeypatch.setattr(A, "DATA", tmp_path / "data")
    monkeypatch.delenv("ZND_DATA", raising=False)
    return A


def test_add_patch_refuses_in_lane_mode_without_data_dir(tmp_path, monkeypatch):
    """判别性用例：车道存在且未给 --data-dir 时必须拒绝，且**不写任何文件**。
    改前这条命令会静默创建并写入主仓 data/patches.jsonl，退出码 0。"""
    import pytest
    A = _fake_repo_with_lane(tmp_path, monkeypatch)
    before = sorted(p for p in tmp_path.rglob("*") if p.is_file())
    with pytest.raises(SystemExit) as e:
        A.main(["--id", "7327", "--zh", "新译", "--reason", "review",
                "--glossary-v", "9"])
    # 退出码非 0，且提示里给出可直接照抄的车道路径。
    assert e.value.code != 0
    assert "pilot/lanes/opus/data" in str(e.value.code)
    # 一个文件都没有新增——尤其没有凭空造出 data/patches.jsonl。
    assert sorted(p for p in tmp_path.rglob("*") if p.is_file()) == before
    assert not (tmp_path / "data" / "patches.jsonl").exists()


def test_add_patch_writes_when_data_dir_explicit_in_lane_mode(tmp_path, monkeypatch):
    """显式给了 --data-dir 就正常写入车道，且不碰主仓 data/。"""
    A = _fake_repo_with_lane(tmp_path, monkeypatch)
    lane_data = tmp_path / "pilot" / "lanes" / "opus" / "data"
    rc = A.main(["--id", "7327", "--zh", "新译", "--reason", "review",
                 "--glossary-v", "9", "--data-dir", str(lane_data)])
    assert rc == 0
    rows = read_jsonl(lane_data / "patches.jsonl")
    assert [r["id"] for r in rows] == [7327] and rows[0]["zh"] == "新译"
    assert not (tmp_path / "data" / "patches.jsonl").exists()


def test_add_patch_accepts_znd_data_as_explicit_choice(tmp_path, monkeypatch):
    """生产命令形态是 `ZND_DATA=<lane>/data uv run python tools/...`——环境变量
    同样是「显式选定」，不得被护栏挡下。"""
    A = _fake_repo_with_lane(tmp_path, monkeypatch)
    lane_data = tmp_path / "pilot" / "lanes" / "opus" / "data"
    monkeypatch.setenv("ZND_DATA", str(lane_data))
    monkeypatch.setattr(A, "DATA", lane_data)  # 进程启动时 pipelib 已据此解析
    assert A.main(["--id", "1", "--zh", "z", "--reason", "review",
                   "--glossary-v", "9"]) == 0
    assert read_jsonl(lane_data / "patches.jsonl")[0]["id"] == 1


def test_add_patch_non_lane_repo_keeps_default_behaviour(tmp_path, monkeypatch):
    """非车道仓库（没有 pilot/lanes/*/data/）行为完全不变：缺省照旧落 DATA。
    护栏不得把历史用法弄坏。"""
    import tools.add_patch as A
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(A, "REPO", tmp_path)
    monkeypatch.setattr(A, "DATA", tmp_path / "data")
    monkeypatch.delenv("ZND_DATA", raising=False)
    assert A.main(["--id", "9", "--zh", "z", "--reason", "polish",
                   "--glossary-v", "9"]) == 0
    assert read_jsonl(tmp_path / "data" / "patches.jsonl")[0]["id"] == 9


def test_add_patch_lane_dirs_listed_in_refusal(tmp_path, monkeypatch):
    """多车道时提示里列出全部候选，控制器不用自己去猜路径。"""
    import pytest
    A = _fake_repo_with_lane(tmp_path, monkeypatch, lanes=("fable", "opus"))
    with pytest.raises(SystemExit) as e:
        A.main(["--id", "1", "--zh", "z", "--reason", "review", "--glossary-v", "9"])
    msg = str(e.value.code)
    assert "fable" in msg and "opus" in msg


def test_add_patch_library_add_unaffected_by_guard(tmp_path, monkeypatch):
    """闸只在 CLI 层：库函数 add() 的既有语义（含默认落 DATA）不变。"""
    A = _fake_repo_with_lane(tmp_path, monkeypatch)
    A.add(3, "z", "review", 9, ts="t", data=tmp_path / "data")
    assert read_jsonl(tmp_path / "data" / "patches.jsonl")[0]["id"] == 3


def test_recall_finds_stale_rows(tmp_path):
    d = tmp_path; (d / "data").mkdir()
    write_jsonl(d / "data" / "ledger.jsonl", [
        {"id": 1, "jp": "彼女の手帳を見た", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"},
        {"id": 2, "jp": "無関係の行", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"}])
    write_jsonl(d / "data" / "forward.jsonl", [
        {"id": 1, "zh": "看了她的手帐", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"},
        {"id": 2, "zh": "无关", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"}])
    hits = find(term="手帳", glossary_v=2, data=d / "data")
    assert [h["id"] for h in hits] == [1]

# ---------------------------------------------------------------------------
# Park 项 B：recall 按「生效译文」的术语表版本判断陈旧（与 resolve 的覆盖语义
# 一致——forward 先铺、patches 后写覆盖，同 id 多条 patch 取最后一条），不再
# 只看 forward 自身的 glossary_v。
# ---------------------------------------------------------------------------

def test_recall_excludes_id_patched_to_newer_version(tmp_path):
    """判别性用例（brief B 测试列表第 1 条）：id=1 首译在 v1，之后被 patch 到
    v2——生效版本是 2，不是 forward 自身的 1。find(glossary_v=2) 不应再召回它
    （2 >= 2）；同一夹具下 find(glossary_v=3) 仍应召回（生效版本 2 < 3）。只看
    forward.glossary_v（改前的行为）会让 v=2 这次查询也召回它（1 < 2），本用例
    对此有判别力：去掉"生效版本"逻辑、退回只读 forward.glossary_v，本测试
    在 glossary_v=2 这个断言上必红。"""
    d = tmp_path; (d / "data").mkdir()
    write_jsonl(d / "data" / "ledger.jsonl", [
        {"id": 1, "jp": "彼女の手帳を見た", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"}])
    write_jsonl(d / "data" / "forward.jsonl", [
        {"id": 1, "zh": "旧译一", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"}])
    write_jsonl(d / "data" / "patches.jsonl", [
        {"id": 1, "zh": "新译一", "reason": "review", "glossary_v": 2, "ts": "t2"}])
    assert find(term="手帳", glossary_v=2, data=d / "data") == []
    hits = find(term="手帳", glossary_v=3, data=d / "data")
    assert [h["id"] for h in hits] == [1]

def test_recall_uses_last_patch_when_multiple(tmp_path):
    """判别性用例（brief B 测试列表第 2 条）：同一 id 有多条 patch（append-only）
    时取最后一条。id=1 依次被 patch 到 v2、再到 v5——生效版本是 5，不是 2。
    find(glossary_v=3) 不应召回（5 >= 3）：若误取第一条 patch（v2），2 < 3 会
    被错误召回，本用例对"取最后一条"这条语义有判别力。find(glossary_v=6) 应
    召回，且 zh 取最后一条 patch 的值。"""
    d = tmp_path; (d / "data").mkdir()
    write_jsonl(d / "data" / "ledger.jsonl", [
        {"id": 1, "jp": "彼女の手帳を見た", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"}])
    write_jsonl(d / "data" / "forward.jsonl", [
        {"id": 1, "zh": "首译", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"}])
    write_jsonl(d / "data" / "patches.jsonl", [
        {"id": 1, "zh": "patch1", "reason": "review", "glossary_v": 2, "ts": "t2"},
        {"id": 1, "zh": "patch2", "reason": "polish", "glossary_v": 5, "ts": "t3"}])
    assert find(term="手帳", glossary_v=3, data=d / "data") == []
    hits = find(term="手帳", glossary_v=6, data=d / "data")
    assert [h["id"] for h in hits] == [1]
    assert hits[0]["zh"] == "patch2"

def test_recall_hit_zh_is_effective_translation_not_forward(tmp_path):
    """判别性用例（brief B 测试列表第 4 条）：召回条目的 zh 必须是生效译文——
    有 patch 时是最后一条 patch 的 zh，不是 forward 的。patch 的 glossary_v
    与 forward 相同（都是 1），刻意让"版本判断"逻辑对新旧实现给出相同的召回
    结果（both < 2 → 都会召回），只有"zh 取哪一份"这一点不同——把这条判断
    与"生效版本"判断解耦：若 zh 仍从 forward 行取（未接入 patches 的 zh），
    本测试必红。"""
    d = tmp_path; (d / "data").mkdir()
    write_jsonl(d / "data" / "ledger.jsonl", [
        {"id": 1, "jp": "彼女の手帳を見た", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"}])
    write_jsonl(d / "data" / "forward.jsonl", [
        {"id": 1, "zh": "旧译", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"}])
    write_jsonl(d / "data" / "patches.jsonl", [
        {"id": 1, "zh": "新译", "reason": "review", "glossary_v": 1, "ts": "t2"}])
    hits = find(term="手帳", glossary_v=2, data=d / "data")
    assert [h["id"] for h in hits] == [1]
    assert hits[0]["zh"] == "新译"


# ---- P1c 硬化：recall --emit-batch 的 term 路径净化 ----

def test_recall_emit_batch_sanitizes_term_path(tmp_path, monkeypatch):
    """term 含路径分隔符/上跳段时，产物必须留在 work/recall/ 内。"""
    import tools.recall as recall
    work = tmp_path / "work"
    monkeypatch.setattr(recall, "WORK", work)
    data = tmp_path / "data"
    data.mkdir()
    (data / "ledger.jsonl").write_text("", encoding="utf-8")
    (data / "forward.jsonl").write_text("", encoding="utf-8")
    recall.main(["--glossary-v", "9", "--term", "../../etc/passwd",
                 "--data-dir", str(data), "--emit-batch"])
    escaped = [p for p in tmp_path.rglob("*passwd*")
               if work / "recall" not in p.parents]
    assert not escaped, f"产物逃出 work/recall/: {escaped}"
    produced = list((work / "recall").glob("*.jsonl"))
    assert len(produced) == 1
    assert "/" not in produced[0].name and ".." not in produced[0].name


def test_recall_emit_batch_keeps_plain_term_filename(tmp_path, monkeypatch):
    """常规术语（含日文/中文）文件名保持原样，不被净化改写。"""
    import tools.recall as recall
    work = tmp_path / "work"
    monkeypatch.setattr(recall, "WORK", work)
    data = tmp_path / "data"
    data.mkdir()
    (data / "ledger.jsonl").write_text("", encoding="utf-8")
    (data / "forward.jsonl").write_text("", encoding="utf-8")
    recall.main(["--glossary-v", "9", "--term", "帰りの歌",
                 "--data-dir", str(data), "--emit-batch"])
    assert (work / "recall" / "帰りの歌.jsonl").exists()
