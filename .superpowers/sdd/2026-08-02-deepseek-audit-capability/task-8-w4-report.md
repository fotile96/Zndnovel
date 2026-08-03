# Task 8：W4 复现句族内逐字一致（顾问级检查）执行报告

状态：**完成**。改动文件仅 `tools/check_batch.py` + `tests/test_check_batch.py`（+ 本报告）。

## 判据（一行）

对本批每一行，在**全库**（`data/ledger.jsonl` 的 jp）范围内取 jp 逐字相同且
**已有译文**（车道 `forward.jsonl` + `patches.jsonl`，patch 覆盖 forward）的兄弟行；
任一兄弟行 zh 与本行不同即报 W4（warn，不阻断）。

## 实现要点

- `build_sibling_index(ledger_rows, zh_map) -> {jp: [(id, zh), ...]}`：**一次性**建族索引
  （ledger 16749 行 / 已译 8816 行，实测 0.05s），行循环内只做 O(1) 查表——不在行循环里扫全库。
- `check(..., siblings=None)`：新增可选参数。**不传即完全不判 W4**，既有调用方行为逐字不变。
- 进 `check()` 后先把本批草稿并入族索引：
  - 批内同 jp 重复因此互为兄弟（兄弟还没进 forward 也能抓）；
  - 本批 id 的新草稿顶掉车道里同 id 的旧译文，避免「与自己的历史版本互报」的假阳。
- `load_siblings(root)`：按 `--lane-dir` 解释车道路径（`<root>/data/{ledger,forward,patches}.jsonl`），
  **未写死仓库根**；ledger 缺失或全库无译文时返回 `None`，W4 静默不判（不伪造绿）。
  仓库根没有 `data/forward.jsonl`，故不带 `--lane-dir` 的既有用法 W4 天然不生效，回归零风险。
- 消息可操作：`复现句族内不一致（同一 jp 另有译法）：id=1611 作「彩野同学压低了声音说道。」`——
  写明兄弟 id 与其 zh；多种异译按 zh 去重、最多列 3 条并附总数。
- 归 `warn` 不归 `hard`（顾问级）：同一句日文在不同语境下偶有正当的不同处理；且本项目吃过
  「谓词过严制造噪声淹没真信号」的亏。未加任何长度阈值或其他过滤（>25 字零违例是数据结论，不是规则）。

## 测试

- `uv run pytest -q` → **462 passed**（`tests/test_check_batch.py` 15 → 23，+8；
  其余测试文件未动，故 HEAD 基线实为 454，交接单里的 436 是更早的数字）。
- 新增合成数据用例（不钉活的生产译文）：jp 同 zh 不同报警且消息含兄弟 id 与 zh／jp 同 zh 同不报／
  jp 差一字不报／批内重复两行都报／兄弟未译不报／自身旧译文不算兄弟／不传 siblings 行为不变。
- 真实数据测试：**保留但只验结构**（`test_w4_real_lane_structure`）——断言族索引读得出、
  `0 < 多成员族数 ≤ 全部族数`、`异译族数 ≤ 多成员族数`。理由：具体数字随生产推进而变
  （`test_saturation.py` 已因钉住 167/13 这类活数据吃过红），但完全跳过又会让「判据能否在真实
  16749×8816 规模上跑通」无人验证；加 `0 < 多成员族数` 是为了让它不至于沦为恒真断言。

## 变异自检（这条闸真的会响）

| 变异 | 结果 |
|---|---|
| `if others:` → `if False and others:`（W4 判断恒假） | 精确 2 红：`test_w4_same_jp_different_zh_...`、`test_w4_catches_duplicates_inside_the_same_batch`；其余 21 绿 |
| `build_sibling_index` 恒不收行（索引恒空） | 精确 2 红：上述第一条 + `test_w4_real_lane_structure`（`assert 0 < 0`）——证明真实数据测试非恒绿 |

两次变异均已改回，改回后 462 passed。

## 真实车道实跑

`pilot/lanes/opus`（forward 8816 + patches 18）：

- 全库族统计：jp 逐字相同且均已译的族 **340 组 / 覆盖 1113 行**，其中 zh 不一致 **19 组**——与交接单实测量级完全一致。
- 把 8816 条已译行整体当作一批过 `check()`：W4 报 **55 行 / 19 个不同句族**（同族多行各自报一次）。
- CLI 路径实跑：`ZND_WORK=<tmp> uv run python -m tools.check_batch --batch 40 --lane-dir pilot/lanes/opus`
  → PASS warn=1（该批 W4 命中 0，符合 5% 族命中率下单批可能为零的预期）。work 目录用的是临时目录，
  **未向 `pilot/lanes/` 写入任何文件**。

## 顾虑

1. **同族多行各报一次**：19 组产出 55 行 warn。当前按行报（每行都给出该改哪边的信息），
   若日后 warn 报表希望「一族一条」，需在报表层去重，check 层不宜改（它是逐行契约）。
2. **W4 只在传了 `--lane-dir` 时才有牙**：仓库根没有 `forward.jsonl`，缺省调用静默不判。
   这是刻意的向后兼容取舍，但意味着「忘了带 `--lane-dir`」＝这条闸静默失效，
   与本项目忌讳的「恒绿安全闸」同形。生产流水线调用一律带 `--lane-dir`，故当前无损；
   若日后有不带车道的生产调用，应改为显式报「W4 未启用」而非静默。
3. **兄弟范围是全库而非前缀**：晚批会把早批的定译当基准比对，早批不会回头查晚批。
   逐批推进下这正是想要的（后来者向已定稿看齐），但整库回扫时同族内谁对谁错仍需人判断。
4. 会话期间工作树里有**其他会话的未提交改动**（`pilot/lanes/opus/data/notes/s4s.md` 等），
   本次只 `git add` 了自己改的三个文件，未触碰它们。
