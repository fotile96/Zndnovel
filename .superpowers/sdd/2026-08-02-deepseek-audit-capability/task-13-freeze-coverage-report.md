# Task 13：冻结校验补 style/voices 覆盖缺口——报告

## 状态

完成。505 → 514 测试全绿（新增 9 条）。

## 改动

- `tools/lane_setup.py`：
  - 新增 `_sha256_dir()`：目录（`glossary/voices/`）确定性哈希。按文件名排序后
    逐份把「文件名长度前缀 + 文件名 + 内容长度前缀 + 内容」喂进同一个 sha256。
  - `freeze_hashes()` 新增 `"style"`（`sha256_file(glossary/style.md)`）与
    `"voices"`（`_sha256_dir(glossary/voices/)`）两项，冻结集从 5 项变 7 项。
  - `CROSS_LANE_KEYS` 加入 `"style"`、`"voices"`，注释同步更新。
  - `verify()` 逐车道自比前新增缺键检测：`missing_keys = sorted(set(got) - set(want))`，
    非空则追加一条明确、可操作的漂移描述（点名具体缺的键 + 提示 `--force` 重新冻结
    或 `record(force=True)`），随后仍继续对 `want` 里已有的键做原有比对——缺键
    提示不会掩盖旧键（如 `active`）的真实漂移。
- `tests/test_lane_setup.py`：`_repo()` fixture 补 `glossary/voices/`（2 份 .md）；
  更新 1 条既有测试（键集断言），新增 9 条：style 漂移检测、voices 内容漂移检测、
  voices 目录哈希对改名/增删文件敏感（各 1 条）、style/voices 跨车道不一致检测
  （各 1 条）、`CROSS_LANE_KEYS` 内容断言、旧 manifest 缺新键场景（3 条：报漂移
  且点名缺键、不掩盖已有键的真实漂移、）。

## 目录哈希算法（一行）

按文件名排序后把每份文件的「文件名长度前缀+文件名+内容长度前缀+内容」依次喂进
同一个 sha256；文件名必须纳入摘要，否则整份文件被删除、或内容不变仅改名（如
`naoya.md`→`naoya2.md`），纯内容拼接哈希认不出区别——长度前缀是为了避免文件名/
内容边界因直接拼接产生的歧义碰撞。

## (c) 向后兼容处理（一行）

`verify()` 遇到「记录的键集合是当前键集合的真子集」（旧 manifest 缺 style/voices）
时，不静默跳过、不抛异常，而是追加一条点名具体缺失键、并提示跑
`lane_setup.py --lane <lane> ... --force`（或 `record(force=True)`）重新冻结的
漂移描述，同时继续用 `want` 里已有的键做原有的逐键比对。

## 变异自检

- 变异 1：从 `freeze_hashes()` 删掉 `"voices"` 键（用脚本做定点删除，非目测）——
  跑测试：7 个测试变红，其中直接命中 `test_verify_detects_drift_in_style` 及多个
  cross-lane/覆盖集测试；确认变异确实改到了目标行（删除后 `grep '"voices"'`
  只剩 `CROSS_LANE_KEYS` 那一处引用），而非误删同名字符串的其他出现——已核实
  该键在文件中只出现一次作为 dict 项。红后已还原，`uv run pytest -q` 回到全绿。
- 变异 2：把 `missing_keys`/追加漂移描述那段代码整体删掉，还原成「静默用
  `want.items()` 遍历，缺键就跳过不查」的旧形态——跑测试：精确 1 个测试变红
  （`test_verify_flags_stale_manifest_missing_new_freeze_keys`），其余 33 个仍绿
  （含 `test_verify_stale_manifest_missing_keys_still_checks_keys_it_does_have`，
  证明该测试确实在检验「缺键提示」这一具体行为，而不是凑巧被别的断言带绿）。
  确认变异打中目标：失败原因是 `assert drift`（`assert []`）——即静默放行复现。
  红后已还原，`uv run pytest -q` 回到全绿。

## `--verify` 实跑真实车道（tail）

```
fable: manifest 缺少冻结键 ['style', 'voices']——这些项从未被校验过（不代表未漂移，
只是从来没查）。请对该车道重新冻结：跑 `python tools/lane_setup.py --lane fable
--model <model> --effort <effort> --append-model-id <id> --force`（或直接调用
record(force=True)）补齐后再校验。
opus: manifest 缺少冻结键 ['style', 'voices']——同上。
（exit code 1）
```

与预期一致：车道内 `style.md`/`voices/` 内容与仓库已由控制器同步一致（`diff`/
`diff -r` 均无差异），但 `pilot-manifest.json` 里两条车道的记录都是旧版
`freeze_hashes` 留下的 5 键，触发 (c) 的提示而非漏报「无漂移」。未对
`pilot-manifest.json` 做任何写入或修改（未跑 `--force`，只读校验）。

## 顾虑

- 未对 `pilot/lanes/pilot-manifest.json` 执行 `--force` 重新冻结（按纪律不得碰
  `pilot/lanes/` 下任何文件）——两条车道目前仍会在 `--verify` 时报「缺键」提示，
  需要另一次显式、经用户确认的 `--force` 操作补齐 style/voices 基准。
- `_sha256_dir` 只 glob `*.md`（与 `build_context.py::_render_voices` 的渲染范围
  严格对齐）；若未来 `voices/` 下混入非 `.md` 文件，该文件既不会被渲染进
  `context.md`，也不会计入冻结哈希——行为一致，非缺陷，但值得留意。
