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
    (d / "glossary" / "voices").mkdir()
    (d / "glossary" / "voices" / "naoya.md").write_text("# 直哉口调", encoding="utf-8")
    (d / "glossary" / "voices" / "ayano.md").write_text("# 彩野口调", encoding="utf-8")
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
    assert set(h) == {"batches", "cards_zh", "anchors", "active", "glossary_max",
                       "style", "voices"}
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


def test_main_refuses_rerun_without_force_when_forward_exists(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    monkeypatch.setattr("tools.lane_setup.REPO", repo)
    monkeypatch.setattr("tools.lane_setup.LANES_ROOT", lanes)
    assert main(["--lane", "opus", "--model", "opus", "--effort", "max",
                 "--append-model-id", "claude-opus-5"]) == 0
    (lanes / "opus" / "data" / "forward.jsonl").write_text(
        '{"id":1,"zh":"x"}\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["--lane", "opus", "--model", "opus", "--effort", "max",
              "--append-model-id", "claude-opus-5"])
    assert main(["--lane", "opus", "--model", "opus", "--effort", "max",
                 "--append-model-id", "claude-opus-5", "--force"]) == 0


def test_verify_without_record_reports_and_does_not_raise(tmp_path):
    """setup 之后没跑 record 就直接 verify——manifest 不存在，须给出可诊断提示
    而非漂移误报为"无漂移"或抛异常。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    drift = verify(lanes, repo)
    assert drift == ["pilot-manifest.json 不存在——尚未记录冻结哈希"]


def test_setup_refuses_rerun_when_forward_exists(tmp_path):
    """试点中途重跑建车道命令必须被拦下——forward.jsonl 已存在说明该车道已经
    有真实译文进度，无条件 setup() 会用当前仓库状态重冻结 skeleton/glossary，
    抹掉原始基准且事后无法证明是否漂移过。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=lanes)
    (lane_dir / "data" / "forward.jsonl").write_text(
        '{"id":1,"zh":"x"}\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)


def test_setup_force_allows_rerun_when_forward_exists(tmp_path):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=lanes)
    (lane_dir / "data" / "forward.jsonl").write_text(
        '{"id":1,"zh":"x"}\n', encoding="utf-8")
    lane_dir2 = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                      lanes_root=lanes, force=True)
    assert lane_dir2 == lane_dir
    # force 重跑不得动 forward.jsonl 本身（那是真实译文，不是 setup() 的管辖范围）
    assert (lane_dir / "data" / "forward.jsonl").read_text(encoding="utf-8") == \
        '{"id":1,"zh":"x"}\n'


def test_record_refuses_to_overwrite_when_frozen_hash_changed_without_force(tmp_path):
    """record() 重跑：若某条车道已记录过、且当前实际哈希与记录不同，必须拒绝
    覆盖（没有 --force）——否则原始基准被静默重写，事后无法证明是否漂移过。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    (lanes / "opus" / "glossary" / "active.json").write_text(
        '{"a":"改了"}', encoding="utf-8")
    with pytest.raises(SystemExit):
        record(lanes, repo)


def test_record_force_overwrites_changed_hash(tmp_path):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    (lanes / "opus" / "glossary" / "active.json").write_text(
        '{"a":"改了"}', encoding="utf-8")
    merged = record(lanes, repo, force=True)
    assert merged["opus"] == freeze_hashes(lanes / "opus", repo)


def test_record_allows_adding_new_lane_without_force(tmp_path):
    """两条车道不是同时 setup 的——先 opus 后 fable，第二次 record() 必须能
    在不动 opus 已记录基准的前提下把 fable 加进去，不需要 --force。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    first = record(lanes, repo)
    setup("fable", "fable", "high", "claude-fable-5", repo=repo, lanes_root=lanes)
    second = record(lanes, repo)
    assert second["opus"] == first["opus"]
    assert "fable" in second


def test_record_rerun_with_unchanged_hashes_is_a_noop_without_force(tmp_path):
    """内容没变的情况下重跑 record()（没有 --force）不该报错——这是最常见的
    "再跑一次确认一下"操作，只有真的发生漂移才需要拦。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    first = record(lanes, repo)
    second = record(lanes, repo)
    assert first == second


def test_record_preserves_other_top_level_manifest_keys(tmp_path):
    """pilot-manifest.json 除 "lanes" 外还会人工写入 collapse_thresholds 等键
    （见 I-extra 修复）；record() 重跑不得把这些键清掉。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    mp = lanes / "pilot-manifest.json"
    doc = json.loads(mp.read_text(encoding="utf-8"))
    doc["collapse_thresholds"] = {"kana_max": 0.03}
    mp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    record(lanes, repo)
    doc2 = json.loads(mp.read_text(encoding="utf-8"))
    assert doc2["collapse_thresholds"] == {"kana_max": 0.03}


def test_verify_detects_cross_lane_glossary_mismatch(tmp_path):
    """两条车道若在仓库 glossary 变更前后分别 setup，各自 verify 都会通过
    （因为各自只跟自己 record() 时的哈希比）——但两条车道的术语基准已经不同，
    正是 spec §0「术语泄漏」要防的事。verify() 须新增跨车道一致性检查。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    (repo / "glossary" / "active.json").write_text(
        '{"a":"改过的"}', encoding="utf-8")
    setup("fable", "fable", "high", "claude-fable-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    drift = verify(lanes, repo)
    assert drift, "两条车道 active.json 冻结快照不同，必须报漂移"
    assert any("跨车道" in d for d in drift)


def test_verify_cross_lane_check_does_not_false_positive_on_matching_lanes(tmp_path):
    """两条车道冻结快照本就相同（正常流程：先后 setup 但仓库中途没变）时，
    跨车道检查不能误报。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    setup("fable", "fable", "high", "claude-fable-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    assert verify(lanes, repo) == []


def test_freeze_hashes_picks_highest_glossary_version_not_lexicographic(tmp_path):
    """v10 与 v6 并存时须选中 v10——防止将来误改成字典序比较（"v10" < "v6"）。"""
    repo = _repo(tmp_path)
    (repo / "glossary" / "glossary.v10.yaml").write_text("version: 10", encoding="utf-8")
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=tmp_path / "lanes")
    h = freeze_hashes(lane_dir, repo)
    assert h["glossary_max"] == sha256_file(lane_dir / "glossary" / "glossary.v10.yaml")


def test_record_skips_lane_with_missing_frozen_files_without_raising(tmp_path):
    """纯克隆场景（云端拿到的内容）：opus 已经在本地完整 setup，fable 只有入库
    的 lane.json（骨架/术语冻结拷贝尚未在本地重建，data/ 符号链接同样没有）。
    record() 扫描 lanes_root 下全部含 lane.json 的目录时会碰到 fable，
    freeze_hashes(fable) 必然因缺文件抛 FileNotFoundError——record() 不得让
    这个异常整条命令崩溃：须跳过 fable、正常记下 opus，且 manifest 里 fable
    若已有旧记录（此前某次成功 record() 留下的基准），不能被这次跳过抹掉。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    # 模拟入库的 pilot-manifest.json：fable 之前 record() 过，基准哈希已在案。
    stale_fable_record = {"batches": "a" * 64, "cards_zh": "b" * 64,
                           "anchors": "c" * 64, "active": "d" * 64,
                           "glossary_max": "e" * 64}
    (lanes / "pilot-manifest.json").write_text(
        json.dumps({"lanes": {"fable": stale_fable_record}}, ensure_ascii=False),
        encoding="utf-8")
    # fable 只有 lane.json——纯克隆里入库的三个文件之一，skeleton/glossary 未重建。
    (lanes / "fable").mkdir(parents=True, exist_ok=True)
    (lanes / "fable" / "lane.json").write_text(
        json.dumps({"lane": "fable"}, ensure_ascii=False), encoding="utf-8")

    merged = record(lanes, repo)  # 关键断言：不抛异常

    assert merged["opus"] == freeze_hashes(lanes / "opus", repo)
    assert merged["fable"] == stale_fable_record, \
        "跳过不得把车道从 manifest 里抹掉——既有记录须原样保留"


def test_record_skip_prints_diagnostic_to_stderr(tmp_path, capsys):
    """跳过车道时须向 stderr 打印可诊断提示，含车道名，方便云端会话定位。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    (lanes / "fable").mkdir(parents=True, exist_ok=True)
    (lanes / "fable" / "lane.json").write_text(
        json.dumps({"lane": "fable"}, ensure_ascii=False), encoding="utf-8")

    record(lanes, repo)

    err = capsys.readouterr().err
    assert "fable" in err


def test_verify_continues_checking_remaining_lanes_after_one_is_corrupted(tmp_path):
    """verify() 遇到一条损坏车道须继续查其余车道，不能提前收工——否则字典序
    靠后的车道即便有真实漂移也永远不会被报出。构造两条车道："fable"（字典序
    靠前，整个被删——命中 verify() 的 except FileNotFoundError 分支）与
    "opus"（字典序靠后，仅内容漂移——命中正常的 got[k] != v 比对分支）。
    manifest 按 record() 的 sorted(iterdir()) 顺序写入，故 fable 先于 opus
    被遍历：若 verify() 在 except 分支里误从 continue 退化成 return，只会报出
    fable、opus 永远查不到——正是本用例要钉住的回归。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("fable", "fable", "high", "claude-fable-5", repo=repo, lanes_root=lanes)
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    shutil.rmtree(lanes / "fable")
    (lanes / "opus" / "glossary" / "active.json").write_text('{"a":"改了"}',
                                                             encoding="utf-8")
    drift = verify(lanes, repo)
    assert any("fable" in d for d in drift), "损坏车道自身须报出"
    assert any("opus" in d for d in drift), \
        "损坏车道之后的车道也须被继续检查——若此断言失败，说明 verify() 遇坏车道就提前退出了"


def test_verify_detects_drift_in_style(tmp_path):
    """glossary/style.md 整篇渲染进 context.md 第四节、译者直接照做——必须在
    冻结集里，漂移了 verify() 须能抓住。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    (lanes / "opus" / "glossary" / "style.md").write_text(
        "# 风格（改过）", encoding="utf-8")
    drift = verify(lanes, repo)
    assert drift and any("style" in d for d in drift)


def test_verify_detects_drift_in_voices_file_content(tmp_path):
    """voices/ 下某份角色口调表内容被改——目录哈希须变化，verify() 须抓住。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    (lanes / "opus" / "glossary" / "voices" / "naoya.md").write_text(
        "# 直哉口调（改过）", encoding="utf-8")
    drift = verify(lanes, repo)
    assert drift and any("voices" in d for d in drift)


def test_freeze_hashes_voices_dir_hash_changes_on_rename_with_same_content(tmp_path):
    """只哈希文件内容会漏掉改名/增删文件：把 naoya.md 改名为 naoya2.md（内容
    不变）必须让 voices 哈希改变，否则说明目录哈希没把文件名纳入摘要。"""
    repo = _repo(tmp_path)
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=tmp_path / "lanes")
    before = freeze_hashes(lane_dir, repo)["voices"]
    voices = lane_dir / "glossary" / "voices"
    (voices / "naoya.md").rename(voices / "naoya2.md")
    after = freeze_hashes(lane_dir, repo)["voices"]
    assert before != after, "重命名文件（内容不变）必须改变 voices 目录哈希"


def test_freeze_hashes_voices_dir_hash_changes_on_added_file(tmp_path):
    """voices/ 下新增一份口调表（如新角色）必须让目录哈希改变。"""
    repo = _repo(tmp_path)
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=tmp_path / "lanes")
    before = freeze_hashes(lane_dir, repo)["voices"]
    (lane_dir / "glossary" / "voices" / "yuichi.md").write_text(
        "# ユウイチ口调", encoding="utf-8")
    after = freeze_hashes(lane_dir, repo)["voices"]
    assert before != after, "新增文件必须改变 voices 目录哈希"


def test_verify_detects_cross_lane_style_mismatch(tmp_path):
    """两条车道若在仓库 style.md 变更前后分别 setup，各自的自比都会通过，
    但风格基准已经不同——跨车道检查须抓住（spec §0「术语泄漏」的同类问题）。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    (repo / "glossary" / "style.md").write_text("# 风格（改过）", encoding="utf-8")
    setup("fable", "fable", "high", "claude-fable-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    drift = verify(lanes, repo)
    assert drift, "两条车道 style.md 冻结快照不同，必须报漂移"
    assert any("跨车道" in d and "style" in d for d in drift)


def test_verify_detects_cross_lane_voices_mismatch(tmp_path):
    """同上，换成 voices/ 目录：两条车道口调表基准不同必须被跨车道检查抓住。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    (repo / "glossary" / "voices" / "naoya.md").write_text(
        "# 直哉口调（改过）", encoding="utf-8")
    setup("fable", "fable", "high", "claude-fable-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    drift = verify(lanes, repo)
    assert drift, "两条车道 voices/ 冻结快照不同，必须报漂移"
    assert any("跨车道" in d and "voices" in d for d in drift)


def test_verify_flags_stale_manifest_missing_new_freeze_keys(tmp_path):
    """向后兼容场景：manifest 是旧版 freeze_hashes（只有 5 个键）留下的记录，
    没有 style/voices。verify() 遇到"记录的键集合是当前键集合的真子集"时，
    不得静默放行（否则新增的 style/voices 校验对所有存量车道形同虚设），
    也不该直接崩——须给出明确、可操作（提示重新冻结）的漂移描述。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=lanes)
    old_style_hashes = {k: v for k, v in freeze_hashes(lane_dir, repo).items()
                        if k not in ("style", "voices")}
    (lanes / "pilot-manifest.json").write_text(
        json.dumps({"lanes": {"opus": old_style_hashes}}, ensure_ascii=False),
        encoding="utf-8")
    drift = verify(lanes, repo)
    assert drift, "manifest 缺 style/voices 键时不得报「无漂移」"
    assert any("style" in d for d in drift) and any("voices" in d for d in drift), \
        "须明确点名缺失的键（style、voices），而不是笼统一句话"
    assert any("--force" in d or "force" in d for d in drift), \
        "须提示可操作的修复方式（重新冻结）"


def test_verify_stale_manifest_missing_keys_still_checks_keys_it_does_have(tmp_path):
    """manifest 缺新键的同时，旧键（如 active）也确实漂移了——两类问题都要报，
    缺键提示不能掩盖既有键的真实漂移。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=lanes)
    old_style_hashes = {k: v for k, v in freeze_hashes(lane_dir, repo).items()
                        if k not in ("style", "voices")}
    (lanes / "pilot-manifest.json").write_text(
        json.dumps({"lanes": {"opus": old_style_hashes}}, ensure_ascii=False),
        encoding="utf-8")
    (lanes / "opus" / "glossary" / "active.json").write_text(
        '{"a":"改了"}', encoding="utf-8")
    drift = verify(lanes, repo)
    assert any("active" in d for d in drift), \
        "manifest 缺新键不能掩盖旧键（active）的真实漂移"


def test_verify_reports_voices_anchors_content_mismatch(tmp_path):
    """verify() 的第三层检查：glossary/voices 示范译例与 skeleton/anchors.yaml
    定稿内容打架时必须被抓住——即便两份文件各自都没有"哈希漂移"（这层检查
    与 record() 是否跑过、manifest 是否存在都无关，见 tools/
    check_voices_anchors.py）。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    (repo / "skeleton" / "anchors.yaml").write_text(
        "- chapter: global\n"
        "  items:\n"
        "    - id: 10\n"
        '      zh: "【甲】「锚点定稿」"\n',
        encoding="utf-8")
    (repo / "glossary" / "voices" / "naoya.md").write_text(
        "1. [10]【甲】「にほんご」\n"
        "   → 【甲】「和定稿不同」\n",
        encoding="utf-8")
    drift = verify(lanes, repo)
    assert any("10" in d and "冲突" in d for d in drift)


def test_verify_voices_anchors_check_does_not_false_positive_when_consistent(tmp_path):
    """voices 示范译例与 anchors 定稿内容一致时，这层检查不能误报——正常流程
    （setup → record → verify）走一遍必须全绿。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    (repo / "skeleton" / "anchors.yaml").write_text(
        "- chapter: global\n"
        "  items:\n"
        "    - id: 10\n"
        '      zh: "【甲】「一致内容」"\n',
        encoding="utf-8")
    (repo / "glossary" / "voices" / "naoya.md").write_text(
        "1. [10]【甲】「にほんご」\n"
        "   → 【甲】「一致内容」\n",
        encoding="utf-8")
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    assert verify(lanes, repo) == []


def test_cross_lane_keys_includes_style_and_voices():
    """CROSS_LANE_KEYS 是两条车道应当彼此相同的冻结基准清单——style/voices
    与 cards_zh/anchors/active/glossary_max 同属此类，必须一并纳入。"""
    from tools.lane_setup import CROSS_LANE_KEYS
    assert set(CROSS_LANE_KEYS) == {"cards_zh", "anchors", "active",
                                     "glossary_max", "style", "voices"}


def test_stale_vs_repo_sees_what_verify_cannot(tmp_path):
    """仓库侧改了 style.md 而未重冻结：verify 无漂移，stale_vs_repo 必须报出。

    这一对断言是本用例的全部意义——只断言 stale 报了，不能证明它补上了
    verify 看不见的那一面（runbook §5 陷阱①）。
    """
    from tools.lane_setup import stale_vs_repo
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    (repo / "glossary" / "style.md").write_text("# 风格\n新增口径", encoding="utf-8")
    assert verify(lanes, repo) == [], "仓库侧改动不该被算作车道漂移"
    stale = stale_vs_repo(lanes, repo)
    assert any("style.md" in s and "落后" in s for s in stale), stale


def test_stale_vs_repo_quiet_when_lane_matches_repo(tmp_path):
    from tools.lane_setup import stale_vs_repo
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    assert stale_vs_repo(lanes, repo) == []


def test_stale_vs_repo_reports_repo_side_new_file(tmp_path):
    from tools.lane_setup import stale_vs_repo
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    (repo / "glossary" / "voices" / "chiaki.md").write_text("# 千秋", encoding="utf-8")
    assert any("chiaki.md" in s and "新增" in s for s in stale_vs_repo(lanes, repo))


def test_main_verify_prints_stale_block_but_still_exits_zero(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    (repo / "glossary" / "style.md").write_text("# 风格\n新增口径", encoding="utf-8")
    monkeypatch.setattr("tools.lane_setup.LANES_ROOT", lanes)
    monkeypatch.setattr("tools.lane_setup.REPO", repo)
    assert main(["--verify"]) == 0, "落后不是错误，退出码须仍为 0"
    out = capsys.readouterr().out
    assert "冻结校验：无漂移" in out
    assert "落后于仓库侧 1 处" in out and "style.md" in out, \
        "绿字必须伴随落后播报，否则「无漂移」会被读成「与仓库一致」"


def test_setup_freeze_exclude_omits_file_from_lane(tmp_path):
    repo = _repo(tmp_path)
    (repo / "glossary" / "style_refine.md").write_text("# 细则", encoding="utf-8")
    lanes = tmp_path / "lanes"
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes,
                     freeze_exclude=["glossary/style_refine.md"])
    assert not (lane_dir / "glossary" / "style_refine.md").exists()
    assert (lane_dir / "glossary" / "style.md").exists(), "只该少那一个文件"
    assert json.loads((lane_dir / "lane.json").read_text(encoding="utf-8")
                      )["freeze_exclude"] == ["glossary/style_refine.md"]


def test_refreeze_inherits_exclusion_without_being_told(tmp_path):
    """段边界重冻结不加参数也必须保持排除——靠记忆的纪律会衰减。"""
    repo = _repo(tmp_path)
    (repo / "glossary" / "style_refine.md").write_text("# 细则", encoding="utf-8")
    lanes = tmp_path / "lanes"
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes,
                     freeze_exclude=["glossary/style_refine.md"])
    (lane_dir / "data" / "forward.jsonl").write_text("{}\n", encoding="utf-8")
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes, force=True)
    assert not (lane_dir / "glossary" / "style_refine.md").exists(), \
        "重冻结未传 freeze_exclude 时必须继承，否则排除会被静默撤销"


def test_refreeze_with_empty_list_clears_exclusion(tmp_path):
    repo = _repo(tmp_path)
    (repo / "glossary" / "style_refine.md").write_text("# 细则", encoding="utf-8")
    lanes = tmp_path / "lanes"
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes,
                     freeze_exclude=["glossary/style_refine.md"])
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes,
          force=True, freeze_exclude=[])
    assert (lane_dir / "glossary" / "style_refine.md").exists(), \
        "显式传空列表须能解除排除（与「不传＝继承」区分开）"


def test_excluded_file_is_not_reported_as_stale_but_is_announced(tmp_path):
    from tools.lane_setup import stale_vs_repo, frozen_exclusions
    repo = _repo(tmp_path)
    (repo / "glossary" / "style_refine.md").write_text("# 细则", encoding="utf-8")
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes,
          freeze_exclude=["glossary/style_refine.md"])
    record(lanes, repo)
    assert not any("style_refine" in s for s in stale_vs_repo(lanes, repo)), \
        "有意排除不该算作「落后」，否则闸永远带着一条假警报"
    assert any("style_refine" in e and "有意排除" in e for e in frozen_exclusions(lanes)), \
        "但也不能因此消失——跳过等于藏起来"


def test_set_exclusions_records_intent_without_refreezing(tmp_path):
    """能在重冻结之前就把决定落盘，是这条路径存在的全部理由。"""
    from tools.lane_setup import set_exclusions, lane_exclusions
    repo = _repo(tmp_path)
    (repo / "glossary" / "style_refine.md").write_text("# 细则", encoding="utf-8")
    lanes = tmp_path / "lanes"
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    before = freeze_hashes(lane_dir, repo)
    assert (lane_dir / "glossary" / "style_refine.md").exists()
    removed = set_exclusions("opus", ["glossary/style_refine.md"], lanes)
    assert removed == ["glossary/style_refine.md"]
    assert not (lane_dir / "glossary" / "style_refine.md").exists()
    assert lane_exclusions(lane_dir) == ["glossary/style_refine.md"]
    assert freeze_hashes(lane_dir, repo) == before, "不得动冻结快照的任何哈希"


def test_setup_warns_when_excluded_path_absent(tmp_path, capsys):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes,
          freeze_exclude=["glossary/typo_refine.md"])
    assert "路径写错了" in capsys.readouterr().err, "排除项打错字必须出声"
