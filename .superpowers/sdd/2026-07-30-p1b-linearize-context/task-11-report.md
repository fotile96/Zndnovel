# Task 11: 端到端 dry-run（无 API、无翻译）— 完成报告

## 结论先行

**状态：BLOCKED。** 测试代码已按 brief Step 1 原样写出（`tests/test_e2e_dryrun.py`），首次运行**红**，根因属于 brief 判断分类里的 **(b)：假草稿确实会触发硬规则**，且触发的硬规则（R2b）经核实是 `check_batch.py` 的**预期正确行为**，不是上游缺陷。按任务指示，我没有为了让它变绿而放宽断言、改造假草稿或改动 `tools/` 下任何脚本，也没有提交这个已知会红的测试进默认套件——测试文件保留在工作区（未 commit）供裁决，仓库未产生任何 commit。

---

## 测试写了什么

`tests/test_e2e_dryrun.py`，逐字照抄 brief Step 1 的测试体（`test_batch1_context_and_fake_roundtrip`），仅在文件顶部加了一句 docstring 说明它会写真实 `work/ctx/batch_1/` 与 `work/out/batch_1.draft.jsonl`（不是 `tmp_path` 隔离；`tmp_path` 形参未被使用，这是 brief 代码本身如此，未改动）：

```python
"""端到端 dry-run：build_context → 假草稿 → check_batch，在真实 data/ 上跑通整条回路。

注意：本测试会写真实的 work/ctx/batch_1/ 与 work/out/batch_1.draft.jsonl（不是
tmp_path 隔离的临时文件）——这是 build_context.py / check_batch.py 的既有行为
（两者都固定写 REPO/work/ 下的路径，不接受输出目录参数）。work/ 已在 .gitignore，
产物不入库；tmp_path fixture 参数保留只是未被使用。
"""
import json, subprocess, sys
from tools.pipelib import REPO, WORK, read_jsonl

def test_batch1_context_and_fake_roundtrip(tmp_path):
    r = subprocess.run([sys.executable, "tools/build_context.py",
                        "--batch", "1", "--profile", "cc", "--jp-fallback"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    src = read_jsonl(WORK / "ctx" / "batch_1" / "source.jsonl")
    draft = [{"id": row["id"], "zh": "【占位】" + row["jp"]} for row in src]
    (WORK / "out").mkdir(parents=True, exist_ok=True)
    (WORK / "out" / "batch_1.draft.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in draft) + "\n",
        encoding="utf-8")
    r2 = subprocess.run([sys.executable, "tools/check_batch.py", "--batch", "1"],
                        cwd=REPO, capture_output=True, text=True)
    # 占位译文可能触发软警但硬规则应可通过（【】/符号照抄自 jp）
    assert r2.returncode == 0, r2.stdout + r2.stderr
```

语义确认：两次真实子进程调用（`tools/build_context.py`、`tools/check_batch.py`，均用 `sys.executable` + `cwd=REPO`），读写的是真实 `data/`（`data/ledger.jsonl`、`data/batches.jsonl`；`data/forward.jsonl` 不存在，靠 `--jp-fallback` 放行）与真实 `work/`，没有任何 mock。

## 首次运行的完整输出（红）

```
$ uv run pytest tests/test_e2e_dryrun.py -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /home/user/Zndnovel/.venv/bin/python
collecting ... collected 1 item

tests/test_e2e_dryrun.py::test_batch1_context_and_fake_roundtrip FAILED  [100%]

=================================== FAILURES ===================================
____________________ test_batch1_context_and_fake_roundtrip ____________________

    def test_batch1_context_and_fake_roundtrip(tmp_path):
        r = subprocess.run([sys.executable, "tools/build_context.py",
                            "--batch", "1", "--profile", "cc", "--jp-fallback"],
                           cwd=REPO, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        src = read_jsonl(WORK / "ctx" / "batch_1" / "source.jsonl")
        draft = [{"id": row["id"], "zh": "【占位】" + row["jp"]} for row in src]
        (WORK / "out").mkdir(parents=True, exist_ok=True)
        (WORK / "out" / "batch_1.draft.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in draft) + "\n",
            encoding="utf-8")
        r2 = subprocess.run([sys.executable, "tools/check_batch.py", "--batch", "1"],
                            cwd=REPO, capture_output=True, text=True)
        # 占位译文可能触发软警但硬规则应可通过（【】/符号照抄自 jp）
>       assert r2.returncode == 0, r2.stdout + r2.stderr
E       AssertionError: batch_1: FAIL  hard=151
E
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['/home/user/Zndnovel/.venv/bin/python', 'tools/check_batch.py', '--batch', '1'], returncode=1, stdout='batch_1: FAIL  hard=151\n', stderr='').returncode

tests/test_e2e_dryrun.py:25: AssertionError
=========================== short test summary info ============================
FAILED tests/test_e2e_dryrun.py::test_batch1_context_and_fake_roundtrip - Ass...
============================== 1 failed in 0.29s ===============================
```

第一个子进程（`build_context.py`）**成功**（returncode 0，produced `work/ctx/batch_1/{context.md,source.jsonl,manifest.json}`）。失败发生在第二个子进程之后的断言：`check_batch.py` 对占位草稿判 **FAIL，hard=151**。

## `check_batch` 对占位草稿的 hard/warn 统计与根因

统计（来自 `work/out/batch_1.check.json`，339 行 source 全覆盖）：

| 类别 | 规则 | 条数 |
|---|---|---|
| hard | R2b | **151**（占 339 行的 44.5%） |
| hard | R2a / R2c / R1 | 0 |
| warn | W3（显示行宽超限） | 207 |
| warn | W2（术语未按定译） | 18 |
| warn | W1（断行数差） | 0 |

**warn 部分完全符合 brief 预期**：`zh = jp` 原文未翻译，W2（术语该出现的中文定译当然不会出现在未翻译的日文里）与 W3（行首多了「【占位】」4 字，行宽必超）两条软警是占位草稿的自然结果，均只进 warning，不挡 PASS。

**hard 部分（R2b，151 条）不符合 brief 的判断**。根因是正则锚定问题，与占位策略和 `check_batch.py` 的交互：

1. `check_batch.py` 的 `SPEAKER_RE = re.compile(r'^【([^】]+)】')`，`re.match` 只捕获字符串**最前面**那一对方括号内的内容。
2. batch 1（339 行）里有 152 行的 `jp` 本身以 `【说话人】` 开头（对白行），其中 151 行的说话人在 `glossary/speakers.json` 里有非 None 映射（另 1 行是 `＊＊＊`，未登记，`want=None` 不触发）。
3. 假草稿 `zh = "【占位】" + jp`：对这 151 行，`jp` 已经是 `【彩野】「…」` 这样的形式，拼接后变成 `【占位】【彩野】「…」`——**多了一层方括号**，不是"照抄"结构，而是在原结构外面新套了一层。
4. `check_batch.py` 里 R2b 的判定：`speakers` 非空时，对每行取 `sm = SPEAKER_RE.match(jp)`（拿到期望说话人，如「彩野」）与 `want = speakers.get(sm.group(1))`（查表映射后的目标中文说话人名，可能与原名相同也可能不同，如「お母さん」→「妈妈」），再取 `dm = SPEAKER_RE.match(zh)`；若 `dm.group(1) != want` 则判 R2b 硬错。由于 `zh` 最前面那对方括号被「占位」占据，`dm.group(1)` 恒为 `"占位"`，不可能等于任何 `want`，于是这 151 行全部 R2b 硬失败。

三个具体样例（`id`、原文 `jp`、占位译文 `zh`）：

```
id 6067
  jp: 【私】「どうぞ。……遅かったわね。道、混んでた？」
  zh(placeholder): 【占位】【私】「どうぞ。……遅かったわね。道、混んでた？」
  → speakers["私"] = "我"；R2b 要求 zh 以【我】开头，实际以【占位】开头 → 硬错

id 6094
  jp: 【彩野】「わかった」
  zh(placeholder): 【占位】【彩野】「わかった」
  → speakers["彩野"] = "彩野"（同名映射也不例外）；同上 → 硬错

id 6105
  jp: 【直哉】「（忘れないよ）」
  zh(placeholder): 【占位】【直哉】「（忘れないよ）」
  → speakers["直哉"] = "直哉" → 硬错
```

151 条 R2b 硬错 id 全部去重、无重复计数（151 entries = 151 distinct ids，已核实）；id 范围 6067–6401，均在 batch 1 的 6060–64xx 区间内。

**这不是 `check_batch.py` 的缺陷**——对真实译者草稿而言，R2b 的设计恰恰就是要求译文首个方括号内是（映射后的）正确说话人名，`tests/test_check_batch.py::test_speaker_map_mismatch_is_hard` 已经用几乎相同的手法（先塞一个错误名字进方括号）专门测试并锁定了这条行为，`check_batch.py` 在这里的表现与既有单测完全一致、符合设计意图。**问题在于 brief Step 1 选择的占位策略**（无条件在整行最前面拼接「【占位】」）没有考虑到「jp 行首若本身带说话人方括号，会被占位再套一层」这个情况，brief 注释里「【】/符号照抄自 jp」的判断因此不成立——"照抄"没错，但"照抄"的结果外面多套了一层方括号，改变了 `SPEAKER_RE` 锚定读到的内容。这精确对应任务说明里的分类 **(b)**。

## 全套回归结果

**不含新文件（确认基线未受影响）：**
```
$ uv run pytest -q --ignore=tests/test_e2e_dryrun.py
........................................................................ [ 76%]
......................                                                   [100%]
94 passed in 2.08s
```

**含新文件（如实记录，未提交）：**
```
$ uv run pytest -q
1 failed, 94 passed in 2.40s
```

基线 94 个既有测试完全不受影响，唯一失败是新增的 `test_e2e_dryrun.py`。

## 完成定义里可独立验证的部分

`build_context --batch 1 --profile cc` 本身运行正常，产出可读的 `work/ctx/batch_1/context.md`（1128 行）。人工抽查：

- `# 一、冻结骨架` 正常渲染 195 张卡的中文摘要；
- `## 五、本批任务` 正常列出全部 339 条 `[id] jp` 行（如 `[6067] 【私】「どうぞ。……遅かったわね。道、混んでた？」`）；
- `manifest.json` 字段齐全（`glossary_v: 6`、`skeleton`/`anchors`/`ctx_sha` 三个 sha256 均非空）。

`source.jsonl` 339 行，与 `data/batches.jsonl` 里 batch 1 的 339 个 id 一致。这部分行为符合预期，问题只出在 `check_batch` 这一环与占位草稿的交互。

## 改了哪些文件

- **新建**：`tests/test_e2e_dryrun.py`（未提交，见下）。
- **未改动**：`tools/`、`config/`、`data/`、`prompts/`、`skeleton/`、`glossary/`、`docs/`、`tests/` 下其他任何文件。
- **工作区副作用（gitignore，未 add）**：`work/ctx/batch_1/{context.md,source.jsonl,manifest.json}`、`work/out/{batch_1.draft.jsonl,batch_1.check.json}` 由测试运行产生；`work/out/batch_1.pass.json` **不存在**（`check_batch.py` 只在 hard 为空时才写这个文件，本次未写，符合其逻辑）。已用 `git status --short` 与 `git check-ignore -v` 核实：仓库唯一的未跟踪变更是 `tests/test_e2e_dryrun.py`，`work/` 下产物确实被 `.gitignore` 第 15 行挡住。

## 为什么没有提交

任务指示明确：分类 (b) 的处理方式是"停下来回报……由控制器裁决"，而不是"提交后再说"。若把这个已知会红的测试提交进 `main`（本仓库无 PR 门禁，直提交进主线），会当场破坏"完成定义"第一条（`uv run pytest -q` 全绿含 e2e），且我被明确告知不能通过放宽断言/改造假草稿/改 `tools/` 来让它变绿——这三条路径没有一条我有权自行选择。所以在裁决之前，提交这个测试没有意义，只会把一个已知冲突静默地带进默认套件。测试文件本身完整保留在工作区，内容可直接核验。

## 自评审

- **完整性**：端到端语义完整——两个真实子进程（`build_context.py`、`check_batch.py`），跑在真实 `data/`（`data/ledger.jsonl`、`data/batches.jsonl`、`data/forward.jsonl` 缺失走 `--jp-fallback`）与真实 `skeleton/`/`glossary/` 之上，没有 mock、没有构造小样本数据。
- **质量**：失败信息可诊断——`assert r2.returncode == 0, r2.stdout + r2.stderr` 原样保留，实际打印出 `batch_1: FAIL hard=151`；本报告进一步下钻到规则/id/原文-占位文对照，足以让控制器直接判断。
- **纪律**：未改动 `tools/` 任何脚本；未放宽/删除任何断言；未修改假草稿生成逻辑；`work/`、`data/` 下均未 `git add`；未创建分支；未 push。
- **测试真实性**：测的是真行为——两次 `subprocess.run` 调用的是仓库里真实的 CLI 入口，读的是真实数据文件，不是任何形式的桩/替身。

自评审未发现"我本可以修但没修"的问题——唯一的"问题"是 brief 判断有误这件事本身，这正是任务要我上报而非自行处理的对象。

## 遗留顾虑 / 供控制器参考的裁决方向（未擅自实施任何一项）

三条技术上可行的解法，按对 brief 原意的保真程度排列，仅供参考：

1. **让占位草稿"说话人感知"**：只在 `jp` 不带 `【】` 前缀的行首拼接「【占位】」，若 `jp` 已带 `【名字】` 前缀，则把占位标记插在方括号**之后**（如 `【私】「【占位】どうぞ……」`），保持"只有一层方括号"的不变量。这是纯测试内改动，不碰 `tools/`，但改变了 brief"照抄"给出的具体代码，需要确认是否仍算"照抄"范围内的"修正测试代码本身的小瑕疵"，还是需要 sign-off 的"改造假草稿"。
2. **只对不带说话人前缀的行做占位验证**：仍用原拼接策略，但 draft 只覆盖 `jp` 无 `【】` 前缀的行，对有前缀的行 `zh` 直接等于 `jp`（不加占位，天然保留说话人结构）。同样是纯测试内改动，且更明显地偏离了 brief"整批统一拼接『【占位】』"的字面写法。
3. **维持 brief 字面代码不变，弱化 check_batch 侧断言范围**（例如只挡 R1，不挡 R2b）——**不建议**，因为这会削弱 e2e 测试本该验证的"硬规则确实生效"这一核心语义，且任务指示明确禁止"放宽断言"。

我个人倾向选项 1（对 brief 原意破坏最小，且与生产环境里真实译文"说话人方括号只出现一次"的不变量一致），但裁决权在控制器，我没有替代决定。

---

**首轮未产生任何 git commit。** `tests/test_e2e_dryrun.py` 以未跟踪文件形式留在工作区，等待裁决后再决定是否需要按裁决结果调整并提交。

*（后注：本报告随后被控制器以 `c58f4d1 docs: 台账记 Task 11 阻塞与占位草稿形态裁决` 提交入库——那是报告文件本身的入库，不是测试代码的落地；`tests/test_e2e_dryrun.py` 在该 commit 里仍不在其中，见下一轮记录。）*

---

## 修复轮 1：按控制器裁决改占位草稿构造

### 裁决内容（原文转录，供存档）

> 计划里那句假草稿 `zh = "【占位】" + jp` 本身是缺陷：它把占位标记塞在**说话人标签之前**，于是 `【占位】【彩野】…` 让 `SPEAKER_RE` 读出说话人 `"占位"`，R2b 必然硬失败。计划自己的注释（「【】/符号照抄自 jp」）以为这样能保住控制码，但没考虑说话人标签必须**留在行首**。
>
> **改法：占位标记改为插在行首说话人标签之后，且不使用全角方括号。**
>
> ```python
> SPEAKER = re.compile(r"^【[^】]*】")
>
> def _placeholder(jp: str) -> str:
>     """假译文：保留行首【说话人】原样，占位标记插在其后；无说话人则直接前置。
>     用〔〕而非【】，避免给旁白行造出假的说话人标签（check_batch 的 R2b 对
>     「jp 无【】而 zh 误加」这一分支恰好拦不到，不该在测试夹具里制造这种脏数据）。"""
>     m = SPEAKER.match(jp)
>     return f"{m.group(0)}〔占位〕{jp[m.end():]}" if m else f"〔占位〕{jp}"
> ```
>
> 理由：
> - R2b 要求 zh 行首的【名字】与 jp 行首的【名字】经 `speakers.json` 映射后一致 → 说话人标签必须原样留在行首；
> - R2a（ruby 良构）与 R2c（`≪≫≦≧○■` 不丢）靠「jp 正文原样照抄在标记之后」保住；
> - `〔〕` 不在 `MARKS` 常量里、也不是 `SPEAKER_RE` 认的括号，因此既不会被误判成说话人标签、也不会触发符号丢失；
> - 旁白行（jp 无【】）若沿用 `【占位】` 前缀，会造出一个 R2b 恰好拦不到的假说话人标签——那正是本计划台账里已记录的 `check_batch` 死分支缺陷，测试夹具不该主动制造这种脏数据。

已把 `_placeholder()` 原样落进 `tests/test_e2e_dryrun.py`（`draft = [...]` 那行改用 `_placeholder(row["jp"])`），并在其 docstring 里追加了一段偏离说明（引用 brief 原写法 `zh = "【占位】" + jp` 与本报告）。两个 `subprocess.run` 调用、`assert r2.returncode == 0, r2.stdout + r2.stderr` 均未改动。

### 改后运行（第二次真实 pytest，仍红）

```
$ uv run pytest tests/test_e2e_dryrun.py -v
============================= test session starts ==============================
collecting ... collected 1 item

tests/test_e2e_dryrun.py::test_batch1_context_and_fake_roundtrip FAILED  [100%]

=================================== FAILURES ===================================
____________________ test_batch1_context_and_fake_roundtrip ____________________

    def test_batch1_context_and_fake_roundtrip(tmp_path):
        r = subprocess.run([sys.executable, "tools/build_context.py",
                            "--batch", "1", "--profile", "cc", "--jp-fallback"],
                           cwd=REPO, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        src = read_jsonl(WORK / "ctx" / "batch_1" / "source.jsonl")
        draft = [{"id": row["id"], "zh": _placeholder(row["jp"])} for row in src]
        (WORK / "out").mkdir(parents=True, exist_ok=True)
        (WORK / "out" / "batch_1.draft.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in draft) + "\n",
            encoding="utf-8")
        r2 = subprocess.run([sys.executable, "tools/check_batch.py", "--batch", "1"],
                            cwd=REPO, capture_output=True, text=True)
        # 占位译文可能触发软警但硬规则应可通过（【】/符号照抄自 jp）
>       assert r2.returncode == 0, r2.stdout + r2.stderr
E       AssertionError: batch_1: FAIL  hard=19
E
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['/home/user/Zndnovel/.venv/bin/python', 'tools/check_batch.py', '--batch', '1'], returncode=1, stdout='batch_1: FAIL  hard=19\n', stderr='').returncode

tests/test_e2e_dryrun.py:40: AssertionError
=========================== short test summary info ============================
FAILED tests/test_e2e_dryrun.py::test_batch1_context_and_fake_roundtrip - Ass...
============================== 1 failed in 0.28s ===============================
```

### hard/warn 对比（改前 → 改后）

| 类别 | 规则 | 改前（`"【占位】"+jp` 前置） | 改后（`_placeholder`，标签后插） |
|---|---|---|---|
| hard | R2b | 151 | **19** |
| hard | R2a/R2c/R1 | 0 | 0 |
| warn | W3 | 207 | 207（不变） |
| warn | W2 | 18 | 18（不变） |
| warn | W1 | 0 | 0 |

改后 132 行（占原 151 的多数）转为 PASS：即 `直哉`（67 行）与 `彩野`（65 行）——这两个说话人在 `glossary/speakers.json` 里是**恒等映射**（`"直哉":"直哉"`、`"彩野":"彩野"`），`_placeholder` 保留 jp 原方括号内容后天然等于 `want`，R2b 满足。

### 根因判断 2（仍是 (b)，但换了一层）

剩余 19 条 hard 全部是 R2b，可归为两类，且这两类穷尽了差集：

```
speakers.json 中的非恒等映射（jp 说话人字面 ≠ 目标中文说话人字面）：
  "教師": "教师"   → batch 1 命中 18 行（id 6174…6218）
  "私":   "我"     → batch 1 命中 1 行（id 6067）
  合计 19，与 hard=19 精确对应（已核实 19 条 id 互不重复）
```

三个具体样例：

```
id 6067   jp: 【私】「どうぞ。……遅かったわね。道、混んでた？」
          zh(placeholder): 【私】〔占位〕「どうぞ。……遅かったわね。道、混んでた？」
          → speakers["私"]="我"；R2b 要求 zh 行首为【我】，实际仍是【私】（占位没有翻译名字本身）→ 硬错

id 6174   jp: 【教師】「あー！ はいはいはいはい！ 彩野さんと一緒の方ね。いらっしゃい！ 夏場の盛りにご苦労様ですわ！」
          zh(placeholder): 【教師】〔占位〕「あー！ ……」
          → speakers["教師"]="教师"；【教師】≠【教师】（日文汉字"師" vs 中文"师"）→ 硬错

id 6218   jp: 【教師】「彩野さん。大変だと思うが、がんばれよ」
          zh(placeholder): 【教師】〔占位〕「彩野さん。大変だと思うが、がんばれよ」
          → 同上，硬错
```

**这不是 `_placeholder` 实现错了控制器给的规则**——代码与控制器给出的实现逐字一致，运行结果也和我改测试文件前用同一份逻辑手工在真实 `source.jsonl`/`check_batch.py` 上跑的结果完全一致（hard=19，19 个 id，全部 R2b，已核对两次运行的 `work/out/batch_1.check.json` 一致）。**根因是控制器裁决本身覆盖的场景有边界**：裁决明确解决的是"结构性"问题（占位标记塞进方括号内部，制造双层【】），对此"保留 jp 原方括号内容"是充分的修复；但 R2b 的语义比"结构良构"更严格——它要求方括号里的**内容**等于 `speakers.json` 映射后的目标中文名，而不仅是"存在一层合法方括号"。当 jp 的说话人标签本身是需要翻译的普通名词/代词（「教師」→「教师」、「私」→「我」，二者字面不同，即便语义/字形接近）而非专有名词（「彩野」「直哉」等在 zh 中保留原字），"照抄 jp 方括号内容"这条策略在结构上正确、在内容上必然不等于 `want`。**任何不真正翻译说话人标签内容的占位策略，理论上都无法让这类行通过 R2b**——这与"标记插在标签前还是标签后"无关，是"占位 ≠ 翻译"这件事本身与 R2b 语义的根本冲突，只是第一版错误（151 条）掩盖了这个更深的 19 条差集。

### 全套回归（第二轮）

```
$ uv run pytest -q --ignore=tests/test_e2e_dryrun.py
94 passed in 1.98s

$ uv run pytest -q
1 failed, 94 passed in 2.28s
```

基线 94 个既有测试仍完全不受影响；`work/out/batch_1.pass.json` 依旧未生成（`check_batch.py` 只在 hard 为空时才写，本轮 hard=19，未写，行为一致）。`git status --short` 核实：仓库里唯一变更仍是未跟踪的 `tests/test_e2e_dryrun.py`（已按控制器代码更新），`work/` 下产物未 `git add`。

### 遵照指示：不再自行尝试第三种写法

控制器原话："若仍红：再次停下来回报，附完整失败原文与新的根因判断。不要继续试第三种写法。" 本轮结果仍红，已按要求止步——**没有**为了让剩余 19 条通过而进一步改写 `_placeholder`（例如给「教師」「私」这类可翻译的说话人标签也做字面替换）。这类改法会把"占位夹具"实质变成"局部真翻译"（至少要维护一张说话人名字翻译表），已经不是"照抄/微调 brief"范畴，需要新一轮裁决。

### 仍未提交

同第一轮理由：这次的失败换了一层（从"结构"到"内容"），但结论没变——不能把已知会红的测试落进默认套件。`tests/test_e2e_dryrun.py` 保持未跟踪状态，已应用控制器给出的 `_placeholder` 实现与偏离说明注释，等待下一轮裁决。

### 供参考（未擅自实施）

如果控制器需要在下一轮直接决策，差集是干净的、封闭的：`speakers.json` 里 39 个键中，`"私"→"我"` 与 `"教師"→"教师"` 这两条（以及同类的 `"看護師"→"护士"`、`"母親"→"母亲"`、`"お母さん"→"妈妈"`、`"店員"→"店员"` 等，batch 1 未命中但后续批次可能命中）是非恒等映射；批次 1 只暴露了其中 2 条、19 行。可能的方向：①占位夹具里维护一张"说话人名替换表"（本质是 `speakers.json` 本身，等价于在 `_placeholder` 里也查一次 `speakers.json` 把方括号内容替换成 `want`，而不仅是原样保留）；②接受"占位草稿天然无法让说话人标签类硬规则全绿"，改用其他方式验证 R2b 生效面（如缩小断言范围到 R1/R2a/R2c，R2b 另用 `tests/test_check_batch.py` 里的单元测试覆盖，e2e 只做"管线打通"）；③换一个不含说话人标签、或说话人标签恰好全部恒等映射的批次/子集做 e2e 载体。三者都改变了测试的验证面或所需数据前提，均未实施，留待裁决。

---

## 修复轮 2：按控制器裁决给占位说话人补上 speakers.json 映射（第 3 轮，转绿）

### 裁决内容（原文转录，供存档）

> 剩下这 19 条不是「占位标记该放哪」的问题，是**假草稿还差一步真正的翻译动作**：R2b 的契约就是「zh 行首的说话人必须是 `speakers.json` 映射后的译名」。`私→我`、`教師→教师` 这类非恒等映射，任何不动说话人内容的占位方案都过不去——这不是缺陷，是硬规则本来就要求的最小翻译量。
>
> 所以假草稿要做的**唯一一个真实转换**，就是把行首说话人按 `speakers.json` 映射一次。正文仍原样照抄（保住 R2a/R2c）。
>
> ```python
> import json
> import re
>
> SPEAKERS = json.loads((REPO / "glossary" / "speakers.json").read_text(encoding="utf-8"))
> SPEAKER = re.compile(r"^【([^】]*)】")
>
>
> def _placeholder(jp: str) -> str:
>     """假译文：行首【说话人】按 speakers.json 映射成译名（R2b 的硬性要求，
>     是这份假草稿里唯一真正的"翻译"动作），占位标记插在其后，正文原样照抄
>     （保住 R2a ruby 与 R2c 符号）。计划原文写的是 `"【占位】" + jp`，实测在真实
>     数据上硬失败 R2b 151 条（双层【】）→ 改为标记后置又剩 19 条（非恒等映射的
>     说话人），故补上这一次映射。"""
>     m = SPEAKER.match(jp)
>     if not m:
>         return f"〔占位〕{jp}"
>     name = SPEAKERS.get(m.group(1), m.group(1))
>     return f"【{name}】〔占位〕{jp[m.end():]}"
> ```
>
> （`SPEAKERS.get(x, x)` 的兜底是必要的：表里没有的说话人，`check_batch` 的 R2b 恰好不比对——原样保留即可。）

已把上面这份实现原样落进 `tests/test_e2e_dryrun.py`：`SPEAKER` 正则改为带捕获组（`^【([^】]*)】`），新增模块级 `SPEAKERS = json.loads(...)`，`_placeholder` 换成"取 jp 说话人 → 查表映射（无命中原样兜底）→ 拼回【译名】〔占位〕+ 正文"。两个 `subprocess.run` 调用与 `assert r2.returncode == 0, r2.stdout + r2.stderr` 一字未动。docstring 里保留了三轮裁决的简history（151 条双层【】→19 条非恒等映射→本轮补映射）供后来者追溯。

### 改后运行（第三次真实 pytest，转绿）

```
$ uv run pytest tests/test_e2e_dryrun.py -v
============================= test session starts ==============================
collecting ... collected 1 item

tests/test_e2e_dryrun.py::test_batch1_context_and_fake_roundtrip PASSED  [100%]

============================== 1 passed in 0.30s ===============================
```

### `check_batch` 最终判定

```
batch_1: PASS  warn=225
```

`work/out/batch_1.pass.json` 首次生成（前两轮因 hard>0 均未生成）：
```json
{"sha256":"792dbe211d04bdd88e58129aa22e1c812495374dcebe6c9c2fe4894ca6b397b7"}
```

`work/out/batch_1.check.json`：`hard: []`（0 条），`warn`: 225 条（`W3` 207 + `W2` 18，`W1` 0）。

### 三轮对照表

| 轮次 | 占位策略 | hard 总数 | hard 规则分布 | warn 总数 | warn 规则分布 |
|---|---|---|---|---|---|
| 1（brief 字面：`"【占位】"+jp` 前置） | 占位塞进说话人标签**之前**，双层【】 | **151** | R2b×151 | 225 | W3×207, W2×18 |
| 2（裁决 1：标记后置，不映射说话人） | 说话人标签留行首、原样保留，标记插其后 | **19** | R2b×19（`私`1 + `教師`18，均非恒等映射） | 225 | W3×207, W2×18 |
| 3（裁决 2：标记后置 + 说话人按 speakers.json 映射） | 说话人先映射成译名，标记再插其后 | **0** | — | 225 | W3×207, W2×18 |

**warn 三轮完全一致**（225 = 207 W3 + 18 W2，逐条 id 也一致，未重新逐条比对但总数与规则分布三轮不变，符合预期——W2/W3 的判定只看正文宽度与术语出现与否，跟行首说话人标签的处理方式无关，三次改动都没碰正文）。hard 从 151 单调降到 19 再到 0，与三轮裁决分别解决"双层【】结构"和"说话人内容映射"两层问题完全对应，没有反复或意外新增的规则种类（自始至终只有 R2b 出现在 hard 里，R1/R2a/R2c 三轮均为 0，说明 id 集合、ruby、符号三项从第一轮起就没问题，纯粹是 R2b 的两层原因)。

### 全套回归（第三轮，含新测试）

```
$ uv run pytest -q
95 passed in 2.30s
```

基线 94 + 本条新增 1 = 95，与控制器预期一致。未回归任何既有测试。

### 提交

```
$ git add tests/test_e2e_dryrun.py   # 只加这一个文件，未 add work/ 或 data/
$ git commit -m "test: 端到端 dry-run（context→假草稿→check_batch）"
[claude/cloud-setup-session-a32ocv 2776d67] test: 端到端 dry-run（context→假草稿→check_batch）
 1 file changed, 41 insertions(+)
 create mode 100644 tests/test_e2e_dryrun.py
```

提交后 `git status --short` 只剩 `task-11-report.md`（本文件，尚待追加/入库）处于已修改未提交状态；无其它未预期变更。

### 最终测试文件全文（供存档核对）

```python
"""端到端 dry-run：build_context → 假草稿 → check_batch，在真实 data/ 上跑通整条回路。

注意：本测试会写真实的 work/ctx/batch_1/ 与 work/out/batch_1.draft.jsonl（不是
tmp_path 隔离的临时文件）——这是 build_context.py / check_batch.py 的既有行为
（两者都固定写 REPO/work/ 下的路径，不接受输出目录参数）。work/ 已在 .gitignore，
产物不入库；tmp_path fixture 参数保留只是未被使用。
"""
import json, re, subprocess, sys
from tools.pipelib import REPO, WORK, read_jsonl

SPEAKERS = json.loads((REPO / "glossary" / "speakers.json").read_text(encoding="utf-8"))
SPEAKER = re.compile(r"^【([^】]*)】")

def _placeholder(jp: str) -> str:
    """假译文：行首【说话人】按 speakers.json 映射成译名（R2b 的硬性要求，
    是这份假草稿里唯一真正的"翻译"动作），占位标记插在其后，正文原样照抄
    （保住 R2a ruby 与 R2c 符号）。计划原文写的是 `"【占位】" + jp`，实测在真实
    数据上硬失败 R2b 151 条（双层【】）→ 改为标记后置又剩 19 条（非恒等映射的
    说话人：私→我、教師→教师），故补上这一次映射——三轮裁决详见 task-11-report.md。
    """
    m = SPEAKER.match(jp)
    if not m:
        return f"〔占位〕{jp}"
    name = SPEAKERS.get(m.group(1), m.group(1))
    return f"【{name}】〔占位〕{jp[m.end():]}"

def test_batch1_context_and_fake_roundtrip(tmp_path):
    r = subprocess.run([sys.executable, "tools/build_context.py",
                        "--batch", "1", "--profile", "cc", "--jp-fallback"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    src = read_jsonl(WORK / "ctx" / "batch_1" / "source.jsonl")
    draft = [{"id": row["id"], "zh": _placeholder(row["jp"])} for row in src]
    (WORK / "out").mkdir(parents=True, exist_ok=True)
    (WORK / "out" / "batch_1.draft.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in draft) + "\n",
        encoding="utf-8")
    r2 = subprocess.run([sys.executable, "tools/check_batch.py", "--batch", "1"],
                        cwd=REPO, capture_output=True, text=True)
    # 占位译文可能触发软警但硬规则应可通过（【】/符号照抄自 jp）
    assert r2.returncode == 0, r2.stdout + r2.stderr
```

### 自评审（第三轮）

- **完整性**：端到端语义自始至终未被削弱——两个真实子进程调用、真实 `data/`、`assert r2.returncode == 0` 三轮均未改动；唯一变化的是假草稿如何构造 `zh`，且每一步变化都直接对应上一轮暴露的具体硬规则原因，不是无根据的试错。
- **质量**：三轮均保留了可诊断的失败信息（`r2.stdout + r2.stderr`），本报告additionally 提供了规则/id/jp/zh 对照，控制器/后来者可独立核实。
- **纪律**：三轮里我从未修改 `tools/check_batch.py`、`tools/build_context.py` 或任何 `tools/`/`config/`/`data/`/`prompts/`/`skeleton/`/`glossary/`/`docs/`/其他 `tests/` 文件；未放宽任何断言；只在明确的控制器裁决下才改动假草稿构造逻辑，且每次改动都是裁决给出的原样实现；未 add `work/` 或 `data/` 下任何产物；未建分支、未 push。
- **测试真实性**：最终落地的测试仍然是两次真实 `subprocess.run`（真实 CLI 入口）+ 真实 `data/`/`glossary/`；`_placeholder` 内部读取的 `glossary/speakers.json` 是仓库里真实的术语表，不是测试自造的假数据。

### 遗留顾虑

无。三轮裁决后 `hard=0`，`warn=225`（均为占位译文预期内的软警，构成合理——正文完全未翻译，术语/行宽类软警必然全触发，这正是"dry-run 不做真翻译，只验证管线"的题中之义）。全套回归 95 passed，无回归。`work/` 与 `data/` 均未被污染入库。

---

**本轮（第三轮）产生 1 个 commit**：`2776d67 test: 端到端 dry-run（context→假草稿→check_batch）`（只含 `tests/test_e2e_dryrun.py`，41 行新增）。`task-11-report.md`（本文件）仍待按既有模式由后续 `docs: 台账记` commit 入库。
