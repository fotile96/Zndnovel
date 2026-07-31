"""三车道批次规划测试。"""
from tools.gen_batches import plan

TL = [
    {"seq": 1, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_10",
     "title": "一", "ids": [1, 2]},
    {"seq": 2, "type": "marker", "text": "【回溯】", "recap": ""},
    {"seq": 3, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_30",
     "title": "三", "ids": [3]},
    {"seq": 4, "type": "unit", "unit_kind": "scene", "src": "snr_b_10_s", "state": "b_10",
     "title": "换章", "ids": [4]},
]
LED = [
    {"id": 1, "jp": "あ" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
    {"id": 2, "jp": "い" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
    {"id": 3, "jp": "う" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f2"},
    {"id": 4, "jp": "え" * 30, "chapter": "b", "kind": "narrative", "file": "snr_b_10_s", "func": "f3"},
    {"id": 9, "jp": "お" * 10, "chapter": "sys", "kind": "ambient", "file": "snr_common", "func": "u1"},
]
EXTRA = [{"key": "snr_a_10_s:5", "jp": "题", "kind": "scene_title", "file": "snr_a_10_s"}]

def test_marker_and_chapter_cut():
    rows = plan(TL, LED, EXTRA, budget_chars=10**6)
    main = [r for r in rows if r["lane"] == "main"]
    assert [r["ids"] for r in main] == [[1, 2], [3], [4]]
    assert main[0]["cut_reason"] == "branch" and main[1]["cut_reason"] == "chapter"

def test_budget_cut_and_lanes():
    rows = plan(TL, LED, EXTRA, budget_chars=40)
    main = [r for r in rows if r["lane"] == "main"]
    assert [r["ids"] for r in main][:2] == [[1], [2]]      # 30字/行，40 预算下逐行成批
    assert any(r["lane"] == "ambient" and r["ids"] == [9] for r in rows)
    assert any(r["lane"] == "extra" for r in rows)

def test_batch_numbering_is_global_and_stable():
    rows = plan(TL, LED, EXTRA, budget_chars=10**6)
    assert [r["batch"] for r in rows] == list(range(1, len(rows) + 1))

def test_seqs_field_main_lane():
    """主车道批次应记录贡献的 unit seq（去重、升序）"""
    tl = [
        {"seq": 10, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_10",
         "title": "unit10", "ids": [1, 2]},
        {"seq": 11, "type": "marker", "text": "【b】", "recap": ""},
        {"seq": 12, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_30",
         "title": "unit12", "ids": [3]},
    ]
    led = [
        {"id": 1, "jp": "a" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
        {"id": 2, "jp": "b" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
        {"id": 3, "jp": "c" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f2"},
    ]
    rows = plan(tl, led, [], budget_chars=10**6)
    main = [r for r in rows if r["lane"] == "main"]
    assert main[0]["seqs"] == [10], f"First main batch should have seq [10], got {main[0]['seqs']}"
    assert main[1]["seqs"] == [12], f"Second main batch should have seq [12], got {main[1]['seqs']}"

def test_seqs_field_extra_ambient_lanes():
    """extra 和 ambient 车道的 seqs 应为空列表"""
    rows = plan(TL, LED, EXTRA, budget_chars=10**6)
    extra = [r for r in rows if r["lane"] == "extra"]
    ambient = [r for r in rows if r["lane"] == "ambient"]
    for r in extra + ambient:
        assert r["seqs"] == [], f"{r['lane']} batch should have empty seqs, got {r['seqs']}"

def test_ambient_grouping_by_filefunc():
    """ambient 车道应按 (file, func) 分组，同组尽量不跨批"""
    # 构造两个 ambient 组，第一组 5 字，第二组 15 字，budget 12
    # 这样第一组（5字）可以单独放在一批，第二组（15字）会超预算但整组放下一批
    tl = [
        {"seq": 1, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_10",
         "title": "u1", "ids": [1]},
    ]
    led = [
        {"id": 1, "jp": "a", "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
        # 第一组 (snr_common, v0.debagMsg) 5 字
        {"id": 10, "jp": "a" * 5, "chapter": "sys", "kind": "ambient", "file": "snr_common", "func": "v0.debagMsg"},
        # 第二组 (snr_common, v0.mesNG) 15 字，单个超过预算
        {"id": 11, "jp": "b" * 7, "chapter": "sys", "kind": "ambient", "file": "snr_common", "func": "v0.mesNG"},
        {"id": 12, "jp": "c" * 8, "chapter": "sys", "kind": "ambient", "file": "snr_common", "func": "v0.mesNG"},
    ]
    rows = plan(tl, led, [], budget_chars=12)
    ambient = [r for r in rows if r["lane"] == "ambient"]
    # 第一个 ambient 批应包含第一组（5 字）
    assert ambient[0]["ids"] == [10], f"First ambient batch should have [10], got {ambient[0]['ids']}"
    assert ambient[0]["jp_chars"] == 5, f"First batch chars should be 5, got {ambient[0]['jp_chars']}"
    # 第二个 ambient 批应包含第二组的两个 id（15 字总）
    assert ambient[1]["ids"] == [11, 12], f"Second ambient batch should have [11, 12], got {ambient[1]['ids']}"
    assert ambient[1]["jp_chars"] == 15, f"Second batch chars should be 15, got {ambient[1]['jp_chars']}"

def test_extra_jp_chars_calculated():
    """extra 车道的 jp_chars 应为该批所有 key 的 len(jp) 之和"""
    tl = [
        {"seq": 1, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_10",
         "title": "u1", "ids": [1]},
    ]
    led = [
        {"id": 1, "jp": "a", "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
    ]
    extra = [
        {"key": "snr_a_10_s:5", "jp": "題", "kind": "scene_title", "file": "snr_a_10_s"},
        {"key": "snr_a_10_s:6", "jp": "副題" * 3, "kind": "scene_title", "file": "snr_a_10_s"},
        {"key": "snr_b_10_s:7", "jp": "別ファイル", "kind": "scene_title", "file": "snr_b_10_s"},
    ]
    rows = plan(tl, led, extra, budget_chars=10**6)
    extra_batches = [r for r in rows if r["lane"] == "extra"]
    # 按 file 分组，应有 2 个 extra 批次
    assert len(extra_batches) == 2
    # snr_a_10_s: len("題") + len("副題" * 3) = 1 + 6 = 7 字
    assert extra_batches[0]["jp_chars"] == 7, f"First extra batch should have jp_chars=7, got {extra_batches[0]['jp_chars']}"
    # snr_b_10_s: len("別ファイル") = 5 字
    assert extra_batches[1]["jp_chars"] == 5, f"Second extra batch should have jp_chars=5, got {extra_batches[1]['jp_chars']}"

def test_empty_ids_unit_with_markers():
    """marker→empty ids unit→marker 序列不应产生空批或 chapter=None 的行"""
    tl = [
        {"seq": 226, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_10",
         "title": "前置", "ids": [1]},
        {"seq": 227, "type": "marker", "text": "【br1】", "recap": ""},
        {"seq": 228, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_20",
         "title": "空", "ids": []},
        {"seq": 229, "type": "marker", "text": "【br2】", "recap": ""},
        {"seq": 230, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_30",
         "title": "后置", "ids": [2]},
    ]
    led = [
        {"id": 1, "jp": "a" * 50, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
        {"id": 2, "jp": "b" * 50, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f2"},
    ]
    rows = plan(tl, led, [], budget_chars=10**6)
    main = [r for r in rows if r["lane"] == "main"]
    # 应产生 3 个 main 批：[1]、[2]、空（对应 marker 227 的 flush）
    # 但空 ids 不会产生空批（flush 内部检查 if cur_ids）
    # 所以应该是：seq 226: [1]（cut_reason="branch" by marker 227），seq 230: [2]（cut_reason="tail"）
    assert all(batch["ids"] for batch in main), "No main batch should be empty"
    assert all(batch["chapter"] is not None for batch in main), "No main batch should have chapter=None"
    assert len(main) == 2, f"Expected 2 main batches (empty unit contributes no batch), got {len(main)}"

def test_unit_split_across_batches_preserves_seq():
    """单个 unit 被预算切成多批时，每批都必须有该 unit 的 seq

    不变量：对任意批次 B，set(B.ids) ⊆ ⋃{ timeline[s].ids : s ∈ B.seqs }
    """
    # 构造一个大 unit，被预算切成 3 批
    tl = [
        {"seq": 100, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_10",
         "title": "huge", "ids": [1, 2, 3, 4, 5, 6]},
    ]
    led = [
        {"id": i, "jp": "x" * 4000, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f"}
        for i in range(1, 7)
    ]
    rows = plan(tl, led, [], budget_chars=9000)
    main = [r for r in rows if r["lane"] == "main"]

    # 应该产生至少 2 个批次（每批最多约 2 个 id）
    assert len(main) >= 2, f"Expected at least 2 batches, got {len(main)}"

    # 重要：每个批次都必须有 seq 100
    for batch in main:
        assert 100 in batch["seqs"], f"Batch {batch['batch']} has ids={batch['ids']} but seqs={batch['seqs']} missing seq 100"

    # 验证所有 id 被覆盖
    all_ids = {i for batch in main for i in batch["ids"]}
    assert all_ids == {1, 2, 3, 4, 5, 6}, f"Not all ids covered: {all_ids}"

def test_multiple_units_same_batch_multiple_seqs():
    """单个批次包含多个 unit 的 id 时，该批的 seqs 必须包含所有这些 unit 的 seq

    不变量：对任意批次 B，set(B.ids) ⊆ ⋃{ timeline[s].ids : s ∈ B.seqs }
    """
    # 构造两个小 unit A/B 和大 unit C，使得 A 和 B 的 id 塞进同一批，C 单独一批
    tl = [
        {"seq": 80, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "s1",
         "title": "unitA", "ids": [10, 11]},
        {"seq": 81, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "s2",
         "title": "unitB", "ids": [20, 21]},
        {"seq": 82, "type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "s3",
         "title": "unitC", "ids": [30]},
    ]
    led = [
        {"id": 10, "jp": "a" * 2000, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f"},
        {"id": 11, "jp": "b" * 2000, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f"},
        {"id": 20, "jp": "c" * 2000, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f"},
        {"id": 21, "jp": "d" * 2000, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f"},
        {"id": 30, "jp": "e" * 5000, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f"},
    ]
    rows = plan(tl, led, [], budget_chars=9000)
    main = [r for r in rows if r["lane"] == "main"]

    # 前两个 unit (4 个 id，共 8000 字) 应该塞进一个批次，第三个 unit (5000 字) 单独一批
    assert len(main) == 2, f"Expected 2 batches, got {len(main)}: {[r['ids'] for r in main]}"

    first_batch = main[0]
    assert first_batch["ids"] == [10, 11, 20, 21], f"Expected first batch with all 4 ids, got {first_batch['ids']}"
    assert sorted(first_batch["seqs"]) == [80, 81], f"Expected seqs [80, 81], got {first_batch['seqs']}"

    second_batch = main[1]
    assert second_batch["ids"] == [30], f"Expected second batch with id 30, got {second_batch['ids']}"
    assert second_batch["seqs"] == [82], f"Expected seqs [82], got {second_batch['seqs']}"
