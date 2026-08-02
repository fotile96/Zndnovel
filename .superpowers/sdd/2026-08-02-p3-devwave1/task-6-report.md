# Task 6 报告：API 薄客户端 `tools/api_client.py`（deepseek）

## 做了什么

严格按 `task-6-brief.md` 的 Step 1–5 执行，代码逐字采用 brief 给出的版本，未做任何改写。

1. **Step 1**：按 brief 逐字写入 `tests/test_api_client.py`（3 条测试：写台账并返回 content、缺 key 时 SystemExit、`load_env` 解析引号与注释）。
2. **Step 2**：跑 `uv run pytest tests/test_api_client.py -v` → 确认失败（`ModuleNotFoundError: No module named 'tools.api_client'`），符合预期的"红"状态。
3. **Step 3**：按 brief 逐字写入 `tools/api_client.py`（`load_env`、`_http_transport`、`chat`、`main` CLI 入口；`PROVIDERS` 表作为提供商无关扩展点）。
4. **Step 4**：跑 `uv run pytest tests/test_api_client.py -v` → 3 passed。
5. **Step 5**：跑 `uv run pytest -q` → 全量 **261 passed**（基线 258 + 本任务新增 3，与父任务给出的目标数字一致；brief 文本里写的"254 passed"是过期数字，未采信，以实测为准）。
6. 仅 `git add tools/api_client.py tests/test_api_client.py`（未用 `-A`/`.`），提交前用 `git status --short` 核对暂存区只含这两个文件，工作树里另一会话正在改的 `.superpowers/sdd/2026-08-02-p3-seg1-s2/progress.md` 保持未暂存、未触碰。

## 命令与实际输出

```
$ uv run pytest tests/test_api_client.py -v          # Step 2（写测试后，实现前）
...
ERROR tests/test_api_client.py
E   ModuleNotFoundError: No module named 'tools.api_client'
1 error in 0.04s

$ uv run pytest tests/test_api_client.py -v          # Step 4（写实现后）
tests/test_api_client.py::test_chat_returns_content_and_writes_ledger PASSED [ 33%]
tests/test_api_client.py::test_missing_key_exits_with_guidance PASSED    [ 66%]
tests/test_api_client.py::test_load_env_parses_quotes_and_comments PASSED [100%]
3 passed in 0.08s

$ uv run pytest -q                                    # Step 5
261 passed in 1.50s
```

## 三条测试各自结果

- `test_chat_returns_content_and_writes_ledger`：PASSED —— 注入 `_fake_transport`，验证返回 `content`/`prompt_tokens`/`completion_tokens`，并验证 `ledger_path` 指向的 tmp_path 文件第一行 JSON 含 `purpose="unit-test"`、`provider="deepseek"`、`prompt_tokens=100`。
- `test_missing_key_exits_with_guidance`：PASSED —— `monkeypatch.delenv("DEEPSEEK_API_KEY")` + `monkeypatch.setattr("tools.api_client.load_env", lambda path=None: {})` 挡住真实环境变量与真实 `.env` 读取后，`chat(...)` 未传 `api_key` 时按预期抛 `SystemExit`，消息含 `DEEPSEEK_API_KEY`。
- `test_load_env_parses_quotes_and_comments`：PASSED —— 对 tmp_path 下手写的 `.env`（含 `# 注释` 行与带引号的值）解析正确，`DEEPSEEK_API_KEY == "sk-abc"`（去引号）、`OTHER == "1"`。

## 零真实网络请求确认

- 三条测试里，两条（写台账、缺 key）从不触达 `_http_transport`：前者显式传入 `transport=_fake_transport`（断言 `url.startswith("https://api.deepseek.com")` 但从未真正发包，只是构造并返回一个假 dict）；后者在拿到 key 之前就 `raise SystemExit`，函数体里连 `payload`/`headers` 都没构造到。第三条测试只跑 `load_env`，不涉及网络。
- 额外核查：仓库根 `ls -la .env` → 不存在；`env | grep -i DEEPSEEK` → 未设置。即便测试没有 monkeypatch 防护，本机当前也没有真 key 可用——但代码仍按 brief 要求做了 monkeypatch 隔离，为未来"本机真有 key"的场景兜底。
- 未调用过真实 `urllib.request.urlopen`（`_http_transport` 只在没有注入 `transport` 且拿到真 key 后才会被调用到，本任务全程未触发该分支）。

## 无 key 入库确认

- `git show db8d44f --stat`：仅 `tools/api_client.py`（+）与 `tests/test_api_client.py`（+），无 `.env`、无 `data/api_ledger.jsonl`。
- 代码与测试全文搜索确认不含任何真实 key 形态的字符串（测试里出现的 `sk-test`/`sk-abc` 都是 brief 指定的占位假值，非真实凭据）。
- `.gitignore` 第 9–10 行 `.env`/`.env.*` 未改动；仓库根未创建 `.env` 文件。
- `data/api_ledger.jsonl` 未被产生（`ls data/` 只看到既有的 `ledger.jsonl`、`ledger_extra.jsonl`，与本任务无关，是其他工具产物）。

## 偏差与处理

- brief Step 5 文本写"→ 254 passed"，与父任务交代的基线（258 passed，本任务后应为 261 passed）不一致。以实测为准：改动前基线未单独重跑（未改动其他文件，无必要），改动后实测 261 passed，与父任务给出的目标数字吻合，判定 brief 里的"254"是撰写时的过期基线数字，未采信、未据此改动任何代码。
- 未修改 `.gitignore`、未创建 `.env`、未 `uv add` 任何依赖，均符合安全纪律要求。
- 工作树里检测到另一会话（生产 SEG-1）对 `.superpowers/sdd/2026-08-02-p3-seg1-s2/progress.md` 的未暂存改动，全程未 `git add`/未触碰该文件。

## 自查结论

- 零真实网络请求发生：确认（两条相关测试均未触达 `_http_transport`/`urllib.request.urlopen`，本机也无真 key 可能意外触发真实调用）。
- 无 key 入库：确认（commit 仅含两个新文件，无 `.env`，无凭据字符串，`.gitignore` 未改动）。
