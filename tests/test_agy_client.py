"""agy 通道客户端：注入 runner 离线测试，**不 spawn 真 agy**。

事件形状全部照 2026-08-14 的真实探针抄（记录见
`docs/ops/agy-cli-channel.md` §2 的实测事件 schema），不是照文档臆造的。
"""
import json

import pytest

from tools.agy_client import (
    AgyContaminated, AgyError, DEFAULT_MODEL, build_argv, chat, parse_stream)


def _ndjson(*objs):
    return [json.dumps(o, ensure_ascii=False) + "\n" for o in objs]


def _ok_stream(text="收到", model=DEFAULT_MODEL, tools=(), input_tokens=100,
               output_tokens=20, thinking=7, cached=0, status="SUCCESS"):
    """一条最小但形状真实的成功事件流。"""
    objs = [{"event": "init", "conversation_id": "cid",
             "init": {"model": model, "cwd": "/tmp/ws", "tools": ["search_web"],
                      "permission_mode": "request-review"}},
            {"event": "step_update",
             "step_update": {"step_index": 0, "state": "DONE", "step_type": "user_input"}}]
    for i, t in enumerate(tools):
        objs.append({"event": "step_update",
                     "step_update": {"step_index": i + 1, "state": "ACTIVE",
                                     "step_type": "tool", "tool_name": t,
                                     "tool_info": {"name": t, "parameters": {}}}})
        objs.append({"event": "step_update",
                     "step_update": {"step_index": i + 1, "state": "DONE",
                                     "step_type": "tool", "tool_name": t,
                                     "tool_info": {"name": t, "parameters": {}}}})
    objs.append({"event": "step_update",
                 "step_update": {"step_index": 9, "state": "DONE",
                                 "step_type": "agent_response", "text_delta": text}})
    objs.append({"event": "result",
                 "result": {"conversation_id": "cid", "status": status,
                            "response": text, "duration_seconds": 3.1, "num_turns": 1,
                            "usage": {"input_tokens": input_tokens,
                                      "output_tokens": output_tokens,
                                      "thinking_tokens": thinking,
                                      "cache_read_tokens": cached,
                                      "total_tokens": input_tokens + output_tokens}}})
    return _ndjson(*objs)


def _runner(lines, rc=0, stderr="", seen=None):
    def run(argv, *, cwd, env):
        if seen is not None:
            seen.append({"argv": argv, "cwd": cwd, "env": env})
        return iter(lines), lambda: (rc, stderr)
    return run


# ——正常路径 ——————————————————————————————————————————————

def test_chat_returns_content_and_writes_ledger(tmp_path):
    lp = tmp_path / "l.jsonl"
    r = chat([{"role": "user", "content": "hi"}], runner=_runner(_ok_stream()),
             ledger_path=lp, purpose="unit-test")
    assert r["content"] == "收到"
    assert r["prompt_tokens"] == 100 and r["completion_tokens"] == 20
    # thinking_tokens → reasoning_tokens、cache_read_tokens → cached_tokens 的映射
    assert r["reasoning_tokens"] == 7 and r["cached_tokens"] == 0
    row = json.loads(lp.read_text(encoding="utf-8").splitlines()[0])
    assert row["provider"] == "antigravity" and row["purpose"] == "unit-test"
    assert row["prompt_tokens"] == 100 and row["effort"] == "high"
    # 订阅制通道也拿得到 token，所以台账不该出现 handoff §6 设想的「缺列」降级
    assert "estimated" not in row and "failed" not in row
    assert isinstance(row["wall_seconds"], (int, float))


def test_on_delta_receives_text(tmp_path):
    got = []
    chat([{"role": "user", "content": "hi"}], runner=_runner(_ok_stream(text="abc")),
         ledger_path=tmp_path / "l.jsonl", on_delta=lambda k, t: got.append((k, t)))
    assert got == [("text", "abc")]


# ——三种已知失败形态（handoff §9 验收项）——————————————————————

def test_bogus_model_id_is_rejected(tmp_path):
    """实测：`--model __bogus__` → rc=1、status=ERROR、错误串在 result.error。"""
    lp = tmp_path / "l.jsonl"
    err = ('invalid model selection (--model "__bogus__" --effort ""): '
           "model __bogus__ is not recognized as a known model")
    lines = _ndjson({"event": "result",
                     "result": {"conversation_id": "", "status": "ERROR",
                                "response": "", "error": err,
                                "usage": {"input_tokens": 0, "output_tokens": 0,
                                          "thinking_tokens": 0, "cache_read_tokens": 0}}})
    with pytest.raises(AgyError, match="退出码 1"):
        chat([{"role": "user", "content": "hi"}], runner=_runner(lines, rc=1),
             ledger_path=lp)
    # 失败也入账，且标了 failed——不记会系统性低估花费
    assert json.loads(lp.read_text(encoding="utf-8").splitlines()[0])["failed"] is True


def test_eligibility_failure_is_rejected(tmp_path):
    """资格校验失败（探针 §四）：历史上这条 rc=0，错误只在文字里。

    故这里刻意用 **rc=0** 造型——判据不能只靠退出码，status 那一层必须独立生效。"""
    lines = _ndjson({"event": "result",
                     "result": {"status": "ERROR", "response": "",
                                "error": "Eligibility check failed: Your current "
                                         "account is not eligible for Antigravity"}})
    with pytest.raises(AgyError, match="Eligibility check failed"):
        chat([{"role": "user", "content": "hi"}],
             runner=_runner(lines, rc=0), ledger_path=tmp_path / "l.jsonl")


def test_zero_output_is_rejected(tmp_path):
    """rc=0 + status=SUCCESS + response 为空——本项目最警惕的「看起来正常」。

    实测触发方式：工具权限被拒，stderr 写 `no output produced`，其余一切正常。
    探针 §8.1 的「形式完美、实质为空」也落在这一层。"""
    lines = _ok_stream(text="")
    with pytest.raises(AgyError, match="零产出"):
        chat([{"role": "user", "content": "hi"}],
             runner=_runner(lines, rc=0,
                            stderr="jetski: no output produced — a tool required "
                                   "the \"write_file\" permission"),
             ledger_path=tmp_path / "l.jsonl")


# ——工具污染闸（彩野测试的命根子）——————————————————————————

@pytest.mark.parametrize("tool", ["search_web", "read_url_content",
                                  "open_browser_url", "call_mcp_tool"])
def test_forbidden_tool_invalidates_run(tool, tmp_path):
    """受试模型上网查了《セカンドノベル》剧情 → 彩野测试作废。

    ⚠ 实测 `search_web` **无法用配置关闭**（permissions.deny 与
    toolPermission=strict 都拦不住，见 agy_client 模块 docstring），所以这道
    事后检测闸是唯一的保护。删它等于让彩野测试静默失效。"""
    with pytest.raises(AgyContaminated, match=tool):
        chat([{"role": "user", "content": "hi"}],
             runner=_runner(_ok_stream(tools=[tool])),
             ledger_path=tmp_path / "l.jsonl")


def test_benign_tool_is_allowed(tmp_path):
    """只读本地文件之类的工具不该误杀——闸是针对「引入外部知识」的。"""
    r = chat([{"role": "user", "content": "hi"}],
             runner=_runner(_ok_stream(tools=["view_file", "grep_search"])),
             ledger_path=tmp_path / "l.jsonl")
    assert r["tools_used"] == ["grep_search", "view_file"]


# ——其余判据层 ——————————————————————————————————————————

def test_truncated_stream_is_rejected(tmp_path):
    """事件流在 result 之前断掉（进程被杀/管道断）——不能当成功。"""
    lines = _ok_stream()[:2]
    with pytest.raises(AgyError, match="result 事件到达前结束"):
        chat([{"role": "user", "content": "hi"}], runner=_runner(lines),
             ledger_path=tmp_path / "l.jsonl")


def test_model_echo_mismatch_is_rejected(tmp_path):
    """探针 §7.1 的形态：请求一个型号、实际跑了另一个，候选/计费全部张冠李戴。

    ⚠ init.model 只是**请求串的回声**，比对通过并不证明远端真用了它（见模块
    docstring）；但回声都对不上时一定有问题，所以这一层仍然守着。"""
    with pytest.raises(AgyError, match="模型回读不符"):
        chat([{"role": "user", "content": "hi"}],
             runner=_runner(_ok_stream(model="gemini-3.6-flash-high")),
             ledger_path=tmp_path / "l.jsonl")


def test_junk_lines_do_not_kill_the_run(tmp_path):
    lines = ["not json\n", "\n"] + _ok_stream()
    r = chat([{"role": "user", "content": "hi"}], runner=_runner(lines),
             ledger_path=tmp_path / "l.jsonl")
    assert r["content"] == "收到"


def test_missing_usage_is_marked_estimated_not_zero(tmp_path):
    """usage 缺失时写 -1 哨兵 + estimated，让 ledger_token 算成 unknown。
    写 0 会被 summarize_ledger 当成真实的 0 求和——静默低估（handoff §6）。"""
    lp = tmp_path / "l.jsonl"
    lines = _ndjson({"event": "init", "init": {"model": DEFAULT_MODEL}},
                    {"event": "result", "result": {"status": "SUCCESS", "response": "x"}})
    chat([{"role": "user", "content": "hi"}], runner=_runner(lines), ledger_path=lp)
    row = json.loads(lp.read_text(encoding="utf-8").splitlines()[0])
    assert row["estimated"] is True and row["prompt_tokens"] == -1

    from tools.api_client import ledger_token, summarize_ledger
    assert ledger_token(row, "prompt_tokens") is None
    assert summarize_ledger([row])["prompt_tokens"] == {"sum": 0, "n": 0, "unknown": 1}


# ——命令行组装的不变量 ————————————————————————————————

def test_argv_invariants():
    argv = build_argv("正文", model=DEFAULT_MODEL, effort="high", print_timeout="60m")
    # `--print` 是带值参数，必须在最后：探针 §7.4 记过被吞掉正文的真实事故
    assert argv[-2] == "--print" and argv[-1] == "正文"
    # 绝不放权：这个 flag 正是探针历次污染仓库的根因
    assert "--dangerously-skip-permissions" not in argv
    # 正文里的 `/` 开头行不得被当成斜杠命令展开
    assert "--disable-slash-commands" in argv
    assert "--sandbox" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"


def test_suffixed_model_with_effort_is_refused():
    """agy 实测：`--model gemini-3.7-flash-low --effort high` → conflicts with。
    与其把这个雷留到真机上炸，不如在组装参数前就拒掉。"""
    with pytest.raises(SystemExit, match="互斥"):
        chat([{"role": "user", "content": "hi"}], model="gemini-3.7-flash-low",
             effort="high", runner=_runner(_ok_stream()))


def test_unknown_effort_is_refused():
    """agy 只有 low|medium|high，不是 api_client 那套 none..max 七档。"""
    with pytest.raises(SystemExit, match="effort"):
        chat([{"role": "user", "content": "hi"}], effort="max",
             runner=_runner(_ok_stream()))


def test_empty_prompt_is_refused():
    with pytest.raises(SystemExit, match="prompt 为空"):
        chat([{"role": "system", "content": "  "}], runner=_runner(_ok_stream()))


def test_system_message_is_prepended_not_dropped():
    """agy 的 print 模式没有 system/user 之分——system 段必须拼进 prompt，不能丢。"""
    seen = []
    chat([{"role": "system", "content": "你是判分员"},
          {"role": "user", "content": "问题"}],
         runner=_runner(_ok_stream(), seen=seen), ledger_path="/dev/null")
    assert seen[0]["argv"][-1] == "你是判分员\n\n问题"


def test_repo_is_never_the_workspace(tmp_path):
    """仓库隔离靠机制：默认 cwd 是临时目录，且用完即删（handoff §7(a)）。"""
    seen = []
    chat([{"role": "user", "content": "hi"}],
         runner=_runner(_ok_stream(), seen=seen), ledger_path=tmp_path / "l.jsonl")
    from tools.pipelib import REPO
    cwd = seen[0]["cwd"]
    assert not str(cwd).startswith(str(REPO))
    import os
    assert not os.path.exists(cwd)      # 用完即删


def test_http_channel_kwargs_are_tolerated(tmp_path):
    """ayano_test 把一份 kw 同时喂给两条通道——HTTP 专属键不该炸掉本通道。"""
    r = chat([{"role": "user", "content": "hi"}], runner=_runner(_ok_stream()),
             ledger_path=tmp_path / "l.jsonl",
             api_key="sk-x", max_tokens=999, temperature=0.2, stream_transport=None)
    assert r["content"] == "收到"


def test_parse_stream_collects_tool_errors():
    lines = _ndjson({"event": "step_update",
                     "step_update": {"step_index": 6, "state": "ERROR",
                                     "step_type": "tool", "tool_name": "write_to_file",
                                     "tool_info": {"error": {
                                         "type": "TOOL_ERROR",
                                         "message": "User denied permission for "
                                                    "write_file(/repo/plan.json)."}}}})
    prog = parse_stream(lines)
    assert prog["tool_errors"][0]["tool"] == "write_to_file"
    assert "denied" in prog["tool_errors"][0]["error"]["message"]
