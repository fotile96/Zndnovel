### Task 7: 彩野测试 harness `tools/ayano_test.py`

**Files:**
- Create: `tools/ayano_test.py`
- Test: `tests/test_ayano_test.py`
- Modify: `docs/ops/p3-production-runbook.md`（§5 段末清单追加一步）

**Interfaces:**
- Consumes: `config/segments.yaml`（label → batches）；车道 `data/batches.jsonl`（batch → ids）与 `resolve_map(forward, patches)`（id → zh）；`skeleton/cards.zh.yaml`（卡组梗概＝压缩前缀）；`tools.api_client.chat`；题库 `config/ayano_qa/<label>.yaml`（Task 8 产出，条目 `{id, question, reference, info_point}`）。
- Produces: CLI `uv run python tools/ayano_test.py --segment <label> --qa config/ayano_qa/<label>.yaml --lane-dir <lane> [--dry-run] [--out FILE] [--transport 仅测试内部用]`——组装「读者上下文」（卡组梗概 + 本段 zh 正文，**不含任何日文原文**），逐题问 deepseek（读者 persona），再逐题让 deepseek 判分（对/部分对/错 + 依据），写 markdown 报告（默认 `work/out/ayano-<label>.md`）。**advisory 工具，恒 exit 0**；段未译完时报告醒目标注缺行数。`--dry-run` 只组装并打印统计（前缀/正文字符数、缺译行数、题数），零 API 调用。

- [ ] **Step 1: 写失败测试**

写入 `tests/test_ayano_test.py`：

```python
"""彩野测试 harness：fixture 车道 + 注入 transport，零网络（P3 spec §5）。"""
import json

import yaml

from tools.ayano_test import assemble_context, main


def _mk_fixture(tmp_path):
    lane = tmp_path / "lane"
    (lane / "data").mkdir(parents=True)
    (lane / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 36, "lane": "main", "ids": [100, 101], "chapter": "s2s"},
        ensure_ascii=False), encoding="utf-8")
    (lane / "data" / "forward.jsonl").write_text("\n".join([
        json.dumps({"id": 100, "zh": "【彩野】「今天讲游泳池的约定」"}, ensure_ascii=False),
    ]), encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "skeleton").mkdir()
    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump(
        [{"seg": 1, "label": "segX", "batches": [36, 36], "lane": "main",
          "chapters": ["s2s"], "jp_chars": 1, "review_focus": "x"}],
        allow_unicode=True), encoding="utf-8")
    (repo / "skeleton" / "cards.zh.yaml").write_text(yaml.safe_dump(
        [{"card": 1, "variant": "a", "title_zh": "卡一标题", "body_zh": "卡一梗概正文"}],
        allow_unicode=True), encoding="utf-8")
    (repo / "config" / "qa.yaml").write_text(yaml.safe_dump(
        [{"id": "q1", "question": "彩野今天讲了什么约定？",
          "reference": "游泳池的约定", "info_point": "s2 周末伏笔"}],
        allow_unicode=True), encoding="utf-8")
    return lane, repo


def test_assemble_context_cards_plus_zh_no_jp(tmp_path):
    lane, repo = _mk_fixture(tmp_path)
    ctx, missing = assemble_context("segX", lane, repo=repo)
    assert "卡一梗概正文" in ctx and "游泳池的约定" in ctx
    assert missing == 1                       # id 101 未译


def test_main_writes_report_with_verdicts(tmp_path):
    lane, repo = _mk_fixture(tmp_path)
    calls = []
    def fake(url, headers, payload):
        calls.append(payload)
        content = "游泳池的约定" if len(calls) == 1 else "对|回答与标准一致"
        return {"choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    out = tmp_path / "report.md"
    rc = main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
               "--lane-dir", str(lane), "--out", str(out), "--repo", str(repo)],
              transport=fake, api_key="sk-test", ledger_path=tmp_path / "l.jsonl")
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "q1" in text and "游泳池的约定" in text and "对|" in text
    assert "缺译 1 行" in text
    assert len(calls) == 2                    # 一次作答 + 一次判分


def test_dry_run_zero_api_calls(tmp_path, capsys):
    lane, repo = _mk_fixture(tmp_path)
    rc = main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
               "--lane-dir", str(lane), "--dry-run", "--repo", str(repo)],
              transport=lambda *a: (_ for _ in ()).throw(AssertionError("不该调 API")))
    assert rc == 0
    assert "题数 1" in capsys.readouterr().out
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_ayano_test.py -v` → FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

写入 `tools/ayano_test.py`：

```python
"""彩野测试（P3 spec §5）：让从未见过原文的外部模型扮演「只靠梗概续听故事的读者」，
只喂 压缩前缀（skeleton/cards.zh.yaml 卡组梗概＝游戏自身的『あらすじ』机制）＋
本段中文译文（零日文原文），回答剧情理解题；答错处＝译文或压缩丢了信息，且丢的
恰是真实玩家会丢的。判分由第二次 API 调用完成。advisory 工具：恒 exit 0，
结论供段末人工验收参考。--dry-run 只组装统计、零 API 调用。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import yaml

from tools.pipelib import REPO, read_jsonl
from tools.resolve import resolve_map
from tools.api_client import chat

READER_SYS = ("你在听人讲一个故事。你只知道两部分信息：①此前剧情的卡片梗概；"
              "②最新一段正文。只根据给定文本回答问题，文本里没有的就答「不知道」，"
              "不要编造，不要使用任何文本之外的知识。用中文简答，两三句以内。")
JUDGE_SYS = ("你是判分员。根据【问题】【标准答案】【受试回答】判定：对／部分对／错。"
             "只输出一行，格式：判定|一句话依据。")


def assemble_context(label: str, lane_dir: Path, repo: Path = REPO):
    segs = yaml.safe_load((repo / "config" / "segments.yaml").read_text(encoding="utf-8"))
    hit = next((s for s in segs if s["label"] == label), None)
    if hit is None:
        raise SystemExit(f"未知段 label：{label}")
    lo, hi = hit["batches"]
    data = Path(lane_dir) / "data"
    batches = {r["batch"]: r for r in read_jsonl(data / "batches.jsonl")}
    fwd = read_jsonl(data / "forward.jsonl") if (data / "forward.jsonl").exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    zh = resolve_map(fwd, pat)
    lines, missing = [], 0
    for n in range(lo, hi + 1):
        if n not in batches:
            continue
        for i in batches[n]["ids"]:
            if i in zh:
                lines.append(zh[i])
            else:
                missing += 1
    cards = yaml.safe_load((repo / "skeleton" / "cards.zh.yaml").read_text(encoding="utf-8"))
    prefix = "\n\n".join(f"【卡{c['card']}·{c.get('title_zh', '')}】\n{c.get('body_zh', '')}"
                         for c in cards)
    ctx = ("＝＝ 此前剧情的卡片梗概 ＝＝\n\n" + prefix
           + "\n\n＝＝ 最新一段正文 ＝＝\n\n" + "\n".join(lines))
    return ctx, missing


def main(argv=None, *, transport=None, api_key=None, ledger_path=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", required=True)
    ap.add_argument("--qa", required=True)
    ap.add_argument("--lane-dir", required=True)
    ap.add_argument("--repo", default=None, help="仅测试用：覆盖仓库根")
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    repo = Path(a.repo) if a.repo else REPO
    ctx, missing = assemble_context(a.segment, Path(a.lane_dir), repo=repo)
    qa = yaml.safe_load(Path(a.qa).read_text(encoding="utf-8"))
    if a.dry_run:
        print(f"segment={a.segment} 上下文 {len(ctx)} 字符 缺译 {missing} 行 题数 {len(qa)}")
        return 0
    kw = dict(transport=transport, api_key=api_key, ledger_path=ledger_path)
    rows = []
    for q in qa:
        ans = chat([{"role": "system", "content": READER_SYS},
                    {"role": "user", "content": f"{ctx}\n\n＝＝ 问题 ＝＝\n{q['question']}"}],
                   purpose=f"ayano:{a.segment}:{q['id']}", **kw)
        verdict = chat([{"role": "system", "content": JUDGE_SYS},
                        {"role": "user", "content":
                         f"【问题】{q['question']}\n【标准答案】{q['reference']}\n"
                         f"【受试回答】{ans['content']}"}],
                       purpose=f"ayano-judge:{a.segment}:{q['id']}", **kw)
        rows.append((q, ans["content"], verdict["content"]))
    out = Path(a.out) if a.out else repo / "work" / "out" / f"ayano-{a.segment}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# 彩野测试报告 · {a.segment}（{len(rows)} 题）", ""]
    if missing:
        lines.append(f"> ⚠ 本段**缺译 {missing} 行**（段未译完，结论仅供参考）。")
        lines.append("")
    for q, ans, verdict in rows:
        lines += [f"## {q['id']}：{q['question']}",
                  f"- 信息点：{q.get('info_point', '-')}",
                  f"- 标准答案：{q['reference']}",
                  f"- 受试回答：{ans}",
                  f"- **判分：{verdict}**", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已写 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_ayano_test.py -v` → 3 passed。

- [ ] **Step 5: runbook §5 追加一步**

`docs/ops/p3-production-runbook.md` §5 段末清单在「打 tag」之前追加：

```markdown
   （tag 前，可选但强烈建议）跑彩野测试作额外验收：
   `uv run python tools/ayano_test.py --segment <label> --qa config/ayano_qa/<label>.yaml --lane-dir pilot/lanes/opus`
   （零订阅额度，走 deepseek API；题库由开发轨按段提供；报告落 work/out/ayano-<label>.md，
   判「错」的题逐条人工核对是译文丢信息还是题目/判分问题，结论记进段末台账。）
```

- [ ] **Step 6: 真实数据 dry-run 冒烟**

Run: `uv run python tools/ayano_test.py --segment seg1-s2 --qa /dev/null --lane-dir pilot/lanes/opus --dry-run`（`--qa /dev/null` 时 `yaml.safe_load` 得 None——若实现对 None 崩溃，改为构造一个单题临时 yaml 传入；把实际命令记进报告）
Expected: 打印上下文字符数（约 6–15 万级：卡组 ~5.8 万 + 已译正文）与**缺译行数**（SEG-1 正在生产中，非零属正常）。零 API 调用。

- [ ] **Step 7: 全量测试 + commit**

Run: `uv run pytest -q` → 257 passed。

```bash
git add tools/ayano_test.py tests/test_ayano_test.py docs/ops/p3-production-runbook.md
git commit -m "feat: 彩野测试 harness（卡组梗概前缀+段译文/读者-判分双调用/dry-run）"
```

---

