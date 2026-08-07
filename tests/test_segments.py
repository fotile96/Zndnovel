"""config/segments.yaml 与 data/batches.jsonl 的锁定测试：
分割必须恰好覆盖 b1–339 各一次（2026-08-07 补 seg0-s0-s1 覆盖此前遗漏的
b1–35 之后，覆盖范围从 b36–339 扩到 b1–339），jp_chars 与实算一致，
label/seg 唯一有序（seg 字段从 0 开始，与 label 前缀数字一一对应——
2026-08-07 二次修正：新段最初占用了 seg:1、把原 seg1-s2 挤成 seg:2，
label 文字保留不变，出现"seg1-s0-s1"与"seg1-s2"两个 label 同时自称
"seg1"的歧义；改为新段用 seg:0、其余 9 条 seg 字段改回原值 1–9 后消除）。"""
import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent


def _load():
    segs = yaml.safe_load((REPO / "config" / "segments.yaml").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in
            (REPO / "data" / "batches.jsonl").read_text(encoding="utf-8").splitlines() if l]
    return segs, {r["batch"]: r for r in rows}


def test_segments_partition_b1_to_339():
    segs, by = _load()
    covered = []
    for s in segs:
        lo, hi = s["batches"]
        covered.extend(range(lo, hi + 1))
    assert covered == list(range(1, 340))


def test_segments_jp_chars_match_batches():
    segs, by = _load()
    for s in segs:
        lo, hi = s["batches"]
        assert s["jp_chars"] == sum(by[b]["jp_chars"] for b in range(lo, hi + 1)), s["label"]


def test_each_segment_covers_exactly_one_lane():
    """终审 I4：`gen_plan.select()` 只按单一 lane 过滤——一个段若横跨两个 lane，
    生成计划时必然静默漏掉另一条 lane 的批次（原 SEG-8 = b174–339 里 b339 是
    ambient、其余是 extra，`--lane extra` 产出 165 批、漏 b339）。"""
    segs, by = _load()
    for s in segs:
        lo, hi = s["batches"]
        lanes = {by[b]["lane"] for b in range(lo, hi + 1)}
        assert len(lanes) == 1, f"{s['label']} 横跨 lane {sorted(lanes)}"


def test_segments_chapters_match_actual_chapters():
    """终审 M5：chapters 是用户抽读时的范围认知来源，必须等于该段实算章别集合
    （原表全段漏 crd、SEG-8 直接是空列表）。"""
    segs, by = _load()
    for s in segs:
        lo, hi = s["batches"]
        actual = {by[b]["chapter"] for b in range(lo, hi + 1)}
        assert len(s["chapters"]) == len(set(s["chapters"])), f"{s['label']} chapters 有重复"
        assert set(s["chapters"]) == actual, (
            f"{s['label']} chapters 与实算不符：多 {sorted(set(s['chapters']) - actual)}"
            f" 缺 {sorted(actual - set(s['chapters']))}")


def test_segments_labels_unique_and_ordered():
    """`seg` 字段从 0 开始连续递增（2026-08-07 起：新增的 seg0-s0-s1 排在游玩顺序
    最前面，其余段延续原有 1..N 编号——见 config/segments.yaml 顶部注释与
    test_seg_field_matches_label_prefix_number 的"为什么是 0 不是把其余段 +1"）。"""
    segs, _ = _load()
    labels = [s["label"] for s in segs]
    assert len(labels) == len(set(labels))
    assert [s["seg"] for s in segs] == list(range(0, len(segs)))
    assert all(s["review_focus"].strip() for s in segs)


def test_seg_field_matches_label_prefix_number():
    """把"seg 数值序与 label 前缀序一致"钉成机械闸——这正是 2026-08-07 出过问题
    的地方：首次给新段编号时把其余 9 段的 `seg` 字段整体 +1、但 label 字符串
    是历史文本不能跟着改名，导致"seg1-s0-s1"（seg 字段=1）与"seg1-s2"（seg
    字段=2 但 label 仍叫"seg1-…"）两个 label 同时自称"seg1"。

    判据：每条记录的 `label` 若匹配 `^seg(\\d+)-` 形式，捕获到的数字必须与该
    记录的 `seg` 字段相等——用 label 本身的文本反过来核对 seg 字段，不依赖
    "seg 字段是否连续"这类间接判据（那类判据即使两个 seg 字段没有重复，也
    发现不了 label 文本对不上号这件事，2026-08-07 的问题正是"seg 字段连续
    无重复"仍然成立、只是与 label 对不上）。"""
    segs, _ = _load()
    pat = re.compile(r"^seg(\d+)-")
    for s in segs:
        m = pat.match(s["label"])
        assert m, f"{s['label']} 不符合 seg<N>-… 命名约定，测试判据需要更新"
        assert int(m.group(1)) == s["seg"], (
            f"{s['label']}：label 前缀数字 {m.group(1)} 与 seg 字段 {s['seg']} 不一致")


def test_segments_lane_field_matches_batches():
    segs, by = _load()
    for s in segs:
        lo, hi = s["batches"]
        lanes = {by[b]["lane"] for b in range(lo, hi + 1)}
        assert lanes == {s["lane"]}, s["label"]


def test_seg0_s0_s1_covers_b1_to_35_prologue_and_chapter1():
    """显式钉死新增段本身（2026-08-07 P4 seg2-prep）——不是只靠上面几条通用
    循环测试"顺带"覆盖它：b1–35 是 P2 试点批次遗留、P3 建段表时"只切余下
    304 批"而从未纳入 config/segments.yaml 的开头整块（序章 + 第1章 + 相关
    卡片剧情），此前任何一份检查段计划都不包含它。这条测试独立锁定其身份
    （label/seg 编号/批号区间/实算 jp_chars），防止未来有人"顺手"把它从
    段表里删掉或改错编号却让上面的通用分区/唯一性测试碰巧继续通过
    （比如误删这一段、同时把 test_segments_partition_b1_to_339 的下界也
    错改回 36——那种双重误改才会被这条测试之外的机制放过，故这条测试只
    钉一半：真正的"分区不能有洞"仍然靠 partition 测试兜底，这条测试钉的
    是"这一段的身份没被张冠李戴"）。

    `seg == 0`（不是 1）：2026-08-07 二次修正后新段排在最前面用 0 表达，
    其余 9 段延续原编号 1–9，label 前缀数字与 seg 字段全线对应（见
    test_seg_field_matches_label_prefix_number）。"""
    segs, by = _load()
    hit = next((s for s in segs if s["label"] == "seg0-s0-s1"), None)
    assert hit is not None, "config/segments.yaml 里找不到 label=seg0-s0-s1"
    assert hit["seg"] == 0
    assert hit["batches"] == [1, 35]
    assert hit["lane"] == "main"
    assert hit["jp_chars"] == sum(by[b]["jp_chars"] for b in range(1, 36))
    assert hit["jp_chars"] == 116282
    actual_chapters = {by[b]["chapter"] for b in range(1, 36)}
    assert set(hit["chapters"]) == actual_chapters
    assert actual_chapters == {"s0f", "crd", "s1s", "sys", "s1f", "s2s"}
