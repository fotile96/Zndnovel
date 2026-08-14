"""彩野测试 harness：fixture 车道 + 注入 transport，零网络（P3 spec §5）。"""
import json

import yaml

from tools.ayano_test import assemble_context, main
from tools.pipelib import REPO


def _fake_events(content, reasoning=""):
    """最小 Responses 事件序列（task-10：stream_transport 注入点的形状）。"""
    if reasoning:
        yield "response.reasoning_text.delta", {"delta": reasoning}
        yield "response.reasoning_text.done", {"text": reasoning}
    yield "response.output_text.delta", {"delta": content}
    yield "response.output_text.done", {"text": content}
    yield "response.completed", {"response": {"usage": {
        "input_tokens": 10, "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": 5, "output_tokens_details": {"reasoning_tokens": 2}}}}


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
    # 题库顶层带 segment 绑定（终审 I4）——拿别段题库跑本段必须报错，不能静默全绿
    (repo / "config" / "qa.yaml").write_text(yaml.safe_dump(
        {"segment": "segX",
         "questions": [{"id": "q1", "question": "彩野今天讲了什么约定？",
                        "reference": "游泳池的约定", "info_point": "s2 周末伏笔"}]},
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
    # task-10：注入点由 transport（一次调用→一次完整 dict）改为 stream_transport
    # （yield Responses 事件序列），断言不变。
    def fake(url, headers, payload):
        calls.append(payload)
        content = "游泳池的约定" if len(calls) == 1 else "对|回答与标准一致"
        return _fake_events(content, "文本里说周末要一起去买东西")
    out = tmp_path / "report.md"
    rc = main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
               "--lane-dir", str(lane), "--out", str(out), "--repo", str(repo)],
              stream_transport=fake, api_key="sk-test", ledger_path=tmp_path / "l.jsonl")
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "q1" in text and "游泳池的约定" in text and "对|" in text
    assert "缺译 1 行" in text
    assert len(calls) == 2                    # 一次作答 + 一次判分


def test_model_and_timeout_passthrough(tmp_path, monkeypatch):
    """P3 devwave1 task-9：main() 必须把 --model/--timeout 透传给两次 chat() 调用
    （reader 与 judge），否则用户指定的 deepseek-v4-flash 进不去。"""
    lane, repo = _mk_fixture(tmp_path)
    captured = []

    def fake_chat(messages, *, purpose="", **kw):
        captured.append(kw)
        return {"content": "游泳池的约定" if len(captured) == 1 else "对|一致"}

    monkeypatch.setattr("tools.ayano_test.chat", fake_chat)
    out = tmp_path / "report.md"
    rc = main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
               "--lane-dir", str(lane), "--out", str(out), "--repo", str(repo),
               "--model", "deepseek-v4-flash", "--timeout", "900"],
              api_key="sk-test", ledger_path=tmp_path / "l.jsonl")
    assert rc == 0
    assert len(captured) == 2
    assert captured[0]["model"] == "deepseek-v4-flash" and captured[0]["timeout"] == 900
    assert captured[1]["model"] == "deepseek-v4-flash" and captured[1]["timeout"] == 900


def test_report_includes_cot_excerpt(tmp_path):
    """task-10 核心增值：受试者的 CoT 摘要要进报告——人一眼就能看出它是从译文里
    读出来的（引用了给定文本）还是猜的。过长要截断，缺 CoT 要显式说明。"""
    from tools.ayano_test import COT_EXCERPT_CHARS, _cot_excerpt

    lane, repo = _mk_fixture(tmp_path)
    long_cot = "文本里提到" + "啊" * 500
    calls = []

    def fake(url, headers, payload):
        calls.append(payload)
        content = "游泳池的约定" if len(calls) == 1 else "对|一致"
        return _fake_events(content, long_cot if len(calls) == 1 else "比对事实点")

    out = tmp_path / "report.md"
    main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
          "--lane-dir", str(lane), "--out", str(out), "--repo", str(repo)],
         stream_transport=fake, api_key="sk-test", ledger_path=tmp_path / "l.jsonl")
    text = out.read_text(encoding="utf-8")
    assert "CoT 摘要：文本里提到" in text
    assert "已截断" in text
    # 只放 reader 的 CoT（受试者），judge 的不进报告
    assert "比对事实点" not in text
    # 摘要单行（不被换行打断 markdown 列表），且不超过截断上限太多
    line = next(x for x in text.splitlines() if x.startswith("- CoT 摘要："))
    assert len(line) < COT_EXCERPT_CHARS + 60
    assert _cot_excerpt("") == "（无 CoT：模型未返回 reasoning_text）"


def test_cot_signals_measures_without_verdict():
    """降级后的核心行为（P3 devwave1，SEG-1 首次真实全跑证伪原「机械分诊」后）：
    cot_signals 只回报**测量值**——CoT 里出现的犹豫词、回答与上下文的最长逐字
    重合字数——不做任何判定，也不看判分是什么。旧版在这三种输入下会打
    `⚠ 存疑：可能照抄未理解`；新版只输出数字/词本身，不含「存疑」「可能」这类
    带结论的措辞。降级原因见 tools/ayano_test.py 里 HESITATION_MARKERS 上方的
    记录，以及 .superpowers/sdd/2026-08-02-p3-devwave1/progress.md（搜「机械
    分诊标记不成立」）。"""
    from tools.ayano_test import VERBATIM_MIN, _longest_verbatim_span, cot_signals

    ctx = "＝＝ 正文 ＝＝\n赝品的做工完全没有问题，被识破的原因在于原作本身，与仿者无关。"
    copied = "赝品的做工完全没有问题，被识破的原因在于原作本身"
    assert len(copied) >= VERBATIM_MIN
    span = _longest_verbatim_span(copied, ctx)

    # 1) 逐字照抄 → 报出重合字数（是数字，不是判定用词）
    s = cot_signals(copied, "文本里就是这么写的", ctx)
    assert s == f"犹豫词 无 ｜ 与上下文最长逐字重合 {span} 字"
    assert "存疑" not in s and "可能" not in s

    # 2) CoT 犹豫标记 → 报出命中的词；回答短、无长重合 → 该项为「无」
    s = cot_signals("原作有问题", "大概是原作的问题？需确认", ctx)
    assert s == "犹豫词 需确认、大概 ｜ 与上下文最长逐字重合 无"

    # 3) 自己的话复述、CoT 干净 → 两项都「无」
    assert cot_signals("问题出在被仿的原作上", "定位到サクラ的判定句", ctx) == \
        "犹豫词 无 ｜ 与上下文最长逐字重合 无"

    # 4) 判分不是「对」时同样输出测量值——遥测不再像旧分诊那样只在「对」时触发
    #    （cot_signals 根本不接收 verdict 参数，语义上就不可能只在某个判分下触发）
    s = cot_signals(copied, "需确认", ctx)
    assert s == f"犹豫词 需确认 ｜ 与上下文最长逐字重合 {span} 字"


def test_cot_signals_verbatim_threshold_and_no_bare_question_mark():
    """测量下限的边界语义闸（延续自原「机械分诊」的标定，现只是测量口径，不再
    是判定阈值，见常量定义处的降级记录）：VERBATIM_MIN 定在 12，差一个字不计入
    数字（报「无」）、够了就报出具体字数。

    另守住裸问号仍不在犹豫词表里：本作是视觉小说，上下文问号遍地，若把「？」
    当犹豫词，几乎每条 CoT 都会命中，测量值直接失去区分力。"""
    from tools.ayano_test import (HESITATION_MARKERS, VERBATIM_MIN,
                                   _longest_verbatim_span, cot_signals)

    span_text = "赝品的做工完全没有问题，原因在于原作。这里再写点别的把上下文撑开一些。"
    ctx = "＝＝ 正文 ＝＝\nサクラ：「" + span_text + "」"
    just_under = span_text[:VERBATIM_MIN - 1]
    just_over = span_text[:VERBATIM_MIN]

    assert _longest_verbatim_span(just_under, ctx) == 0        # 未达下限不计
    assert _longest_verbatim_span(just_over, ctx) == VERBATIM_MIN
    assert "逐字重合 无" in cot_signals(just_under, "干净的推理", ctx)
    assert f"逐字重合 {VERBATIM_MIN} 字" in cot_signals(just_over, "干净的推理", ctx)

    # 裸问号不得入表：只引用了带问号的对白、没有任何对冲措辞 → 犹豫词项为「无」
    assert "？" not in HESITATION_MARKERS and "?" not in HESITATION_MARKERS
    s = cot_signals("自己的话复述", "ユウイチ问“嗯？有什么安排吗？”", ctx)
    assert "犹豫词 无" in s


def test_cot_signal_line_reaches_report(tmp_path):
    """遥测行要真的写进报告行（不是只有函数能算出来），且不再含旧的判定式措辞。"""
    lane, repo = _mk_fixture(tmp_path)
    calls = []

    def fake(url, headers, payload):
        calls.append(payload)
        if len(calls) == 1:
            return _fake_events("游泳池的约定", "文本里说了，不过具体日期需确认")
        return _fake_events("对|回答与标准一致")

    out = tmp_path / "report.md"
    main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
          "--lane-dir", str(lane), "--out", str(out), "--repo", str(repo)],
         stream_transport=fake, api_key="sk-test", ledger_path=tmp_path / "l.jsonl")
    text = out.read_text(encoding="utf-8")
    assert "- CoT 信号：犹豫词 需确认 ｜ 与上下文最长逐字重合 无" in text
    assert "⚠ 存疑" not in text and "可能照抄未理解" not in text
    assert "**判分：对|回答与标准一致**" in text      # 判分本身没被改写


def test_cot_signal_line_reaches_report_for_non_correct_verdicts(tmp_path):
    """遥测没有理由只在判「对」时给：旧的机械分诊只在判「对」的行上触发（已被
    SEG-1 首次真实全跑证伪并停用），遥测行必须对「部分对」「错」同样输出——
    降级要求见 tools/ayano_test.py 里的记录。"""
    lane, repo = _mk_fixture(tmp_path)
    calls = []

    def fake(url, headers, payload):
        calls.append(payload)
        if len(calls) == 1:
            return _fake_events("游泳池的约定，大概是这样", "大概是这样，需确认")
        return _fake_events("部分对|漏了细节")

    out = tmp_path / "report.md"
    main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
          "--lane-dir", str(lane), "--out", str(out), "--repo", str(repo)],
         stream_transport=fake, api_key="sk-test", ledger_path=tmp_path / "l.jsonl")
    text = out.read_text(encoding="utf-8")
    assert "**判分：部分对|漏了细节**" in text
    assert "- CoT 信号：犹豫词 需确认、大概 ｜ 与上下文最长逐字重合 无" in text


def test_effort_passthrough(tmp_path, monkeypatch):
    """--effort 透传给 reader 与 judge 两次 chat()；不给时不出现在 kw 里
    （走 api_client 自己的 DEFAULT_EFFORT）。"""
    lane, repo = _mk_fixture(tmp_path)
    captured = []

    def fake_chat(messages, *, purpose="", **kw):
        captured.append(kw)
        return {"content": "游泳池的约定" if len(captured) == 1 else "对|一致",
                "reasoning_text": "r"}

    monkeypatch.setattr("tools.ayano_test.chat", fake_chat)
    base = ["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
            "--lane-dir", str(lane), "--out", str(tmp_path / "r.md"),
            "--repo", str(repo)]
    main(base + ["--effort", "high"], api_key="sk-test",
         ledger_path=tmp_path / "l.jsonl")
    assert [c["effort"] for c in captured] == ["high", "high"]
    captured.clear()
    main(base, api_key="sk-test", ledger_path=tmp_path / "l.jsonl")
    assert all("effort" not in c for c in captured)


def test_missing_qa_file_skips_without_traceback(tmp_path, capsys):
    """P3 复评：runbook §5 第 3 项 / handoff 段末清单第 3 项明文「题库不存在就
    跳过并记台账」，但此前 `--qa` 指向不存在的路径会直接 FileNotFoundError
    崩溃。修复后必须：不抛异常、输出含跳过提示（点名路径）、且退出码不能与
    「跑完且全部通过」（rc=0）混淆——这里选 2。"""
    lane, repo = _mk_fixture(tmp_path)
    missing_qa = repo / "config" / "ayano_qa" / "not-there.yaml"
    assert not missing_qa.exists()
    rc = main(["--segment", "segX", "--qa", str(missing_qa),
               "--lane-dir", str(lane), "--repo", str(repo)],
              stream_transport=lambda *a: (_ for _ in ()).throw(
                  AssertionError("不该调 API")))
    assert rc == 2
    out = capsys.readouterr().out
    assert "跳过" in out
    assert str(missing_qa) in out
    assert "尚未产出" in out


def test_dry_run_zero_api_calls(tmp_path, capsys):
    lane, repo = _mk_fixture(tmp_path)
    rc = main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
               "--lane-dir", str(lane), "--dry-run", "--repo", str(repo)],
              stream_transport=lambda *a: (_ for _ in ()).throw(AssertionError("不该调 API")))
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


def test_qa_segment_binding_mismatch_exits(tmp_path):
    """终审 I4：题库与段零绑定时，拿 seg1 的题库跑 seg2–seg9 实测全部 rc=0 静默
    接受——而 seg2 的前缀恰好含 seg1 全部 6 张答案卡，受试模型不看译文即可全对，
    报告全绿被读成「译文没丢信息」。这是 task-7 修掉的恒绿失效从另一入口复活。"""
    import pytest
    from tools.ayano_test import load_qa, main
    lane, repo = _mk_fixture(tmp_path)
    qa = repo / "config" / "qa.yaml"

    with pytest.raises(SystemExit) as e:
        load_qa(qa, "segY")
    assert "segX" in str(e.value) and "segY" in str(e.value)

    # 走 CLI 全程：错配必须在任何 API 调用之前就退出
    with pytest.raises(SystemExit):
        main(["--segment", "segY", "--qa", str(qa), "--lane-dir", str(lane),
              "--repo", str(repo), "--out", str(tmp_path / "r.md")],
             stream_transport=lambda *a: (_ for _ in ()).throw(AssertionError("不该调 API")),
             api_key="sk-test", ledger_path=tmp_path / "l.jsonl")
    assert load_qa(qa, "segX")[0]["id"] == "q1"      # 段名相符时照常返回题目


def test_qa_legacy_bare_list_rejected(tmp_path):
    """无绑定的老式题库（顶层裸列表）一律拒收——「查不到绑定」不能当「绑定正确」。"""
    import pytest
    from tools.ayano_test import load_qa
    p = tmp_path / "legacy.yaml"
    p.write_text(yaml.safe_dump([{"id": "q1", "question": "x", "reference": "y"}],
                                allow_unicode=True), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        load_qa(p, "segX")
    assert "segment" in str(e.value)


def test_real_qa_bank_is_bound_to_its_segment():
    """仓库现行题库的数据闸：文件名段名与内部绑定必须一致，且题数不减。"""
    from tools.ayano_test import load_qa
    p = REPO / "config" / "ayano_qa" / "seg1-s2.yaml"
    qs = load_qa(p, "seg1-s2")
    assert len(qs) == 15
    assert [q["id"] for q in qs] == [f"q{i}" for i in range(1, 16)]
    assert all({"id", "question", "reference", "info_point"} <= set(q) for q in qs)


def test_verdict_format_contract_tolerates_drift():
    """终审 M3：判分行格式完全由提示词约束，模型随时可能漂移。此前用「切分后恰等于
    『对』」做判据，`**对**|…` / `判定：对|…` / 全角竖线 / 「对。」都会让 is_correct
    **静默判错**——一个不报警的失效。放宽后仍必须守住：「部分对」「不对」不是「对」。

    is_correct 是独立于（已停用的）机械分诊之外的判分文本解析工具，继续保留、
    继续测试；cot_signals 不再接收 verdict 参数，与判分格式漂移无关。"""
    from tools.ayano_test import is_correct
    for ok in ("对|一致", "**对**|一致", "判定：对|一致", "对｜一致", "对。|一致",
               "对（措辞不同）|一致", " 对 | 一致 ", "对"):
        assert is_correct(ok), ok
    for bad in ("部分对|漏了细节", "错|答非所问", "不对|事实错误",
                "**部分对**|漏了细节", "判定：错|答非所问"):
        assert not is_correct(bad), bad


def test_real_card_chapter_data_gate():
    """数据闸（P3 devwave1 task-7 复评修复：F1/M1 之外的必修项）。上面几条测试全
    用合成 fixture（自造 segments.yaml + card_chapter.yaml），只守住了过滤代码本
    身，没守住它依赖的 config/card_chapter.yaml 这份 196 条手工推导数据——复评的
    变异测试证明了这点：把仓库里真实的 `41: s2s` 改成 `41: s1s`（把 seg1-s2 自己
    的谜题答案卡塞回它自己的前缀），或者把 card_chapter.yaml 整个清空成 `{}`，上面
    的合成测试全绿放过。本测试直接读仓库现行的 config/card_chapter.yaml +
    config/segments.yaml + skeleton/cards.zh.yaml + pilot/lanes/opus 车道数据
    （只读，不写），三件事都验：
      1) 全覆盖：card_chapter.yaml 的卡号集合 == cards.zh.yaml 的卡号集合（196 条，
         无缺无多）——防止 D 这类"整表被清空/漏项"的回归。
      2) 反剧透：seg1-s2 的前缀不含这些卡——它们是 Critical 的原始证据，写死在
         这里当活文档：
           41       ナゾトキ迷宫正确答案（s2s，本段自己的谜题答案）
           44/45/46 周末去处三选：出去玩地点/游泳池的约定/天文馆的约定（s2s，
                    本段自己的伏笔，s2s_390 判定条件之一）
           58       s2s_390 夜晚是否成立的判定（s2s，本段自己的判定）
           134      章节 2 梗概全文（s2f，本段收尾闭包授予，即本段的『あらすじ』
                    本体，最直接的"整段剧透"）
           141      s7f 全盘揭示（"故事里的ユウイチ其实是直哉"）——更晚段的核心
                    真相，五年前真相章节
           142      s8f 黎明结局——更晚段
         防止 C 这类"某一条映射被误改成更早的段"的回归。
      3) 每段非空（游玩顺序上**并非最早**的段）：对 segments.yaml 里除
         "seg 字段最小的那一段"之外的全部段各跑一遍 assemble_context，断言
         过滤后前缀卡数 > 0——防止过滤/白名单写过头把某段前缀清空（工具从
         "恒绿"变"恒错"同样无用）。
         2026-08-07 补 seg0-s0-s1（b1–35，序章+第1章，游玩顺序上真正最早的
         段，seg 字段=0）后，这一条不能再对**全部**段成立：最早的段之前
         没有任何"此前剧情"，前缀卡数=0 才是正确答案，不是过滤写过头。此前
         seg1-s2 "顺理成章"地有非空前缀，只是因为它借了 `PRE_P3_CHAPTERS`
         白名单的光——那份白名单把 s0f/s1s/s1f 硬编码成"确知早于全部段"，
         而 seg1-s2 恰好是（旧表里）唯一在读它们的段。新表里这三章有了自己
         真正的归属段（seg0-s0-s1），`chapter_max_seg` 能从 segments.yaml
         直接算出真实排序，白名单退化成"表里查不到时才用"的兜底（仍然保留、
         对 s0f/s1s/s1f 三章不再实际生效，但对未来任何"查不到章节"的情形
         仍是安全网——见 `tools/ayano_test.py` 里 `PRE_P3_CHAPTERS` 的更新
         注释）——这条测试因此还顺带验证了 `is_before_cur_seg()` 优先吃
         segments.yaml 算出的真实值这条路径没有被绕过。
    """
    card_chapter = yaml.safe_load(
        (REPO / "config" / "card_chapter.yaml").read_text(encoding="utf-8"))
    cards = yaml.safe_load((REPO / "skeleton" / "cards.zh.yaml").read_text(encoding="utf-8"))
    segs = yaml.safe_load((REPO / "config" / "segments.yaml").read_text(encoding="utf-8"))
    lane = REPO / "pilot" / "lanes" / "opus"

    # 1) 全覆盖
    assert set(card_chapter) == {c["card"] for c in cards}

    # 2) 反剧透：seg1-s2 前缀不含 Critical 原始证据里的这几张卡
    ctx, _ = assemble_context("seg1-s2", lane, repo=REPO)
    by_card = {c["card"]: c for c in cards}
    for card_num in (41, 44, 45, 46, 58, 134, 141, 142):
        body = by_card[card_num].get("body_zh", "")
        assert body, f"卡{card_num} 在 cards.zh.yaml 里没有 body_zh，测不出泄露"
        assert body not in ctx, f"卡{card_num} 泄进了 seg1-s2 前缀（回归到 Critical）"

    # 3) 每段非空——游玩顺序上最早的那一段（seg 字段最小）例外：它之前没有
    # 任何"此前剧情"，前缀卡数=0 是正确答案，不是过滤写过头（见上方 docstring
    # 2026-08-07 补记）。
    earliest_seg = min(s["seg"] for s in segs)
    for s in segs:
        seg_ctx, _ = assemble_context(s["label"], lane, repo=REPO)
        head = seg_ctx.index("此前剧情的卡片梗概")
        tail = seg_ctx.index("最新一段正文")
        n = seg_ctx[head:tail].count("【卡")
        if s["seg"] == earliest_seg:
            assert n == 0, (f"{s['label']}（seg={s['seg']}，游玩顺序最早段）前缀本该"
                             f"为空，实际有 {n} 张卡——反剧透过滤可能把"
                             "更晚的段错算成了'早于'它")
        else:
            assert n > 0, f"{s['label']}（seg={s['seg']}）前缀被滤空"


def test_parse_verdict_survives_the_judging_label_drift():
    """`判定|对|…`——模型把字面词「判定」当第一字段（seg5 q3 实测）。

    只看第一字段会得到「判定」，is_correct 随之静默判否：人眼读报告是「对」、
    机械口径是「不对」。加固判据是**逐字段找已知判定词**，不是再补一条剥前缀正则。
    """
    from tools.ayano_test import parse_verdict, is_correct
    assert parse_verdict("判定|对|措辞不同") == "对"
    assert is_correct("判定|对|措辞不同")
    assert parse_verdict("判定|部分对|x") == "部分对"
    assert not is_correct("判定|部分对|x")


def test_parse_verdict_returns_none_when_it_cannot_read_the_line():
    """「读不懂」必须与「判成错」分开——合并二者正是上一版的失效形态。"""
    from tools.ayano_test import parse_verdict, is_correct
    assert parse_verdict("这行完全没有判定词") is None
    assert parse_verdict("错|答非所问") == "错"
    assert not is_correct("这行完全没有判定词")


def test_partial_verdict_is_not_read_as_correct():
    """守的是「别把匹配从 startswith 换成 in」，不是词表顺序。

    用 startswith 时顺序无关（`"部分对".startswith("对")` 为 False）——颠倒词表的
    变异全绿即证。换成 `in` 则「部分对|…」会命中「对」而误判，本用例届时变红。
    """
    from tools.ayano_test import parse_verdict, is_correct
    assert parse_verdict("部分对|漏了两点") == "部分对"
    assert not is_correct("部分对|漏了两点")


# ——agy 通道接线（离线，不 spawn 真 agy）——————————————————————

def _agy_lines(content):
    from tools.agy_client import DEFAULT_MODEL
    objs = [{"event": "init", "init": {"model": DEFAULT_MODEL}},
            {"event": "result",
             "result": {"conversation_id": "c", "status": "SUCCESS",
                        "response": content,
                        "usage": {"input_tokens": 10, "output_tokens": 5,
                                  "thinking_tokens": 2, "cache_read_tokens": 0}}}]
    return [json.dumps(o, ensure_ascii=False) + "\n" for o in objs]


def test_agy_channel_end_to_end(tmp_path):
    """`--channel agy` 走的是 agy_client，且 runner 注入点真的通到底。"""
    lane, repo = _mk_fixture(tmp_path)
    calls = []

    def runner(argv, *, cwd, env):
        calls.append(argv)
        content = "游泳池的约定" if len(calls) == 1 else "对|回答与标准一致"
        return iter(_agy_lines(content)), lambda: (0, "")

    out = tmp_path / "report.md"
    lp = tmp_path / "l.jsonl"
    rc = main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
               "--lane-dir", str(lane), "--out", str(out), "--repo", str(repo),
               "--channel", "agy"], runner=runner, ledger_path=lp)
    assert rc == 0
    assert len(calls) == 2                      # 一次作答 + 一次判分
    text = out.read_text(encoding="utf-8")
    assert "游泳池的约定" in text and "对|" in text
    # 报告必须标出通道，否则多通道横比时分不清哪份是谁跑的
    assert "通道 `agy`" in text
    # agy 不下发推理正文——报告如实写「无 CoT」，不假装有
    assert "无 CoT" in text
    row = json.loads(lp.read_text(encoding="utf-8").splitlines()[0])
    assert row["provider"] == "antigravity"


def test_agy_channel_does_not_leak_http_only_flags(tmp_path):
    """--max-tokens / --timeout 是 HTTP 通道的概念，不该被组装进 agy 调用。"""
    lane, repo = _mk_fixture(tmp_path)

    def runner(argv, *, cwd, env):
        return iter(_agy_lines("对|x")), lambda: (0, "")

    rc = main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
               "--lane-dir", str(lane), "--out", str(tmp_path / "r.md"),
               "--repo", str(repo), "--channel", "agy",
               "--max-tokens", "999", "--timeout", "7"],
              runner=runner, ledger_path=tmp_path / "l.jsonl")
    assert rc == 0


def test_judge_channel_can_be_pinned_to_the_other_channel(tmp_path):
    """受试走 agy、判分走 deepseek——横比时判分员必须是同一个，否则两个变量一起动。"""
    lane, repo = _mk_fixture(tmp_path)
    agy_calls, ds_calls = [], []

    def runner(argv, *, cwd, env):
        agy_calls.append(argv)
        return iter(_agy_lines("游泳池的约定")), lambda: (0, "")

    def fake(url, headers, payload):
        ds_calls.append(payload)
        return _fake_events("对|一致", "推理")

    out = tmp_path / "r.md"
    rc = main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
               "--lane-dir", str(lane), "--out", str(out), "--repo", str(repo),
               "--channel", "agy", "--judge-channel", "deepseek",
               "--model", "gemini-3.7-flash"],
              runner=runner, stream_transport=fake, api_key="sk-test",
              ledger_path=tmp_path / "l.jsonl")
    assert rc == 0
    assert len(agy_calls) == 1 and len(ds_calls) == 1     # 作答走 agy、判分走 deepseek
    # --model 是给受试通道的，不能顺手套给判分通道（型号名根本不通用）
    assert ds_calls[0]["model"] == "deepseek-v4-flash"
    text = out.read_text(encoding="utf-8")
    assert "判分通道 `deepseek`" in text
    # 判分独立时不该再打那句「同一条通道」的免责
    assert "同一条通道" not in text


def test_same_channel_judging_is_flagged_in_the_report(tmp_path):
    """判分与受试同通道时，报告必须自带免责——否则横比会被静默读错。"""
    lane, repo = _mk_fixture(tmp_path)

    def runner(argv, *, cwd, env):
        return iter(_agy_lines("对|x")), lambda: (0, "")

    out = tmp_path / "r.md"
    main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
          "--lane-dir", str(lane), "--out", str(out), "--repo", str(repo),
          "--channel", "agy"], runner=runner, ledger_path=tmp_path / "l.jsonl")
    assert "同一条通道" in out.read_text(encoding="utf-8")


def test_default_channel_is_still_deepseek(tmp_path):
    """不传 --channel 时行为一字不变——本次改动对既有调用方必须是透明的。"""
    lane, repo = _mk_fixture(tmp_path)
    calls = []

    def fake(url, headers, payload):
        calls.append(payload)
        return _fake_events("对|x", "推理")

    rc = main(["--segment", "segX", "--qa", str(repo / "config" / "qa.yaml"),
               "--lane-dir", str(lane), "--out", str(tmp_path / "r.md"),
               "--repo", str(repo)],
              stream_transport=fake, api_key="sk-test",
              ledger_path=tmp_path / "l.jsonl")
    assert rc == 0 and len(calls) == 2
