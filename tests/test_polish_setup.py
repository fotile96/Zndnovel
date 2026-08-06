"""tools/polish_setup.py：SEG 冻结的单测。mini_repo 造一个 2 批 4 行 ledger、
1 条 anchor、1 条 patch 的替身仓库——不得触碰真实仓库的 pilot/polish/。"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_setup as ps
from tools.pipelib import read_jsonl, write_jsonl, dumps


def _mini_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 99, "label": "segX", "lane": "main", "batches": [1, 2],
         "chapters": ["s2s", "crd"], "jp_chars": 40, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")

    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": [10, 11], "seqs": [1],
         "jp_chars": 20, "chapter": "s2s", "cut_reason": "budget"},
        {"batch": 2, "lane": "main", "ids": [12, 13], "seqs": [2],
         "jp_chars": 20, "chapter": "crd", "cut_reason": "budget"},
    ])

    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([
        {"chapter": "global", "items": [
            {"id": 11, "jp": "锚点原文", "zh": "锚点定译", "recall": "测试锚点"},
        ]},
    ], allow_unicode=True), encoding="utf-8")

    (repo / "glossary" / "active.json").write_text('{"a":"啊"}', encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 润色细则", encoding="utf-8")
    (repo / "glossary" / "voices" / "naoya.md").write_text("# 直哉口调", encoding="utf-8")
    (repo / "glossary" / "glossary.v3.yaml").write_text("version: 3", encoding="utf-8")

    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", [
        {"id": 10, "jp": "第十句", "voice": "NONVOICE", "file": "snr_s2_10_s",
         "func": "f", "literal": False, "line": 1, "chapter": "s2s", "kind": "story"},
        {"id": 11, "jp": "第十一句", "voice": "NONVOICE", "file": "snr_s2_10_s",
         "func": "f", "literal": False, "line": 2, "chapter": "s2s", "kind": "story"},
        {"id": 12, "jp": "第十二句", "voice": "NONVOICE", "file": "snr_crd_1",
         "func": "f", "literal": False, "line": 3, "chapter": "crd", "kind": "story"},
        {"id": 13, "jp": "第十三句", "voice": "NONVOICE", "file": "snr_crd_1",
         "func": "f", "literal": False, "line": 4, "chapter": "crd", "kind": "story"},
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": 10, "zh": "译十", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 3, "ts": "t"},
        {"id": 11, "zh": "译十一", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 3, "ts": "t"},
        {"id": 12, "zh": "译十二", "batch": 2, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 3, "ts": "t"},
        {"id": 13, "zh": "补丁前文本", "batch": 2, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 3, "ts": "t"},
    ])
    write_jsonl(opus_data / "patches.jsonl", [
        {"id": 13, "zh": "补丁后文本", "reason": "recall", "glossary_v": 3, "ts": "t"},
    ])
    (opus_data / "notes" / "s2s.md").write_text("# s2s 纪要", encoding="utf-8")
    # 故意不建 crd.md：覆盖「某章无对应 notes 文件」分支。

    return SimpleNamespace(root=repo, opus_data=opus_data)


@pytest.fixture
def mini_repo(tmp_path):
    return _mini_repo(tmp_path)


def test_setup_freezes_and_locks(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    src = {r["id"] for r in read_jsonl(d / "frozen" / "source.jsonl")}
    assert src == {10, 11, 12, 13}
    locked = json.loads((d / "frozen" / "locked.json").read_text(encoding="utf-8"))
    assert set(locked["ids"]) == {11, 13}          # 11=anchor, 13=已有 patch
    assert locked["why"]["11"] == "anchor" and locked["why"]["13"] == "patched"
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert m["opus_at"]["patches_lines"] == 1


def test_opus_snapshot_is_resolved(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    opus = {r["id"]: r["zh"] for r in read_jsonl(d / "frozen" / "opus.jsonl")}
    assert opus[13] == "补丁后文本"                 # patch 覆盖 forward


def test_verify_detects_drift(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    assert ps.verify("segX", repo=mini_repo.root) == []
    (d / "frozen" / "opus.jsonl").write_text("坏", encoding="utf-8")
    assert ps.verify("segX", repo=mini_repo.root) != []


# --- 补充断言：brief 未覆盖但本任务明确要求的行为 ---

def test_setup_never_touches_real_repo(mini_repo):
    """安全网：setup() 必须尊重传入的 repo 参数，绝不落到真实仓库
    pilot/polish/ 下（若 seg_dir 漏传 repo 直接用全局 REPO，这条会失败）。"""
    from tools.pipelib import REPO
    ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    assert not (REPO / "pilot" / "polish" / "segX").exists()


def test_source_jsonl_carries_batch_number(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    by_id = {r["id"]: r for r in read_jsonl(d / "frozen" / "source.jsonl")}
    assert by_id[10]["batch"] == 1 and by_id[13]["batch"] == 2
    assert by_id[11]["jp"] == "第十一句"


def test_notes_copied_by_chapter_list_and_missing_one_is_reported(mini_repo):
    """按 chapters=[s2s, crd] 拷贝：s2s.md 存在应拷贝；crd.md 缺失应跳过且不
    静默——manifest 里须能看到缺失说明，日志（stderr）也须提示。"""
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    assert (d / "frozen" / "notes" / "s2s.md").exists()
    assert not (d / "frozen" / "notes" / "crd.md").exists()
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert "crd" in m.get("notes_missing", []), \
        "manifest 必须记录缺失的 notes 章节，不能悄悄跳过"


def test_notes_not_batch_numbered(mini_repo):
    """裁定点回归锁：notes/ 不是按批号取的（opus 车道 notes 是按章命名的
    25 个文件，没有批号维度）——冻结产物里不该出现任何形如 notes/1.md 的文件。"""
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    names = {p.name for p in (d / "frozen" / "notes").glob("*")}
    assert "1.md" not in names and "2.md" not in names

def test_glossary_snapshot_contains_expected_files(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    g = d / "frozen" / "glossary"
    assert (g / "active.json").exists()
    assert (g / "style.md").exists()
    assert (g / "polish.md").exists()
    assert (g / "voices" / "naoya.md").exists()
    assert (g / "anchors.yaml").exists()


def test_manifest_glossary_v_uses_highest_version(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert m["glossary_v"] == 3


def test_rulings_placeholder_created(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    assert (d / "frozen" / "rulings.md").exists()
    assert "segX" in (d / "frozen" / "rulings.md").read_text(encoding="utf-8")


def test_verify_missing_manifest_reports_not_raises(mini_repo):
    assert ps.verify("segX", repo=mini_repo.root) != []


def test_verify_missing_file_reported(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    (d / "frozen" / "opus.jsonl").unlink()
    drift = ps.verify("segX", repo=mini_repo.root)
    assert drift and any("opus.jsonl" in x for x in drift)


def test_verify_detects_unregistered_extra_file(mini_repo):
    """反向扫描：evidence 评审实测发现的漏洞——setup() 之后往 frozen/ 下按目录
    整体消费的位置（glossary/voices/、notes/）多丢一个 manifest 从未登记过的
    文件，只要不覆盖已登记文件名，纯正向核对（只查 manifest 里的文件是否存在/
    哈希对不对）永远看不见它。verify() 必须双向：也要反过来扫 frozen/ 实际
    目录树，把「磁盘上有、manifest 没登记」的文件计入 drift。"""
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    assert ps.verify("segX", repo=mini_repo.root) == []
    (d / "frozen" / "glossary" / "voices" / "sneaky_extra.md").write_text(
        "# 未经审的口调表", encoding="utf-8")
    drift = ps.verify("segX", repo=mini_repo.root)
    assert drift and any("sneaky_extra.md" in x for x in drift)


def test_verify_detects_unregistered_extra_notes_file(mini_repo):
    """同一漏洞的第二个复现位置（评审实测的另一半）：notes/ 下多出一份未登记
    的章节 notes（如误拷了一份未经审的 s3s.md）也必须被反向扫描抓住。"""
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    (d / "frozen" / "notes" / "s3s.md").write_text("# 误拷的章节纪要", encoding="utf-8")
    drift = ps.verify("segX", repo=mini_repo.root)
    assert drift and any("s3s.md" in x for x in drift)
