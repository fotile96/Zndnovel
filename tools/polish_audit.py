"""P4 润色 pass：抽检推翻率闸——自动清关这条免检通道**唯一**的事后反馈回路。

## 这个工具存在的理由（最终评审 I7）

spec §5 写明："10% 随机抽检混入裁决会话（占 K 额度）；单通道抽检推翻率 >20%
→ 冻结该通道本 SEG 自动清关权，存量自动清关 patch 全部回滚复审。" 落地时这条
闸**只写进了 runbook，没有任何代码**——runbook §十二自陈"这条闸没有专属 CLI，
由裁决会话人工执行"。

问题不在于"人做不到"，在于：

1. 自动清关是整条流水线上唯一无人值守的写入路径，抽检是它唯一的兜底，而
   **推翻率闸是抽检唯一的出口**——抽了、发现不对，然后呢？没有代码就没有然后。
2. `polish_triage` 已经会主动压缩抽检覆盖率（`sample_cap`，Task 7 评审修复：
   宁可降覆盖率也不突破人工预算 K）。SEG-1 规模下配置的 10% 实际会掉到 6% 上下。
   覆盖率本来就在打折，出口再靠人记，等于没有闭环。
3. "人工执行"的闸在本项目的历史里从来不响——CLAUDE.md 记的两次事故都是
   "本该有人记得的一步没人记得"。

## 判据：什么算"这条抽检样本被推翻了"

抽检样本 = `triage.json` 里 `autoclear=True and sampled=True` 的行（`polish_
commit` 对这些行**不**直接清关，它们被塞回 `queue.md` 让人当普通候选审）。
对样本行 `(id, channel)`，看 `decisions.jsonl` 里该 id 的**最后一条**人裁
（`verdict ∈ {adopt, edit, keep_opus}`，`auto` 不算——那是工具自己铸造的记录，
不是人的判断）：

| 人裁结果 | 对该 channel 算不算推翻 | 理由 |
|---|---|---|
| `adopt` 且 `chosen_channel == channel` | **不算** | 人看过之后确认这份候选可以原样入库——自动清关当初的判断是对的 |
| `adopt` 且 `chosen_channel != channel` | **算** | 人否掉了本通道的候选、改用别家的，本通道那一行如果没被抽中就会被原样自动清关进库 |
| `edit` | **算** | 人认为候选还得改——自动清关会把一个需要人改的稿子直接入库 |
| `keep_opus` | **算** | 人认为根本不该动——自动清关会写一条本不该存在的 patch |
| 尚无人裁 | 不计入分母 | 裁决还没做完，既不能算推翻也不能算通过；**单独播报待裁数**，避免"分母太小导致率虚低"被无声吞掉 |

`rate = 推翻数 / (推翻数 + 通过数)`。`rate >= CFG["overturn_freeze"]` → 冻结。

**边界取 `>=` 而不是 `>`**：`config/polish.yaml` 里这一行的注释本身写的就是
"≥ 此值 → 冻结"（spec §5 散文写的是 ">20%"）。两者只在恰好等于 0.20 时有别，
取 `>=` 是把边界向安全侧靠——闸在临界点上宁可响。

## 冻结动作与"不能被悄悄解冻"

命中即改写 `channel_state.json`：该通道 `autoclear` 置 `False`，并**保留原有
其它键**、另记三个审计字段：

```json
{"fable-wf": {"autoclear": false, "autoclear_frozen_by": "overturn",
              "overturn_rate": 0.33, "frozen_ts": "…"}}
```

`autoclear_frozen_by` 不是装饰：`polish_calibrate.score()` 每次判卷都会重写
该通道的条目，如果它照旧整条覆盖，一次"重跑准入小考"就能把本闸刚落的冻结
**悄悄**解掉。故 `polish_calibrate.score()` 已配套改成"看到 `autoclear_frozen_
by` 就不予重开、并显著播报"（见那边的 docstring）。

## 存量回滚不在本工具里（有意）

spec 还写了"存量自动清关 patch 全部回滚复审"。回滚要写生产车道
`patches.jsonl`，而**本项目只允许 `polish_commit --apply` / `add_patch.py`
两个入口写它**（2026-08-02 事故的防线）。本工具因此只做"关权 + 把需要复审的
patch 逐条列出来（按 `prov.channel` 精确定位）"，回滚由人按 runbook §十二 用
`add_patch.py` 落 `reason=review` 覆盖 patch 执行——工具不发明第三条写入路径。
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, dumps, read_jsonl
from tools.polishlib import CFG

HUMAN_VERDICTS = ("adopt", "edit", "keep_opus")


def _dir_for(label, repo) -> Path:
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def _last_human_decision(decisions) -> dict:
    """`{id: 最后一条人裁记录}`——append-only 文件里"后来者为现行"，与
    `resolve.resolve_map` / `polish_check.gate()` 同一约定。`verdict="auto"`
    是工具自己铸造的记录，不是人的判断，不参与。"""
    out = {}
    for dec in decisions:
        if dec.get("verdict") in HUMAN_VERDICTS:
            out[dec.get("id")] = dec
    return out


def audit(label, repo=None, apply=True, ts=None) -> dict:
    """算各通道的抽检推翻率；超线即关闭该通道自动清关权（`apply=False` 只报不改）。

    返回 `{channel: {"sampled": n, "decided": n, "overturned": n, "pending": n,
    "rate": float|None, "frozen": bool, "rollback_ids": [...]}}`。
    """
    d = _dir_for(label, repo)
    triage_path = d / "triage.json"
    if not triage_path.exists():
        raise FileNotFoundError(
            f"{triage_path} 不存在——推翻率闸的输入是 triage 的抽检结果，"
            "先跑 polish_triage.py")
    triage = json.loads(triage_path.read_text(encoding="utf-8"))

    dec_path = d / "decisions.jsonl"
    decisions = read_jsonl(dec_path) if dec_path.exists() else []
    last_human = _last_human_decision(decisions)

    stats = {}
    for r in triage.get("rows", []):
        if not (r.get("autoclear") and r.get("sampled")):
            continue
        ch = r.get("channel")
        s = stats.setdefault(ch, {"sampled": 0, "decided": 0, "overturned": 0,
                                   "pending": 0, "pending_ids": [],
                                   "overturned_ids": []})
        s["sampled"] += 1
        dec = last_human.get(r["id"])
        if dec is None:
            s["pending"] += 1
            s["pending_ids"].append(r["id"])
            continue
        s["decided"] += 1
        upheld = (dec.get("verdict") == "adopt"
                  and dec.get("chosen_channel") == ch)
        if not upheld:
            s["overturned"] += 1
            s["overturned_ids"].append(r["id"])

    limit = CFG["overturn_freeze"]
    state_path = d / "channel_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    now = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")

    changed = False
    for ch in sorted(stats):
        s = stats[ch]
        s["rate"] = (s["overturned"] / s["decided"]) if s["decided"] else None
        s["frozen"] = s["rate"] is not None and s["rate"] >= limit
        s["rollback_ids"] = _autocleared_ids(triage, ch) if s["frozen"] else []
        if s["pending"]:
            print(f"!! polish_audit: {label}/{ch} 有 {s['pending']} 条抽检样本尚未裁决"
                  f"（id {sorted(s['pending_ids'])}）——它们不进分母，本次推翻率是在 "
                  f"{s['decided']} 条已裁样本上算的。裁决没做完就下结论会让率虚高或虚低。",
                  file=sys.stderr)
        if s["decided"] == 0:
            print(f"!! polish_audit: {label}/{ch} 没有任何**已裁决**的抽检样本，"
                  "推翻率无从计算——本次不对该通道做任何判定（既不冻结也不背书）。",
                  file=sys.stderr)
            continue
        if not s["frozen"]:
            continue
        print(f"!! polish_audit: {label}/{ch} 抽检推翻率 {s['rate']:.1%} "
              f"（{s['overturned']}/{s['decided']}，被推翻的 id "
              f"{sorted(s['overturned_ids'])}）**已达/超过冻结线 {limit:.0%}**"
              f"\n   → 该通道本 SEG 自动清关权立即关闭。"
              f"\n   → 存量需回滚复审的自动清关 patch（prov.channel={ch}）共 "
              f"{len(s['rollback_ids'])} 条：{s['rollback_ids']}"
              f"\n   → 回滚不在本工具里做（生产 patches.jsonl 只经 polish_commit "
              "--apply / add_patch.py 写入）：按 runbook §十二 逐条用 add_patch.py "
              "落 reason=review 覆盖 patch。", file=sys.stderr)
        if apply:
            entry = dict(state.get(ch) or {})
            entry.update({"autoclear": False, "autoclear_frozen_by": "overturn",
                          "overturn_rate": s["rate"], "frozen_ts": now})
            state[ch] = entry
            changed = True

    if apply and changed:
        state_path.write_text(dumps(state), encoding="utf-8")

    for s in stats.values():
        s.pop("pending_ids", None)
    return stats


def _autocleared_ids(triage, channel) -> list:
    """该通道真正被自动清关掉（`autoclear and not sampled`——`polish_commit`
    只对这一类直接落 patch）的 id，供人按 `prov.channel` 逐条回滚复审。"""
    return sorted(r["id"] for r in triage.get("rows", [])
                  if r.get("channel") == channel
                  and r.get("autoclear") and not r.get("sampled"))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="P4 抽检推翻率闸：超线即关闭该通道本 SEG 自动清关权")
    ap.add_argument("--seg", required=True, help="段表 label（如 seg1-s2）")
    ap.add_argument("--dry-run", action="store_true",
                     help="只报不改（默认会真的改写 channel_state.json——关权是安全"
                          "方向的动作，不该需要额外开关才肯生效）")
    ap.add_argument("--repo", default=None,
                     help="车道根目录（省略时用仓库根；测试用 tmp_path 传替身仓库）")
    args = ap.parse_args(argv)

    stats = audit(args.seg, repo=args.repo, apply=not args.dry_run)
    if not stats:
        print(f"polish_audit: {args.seg} 本轮没有任何抽检样本"
              "（triage.json 里没有 autoclear+sampled 的行）")
        return 0
    for ch in sorted(stats):
        s = stats[ch]
        rate = "N/A" if s["rate"] is None else f"{s['rate']:.1%}"
        print(f"polish_audit: {args.seg}/{ch} 抽检 {s['sampled']} 条"
              f"（已裁 {s['decided']}，待裁 {s['pending']}），推翻 {s['overturned']} 条，"
              f"推翻率 {rate}，冻结线 {CFG['overturn_freeze']:.0%} → "
              f"{'已冻结自动清关权' if s['frozen'] else '维持现状'}"
              f"{'（--dry-run，未写盘）' if s['frozen'] and args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
