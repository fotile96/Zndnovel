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
