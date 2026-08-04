# Task 15：voices 示范译例 vs anchors 定稿自洽机械闸——报告

## 状态

完成。535 测试全绿（521 → 535，新增 14 条：`tests/test_check_voices_anchors.py`
12 条 + `tests/test_lane_setup.py` 2 条）。

## 改动

- 新增 `tools/check_voices_anchors.py`（独立工具，非 `lane_setup.py` 内联）：
  - `load_anchors(anchors_path)`：按真实嵌套 schema
    `[{chapter, items: [{id, zh, ...}]}]` 取 `id -> zh`。
  - `extract_citations(md_path)`：抽取 voices「例句（日→中）」小节的两行体示范
    译例 `(行号, id, voices_zh)`。
  - `check(voices_dir, anchors_path)`：对每个可比条目（id 能在 anchors 查到）比
    对 zh 是否逐字一致，返回 `(mismatches, n_comparable)`。
  - `main()`：CLI 包装，读仓库 `glossary/voices/` + `skeleton/anchors.yaml`，
    有冲突打印后 rc=1，否则 rc=0（`uv run python -m tools.check_voices_anchors`）。
- `tools/lane_setup.py`：`verify()` 新增"第三层"检查——调用
  `check_voices_anchors.check()`，查**仓库侧**（`repo` 参数指向的
  `glossary/voices/` + `skeleton/anchors.yaml`，非各车道冻结拷贝）自洽性，结果
  并入返回的 drift 列表。这一层与 `pilot-manifest.json` 是否存在无关，放在
  `mp.exists()` 判断之前，任何时候 `--verify` 都会跑到。
- `tests/test_check_voices_anchors.py`（新增，12 条）：schema 解析、两行体抽取、
  多 id 合引行跳过、下一行非 `→`（只引日文）跳过、id 不在 anchors 里不计入
  comparable、内容一致/不一致、报错文本含文件:行号/id/两侧 zh、多文件扫描、
  CLI rc 0/1。
- `tests/test_lane_setup.py`：新增 2 条集成测试——`verify()` 能抓住仓库侧
  voices/anchors 内容冲突（与哈希漂移无关）、内容一致时 `setup→record→verify`
  正常流程不误报。

## 判据：一行内说清

一行里 `\[(\d+)\]` 恰好命中一次、且紧邻的下一行 lstrip 后以 `→` 开头，且该 id
能在 `anchors.yaml` 查到——四者同时成立才算「可比条目」，否则跳过（不算冲突，
只是不比）。

## 判据相对控制器原型的调整

控制器原型只写了"一行恰好一个 `[数字]`，且下一行以 `→` 开头"。我重新过了一遍
7 份 voices 全部 `\[\d+\]` 出现处（不止「例句」小节，含正文表格/项目符号里的行
内引用如 `ayano_real.md:17` `[16382]「直哉……くん？」→「直哉……君？」`），确认
了两件事，最终**没有扩大**判据范围：

1. **三行体会被漏判，但影响是 0**：`naoya.md` 例 1（id 6085，母题句）是
   "id 行 / 日文另起一行 / → 译文再一行"的三行体，严格"下一行"判据接不住。
   该 id 确实在 anchors 里，且内容本就完全一致（不含冲突）——纳入与否不改变
   真实结论，而要接住它就得处理"跨行回溯时中途混入别的 id"这类新歧义，不值得
   为一条已知一致的记录扩大判据面，故按兵不动。
2. **行内引用形态（`[id]「日文」→「中文」` 全部挤在同一行）会被漏判，且是
   刻意的**：这类引用命中 anchors 的唯一一例是 `yukari.md` 的 `[3962]`——其
   行内译文是「「啊，不良少年」」（表格行里说话人已由行首列名担当，故省略
   前缀），而 anchors 该条 zh 固定带「【ユカリ】」前缀。若不做归一化直接按原样
   字符串比对，会把这个纯格式差异（有没有说话人前缀）误判成翻译冲突——这正是
   SEG-4 教训（"判据过宽会用伪报淹没真信号"）要防的事。要安全纳入需要先做
   "剥离说话人前缀再比"的归一化，但归一化本身可能真的吃掉说话人错位这类实质
   冲突；语料里目前只多验 1 条、且已知内容一致，收益不足以抵消这层复杂度，故
   本版本明确不纳入行内引用形态（`check_voices_anchors.py` 模块文档里写明了
   理由，供未来该形态命中数变多时重新评估）。

结论：判据保持原样（不扩、也没有理由收窄），仅额外确认了它为什么"窄"是安全
的——不是漏检、是漏掉的两类都已知不构成冲突。

## 归属决定

放进 `tools/lane_setup.py` 的 `verify()` 里调用，但检查逻辑本体独立成
`tools/check_voices_anchors.py`：

- `verify()` 是 `lane_setup --verify` 的实现，而 `lane_setup --verify` 是生产
  会话开工自检必跑的一步（runbook §2）——放进去能保证这道闸被执行，不依赖
  译者/控制器另外记得跑一个新命令。
- 但 `check_voices_anchors.check()` 校验的是**内容自洽**（voices 与 anchors
  两份文件是否互相打架），与 `verify()` 原本的语义"冻结哈希有没有漂移"是两件
  不同的事——即便两份文件各自都没有漂移，也可能从来就没自洽过。把检查逻辑本体
  拆成独立模块，既避免把两种语义焊死在同一个函数体里（`verify()` 内只是"调用
  + 把结果并进 drift 列表"一行注入，逻辑本体可独立单测、独立复用、独立在 CI
  或 pre-commit 里单跑），也让 `verify()` 的 docstring 能诚实地说"这是第三层、
  与前两层机制不同"而不是含糊带过。

## 真实语料实跑

```
$ uv run python -m tools.check_voices_anchors
OK（共比对 14 条可比条目，0 条冲突）
```

与任务给出的既有结论一致：14 条可比、0 条冲突。

## 变异自检（含"变异是否真的打中"的确认）

- 变异：把 `glossary/voices/ayano_real.md` 里 id 6111 的示范译文
  「呐，这件事，我以前听过吗？」改成「呐，这件事，我以前有没有听过？」（与
  `anchors.yaml` 定稿不同）。
- 确认变异真的打中目标（不是没打中就直接看绿）：变异前先跑一次
  `check_voices_anchors`，确认 6111 本就在"0 条冲突"的 14 条可比条目里（若它
  本不可比，改坏它也不会被抓到，绿会是"没打中"而非"闸有牙"）；变异后再跑：
  ```
  glossary/voices/ayano_real.md:46: 锚点 id 6111 冲突——voices 写「【彩野】
  「呐，这件事，我以前有没有听过？」」，anchors 定稿「【彩野】「呐，这件事，
  我以前听过吗？」」（anchors 为终审定稿，应改 voices）
  （共比对 14 条可比条目，1 条冲突）
  rc=1
  ```
  文件名、行号（46，即 `→` 那一行）、id（6111）、voices 侧、anchors 侧四项
  齐全，且比对基数仍是 14（未误伤其余可比条目）。另外用
  `tools.lane_setup.verify()`（默认 REPO/LANES_ROOT，即走生产会话实际会跑的
  `lane_setup --verify` 路径）复核，同一条冲突同样出现在返回的 drift 列表里，
  确认第三层检查确实挂上了 `--verify` 入口。
- 变异已用变异前备份的原文件逐字还原（`diff` 确认字节级一致），
  `uv run python -m tools.check_voices_anchors` 复跑回到「0 条冲突」。

## 顾虑

- `glossary/voices/*.md` 里除本闸认得的两行体、行内引用之外，理论上还可能有
  未来新增的第三种引用写法（如控制器可能改用的其它示范格式）——本闸只覆盖当前
  语料实测到的两种，若格式变了需要重新扫描确认。
- 行内引用形态目前只有 1 条命中 anchors 且已知一致，故意未纳入判据；如果之后
  控制器往 voices 里补更多行内引用形式的示范译例（尤其是带 id 又带译文的），
  这道闸不会覆盖到它们，需要有人记得回来重新评估这条决策。
- 本次改动只触达仓库侧 `glossary/voices/` 与 `skeleton/anchors.yaml`（只读），
  未触达 `pilot/lanes/` 下任何车道的冻结拷贝——按纪律这些目录也在禁止改动
  之列，`verify()` 新增的检查同样只读，不会写回任何车道内容。
