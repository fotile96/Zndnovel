import json
import shutil
import pytest
from tools.lane_setup import setup, freeze_hashes, record, verify, main
from tools.pipelib import sha256_file


def _repo(tmp_path):
    """替身仓库：只读数据 + skeleton/ + glossary/。"""
    d = tmp_path / "repo"
    (d / "data").mkdir(parents=True)
    (d / "skeleton").mkdir()
    (d / "glossary").mkdir()
    for name in ("ledger.jsonl", "ledger_extra.jsonl", "timeline.jsonl",
                 "batches.jsonl", "dag.json", "scene2card.json"):
        (d / "data" / name).write_text("{}\n", encoding="utf-8")
    (d / "skeleton" / "cards.zh.yaml").write_text("- {card: 1}\n", encoding="utf-8")
    (d / "skeleton" / "anchors.yaml").write_text("- {chapter: g, items: []}\n",
                                                 encoding="utf-8")
    (d / "glossary" / "active.json").write_text('{"a":"啊"}', encoding="utf-8")
    (d / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (d / "glossary" / "glossary.v6.yaml").write_text("version: 6", encoding="utf-8")
    return d


def test_setup_symlinks_data_and_copies_frozen_assets(tmp_path):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    assert (lane_dir / "data" / "ledger.jsonl").is_symlink(), "只读数据须为符号链接"
    assert (lane_dir / "data" / "timeline.jsonl").is_symlink()
    assert not (lane_dir / "skeleton" / "cards.zh.yaml").is_symlink(), \
        "skeleton 须为拷贝（冻结），不能是符号链接"
    assert not (lane_dir / "glossary" / "active.json").is_symlink(), \
        "glossary 须为拷贝（冻结），不能是符号链接"
    assert (lane_dir / "glossary" / "glossary.v6.yaml").exists()


def test_setup_writes_lane_config(tmp_path):
    repo = _repo(tmp_path)
    lane_dir = setup("fable", "fable", "high", "claude-fable-5", repo=repo,
                     lanes_root=tmp_path / "lanes")
    cfg = json.loads((lane_dir / "lane.json").read_text(encoding="utf-8"))
    assert cfg == {"lane": "fable", "lane_dir": str(lane_dir), "model": "fable",
                   "effort": "high", "append_model_id": "claude-fable-5"}


def test_setup_creates_no_forward_file(tmp_path):
    """车道的 forward.jsonl 由 append_forward 首次写入，setup 不得预建——
    预建空文件会让 build_context 把它当"已存在但无译文"，掩盖前缀空洞。"""
    repo = _repo(tmp_path)
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=tmp_path / "lanes")
    assert not (lane_dir / "data" / "forward.jsonl").exists()


def test_freeze_hashes_covers_the_frozen_set(tmp_path):
    repo = _repo(tmp_path)
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=tmp_path / "lanes")
    h = freeze_hashes(lane_dir, repo)
    assert set(h) == {"batches", "cards_zh", "anchors", "active", "glossary_max"}
    assert all(isinstance(v, str) and len(v) == 64 for v in h.values())


def test_verify_detects_drift_in_copied_glossary(tmp_path):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)          # verify 比对的是 record() 落下的基准，必须先记
    assert verify(lanes, repo) == []
    (lanes / "opus" / "glossary" / "active.json").write_text('{"a":"改了"}',
                                                             encoding="utf-8")
    drift = verify(lanes, repo)
    assert drift and any("active" in d for d in drift)


def test_verify_detects_drift_in_repo_batches(tmp_path):
    """batches.jsonl 被重切 → 两条车道的批号语义不再一致，必须拦下。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    (repo / "data" / "batches.jsonl").write_text('{"batch":1}\n', encoding="utf-8")
    drift = verify(lanes, repo)
    assert drift and any("batches" in d for d in drift)


def test_main_verify_exits_nonzero_on_drift(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    monkeypatch.setattr("tools.lane_setup.REPO", repo)
    monkeypatch.setattr("tools.lane_setup.LANES_ROOT", lanes)
    assert main(["--lane", "opus", "--model", "opus", "--effort", "max",
                 "--append-model-id", "claude-opus-5"]) == 0
    assert main(["--verify"]) == 0
    (lanes / "opus" / "skeleton" / "cards.zh.yaml").write_text("- {card: 2}\n",
                                                              encoding="utf-8")
    assert main(["--verify"]) == 1


def test_verify_reports_deleted_lane_without_raising(tmp_path):
    """整条车道目录被删（手滑 rm -rf）——verify 是漂移安全网，不能自己栈回溯。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    shutil.rmtree(lanes / "opus")
    drift = verify(lanes, repo)
    assert drift and any("opus" in d for d in drift)


def test_verify_reports_missing_frozen_file_without_raising(tmp_path):
    """车道内单个冻结文件被误删——同样必须落成漂移描述，不能抛异常。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    (lanes / "opus" / "glossary" / "active.json").unlink()
    drift = verify(lanes, repo)
    assert drift and any("opus" in d for d in drift)


def test_main_verify_returns_1_on_corrupted_lane(tmp_path, monkeypatch):
    """main(["--verify"]) 面对车道损坏须返回 1，不得把异常透传给调用方。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    monkeypatch.setattr("tools.lane_setup.REPO", repo)
    monkeypatch.setattr("tools.lane_setup.LANES_ROOT", lanes)
    assert main(["--lane", "opus", "--model", "opus", "--effort", "max",
                 "--append-model-id", "claude-opus-5"]) == 0
    shutil.rmtree(lanes / "opus")
    assert main(["--verify"]) == 1


def test_verify_without_record_reports_and_does_not_raise(tmp_path):
    """setup 之后没跑 record 就直接 verify——manifest 不存在，须给出可诊断提示
    而非漂移误报为"无漂移"或抛异常。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    drift = verify(lanes, repo)
    assert drift == ["pilot-manifest.json 不存在——尚未记录冻结哈希"]


def test_freeze_hashes_picks_highest_glossary_version_not_lexicographic(tmp_path):
    """v10 与 v6 并存时须选中 v10——防止将来误改成字典序比较（"v10" < "v6"）。"""
    repo = _repo(tmp_path)
    (repo / "glossary" / "glossary.v10.yaml").write_text("version: 10", encoding="utf-8")
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=tmp_path / "lanes")
    h = freeze_hashes(lane_dir, repo)
    assert h["glossary_max"] == sha256_file(lane_dir / "glossary" / "glossary.v10.yaml")
