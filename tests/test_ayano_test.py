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


def test_triage_flags_hesitation_and_verbatim_copy():
    """复评采纳项：机械分诊（纯本地后处理、零额外 API 成本）。判「对」时若 CoT
    含犹豫标记，或回答与上下文有长逐字重合，就打存疑标记——把「答案层评分对可被
    字符串检索答对的题天然失效」这件事固化成可复现信号（seg1-s2 q4 是原始实例）。
    分诊**不改判分语义**：非「对」的行一律不打标。"""
    from tools.ayano_test import VERBATIM_MIN, triage

    ctx = "＝＝ 正文 ＝＝\n赝品的做工完全没有问题，被识破的原因在于原作本身，与仿者无关。"
    copied = "赝品的做工完全没有问题，被识破的原因在于原作本身"
    assert len(copied) >= VERBATIM_MIN

    # 1) 逐字照抄 → 打标，且标出重合字数
    f = triage("对|一致", copied, "文本里就是这么写的", ctx)
    assert f.startswith("⚠ 存疑") and "逐字重合" in f

    # 2) CoT 犹豫标记 → 打标（回答很短、无长重合）
    f = triage("对|一致", "原作有问题", "大概是原作的问题？需确认", ctx)
    assert "犹豫标记" in f and "需确认" in f and "逐字重合" not in f

    # 3) 自己的话复述、CoT 干净 → 不打标（不能变成恒打标的噪声）
    assert triage("对|一致", "问题出在被仿的原作上", "定位到サクラ的判定句", ctx) == ""

    # 4) 判分不是「对」时一律不打标——分诊不改判分语义
    assert triage("错|答非所问", copied, "需确认", ctx) == ""
    assert triage("部分对|漏了细节", copied, "需确认", ctx) == ""


def test_triage_threshold_boundary_and_no_bare_question_mark():
    """阈值语义闸。VERBATIM_MIN 的标定依据是 seg1-s2 的真实产出（离线复算：q1
    「自己的话复述、确实读懂了」最长逐字重合 7 字；q4「照抄得分但 CoT 自陈没读懂」
    12 字，即「赝品的做工完全没有问题，」），故取 12。这里不去伪造一份假的
    "真实上下文"来复现那两个数字，只钉死**边界语义**：差一个字不打标、够了就打标。

    另守住裸问号必须留在标记表**之外**：复评给的原始清单含 `？`，但 q1 那条干净
    CoT 里逐句引用了译文对白（本作是视觉小说，问号遍地）照样命中——留着它等于
    每条都打标、信号归零。"""
    from tools.ayano_test import HESITATION_MARKERS, VERBATIM_MIN, _longest_verbatim_span, triage

    span = "赝品的做工完全没有问题，原因在于原作。这里再写点别的把上下文撑开一些。"
    ctx = "＝＝ 正文 ＝＝\nサクラ：「" + span + "」"
    just_under = span[:VERBATIM_MIN - 1]
    just_over = span[:VERBATIM_MIN]

    assert _longest_verbatim_span(just_under, ctx) == 0        # 未达门槛不计
    assert _longest_verbatim_span(just_over, ctx) == VERBATIM_MIN
    assert triage("对|一致", just_under, "干净的推理", ctx) == ""
    assert f"{VERBATIM_MIN} 字逐字重合" in triage("对|一致", just_over, "干净的推理", ctx)

    # 裸问号不得入表：只引用了带问号的对白、没有任何对冲措辞 → 不该打标
    assert "？" not in HESITATION_MARKERS and "?" not in HESITATION_MARKERS
    assert triage("对|一致", "自己的话复述", "ユウイチ问“嗯？有什么安排吗？”", ctx) == ""


def test_triage_marker_reaches_report(tmp_path):
    """分诊标记要真的写进报告行（不是只有函数能算出来）。"""
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
    assert "⚠ 存疑：可能照抄未理解" in text and "需确认" in text
    assert "**判分：对|回答与标准一致**" in text      # 判分本身没被改写


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
    『对』」做判据，`**对**|…` / `判定：对|…` / 全角竖线 / 「对。」都会让分诊标记
    **静默归零**——一个不报警的失效。放宽后仍必须守住：「部分对」「不对」不是「对」。"""
    from tools.ayano_test import is_correct, triage
    for ok in ("对|一致", "**对**|一致", "判定：对|一致", "对｜一致", "对。|一致",
               "对（措辞不同）|一致", " 对 | 一致 ", "对"):
        assert is_correct(ok), ok
    for bad in ("部分对|漏了细节", "错|答非所问", "不对|事实错误",
                "**部分对**|漏了细节", "判定：错|答非所问"):
        assert not is_correct(bad), bad

    ctx = "＝＝ 正文 ＝＝\n赝品的做工完全没有问题，被识破的原因在于原作本身。"
    copied = "赝品的做工完全没有问题，被识破的原因在于原作本身"
    assert triage("**对**|一致", copied, "干净", ctx).startswith("⚠ 存疑")
    assert triage("**部分对**|漏了细节", copied, "需确认", ctx) == ""


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
      3) 每段非空：对 segments.yaml 全部 9 段各跑一遍 assemble_context，断言过滤
         后前缀卡数 > 0——防止过滤/白名单写过头把某段前缀清空（工具从"恒绿"变
         "恒错"同样无用）。
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

    # 3) 每段非空
    for s in segs:
        seg_ctx, _ = assemble_context(s["label"], lane, repo=REPO)
        head = seg_ctx.index("此前剧情的卡片梗概")
        tail = seg_ctx.index("最新一段正文")
        n = seg_ctx[head:tail].count("【卡")
        assert n > 0, f"{s['label']}（seg={s['seg']}）前缀被滤空"
