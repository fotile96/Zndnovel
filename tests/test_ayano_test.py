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
    # 卡 1 挂在 s0f（不出现在任何段的 chapters 里 → 恒早于全部段，见
    # config/card_chapter.yaml 头注释），故对 seg=1 的 segX 而言"严格早于"成立。
    (repo / "config" / "card_chapter.yaml").write_text("1: s0f\n", encoding="utf-8")
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


def test_assemble_context_excludes_current_and_later_cards(tmp_path):
    """反剧透闸（P3 devwave1 task-7 Critical 修复）：卡组前缀只取严格早于当前段
    的卡。同段的卡（本段自己的答案，如原 brief fixture 里卡 45「游泳池的约定」
    那类命题）与更晚段的卡（如卡 141「原来是直哉」这类 s7f 真相）都不该出现在
    segX（seg=1）的前缀里；只有更早段（这里模拟成不属于任何段、恒早于全部段的
    s0f）的卡才该出现。"""
    lane, repo = _mk_fixture(tmp_path)
    segs = yaml.safe_load((repo / "config" / "segments.yaml").read_text(encoding="utf-8"))
    segs.append({"seg": 2, "label": "segY", "batches": [37, 37], "lane": "main",
                 "chapters": ["s7f"], "jp_chars": 1, "review_focus": "y"})
    (repo / "config" / "segments.yaml").write_text(
        yaml.safe_dump(segs, allow_unicode=True), encoding="utf-8")
    (repo / "skeleton" / "cards.zh.yaml").write_text(yaml.safe_dump([
        {"card": 1, "variant": "a", "title_zh": "卡一标题", "body_zh": "早期卡内容"},
        {"card": 2, "variant": "a", "title_zh": "卡二标题", "body_zh": "本段谜题正确答案是水池"},
        {"card": 3, "variant": "a", "title_zh": "卡三标题", "body_zh": "原来是直哉"},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "config" / "card_chapter.yaml").write_text(
        "1: s0f\n2: s2s\n3: s7f\n", encoding="utf-8")   # 卡2同段(s2s)/卡3更晚段(s7f)

    ctx, _ = assemble_context("segX", lane, repo=repo)
    assert "早期卡内容" in ctx
    assert "本段谜题正确答案是水池" not in ctx   # 本段自己的答案不该在前缀里
    assert "原来是直哉" not in ctx               # 更晚段的真相不该提前泄露


def test_assemble_context_prefix_not_emptied_by_filter(tmp_path):
    """前缀非空闸：反剧透过滤不能把卡组前缀整个滤空——那会让工具从"恒绿"变成
    "恒错"，同样测不出任何东西。"""
    lane, repo = _mk_fixture(tmp_path)
    ctx, _ = assemble_context("segX", lane, repo=repo)
    head = ctx.index("此前剧情的卡片梗概")
    tail = ctx.index("最新一段正文")
    prefix_section = ctx[head:tail]
    assert "卡一梗概正文" in prefix_section
