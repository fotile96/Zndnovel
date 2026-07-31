# Hotfix C（Task 5 全书路线跑通后暴露）：unit 发卡口径统一 + 全局 id 去重

**背景**：主会话已把全书 route_plan 草稿（223 条移动）在干跑谐波里调到「全局缺口 0 行、重复 0 行、ambient 混入 0 行、全部场景卡做成」。但那份谐波里预演了两条尚未落地的产码规则；不落地，真实 `gen_timeline.py` 跑出来的 timeline 会有 ~180 行重复 + 卡 141 链断裂。

本 Hotfix 在 Hotfix B 之上继续改同三个文件，**并把 B 的 fscene 特例替换成统一规则**（别留两套）。

## C1 — `Expander.emit_unit`：对「实际取到 id 的全部函数」生效 scene_meta 发卡

现状：`story()` 在 emit 之后对 `funcs`（play + subcall）逐个 `_apply_meta`；Hotfix B 又给 fscene 单独加了一遍。两处都不覆盖 **unit_funcs 附挂进来的函数**。

真实数据的反例：`snr_s7_10_f:scene_s7f_dispatch_v52` 在 dispatcher 里是带参调用（`scene_s7f_dispatch_v52("その『お話』の題名は――", 104, v1, 10)`），`PLAY_RE`/`SUBCALL_RE` 都抓不到，因此它是「孤儿函数」、只能靠 `config/unit_funcs.yaml` 附挂到相邻单元；而它恰恰授予卡 **111/112/113/141**。卡 141 是 `crd_94` 的 req，`crd_94` 又 `run` 了 `snr_s8_10_f`（授予卡 142），142 再门控 `s4s_100_sel`——一环断则第 8 章卡片、EX1/EX2 卡片、s4s_100_sel 的 3 行文本全部塌掉。

改法：把发卡统一到 `emit_unit` 里——**该 unit 实际匹配到的每个 `(file, func)`**（即 `_ids_for` 里 fnmatch 命中的那批，含 unit_funcs 附挂）都 `_apply_meta(fn)`。相应地：
- 删掉 `story()` 里 emit 之后的 `for f in funcs: self._apply_meta(f)`（已被 emit_unit 覆盖）；
- 删掉 Hotfix B 在 `fragment_sweep` 里给 fscene 加的那段 `_apply_meta` 循环（同样被覆盖）；
- `fragment_sweep` 里「crd 自身发卡」（`crds[cid]["gets"]`）**保留**——那不是 scene_meta，emit_unit 覆盖不到。

建议把「一个 unit 命中哪些函数」抽成一个方法（如 `_matched_funcs(file, funcs) -> set[str]`），`_ids_for` 与 `emit_unit` 共用，避免 fnmatch 逻辑抄两份。

## C2 — `Expander.emit_unit`：全局 id 去重

现状：不同状态可以共用同一批函数，于是同一条 vms 会被两个 unit 各 emit 一次。真实数据实测重复：
- `snr_s4_10_s`：两个探索场景 `s4s_210_sel` / `s4s_450_sel` 共用 `scene_s4s_dispatch_v14..v27`（约 50 行）；
- `snr_s4_10_s:scene_s4s_dispatch_v34`「物音」被 `s4s_300` 与 `s4s_310` 双方 play（35 行）。

计划的 A 段断言要求「每个 narrative id 恰好出现一次」，所以展开器必须保证之。

改法：`Expander` 持一个 `self._emitted_ids: set[int]`；`emit_unit` 写入 timeline 前把已出现过的 id 滤掉，再把剩下的登记进去。**unit 本身照常 emit**（即便 ids 被滤空）——它承载 `state`/`title`/`unit_kind`，是叙事节拍，不能丢。

## C3 — `check_timeline` 的 held 推导：改成「从 timeline 自身可导出」的超集

`check()` 的签名 `check(timeline, ledger_rows, dag, scene2card, gates)` 里**没有 unit_funcs**，所以它无法照抄展开器的内部口径。改用一条只依赖入参、且保证**不会比展开器更严**（不会误报）的推导：对每个 unit，把下面几路发卡取并集施加到 `held` ——

1. **由 ids 反查**：`{ledger_rows[i].func for i in unit["ids"]}` 的 `scene_meta.gets`（这一路自动覆盖 unit_funcs 附挂进来的函数，因为它们的 id 就在这个 unit 里）；
2. **scene unit**：`dag["states"][state]["seq"]` 里 `play` 与 `subcall` 两类事件的 `scene_meta.gets`；
3. **card unit**：`scene2card[state]` 那张卡本身 + `dag["crds"][str(cid)]["gets"]`；
4. **fscene / script unit**：该 `src` 文件在 `ledger_rows` 里出现过的全部 func 的 `scene_meta.gets`。

B 段（按 timeline 顺序累积）与 C 段（重扫 `timeline[:pos]`）继续共用同一个实现——就是 Hotfix B 已经抽好的那个共用辅助函数，只是把它的推导换成上面四路的并集。

**不要改动**：`check()` 的对外签名、四个中文错误关键词（重复/缺失/门控/req）、A 段覆盖断言。

## 测试要求（TDD，先红后绿，每条都要判别）

在 `tests/test_gen_timeline.py` / `tests/test_check_timeline.py` 补：
1. unit_funcs 附挂进来的函数，其 `scene_meta.gets` 生效（断言 emit 后 `held` 含该卡）——去掉 C1 必红。
2. 两个不同状态共用同一函数时，第二个 unit 的 `ids` 为空、第一个拿全（并断言该 unit 仍然出现在 timeline 里、`state`/`title` 完好）——去掉 C2 必红。
3. `check()` 对「卡 X 的 req 由 unit_funcs 附挂函数发卡满足」的合法 timeline 返回空错误列表——去掉 C3 第 1 路必红。
4. 回归：Hotfix B 补的 4 条用例保持绿（fscene 章梗概卡、crd 自身发卡、subcall 发卡等），若因删除 B 的 fscene 特例而需要调整断言写法，**行为断言不许放松**。

## 验收

```bash
uv run pytest -q         # 无回归
```

## 提交

`fix: unit 发卡口径统一到 emit_unit，timeline 全局 id 去重`（可与 check_timeline 的对齐拆两个 commit）。不要 push、不要建分支。
不要动 `config/route_plan.yaml`、`config/unit_funcs.yaml`、`config/gates.yaml`、`data/timeline.jsonl`、`data/scene2card.json`。
