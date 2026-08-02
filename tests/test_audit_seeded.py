"""播种检验（spec §5.1 硬门）：人为构造已知被违反的承诺，审计必须报出未履行。

不通过即视为审计器不可用——本项目反复吃过「恒绿关卡比没有关卡更危险」的亏。
本测试用注入 runner，不发真实网络；它验的是**判定路径与阈值语义**，模型判断
质量另由 Task 6 的人工抽核负责。

**这个区分必须读懂，否则会高估本文件的保证范围**：

- 本文件**保证**的是：给定「材料里确实存在与承诺矛盾的字面事实」这一前提，
  (a) 那份材料确实被预拼进了送给模型的提示里（断言违规译文逐字出现在 user
  消息中），(b) 模型作出的「未履行」判断被如实传递、归类、并保住依据行 id，
  没有在三条机械闸/兜底逻辑里被静默改写成「已履行」或吞掉。
- 本文件**不保证**的是：真实模型面对同样的材料能不能看出那个矛盾。这里的
  runner 是一个确定性的机械裁判（按可复算规则读上下文后作答），不是模型。
  「模型判得准不准」只能由首次全量真跑后的人工抽核（spec §5.2）回答。

为了让断言不至于沦为「把答案硬编在假 runner 里」，三条违约用例与那条反向
用例**共用同一批裁判规则**：同一个 `_judge_runner(rule)`，喂违约数据出
「未履行」、喂合规数据出「已履行」。verdict 是数据的函数，不是常量。
"""
import json
import re

from tools import audit_notes_promises as A

# 送给模型的上下文行形如：
#   id 9441（s2s）
#     原文：……
#     译文：……
_CTX_LINE = re.compile(r"id (\d+)（[^）]*）\n  原文：(.*)\n  译文：(.*)")


def _parse_ctx(user_msg):
    """把 verify_promise 预拼进 user 消息的【相关行】读回结构化形式。

    机械裁判只允许看这里读回来的东西——与 spec §5.3「判定必须锚定可复算的
    字面事实」同一口径：它拿不到测试里的期望答案，只拿得到上下文。
    """
    return [{"id": int(i), "jp": jp, "zh": zh}
            for i, jp, zh in _CTX_LINE.findall(user_msg)]


def _judge_runner(rule):
    """确定性的机械裁判，冒充模型。

    `rule(lines) -> (verdict, evidence_ids, reason)`。裁判只读被预拼进提示的
    上下文，因此「材料没被拼进去」这类失败会让它判不出违约，用例随之变红——
    这正是我们要它守住的东西。
    """
    calls = []

    def fake(messages, **kw):
        user = messages[-1]["content"]
        calls.append({"user": user, "tool_names": kw.get("tool_names")})
        verdict, evidence, reason = rule(_parse_ctx(user))
        return {"content": json.dumps(
                    {"verdict": verdict, "evidence_ids": evidence, "reason": reason},
                    ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "tool_errors": 0,
                "stopped_reason": "finished", "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}

    fake.calls = calls
    return fake


# --- 三条机械规则（各对应一类承诺形态） -----------------------------------


def rule_uniform(target):
    """「本批已统一为 X」：每一行的译文都得含 X。"""
    def rule(lines):
        bad = [ln["id"] for ln in lines if target not in ln["zh"]]
        if bad:
            return "未履行", bad, f"以下行的译文不含统一译法「{target}」：{bad}"
        return "已履行", [ln["id"] for ln in lines], f"全部 {len(lines)} 行均含「{target}」"
    return rule


def rule_verbatim(lines):
    """「须逐字一致」：原文相同的行，译文必须相同。"""
    by_jp = {}
    for ln in lines:
        by_jp.setdefault(ln["jp"], []).append(ln)
    for group in by_jp.values():
        zhs = {g["zh"] for g in group}
        if len(zhs) > 1:
            ids = [g["id"] for g in group]
            return "未履行", ids, f"原文相同的 {ids} 译文却有 {len(zhs)} 种写法"
    return "已履行", [ln["id"] for ln in lines], "同原文组内译文一致"


def rule_preserve(lines):
    """「照原样保留、不得压平」：原文有字面差异的行，译文不得被压成同一句。"""
    by_zh = {}
    for ln in lines:
        by_zh.setdefault(ln["zh"], []).append(ln)
    for group in by_zh.values():
        if len({g["jp"] for g in group}) > 1:
            ids = [g["id"] for g in group]
            return "未履行", ids, f"{ids} 原文书写有别，译文却被压成同一句"
    return "已履行", [ln["id"] for ln in lines], "原文的字面差异在译文里仍可区分"


def _lines_stub(lines):
    return lambda name, args, lane_dir=None: {"lines": lines}


# --- 播种①：「已统一」被违反 ---------------------------------------------

SEED_UNIFORM_PROP = {
    "chapter": "s1s", "batch": 4, "num": 1, "title": "寝癖 → 睡翘的头发",
    "body": "- id 7327、7329、7332（本批 3 处）\n"
            "- 理由：两处措辞必须能对上。本批已按上述译法统一。\n",
}
# 播种点：7332 没按承诺的译法走。
SEED_UNIFORM_LINES = [
    {"id": 7327, "chapter": "s1s", "jp": "寝癖ついてる。", "zh": "头发睡翘了。"},
    {"id": 7329, "chapter": "s1s", "jp": "まだ寝癖が。", "zh": "头发还睡翘着。"},
    {"id": 7332, "chapter": "s1s", "jp": "寝癖、直った？", "zh": "乱翘的头发，弄好了？"},
]


def test_seeded_uniformity_promise_violation_is_reported(monkeypatch):
    """播种①「本批已按上述译法统一」被违反：3 行里 1 行没用统一译法。"""
    monkeypatch.setattr(A, "call_tool", _lines_stub(SEED_UNIFORM_LINES))
    runner = _judge_runner(rule_uniform("睡翘"))
    promise = {"kind": "已统一", "ids": [7327, 7329, 7332],
               "ids_source": "model", "prewire_ids": [7327, 7329, 7332],
               "ids_invalid": [], "quote": "本批已按上述译法统一",
               "quote_verified": True}

    out = A.verify_promise(promise, SEED_UNIFORM_PROP, runner=runner)

    assert out["verdict"] == "未履行", "播种的违约未被检出——审计器不可用（spec §5.1）"
    assert 7332 in out["evidence_ids"], "依据行必须指向真正违约的那一行"
    # 违约的字面事实确实被预拼进了提示，而不是靠 runner 里硬编的答案。
    assert "乱翘的头发，弄好了？" in runner.calls[0]["user"]


# --- 播种②：「须逐字一致」被违反 -----------------------------------------

SEED_VERBATIM_PROP = {
    "chapter": "s2s", "batch": 12, "num": 3, "title": "分支重复段须逐字一致",
    "body": "- id 8801、8802\n"
            "- 两支路共用同一句原文，译文须逐字一致；回改时整组同步。\n",
}
# 播种点：jp 完全相同，zh 却是两种写法。
SEED_VERBATIM_LINES = [
    {"id": 8801, "chapter": "s2s", "jp": "【アヤノ】「またね」", "zh": "【アヤノ】「回头见」"},
    {"id": 8802, "chapter": "s2s", "jp": "【アヤノ】「またね」", "zh": "【アヤノ】「再见啦」"},
]


def test_seeded_verbatim_promise_violation_is_reported(monkeypatch):
    """播种②「须逐字一致」被违反：两行 jp 相同、zh 不同。"""
    monkeypatch.setattr(A, "call_tool", _lines_stub(SEED_VERBATIM_LINES))
    runner = _judge_runner(rule_verbatim)
    promise = {"kind": "须逐字一致", "ids": [8801, 8802],
               "ids_source": "model", "prewire_ids": [8801, 8802],
               "ids_invalid": [], "quote": "译文须逐字一致；回改时整组同步",
               "quote_verified": True}

    out = A.verify_promise(promise, SEED_VERBATIM_PROP, runner=runner)

    assert out["verdict"] == "未履行", "播种的违约未被检出——审计器不可用（spec §5.1）"
    assert set(out["evidence_ids"]) == {8801, 8802}
    assert "再见啦" in runner.calls[0]["user"]


# --- 播种③：「照原样保留」被违反（真实数据 + 播种过的承诺） ---------------

# 依据行取自真实语料（s2s b37，id 9441/9460/9483）：9441/9483 作『人の事』、
# 9460 作『人のこと』，三行译文完全相同。这里把 jp/zh 逐字复制成合成夹具，
# **不读生产会话正在追加的车道文件**（brief §6）。
SEED_PRESERVE_LINES = [
    {"id": 9441, "chapter": "s2s",
     "jp": "【アヤノ】「ううん！ そんなこと、全然っ！ だって、私だって人の事言えるほど――」",
     "zh": "【アヤノ】「哪有！ 那种事，完全没有的！ 因为，我自己也没到能说别人的地步――」"},
    {"id": 9460, "chapter": "s2s",
     "jp": "【アヤノ】「ううん！ そんなこと、全然っ！ だって、私だって人のこと言えるほど――」",
     "zh": "【アヤノ】「哪有！ 那种事，完全没有的！ 因为，我自己也没到能说别人的地步――」"},
    {"id": 9483, "chapter": "s2s",
     "jp": "【アヤノ】「ううん！ そんなこと、全然っ！ だって、私だって人の事言えるほど――」",
     "zh": "【アヤノ】「哪有！ 那种事，完全没有的！ 因为，我自己也没到能说别人的地步――」"},
]
# 播种：这是把真实提案改写成与现行译文矛盾的副本（spec §5.1「改一份提案副本，
# 使其与现行译文矛盾」）。真实提案说的恰恰相反——「中文无从区分，三句同译」，
# 那是**已履行**；这里播种成「照原样保留、不得压成同一句」，于是必然违约。
SEED_PRESERVE_PROP = {
    "chapter": "s2s", "batch": 37, "num": 4, "title": "分支重复段的唯一字面差",
    "body": "- id 9441、9460、9483\n"
            "- 9441/9483 作『人の事言えるほど』，9460 作『人のこと言えるほど』。"
            "此处书写差异照原样保留、未拉平，三句不得压成同一句译文。\n",
}


def test_seeded_preserve_as_is_promise_violation_is_reported(monkeypatch):
    """播种③「照原样保留」被违反：jp 有细微书写差异，zh 却被压成同一句。

    数据是真实的（b37 的 9441/9460/9483），被播种的是承诺——真实提案登记的
    是「三句同译，此处留痕以免机械核对时误判」，属已履行；把它改写成
    「照原样保留、不得压平」后，现行译文就与之矛盾。
    """
    monkeypatch.setattr(A, "call_tool", _lines_stub(SEED_PRESERVE_LINES))
    runner = _judge_runner(rule_preserve)
    promise = {"kind": "照原样保留", "ids": [9441, 9460, 9483],
               "ids_source": "model", "prewire_ids": [9441, 9460, 9483],
               "ids_invalid": [], "quote": "此处书写差异照原样保留、未拉平，"
                                           "三句不得压成同一句译文",
               "quote_verified": True}

    out = A.verify_promise(promise, SEED_PRESERVE_PROP, runner=runner)

    assert out["verdict"] == "未履行", "播种的违约未被检出——审计器不可用（spec §5.1）"
    assert set(out["evidence_ids"]) == {9441, 9460, 9483}
    assert "人のこと言えるほど" in runner.calls[0]["user"]


# --- 反向用例：承诺确实被履行时不得报「未履行」 ---------------------------


COMPLIANT_CASES = [
    # 与播种①同一裁判、同一承诺，只把违约那一行改回合规。
    ("已统一", rule_uniform("睡翘"),
     [{"id": 7327, "chapter": "s1s", "jp": "寝癖ついてる。", "zh": "头发睡翘了。"},
      {"id": 7329, "chapter": "s1s", "jp": "まだ寝癖が。", "zh": "头发还睡翘着。"},
      {"id": 7332, "chapter": "s1s", "jp": "寝癖、直った？", "zh": "睡翘的头发弄好了？"}]),
    # 与播种②同一裁判：jp 相同、zh 也相同。
    ("须逐字一致", rule_verbatim,
     [{"id": 8801, "chapter": "s2s", "jp": "【アヤノ】「またね」", "zh": "【アヤノ】「回头见」"},
      {"id": 8802, "chapter": "s2s", "jp": "【アヤノ】「またね」", "zh": "【アヤノ】「回头见」"}]),
    # 与播种③同一裁判、同一批真实行：把 9460 的译文改成能体现差异的写法。
    ("照原样保留", rule_preserve,
     [dict(SEED_PRESERVE_LINES[0]),
      dict(SEED_PRESERVE_LINES[1], zh="【アヤノ】「哪有！ 那种事，完全没有的！ "
                                       "因为，我自己也没到能说人家的地步――」"),
      dict(SEED_PRESERVE_LINES[2])]),
]


def test_fulfilled_promise_is_not_reported_as_unfulfilled(monkeypatch):
    """反向：承诺确实被履行时不得报「未履行」。

    三种承诺形态各一组合规数据，与上面的播种用例**共用同一裁判规则**，只换
    数据——若这里也报「未履行」，说明上面三条绿是「无论喂什么都判违约」造成
    的假绿，播种检验本身就失去意义。
    """
    for kind, rule, lines in COMPLIANT_CASES:
        monkeypatch.setattr(A, "call_tool", _lines_stub(lines))
        runner = _judge_runner(rule)
        promise = {"kind": kind, "ids": [ln["id"] for ln in lines],
                   "ids_source": "model", "prewire_ids": [ln["id"] for ln in lines],
                   "ids_invalid": [], "quote": "（合规对照组）", "quote_verified": True}

        out = A.verify_promise(promise, SEED_UNIFORM_PROP, runner=runner)

        assert out["verdict"] != "未履行", f"{kind}：合规数据被误报为未履行"
        assert out["verdict"] == "已履行", f"{kind}：合规数据未被判为已履行"
