"""P4 润色 pass：保税仓唯一清关口——把 `pilot/polish/<label>/` 里胜出的译文
（人工裁决 `decisions.jsonl` 的 adopt/edit，或 `triage.json` 判定的
`autoclear and not sampled`）落成 `patches.jsonl` 里的正式 patch，写进生产
车道（如 `pilot/lanes/opus/data/`）。**全计划里唯一真正写生产数据的工具**。

## 本模块存在的直接理由（2026-08-02 事故）

见 `tools/add_patch.py` 模块 docstring：控制器发的 4 条译文回改补丁命令零
报错、退出码 0，但 `--data-dir` 缺省落到了主仓 `data/`（那个文件当时甚至
不存在，是被那条命令连同目录一起凭空创建的），生产车道用的是
`pilot/lanes/opus/data/`——四条回改一条都没生效。**「静默写错比报错更坏」**
是本模块的第一原则，具体落地为下面四条：

1. **车道模式拒绝闸原样复用**：本模块自己不做任何"缺省 data 目录"的决定，
   CLI 层 `main()` 一律先调 `add_patch.resolve_data_dir(args.data_dir,
   repo=args.repo)`——车道模式下没显式给 `--data-dir` 也没设 `ZND_DATA` 就
   `SystemExit(2)`，在任何文件被创建之前。`commit()` 本身（库函数）像
   `add_patch.add()` 一样接受一个**已经解析好**的 `data_dir`，不重复做这层
   判断——闸只设在 CLI 这一层是 `add_patch.py` 自己的既定设计（"程序化调用方
   本来就一直显式传 `data=`，不受影响"），本模块延续同一约定，不另起一套。
2. **写前逐 id 过 `existing_patches` 播报**：无论 dry-run 还是 `--apply`，
   每一条即将落地的 patch 在写之前都会先查一遍该 id 是否已有 patch——锁定
   面本就排除了"冻结时点已有 patch"的 id（这些 id 根本不会出现在候选/
   触发路径里），这里要防的是**润色期间新落的**patch（比如另一个会话正好
   在裁决同一行，或人工直接用 `add_patch.py` 手工回改过）。`--apply` 时
   这层播报直接由 `add_patch.add()` 内部完成（它自己就会查
   `existing_patches` 并在有前科时 print 到 stderr）；dry-run 模式下
   `add()` 根本不会被调用（不能有任何副作用），所以本模块另外用
   `add_patch.existing_patches()`（只读）自己打印同款预告，保证**两种
   模式下这条播报都不会缺席**。
3. **`dry_run=True` 是默认**：只打印将写入的 patch 与完整倒查链
   （id → candidate 的 channel/ts → prompt_hash），不碰任何文件；只有
   `--apply` 才真的写 `patches.jsonl`/`decisions.jsonl`/`committed.json`。
4. **幂等键 `(id, decision_ts)`**：`committed.json` 记录已经真正落地过的
   `(id, decision_ts)` 对，重复 `--apply` 是 no-op。见下方"幂等键粒度"专节
   ——同一 id 可能先被自动清关、后来又被人裁改判，那是**两条不同的
   decision**（不同的 `decision_ts`），必须都能落地，不能因为"这个 id 已经
   处理过"就整体跳过。

## `prov` 字段的接口选择：给 `add_patch.add()` 加一个可选参数（方案①）

brief 要求 patch 行带 `prov: {channel, candidate_ts, seg}` 回指来源，但
`add_patch.add()` 原本的行结构固定死了五个键。两条路里选了给 `add()` 加
`prov=None` 可选参数（见 `tools/add_patch.py` 改动），理由：
- `add()` 已经把"查重播报 + 追加写入"这两件事封装得很干净，本模块如果
  自己另起一套 `pipelib.append_jsonl` 写 patch 行，就必须**重新实现**一遍
  `existing_patches` 查重播报逻辑（否则会重蹈"两套写入路径，一套有查重
  一套没有"的分裂局面）——那正是补充信息里明确警告的风险点。
- 改动本身极小（4 行）且完全向后兼容：`prov=None`（默认）时行里完全不带
  这个键，`tests/test_add_patch.py` 原有全部测试未受影响（已重跑确认）。
- `resolve.resolve_map()` 只读 `id`/`zh` 两个键，`prov` 这个多余的键对它
  向后兼容，不会把现有下游消费者弄坏。

## `glossary_v` 取哪个时点：清关时点（现行），不是冻结时点（manifest 里那个）

`pilot/polish/<label>/manifest.json` 的顶层 `glossary_v` 是 `polish_setup.
setup()` **冻结那一刻**的仓库 glossary 版本快照（`build_context.
glossary_version(repo)` 在 setup 时调用一次，此后不再变）。但润色是个跨越
数天的多阶段流程（冻结→通道出稿→裁决→清关），glossary 是 append-only 的，
版本号在这段时间里完全可能继续往上涨。

**裁定：本模块在 `commit()` 执行的那一刻重新调用 `build_context.
glossary_version(repo)`，取仓库当前现行版本，不读 manifest 里冻结的那个
快照值。** 理由（有实测证据支持，不是纯理论选择）：
- 翻查真实生产 `pilot/lanes/opus/data/patches.jsonl` 尾部：同一天之内的
  `reason=review`/`recall` patch 的 `glossary_v` 从 13 跳到 14——**现有的
  唯一入库口 `add_patch.py` 本来就是这么用的**：调用方每次都传"当前调用
  这一刻"的现行版本，而不是某个更早的冻结快照。本模块作为同一条生产链路
  上另一个入库口，理应延续同一约定，否则同一批 `patches.jsonl` 里会出现
  两种互相矛盾的 `glossary_v` 语义（有的行记"生成时冻结的版本"，有的行记
  "写入那一刻的版本"），下游没有任何办法区分。
- 语义上更准确：`glossary_v` 描述的是"这次修订是在哪个术语/风格版本下
  拍板的"，而清关（写入生产车道）这个动作本身才是"拍板"发生的时刻——
  候选出稿时用的是冻结快照没错（那是翻译 prompt 的构建依据，记在
  candidate 行自己的 `prompt_hash` 里，见倒查链），但候选是否被采纳（`
  adopt`/`edit`/`auto` 判定本身）是在清关这一刻做出的决定，理应用清关
  时点的术语基线来标注。
- `tests/test_polish_commit.py::test_glossary_v_uses_current_repo_not_frozen`
  构造了一个明确的对抗场景验证这一点：SEG 冻结时仓库只有
  `glossary.v1.yaml`，冻结完成后（不重新 `setup()`）又新增
  `glossary.v2.yaml`——此时 manifest 里的 `glossary_v` 仍是 1，而
  `commit()` 产出的 patch 必须是 2。

## 幂等键的粒度：`(id, decision_ts)`，不是单纯的 `id`

`committed.json` 记录 `{"committed": [{"id":.., "decision_ts":..}, ...]}`。
**不能只用 `id` 做幂等键**——brief 明确点出的场景："同一 id 可能先被 auto
清关、后来又被人裁改判，那是两条不同的 decision，应当都能落地"。具体展开：

- 一个 id 若先被 `triage()` 判定 `autoclear and not sampled`，`commit()`
  会**铸造一条新的 `verdict="auto"` 决策**（`decisions.jsonl` 追加，
  `ts` 取本次 `commit()` 调用的时刻），随即落一条 patch，`committed.json`
  记下 `(id, 这个 auto 决策的 ts)`。
- 之后如果人工发现这条自动清关有问题，直接往 `decisions.jsonl` **追加**
  一条新的 `verdict="edit"` 记录（不同的 `ts`，晚于前一条），下次
  `commit()` 跑起来时：这是一条**新**的 `(id, decision_ts)` 组合，不在
  `committed.json` 里，会被当作一条独立的新 patch 落地——`patches.jsonl`
  里这个 id 会有两条 patch（先 auto 后 edit），`resolve.resolve_map()`
  的"后写者胜"语义自然让 edit 版本生效，不需要任何特殊处理。
- 反过来，同一条 decision（同一个 `ts`）被 `commit()` 处理第二次（重复
  `--apply`），`(id, decision_ts)` 已经在 `committed.json` 里，直接跳过——
  这才是"幂等"字面意义上要防的事。

**避免同一个自动清关"事实"被反复铸造成多条 auto 决策**：`commit()` 每次
运行都会重新读一遍 `triage.json`（`triage()` 可能被重跑过，比如 gates/
channel_state 有更新），如果每次都对同一个 autoclear 候选铸造一条全新的
`verdict="auto"` 决策（带新 `ts`），幂等键 `(id, decision_ts)` 会因为 `ts`
一直变而永远"看起来是新的"，导致 `patches.jsonl` 里堆积大量内容完全相同
的重复 patch。故铸造新决策前先查 `decisions.jsonl` 里是否已经存在一条
`(id, chosen_channel, candidate_ts)` 三元组完全一致的 `verdict="auto"`
记录——完全一致就说明"这个自动清关事实此前已经被记录过"，直接复用那条
记录的 `ts` 走幂等检查，不铸造新的；若 `candidate_ts` 变了（说明该通道
针对这个 id 重新提交过候选），则视为一个新的自动清关事实，铸造新决策——
这与"同一 id 先 auto 后人工改判都要能落地"是同一套原则的自然延伸。

## 改判与撤回：同 id 取最后一条，keep 能撤掉已经落地的 patch

`decisions.jsonl` 是 append-only 的，改判＝追加一行、读时同 id 取最后一条
（裁决 UI 的草稿也是这个语义）。本模块最初**逐行**处理每条 adopt/edit，
靠 `patches.jsonl` 的"后写者胜"让最后一条自然生效——adopt→adopt、
adopt→edit 都对，唯独**撤回**（adopt→keep_opus）不对：`keep` 不产生任何
patch，于是撤不掉前面那条已经落地的，而且全程零告警。

2026-08-20 实测 `p5seg0-s0-s1`：492 行决策里 20 个 id 被改判过，其中 7 个
的最后一条是 `keep_opus`；这 7 条里 6 条的车道文本一直停在**被人撤回的
那一版**上（第 7 条 7137 恰好前后等价）。这正是「恒绿的安全闸」那类病的
变体——不是闸报错了，是根本没有闸。

现在两步处理：

1. **同 id 只认最后一条裁决**（`last_ruling_idx`）。顺带消掉 adopt→adopt
   这种改判在 `patches.jsonl` 里留下的冗余中间态。
2. **撤回路径**（`verdict="retract"`）：最后一条是 `keep_opus`/`keep`，而
   `committed.json` 里存在该 id 一条更早的 adopt/edit/auto——说明本 SEG
   确实为它落过 patch——就追加一条内容为**冻结面 opus 原文**的 patch 把它
   撤回，`prov.retract=True` 标明这不是一次采纳。幂等键用那条 keep 决策的
   `ts`。

撤回的射程严格限制在"本 SEG 自己落的 patch"上：
- 判据是 `committed.json` 有记录，不是"车道文本和冻结面不一样"；
- 命中 `lane_drift.json`（润色期间别的会话改过这一行）一律**拒绝**并告警
  ——撤回冻结面会把别人的改动一起抹掉，那是越权；
- 车道现值已经等于冻结面就静默跳过（没有东西要撤）；
- 冻结后的人裁 patch 冲突闸里，`retract` 与 `auto` 同级——一律拒写。撤回
  是机械回退，不具备"有人正看着这一行"的资格。

## 多通道同一 id 都自动清关时，选哪个通道的译文

`triage()` 的"id 级 all-or-nothing"规则允许同一 id 下**多个**通道的候选
同时满足 autoclear 资格（这是 P4 设计的常态，不是边缘情况——多通道本来就
是要对同一批 id 各自出一份候选、互相比较）。这种情况下自动清关只能写入
**一份** zh，必须有确定性的选择规则，brief 未明确规定，本模块自行裁定：

**取 `edit`（相对 opus 的编辑距离）最小的那个通道**，同分再按通道名字典
序打散。理由：`edit` 是"客观信号"（spec §9 明确认可的跨通道可比量，与
`score` 不同），取最小即取"改动最保守"的那个——多个通道都被判定为"安全
可自动清关"时，选择离 opus 现行译文最近的那个，是这批"安全"候选里风险
最低的一个（万一某个通道的 autoclear 资格判定本身有系统性偏差，保守的
那个造成的下游影响也最小）。

## 冻结基线之后新落的人裁 patch：自动清关一律拒写（最终评审 I4）

spec §3 把 `manifest.opus_at`（冻结时点 opus 车道 `forward`/`patches` 的行数
与整体哈希）称作"安全承重点"，并承诺："润色期间若有新裁决 patch 落库，过期
候选由 §4 回执核验**机械失败**，不靠人记"。最终评审 grep 全仓发现
**`opus_at` 只有 `polish_setup` 写、没有任何工具读**（`candidates` 行的
`jp_hash`/`opus_hash` 同样只写不读），并实测复现：冻结之后对某 id 落一条
`reason=review` 的人裁 patch，`commit --apply` 的自动清关照样写一条
`reason=polish` 盖上去，只有一行 stderr `⚠`，**不阻断**。这正是 CLAUDE.md 记
的「SEG-5 id 1600 误覆盖已裁定稿」同一失败模式，区别只在于这次执行者是无人
值守的自动清关。

修法（`_post_freeze_rulings()` + `commit()` 里的拒写分支）：

- 基线取 `manifest["opus_at"]["patches_lines"]`——冻结那一刻 `patches.jsonl`
  的行数。该文件是 append-only 的，故第 `patches_lines` 行之后的全部行都是
  **冻结之后**新落的。
- 其中 `reason ∈ {review, recall}` 的行 = 润色期间新增的**人的裁决**。
- **自动清关路径（`verdict="auto"`）命中即拒绝写入**，并把冲突详情打进
  stderr（id、那条人裁 patch 的 reason/ts/zh 摘要）。人裁路径
  （`verdict ∈ {adopt, edit}`）**放行但显著播报**——那条路径上有人正在看着
  这个 id，他有权在知情的前提下覆盖；无人值守的自动清关没有这个资格。
- 行数比基线**少**（append-only 被破坏，或换了一个车道的 data 目录）：
  无法建立基线 → 保守把**全部** review/recall patch 都视为"冻结后的"，
  自动清关因此在这些 id 上一律拒写，并显式告警。宁可多拦，不可漏拦。
- `manifest.json` 或 `opus_at` 缺失（老 SEG 目录）：同样告警 + 保守按"全部
  review/recall 都算冻结后"处理。

## `queue.md`/`triage.json` 不认识的字段：`decisions.jsonl` 里的额外键

`verdict="auto"` 决策记录除了 brief 给的五个字段（`id`/`verdict`/
`chosen_channel`/`edited_zh`/`reason_code`/`ts`）外，额外带 `zh`/
`candidate_ts`/`prompt_hash`——这是本模块为了让 `decisions.jsonl` 自身就
能支撑"倒查链"审计（不需要再去交叉引用 `candidates.*.jsonl`）而加的，
`edited_zh` 固定填 `None`（这条决策不是人工编辑出来的）。Task 9
`polish_amplify.py` 按 plan 只读 `reason_code`，多出的键对它向后兼容。
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import add_patch
from tools.build_context import glossary_version
from tools.check_batch import _ruby_ok
from tools.pipelib import REPO, append_jsonl, read_jsonl


def _dir_for(label, repo) -> Path:
    """同 Task 3/4/5/6/7 一致的理由：本模块必须能被 tmp_path 造的替身仓库
    完全接管，不得写进真实仓库的 `pilot/polish/`。"""
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def _ws_equal(a, b) -> bool:
    """同 `polish_triage._ws_equal` 的判据（独立定义，不跨模块耦合）：只做
    `.strip()` 空白归一，`_n`/`_r`/ruby 原样参与比较——够用即可，这里只是
    "要不要打一条信息级提示"的软判断，不是安全闸，不需要更严格的归一化。"""
    sa = a.strip() if isinstance(a, str) else ""
    sb = b.strip() if isinstance(b, str) else ""
    return sa == sb


def _load_committed(path) -> set:
    p = Path(path)
    if not p.exists():
        return set()
    data = json.loads(p.read_text(encoding="utf-8"))
    return {(item["id"], item["decision_ts"]) for item in data.get("committed", [])}


def _save_committed(path, committed: set) -> None:
    rows = [{"id": i, "decision_ts": t} for (i, t) in committed]
    rows.sort(key=lambda r: (r["id"] if isinstance(r["id"], int) else 0, r["decision_ts"]))
    Path(path).write_text(
        json.dumps({"committed": rows}, ensure_ascii=False, indent=1), encoding="utf-8")


def _announce_prior(cid, data_dir, *, tag) -> list:
    """dry-run 预览专用：只读地查一遍该 id 是否已有 patch 并打印同款告警。
    `--apply` 路径不调用这个函数——那条路径的播报由 `add_patch.add()` 内部
    自己完成（它本来就会做这件事），避免同一条告警在 apply 模式下打印两遍。
    """
    prior = add_patch.existing_patches(cid, data_dir)
    if prior:
        last = prior[-1]
        print(f"{tag} ⚠ id {cid} 已有 {len(prior)} 条 patch（最近一条 "
              f"reason={last.get('reason')} glossary_v={last.get('glossary_v')} "
              f"ts={last.get('ts')}）\n{tag}   现行译文：{last.get('zh', '')[:60]}\n"
              f"{tag}   ——本次清关将追加新的一条，不覆盖历史；若你以为这一行在润色期间"
              "没被别的会话动过，请先核对。", file=sys.stderr)
    return prior


def _drifted_ids(d: Path) -> set:
    """本 SEG 冻结之后被别的会话改过的 id（`polish_check --lane-drift` 的产物）。
    读不到就返回空集——撤回路径会因此少一层保护，但读不到文件本身不该阻断
    清关；真正的兜底是撤回只对 `committed.json` 里有记录的 id 生效。"""
    p = d / "lane_drift.json"
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    return {f.get("id") for f in data.get("findings", [])}


def _lane_map(data_dir: Path) -> dict:
    """车道现行译文表（forward + patches 解析后）。撤回前用它判断"还有没有
    东西要撤"——车道现值已经等于冻结面就什么都不做，避免写空 diff patch。"""
    from tools.resolve import resolve_map
    fw = read_jsonl(Path(data_dir) / "forward.jsonl")
    pt = read_jsonl(Path(data_dir) / "patches.jsonl")
    return resolve_map(fw, pt)


HUMAN_REASONS = ("review", "recall")


def _post_freeze_rulings(d: Path, data_dir: Path) -> dict:
    """冻结基线之后新落的**人裁** patch：`{id: [patch_row, ...]}`。

    见模块 docstring「冻结基线之后新落的人裁 patch」一节——这是 spec §3 承诺
    的 `manifest.opus_at` 安全承重点第一次真正被消费。基线建不起来时一律
    **保守放大**（把全部 review/recall patch 都当成冻结后的），绝不因为
    "算不出来"就返回空字典放行。
    """
    pat_path = Path(data_dir) / "patches.jsonl"
    rows = read_jsonl(pat_path) if pat_path.exists() else []

    baseline = None
    mp = d / "manifest.json"
    if mp.exists():
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        baseline = (manifest.get("opus_at") or {}).get("patches_lines")
    if baseline is None:
        print(f"!! polish_commit: {mp} 缺 opus_at.patches_lines，无法确定冻结基线"
              "——保守把全部 reason∈{review,recall} 的 patch 都视为「冻结后的人裁」，"
              "自动清关在这些 id 上一律拒写", file=sys.stderr)
        baseline = 0
    elif baseline > len(rows):
        print(f"!! polish_commit: {pat_path} 只有 {len(rows)} 行，少于冻结基线 "
              f"{baseline} 行——append-only 约定被破坏，或 --data-dir 指向了别的车道。"
              "保守把全部 reason∈{review,recall} 的 patch 都视为「冻结后的人裁」",
              file=sys.stderr)
        baseline = 0

    out = {}
    for r in rows[baseline:]:
        if r.get("reason") in HUMAN_REASONS:
            out.setdefault(r.get("id"), []).append(r)
    return out


def commit(label, data_dir, dry_run=True, repo=None, ts=None) -> list:
    """对该 SEG 保税仓里"已裁决/可自动清关"的候选执行唯一清关：写
    `patches.jsonl`（生产车道，`reason="polish"`）。返回本次处理的 patch 行
    列表（`dry_run=True` 时是"将会写入"的预览，`dry_run=False` 时是实际
    已写入的行）。`ts`：仅用于测试注入固定时间戳（本次调用铸造的全部新
    `verdict="auto"` 决策共用同一个值，同一次调用内不同 id 靠 id 本身区分，
    不会产生幂等键碰撞）。
    """
    d = _dir_for(label, repo)
    data_dir = Path(data_dir)
    repo_root = Path(repo) if repo is not None else REPO

    triage_path = d / "triage.json"
    triage = (json.loads(triage_path.read_text(encoding="utf-8"))
              if triage_path.exists() else {"rows": []})
    decisions_path = d / "decisions.jsonl"
    decisions = read_jsonl(decisions_path) if decisions_path.exists() else []
    committed_path = d / "committed.json"
    committed = _load_committed(committed_path)

    # D3 追加：零改动+请裁的行（见 polish_triage 模块 docstring）若被人工裁成
    # adopt/edit 而最终文本又与冻结时点 opus 逐字相同，见下方循环里的信息级
    # 提示——这里先把 opus 现行译文表读出来，供那条检查用。
    opus_fz = d / "frozen" / "opus.jsonl"
    id2opus = ({r["id"]: r["zh"] for r in read_jsonl(opus_fz)}
               if opus_fz.exists() else {})

    gv = glossary_version(repo_root)
    minted_ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")

    _cand_cache = {}

    def last_candidate(channel, cid):
        if channel not in _cand_cache:
            p = d / f"candidates.{channel}.jsonl"
            rows = read_jsonl(p) if p.exists() else []
            last = {}
            for r in rows:
                last[r["id"]] = r  # append-only：同 id 后行覆盖前行，取最后一条
            _cand_cache[channel] = last
        return _cand_cache[channel].get(cid)

    plan = []  # 统一计划项，见模块 docstring；处理前按 decision_ts 排序

    # ---- 同 id 多条裁决：只有最后一条算数（append-only 改判语义）----
    # `decisions.jsonl` 和裁决 UI 的草稿一样是 append-only——人改判就追加一行，
    # 读的时候同 id 取最后一条。本模块此前**逐行**处理，靠 patches.jsonl 的
    # "后写者胜"让最后一条自然生效。那对 adopt→adopt / adopt→edit 是成立的，
    # 但对**撤回**（adopt→keep_opus）根本不成立：keep 不产生 patch，撤不掉
    # 前面那条已经落地的。2026-08-20 实测 p5seg0-s0-s1 有 7 个 id 是这种改判，
    # 其中 6 条的车道文本一直停在被人撤回的那一版上，且全程零告警。
    # 修法两步：这里先只认最后一条（顺带消掉 adopt→adopt 的冗余 patch），
    # 下面再补一条"撤回"路径去追回已经落地的那些。
    RULING_VERDICTS = ("adopt", "edit", "keep_opus", "keep")
    last_ruling_idx = {}
    for i, dec in enumerate(decisions):
        if dec.get("verdict") in RULING_VERDICTS:
            last_ruling_idx[dec.get("id")] = i

    # ---- 来源①：decisions.jsonl 里 verdict in {adopt, edit} 的既有人工裁决 ----
    for i, dec in enumerate(decisions):
        verdict = dec.get("verdict")
        if verdict not in ("adopt", "edit"):
            continue
        cid = dec.get("id")
        if last_ruling_idx.get(cid) != i:
            continue  # 被同 id 的后续裁决取代，不再落地
        decision_ts = dec.get("ts")
        if decision_ts is None:
            print(f"!! polish_commit: id={cid} verdict={verdict} 的 decision 缺 ts，跳过",
                  file=sys.stderr)
            continue
        if (cid, decision_ts) in committed:
            continue
        channel = dec.get("chosen_channel")
        # `edit` 允许没有 chosen_channel（2026-08-20 修）：P4 时期的人工编辑总是
        # "先挑一条通道候选再改"，于是这里把 chosen_channel 当必填；但 P5 的裁决
        # UI 支持**纯人工编辑**——人读了原文自己写一版，不以任何通道候选为底本，
        # 这类决定天然没有通道可指。旧逻辑会把它们**静默跳过**（p5seg0 实测 35 条
        # 人工编辑里 32 条被这样丢掉，而 dry-run 只在 stderr 刷一行"跳过"，
        # 总数对不上才发现）。`adopt` 仍必须带 chosen_channel——它的语义就是
        # "采纳某通道的那一版"，没有通道就无从谈起。
        if not channel:
            if verdict != "edit":
                print(f"!! polish_commit: id={cid} verdict={verdict}（ts={decision_ts}）缺 "
                      "chosen_channel，无法回指候选来源，跳过", file=sys.stderr)
                continue
            cand = None
        else:
            cand = last_candidate(channel, cid)
            if cand is None:
                print(f"!! polish_commit: id={cid} 在 candidates.{channel}.jsonl 里找不到候选"
                      f"（verdict={verdict}，ts={decision_ts}），跳过", file=sys.stderr)
                continue
        if verdict == "adopt":
            # P5 契约 v2：chosen_alt=N（1-based，queue.md 的「备选N」编号）时
            # 采纳该备选而非主候选。备选在入仓时只过了轻量结构闸（【】对齐
            # +MARKS），ruby 良构在此补查——采纳落库是备选文本首次成为现行
            # 文本的时刻，闸必须在这之前。
            alt_n = dec.get("chosen_alt")
            if alt_n:
                alts = cand.get("alts") or []
                if not isinstance(alt_n, int) or not (1 <= alt_n <= len(alts)):
                    print(f"!! polish_commit: id={cid} chosen_alt={alt_n!r} 越界"
                          f"（该候选只有 {len(alts)} 条备选），跳过", file=sys.stderr)
                    continue
                zh = alts[alt_n - 1].get("zh")
                if not _ruby_ok(zh):
                    print(f"!! polish_commit: id={cid} 备选 {alt_n} ruby 不良构，跳过",
                          file=sys.stderr)
                    continue
            else:
                zh = cand.get("zh")
        else:
            zh = dec.get("edited_zh")
            if zh is None:
                print(f"!! polish_commit: id={cid} verdict=edit（ts={decision_ts}）缺 "
                      "edited_zh，跳过", file=sys.stderr)
                continue
        plan.append({
            "id": cid, "verdict": verdict, "decision_ts": decision_ts,
            "channel": channel, "candidate_ts": cand.get("ts") if cand else None,
            "prompt_hash": cand.get("prompt_hash") if cand else None, "zh": zh,
            "chosen_alt": dec.get("chosen_alt") if verdict == "adopt" else None,
            "needs_new_decision_row": False, "decision_row": None,
        })

    # ---- 撤回：最后一条是 keep，但本 SEG 早先已经为这个 id 落过 patch ----
    # 只在"本 SEG 自己落的 patch"上生效：判据是 `committed.json` 里存在该 id
    # 的一条早于这次 keep 的决策。别的会话在润色期间对同一行做的正当改动
    # （lane_drift 记录的那些）不在撤回射程内——那不是本 SEG 的作为，撤它
    # 就成了越权覆盖，故命中漂移一律拒绝并告警，交给人处理。
    drift_ids = _drifted_ids(d)
    lane_now = _lane_map(data_dir)
    for cid, i in sorted(last_ruling_idx.items(),
                         key=lambda kv: (kv[1], kv[0] if isinstance(kv[0], int) else 0)):
        dec = decisions[i]
        if dec.get("verdict") not in ("keep_opus", "keep"):
            continue
        keep_ts = dec.get("ts")
        if keep_ts is None:
            print(f"!! polish_commit: id={cid} verdict={dec.get('verdict')} 缺 ts，"
                  "无法判定撤回，跳过", file=sys.stderr)
            continue
        landed = [x for x in decisions[:i]
                  if x.get("id") == cid
                  and x.get("verdict") in ("adopt", "edit", "auto")
                  and (cid, x.get("ts")) in committed]
        if not landed:
            continue  # 前面那些裁决从没落过地，keep 本来就是"什么都不做"
        if (cid, keep_ts) in committed:
            continue  # 这次撤回已经执行过
        target = id2opus.get(cid)
        if target is None:
            print(f"!! polish_commit: id={cid} 需要撤回，但冻结面 opus.jsonl 里没有"
                  "这个 id，无法确定要回退到什么文本，跳过", file=sys.stderr)
            continue
        # 顺序要紧：先看「还有没有东西要撤」，再看漂移。车道现值已经等于冻结面
        # 时本来就是 no-op，不该因为 lane_drift.json 里有这个 id 就打一条吓人的
        # 告警——而 `polish_check --lane-drift` 若在本段清关**之后**重跑过，
        # 本段自己落的那批 patch 会全部被记成「漂移」，两条检查倒过来就会让
        # 每一条 no-op 撤回都报一次假警（2026-08-23 实测 9050/9051 即如此）。
        if _ws_equal(lane_now.get(cid), target):
            continue  # 车道现值已经等于冻结面，没有要撤的东西
        if cid in drift_ids:
            print(f"!! polish_commit: id={cid} 需要撤回，但它在 lane_drift.json 里"
                  "——冻结之后有别的会话改过这一行，回退冻结面会把那次改动一起"
                  "抹掉。跳过，请人工确认要回到哪一版。", file=sys.stderr)
            continue
        plan.append({
            "id": cid, "verdict": "retract", "decision_ts": keep_ts,
            "channel": None, "candidate_ts": None, "prompt_hash": None,
            "zh": target, "chosen_alt": None,
            "needs_new_decision_row": False, "decision_row": None,
        })

    # ---- 来源②：triage.json 里 autoclear and not sampled 的候选 ----
    rows = triage.get("rows", [])
    auto_by_id = {}
    for r in rows:
        if r.get("autoclear") and not r.get("sampled"):
            auto_by_id.setdefault(r["id"], []).append(r)

    # 已存在的 auto 决策，按 (id, chosen_channel, candidate_ts) 三元组索引——
    # 完全一致视为"同一个自动清关事实此前已记录过"，见模块 docstring。
    existing_auto = {}
    for dec in decisions:
        if dec.get("verdict") == "auto":
            existing_auto[(dec.get("id"), dec.get("chosen_channel"),
                           dec.get("candidate_ts"))] = dec

    for cid in sorted(auto_by_id):
        group = auto_by_id[cid]
        # 多通道同 id 都自动清关：取 edit 最小者，同分按通道名打散（见 docstring）。
        chosen = sorted(group, key=lambda r: (r["edit"], r["channel"]))[0]
        channel = chosen["channel"]
        cand = last_candidate(channel, cid)
        if cand is None:
            print(f"!! polish_commit: id={cid} autoclear 但在 candidates.{channel}.jsonl "
                  "里找不到候选，跳过", file=sys.stderr)
            continue
        candidate_ts = cand.get("ts")
        key = (cid, channel, candidate_ts)
        if key in existing_auto:
            dec = existing_auto[key]
            decision_ts = dec.get("ts")
            if (cid, decision_ts) in committed:
                continue
            plan.append({
                "id": cid, "verdict": "auto", "decision_ts": decision_ts,
                "channel": channel, "candidate_ts": candidate_ts,
                "prompt_hash": cand.get("prompt_hash"),
                "zh": dec.get("zh", cand.get("zh")),
                "needs_new_decision_row": False, "decision_row": None,
            })
        else:
            decision_ts = minted_ts
            decision_row = {
                "id": cid, "verdict": "auto", "chosen_channel": channel,
                "edited_zh": None, "zh": cand.get("zh"), "reason_code": "autoclear",
                "candidate_ts": candidate_ts, "prompt_hash": cand.get("prompt_hash"),
                "ts": decision_ts,
            }
            plan.append({
                "id": cid, "verdict": "auto", "decision_ts": decision_ts,
                "channel": channel, "candidate_ts": candidate_ts,
                "prompt_hash": cand.get("prompt_hash"), "zh": cand.get("zh"),
                "needs_new_decision_row": True, "decision_row": decision_row,
            })

    # 按 decision_ts（同 ts 再按 id）处理，保证多条落地时 patches.jsonl 的
    # 追加顺序与决策产生的时间顺序一致——resolve.resolve_map() 的"后写者胜"
    # 才能正确反映"谁是最后的决定"。
    plan.sort(key=lambda p: (p["decision_ts"], p["id"] if isinstance(p["id"], int) else 0))

    tag = "[dry-run]" if dry_run else "[apply]"
    post_freeze = _post_freeze_rulings(d, data_dir)
    result = []
    for item in plan:
        cid = item["id"]
        # ---- 冻结后人裁 patch 的拒写闸（最终评审 I4）----
        clash = post_freeze.get(cid)
        if clash:
            last = clash[-1]
            detail = (f"id {cid} 在本 SEG 冻结之后新落过 {len(clash)} 条人裁 patch"
                      f"（最近一条 reason={last.get('reason')} ts={last.get('ts')}）\n"
                      f"{tag}   人裁现行译文：{str(last.get('zh', ''))[:60]}\n"
                      f"{tag}   本次拟写入：{str(item['zh'])[:60]}")
            if item["verdict"] in ("auto", "retract"):
                print(f"{tag} ✗ 拒绝写入（自动清关/撤回不得覆盖冻结后的人工裁决）：{detail}\n"
                      f"{tag}   ——这条候选是基于冻结时点的旧 opus 产出的，人裁已经在它"
                      "之后改过这一行。要落它必须走人工裁决（在 decisions.jsonl 里显式"
                      f"给一条 adopt/edit），由人确认是否真的要覆盖 id {cid} 的裁定稿。",
                      file=sys.stderr)
                continue
            print(f"{tag} ⚠ 人工裁决路径覆盖冻结后的人裁 patch：{detail}\n"
                  f"{tag}   ——放行（人裁路径有人在看），但请确认你知道自己在覆盖什么。",
                  file=sys.stderr)
        prov = {"channel": item["channel"], "candidate_ts": item["candidate_ts"], "seg": label}
        if item.get("chosen_alt"):
            prov["chosen_alt"] = item["chosen_alt"]  # 采纳的是第 N 条备选（P5 契约 v2）
        if item["verdict"] == "retract":
            # 这条 patch 不是"采纳了谁"，而是"把本 SEG 早先落的那条撤回"——
            # 内容是冻结面 opus 原文。标出来，免得下游把它当成一次正常采纳。
            prov["retract"] = True
        patch_row = {"id": cid, "zh": item["zh"], "reason": "polish",
                     "glossary_v": gv, "ts": item["decision_ts"], "prov": prov}

        print(f"{tag} id={cid} verdict={item['verdict']} 渠道={item['channel']} "
              f"glossary_v={gv} ts={item['decision_ts']}", file=sys.stderr)
        if item["verdict"] == "retract":
            print(f"{tag}   撤回：本 SEG 早先为这个 id 落过 patch，但最后一条裁决是 "
                  "keep——回退到冻结面 opus 原文。", file=sys.stderr)
        else:
            print(f"{tag}   倒查链：id {cid} → 候选({item['channel']}, "
                  f"ts={item['candidate_ts']}) → prompt_hash={item['prompt_hash']}",
                  file=sys.stderr)
        print(f"{tag}   zh：{item['zh']}", file=sys.stderr)
        # D3 信息级提示（不阻断）：人工裁决（adopt/edit）落地的文本若与冻结
        # 时点 opus 逐字相同，这是一条"空 diff"patch——常见于零改动+请裁
        # 的行被人工 adopt 确认（见 polish_triage 模块 docstring"polish_commit
        # 侧的对应处理"专节）。不是错误，`add_patch.add()` 照常写入，但要
        # 提醒操作者：这类确认通常应该用 keep_opus（不产生任何 patch），
        # 用 adopt/edit 会在 patches.jsonl 里留下一条文字未变的记录。
        if item["verdict"] in ("adopt", "edit") and _ws_equal(item["zh"], id2opus.get(cid)):
            print(f"{tag}   ℹ️ 提示：这条 patch 的译文与冻结时点 opus 逐字相同"
                  "（空 diff）——通常是零改动+请裁的行被人工确认维持原译，"
                  "keep_opus 才是这类确认的正常归宿（不产生任何 patch）；"
                  "本次仍会按 adopt/edit 正常写入，不阻断。", file=sys.stderr)

        if dry_run:
            _announce_prior(cid, data_dir, tag=tag)
            result.append(patch_row)
            continue

        if item["needs_new_decision_row"]:
            append_jsonl(decisions_path, [item["decision_row"]])
            decisions.append(item["decision_row"])

        add_patch.add(cid, item["zh"], "polish", gv, ts=item["decision_ts"],
                       data=data_dir, prov=prov, announce=True)
        committed.add((cid, item["decision_ts"]))
        _save_committed(committed_path, committed)
        result.append(patch_row)

    return result


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="P4 润色 pass：保税仓唯一清关口——dry-run 默认，--apply 才真写",
        epilog="⚠ 车道模式（存在 pilot/lanes/*/data/）下必须显式给 --data-dir 或设 "
               "ZND_DATA，否则拒绝执行——见 tools/add_patch.resolve_data_dir。")
    ap.add_argument("--seg", required=True, help="段表 label（如 seg1-s2）")
    ap.add_argument("--data-dir", type=Path, default=None,
                     help="生产车道 data 目录（如 pilot/lanes/opus/data）；车道模式下"
                          "缺省即拒绝执行")
    ap.add_argument("--apply", action="store_true",
                     help="真正写入 patches.jsonl/decisions.jsonl/committed.json；"
                          "省略则只预览（dry-run，默认）")
    ap.add_argument("--repo", default=None,
                     help="车道根目录（省略时用仓库根；测试用 tmp_path 传替身仓库）")
    args = ap.parse_args(argv)

    data_dir = add_patch.resolve_data_dir(args.data_dir, repo=args.repo)
    result = commit(args.seg, data_dir, dry_run=not args.apply, repo=args.repo)

    mode = "APPLY" if args.apply else "DRY-RUN"
    tail = f"已写入 {data_dir}" if args.apply else "未写入任何文件——加 --apply 才真写"
    print(f"polish_commit[{mode}]: {args.seg} 共 {len(result)} 条 patch（{tail}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
