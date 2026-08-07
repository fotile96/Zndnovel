# P4 润色 pass — SEG-0（`seg0-s0-s1`，b1–35）点火 handoff

> runbook：`docs/ops/p4-polish-runbook.md`（流程语义以它为准，本文只管本段的具体安排）。
> 前一段的 handoff：`docs/ops/p4-seg1-polish-handoff.md`——**其中「通道二 ds-flash」的三条
> paseo 实操教训、提示词骨架、并行安全条款本段完全适用，不在这里重复，去读那一份。**

## 这一段为什么现在才跑

段表（`config/segments.yaml`）是 P3 建的，只切「余下 304 批（b36–339）」——**b1–35 属于更早的
P2 试点批次**，建表时已译完，从没进过段表；P4 直接沿用这张表，就把开头整块漏了。
2026-08-07 用户发现并裁定补上，段号取 `seg: 0`（label `seg0-s0-s1`），其余 9 段的 `seg` 与
label 全部不动。已有测试 `test_seg_field_matches_label_prefix_number` 钉死 seg 序与 label 前缀序一致。

## 规模：全项目最大的一段

| | SEG-0 | SEG-1（已完成，作参照） |
|---|---|---|
| 批 | 35（b1–35） | 27 |
| 行 | **4282** | 1992 |
| jp 字 | **116,282** | 53,183 |
| 会话组 | **9** | 4 |
| 硬锁（已有人裁 patch） | 6 | 4 |
| **软锁（anchors 锚点）** | **33** | 4 |

章别构成：`s1s 1433 / crd 1414 / s1f 652 / s0f 568 / s2s 172 / sys 43` 行。

⚠ **`sys` 那两批（b5=13 行、b18=30 行）不是 UI 文本**，别按系统字符串处理——实测内容是
现实层过场旁白（「彩野同学的『记忆』，似乎已经中断了」）与探索场景里彩野的到场语音
（【アヤノ】「到教室了哦」）。`sys` 只是「这些行住在 `snr_common.lua` 共享脚本里」的章别代号，
文本性质就是正文对白与旁白，**六条母语感细则完全适用，整段一起跑**。

## 会话分组（已渲染，不要重渲染）

`plan.json` 已记录各 session 的 `prompt_hash`；prompt 已落在 `work/ctx/`。**无故重渲染会刷新
哈希，已入仓候选的倒查链会悬空。**

| session | 批 | 行 | prompt |
|---|---|---|---|
| 1 | b1–3 | 569 | `work/ctx/p4s0-s1.md` |
| 2 | b4–9 | 508 | `work/ctx/p4s0-s2.md` |
| 3 | b10–14 | 598 | `work/ctx/p4s0-s3.md` |
| 4 | b15–18 | 433 | `work/ctx/p4s0-s4.md` |
| 5 | b19–24 | 525 | `work/ctx/p4s0-s5.md` |
| 6 | b25–26 | 318 | `work/ctx/p4s0-s6.md` |
| 7 | b27–28 | 449 | `work/ctx/p4s0-s7.md` |
| 8 | b29 | 311 | `work/ctx/p4s0-s8.md` |
| 9 | b30–35 | 571 | `work/ctx/p4s0-s9.md` |

两条通道 = **18 次派发**。prompt 单份 770–830KB（比 SEG-1 略大），派发前确认执行通道的
上下文窗口吃得下。

## K = 700（2026-08-07 用户裁定）

`config/polish.yaml` 已由 500 改为 700。依据：按 SEG-1 实测待裁率 11.7%（1992 行 → 233 个 id）
外推本段约 500 个 id，加 33 条软锁强制项，700 留余量。

**建议按会话组拆两次裁决**（s1–s5 一次约 2633 行、s6–s9 一次约 1649 行），不要攒到段末一次看
500+ 条——SEG-1 那次 233 条已接近单次可持续的上限。拆开的做法：跑完前五个会话就 ingest →
check → triage 一轮先裁，再跑后四个会话第二轮。`polish_triage` 每次跨全部已入仓通道重新分流，
第二轮会把第一轮已裁的 id 照常带出来——裁决时按 `decisions.jsonl` 里已有的 id 跳过即可
（`polish_commit` 的幂等键是 `(id, decision_ts)`，重复清关是 no-op）。

## ⚠ 本段最需要小心的：软锁锚点的跨段伙伴行

33 条软锁里有 **8 条在后续段存在同 jp 的伙伴行**。这是 SEG-1 那两处 W4 漏网
（9546↔13448、9862↔12058，伙伴行在冻结面外、两通道都无从知晓）的**放大版**，而且这次涉及的
是全书的镜像结构——序章 `sof_20` 与 `s7f_10` 整段互为镜像重演。

| 本段 id | 段外伙伴 | 伙伴所在段 | 原文 |
|---|---|---|---|
| 6070 | 15798 | seg5-s6-s7f | 『じゃあね』と彼女は言って、立ち上がり…部屋から出て行った |
| 6085 | 15804 | seg5-s6-s7f | あのとき彼女の腕をつかんでいたらどうなっていたんだろう |
| 6093 | 15174 | seg4-s3tail-s5 | 微笑むことができたのかはわからない。…目を合わすことがまだ、できない |
| 6099 | 15818 | seg5-s6-s7f | そんな風にしてあれから５年が経ったんだ。…何も変わってないと思うんだ |
| 6102 | 15820 | seg5-s6-s7f | 【彩野】「もしその彼女が『あなたの場所』に帰ってきて…今度はしっかりと腕を掴…」 |
| 6104 | 15822 | seg5-s6-s7f | 【彩野】「忘れないで」 |
| 6107 | **5341, 15823** | seg5-s6-s7f, **seg7-e2** | 【直哉】「忘れないよ」 |
| 6111 | 15827 | seg5-s6-s7f | 【彩野】「ねえ、この事、前に聞いた？」 |

**裁决时对这 8 条的处置纪律：**

1. 这些行**都已有 `skeleton/anchors.yaml` 的逐字定译**，且伙伴行按 `style.md` 必须与之逐字一致。
2. 通道若对其中任何一条提出改动（软锁规则要求它必须带 `adjudicate=true`），**采纳前必须想清楚
   伙伴行怎么办**——伙伴行不在本段冻结面里，本段清关不会碰它，于是采纳即制造跨段不一致。
3. 三条出路，按情况选：
   - **保留原译**（最省事，且锚点本就是定译）；
   - **采纳 + 同步改伙伴行**——照 SEG-1 的先例落一条跨 SEG 的 `reason=review` patch。SEG-1 那次
     用户明示裁定过一次，commit 里写明「是明示裁定的例外，不是先例」，所以这条路**每次都要单独裁**；
   - **采纳但推迟**——记进 `decisions.jsonl` 时用 `keep_opus` + `note` 说明「建议改，待全部 SEG
     跑完后连同伙伴行一并处理」，把改动留到能一次看全所有伙伴行的时候。
4. **清关后必跑全段 W4 复检**（见 runbook §十一）。它是这类漏网的事后兜底，SEG-1 首次实战就抓到
   2 处——本段锚点密度是 SEG-1 的 8 倍，这道闸这次更要紧。

其余 25 条软锁没有段外伙伴，按软锁常规规则处理即可（不改就照抄、改了必 `adjudicate=true`、
永不自动清关、无条件进裁决队列不被 K 挤出）。

## 准入小考：跑不跑都行，默认是安全的

`pilot/polish/seg0-s0-s1/channel_state.json` **尚不存在** → `polish_triage` 对两条通道一律按
「自动清关权关闭」处理（保守缺省）。也就是说**不跑小考，本段就是全量人裁**，与 SEG-1 的实际
形态完全相同，没有任何风险。

想跑的话校准批与 prompt 已备：
- `pilot/polish/seg0-s0-s1/calib/seg0-s0-s1.batch.jsonl`（20 句）
- `work/ctx/p4s0-calib.md`

```bash
uv run python tools/polish_calibrate.py --seg seg0-s0-s1 --score --channel <ch> \
    --raw pilot/polish/seg0-s0-s1/calib/raw.<ch>.jsonl
```

参考：SEG-1 两条通道**都没通过**（判据是「改了人裁定稿却没显式请裁」，阈值 0.10）。本段锚点密度
高得多，通过的可能性不会更大。**若只是想开免检通道，收益预期不高；若是想拿一份「这条通道会不会
误伤既有裁决」的实测读数，那仍然值得跑。**

## 润色契约本轮的两处新增（点火会话应知道）

`glossary/polish.md` 于 2026-08-07 追加两节，已随本段冻结面进入全部 prompt：

- **§0「抓出错译」**——优先级压过原六条。要求执行通道主动对着日文过一遍意思，重点是
  `はいはい`／`わからない`／`きく` 这类**单看中文完全通顺、错了也看不出来**的取义分岔；
  发现后一律 `adjudicate=true` + `note` 写依据，不自行改掉了事。
  SEG-1 有实测支撑：`#8778` 是那一段唯一一条真错译，正是由通道主动请裁报出的。
- **§5(d)「判断单位是上下文，不是单行」**——「首次用名字、其后用代词」的「首次」指这一段
  对话里的首次。本段 `s0f`/`s1s` 是全书人名呼唤最密集的部分（初次见面、自我介绍、反复确认
  名字写法），这一条在本段的适用面比任何一段都大。

## 起手命令

```bash
cd /Users/fotile96/Zndnovel
uv run python tools/polish_setup.py --verify seg0-s0-s1     # 应输出「冻结校验：无漂移」
git status --short pilot/lanes/opus/data/                    # 应为空
uv run python tools/polish_context.py --seg seg0-s0-s1 --plan
```

然后按 `docs/ops/p4-seg1-polish-handoff.md` 的「通道一/通道二」派发形态发 session 1 的两条通道，
raw 落**绝对路径**：

```
/Users/fotile96/Zndnovel/pilot/polish/seg0-s0-s1/raw/fable-wf/b<批号>.out
/Users/fotile96/Zndnovel/pilot/polish/seg0-s0-s1/raw/ds-flash/b<批号>.out
```

派发后**必须自己确认产物落盘**（`wc -l`）——paseo 的 workspace 不可跨会话复用，复用会
`WORKSPACE_NOT_FOUND` 但退出码仍是 0，静默零产出。详见 SEG-1 handoff 通道二那三条教训。

## 段末流程

回指 runbook：ingest → **必须重跑 check** → triage → 裁决（append `decisions.jsonl`，
每条带 `reason_code`）→ `polish_audit` → amplify（本段是否跑由你定；SEG-1 主动放弃并记了理由）
→ `polish_commit` 先 dry-run 核对倒查链再 `--apply --data-dir pilot/lanes/opus/data`
→ 清关后必跑全段 W4 复检 + `check_qa_quotes`。

`check_qa_quotes` 现在带抑制清单（`config/qa_quote_suppressions.yaml`）：豁免项仍会列出、
只是不计退出码；**新增豁免必须写理由**，粒度精确到 `(题库, id, 片段)`。
