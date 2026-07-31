# Hotfix B（Task 5 全书验证暴露）：发卡语义三处补齐

**背景**：主会话在编写全书 route_plan（Task 5 Step 2）时用干跑谐波驱动 `Expander` 实测，发现三处「持卡集合 held」推导缺口。它们不影响已通过的单元测试，但在真实全书数据上必然导致：大量场景卡无法做成（`_makeable` 的 req 判否）、章梗概卡 133-145 永不入手、`check_timeline` 对合法 timeline 大面积误报。

## B1 — `tools/build_dag.py`：crds 增加 `gets`

crd 脚本自身会发卡。实测三处唯一来源：
- `lua_scripts/snr_crd_10.lua:41` → `gameSave.myCard[126].hold = 1`
- `lua_scripts/snr_crd_51.lua:34` → `gameSave.myCard[115].hold = 1`
- `lua_scripts/snr_crd_56.lua:48` → `gameSave.myCard[97].hold = 1`

卡 97/115/126 在全库**没有任何其他获得途径**（既不在 `sceneId2aCard`，也不在任何 `scene_meta.gets`），而它们是卡 36/44/51 等的 `req`——不补这条，第 2 章半数卡片做不成。

改法：`parse_crds` 产出的每条增加
```python
"gets": sorted({int(x) for x in re.findall(r'myCard\[(\d+)\]\.hold = 1', t)}),
```
（该卡自身的授予写作 `gameSave.myCard[fragmentDoCardId].hold = 1`，是变量、不会被这条字面量正则命中——这正是我们要的：`gets` 只收「附带发出的别的卡」。）

`crds` 的键顺序保持 `answers/gets/req/runs/stub`（`json.dumps(..., sort_keys=True)` 自动排）。
改完必须重跑 `uv run python tools/build_dag.py` 重新生成 `data/dag.json` 并**入库**，且双跑 diff 为空。

## B2 — `tools/gen_timeline.py`：`fragment_sweep` 生效两类发卡

现状 `fragment_sweep` 只 `self.held.add(cid)`。缺两项：

1. **crd 自身发卡**：emit card unit 后 `self.held.update(crd.get("gets", []))`（用 B1 的新字段）。
2. **`_f` 章 fscene 的发卡**：`runs` 里的 `_f` 脚本被整文件 emit 成 fscene unit，就等于「这一章现实层被经历了」，其 `scene_meta` 的 `gets` 必须生效——**章梗概卡 133-145 全部由各 `_f` 章的 `*_complete` 场景授予**（如 `scene_s1f_complete` 发卡 133）。不补这条，`crd_177`（日记章解锁，req 含 133-138+145）与 `crd_103`/`crd_104` 的 req 永远不满足。
   改法：emit fscene unit 后，对该文件的全部函数逐个 `self._apply_meta(fn)`（函数集合的取法与该 unit 的 `funcs` 一致，即 `sorted({fn for (f, fn) in self.by_filefunc if f == runf})`）。

**顺序要求**：两类发卡都必须在**本次 sweep 的循环内、紧随该卡 emit 之后**生效，好让同一次 sweep 里后面的卡立刻能用上（route 序靠后的卡常依赖前面刚发的卡）。

## B3 — `tools/check_timeline.py`：独立重放的 held 口径对齐

`check()` 现在只从 scene unit 的 `play` 事件累积 `held`。展开器的口径更宽：
- scene unit：`play` **与 `subcall`** 的 `scene_meta.gets` 都生效（真实数据里 `scene_s5s_dispatch_v45` 就是 subcall 且授予卡 105/106/109）；
- card unit：`scene2card[state]` 那张卡本身，**外加** `crds[cid]["gets"]`；
- fscene unit：该文件全部函数的 `scene_meta.gets`（文件→函数集合可由 `ledger_rows` 的 `file`/`func` 反查得到）。

B 段（crd 合法）与 C 段（门控表）**必须用同一套推导**——现在 C 段自己重扫一遍 `timeline[:pos]`，口径与 B 段还不一样。请抽一个共用的辅助函数（例如 `_grant(held, unit, dag, scene2card, file_funcs)`，对单个 unit 施加发卡），B 段顺序累积、C 段用它重扫前缀，两边共用同一实现，消除口径漂移。

**不要改动**：`check()` 的对外签名 `check(timeline, ledger_rows, dag, scene2card, gates) -> list[str]`、四个中文错误关键词（重复/缺失/门控/req）、A 段覆盖断言、`config/gates.yaml`。

## 测试要求（TDD，先红后绿）

在 `tests/test_gen_timeline.py` 与 `tests/test_check_timeline.py` 各补最小用例，且**每条都要能判别**（去掉对应产码行必须变红）：

1. `parse_crds` 对一段内联 crd lua 文本产出正确的 `gets`（含「自身授予用变量、不进 gets」这一点）。
2. `fragment_sweep` 后 `held` 含该 crd 的 `gets`（构造一张 crd，其 `gets` 里的卡是**另一张卡的 req**，断言那另一张卡在同一次 sweep 内被做成——这样才测到「循环内即时生效」）。
3. `fragment_sweep` 的 fscene 令 `_f` 文件的 `scene_meta.gets` 生效（断言 held 含该章梗概卡）。
4. `check_timeline.check` 对一条「卡 A 的 req 由 crd/ fscene/ subcall 发卡满足」的合法 timeline 返回**空错误列表**（改前必红：现在会误报 req 未满足）。

## 验收

```bash
uv run python tools/build_dag.py && uv run python tools/build_dag.py && git diff --stat data/dag.json   # 第二次跑后应为空
uv run pytest -q          # 此前基线 62 passed，补测后应更多且无回归
```

## 提交

一个逻辑变更一个 commit（`type: 中文摘要`），建议两个：
- `fix: crd 自身发卡进 dag，展开器 sweep 生效 crd/fscene 发卡`（含 build_dag + gen_timeline + data/dag.json + 两处测试）
- `fix: check_timeline 的 held 推导与展开器口径对齐`（含 check_timeline + 测试）

不要 push、不要建分支。
