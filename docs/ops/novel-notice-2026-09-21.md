# 文库（游戏内小说）中文说明：施工方案与措辞（2026-09-21）

> 起因：`png/novel/` 993 张竖排页图小说不烤字（用户 2026-08-30 裁定出范围）。玩家日后点进文库看到日文原图
> 会以为是漏译。用户 2026-09-21 要求在 lua 里第一次介绍 novel 模式的位置加几句解释，并就「标题界面进 novel
> 时要不要也提示」征求建议。本文是方案 + 措辞 + 落地记录；两层叠加文件已写好、过闸、模拟器目检通过，
> **措辞待用户复看后再提交**。

## 1. 原作在哪里介绍 novel 模式

只有一处：`snr_s1_10_f.lua` 的 `scene_s1f_complete`（章节 1 现实层读完）。流程：授卡 133 → 17002「片段模式：
章节１已完结」→ cutin `tut_0_a`/`tut_1_a`（「阅读游戏内小说时，请竖屏持握」）→ 17003–17011 一组九条
【■おしらせ】（阅览方法 / 操作方法 / 什么是游戏内小说 / 获得方法 / 与正篇的关系 / 随喜阅读）→ 淡出。
memory 模式重放 s1f 时 `if memoryFlag == true then run snr_memory` 早退，不进 complete 场景——这组通知一局只出现一次。
另有 crd_6 教程回顾 17060/17061 顺带提到 library 与游戏内小说（一句话，不动）。

文库本身（`snr_novel.lua`）是纯图片 UI，唯一的文字是空列表时的 `msg("まだ一冊も取得していません。")`。

## 2. 施工方案（已落地为两层，未提交）

| 层 | 目标 | 锚点 | 内容 |
|---|---|---|---|
| `layers/overlays/novel-notice-s1f.toml` | `snr_s1_10_f.lua` | `comEffectFadeOut(60)` + `l1_0()` + `end` + `main = function()` 四行连读（全文件唯一） | `insert_before`：原通知 17011 之后、淡出之前，追加 8 条【■汉化说明】（vms 17500–17507） |
| `layers/overlays/novel-notice-entry.toml` | `snr_novel.lua` | `systemConfig.unsetConfigButton()`（唯一） | `insert_before`：`if systemSave.novelNoticeSeen ~= true then` 两条提示（17510–17511）+ 置 true。位于「一本也没有」早退之后、`advPart(false)` 之前——原作在同一位置用 `msg()` 显示空列表提示，证明消息窗可用 |

- 说话人标签仿【■おしらせ】→【■通知】的定译，作**【■汉化说明】**：引擎把【】画成名牌，不占正文 25 格；
  与原通知同屏时一眼可分「哪句是游戏说的、哪句是中文版说的」。
- id：账本占 1..17220、谢幕章 17300–17481、卡消息 18001–18195；取 **17500–17507 / 17510–17511**，登记在
  `layers/vms_ids.toml`，`layers.py check` 的 `check_ids()` 硬拦越段与撞号。
- 一次性守卫用**新系统键** `systemSave.novelNoticeSeen`：旧系统数据没有这个键，读出 nil，`~= true` 即显示一次；
  `snr_novel.main()` 末尾原有 `autoSystemSave(0)` 把 true 写盘，不必另加保存。**刻意不改** `snr_common` 的
  systemSave 字面表——那个锚点已被 `finale-read-flag` 层改写，再叠一层会让两层耦合；nil 守卫已足够
  （`title-logo-zh` 层对 finaleReadFlag 也是这么做的）。老存档兼容：无迁移、无自愈需求（缺键＝未看过＝显示一次）。
- 字体：字集由 `layers.py` 从 release 最终源机械算出，新字自动进字集，`build_disc.py` 的 fonts 阶段重生成即可。
- 不动 EBOOT、不烤图、不进 storyRoute、不进存档 gameSave。

## 3. 措辞（待复看）

约束：消息窗 4 行 × 25 格；沿用原通知的「・小标题_n_r正文」体例；系统口吻用书面语（style.md「UI 与系统文本」）。
全部经 `msg_layout_check` 模拟，最多 3 行、零告警。

### 3.1 章节 1 读完，紧接原通知（8 条）

| id | 文本 | 行 |
|---|---|---|
| 17500 | 【■汉化说明】关于游戏内小说，中文版另有几句话要向您说明。 | 1 |
| 17501 | 【■汉化说明】・未作翻译_n_r本中文版没有翻译游戏内小说。文库里的五本小说，仍是日文原版的页面。 | 3 |
| 17502 | 【■汉化说明】・原因之一_n_r这几部作品在中文社区早有网友倾注心力译出的版本，质量与水准都很好。 | 3 |
| 17503 | 【■汉化说明】我们不希望再造成版本的分裂，却也没有精力一一联络原译者取得授权。 | 2 |
| 17504 | 【■汉化说明】・原因之二_n_r游戏内小说需要把主机竖过来阅读，而我们预想多数初次接触本作的玩家会在电脑上用模拟器游玩。 | 3 |
| 17505 | 【■汉化说明】对这样的游玩环境来说，这种阅读形式本身就不算合适。 | 2 |
| 17506 | 【■汉化说明】・建议_n_r欢迎自行检索中文社区流传的译本来阅读；也欢迎日后学会日语之后，再回来重温这个故事。 | 3 |
| 17507 | 【■汉化说明】游戏正篇的推进不受任何影响。以上，感谢您的理解。 | 1 |

拆句原则：一条一个意思；原因二若合成一条正好 4 行（引擎上限、第 5 行起不画），故拆成两条。
可议之处：①「版本的分裂」是用户原话，也可作「重复劳动」或「多一个版本」；②「学会日语」vs「学习日语」；
③ 17500 开场句可删，直接从 17501 起——删掉后 7 条。

### 3.2 文库入口，只第一次（2 条）

| id | 文本 | 行 |
|---|---|---|
| 17510 | 【■汉化说明】游戏内小说未作翻译，以下为日文原版页面。 | 1 |
| 17511 | 【■汉化说明】中文社区早有网友译出的版本，欢迎自行检索阅读；也欢迎学会日语后再来重温。 | 2 |

两句自足，不引用章节 1 的通知（那组通知不可重看）。

## 4. 「标题界面进 novel 时要不要提示」——建议：要，但只第一次，两句

| 选项 | 评价 |
|---|---|
| 不提示 | 章节 1 那组通知一局只出一次、不可重看；读别人存档／连点跳过的玩家第一次点进文库看到日文页面，正是最容易以为漏译的时刻，而那时没有任何文字 |
| 每次提示 | 常客会烦；文库本来就是反复进出的地方 |
| **只第一次（推荐，已落地）** | 系统键守卫，机制与 finaleReadFlag 同款、已在实机路径验证过；代价是两条 vms 与一个新系统键，零迁移 |
| 只在空列表时提示 | 空列表时玩家根本看不到日文页面，说明放错了地方 |

若用户不要入口提示：删 `novel-notice-entry.toml`、`manifest.toml` order 里的名字与 `vms_ids.toml` 的登记即可，
s1f 层独立成立。

## 5. 验证

- `layers.py check --profile release`：7 层全部命中，msg-layout 17079 条、错误 0（原 17069 + 新 10 条）。
- `tests/test_layers_corpus.py`：新增 `test_novel_notice_ids_are_inside_declared_range`（两层参数化）与
  `test_novel_notice_lands_where_intended`（装配后的最终源里两块落在预期位置、守卫存在）。
- **模拟器目检（PPSSPP，已做）**：
  - 入口：`build_disc.py --profile test --mode mainmenu` → `tools/emu/drives/novel_notice.py`。第一次进 novel 先出两条
    【■汉化说明】（黑底 + 消息窗，与原作空列表提示同一形态），关掉后进浏览画面；退回主菜单再进，直接是浏览画面，
    不再提示——`novelNoticeSeen` 经退出时的 autoSystemSave 落盘生效。截图 `build/emu/drives/novel_notice/`。
  - s1f 块：`build_disc.py --profile test --mode scene --scene s1f-complete` → `tools/emu/drives/novel_notice_s1f.py`
    （每按一次 CIRCLE 截一帧）。授卡 → 17002 → cutin → 原通知九条 → **八条汉化说明依次出现（帧 18–29）** → 淡出回标题。
    名牌「■汉化说明」与「■通知」同位同形；正文最多 3 行；截图 `build/emu/drives/novel_notice_s1f/`。
  - ERROR 日志只有基线的 `ILLEGAL_THID=sceKernelWaitThreadEnd(0)` 一条（历次探针皆有，与本改动无关）。
- **顺手抓到并已修的管线坑**（`39e27cb`）：第一轮 test 盘上「译」画成了下划线——`stage_font` 只从 release 的
  lua/final 算字集，那棵树是上一次 release 构建留下的、不含新层。现在字集取本剖面 final ∪ release final。
  「译」是本次新增的唯一新字（字集 3390 → 3391）。

## 6. 落地清单（提交时）

- `layers/overlays/novel-notice-s1f.toml`、`layers/overlays/novel-notice-entry.toml`（新）
- `layers/manifest.toml`：`[overlays].order` 加两层（在 `title-logo-zh` 之后、`strip-ipl` 之前）
- `layers/vms_ids.toml`：两条 `[[ranges]]`
- `tests/test_layers_corpus.py`：两条测试
- `docs/ops/disc-pipeline.md` §「加一个新层的完整走查」：把「尚未实施」改为指向本文
- `CLAUDE.md` 文件构成表 layers 行 / 已知坑：一句话登记
- 记忆 `novel-menu-notice-todo` → 已完成
