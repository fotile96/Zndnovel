# Task 3 报告：字集抽取与 provenance

## 实现内容

在 `tools/layers.py` 末尾追加（紧接 Task 2 的 `_check_ids_of` 之后）：

- `charset_of(sources, ledger_jp, always) -> list[int]`：从「最终源」的 lua 双引号字面串
  （正则 `"((?:[^"\\\n]|\\.)*)"`，转义引号留在串内、遇裸换行终止）∪ 账本 jp 全字集 ∪
  常驻表三处收码位，过滤到 BMP 可见区 `0x20..0xFFFF` 后排序去重返回。
- `write_charset(codes, path) -> None`：按 `ttf_pgf` 要的格式写码位表——一行一个四位
  小写十六进制，自动建父目录。
- `_sha256(path) -> str`：文件不存在返回字符串 `"absent"`，不抛异常。
- `_git(*args) -> str`：包一层 `subprocess.run`，任何异常（不是 git 仓库、命令不存在、
  非零退出）一律吞掉返回空串——取证失败不该阻断构建。
- `provenance(profile, manifest, root, applied, scripts_added, members, outputs) -> dict`：
  汇总车道三文件、账本两文件、`layers/` 树逐文件的 sha256，`luac_sz4`/`ttf_pgf` 哈希，
  git HEAD/branch/dirty 列表，本次施加的层摘要，以及调用方传入的 `scripts_added`/
  `members`/`outputs`，拼成一份 dict。
- `write_provenance(prov, path) -> None`：把 `provenance()` 的返回值写成带缩进的 UTF-8
  JSON（`ensure_ascii=False`，保留中文原样）。虽然 brief 顶部「Interfaces: Produces」
  的三条清单没列出它，但 Step 3 的实现代码块本身完整给出了这个函数——详见下方
  「自评发现」，我判定这是清单遗漏而非叫我别写，按代码块转录。

`tests/test_layers.py`：顶部导入语句里补 `charset_of, provenance, write_charset`
（并入既有那条 `from tools.layers import (...)`，见下方自评），文件末尾追加 brief
Step 1 给出的 7 个测试，逐字转录、未改动断言。

## 测试与结果

- `uv run pytest tests/test_layers.py -q -k "charset or provenance"` → 7 passed（含一次
  RED 复现，见下方 TDD Evidence）。
- `uv run pytest tests/test_layers.py -q` → **40 passed**（33 旧 + 7 新；brief 预期
  「约 35 passed」，实际 40，偏差与 Task 1 报告里记录的同类计数误差同源，不影响结论）。
- `uv run pytest -q`（全库）→ **1720 passed, 4 skipped in 299.94s**（4 skip 是
  `pyproject.toml` 里声明的 `emu` 标记——本机无 PPSSPP 构建，按设计自动跳过）。
- `uv run pytest --collect-only -q` → 1724 收集成功、0 收集错误，确认改动没有在任何
  模块的 import 链上引入语法/名字错误。
- 额外的真实语料冒烟（非 brief 要求，自行加做的验证，非交付物）：把
  `charset_of` 实跑在 230 个真实文件（`lua_scripts/*.lua` 229 个 + `docs/finale/*.lua`
  1 个）与 `data/ledger.jsonl` 的全部 16749 条 `jp` 字段上，0.11s 内产出 2057 个码位，
  区间 `0x20..0xff5e`，全部落在 BMP 内——证明实现在生产规模输入下既不崩溃也不失控地慢。

## TDD Evidence

**RED**（brief Step 2，导入期失败）：

```
$ uv run pytest tests/test_layers.py -q -k "charset or provenance"
ImportError while importing test module '.../tests/test_layers.py'.
tests/test_layers.py:8: in <module>
    from tools.layers import (OverlayError, apply_op, apply_overlay, charset_of, check_ids,
E   ImportError: cannot import name 'charset_of' from 'tools.layers'
```
预期如此：测试先于实现写入，`charset_of`/`provenance`/`write_charset` 三个名字此时
在 `tools/layers.py` 里还不存在。

**中间 RED**（不在 brief 步骤里，是我为核实自己发现的 bug 而主动补的一轮）：先把 Step 3
的实现**逐字**贴入（含 `p.relative_to(REPO)` 这一行），跑同一条命令：

```
$ uv run pytest tests/test_layers.py -q -k "charset or provenance"
......F
tools/layers.py:346: in provenance
    inputs[str(p.relative_to(REPO))] = _sha256(p)
ValueError: '/private/var/.../pytest-.../layers/manifest.toml'
    is not in the subpath of '/Users/fotile96/Zndnovel'
6 passed, 1 failed
```
6 个 `charset_of`/`write_charset` 测试直接通过；`test_provenance_has_required_top_level_keys`
崩在 `ValueError`（不是断言失败）——证实了自评里推定的缺陷是真的会被 brief 自带的这个
测试当场踩中，不是纸上谈兵。

**GREEN**（改 `p.relative_to(REPO)` → `p.relative_to(root.parent)` 之后）：

```
$ uv run pytest tests/test_layers.py -q -k "charset or provenance"
.......
7 passed in 0.90s

$ uv run pytest tests/test_layers.py -q
........................................
40 passed in 0.06s

$ uv run pytest -q
1720 passed, 4 skipped in 299.94s (0:04:59)
```

## Files changed

- `tools/layers.py`（+82 行）：`charset_of`、`write_charset`、`_sha256`、`_git`、
  `provenance`、`write_provenance`。
- `tests/test_layers.py`（+51/-3 行）：顶部 import 扩充三个名字；追加 7 个新测试。

commit：`e95da15 feat: 字集抽取与构建取证`（brief 给的提交信息逐字使用）。

## 自评发现

1. **真缺陷，已修（不是转录已知缺陷）**：`provenance()` 第三段循环
   （`for p in sorted(root.rglob("*")): ... p.relative_to(REPO)`）在 brief 原文里用
   `REPO`（模块级常量，恒等于本仓库根）做相对基准。但 `provenance()` 的 `root` 是**调用方
   传入的参数**，brief 自己写的测试 `test_provenance_has_required_top_level_keys` 传的是
   `tmp_path` 下临时构造的层根——不在 `REPO` 子树内，`relative_to(REPO)` 当场
   `ValueError`，测试连断言都跑不到就崩。这正是 task 说明里点名的那类缺陷（「brief 的代码块
   不是正确性判据」）。用真实跑测（见上方「中间 RED」）先复现、再定位、再修：改成
   `p.relative_to(root.parent)`。生产环境里 `root == LAYERS == REPO/"layers"`，
   `root.parent == REPO`，行为与原文完全一致（产出 `"layers/manifest.toml"` 这类键，
   与设计稿 §6.6 示例的 `"layers/**"` 前缀吻合）；测试环境里 `root.parent == tmp_path`，
   同样产出 `"layers/xxx"` 形态的键而不崩溃。已加中文注释说明取舍。

2. **`write_provenance` 不在「Interfaces: Produces」清单里，但在 Step 3 代码块里**：
   对比 Task 1 的 brief（Produces 五条，实现的公开函数/类也恰好五个，一一对应），Task 3
   的 Produces 只列三条，比代码块少了 `write_provenance` 这一个公开函数。判定为清单遗漏
   （很可能是因为它没有专门的单元测试、写清单时漏记），而不是「brief 想让我别实现它」——
   理由：这是 `write_charset` 的直接对应物，设计稿 §6.6 明确要求「写在
   `build/<profile>/provenance.json`」，没有写文件的函数这句话就落不了地；Step 3 的
   代码块本身完整给出了函数体，task 说明要求「实现 brief 指定的内容，按其步骤顺序」，
   代码块比顶部摘要清单更接近「规格」。按代码块转录，未新增测试（brief 的 Step 1
   测试列表里也没有它——没有为它杜撰一个 brief 没要求的测试，避免 YAGNI 越界）。

3. **`charset_of` 对「注释里的字不算」只在测试给的场景下成立，不是通用保证**——已用
   真实语料验证、判定不必修：正则只按「引号...引号」配对扫描全文，不理会 `--` 注释边界。
   若一行 `--` 注释本身包含带引号的片段（如
   `-- TODO(eve_74_z)...cGetFileName("event", "eve_74_z")`），这段引号内容会被当成
   字面串收进字集。实测 `docs/finale/snr_finale.lua`（这是编外脚本层的真实来源，会话进
   `layers/scripts/` 后就是 `charset_of` 的真实输入）里确有 2 处这样的注释，内容都是纯
   ASCII（`"fin-10"`、`"event"`、`"eve_74_z"`）。brief 给的测试
   `test_charset_takes_non_ascii_from_string_literals_only` 测的是「注释里不带引号的
   裸文字不算」，不是「注释里带引号的文字也不算」——两者是不同的命题，现有实现只满足
   前者。我判定不必为后者加注释剥离逻辑：(a) 两个真实命中都是 ASCII，不会引发缺字（伤害
   模型只可能是「漏收」，这里只会「多收」几个已经必然存在的 ASCII 码位，命中项目自己写
   在 docstring 里的宁滥勿缺原则）；(b) 加一层注释感知扫描本身是新的正确性面，如果它有
   bug（比如把跨行字符串状态机搞错），代价是可能反而漏收——用一个当前没有任何测试要求、
   且实测无害的场景去换取新的出错面，不划算。写在这里存证，供 Task 4/8 若发现新的、
   有 CJK 字符的反面案例时重新评估。

4. **测试文件顶部 import 语句：把新三个名字并入既有的 `from tools.layers import (...)`
   语句，没有像 brief 字面那样在文件底部另起一条 `from tools.layers import charset_of,
   provenance, write_charset`**。这是本任务里唯一一处「没有逐字照抄 brief」的地方，
   原因是 `progress.md` 记录 Task 2 的 review 明确把「新增第二条 from import 语句、
   且带未使用的名字」判成 minor 缺陷并在 fix round 里清理掉——我在开工前读过这条记录，
   直接按同一标准把三个新名字揷进已有那条语句的字母序位置（`charset_of` 排 `check_ids`
   前，`provenance` 排 `select_indices` 前），避免复现一个已经在这个任务序列里被明确
   点名过的问题。7 个新测试逐字未改。

5. **`test_charset_is_sorted_and_unique` 乍看像重言式，复核后确认不是**：
   `codes == sorted(set(codes))` 第一眼像是拿函数输出去跟自己的重排版本比，但实际上
   `charset_of` 若漏排序或漏去重（比如返回未排序的 list 或带重复项），这个断言就会为
   假——它比较的是「实际返回值」与「该返回值的规范形式」，不是把规范形式再规范一次。
   确认是有效测试，未改动。

## Concerns

- `provenance()` 里 `Path("/tmp/pgftool/ttf_pgf")` 是硬编码路径，没有走
  `tools/build_font.py` 里 `TTF_PGF = Path(os.environ.get("SNDL_TTF_PGF", "/tmp/pgftool/ttf_pgf"))`
  这种环境变量可覆盖的写法——brief 原文如此，且当前没有测试要求可覆盖行为，我没有改动。
  如果 Task 4/8 的构建脚本需要在非默认路径下找 `ttf_pgf`，这里会需要同步补上
  `SNDL_TTF_PGF` 读取，目前只会静默按 `_sha256` 的「absent」兜底，不会报错也不会提示
  路径可配置。
- `provenance()` 的 `root.rglob("*")` 对 `layers/` 做全量递归哈希，文件数与仓库规模成
  正比；当前 `layers/` 极小（几个 toml + 未来的 scripts），可忽略；如果之后
  `layers/scripts/` 塞进大量生成产物（比如 test 剖面 `generated/` 目录若被误放进
  `layers/` 而非 `build/test/generated/`），这里的哈希成本会跟着涨——设计稿把
  `generated/` 明确放在 `build/test/` 下，不在 `layers/` 里，所以按现有设计不会发生，
  仅记录以防未来误用。
- 未给 `write_provenance` 单独补测试（详见自评第 2 点），它逻辑上是 `write_charset`
  的同构简化版（少一步 `f"{c:04x}"` 格式化，多一步 `json.dumps`），复杂度很低；
  若 Task 4/8 集成时它是第一次被真正调用，建议在那一层的集成测试里覆盖到「provenance.json
  确实落盘且可被 `json.load` 读回」这一路径。

全部发现已在实现里处理或在此说明取舍；没有遗留未决的正确性问题。
