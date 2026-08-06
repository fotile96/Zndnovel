"""P4 润色 pass：保税仓机械闸——候选级复用 `check_batch.check()`。

薄封装：把已经成熟的批校验（R2a/R2b/R2c 硬规则、W1/W2/W3 软规则，见
`tools/check_batch.py`）套用到某个 SEG 某个通道当前保税仓（`candidates.<channel>
.jsonl`，`tools/polish_ingest.py` 的唯一入仓口）里的候选上，产出
`gates.<channel>.json`：`{id: {"hard": [...], "warn": [...]}}`，**只收有问题的
id**（全绿的 id 不进字典——`gates.json` 的用途是"标出问题"，Task 7 消费时只
需要判断某 id 是否在字典里、`hard` 是否非空，不需要靠这份文件反查"全库有多
少 id"，那个信息 `frozen/source.jsonl`/`candidates.<channel>.jsonl` 本身就有）。

**hard 非空的候选后续一切分流不得自动清关**（Task 7 消费本模块产出时的硬
约束，brief 原文）。

## 与 check_batch.check() 的接口对齐——id 集裁剪（本模块最关键的一步）

`check_batch.check(source_rows, draft_rows, ...)` 开头就断言两者 id 集合
完全一致，不一致立刻返回一条 R1 硬伤并**放弃后续全部检查**（见其源码开头
`if set(src) != set(drf) or len(draft_rows) != len(drf): ...; return`）。
`frozen/source.jsonl` 含该 SEG 全部 id（含锁定 id），而候选 `candidates.
<channel>.jsonl` 天生只含**非锁定** id（`polish_ingest.ingest()` 判死锁定
id 出稿，锁定 id 从不出现在候选里）——两个集合按定义就不相等。如果不按
候选实际覆盖的 id 集裁剪 `source_rows`，`gate()` 每次都只会得到孤零零一条
`R1`，R2a/R2b/R2c/W1/W2/W3 一条都跑不出来——闸看起来跑了（有输出、有
`gates.<channel>.json` 文件），实际什么也没查，是本项目反复吃过亏的"恒绿闸"
的又一种形态（参见 `check_batch.py`/`polish_ingest.py` 里同类告诫）。本模块
的自检变异②专门验证"不裁剪会导致这种恒绿闸重新出现"（见测试文件）。

## speakers 的取法——frozen-only，无回落（评审修复轮定案）

初版实现在 `frozen/glossary/speakers.json` 缺失时退化读 `<repo>/glossary/
speakers.json`（活仓库）。**评审判定这条退化本身就是缺陷（Important）**：
它复现了 `polish_context.render()` 专门用变异测试钉死过的同一类问题（"润色
输入只认冻结面，不读活仓库"，见 spec §3/`docs/superpowers/specs/
2026-08-07-p4-polish-pass-design.md`）——R2b 的说话人映射是**影响判定
结果**的输入，一旦某 SEG 冻结之后活仓库的 `glossary/speakers.json` 被
修订，该 SEG 的机械闸结论会**静默漂移**，而 `polish_setup.verify()` 对此
完全失明（它只哈希 frozen 里已登记的文件，不知道"活仓库又变了"这件事）。
初版能跑对纯粹是因为仓库根恰好有这份文件，不是设计上的保证。

**根因不在本模块，在 `tools/polish_setup.py` 的冻结清单本身漏了
`speakers.json`**（spec §3 的 frozen glossary 清单与 §8 机械闸依赖 R2b
两处对不上）——已回填：`_copy_glossary()` 现在会把 `glossary/speakers.json`
一并拷进 `frozen/glossary/`（连带更新了 spec §3 清单、计划文本 Task 3
描述、`tests/test_polish_setup.py` 的 mini 夹具与新增回归测试）。

本模块现在**只读 `frozen/glossary/speakers.json`，不做任何回落**：文件
不存在时 `_load_speakers()` 返回 `None`（`check()` 内部对应分支会跳过
名字映射校验，但 R2b 的**结构对齐**检查恒查、不受影响，见 `check_batch.py`
的 P1c 硬化）。这与 `polish_context.render()` 已确立的"frozen-only，无
回落"约定一致，也用变异④验证了"回落"这条老代码路径一旦被误改回来，测试
必须真正抓到（见测试文件 `test_polish_check.py`）。

## W4 不在此跑——分工说明

`check_batch.check()` 的 `siblings` 参数（W4：复现句族逐字一致）需要
`check_batch.load_siblings(root)` 建立的**全库**兄弟索引（依赖车道
`data/ledger.jsonl` + `forward.jsonl`/`patches.jsonl`），这是"清关后全段
复检"的范畴（Task 11 runbook），不是候选级机械闸的职责——保税仓阶段还没
有清关，谈不上"全段"。本模块调用 `check()` 时恒传 `siblings=None`，W4 在
这一层**完全不跑**（不是"跑了但没查出问题"）。**别把这一点和"W4 已被
Task 6 覆盖"搞混**——Task 5 `polish_ingest.py` 的模块 docstring 在"错位
侦测"一节点名引用了本模块的 R2b 作为下游兜底之一，两边的分工描述要对得
上：本模块负责 R2a/R2b/R2c/W1/W2/W3，W4 由 Task 11 负责。

## R2b 与 Task 5 错位侦测的关系

`polish_ingest.ingest()` 的错位侦测只抓一种确切指纹——"`zh` 逐字等于本批
另一 id 的 opus"；模型如果把错挂的 `zh` 又顺手润色改写过（不再与任何 opus
逐字相同），那道闸抓不住，会放行入仓。**本模块的 R2b（【】说话人结构对齐
+ 名字映射）是这一残留面的主要兜底**：错位挂过来的文本大概率带着错误场景
的说话人前缀（原文说话人对不上），R2b 会把它报成 hard，挡在自动清关之外。

## 同 id 多条候选——取最后一条

理论上同一 (label, channel) 下同一 id 不应有多条候选（`ingest()` 对同批
重跑是幂等的），但 amplify 等场景会以不同 batch/轮次向同一个
`candidates.<channel>.jsonl` 继续 append。若真出现同 id 多条，取**最后一
条**——append-only 文件里"后来者为现行"是通篇一致的语义（同一约定见
`check_batch.py` 对 forward/patches 的处理方式）。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.check_batch import check
from tools.pipelib import REPO, dumps, read_jsonl


def _dir_for(label, repo) -> Path:
    """同 `polish_setup._dir_for` / `polish_ingest._dir_for` 的理由：
    `polishlib.seg_dir()` 硬编码用仓库根，不接受覆盖；这里另起一份，只在
    `repo` 落空时才退化到默认路径，使 `gate()`/CLI 都能被 tmp_path 造的替身
    仓库完全接管（测试要求：不得写进真实仓库的 `pilot/polish/`）。"""
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def _load_speakers(fz: Path) -> dict | None:
    """见模块 docstring"speakers 的取法"一节：frozen-only，无回落——不存在
    就是 None，绝不去读活仓库（`polish_context.render()` 已确立的同一约定；
    评审判定"回落读活仓库"本身是缺陷，见 docstring）。"""
    frozen_p = fz / "glossary" / "speakers.json"
    if frozen_p.exists():
        return json.loads(frozen_p.read_text(encoding="utf-8"))
    return None


def gate(label, channel, repo=None) -> dict:
    """对该 SEG/通道当前保税仓里的全部候选跑 `check_batch.check()`，返回
    `{id: {"hard": [...], "warn": [...]}}`（只收有问题的 id），并写
    `gates.<channel>.json`。

    `candidates.<channel>.jsonl` 不存在（该通道还没入仓过任何东西）时，
    等同于"零候选"：返回空字典，照常落盘一份空 `gates.<channel>.json`（不
    报错——尚未入仓是正常的中间状态，不是异常）。
    """
    d = _dir_for(label, repo)
    fz = d / "frozen"
    source_rows = read_jsonl(fz / "source.jsonl")
    src_jp = {r["id"]: r["jp"] for r in source_rows}

    cand_path = d / f"candidates.{channel}.jsonl"
    candidates = read_jsonl(cand_path) if cand_path.exists() else []

    # 同一 id 多条 → 取最后一条（见模块 docstring）。
    last_by_id = {}
    for row in candidates:
        last_by_id[row["id"]] = row
    ids = list(last_by_id.keys())

    stray = [i for i in ids if i not in src_jp]
    if stray:
        print(f"!! polish_check.gate: {label}/{channel} 的候选里有 "
              f"{len(stray)} 个 id 不在 frozen/source.jsonl 里（{sorted(stray)}），"
              "已跳过——正常的 polish_ingest 入仓流程不会产生这种候选，出现"
              "说明 candidates 文件与这份 frozen 快照不属于同一个 SEG",
              file=sys.stderr)
        ids = [i for i in ids if i in src_jp]

    # 关键一步：source_rows 按候选实际覆盖的 id 集裁剪，理由见模块 docstring
    # 顶部专节——不裁剪会让 check() 每次都只吐一条 R1 就放弃，是恒绿闸的一种
    # 形态。
    cropped_source = [{"id": i, "jp": src_jp[i]} for i in ids]
    draft_rows = [{"id": i, "zh": last_by_id[i]["zh"]} for i in ids]

    speakers = _load_speakers(fz)
    glossary_path = fz / "glossary" / "active.json"
    glossary = (json.loads(glossary_path.read_text(encoding="utf-8"))
                if glossary_path.exists() else None)

    # W4 本任务不跑，siblings 恒 None——见模块 docstring"W4 不在此跑"一节。
    result = check(cropped_source, draft_rows, speakers=speakers, glossary=glossary,
                    siblings=None)

    gates = {}
    for v in result["hard"]:
        gates.setdefault(v["id"], {"hard": [], "warn": []})["hard"].append(v)
    for v in result["warn"]:
        gates.setdefault(v["id"], {"hard": [], "warn": []})["warn"].append(v)

    d.mkdir(parents=True, exist_ok=True)
    # JSON 对象键只能是字符串，id 在这里是 int——落盘前显式转 str（与
    # tools/check_charlevel.py 的 per_id 输出同一约定），排序保证输出确定性；
    # gate() 的返回值本身仍是 int 键的字典，与仓库里其它按 id 建索引的字典
    # （如 check_batch.check() 内部的 src/drf）保持同一类型习惯。
    (d / f"gates.{channel}.json").write_text(
        dumps({str(k): v for k, v in sorted(gates.items())}), encoding="utf-8")
    return gates


def main(argv=None):
    ap = argparse.ArgumentParser(description="P4 保税仓机械闸：候选级复用 check_batch.check()")
    ap.add_argument("--seg", required=True, help="段表 label（如 seg1-s2）")
    ap.add_argument("--channel", required=True, help="执行通道（如 fable/deepseek）")
    ap.add_argument("--repo", default=None,
                     help="车道根目录（省略时用仓库根；测试用 tmp_path 传替身仓库）")
    args = ap.parse_args(argv)

    gates = gate(args.seg, args.channel, repo=args.repo)
    n_hard = sum(1 for v in gates.values() if v["hard"])
    n_warn = sum(1 for v in gates.values() if v["warn"] and not v["hard"])
    print(f"gate: {args.seg}/{args.channel} 有问题 {len(gates)} 个 id"
          f"（hard {n_hard}，仅 warn {n_warn}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
