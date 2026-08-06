### Task 2: config/polish.yaml + tools/polishlib.py（公共层）

**Files:**
- Create: `config/polish.yaml`、`tools/polishlib.py`
- Test: `tests/test_polishlib.py`

**Interfaces:**
- Produces:
  - `polishlib.CFG` → dict（读 config/polish.yaml）
  - `polishlib.seg_dir(label) -> Path`（`REPO/pilot/polish/<label>`）
  - `polishlib.jp_tail(s, n=8) -> str`（剥控制码/ruby 注音后取末 n 字符）
  - `polishlib.edit_distance(a, b) -> int`（字符级 Levenshtein，difflib opcodes 计数）
  - `polishlib.autoclear_limit(opus_zh) -> int`（`max(4, int(len×0.15))`，len 取剥控制码后）
  - `polishlib.strip_ctl(s) -> str`（去 `_n/_r`、ruby 注音部、不去文本）

- [ ] **Step 1: 写 config/polish.yaml**

```yaml
# P4 润色 pass 阈值（spec §9：集中一处；调整记台账；不以自动入库率为优化目标）
K: 150                 # 每 SEG 请裁配额（总额，多通道共享，含抽检占用）
sample_rate: 0.10      # 自动清关随机抽检率
overturn_freeze: 0.20  # 抽检推翻率 ≥ 此值 → 冻结该通道本 SEG 自动清关权
calib_fail: 0.30       # 准入小考：金标句实质改写占比 ≥ 此值 → 自动清关权初始关闭
autoclear_abs: 4       # 自动清关幅度 = max(autoclear_abs, len(opus)×autoclear_ratio)
autoclear_ratio: 0.15
minor_edit: 4          # 校准三档：edit≤minor_edit 为轻微，>autoclear_limit 为实质
amplify_rounds: 1
session_size: 10       # 长对话双帽（沿 P3）
session_lines: 600
jp_tail_n: 8           # 回执尾串长度
```

- [ ] **Step 2: 写失败测试**

```python
# tests/test_polishlib.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polishlib as pl

def test_cfg_loads():
    assert pl.CFG["K"] == 150 and 0 < pl.CFG["sample_rate"] < 1

def test_jp_tail_strips_ctl_and_ruby():
    s = "こんにちは_nよろしく<漢字,かんじ>ね"
    # 剥 _n 与 ruby 注音部（保留汉字前半），末 8 字
    assert pl.jp_tail(s) == "よろしく漢字ね"[-8:]

def test_edit_distance_basic():
    assert pl.edit_distance("abc", "abc") == 0
    assert pl.edit_distance("abc", "axc") == 1
    assert pl.edit_distance("", "abc") == 3

def test_autoclear_limit_floor_and_ratio():
    assert pl.autoclear_limit("四字") == 4            # floor
    assert pl.autoclear_limit("十" * 100) == 15       # 100×0.15
```

- [ ] **Step 3: 跑测确认失败** — `uv run pytest tests/test_polishlib.py -q` → FAIL (no module)

- [ ] **Step 4: 实现 tools/polishlib.py**

```python
"""P4 润色 pass 公共层：配置、路径、回执尾串、编辑距离。"""
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO

RUBY_RE = re.compile(r"<([^,<>]+),[^,<>]+>")
CTL_RE = re.compile(r"_[nr]")

def _load_cfg():
    import yaml
    return yaml.safe_load((REPO / "config" / "polish.yaml").read_text(encoding="utf-8"))

CFG = _load_cfg()

def seg_dir(label) -> Path:
    return REPO / "pilot" / "polish" / label

def strip_ctl(s: str) -> str:
    return CTL_RE.sub("", RUBY_RE.sub(lambda m: m.group(1), s or ""))

def jp_tail(s: str, n: int = None) -> str:
    return strip_ctl(s)[-(n or CFG["jp_tail_n"]):]

def edit_distance(a: str, b: str) -> int:
    # difflib opcodes：replace 记 max(删,插)，insert/delete 记其长——字符级近似 Levenshtein，
    # 用途只是「幅度分档」，不需要严格最优解。
    d = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "replace":
            d += max(i2 - i1, j2 - j1)
        elif tag in ("delete", "insert"):
            d += (i2 - i1) + (j2 - j1)
    return d

def autoclear_limit(opus_zh: str) -> int:
    return max(CFG["autoclear_abs"], int(len(strip_ctl(opus_zh)) * CFG["autoclear_ratio"]))
```

- [ ] **Step 5: 跑测通过 + 变异自检**

Run: `uv run pytest tests/test_polishlib.py -q` → 4 passed。
变异（各改一处→对应测试必须红→还原）：①`autoclear_abs` 取 0；②`edit_distance` 的 replace 记 min；③`jp_tail` 不剥 ruby。

- [ ] **Step 6: Commit**

```bash
git add config/polish.yaml tools/polishlib.py tests/test_polishlib.py
git commit -m "feat: P4 润色公共层 polishlib + 集中阈值配置"
```

---

