# 卡 93『アヤノの返信：９月２５日』末句「あったね」改译——解读、裁定与落地（2026-09-23）

> 起因：用户 2026-09-22 对卡 93 卡面译文「Yuichi来探病的那天，真的有过呢！」存疑，
> 并指出原文「ユウイチがお見舞いに来た日、あったね！」本身也不是常见说法，问应作何解。
> 解读见 §一；用户 2026-09-23 采纳「对了对了，Yuichi来探病的那天，还记得吧！」。
> 按 CLAUDE.md「骨架改动须走新 glossary 版本 + 召回令」走 **glossary v25 + skeleton 召回
> （tag skeleton-v6）**。先例：v23（skeleton-v5，`382e259`，同样只动卡 93 body）。
>
> 状态：**已落地**（skeleton 两文件 + glossary v25 + 卡图重烤 + release 出盘）。

## 一、原文怎么读

卡 93 是 s5s_806「アヤノの返信：９月２５日」的梗概，写成 Ayano 给 Sakura 回信的开头：

> サクラちゃん、元気？ そうそう、ユウイチがお見舞いに来た日、あったね！

「〜日、あったね！」是口语里省掉「が」的「〜日があったね」，功能是**唤起两人共有的记忆**
（「そんなこともあったね」同型），然后正文开始讲那天的事。「ね」求的是对方的共同回忆，
不是在确认此事发生过。旧译「真的有过呢」把语气推成辩白式强调，反而暗示探病的真实性有疑问，
而游戏里有疑问的从来不是探病是否发生，而是**来的人是谁**。

剧情链条（读 `analysis/text_digest/snr_s5_10_s.txt`、`snr_s7_10_f.txt` 即可复核）：

| 日期 / 场景 | 事实 |
|---|---|
| 9/16 Sakura 日记（s5s_260） | 真 Yuichi 唯一一次探病就在这天。同一天甜甜圈青年（＝直哉）在中庭遇到 Sakura；Ayano 跑来问「刚才 Yuichi 是不是来过这边」，Sakura 从此把甜甜圈青年当成 Yuichi。Sakura 自己写「今日は色々と忙しい日だ」 |
| 9/25 Ayano 回信（s5s_806） | 讲的是真 Yuichi 坐立不安、怕医院、从小怕打针的那次探病。开头有人说了「あとは二人で」然后离开——对应 s7f 真相就是直哉来探病撞见 Yuichi，识趣退出 |
| 9/29 Sakura 日记（s5s_550） | 她看着天天来的甜甜圈青年嘀咕「ユウイチさん、病院、苦手なのに……」。这条知识只能来自 9/25 的回信，误认在这里焊死 |
| s7f_520 直哉推理 | 「ユウイチは病院が苦手だった。そしてユウイチが彩野さんにお見舞いに行ったのは、彩野さんが入院した時の一度きりだけだった」 |

所以「あったね」还带着「有过那么一天」的单次感，本身也是给玩家的线索。

## 二、裁定

| 候选 | 说明 | 结果 |
|---|---|---|
| 「对了对了，Yuichi来探病的那天，还记得吧！」 | 把「ね」的共有记忆语气明写出来；「记得」是原文没有的词 | **采纳**（用户 2026-09-23） |
| 「对了对了，有过Yuichi来探病的那么一天呢！」 | 更贴「あった」的字面，保留「只有那么一次」的线索感 | 备选，未采 |
| 「对了对了，Yuichi来探病的那天，真的有过呢！」 | 旧译；「真的」把语气推成辩白式确认 | 废止 |

两个候选都经 `bake_card.plan_body` 复核为 3 行、无超宽无截断。

## 三、载体与落点

| 载体 | 处置 |
|---|---|
| `skeleton/cards.zh.yaml`、`skeleton/cards.zh/batch_02.yaml` 卡 93 `body_zh` | 改为「Sakura酱，最近好吗？／对了对了，Yuichi来／探病的那天，还记得吧！」；yaml 换行按 v21 口径写成与烤字输出相同（`zh_wrap` DP 词边界优先 + 行长均衡，断在「来／探病」）；`tr_note` 沿惯例保留历史原文，只在其后加 `〔v25 …〕` |
| `glossary/glossary.v25.yaml` | 新版（append-only），记解读、证据、备选与召回范围；`active.json` **无变化**（句级改译，不是术语映射） |
| 主轨 / extra 轨 | **不涉**：该句只在卡面，vms 无同文；卡 93 只派生 `title_zh`，标题未动 |
| plot / scene / select 面 | **不涉**：同源于 `title_zh` |
| 攻略 `guide/` | **不涉**：`build_guide` 只取 `title_zh` |
| 谢幕章 | **不涉** |
| 图 | `png/card/crd_93_a` 重烤（`build/card_zh/`，不入库），已目检：三行清晰，断行「Yuichi来／探病的那天」 |
| 盘 | `build_disc.py --profile release --stage all` 重跑到 iso（`build/dist/game_zh.iso`，不入库） |
| `pilot/lanes/opus/skeleton/`、`.claude/worktrees/*/skeleton/` | **不动**：车道建立时的冻结快照，v23 起历次召回也未同步 |

## 四、验证结论

- `check_skeleton` 五批 + 合并版 **OK**。
- `bake_card` 196 卡：validation gate max_diff 52 / 阈值 60，超阈 0；溢出 0；像素保全违例 0
  （与 v23 落地时同值）；卡 93 目检通过。
- `layers.py check --profile release` rc=0：9 层全部命中、eboot 23 条锚点命中、sound 1 首核对；
  `msg-layout` 错误 0、警告 32（与改前同一集合，卡面文本不经消息窗）。
- `pytest` 全量 **1990 passed, 4 skipped**（7 分 05 秒，rc=0）。
- `build_disc.py --profile release --stage all` rc=0：members 阶段 gim 591 张（1 新编码＝卡 93，590 缓存命中）；
  iso 五道断言全过，写出 `build/dist/game_zh.iso`（645982208 B）；盘上 `card/crd_93_a.gim` 经 `gimcodec decode`
  回读目检，与烤字 PNG 一致。
- ⚠ **members 阶段的「超阈(15.0) 1 张：crd_93_a MSE 20.26」不是本次改字造成的**，是这族卡面本来的量化损耗：
  用 `build_disc._encode_gim_cached` 就地复测，改前的卡 93（「真的有过呢」）MSE 20.27，同族卡 191／92／1／178 为
  20.24／20.44／19.46／19.88。全量重烤时它们淹没在 196 张里不显眼；单独重烤一张时它就成了榜首。
  **以后任何只动一张卡的召回都会看到这条告警，属预期。**

## 五、执行台账

| 步骤 | 规模 | commit |
|---|---|---|
| glossary v25 + skeleton 召回（卡 93 body）+ tag `skeleton-v6` | 3 文件 | 见 git log |
| 本文 + `docs/ops/bake-progress.md` 追记 | 2 文件 | 见 git log |
| 图片重烤 `build/card_zh` + release 出盘（不入库） | 196 卡 / 1 盘 | — |
