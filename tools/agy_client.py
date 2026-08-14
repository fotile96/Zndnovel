"""Antigravity CLI（`agy`）通道客户端：**subprocess 形态**的外部模型通道。

与 `tools/api_client.py`（HTTP/SSE，deepseek Responses API）并列的第二条通道。
对外暴露与 `api_client.chat()` **同名同形**的 `chat()`，返回 dict 的
`content`/`prompt_tokens`/`completion_tokens`/`cached_tokens`/`reasoning_tokens`
/`model`/`provider`/`status` 语义与之一致，故 `tools/ayano_test.py` 只需换一个
函数引用即可切换通道。

## ⚠ 不要走 paseo（用户 2026-08-14 裁定）

`docs/ops/paseo-antigravity-probe.md` 里大段篇幅在讲经 paseo 的
`antigravity-acp` provider——**那不是本模块的路线，也不要照着修**。paseo 侧的
对接是社区 extension、非官方支持、功能不完整（§7.2 `bypassPermissions` 建不出
agent、§7.3 写文件静默无效都是它的缺陷）。本模块**直连本机 `agy` 可执行文件**。

## 架构选择：为什么另起一个模块，而不是往 `PROVIDERS` 里加一条（handoff §4.1 甲/乙）

选 **（乙）**。`api_client.PROVIDERS` 的表项形状是 `{url, key_env, default_model}`
——三个键对 subprocess 通道**一个都不成立**（没有 URL、没有 API key、模型表由
`agy models` 决定）。更要紧的是 `api_client` 的模块 docstring 与大半注释在讲
Responses API、SSE 逐 chunk 静默超时、`cached_tokens` 命中率、429 `Retry-After`
——这些对本通道全部不适用。把 subprocess 分支塞进 `chat()` 会让那份写得很准的
文档变成半真半假，而**注释一旦半真半假就比没有注释更坏**（这条教训
`ayano_test.VERDICT_WORDS` 上方已经吃过一次）。

读侧不重复造轮子：`ledger_token` / `summarize_ledger` 直接复用 `api_client` 的
——台账消费口径必须只有一份。只有写侧（多一列 `wall_seconds`）是本模块自己的。

## 官方文档要点（2026-08-14 查证，https://antigravity.google/docs/cli/headless）

- `--output-format` ∈ `text|json|stream-json`。`stream-json` 是 NDJSON：一条
  `init`、零或多条 `step_update`、一条终结 `result`（其载荷与 `json` 档相同）。
- `result` 载荷字段：`conversation_id` / `status` / `response` / `error` /
  `duration_seconds` / `num_turns` / `structured_output` / `usage`。
  `status` ∈ `SUCCESS|ERROR|CANCELED|INTERRUPTED|INVALID|WAITING|RUNNING`。
- `usage` 四元组：`input_tokens` / `output_tokens` / `thinking_tokens` /
  `cache_read_tokens` / `total_tokens`——**订阅制通道居然给了 token 数**，故台账
  四列全部有真值可写，不需要 handoff §6 设想的「缺键即未知」降级。
- `--json-schema` 接受 schema 串/文件路径/基元类型名，解析结果落在 `structured_output`；
  **对 stream-json 只作用于最终 result**。
- `--continue` / `--conversation <id>` 续接会话。
- 官方称「Unknown models cause non-zero exit」——**已实测为真**，见下。

**查不到的**：`--add-dir` / `--project` / `--new-project` 的确切 workspace 语义
（官方文档站没有 CLI flag 参考页，`/docs/cli/reference` 只讲斜杠命令与配置键），
配额/计费口径（只有 TUI 的 `/credits`、`/usage` 斜杠命令，无 headless 等价物）。
下面凡标「实测」的结论一律以本机 agy **1.1.12** 的探针为准，不以文档为准。

## ⚠⚠ 最重要的一条：`search_web` 关不掉，彩野测试**必须**靠事后检测

`agy` 的工具表有 56 项，其中 `search_web` / `read_url_content` /
`open_browser_url` / `browser_*` / `call_mcp_tool` 全部默认可用。这正是
`api_client._validate_tools` 拼命防守的那个失效模式——**受试模型上网查
《セカンドノベル》剧情，不看译文也能答对，彩野测试静默失效**。

实测（2026-08-14，隔离 HOME + 自带 settings.json）：

| 尝试的关法 | 结果 |
|---|---|
| `permissions.deny: ["read_url(*)","execute_url(*)","mcp(*)","command(*)"]` | ❌ `search_web` 照跑 |
| 追加 `deny: ["search_web(*)", ...]` | ❌ 且 agy 回写 settings 时**静默丢弃**这些条目（不是合法 action 名） |
| `toolPermission: "strict"`（init 回读确认 `permission_mode=strict` 已生效） | ❌ `search_web` 照跑 |

两次探针里它都真的搜到了并复述出「15 分钟顺行性遗忘 / 五年前事故 / 亲友之死」
——**恰好就是彩野测试要考的东西**。官方文档列出的 action 类别只有
`read_file/write_file/read_url/execute_url/command/unsandboxed/mcp`，
`search_web` 不属于其中任何一类，**配置层没有关它的手段**。

故本模块的立场是：**预防不可得，检测必须有**。`chat()` 扫描事件流里每一次
工具调用，命中 `FORBIDDEN_TOOLS` 即抛 `AgyContaminated` 作废本次调用。
检测消不掉已经发生的污染，但能让它**可见且不进结论**——这是当前能给到的最强保证。
⚠ 不要因为「提示词里没让它搜」就删掉这道闸：它防的正是模型**自发**去搜。

## ⚠ 判据：退出码可用，但**远远不够**（handoff §5）

handoff 依据探针 §一 断言「这条链上的失败全部返回退出码 0，绝不能用退出码判断」。
**该结论在 agy 1.1.12 上已不成立**，实测：

| 形态 | rc | status |
|---|---|---|
| `--model __bogus_model_id__` | **1** | `ERROR`（错误串在 stderr / result.error） |
| `--model <带后缀> --effort <档>` 冲突 | **1** | `ERROR` |

但**退出码仍然不是充分判据**——最危险的那一类照样 rc=0：

| 形态 | rc | status | 实况 |
|---|---|---|---|
| 工具权限被拒、**一个字都没产出** | **0** | **SUCCESS** | `response` 为空串，真相只在 stderr 的 `no output produced` |
| 上网查了答案再作答 | **0** | **SUCCESS** | 看 `response` 完全正常 |

所以 `chat()` 的判据是**多层与**：rc==0 且 收到 result 且 status==SUCCESS 且
`response` 非空 且 未命中禁用工具 且 模型回读一致。任何一层不过即抛。

## ⚠ 模型「回读」只是回声，不是独立确认

`init.model` 回读的是**我们请求的那个字符串**，不是远端解析后的真实型号
（探针 §7.1 那次「静默落到别的模型」正是回声看不出来的形态）。本模块仍然比对它
（不符即抛），但**它证明不了远端真的用了这个模型**。真正的强证据是「假 id 被拒」
——说明 flag 确实被校验了；本模块把 `--model` 必传写死，不依赖任何默认值。

## 其他实测约定

- **模型后缀与 `--effort` 互斥**：`--model gemini-3.7-flash-low --effort high` 直接
  报 `conflicts with`。故本模块**只发裸模型名 + `--effort`**，并在参数校验时
  拒绝带 `-high/-medium/-low` 后缀的模型名——两种写法混用是纯粹的踩雷面。
- **`--disable-slash-commands` 默认必带**：print 模式会展开斜杠命令与 skill。
  本项目的 prompt 是长正文（润色轨 760KB），正文里出现 `/` 开头的行会被当成命令
  展开——一个不报错、结果全错的形态。关掉它。
- **`--sandbox` 默认开**：macOS 上走 `sandbox-exec`，限制 agent 发起的终端命令的
  绝对路径文件访问与裸 TCP。探针 §9.3(a) 那次污染（跑 `polish_context.py` 覆盖了
  已 tag 段的 `plan.json`）正是**终端命令**造成的，故这道闸对症。
  ⚠ 但它**只管终端命令**，不管 `write_to_file` 工具——后者靠下面这条。
- **绝不传 `--dangerously-skip-permissions`**。探针历次都带着它，而它的作用正是
  「auto-approve all tools」。不带它时实测：workspace 之外的 `write_to_file`
  被拒（`User denied permission for write_file(...)`），仓库零污染。
  **仓库隔离因此是机制性的，不再依赖提示词条款**（handoff §7(a) 的硬要求）。
- **agent 眼里的「当前目录」不是进程 cwd**：实测让它写相对路径 `inside.txt`，
  文件落在了 `~/.gemini/antigravity-cli/scratch/`。故**不要让它写文件**——
  本通道的产物一律从 `result.response` 取回，由调用方自己落盘。这同时绕开了
  探针 §9.2「它把文件内容打进 stdout 而不落盘」那个问题：对本模块而言，
  打进 stdout 本来就是唯一约定的交付方式。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO
from tools.api_client import ledger_token, summarize_ledger  # noqa: F401  读侧口径复用

PROVIDER = "antigravity"
DEFAULT_MODEL = "gemini-3.7-flash"
# agy 只有三档（low|medium|high），没有 api_client 那套 none..max。取最高档，与
# `api_client.DEFAULT_EFFORT="max"` 同一政策方向：外部通道一律用最强推理力度。
DEFAULT_EFFORT = "high"
EFFORTS = ("low", "medium", "high")
EFFORT_SUFFIXES = tuple(f"-{e}" for e in EFFORTS)

# print 模式的总时长上限（agy 自己的看门狗，默认仅 5m）。
# **为什么不像 api_client 那样自己实现逐 chunk 静默超时**：那边的 idle timeout 是
# 为「HTTP 连接可能静默僵死、socket 层察觉不到」设计的；subprocess 没有这个问题
# ——进程死了立刻 EOF，进程活着但卡住由 `--print-timeout` 兜底。多加一层看门狗
# 只会多一个可能误杀的部件。
DEFAULT_PRINT_TIMEOUT = "60m"

# 命中即作废本次调用。理由见模块 docstring「search_web 关不掉」一节。
# 宁严勿松：凡是能把**文本之外的知识**带进上下文的工具全列进来。
FORBIDDEN_TOOLS = frozenset({
    "search_web",
    "read_url_content",
    "open_browser_url",
    "read_browser_page",
    "browser_subagent",
    "execute_browser_javascript",
    "call_mcp_tool",
    "read_resource",
    "generate_image",
})

TERMINAL_STATUS_OK = "SUCCESS"


class AgyError(RuntimeError):
    """本次 agy 调用不可信。`partial` 挂上已解析到的进度快照（可能为 None）。"""

    def __init__(self, message, *, partial=None):
        super().__init__(message)
        self.partial = partial


class AgyContaminated(AgyError):
    """受试模型调用了能引入外部知识的工具——彩野测试的结论就此作废。"""


def _check_model_effort(model: str, effort):
    if not model:
        raise SystemExit("agy 通道必须显式指定 --model（不依赖 agy 的默认模型）")
    if model.endswith(EFFORT_SUFFIXES):
        raise SystemExit(
            f"模型名 {model!r} 带档位后缀，与 --effort 互斥（agy 实测直接报 "
            f"conflicts with）。本通道只收裸模型名 + effort，例如 "
            f"model='gemini-3.7-flash', effort='high'。")
    if effort is not None and effort not in EFFORTS:
        raise SystemExit(f"agy 的 effort 只有 {EFFORTS}，收到 {effort!r}"
                         f"（注意与 api_client 的 none..max 七档不是一回事）")


def _flatten_messages(messages) -> str:
    """`[{role, content}]` → 单个 prompt 串。

    agy 的 print 模式只吃一个 prompt，没有 system/user 之分，也没有多轮入参
    （多轮要靠 `--continue`）。故把 system 段以醒目分隔拼在最前——与
    `api_client._split_messages` 把 system 塞进 `instructions` 是同一意图的
    不同落点，**不是**丢弃。"""
    sys_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    turns = [m.get("content", "") for m in messages if m.get("role") != "system"]
    blocks = []
    if any(sys_parts):
        blocks.append("\n\n".join(p for p in sys_parts if p))
    blocks.extend(t for t in turns if t)
    return "\n\n".join(blocks)


def build_argv(prompt, *, model, effort, print_timeout, sandbox=True,
               disable_slash_commands=True, json_schema=None, extra_flags=()):
    """组装 agy 命令行。⚠ `--print` 是**带值参数**，必须放在最后一组——
    探针 §7.4 记过一个真实事故：`agy --print --dangerously-skip-permissions "<正文>"`
    被解析成「prompt＝那个 flag」，正文被丢掉而它一本正经地讲解那个 flag。"""
    argv = ["agy", "--output-format", "stream-json",
            "--print-timeout", print_timeout, "--model", model]
    if effort is not None:
        argv += ["--effort", effort]
    if sandbox:
        argv.append("--sandbox")
    if disable_slash_commands:
        argv.append("--disable-slash-commands")
    if json_schema is not None:
        argv += ["--json-schema", json_schema]
    argv += list(extra_flags)
    argv += ["--print", prompt]
    return argv


def _subprocess_runner(argv, *, cwd, env):
    """默认 runner。契约：返回 `(lines, finish)`——`lines` 惰性产出 stdout 行
    （让 `on_delta` 能实时回调），`finish()` 在 lines 耗尽后返回 `(rc, stderr)`。

    测试注入同形的假 runner 即可离线驱动解析逻辑，**不 spawn 真 agy**
    （与 `api_client` 的 `stream_transport` 注入点同一意图）。"""
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace")

    def lines():
        for line in proc.stdout:
            yield line

    def finish():
        stderr = proc.stderr.read()
        proc.stdout.close()
        proc.stderr.close()
        return proc.wait(), stderr

    return lines(), finish


def parse_stream(lines, *, on_delta=None) -> dict:
    """把 stream-json 的 NDJSON 行流解析成进度快照。

    非 JSON 行不炸掉整次调用（半行/未来协议变化），只记进 `junk`——与
    `api_client.iter_sse_events` 对坏 data 的处理同向。"""
    prog = {"init": None, "result": None, "text": [], "tools": [],
            "tool_errors": [], "junk": 0, "events": 0}
    for raw in lines:
        line = raw.strip() if isinstance(raw, str) else raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            prog["junk"] += 1
            continue
        if not isinstance(obj, dict):
            prog["junk"] += 1
            continue
        prog["events"] += 1
        ev = obj.get("event")
        if ev == "init":
            prog["init"] = obj.get("init") or {}
        elif ev == "result":
            prog["result"] = obj.get("result") or {}
        elif ev == "step_update":
            b = obj.get("step_update") or {}
            name = b.get("tool_name")
            if name and b.get("state") == "ACTIVE":
                prog["tools"].append(name)
            err = (b.get("tool_info") or {}).get("error")
            if err:
                prog["tool_errors"].append({"tool": name, "error": err})
            d = b.get("text_delta")
            if d and b.get("step_type") == "agent_response":
                prog["text"].append(d)
                if on_delta:
                    on_delta("text", d)
    return prog


def _usage_of(prog) -> dict:
    """`result.usage` → 台账四元组。映射见模块 docstring。

    拿不到 usage（result 缺失/字段缺失）时用 -1 哨兵并标 estimated——与
    `api_client._usage_of` 同一约定，好让 `ledger_token` 把它算成 unknown 而
    **不是 0**（把未知当 0 求和是静默低估，handoff §6 特意点过）。"""
    u = ((prog.get("result") or {}).get("usage")) or {}
    if not u:
        return {"prompt_tokens": -1, "completion_tokens": -1, "cached_tokens": -1,
                "reasoning_tokens": -1, "estimated": True}
    return {"prompt_tokens": u.get("input_tokens", -1),
            "completion_tokens": u.get("output_tokens", -1),
            "cached_tokens": u.get("cache_read_tokens", -1),
            "reasoning_tokens": u.get("thinking_tokens", -1),
            "estimated": False}


def _write_ledger(lp, *, model, purpose, usage, effort, wall_seconds, failed=False):
    """台账行。列名与 `api_client._write_ledger` 保持一致（同一个账本，消费侧
    `summarize_ledger` 按列汇总，列名一漂就统计不到一起去），额外多两列：

    - `wall_seconds`：agy 是订阅制，token 之外「耗时」是判费效比的主要依据
      （SEG-6 评 kimi 时用的就是耗时 + 滚动用量，见 channel_feedback.md §七）。
    - `failed`：只在失败行上出现。失败也要入账——请求已经发出、token 已经花掉，
      不记就系统性低估（与 api_client 的 partial 行同一理由）。
    """
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "provider": PROVIDER,
           "model": model, "purpose": purpose,
           "prompt_tokens": usage["prompt_tokens"],
           "completion_tokens": usage["completion_tokens"],
           "cached_tokens": usage["cached_tokens"],
           "reasoning_tokens": usage["reasoning_tokens"],
           "wall_seconds": round(wall_seconds, 2)}
    if effort is not None:
        row["effort"] = effort
    if usage["estimated"]:
        row["estimated"] = True
    if failed:
        row["failed"] = True
    with open(lp, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def chat(messages, *, model=None, effort=DEFAULT_EFFORT, purpose="",
         ledger_path=None, workspace=None, runner=None, on_delta=None,
         print_timeout=DEFAULT_PRINT_TIMEOUT, sandbox=True,
         json_schema=None, forbidden_tools=FORBIDDEN_TOOLS,
         env=None, provider=PROVIDER, **_ignored) -> dict:
    """调一次 agy，返回与 `api_client.chat()` 同形的 dict。

    `**_ignored` 吸收调用方为 HTTP 通道准备的入参（`api_key`/`max_tokens`/
    `temperature`/`stream_transport`/`timeout`/`retries` 等）——`ayano_test.main()`
    把一份 kw 同时喂给两条通道，这里静默忽略不适用的键，比让调用方分叉两套
    kw 组装逻辑干净。⚠ 但**不吸收** `model`/`effort`：那两个必须显式且被校验。

    `workspace`：agy 进程的 cwd。默认建一个临时目录并在结束后删除——**绝不用
    仓库目录**（handoff §7(a)：隔离靠机制不靠提示词）。

    `runner`：注入点，签名见 `_subprocess_runner`。测试用假 runner 离线驱动。

    不重试。理由：本通道的失败形态（模型名错、权限被拒、工具污染）**全部是
    确定性的**，重试一次只会再花一次钱得到同样结果；而真正值得重试的网络抖动
    发生在 agy 进程内部，由它自己处理。
    """
    model = model or DEFAULT_MODEL
    _check_model_effort(model, effort)
    prompt = _flatten_messages(messages)
    if not prompt.strip():
        raise SystemExit("prompt 为空——不发。")
    argv = build_argv(prompt, model=model, effort=effort,
                      print_timeout=print_timeout, sandbox=sandbox,
                      json_schema=json_schema)

    tmp = None
    if workspace is None:
        tmp = tempfile.mkdtemp(prefix="agy-ws-")
        workspace = tmp
    lp = Path(ledger_path) if ledger_path else REPO / "data" / "api_ledger.jsonl"
    run = runner if runner is not None else _subprocess_runner
    t0 = time.time()
    try:
        lines, finish = run(argv, cwd=workspace, env=env or dict(os.environ))
        prog = parse_stream(lines, on_delta=on_delta)
        rc, stderr = finish()
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    wall = time.time() - t0
    usage = _usage_of(prog)

    def fail(msg, cls=AgyError):
        _write_ledger(lp, model=model, purpose=purpose, usage=usage, effort=effort,
                      wall_seconds=wall, failed=True)
        raise cls(msg, partial=prog)

    # ——判据（多层与，任何一层不过即作废）。顺序：先报最有信息量的那一层。
    result = prog["result"] or {}
    if rc != 0:
        fail(f"agy 退出码 {rc}：{(result.get('error') or stderr or '').strip()[:800]}")
    if prog["result"] is None:
        fail(f"事件流在 result 事件到达前结束（收到 {prog['events']} 个事件）"
             f"：{stderr.strip()[:400]}")
    status = result.get("status")
    if status != TERMINAL_STATUS_OK:
        fail(f"status={status!r}：{(result.get('error') or stderr or '').strip()[:800]}")
    hits = sorted(set(prog["tools"]) & set(forbidden_tools))
    if hits:
        fail(f"受试模型调用了禁用工具 {hits}——本次结论作废（它可能拿到了译文之外的"
             f"知识，彩野测试就此失效）。", AgyContaminated)
    content = result.get("response") or ""
    if not content.strip():
        # 探针 §8.1「形式完美、实质为空」与本次实测的「权限被拒但 SUCCESS」都落在这里。
        fail(f"status=SUCCESS 但 response 为空（零产出）。stderr：{stderr.strip()[:400]}")
    echoed = (prog["init"] or {}).get("model")
    if echoed and echoed != model:
        fail(f"模型回读不符：请求 {model!r}，init 回读 {echoed!r}")

    _write_ledger(lp, model=model, purpose=purpose, usage=usage, effort=effort,
                  wall_seconds=wall)
    return {"content": content,
            # agy 不下发推理正文（只给 thinking_tokens 计数），故恒为空串。
            # 保留这个键是为了与 api_client 同形——`ayano_test` 会读它做 CoT 摘要，
            # 缺键会 KeyError。⚠ 代价：本通道的彩野报告里「CoT 摘要」一栏恒为
            # 「无 CoT」，即**判不了「真读出来 vs 猜」**，这是通道能力差异，不是 bug。
            "reasoning_text": "",
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "cached_tokens": usage["cached_tokens"],
            "reasoning_tokens": usage["reasoning_tokens"],
            "model": model, "provider": provider,
            "status": status,
            "conversation_id": result.get("conversation_id", ""),
            "structured_output": result.get("structured_output"),
            "wall_seconds": wall,
            "tools_used": sorted(set(prog["tools"])),
            "tool_errors": prog["tool_errors"]}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default=DEFAULT_EFFORT, choices=list(EFFORTS))
    ap.add_argument("--purpose", default="agy-cli-smoke")
    ap.add_argument("--print-timeout", default=DEFAULT_PRINT_TIMEOUT)
    ap.add_argument("--workspace", default=None)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--no-sandbox", action="store_true")
    a = ap.parse_args(argv)
    r = chat([{"role": "user", "content": a.prompt}], model=a.model, effort=a.effort,
             purpose=a.purpose, print_timeout=a.print_timeout,
             workspace=a.workspace, ledger_path=a.ledger, sandbox=not a.no_sandbox)
    print(r["content"])
    print(f"[{r['provider']}/{r['model']} effort={a.effort} "
          f"tokens {r['prompt_tokens']}(cached {r['cached_tokens']})"
          f"+{r['completion_tokens']}(thinking {r['reasoning_tokens']}) "
          f"{r['wall_seconds']:.1f}s tools={r['tools_used']}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
