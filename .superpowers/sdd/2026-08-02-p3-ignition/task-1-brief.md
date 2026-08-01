### Task 1: 检查段切分表 `config/segments.yaml`

**Files:**
- Create: `config/segments.yaml`
- Test: `tests/test_segments.py`

**Interfaces:**
- Consumes: `data/batches.jsonl`（字段 `batch/lane/ids/seqs/jp_chars/chapter/cut_reason`，339 行，main 车道 b1–173、extra/ambient b174–339；P2 已完成 b1–35）。
- Produces: 段定义列表，每项 `{seg:int, label:str, batches:[lo,hi], chapters:[...], jp_chars:int, review_focus:str}`。后续任务按 `label` 引用（Task 4 的 `--segment`、Task 7 的 SEG-1 = `seg1-s2`）。

- [ ] **Step 1: 写切分表**

写入 `config/segments.yaml`（数值已按 batches.jsonl 实算核对）：

```yaml
# P3 检查段切分表（spec §2）：opus 侦察全量余下 304 批（b36–339）按章切 8 段。
# 段完成 = 机检全绿 + 用户按 review_focus 抽读 + git tag prod-opus-<label>-done + 段末小裁决。
# jp_chars 与 batches 区间由 tests/test_segments.py 对 data/batches.jsonl 锁定。
- seg: 1
  label: seg1-s2
  batches: [36, 62]
  chapters: [s2s, s2f]
  jp_chars: 53183
  review_focus: "ナゾトキ多层选择迷宫（答对/答错影响 s2s_260_sel 选项集）；s2s_390 夜晚成立判定三条件；周末プール/プラネタリウム伏笔；s2f 章终框架剧情"
- seg: 2
  label: seg2-s3
  batches: [63, 90]
  chapters: [s3s, s3fa]
  jp_chars: 49685
  review_focus: "楼梯怪谈线；s3s_50_sel→s6、s3s_300_sel→s4 跨章门控句；s3s_620/641_sel 的 3A 分支（ユウイチとキス）；s3fa 现实层"
- seg: 3
  label: seg3-s4
  batches: [91, 117]
  chapters: [s4s, s4fa, s4fb]
  jp_chars: 61226
  review_focus: "ユウイチ视点开场的人称与口吻；s4s_30_sel「私じゃない」回 s3s_340；s4s_100_sel→e1、s4s_490_sel→s8 门控；4A（消えたサクラ）/4B（サクラを待つ）双结局"
- seg: 4
  label: seg4-s3tail-s5
  batches: [118, 138]
  chapters: [s3s, s3fb, s3fc, s5s, s5f]
  jp_chars: 47299
  review_focus: "s3fc_90 绘本『总有一天你会看到的故事。』全文（童谣体，全篇最高难度润色位）；s5 日记体日期格式（9/13→2/13 + 返信）；「发作」选择 GAMEOVER 支线；s5s_680→e2 门控"
- seg: 5
  label: seg5-s6-s7f
  batches: [139, 154]
  chapters: [s6s, s6f, s7f]
  jp_chars: 36767
  review_focus: "s6『True Color』大谜题与中庭の雪；s7f 全盘揭示章＝全知纪律最危险段（递卡段逐张核对、雪乃名字首次揭示位）；第一次 staff roll"
- seg: 6
  label: seg6-s8-e1
  batches: [155, 166]
  chapters: [s8s, s8f, s4s, e1s, e1f]
  jp_chars: 30037
  review_focus: "s8 黎明结局：坠落抓手句族与 anchors 逐字核对；五年后尾声与『True Color，』逗号；e1 ユカリ第一人称 25 连场的语域"
- seg: 7
  label: seg7-e2
  batches: [167, 173]
  chapters: [e2s, e2f]
  jp_chars: 36440
  review_focus: "e2s 单边电话/拜访独白（全书对上下文依赖最强段，CLAUDE.md 指定最后翻档位）；e2f if 幸福线＝标题回收章"
- seg: 8
  label: seg8-extra
  batches: [174, 339]
  chapters: []
  jp_chars: 10382
  review_focus: "extra 车道 UI/系统/tr_line 串（str id）：cHan2Zen 全角渲染、数字形制跟随原文、菜单词英日对版式；机械段，抽读以形制一致性为主"
```

- [ ] **Step 2: 写校验测试**

写入 `tests/test_segments.py`：

```python
"""config/segments.yaml 与 data/batches.jsonl 的锁定测试：
分割必须恰好覆盖 b36–339 各一次，jp_chars 与实算一致，label/seg 唯一有序。"""
import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent


def _load():
    segs = yaml.safe_load((REPO / "config" / "segments.yaml").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in
            (REPO / "data" / "batches.jsonl").read_text(encoding="utf-8").splitlines() if l]
    return segs, {r["batch"]: r for r in rows}


def test_segments_partition_b36_to_339():
    segs, by = _load()
    covered = []
    for s in segs:
        lo, hi = s["batches"]
        covered.extend(range(lo, hi + 1))
    assert covered == list(range(36, 340))


def test_segments_jp_chars_match_batches():
    segs, by = _load()
    for s in segs:
        lo, hi = s["batches"]
        assert s["jp_chars"] == sum(by[b]["jp_chars"] for b in range(lo, hi + 1)), s["label"]


def test_segments_labels_unique_and_ordered():
    segs, _ = _load()
    labels = [s["label"] for s in segs]
    assert len(labels) == len(set(labels))
    assert [s["seg"] for s in segs] == list(range(1, len(segs) + 1))
    assert all(s["review_focus"].strip() for s in segs)
```

- [ ] **Step 3: 跑测试确认通过**

Run: `uv run pytest tests/test_segments.py -v`
Expected: 3 passed（若 jp_chars 断言失败＝表抄错数，以测试实算值为准修表）。

- [ ] **Step 4: 全量测试 + commit**

Run: `uv run pytest -q` → 211 passed。

```bash
git add config/segments.yaml tests/test_segments.py
git commit -m "feat: P3 检查段切分表（8 段覆盖 b36-339，测试锁定）"
```

---

