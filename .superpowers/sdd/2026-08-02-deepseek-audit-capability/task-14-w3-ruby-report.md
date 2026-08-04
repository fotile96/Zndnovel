# task-14 报告：W3 行宽剥 ruby + translator_cc 补 W3 触发口径

日期 2026-08-04 ｜ 基线 HEAD `e7529ae`（`uv run pytest -q` = **514 passed**）
产出 commit：① `43e3dd9` fix ｜ ② `4f70c9e` docs
终态测试：**521 passed**（+7，全部为本次新增的 W3/ruby 测试）

---

## ① `check_batch` 的 W3 不剥 ruby（`tools/check_batch.py`）

### 缺陷

`_max_line_width(s)` 对**原始字符串**算显示宽度，把 ruby `<A,B>` 整段计进去。
引擎只在 A 正上方以小字号渲染 B，**行宽只占 A**。

后果双向：

- **zh 侧**：译文一加注音 W3 必然虚高误报；译者消警最省事的办法是删注音——
  用户刚裁决用引擎 ruby 给生僻字注拼音（已写进 `glossary/style.md`），机制刚
  立起来就会被工装惩罚。
- **jp 侧**：日文原文 38 处原生 ruby（`<前向性健忘,ぜんこうせいけんぼう>` 等）
  同样被算成超宽，**撑大分母**、把真超宽的译文放过去。分子分母双双失真。

### 实现

抽出独立函数 `_strip_ruby(s)`，`_max_line_width` 调用它：

```python
def _strip_ruby(s: str) -> str:
    return RUBY_RE.sub(lambda m: m.group(1), s)

def _max_line_width(s: str) -> int:
    return max(display_width(seg)
               for seg in BREAK_RE.split(_strip_ruby(s))) if s else 0
```

`RUBY_RE` 由 `r'<[^<>,]+,[^<>,]+>'` 改为带捕获组的 `r'<([^<>,]+),([^<>,]+)>'`
——**匹配集合逐字未变**，只是把两段捞出来；`_ruby_ok` 的 `RUBY_RE.sub("", s)`
行为不受影响（`sub` 不关心有无组）。

**为什么抽成独立函数而不是内联**：(1) 可单测——直接钉 `_strip_ruby("<囔,nāng>")
== "囔"`，不必绕过 `display_width` 的东亚宽度换算去反推；(2) 语义是「标记 →
屏幕文本」的通用变换，`_max_line_width` 由此退回一行「按屏幕占位取最宽行」，
职责单一；(3) 日后若有别的规则（硬折行预演、卡面排版核对）需要同一变换，有现成
入口，不会各写一份走形。

**为什么与 `_ruby_ok` 共用同一条正则**：两者对「什么算良构 ruby」必须同一口径。
若计宽用一套更宽松的模式，就会出现「`_ruby_ok` 判为不良构而 hard 拦下、计宽却
已按 ruby 剥掉」的错位。

### 「先剥 ruby 还是先按 `_n`/`_r` 切」——选先剥

**两种顺序仅在断行码落进 ruby 标记内部时有别**，例如 `<漢字,か_nな>`：

- 先切：`BREAK_RE` 把它拆成 `<漢字,か` 和 `な>` 两段废片，两段都不再匹配
  `RUBY_RE`，于是尖括号、逗号、注音假名全部按字面计宽 → 虚高（该例 4 → 7），
  且凭空多出一个并不存在的断行。
- 先剥：ruby 作为**原子标记参数**先解析掉，得 `漢字` = 4，不引入断行。

其余所有输入两种顺序等价（如 `A_n<x,y>_nB` 两路都得 `["A","x","B"]`），因为
`BREAK_RE.split` 与 `RUBY_RE.sub` 只在字符区间重叠时才互相干扰。

选先剥的理由：ruby 是一个**标记 token**，`_n` 落在其参数内部时属于 token 内部
字节，不是主文本的断行；先切等于在解析标记之前就把标记撕开，产出的两段废片既不
代表屏幕内容、也不代表任何真实断行。真实语料 34 种 ruby 里没有一例含 `_n`/`_r`
（已 grep 确认），但错误顺序在这类输入上会**虚高**，方向恰好和本次要修的缺陷一致
——所以顺序也写了专门的测试钉死（`test_width_strips_ruby_before_splitting_breaks`）。

### 边界（先看真实语料再定）

`grep -ohE '<[^,<>]+,[^,<>]+>' lua_scripts/*.lua | sort -u` → 34 种，含：

- 单字训读 `<亡,な>`、多字音读 `<前向性健忘,ぜんこうせいけんぼう>`；
- **全角拉丁前半段** `<Ｔｒｕｅ Ｃｏｌｏｒ,トゥルー カラー>`：前半段 9 个全角
  字符 + 1 个**半角**空格（U+0020，`east_asian_width='Na'`）= 宽 19。`display_width`
  逐字符判定，剥离后天然正确；已单测钉死这个 19。

**畸形/不成对尖括号一律不吃**（`RUBY_RE` 要求良构的 `<非<>,段, 非<>,段>`）：

| 输入 | 计宽 | 说明 |
|---|---|---|
| `a<b` | 3 | 无逗号无闭合，`<` 在屏幕上确实占位 |
| `5 > 3` | 5 | 纯不等号 |
| `<a,b,c>` | 7 | 两个逗号，非良构，按字面计 |

即：**宁可少剥（保守地把可疑串按字面计宽，最多虚高一点、误报方向）也不多剥**
（多剥会把真实占位的字符算没，制造漏报）。另外 zh 侧的畸形尖括号本就会被
`_ruby_ok` 判 R2a 硬拦，计宽这层只需不添乱。

**未动阈值**：`> max(10, ..._max_line_width(jp) * 1.15)` 逐字未改。本次只修计宽
的正确性。

### 新增测试（7 条，jp/zh 两侧分别钉）

| 测试 | 钉住的东西 |
|---|---|
| `test_strip_ruby_keeps_base_drops_reading` | 剥离函数本身：留 A 去 B |
| `test_width_counts_only_ruby_base` | 任务书给的 4 个实测值（2 / 2 / 16 / 16） |
| `test_width_handles_fullwidth_latin_ruby_base` | 全角拉丁前半段 = 19 |
| `test_width_does_not_eat_stray_angle_brackets` | 3 类畸形尖括号不被吃掉 |
| `test_width_strips_ruby_before_splitting_breaks` | **顺序**：`<漢字,か_nな>` = 4 |
| `test_zh_ruby_does_not_false_trigger_w3` | **zh 侧**：加注音不报 W3 |
| `test_jp_ruby_no_longer_inflates_threshold` | **jp 侧**：原文 ruby 不撑大分母 |

jp 侧那条是**真有牙的**：jp 屏幕宽 32（含 ruby 字面虚高到 55），zh 宽 40 →
真阈值 36.8 **超**、虚高阈值 63.25 **曾被放过**。修前它是漏报，修后必须报。

---

## ② `prompts/translator_cc.md` 补「W3 真触发了怎么办」

在「一条来自实测的提醒：不要心算 W3」节**末尾追加**两段（未动该节及任何其他节
的既有文字）：

1. **W3 真触发时的默认动作：保留 warning、不改译文。** 仅当收紧措辞的语感代价为
   零时才顺手改；W3 是顾问级 warn，不是必须清零的 hard。附实战溯源：SEG-4 前三组
   因无明文口径出现三种做法（b121 收紧 / b124 拒绝 / b127 收紧），自 b130 组起在
   派发单里明确该动作后，**b130–138 五批 W3 warn 全部为正当保留**。
2. 顺带写明宽度按屏幕实际占位算、ruby 注音不计宽——**不要为消警删注音**。这条与
   ① 是同一件事的两面：工装不再惩罚注音，prompt 也要明说，否则译者仍会凭旧印象
   自我审查。

**只增不删核实**：`git diff --numstat prompts/translator_cc.md` → **`4  0`**；
另跑 `git diff -U0 | grep '^-' | grep -v '^---'` 输出为空，确认零删除行。

---

## 验收

### 变异自检（4 个变异，全部被杀）

方法：脚本逐个把目标串 `replace(old, new, 1)` 写回 `tools/check_batch.py`，
**先打印该串在文件中的出现次数**（确认 `,1` 不会打错位置）、**再打印
`git diff -U0` 的实际改动行**（确认变异真的落在目标位置），最后跑全量 pytest，
跑完把原文逐字写回（未用 `git checkout`/`restore`/`stash`）。

| 变异 | 出现次数 | 实际改动行（已核对） | 结果 | 杀手 |
|---|---|---|---|---|
| M1 `BREAK_RE.split(_strip_ruby(s))` → `BREAK_RE.split(s)`（还原缺陷本身） | 1 | `+ for seg in BREAK_RE.split(s))` | **4 failed** | width_counts_only_ruby_base / fullwidth / order / **jp_ruby_no_longer_inflates** |
| M2 `m.group(1)` → `m.group(2)`（剥成注音段） | 1 | `+ return RUBY_RE.sub(lambda m: m.group(2), s)` | **5 failed** | strip_ruby / counts_only / fullwidth / order / jp_ruby |
| M3 `_strip_ruby` 体改成 `RUBY_RE.sub("", s)`（连本体也删光） | 1 | `+ return RUBY_RE.sub("", s)`（位于 `_strip_ruby` 体内） | **6 failed** | 上列 + **zh_ruby_does_not_false_trigger_w3** |
| M4 先切后剥（`map(_strip_ruby, BREAK_RE.split(s))`） | 1 | `+ for seg in map(_strip_ruby, BREAK_RE.split(s)))` | **1 failed** | **strips_ruby_before_splitting_breaks** |

**「变异是否真的打中」的确认**：四个目标串在文件中的出现次数**均为 1**，
`replace(..., 1)` 不存在「换错了另一处同名字符串」的可能；且每次都从 `git diff`
里核对到了改动后的那一行本身（表中第 3 列），不是靠「跑了没炸」倒推。M3 是最需要
这层确认的一个——`RUBY_RE.sub("", s)` 在文件里另有一处（`_ruby_ok`），故变异用的
是完整的 `RUBY_RE.sub(lambda m: m.group(1), s)` 作匹配串（唯一），并核对到新行落在
`_strip_ruby` 体内而非 `_ruby_ok`。

M4 只杀 1 条是预期的：先切/先剥的分歧面本就极窄（仅断行码落进 ruby 内部），
正因如此才专门写了一条测试去覆盖它，否则这个顺序决策会是**无测试保护**的。

变异全部还原后复跑：**521 passed**，文件与变异前逐字相同（脚本内 `== ORIG` 断言）。

### 真实语料回归（`pilot/lanes/opus`，只读）

对该车道 `data/ledger.jsonl` × `resolve_map(forward, patches)` 的**全部已译
12702 行**，用「修前实现」与「修后实现」各跑一遍 W3 判据（阈值同一条，只换计宽）：

```
W3 命中：修前 59 → 修后 51
  消失（虚报解除）8      新增（分母不再虚高）0
```

**抽验（消失的 8 条全部含 zh ruby，无一例外）**：

| id | jp 宽（修前→修后） | 阈值 | zh 宽（修前→修后） | zh ruby |
|---|---|---|---|---|
| 11148 | 26 → 26（jp 无 ruby） | 29.9 | **36 → 18** | `<哐,kuāng>` ×2 |
| 11132 | 30 → 30 | 34.5 | **45 → 26** | `<纳,nà>`/`<哈,hā>`/`<梅,méi>`/`<妖,yāo>` |
| 11141 | 30 → 30 | 34.5 | **41 → 24** | `<咚,dōng>`/`<哐,kuāng>` |

三条的 jp 宽与阈值**逐字未变**（jp 无 ruby），变的只有 zh 一侧、且降幅恰等于被剥掉
的注音串宽度 → 确认是「注音虚报解除」，不是别的东西被误伤。消失的全部 8 条
id 为 `11126, 11132, 11141, 11148, 11151, 11153, 11157, 11274`（均在 s3fc_90 绘本
全平假名段一带，正是拼音注音最密集的地方）。

**修后剩余的 51 条命中里，zh 含 ruby 的为 0 条** → 剩余命中都是真实的行宽超限，
没有一条是注音撑出来的。

**jp 侧的影响**：已译行中 jp 含 ruby 的有 29 行，阈值全部下降（如 id=6351：
71.3 → 32.2，几近腰斩；id=6089：65.5 → 55.2）。这 29 行现有译文在收紧后的阈值下
**仍全部不触发 W3**，故新增 0。即：jp 侧的分母失真是**真的被修掉了**，只是当前
车道恰好没有藏在虚高阈值背后的漏报——这条对后续批次是**收紧**，不是空转。

---

## 顾虑

1. **`tools/check_skeleton.py:61` 也用 `display_width` 判卡面标题宽（>28）**，同样
   不剥 ruby。当前 197 张卡的 `title_zh` 未见 ruby，故无实害；但若日后卡名开始注
   拼音，会重演同一缺陷。本次按「只修 W3」的授权范围未动它——**建议后续单独立项**
   （连带 `tools/check_charlevel.py` 里那条独立的 `RUBY_RE`，全仓共三处 ruby 正则
   各写各的，有走形风险）。
2. **`_ruby_ok` 只查 zh、不查 jp**：若 ledger 里的 jp 出现畸形 ruby（现无），计宽会
   按字面把它算进分母、虚高阈值。属既有行为，本次未改。
3. **顺序决策靠的是引擎语义推理，不是实机验证**：`_n` 落进 ruby 参数内部时 PSP 引擎
   究竟怎么解析，无从在本仓库验证。但两种顺序在真实语料上**没有任何分歧**（34 种
   ruby 无一含断行码），且错误顺序只会**虚高**（误报方向，不制造漏报），风险可接受。
4. **W3 阈值本身没动**，但计宽收紧后 jp 侧阈值实际下降（最多近腰斩）——后续批次
   W3 命中率可能**小幅上升**，那是修掉漏报的正常结果，不应被当成回归。② 追加的
   「默认保留 warning」口径正好覆盖这类新增 warn 的处理方式。
5. 工作树原有的未提交改动（`data/api_ledger.jsonl`、
   `docs/superpowers/specs/2026-08-03-extra-lane-collapse-design.md`）**全程未触碰**，
   两次 commit 均只 `git add` 本次实改文件。
