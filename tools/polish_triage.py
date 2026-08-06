"""P4 润色 pass：四桶分流决策中枢——整条润色流水线里"谁自动入库、谁排队
给人裁、谁保留 opus"的唯一判定点。消费 Task 5/6 的产出（`candidates.
<channel>.jsonl` / `gates.<channel>.json`）与 Task 3 的冻结面（`frozen/
opus.jsonl` / `frozen/locked.json`），产出 `triage.json`（机器可读的分流
结果，Task 8 `polish_commit.py` 的唯一输入）与 `queue.md`（人读的裁决
队列）。

## 核心原则（spec §9 明写，本模块存在的理由）

**模型自报的 `score` 只在同档内排序，绝不作为绝对阈值**——跨模型（fable/
deepseek/未来第三个）的自报分不可比。分桶靠的是客观信号：是否命中冻结面、
有没有真的改动、改动幅度多大、机械闸是否全绿；`score` 只用来在"改动幅度
打平"时做同档内的精细排序。任何把 `score` 变成阈值（比如"score<60 才
autoclear"）的实现都是错的——本模块通篇不出现这种比较。

## 桶判定顺序（brief 原文，逐字照抄）

对每一条 `(id, channel)` 候选行：
1. **locked → 0**：id 在 `frozen/locked.json` 的锁定集合里。理论上
   `polish_ingest.ingest()` 已经在入仓时判死锁定 id 出稿，候选文件里
   不应该出现锁定 id——这里是**兜底**（防御 `locked.json` 在 ingest 之后
   被新裁决 patch 更新、或任何绕过 ingest 直接写入 candidates 文件的
   异常路径）。
2. **`zh == opus`（归一后逐字相等）→ 1**：见下方"零改动判据"专节，
   这里刻意只做**空白归一**，不剥控制码/ruby。
3. 其余（有真实改动的候选）进入排队池，按 id 分组（见"K 配额与多通道
   同 id"专节）用（`adjudicate` 显式请裁优先 → `edit` 大→小 → 同 edit
   按 `score` 低→高 → id 升序兜底去重）排序，前 `K − 抽检占用` 个 id
   → 2；其余 → 3。

## 自动清关（从桶 2/3 前"截流"——见"K 配额"专节展开这句话到底什么顺序）

`bucket∈{2,3}` 且 `edit ≤ autoclear_limit(opus)` 且该行所在通道
`gates.<channel>.json` 里这个 id 的 `hard` 为空且该通道自动清关权开启
（`channel_state.json`，缺省关闭）→ 从竞争排队的候选池里摘出，`autoclear
=True`；其中按 `sample_rate` 抽一部分 `sampled=True` 塞回裁决队列（占用
K 配额，供人工事后审计，Task 8 只对 `autoclear and not sampled` 的候选
直接清关，`sampled=True` 的即使 `autoclear=True` 也还要走一遍人工裁决——
这是 Task 8 brief 原文的分工，本模块只需要保证两个字段都如实落盘）。

`channel=="amplify"` 恒不 autoclear，与 `channel_state.json` 里写了什么
无关——测试 `test_amplify_never_autoclears` 故意先开启 amplify 的清关权
再断言它仍然不生效，就是为了钉死"这条硬规则不依赖配置，配置开对了也没用"。

## 三个自行裁定的设计点（brief 明确点名要我拿主意的地方）

### 1. K 的分配：多通道同一 id 只占一个名额

`K`（`config/polish.yaml` 里的 `K: 150`）是**整个 SEG 的总额，多通道
共享**。裁决时是**并排比较**（`queue.md` 把同一 id 的全部通道候选列在
一起给人一次看完），所以"要不要占用一个 K 名额"天然是**按 id**、不是
按 `(id, channel)` 行。

实现：把"需要裁决"的候选行（桶 2/3 候选，不含 0/1）先按 `id` 分组
（`pool: dict[id -> list[row]]`），K 配额的排序、截断、abstain 全部在
"id 分组"这一层操作——一个 id 无论有 1 个还是 3 个通道的候选行，进
`pool` 之后只对应**一次**排序 key、**一次**"是否挤进前 K"的判断，决定
出的 bucket 会**同时施加给该 id 名下的全部候选行**（不会出现同一 id
在不同通道下拿到不同 bucket 的情况——那样"并排比较"就没有意义了：
人工裁决台面上摆着同一个 id 的两个候选，总不能一个算"配额内"另一个
算"配额外"）。

排序 key 里"多通道怎么聚合成一个"的选择（都记在 `_sort_key` 里）：
- **`adjudicate` 优先级**：组内**任意**一行显式请裁 → 整个 id 视为显式
  请裁。理由：显式请裁是模型主动喊"这句我吃不准，请人看"，任何一个
  通道喊了，这个 id 就该被人看到，不该因为另一个通道没喊就被稀释掉。
- **`edit`（改动幅度）聚合**：取组内**最大**编辑距离。理由：多通道里
  只要有一个通道对这个 id 提出了大改动，这个 id 本身就值得优先审——
  用最小值聚合会让"一个通道乱改、另一个通道没怎么动"的危险案例被
  没怎么动的那个通道拖累评分，systematically 压低优先级，不安全。
- **`score`（同 edit 打平的最后并列）聚合**：取组内**最小**分。理由与
  上面对称——`score` 低代表"这个通道自己都不太确定"，聚合取更谨慎的
  那个值，不让"某个通道虚报高分"把整个 id 的排队优先级拉低。
  ⚠ 再强调一次：这只是**同一 id 内、edit 打平之后**的最后一道并列
  打散手段，从未跨 id/跨通道地把 score 当阈值用。

### 2. 抽检占用 K：顺序依赖的正确展开

brief 原文点破了这里的循环依赖："抽检数取决于自动清关数，而自动清关是
从桶 2/3 前截流的"。真正的执行顺序（避免循环的唯一办法：让"是否
autoclear-eligible"完全独立于"排位排到第几"）：

1. 先算桶 0（locked）、桶 1（零改动）——这两桶的判据不依赖 K/排序/
   autoclear，可以无条件先算。
2. 剩下的候选行按 id 分组成 `pool`。**对每一行**（不依赖它将来会被
   排到桶 2 还是桶 3）算 `_eligible`：`edit ≤ autoclear_limit(opus)`
   且该行所在通道这个 id 的 gates hard 为空且该通道自动清关权开启且
   `channel != "amplify"`——这四个条件全部只看"这一行自己的属性"，
   与"它在全体候选里排第几"完全无关，所以可以在排序之前就算出来，
   打破了"autoclear 依赖 bucket、bucket 依赖排序、排序又要扣掉抽检
   占用"这个看似循环的链条：**只要 autoclear 的判据本身不依赖排名，
   循环就不存在**——brief 里"bucket∈{2,3}"这半句话不是要求"先分出
   2/3 再倒查 autoclear"，而是在说"只有非 0/1 的候选才谈得上 autoclear
   这件事"（0/1 桶的候选不需要"自动清关"这个动作：0 桶本来就不出稿，
   1 桶本来就零改动不产生 patch），这一点在算 `_eligible` 时已经隐含
   满足（只对 `pool` 里的行算）。
3. 一个 id **只有组内全部候选行都 `_eligible`**，才把整个 id 从 `pool`
   摘出、归入 `autoclear_ids`（"unanimous" 规则，展开见下一节）；否则
   留在 `pool` 里正常参与排序竞争（即使其中某一行单独看是"小改+绿"，
   只要同 id 还有别的通道候选没过关，人工照样要把这几行摆在一起看，
   autoclear 单独摘走其中一行没有意义——见"id 级 all-or-nothing"专节）。
4. 对 `autoclear_ids`（此时已确定，不再变化）用种子化的 `random.Random`
   逐 id 抽样，抽中的记 `sampled=True` 并**强制**收进裁决队列（bucket=2，
   不参与下面的排序竞争、直接占一个位置）；抽不中的 `sampled=False`，
   `bucket=3`（未进队列——即"记录在案，autoclear 已经把它清关掉了，
   不需要也不会出现在 `queue.md`"）。
5. 到这一步，"抽检占用了多少个 K 名额"（`len(sampled_ids)`）已经是
   确定数字，`pool` 里剩下的（未被摘出的）id 才真正进入"按 key 排序、
   取前 `K − len(sampled_ids)` 个 → 桶 2，其余 → 桶 3"这一步。

这个顺序——**先兜底桶 0/1，再逐行独立算 autoclear 资格，再按 id 做
all-or-nothing 摘除+抽样，最后才用"K 减去抽样数"去切排序队列**——是
本模块唯一不产生循环依赖的写法，因为每一步只依赖"更早、且与自身无关"
的信息。

### 3. `edit == 0` 与 `zh == opus` 的关系：两套归一化，不能共用一套

brief 点名的风险："归一过头会把「只改了控制码位置」的真实改动误判成
零改动，那是静默丢失"。本模块对"相等"和"幅度"故意用**两套不同**的
归一化，缺一不可：

- **桶 1 的"零改动"判据**（`_ws_equal`）：只做 `.strip()`（掐首尾空白），
  `_n`/`_r`/ruby 全部**原样保留参与比较**。理由：这些控制码是内容的
  一部分（`_n`/`_r` 决定断行位置，ruby 的拼音/注音部分是要显示给玩家
  看的文字），如果润色只是把 `_n` 挪了个位置、或者改了 ruby 注音的
  拼音拼写，这**是一次真实的、需要被看见的改动**——不能因为"剥掉
  控制码之后两边长得一样"就悄悄归零，那样这次改动会从 triage.json
  里彻底消失（既不产生 patch，也不会被任何人看到），是不可接受的
  静默丢失。
- **`edit`（幅度分档，供排序与 autoclear 阈值比较用）**：`edit_distance`
  跑在 `polishlib.strip_ctl()` 剥过控制码/ruby 之后的文本上。理由：
  `autoclear_limit(opus_zh)` 本身就是"以剥控制码后的长度算比例阈值"
  （`tools/polishlib.py` 第 39-40 行），如果 `edit` 却在带控制码的原文
  上算，两者的"单位"对不上——一次纯粹的 `_n`→`_r` 换行方式调整会被
  计入很大的编辑距离，跟"幅度阈值是按可读正文字数定的"这个设计初衷
  冲突，会把大量"内容其实没怎么变、只是断行方式变了"的候选错误地
  推去人工排队，稀释 K 配额、掩盖真正的大改动。

两套分开之后互不干扰：一次纯控制码变动，`_ws_equal` 判定为"有改动"
（不会被静默吞掉、能进入 pool 参与排序/autoclear），但 `edit`（幅度）
很可能算出接近 0（因为剥控制码后两边文本一样）——只要 gates 绿、通道
清关权开，这类"改动真实存在但幅度可忽略"的候选恰好会被 autoclear
判定为"小改"而自动清关，这正是我们想要的行为：改动没有被隐藏（触发
了自动清关流程），但也没有占用宝贵的人工审阅名额（幅度确实可忽略）。

## id 级 all-or-nothing 的 autoclear 规则

上面第 3 点提到："一个 id 只有组内全部候选行都 eligible 才整体摘出"。
换句话说：**autoclear 是以 id 为单位的整体决定，不是逐通道各自决定**。
如果同一 id 下 channel A 的候选够格自动清关、channel B 的候选不够格
（比如改动更大、或 gates 没过），这个 id 整体留在 `pool` 里正常排队，
channel A 那一行**不会**被单独摘走——理由与 K 配额分组一致：既然这个
id 注定要摆上人工裁决台面（因为 channel B 需要人看），channel A 的
候选留在台面上供人一起参照比较，没有必要（也不应该）自己先斩后奏
清关掉。反过来，如果这个 id 名下**只有一个**通道提交过候选（P4 的
主要形态——多通道分段分担为主），"全部候选行" 退化成"这一行"，
all-or-nothing 规则自然退化成普通的单行判定，不额外增加负担。

## 抽样与排序的确定性

`random.Random(int(manifest["files"]["frozen/source.jsonl"][:8], 16))`
——⚠ **与 brief 原文一处已核实的偏差**：brief 写的 key 是
`"source.jsonl"`，但实测 `polish_setup.setup()` 落盘的 `manifest.json`
里 `files` 字典的 key 是**相对 SEG 目录**的路径（`p.relative_to(d)`，
`d` 是 `pilot/polish/<label>/`，`p` 遍历的是 `d/"frozen"` 子树），实际
key 是 `"frozen/source.jsonl"`，不带 `frozen/` 前缀的 `"source.jsonl"`
在真实 manifest 里**不存在**，按 brief 字面实现会在真实 SEG 上直接
`KeyError`。已用临时仓库跑过一遍 `polish_setup.setup()` 验证（见
task-7-report.md），按实测结果改用 `"frozen/source.jsonl"`。

随机数**只用在一处**：从 `autoclear_ids`（此时已经是一个与排序无关、
仅由"是否全部符合 autoclear 资格"决定的集合）按固定顺序（`sorted()`
出来的 id 升序）逐个抽取 `rng.random() < sample_rate`。这保证了两次
调用 `triage()`（同一份磁盘状态、没有任何东西被改动）产生**完全一致**
的抽样结果——`test_deterministic_sampling` 验证的就是这件事。**排序
本身不需要随机数**：`_sort_key` 用显式的 `(adjudicate, edit, score, id)`
四元组做 key，`id` 作为最终并列打散兜底，Python 的 `sorted()` 本身
就是确定性的稳定排序，不依赖字典/集合的迭代顺序（本模块里所有会影响
输出顺序的地方——`channels`、`pool` 的 id 遍历、最终 `rows` 落盘前—
—都显式 `sorted()` 过，不依赖 `dict`/`set` 的天然迭代顺序，虽然
CPython 3.7+ 字典本身有序，但集合 `set` 的迭代顺序不保证，本模块用到
集合的地方（`locked_ids`、`sampled_ids`、`top_ids`）全部只用来做
`in` 成员判断，从不直接迭代取顺序）。

## queue.md：给人裁决用，抽检项"标出来但不泄露"

`queue.md` 只收桶 2（K 配额内）的 id，按 id 升序排列；每个 id 一节，
并排列出该 id 全部通道的候选（jp 原文 + opus 现行译文 + 各通道
`zh`/`score`/批注），外加一行"为什么进队列"。

**抽检的标注权衡**（brief 明确要求自己拿主意）：`triage.json` 里的
`sampled` 字段如实记录（机器可读、供 Task 10 之后统计推翻率），但
`queue.md`（人读的裁决界面）**故意不出现"这是随机抽检"这几个字**。
原因：知道某一条是"已经自动清关、只是抽出来给你复核一下"会实质性
改变裁决者的心态——大概率会倾向于"既然已经通过了，那就没问题吧"
从而降低审查强度，这恰恰摧毁了抽检本来要验证的东西（"自动清关的
判定是否可信"，需要裁决者用跟审别的候选**同样**的严格程度去看它，
结果才有统计意义）。所以 `queue.md` 里能显式区分的"为什么进队列"
只有两档：
- **「显式请裁」**：该 id 至少一个通道候选 `adjudicate=True`。
- **「进入本轮裁决队列」**：其余全部情况——不管是"改动幅度靠前、
  正常排位挤进了 K 配额"还是"已自动清关、抽中审计样本被塞回来"，
  一律用这句话，**故意不再细分**，让两者在文档里长得一模一样。

## `channel_state.json` 缺失时的保守缺省

`channel_state.json` 是 Task 10（准入小考）的产出，本任务实施时**尚
不存在**、也不应该在本模块里创建。文件整体缺失，或者某个 channel
压根不在里面（比如刚接入的新通道，还没跑过准入小考）——两种情况
一律视为"该通道自动清关权关闭"。这是故意的保守缺省，呼应 CLAUDE.md/
brief 反复强调的原则："没考过准入小考就不许免检"——**任何把这个缺省
翻转成"缺失=默认开启"的改动都是危险的**（会让一个从未被校准过的
新通道，第一天接入就能自动往库里写东西），本模块专门为这个缺省
方向配了一个变异自检（见 `tests/test_polish_triage.py`）。
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, dumps, read_jsonl
from tools.polishlib import CFG, autoclear_limit, edit_distance, strip_ctl


def _dir_for(label, repo) -> Path:
    """同 Task 3/4/5/6 一致的理由：`polishlib.seg_dir()` 硬编码仓库根，
    这里另起一份只在 `repo` 落空时退化，使 `triage()`/CLI 都能被 tmp_path
    造的替身仓库完全接管（测试要求：不得写进真实仓库的 `pilot/polish/`）。"""
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def load_gates(path) -> dict | None:
    """`gates.<channel>.json` 磁盘上的 key 是 JSON 字符串（int 键无法落
    JSON——见 Task 6 `polish_check.gate()` 落盘前的显式转换），这里统一转
    回 int 键，供本模块直接用 id（int）查。

    返回 `None`（不是 `{}`）表示"这个通道的 gates 文件根本不存在"——即
    Task 6 `gate()` 从未针对这个通道跑过；这与"跑过、返回空字典（全绿）"
    是两种不同的状态，`triage()` 据此做出的默认动作也不同：**没有 gates
    证据 → 不允许该通道任何候选自动清关**（与 `channel_state.json` 缺失
    时的保守缺省同一逻辑：没有证据就不给通过）。这个 helper 按 Task 6
    评审遗留的 concern（磁盘 str key / 内存 int key 的落差）而设，放在本
    模块而不是回去改 `polish_check.py`——那个文件已经过评审、进入 clean
    状态，本模块是它目前唯一的消费方，没有必要为了一个纯读取侧的小转换
    再触碰一个已完成任务的文件。
    """
    p = Path(path)
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {int(k): v for k, v in raw.items()}


def _load_channel_state(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _channel_autoclear_power(channel, channel_state) -> bool:
    """`channel_state.json` 缺失、或该 channel 不在里面 → 自动清关权
    一律关闭（保守缺省，见模块 docstring 专节）。`channel == "amplify"`
    恒 False，与 `channel_state` 内容无关——这条硬规则由调用方
    （`_row_eligible`）里另一个独立条件表达，这个函数本身只负责读取
    配置这一件事，不在这里重复判 amplify（保持单一职责，"amplify 恒
    不清关"这条硬规则集中写在一处，靠调用方合取）。
    """
    return bool(channel_state.get(channel, {}).get("autoclear", False))


def _ws_equal(a, b) -> bool:
    """桶 1"零改动"判据的归一化——只做空白层面的 `.strip()`，`_n`/`_r`/
    ruby 全部原样保留参与比较。见模块 docstring"edit==0 与 zh==opus 的
    关系"专节：归一过头（比如顺手剥了控制码再比）会把"只改了控制码
    位置/ruby 拼音"这类真实改动误判成零改动，那是静默丢失。"""
    sa = a.strip() if isinstance(a, str) else ""
    sb = b.strip() if isinstance(b, str) else ""
    return sa == sb


def _content_edit(zh, opus_zh) -> int:
    """幅度分档用的编辑距离——在 `strip_ctl()` 剥过控制码/ruby 之后的
    文本上算，与 `polishlib.autoclear_limit()` 的阈值基准（同样剥过
    控制码再算长度）保持同一"单位"，见模块 docstring 专节。"""
    zs = strip_ctl(zh) if isinstance(zh, str) else ""
    os_ = strip_ctl(opus_zh) if isinstance(opus_zh, str) else ""
    return edit_distance(zs, os_)


def triage(label, repo=None) -> dict:
    """对该 SEG 全部通道当前保税仓里的候选做四桶分流 + 条件自动清关 +
    确定性抽检，写 `triage.json` + `queue.md`，返回
    `{"rows": [{id, channel, bucket, edit, autoclear, sampled}, ...],
      "queue_ids": [...]}`。
    """
    d = _dir_for(label, repo)
    fz = d / "frozen"

    source_rows = read_jsonl(fz / "source.jsonl")
    id2jp = {r["id"]: r["jp"] for r in source_rows}
    opus_rows = read_jsonl(fz / "opus.jsonl")
    id2opus = {r["id"]: r["zh"] for r in opus_rows}
    locked = json.loads((fz / "locked.json").read_text(encoding="utf-8"))
    locked_ids = set(locked.get("ids", []))

    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    seed_hash = manifest["files"]["frozen/source.jsonl"]
    rng = random.Random(int(seed_hash[:8], 16))

    channel_state = _load_channel_state(d / "channel_state.json")

    channels = sorted(
        p.name[len("candidates."):-len(".jsonl")]
        for p in d.glob("candidates.*.jsonl")
    )

    rows = []       # 已定桶（0/1）或即将定桶（2/3）的全部候选行，最终输出源
    pool = {}       # id -> [row, ...]：尚待裁决/自动清关判定的候选

    for channel in channels:
        candidates = read_jsonl(d / f"candidates.{channel}.jsonl")
        last_by_id = {}
        for c in candidates:
            last_by_id[c["id"]] = c  # 同 id 后行覆盖前行——取最后一条

        gates = load_gates(d / f"gates.{channel}.json")

        for cid in sorted(last_by_id):
            c = last_by_id[cid]
            if cid not in id2jp:
                print(f"!! polish_triage: {label}/{channel} 的候选 id={cid} "
                      "不在 frozen/source.jsonl 里，已跳过", file=sys.stderr)
                continue

            zh = c.get("zh")
            opus_zh = id2opus.get(cid, "")
            row = {
                "id": cid, "channel": channel,
                "bucket": None, "edit": _content_edit(zh, opus_zh),
                "autoclear": False, "sampled": False,
                "_zh": zh, "_note": c.get("note", ""),
                "_score": c.get("score"), "_adjudicate": bool(c.get("adjudicate", False)),
            }

            if cid in locked_ids:
                row["bucket"] = 0
                rows.append(row)
                continue
            if _ws_equal(zh, opus_zh):
                row["bucket"] = 1
                rows.append(row)
                continue

            gate_entry = gates.get(cid) if gates is not None else None
            gates_hard_empty = gates is not None and not (gate_entry or {}).get("hard")
            row["_eligible"] = (
                channel != "amplify"
                and row["edit"] <= autoclear_limit(opus_zh)
                and gates_hard_empty
                and _channel_autoclear_power(channel, channel_state)
            )
            pool.setdefault(cid, []).append(row)

    # --- id 级 all-or-nothing：组内全部候选行都 eligible 才整体摘出 ---
    autoclear_ids = sorted(cid for cid, grp in pool.items()
                            if grp and all(r["_eligible"] for r in grp))
    non_autoclear_ids = sorted(set(pool) - set(autoclear_ids))

    # --- 确定性抽样：固定顺序（id 升序）逐个抽，seed 来自 manifest 哈希 ---
    sampled_ids = {cid for cid in autoclear_ids if rng.random() < CFG["sample_rate"]}

    for cid in autoclear_ids:
        for r in pool[cid]:
            r["autoclear"] = True
            r["sampled"] = cid in sampled_ids
        if cid not in sampled_ids:
            for r in pool[cid]:
                r["bucket"] = 3
            rows.extend(pool[cid])

    # 抽中的自动清关 id：强制塞回裁决队列（bucket=2），不参与下面的排序
    # 竞争——它们"占 K"，不是"跟别人抢 K"。
    for cid in sorted(sampled_ids):
        for r in pool[cid]:
            r["bucket"] = 2
        rows.extend(pool[cid])

    def _sort_key(cid):
        grp = pool[cid]
        adjudicate_flag = any(r["_adjudicate"] for r in grp)
        max_edit = max(r["edit"] for r in grp)
        scores = [r["_score"] for r in grp if isinstance(r["_score"], (int, float))]
        min_score = min(scores) if scores else -1  # 缺分默认最优先复核
        return (not adjudicate_flag, -max_edit, min_score, cid)

    ranked_ids = sorted(non_autoclear_ids, key=_sort_key)
    quota = max(0, CFG["K"] - len(sampled_ids))
    top_ids = set(ranked_ids[:quota])

    for cid in ranked_ids:
        bucket = 2 if cid in top_ids else 3
        for r in pool[cid]:
            r["bucket"] = bucket
        rows.extend(pool[cid])

    rows.sort(key=lambda r: (r["id"], r["channel"]))
    queue_ids = sorted({r["id"] for r in rows if r["bucket"] == 2})

    out_rows = [{"id": r["id"], "channel": r["channel"], "bucket": r["bucket"],
                 "edit": r["edit"], "autoclear": r["autoclear"], "sampled": r["sampled"]}
                for r in rows]
    result = {"rows": out_rows, "queue_ids": queue_ids}

    d.mkdir(parents=True, exist_ok=True)
    (d / "triage.json").write_text(dumps(result), encoding="utf-8")
    _write_queue_md(d, queue_ids, rows, id2jp, id2opus)
    return result


def _write_queue_md(d: Path, queue_ids, rows, id2jp, id2opus) -> None:
    """人读的裁决队列。同 id 的多通道候选并排列出；"为什么进队列"只分
    两档（显式请裁 / 进入本轮裁决队列），刻意不区分"正常排位"与"抽检"
    ——见模块 docstring"queue.md：抽检项标出来但不泄露"专节。"""
    by_id_rows = {}
    for r in rows:
        if r["bucket"] == 2:
            by_id_rows.setdefault(r["id"], []).append(r)

    lines = ["# 裁决队列\n", f"共 {len(queue_ids)} 个待裁 id（K 配额内）。\n"]
    for cid in queue_ids:
        group = sorted(by_id_rows.get(cid, []), key=lambda r: r["channel"])
        lines.append(f"## id {cid}\n")
        lines.append(f"- 日文原文：{id2jp.get(cid, '')}")
        lines.append(f"- 现行译文（opus）：{id2opus.get(cid, '')}")
        reason = "显式请裁" if any(r["_adjudicate"] for r in group) else "进入本轮裁决队列"
        lines.append(f"- 进入队列原因：{reason}")
        for r in group:
            note = f"（批注：{r['_note']}）" if r["_note"] else ""
            lines.append(f"- **{r['channel']}**（score={r['_score']}）：{r['_zh']}{note}")
        lines.append("")
    (d / "queue.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="P4 四桶分流 + 条件自动清关 + 确定性抽检")
    ap.add_argument("--seg", required=True, help="段表 label（如 seg1-s2）")
    ap.add_argument("--repo", default=None,
                     help="车道根目录（省略时用仓库根；测试用 tmp_path 传替身仓库）")
    args = ap.parse_args(argv)

    result = triage(args.seg, repo=args.repo)
    rows = result["rows"]
    counts = {b: sum(1 for r in rows if r["bucket"] == b) for b in (0, 1, 2, 3)}
    n_autoclear = sum(1 for r in rows if r["autoclear"])
    n_sampled = sum(1 for r in rows if r["sampled"])
    print(f"triage: {args.seg} 共 {len(rows)} 条候选（跨全部通道）——"
          f"桶0 {counts[0]} / 桶1 {counts[1]} / 桶2 {counts[2]} / 桶3 {counts[3]}，"
          f"自动清关 {n_autoclear}（其中抽检 {n_sampled}），"
          f"裁决队列 {len(result['queue_ids'])} 个 id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
