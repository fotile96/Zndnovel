# extra 轨 829 条落盘——实现与验收报告

任务：把 extra 轨（`pilot/lanes/opus/data/ledger_extra.jsonl`，829 行，键为字符串
`"<file>:<line>[:idx]"`）的中文**落盘为生产数据**，并把本轮临时脚本里用过的四条派生
规则补进 `tools/derive_extra.py`，使整条链路可重跑，不再依赖任何一次性手工脚本。

## 产物清单

- `tools/derive_extra.py`（扩写）——新增 `card_msg` 的模板 + 槽位解析（原来恒
  `confidence=none`，现在能解出 172/172）。
- `tools/land_extra.py`（新增）——落盘工具：机械派生 + 人工裁定译文 → 校验 → 追加。
- `data/extra_translated.jsonl`（新增，入库）——243 条去重模型译文（fable 复核 +
  用户逐条裁定的最终稿），从 `build/extra_translated.jsonl` 原样搬入。
- `pilot/lanes/opus/data/forward_extra.jsonl`（新增，入库，829 行）——本次真正落盘
  的生产数据。
- `tests/test_derive_extra.py`（扩写，+24 用例）、`tests/test_land_extra.py`
  （新增，16 用例）。
- `.gitignore`（改 1 行）——`pilot/lanes/*/data/*` 忽略规则下补一条
  `!pilot/lanes/*/data/forward_extra.jsonl` 否定项（与既有 `forward.jsonl`/
  `patches.jsonl` 两条同款式），否则新文件会被静默忽略、`git status` 看不到它。

## 一、forward_extra.jsonl 的 schema 与理由

```json
{"key": "snr_crd_100:35", "kind": "card_msg", "zh": "已写下『选择：在哪里读』的选项（在图书室读）。",
 "source": "template:『…』の選択肢（…）を作成しました。 + cards.zh:card=100 + cards.zh:card=102",
 "glossary_v": 14, "ts": "2026-08-08T16:43:39+00:00"}
```

字段设计：
- `key`（主键，字符串）：与 `ledger_extra.jsonl` 的 key 一一对应，这是全部校验的锚点。
- `kind`：冗余自 ledger（`plot_title`/`scene_title`/`card_msg`/`savedata`），下游按
  kind 分流时不必回查 ledger；轻量冗余换查询方便，向 `forward.jsonl` 的既有习惯
  （它也不强求"最省字段"）看齐。
- `zh`：译文，**空串是合法值**（3 条 savedata）。
- `source`：任务要求"精确到能倒查"，本工具用四种前缀区分来源：
  - `cards.zh:card=N[|M（同名多卡，zh 一致）]` —— 精确匹配冻结卡名。
  - `template:<模板骨架> + cards.zh:card=N[ + cards.zh:card=M / ruling:选项文本]`
    —— card_msg 的模板拼装，槽位来源逐个列出。
  - `rule:セクション→章节` —— 章节代号兜底规则命中。
  - `model+review:data/extra_translated.jsonl` —— 人工裁定译文（非空）。
  - `reviewed-empty:data/extra_translated.jsonl（style.md v14：…不译，原样留空）`
    —— 人工裁定译文（合法空串），与"没查到"在字面上就能区分开，不会被误读成缺失。
- `glossary_v`：落盘时点 `tools/build_context.glossary_version(REPO)` 的动态扫描结果
  （当前 14；CLAUDE.md 文中仍写 v6，那是文档滞后，代码不依赖文档里的旧数字）。
- `ts`：单次落盘运行统一的 UTC 时间戳（`datetime.now(timezone.utc).isoformat(timespec="seconds")`），
  与 `tools/append_forward.py` 的既有写法一致。

未采用 `id`（`forward.jsonl` 的主键名）：用户已裁定 extra 轨主键叫 `key`（字符串），
沿用同名会误导读者以为两个文件同构、可以互相 `resolve_map`；未收 `jp`：`key→jp` 的
映射本来就在 `ledger_extra.jsonl` 里，`forward.jsonl` 也不重复存 `jp`，保持同一条
"单一事实来源"的既有约定。

## 二、243 条模型译文的入库位置与理由

放在 **`data/extra_translated.jsonl`**（新文件，与 `build/extra_translated.jsonl`
内容逐字节相同，`diff` 确认 `IDENTICAL`）。

候选地点排除过程：
- `pilot/lanes/opus/data/` ——硬约束明确只许新增 `forward_extra.jsonl`，此路不通。
- `glossary/`——目录语义是"版本化术语表 + 风格/口调表"（`glossary.vN.yaml`/
  `style.md`/`voices/`），243 条是一次性的场景标题/存档标题翻译裁定，不是术语条目，
  混进去会打乱该目录"只有这几类文件"的既有约定。
- `data/`——目录里已有 `ledger.jsonl`/`ledger_extra.jsonl`/`batches.jsonl`/
  `dag.json`/`timeline.jsonl`/`scene2card.json`，全部是 `tools/build_*.py` 的
  可重生产物；`extra_translated.jsonl` 是例外（人工裁定，不可再生），但语义上仍是
  "翻译流水线的输入数据"，与该目录的定位最贴近，且硬约束只点名 `data/batches.jsonl`
  只读，未禁止在 `data/` 下新增文件。最终选定此处，并在
  `tools/land_extra.py` 的模块 docstring 里显式标注它"不可再生"，提醒后来者
  不要把它当成派生产物误删或用 `tools/build_*.py` 覆盖。

⚠ 这 243 条内容本身**逐字未改动**——本轮只做了搬运（`cp` + `diff` 校验），
翻译内容的复核与裁定发生在上一轮会话，不在本次改动范围内。

## 三、四条派生规则的实现

全部落在 `tools/derive_extra.py`，作为 `derive_card_msg()` 的槽位解析升级（原来
card_msg 恒 `confidence=none`，现在 172/172 都能解出 `confidence=template`）：

1. **14 条选项文本定译表 `OPTION_TABLE`**（（…）槽位兜底）：字典直接收录用户给定的
   14 对 jp→zh（含 `約束をしていない、している→没有约定、有约定`——这是**单条**
   表项，key 本身就带顿号，不是两条分开的表项，与真实 172 条 card_msg 里唯一一处
   `の分岐（約束をしていない、している）` 的原文完全对应，不需要按逗号拆分再分别
   查表）。`腕を掴む→抓紧她的手` 一条按任务要求把用户原话原样写进了代码注释：
   > "此裁定仅限这处选项文字翻译，正文类似表现的处理不作变更"

2. **`セクション<X>` → `章节 <X>`（X 全角拉丁/数字转半角）**：`_ZEN2HAN_ALNUM`
   转换表只覆盖 `０-９ＡＺａｚ` 三段（`str.maketrans` 精确列出 62 个字符对），不碰
   全角标点（如「：」）；`resolve_section_label()` 只在精确卡名匹配失败后才被
   调用（多数 `セクションN：人名` 形式本身就是冻结卡名，已在那一步命中，不会走到
   这条兜底规则；真正吃到这条规则的是 13 条无冒号后缀的纯章节代号，如
   `セクション１`、`セクションＥＸ２`）。

3. **绘本标题分かち書き空格形 `TITLE_ALIASES`**：`{"いつか きみが みる お話": 145}`，
   命中后取冻结卡 145 的 `title_zh`（`总有一天你会看到的故事。`）并 `rstrip("。")`
   去尾句号——因为冻结卡 145 的 `title_jp` 是 `いつかきみがみるお話。`（无空格、
   带句号），与 card_msg 里出现的分かち書き形字面不同，精确匹配天然对不上，故需
   单独的别名表而非扩大精确匹配的判据范围（判据过宽=张冠李戴，是本项目明确反对的
   恒绿形态；专设别名表把"这条例外"显式收录，而不是放宽通用规则去迁就它）。

4. **12 句模板表 `CARD_MSG_TEMPLATES`**：键是 `template_of()` 输出的模板骨架（含正确
   的省略号 `…`、全角标点），逐字取自对真实 172 条数据穷举去重的结果，与任务给定的
   12 句译文一一核对无误；`作成`→「写下」等措辞按用户裁定原样收录。
   **槽位解析的顺序与坑**：`『…』` 槽位先精确卡名匹配→别名表→セクション 规则；
   `（…）` 槽位先精确卡名匹配→14 条选项表。新增 `paren_content_after_quote()`
   专门处理"卡名本身可能含括号"的坑（如卡 180「サクラの日記：７月（書きかけ）」）：
   **必须先跳过 `『…』` 闭合位置，只在剩余文本里找 `（…）`**，不能对整个 jp 字符串
   做全局搜索——否则会把卡名内嵌的括号误当成模板槽位，取到「未写完」而不是真正的
   选项文本。真实 172 条数据里恰好没有"卡名带括号 + 真槽位括号"同时出现的行（用
   `grep '（' 计数≥2` 核实过），但这是"目前没暴露"不代表"规则本身安全"，故仍按
   最严谨的方式实现并配了专门的回归测试（见下）。

任一槽位解不出（既不是卡名也不匹配兜底规则/定译表），一律 `confidence=none` 并
单列具体原因的异常，绝不允许"解出一半就拼一句带空槽的译文"悄悄放行——这是
`derive_card_msg()` 里连续三处 `if ... is None: return (...none..., 具体原因)`
的共同设计意图。

## 四、校验结果

```
$ uv run python tools/land_extra.py --check
校验通过：829 行，key 集合与 ledger_extra 完全一致，无重复，source 全部非空。glossary_v=14
--check 模式：不落盘。

$ uv run python tools/land_extra.py
校验通过：829 行，key 集合与 ledger_extra 完全一致，无重复，source 全部非空。glossary_v=14
已落盘 /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward_extra.jsonl（829 行），落盘后回读校验通过。
```

- 行数：`wc -l pilot/lanes/opus/data/forward_extra.jsonl` = 829。
- key 集合：`{r["key"] for r in forward_extra} == {r["key"] for r in ledger_extra}`
  程序化核实为 `True`（脚本内建于 `validate_forward_extra()`，落盘前后各跑一次）。
- 无重复 key：`validate_forward_extra()` 显式检查（落盘前 + 落盘后回读）。
- 空串合法：3 条 `savedata` 空串 zh 均在文件中，`source` 前缀 `reviewed-empty:`
  与非空的 `model+review:` 区分开，不是"漏查"的假象。
- 抽样倒查（随机 8 条，`random.seed(42)`，人工核对 3 条）：
  - `plotTitle:21` → `source=cards.zh:card=21` → `skeleton/cards.zh.yaml` 卡 21
    `title_zh="放学后的钱仙"`，与落盘的 `zh` 逐字一致。
  - `snr_s4_10_s:2556`（scene_title）→ `source=cards.zh:card=148` →
    `ledger_extra` 里该 key 的 `jp="私じゃない"`，与冻结卡 148 的 `title_jp`
    逐字相同，`title_zh="不是我"`，与落盘 `zh` 一致。
  - `snr_crd_60:9`（card_msg）→ 模板 `『…』のあらすじを作成しました。` + 卡 60
    → `已写下『天文馆』的梗概。`，人工核对拼装正确。

## 五、变异红绿实况

四处安全闸，全部用 Edit 应用/还原（未使用任何 git 回滚类命令），每次变异后单独跑
相关测试文件，还原后用 `diff` 与预先存在 scratchpad 的原始文件逐字节比对确认无残留，
最后跑一次全量 `uv run pytest -q` 确认整体回到 938 passed：

| # | 变异内容（文件/函数） | 命中测试 | 结果 |
|---|---|---|---|
| 1 | `land_extra.assemble_rows`：`if not row["jp"]: continue`（空 jp 当缺失跳过） | `test_assemble_rows_empty_savedata_string_is_kept_not_skipped` 等 6 条（含内部"严禁静默丢行"断言先触发） | 红（6 failed） |
| 2 | `land_extra.validate_forward_extra`：删除 key 集合一致性校验块 | `test_validate_forward_extra_rejects_key_set_mismatch` | 红（1 failed，唯一一条，无旁的测试被波及） |
| 3 | `derive_extra.resolve_section_label`：漏调用 `zen2han_alnum`，直接拼全角 X | `test_resolve_section_label_basic` / `test_resolve_quote_content_section_fallback` / `test_derive_card_msg_section_fallback_resolves` | 红（3 failed） |
| 4 | `derive_extra.paren_content_after_quote`：退化为对整串 jp 全局搜索（不跳过『…』闭合位置） | `test_paren_content_after_quote_skips_embedded_parens_in_card_name` / `test_derive_card_msg_embedded_parens_in_card_name_not_confused_with_slot` | 红（2 failed，唯二命中，符合"这条正是为这个坑设的"预期） |

四处变异分别精确对应被删除/放宽的那一行判据，命中测试的失败原因与变异内容一一
对应；变异 2 与变异 4 都只精确命中"专门为它设计"的那条/那两条测试，没有旁的测试
意外变红（说明测试粒度够细，不是"测试无牙"也不是"变异没打中"）。

还原后核对：
```
diff derive_extra.py.orig tools/derive_extra.py   # IDENTICAL（四轮变异后）
diff land_extra.py.orig tools/land_extra.py       # IDENTICAL（两轮变异后）
uv run pytest -q   # 938 passed
```

## 六、测试结果

```
uv run pytest -q
938 passed
```

（基线 898 → 本轮 +40：`tests/test_derive_extra.py` 由 23 条扩到 47 条（+24），
新增 `tests/test_land_extra.py` 16 条。）

分层覆盖：
- `tools/derive_extra.py` 新增的纯函数（`paren_content_after_quote`/
  `zen2han_alnum`/`resolve_section_label`/`resolve_quote_content`/
  `resolve_paren_content`）各有独立单测，覆盖命中与未命中路径。
- `derive_card_msg()` 端到端：已知卡名、选项表命中、卡名/选项表二选一都能命中的
  paren 槽位、卡名带括号的回归用例、セクション 兜底、绘本别名、槽位解不出的两种
  异常（quote 解不出 / paren 解不出）、未知模板骨架不崩溃三类失败路径都各有用例。
- `tools/land_extra.py`：`load_translated_by_jp` 的重复 jp 拒绝、`assemble_rows`
  的全 kind 覆盖 + 空串保留 + 查不到即 raise、`validate_forward_extra` 的四类
  校验失败路径、`land()` 的新建/追加/冲突拒绝三态、CLI `main()` 的 `--check` 与
  真实落盘两条路径，均用 `tmp_path` 隔离，不碰生产目录。
- 两个真实数据冒烟测试（`test_real_data_card_msg_all_172_resolve_to_template`、
  `test_real_data_assemble_and_validate_829_rows_no_dup_no_missing`）钉住
  "172/172 card_msg 可解" 与 "829/829 可落盘且 key 集合吻合" 两个已实测核对过的
  前提，未来 `skeleton/`、`ledger_extra.jsonl` 或 `data/extra_translated.jsonl`
  有变动时会先叫出来。

## 七、硬约束核对

- `git status --short pilot/lanes/opus/data/` → 仅 `?? forward_extra.jsonl`
  一个新文件（落盘前已确认该目录为空 diff；落盘后未改动 `forward.jsonl`/
  `patches.jsonl`/`ledger*.jsonl` 任何一行）。
- `skeleton/`、`data/batches.jsonl`、`png/`、`lua_scripts/` 全程只读（脚本内
  仅 `open(..., encoding="utf-8")`/`yaml.safe_load` 读取，无写入调用）。
- 未触碰 `.claude/settings.json`、`data/api_ledger.jsonl`。
- 变异测试全程用 Edit 应用/还原，未使用任何 `git checkout`/`reset`/`stash` 等命令。
- `.gitignore` 改动仅新增一行否定规则（`!pilot/lanes/*/data/forward_extra.jsonl`），
  与既有 `forward.jsonl`/`patches.jsonl` 两条同款式，未改动其余任何一行。
