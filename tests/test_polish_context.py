"""tools/polish_context.py：会话分组（长对话双帽）+ prompt 拼接的单测。

mini 夹具复用 `tools/polish_setup.setup()` 造出真正的 `frozen/` 快照（比手搓
目录更可靠——见 task-4-brief 补充说明第 1 条），只是按测试需要控制批次/行数。
全部测试都显式传 `repo=` 隔离到 tmp_path，绝不触碰真实仓库的 `pilot/polish/`。
"""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_context as pc
from tools import polish_setup as ps
from tools.pipelib import read_jsonl, write_jsonl


def _build_mini_seg(tmp_path, batch_sizes, label="segX", locked_ids=(),
                     patched_ids=(), zh_override=None, jp_override=None):
    """batch_sizes: [(batch_no, n_ids), ...]，按顺序生成 id（从 1 递增）。
    locked_ids: 应该落进 anchors.yaml（=锚点）的 id 集合。
    patched_ids: 应该额外落一条 patches.jsonl 记录的 id 集合——2026-08-07
    裁定后，锚点行默认只是**软锁**；要造出**硬锁**场景（该 id 冻结时点
    已有人裁 patch），必须显式把它也放进这个集合（可以是 locked_ids 的
    子集，也可以是 locked_ids 之外单独打 patch 的 id）。
    zh_override: {id: zh} 强制覆盖该 id 的 opus 译文字面内容（用于断言
    "opus 译文确实被嵌进正文"这条——不能靠自动生成的占位字符串验证）。
    jp_override: {id: jp} 强制覆盖该 id 的原文字面内容（用于构造带真实
    `【名字】「台词」` 说话人前缀形态的样本，核实 render 不产生括号嵌套）。
    """
    zh_override = zh_override or {}
    jp_override = jp_override or {}
    patched_ids = set(patched_ids)
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    lo, hi = batch_sizes[0][0], batch_sizes[-1][0]
    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": label, "lane": "main", "batches": [lo, hi],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")

    batch_rows, ledger_rows, forward_rows = [], [], []
    anchor_items = []
    next_id = 1
    for bno, n in batch_sizes:
        ids = list(range(next_id, next_id + n))
        next_id += n
        batch_rows.append({"batch": bno, "lane": "main", "ids": ids, "seqs": [bno],
                            "jp_chars": n, "chapter": "s2s", "cut_reason": "budget"})
        for i in ids:
            jp = jp_override.get(i, f"第{i}句テキスト")
            ledger_rows.append({"id": i, "jp": jp, "voice": "NONVOICE",
                                 "file": "snr_s2_10_s", "func": "f", "literal": False,
                                 "line": i, "chapter": "s2s", "kind": "story"})
            zh = zh_override.get(i, f"第{i}句译文")
            forward_rows.append({"id": i, "zh": zh, "batch": bno, "backend": "cc",
                                  "model": "m", "ctx": "x", "glossary_v": 1, "ts": "t"})
            if i in locked_ids:
                anchor_items.append({"id": i, "jp": jp, "zh": zh,
                                      "recall": "测试锚点"})
    write_jsonl(repo / "data" / "batches.jsonl", batch_rows)

    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([
        {"chapter": "global", "items": anchor_items},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text('{"あ":"啊"}', encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text('{}', encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格\n活仓库版本。", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text(
        "# 汉语母语感细则\n\n1. 量词。\n2. 语序。\n", encoding="utf-8")
    (repo / "glossary" / "voices" / "naoya.md").write_text("# 直哉口调", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", ledger_rows)
    write_jsonl(opus_data / "forward.jsonl", forward_rows)
    zh_by_id = {r["id"]: r["zh"] for r in forward_rows}
    write_jsonl(opus_data / "patches.jsonl", [
        {"id": i, "zh": zh_by_id[i], "reason": "review", "glossary_v": 1, "ts": "t"}
        for i in sorted(patched_ids)
    ])
    (opus_data / "notes" / "s2s.md").write_text("# s2s 纪要", encoding="utf-8")

    d = ps.setup(label, opus_data, repo=repo)
    return SimpleNamespace(root=repo, seg_dir=d, label=label)


@pytest.fixture
def mini_seg(tmp_path):
    """3 批：300/300/100 行——双帽切组测试用（600 顶帽）。"""
    return _build_mini_seg(tmp_path, [(1, 300), (2, 300), (3, 100)])


@pytest.fixture
def mini_seg11(tmp_path):
    """11 个 10 行小批——批数帽先触发测试用。"""
    return _build_mini_seg(tmp_path, [(n, 10) for n in range(1, 12)])


@pytest.fixture
def mini_seg_render(tmp_path):
    """2 批各 2 个 id：batch1=[10(普通),11(锁)]，batch2=[12(普通),13(锁)]。
    id=10 的 opus 译文强制写成 "旧译文本样例"——用于断言 opus 现行译文确实被
    嵌进 prompt 正文（这不是自动生成的占位串，字面内容由测试直接指定）。
    锁定 id（2、4）同时进 anchors.yaml 与 patches.jsonl——按 2026-08-07 裁定
    的 tie-break 规则归为**硬锁**，保留本文件既有测试对"锁定 id 绝不出稿"
    的假设；纯软锁（anchor-only）场景见下方 `mini_seg_soft_render`。
    """
    return _build_mini_seg(tmp_path, [(1, 2), (2, 2)],
                            locked_ids={2, 4}, patched_ids={2, 4},
                            zh_override={1: "旧译文本样例"})


@pytest.fixture
def mini_seg_soft_render(tmp_path):
    """同上但锁定 id（2、4）只进 anchors.yaml、不落 patch——纯软锁场景。"""
    return _build_mini_seg(tmp_path, [(1, 2), (2, 2)],
                            locked_ids={2, 4}, zh_override={1: "旧译文本样例"})


@pytest.fixture
def mini_seg_speaker(tmp_path):
    """评审 Finding 2 的真实语料复现：单批 1 个 id，jp/zh 都带真实
    `【名字】「台词」` 说话人前缀（评审抽样 id=27 的实际形态）。"""
    return _build_mini_seg(
        tmp_path, [(1, 1)],
        jp_override={1: "【アヤノ】「教室に来たよ」"},
        zh_override={1: "【彩野】「到教室了哦」"})


# --- plan()：长对话双帽 ---

def test_plan_respects_double_cap(mini_seg):
    sessions = pc.plan("segX", session_lines=600, session_size=10, repo=mini_seg.root)
    assert [s["batches"] for s in sessions] == [[1, 2], [3]]
    assert sessions[0]["lines"] == 600
    assert sessions[1]["lines"] == 100


def test_plan_size_cap(mini_seg11):
    sessions = pc.plan("segX", session_lines=600, session_size=10, repo=mini_seg11.root)
    assert len(sessions[0]["batches"]) == 10
    assert sessions[0]["batches"] == list(range(1, 11))
    assert sessions[1]["batches"] == [11]


def test_plan_defaults_from_cfg(mini_seg):
    """不传 session_lines/session_size 时应退化到 polishlib.CFG 的
    session_size=10 / session_lines=600——与显式传相同阈值的结果一致。"""
    from tools.polishlib import CFG
    assert CFG["session_size"] == 10 and CFG["session_lines"] == 600
    default_sessions = pc.plan("segX", repo=mini_seg.root)
    explicit_sessions = pc.plan("segX", session_lines=600, session_size=10, repo=mini_seg.root)
    assert default_sessions == explicit_sessions


def test_plan_session_numbers_start_at_1(mini_seg):
    sessions = pc.plan("segX", session_lines=600, session_size=10, repo=mini_seg.root)
    assert [s["session"] for s in sessions] == [1, 2]


# --- render()：任务说明 + 锁定 + glossary 全套 + 逐批正文 + 输出契约 ---

def test_render_marks_locked_and_embeds_opus(mini_seg_render):
    p = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "【硬锁】" in p and "硬锁 id 清单" in p
    assert "旧译文本样例" in p  # opus zh 在正文里


def test_render_output_contract_uses_real_batch_numbers(mini_seg_render):
    """brief 里 `assert "b<批号>.out" not in p or True` 是恒真断言（永远通过，
    什么也没测）——已按用户裁定删除，换成真断言：输出契约里必须出现执行模型
    要写的 raw 文件路径，且路径里的批号是本会话实际渲染出来的批号（b1/b2），
    而不是字面占位符 "<批号>"。"""
    p = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "raw/<channel>/b1.out" in p
    assert "raw/<channel>/b2.out" in p
    assert "b<批号>.out" not in p


def test_render_locked_ids_excluded_from_body(mini_seg_render):
    """硬锁 id（2、4）不得出现在「逐批正文」的 [bN] id: 形式里——它们只应
    出现在「硬锁 id 清单」一节。"""
    p = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "[b1] 2:" not in p
    assert "[b2] 4:" not in p
    assert "[b1] 1:" in p
    assert "[b2] 3:" in p


def test_render_soft_locked_ids_appear_in_body_with_marker(mini_seg_soft_render):
    """2026-08-07 裁定：软锁（纯 anchor，未落 patch）id 必须像普通行一样
    出现在正文里（带【软锁】标记），不再被排除——这是与硬锁行为唯一的
    分叉点。"""
    p = pc.render("segX", 1, repo=mini_seg_soft_render.root)
    assert "（本会话无硬锁 id）" in p
    assert "## 软锁 id 清单" in p
    assert "【软锁】2" in p or "- 【软锁】2：" in p
    assert "[b1] 2 【软锁】:" in p
    assert "[b2] 4 【软锁】:" in p
    assert "[b1] 1:" in p  # 普通 id 不受影响，格式不带多余空格


def test_render_embeds_full_glossary_set(mini_seg_render):
    """frozen/glossary 全套须整篇嵌入：术语表、style.md、polish.md（语感细则
    全文，非摘要）、口调表、锚点渲染。"""
    p = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "啊" in p  # active.json 内容
    assert "直哉口调" in p  # voices/naoya.md
    assert "汉语母语感细则" in p  # polish.md 标题
    assert "量词" in p and "语序" in p  # polish.md 正文（非摘要，须整篇嵌入）
    assert "锚点" in p  # anchors 渲染


def test_render_embeds_task_instructions_and_score_semantics(mini_seg_render):
    """任务说明须覆盖：目标（汉语母语感）、锁定约束、术语/口调/锚点强制性、
    score 语义（仅同档排序、非入库阈值）、adjudicate 触发时机。"""
    p = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "母语" in p
    assert "score" in p and "不是入库阈值" in p
    assert "adjudicate" in p


def test_render_unknown_session_raises(mini_seg_render):
    with pytest.raises(KeyError):
        pc.render("segX", 99, repo=mini_seg_render.root)


def test_render_reads_frozen_glossary_not_live(mini_seg_render):
    """变异②回归锁：render 必须只读 frozen/，不读活仓库 glossary——改坏
    frozen 里的一字，prompt 必须跟着变；活仓库版本的 style.md 内容不该
    出现在 prompt 里（因为它已被 frozen 版本覆盖读取）。"""
    frozen_style = mini_seg_render.seg_dir / "frozen" / "glossary" / "style.md"
    frozen_style.write_text("# 风格\n冻结专属标记ZZZFROZENMARK。", encoding="utf-8")

    p = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "ZZZFROZENMARK" in p
    assert "活仓库版本" not in p  # 这句只存在于活仓库的 glossary/style.md


# --- 评审 Finding 1：frozen/rulings.md 必须进 prompt ---

def test_rulings_content_appears_in_prompt(mini_seg_render):
    """spec §6/§3：拼接器须读 jp/opus/notes/**rulings**。`polish_setup.setup()`
    起初写的是占位骨架，这里改写成模拟"跨段前馈裁决纪要"的真实场景
    （spec §7.4：`polish_amplify.digest()` 会把裁决意图纪要前馈写进下一段的
    rulings.md）——render() 必须能读到，不能永久静默丢弃。"""
    rulings_path = mini_seg_render.seg_dir / "frozen" / "rulings.md"
    rulings_path.write_text(
        "# segX 润色裁决与前序纪要\n\n"
        "- 【裁决】b1#7：量词『个』改『位』，理由：指人自然搭配（用户 2026-08-06 裁定）。\n",
        encoding="utf-8")
    p = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "【裁决】b1#7" in p
    assert "指人自然搭配" in p


def test_rulings_section_skipped_when_placeholder_stripped_empty(mini_seg_render):
    """占位骨架非空（"（追加式）"）时仍会出现——这不是 bug；但若 rulings.md
    的内容整体为空白（理论上的退化情形），渲染不应该产出一个空标题节。"""
    rulings_path = mini_seg_render.seg_dir / "frozen" / "rulings.md"
    rulings_path.write_text("   \n\n  ", encoding="utf-8")
    p = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "裁决与前序纪要" not in p


# --- 评审 Finding 2：正文行分隔符不得与游戏原生控制码嵌套 ---

def test_render_body_line_has_no_bracket_nesting_with_speaker_prefix(mini_seg_speaker):
    """真实语料复现（评审抽样 id=27 的实际形态）：jp/zh 都带
    `【名字】「台词」` 说话人前缀控制码。渲染出的正文行不得把这类内容
    包在与游戏原生控制码集合冲突的括号里（【】/『』/「」/≪≫/≦≧），
    否则模型无法区分"外层括号是排版噪声"还是"必须原样保留的控制码"。"""
    p = pc.render("segX", 1, repo=mini_seg_speaker.root)
    assert "【アヤノ】「教室に来たよ」" in p  # 原文控制码本身必须完整保留
    assert "【彩野】「到教室了哦」" in p
    # 不得出现"控制码前紧跟一个额外包裹括号"的嵌套形态
    assert "【【" not in p
    assert "】】" not in p
    assert "「「" not in p
    assert "」」" not in p
    # 换成不冲突的 ASCII 标签
    assert "JP:" in p and "ZH(opus):" in p


# --- Task 4/Task 11 收尾：章节编号撞号（"三"出现两次后跳到"四"）---

def test_render_has_no_duplicate_or_skipped_chapter_numbers(mini_seg_render):
    """`_render_anchors`（build_context.py 共享函数）自带硬编码的"## 三、锚点行"
    标题，而 render() 自己此前也给"术语/风格/口调/锚点"编了"## 三、"——两个
    "三"撞在一起，加上 notes/rulings 为空时的条件小节又会跳号。修法：本工具
    顶层标题一律不带序号；`_render_anchors` 的产出在拼进本工具输出前被降级为
    "### 锚点行"（不带数字），读起来是"术语..."节下的子块。"""
    p = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "## 三、" not in p
    assert "### 锚点行" in p
    # 顶层标题不编号：任何 "## <汉字数字>、" 形态都不应出现
    for numeral in "一二三四五六七八九十":
        assert f"## {numeral}、" not in p


def test_render_chapter_titles_stable_regardless_of_optional_sections(mini_seg_render):
    """notes/rulings 都缺席时（不带任何裁决前馈、章节纪要）——既有小节的标题
    文字不应因为"少了几节"而漂移（没有序号可跳，天然稳定）。"""
    (mini_seg_render.seg_dir / "frozen" / "rulings.md").write_text("   ", encoding="utf-8")
    import shutil
    shutil.rmtree(mini_seg_render.seg_dir / "frozen" / "notes")
    p = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "## 任务说明（润色契约）" in p
    assert "## 硬锁 id 清单" in p
    assert "## 软锁 id 清单" in p
    assert "## 术语 / 风格 / 口调 / 锚点" in p
    assert "## 逐批正文" in p
    assert "## 输出契约" in p
    assert "章节纪要" not in p
    assert "裁决与前序纪要" not in p


def test_render_has_no_stale_numbered_cross_references(mini_seg_render):
    """评审 Finding A（Task 11 修复轮）：上两条测试只断言了标题层面不撞号/
    不跳号，没覆盖**正文散文里引用旧编号标题**这个盲点——`TASK_INSTRUCTIONS`
    去编号后仍留着字面「二、锁定 id 清单」（顶层标题早已改成不带编号的
    「锁定 id 清单」），评审在真实渲染的 session 1 prompt 第 13 行实测抓到。
    用一个通用正则扫全文找「<汉字数字>、...」这类散文引用，不满足于只测
    已知出过问题的那一处——万一将来又在别的常量里引入同类残留，这条测试
    应该也能抓到。"""
    p = pc.render("segX", 1, repo=mini_seg_render.root)
    stale = re.findall(r"「[一二三四五六七八九十]+、[^」]*」", p)
    assert stale == [], f"发现指向带编号旧标题的散文引用：{stale}"


# --- CLI ---

def test_cli_plan_prints_sessions(mini_seg, capsys):
    rc = pc.main(["--seg", "segX", "--plan", "--repo", str(mini_seg.root)])
    assert rc == 0
    out = capsys.readouterr().out.strip().splitlines()
    rows = [json.loads(line) for line in out]
    assert [r["batches"] for r in rows] == [[1, 2], [3]]


def test_cli_session_writes_prompt_and_records_plan_json(mini_seg_render, tmp_path, capsys):
    out_path = tmp_path / "prompt_s1.md"
    rc = pc.main(["--seg", "segX", "--session", "1", "--out", str(out_path),
                  "--repo", str(mini_seg_render.root)])
    assert rc == 0
    digest = capsys.readouterr().out.strip()
    assert len(digest) == 64  # sha256 hex

    written = out_path.read_text(encoding="utf-8")
    assert written  # 非空
    import hashlib
    assert hashlib.sha256(written.encode("utf-8")).hexdigest() == digest

    plan_path = mini_seg_render.seg_dir / "plan.json"
    records = json.loads(plan_path.read_text(encoding="utf-8"))
    assert records == [{"session": 1, "batches": [1, 2], "prompt_hash": digest}]


def test_cli_session_rerender_replaces_same_session_record(mini_seg_render, tmp_path):
    out_path = tmp_path / "prompt_s1.md"
    pc.main(["--seg", "segX", "--session", "1", "--out", str(out_path),
             "--repo", str(mini_seg_render.root)])
    pc.main(["--seg", "segX", "--session", "1", "--out", str(out_path),
             "--repo", str(mini_seg_render.root)])
    plan_path = mini_seg_render.seg_dir / "plan.json"
    records = json.loads(plan_path.read_text(encoding="utf-8"))
    assert len(records) == 1  # 同一 session 重渲染不应重复追加


# ---- 最终评审 I9：校准批渲染器（准入小考的 prompt） ----

def _make_calib(m, rows):
    calib = m.seg_dir / "calib"
    calib.mkdir(exist_ok=True)
    write_jsonl(calib / f"{m.label}.batch.jsonl", rows)
    (calib / f"{m.label}.truth.json").write_text(
        json.dumps({str(r["id"]): {"is_gold": i == 0}
                     for i, r in enumerate(rows)}, ensure_ascii=False),
        encoding="utf-8")
    return calib


def test_render_calib_is_isomorphic_to_production_prompt(tmp_path):
    """校准批 prompt 必须与生产 prompt **同构**——同一份任务说明、术语表、
    style.md、语感细则、口调表、锚点。

    此前 handoff/runbook 只说"把 `calib/<label>.batch.jsonl` 分别喂给两条
    通道（同一套派发方式）"，但生产的派发方式是"读渲染好的 `work/ctx/
    p4s1-sN.md`"，校准批既无对应 prompt 文件也无工具生成——操作者只能自己
    拼，拼得跟生产不等价，这场小考就测不到生产行为，**而它的产物直接决定
    免检权**。
    """
    m = _build_mini_seg(tmp_path, [(1, 3)])
    _make_calib(m, [{"id": 1, "batch": f"calib-{m.label}", "jp": "第1句テキスト",
                     "opus_zh": "第1句译文"},
                    {"id": 2, "batch": f"calib-{m.label}", "jp": "第2句テキスト",
                     "opus_zh": "第2句译文"}])
    calib_prompt = pc.render_calib(m.label, repo=m.root)
    prod_prompt = pc.render(m.label, 1, repo=m.root)

    for block in (pc.TASK_INSTRUCTIONS,
                  "### active.json（术语表）",
                  "### style.md（对/错标准，与下方语感细则冲突时以此为准）",
                  "### polish.md（汉语母语感细则）",
                  "### 锚点行",
                  "## 章节纪要（背景参考）"):
        assert block in calib_prompt, f"校准批 prompt 缺了生产 prompt 有的：{block}"
        assert block in prod_prompt

    # 正文换成校准批的行，且带 opus 对照（润色起点）。
    assert "第1句テキスト" in calib_prompt and "第2句译文" in calib_prompt
    assert f"[calib-{m.label}] 1:" in calib_prompt
    # 输出契约换成单文件，不提生产的 raw/<channel>/b<N>.out 分批路径。
    assert "calib/raw.<channel>.jsonl" in calib_prompt
    assert "b1.out" not in calib_prompt


def test_calib_prompt_never_contains_truth(tmp_path):
    """⚠ `truth.json` 绝不能进这份 prompt——它是判卷答案，进了 prompt 这场
    考试当场作废（金标 id 一旦被模型认出来，"它会不会改坏人工定稿"这个
    问题就问不出结果了）。这条测试是那件事的钉死锁。"""
    m = _build_mini_seg(tmp_path, [(1, 3)])
    calib = _make_calib(m, [{"id": 1, "batch": f"calib-{m.label}", "jp": "第1句テキスト",
                             "opus_zh": "第1句译文"}])
    truth_text = (calib / f"{m.label}.truth.json").read_text(encoding="utf-8")
    prompt = pc.render_calib(m.label, repo=m.root)
    assert "is_gold" not in prompt
    assert "truth" not in prompt.lower()
    assert truth_text.strip() not in prompt


def test_calib_prompt_has_no_lock_marks(tmp_path):
    """校准批"不带锁标"（spec §6 原话：与生产批分离故无泄露）——【硬锁】/
    【软锁】一个都不许出现在具体标出某个 id 的行里，但"硬锁/软锁 id 清单"
    这一节仍在（任务说明引用它）。夹具里 id=1 是硬锁（anchor+patch），
    id=3 是软锁（纯 anchor）。"""
    m = _build_mini_seg(tmp_path, [(1, 3)], locked_ids=(1, 3), patched_ids=(1,))
    _make_calib(m, [{"id": 2, "batch": f"calib-{m.label}", "jp": "第2句テキスト",
                     "opus_zh": "第2句译文"}])
    prompt = pc.render_calib(m.label, repo=m.root)
    # 任务说明里"带【硬锁】/【软锁】标记"这类共用文案是同构的一部分，要卡的
    # 是清单里**真的标出了某个 id**——生产 prompt 里那是 `- 【硬锁】<id>（…）`
    # / `- 【软锁】<id>：` 这类行。
    assert not [ln for ln in prompt.splitlines()
                if ln.startswith("- 【硬锁】") or ln.startswith("- 【软锁】")]
    assert "硬锁 / 软锁 id 清单" in prompt
    assert "普通陪考句**取样时已排除" in prompt
    assert "本校准批不含锁定 id" not in prompt  # 旧措辞已修正，不该再出现
    # 对照：生产 prompt 在同一个夹具下**确实**会标出锁定 id=1（硬）与 3
    # （软），证明上面那条断言不是因为"这种行本来就不存在"而恒真。
    prod_lines = pc.render(m.label, 1, repo=m.root).splitlines()
    assert [ln for ln in prod_lines if ln.startswith("- 【硬锁】")]
    assert [ln for ln in prod_lines if ln.startswith("- 【软锁】")]


def test_calib_prompt_reads_frozen_not_live_repo(tmp_path):
    """与 `render()` 同一条铁律：只读 frozen/，不读活仓库的 glossary。"""
    m = _build_mini_seg(tmp_path, [(1, 3)])
    _make_calib(m, [{"id": 1, "batch": f"calib-{m.label}", "jp": "第1句テキスト",
                     "opus_zh": "第1句译文"}])
    (m.root / "glossary" / "style.md").write_text(
        "# 风格\n活仓库被改过了。", encoding="utf-8")
    prompt = pc.render_calib(m.label, repo=m.root)
    assert "活仓库被改过了" not in prompt
    assert "活仓库版本" in prompt          # frozen 里那一份


def test_cli_calib_writes_file_and_prints_hash(tmp_path, capsys):
    m = _build_mini_seg(tmp_path, [(1, 3)])
    _make_calib(m, [{"id": 1, "batch": f"calib-{m.label}", "jp": "第1句テキスト",
                     "opus_zh": "第1句译文"}])
    out = tmp_path / "calib_prompt.md"
    rc = pc.main(["--seg", m.label, "--calib", "--out", str(out),
                  "--repo", str(m.root)])
    assert rc == 0
    assert out.read_text(encoding="utf-8") == pc.render_calib(m.label, repo=m.root)
    assert len(capsys.readouterr().out.strip()) == 64      # sha256 十六进制
    # 刻意不写 plan.json：那份记录是给 polish_ingest 反查生产批 prompt_hash
    # 用的，而校准批的输出绝不入仓。
    assert not (m.seg_dir / "plan.json").exists()


# --- P5 契约 v2：prompt 新元素 ---

def test_render_carries_p5_additions(mini_seg_render):
    """P5 二轮补充（三问/两遍读/豁免提醒）与 alts 契约必须出现在生产 prompt 里。"""
    text = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "P5 二轮补充" in text
    assert "每行三问" in text
    assert "每批两遍读" in text
    assert "可选字段 `alts`" in text
    assert "至多 **2 条**备选候选" in text
    assert "v19 修订豁免清单不得回改" in text


def test_render_carries_zero_change_obligation(mini_seg_render):
    """守门条款的配平：零改动批须附批末说明（影子实测 0 改动事故的对策）。"""
    text = pc.render("segX", 1, repo=mini_seg_render.root)
    assert "不是\"不确定就别动\"的许可证" in text
    assert "整批零改动时" in text
    assert "批末说明" in text
