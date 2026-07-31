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
