"""polish.md 里**可机械检测、但不可机械改写**的细则，全库清点。

## 与 `tools/sweep_punct.py` 的分工（不要搞混）

`sweep_punct.py` 是**改写器**：§7(a)「句末 `……。` 删句号」是纯删一个字符，
删了不影响别的东西，所以它直接写 patch。本模块是**检测器**：这里的每条规则
命中之后都需要**重写整句**（换语序会连带动读点、动重心、动主语），机械替换
一定出错，所以本模块**永不写任何文件**，只出清单给人裁。

这个分工是有代价换来的：SEG-3 曾经出过「采纳了撑破 W3 的稿」的事故，根因就是
把「能检测」当成了「能自动处理」。**能检测 ≠ 能自动改**——本模块存在的意义
就是给「只能检测」的那一类规则一个正式的落脚点，而不是让它们散落在一次性脚本里。

## 现有规则

| 规则 | 出处 | 为什么不能自动改 |
|---|---|---|
| `S9b-order` | polish.md §9(b) | 「X和我」→「我和X」换位后，原来的读点位置往往就不对了（#15744 换位后要连删两个读点），且极少数原文真在强调对方，得看上下文 |
| `S7a-mid` | polish.md §7(a) | 行中的 `……。` 是判断题：真是「顿住了，然后说」就该留。用户 2026-08-13 明确暂缓这一档，本规则只做计数不做主张 |
| `S7a-tail` | polish.md §7(a) | 句末 `……。` 的**残留**——`sweep_punct.py` 有意跳过了锚点行（改锚点要走 glossary 版本 + 召回令）。这里把残留列出来，免得「扫过了」被误读成「清干净了」 |

## 用法

```bash
uv run python tools/polish_lint.py --data-dir pilot/lanes/opus/data
uv run python tools/polish_lint.py --data-dir pilot/lanes/opus/data --rule S9b-order
```

退出码恒为 0——**本模块是台账不是闸**。有命中不代表有错（`S7a-mid` 整档都是
待议的），拿退出码去卡 CI 会把「待人裁」误判成「构建失败」。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, read_jsonl

# §9(b)：jp 把说话人摆在并列的后位，zh 也跟着摆在后位
_JP_COORD = re.compile(r"と(私|僕|俺|自分)")
_ZH_COORD = re.compile(r"(同学|老师|君|哥哥|姐姐|叔叔|阿姨|妈妈|爸爸|[ァ-ヶー]{2,8})和(我|我们)")
# §7(a)：`……。` 收在句末（行尾或换行控制码之前）
_TAIL = re.compile(r"……。(?=$|_n|_r)")


def _mid_tail_count(zh: str) -> int:
    """行中（非句末）的 `……。` 条数。"""
    return len(re.findall("……。", zh)) - len(_TAIL.findall(zh))


RULES = {
    "S9b-order": (
        "polish.md §9(b) 并列人称里「我」应在前",
        lambda jp, zh: bool(_JP_COORD.search(jp) and _ZH_COORD.search(zh)),
    ),
    "S7a-tail": (
        "polish.md §7(a) 句末 `……。` 残留（sweep_punct 有意跳过的锚点等）",
        lambda jp, zh: bool(_TAIL.search(zh)),
    ),
    "S7a-mid": (
        "polish.md §7(a) 行中 `……。`（B 档，判断题，用户暂缓）",
        lambda jp, zh: _mid_tail_count(zh) > 0,
    ),
}


def load(data_dir):
    """返回 {id: (jp, zh)}，zh 取车道现行（patches 覆盖 forward）。"""
    d = Path(data_dir)
    jp = {}
    for fn in ("ledger.jsonl", "ledger_extra.jsonl"):
        p = d / fn
        if p.exists():
            for r in read_jsonl(p):
                k = r.get("id", r.get("key"))
                if k is not None and r.get("jp"):
                    jp[k] = r["jp"]
    zh = {}
    for fn in ("forward.jsonl", "forward_extra.jsonl", "patches.jsonl"):
        p = d / fn
        if p.exists():
            for r in read_jsonl(p):
                k = r.get("id", r.get("key"))
                if k is not None and r.get("zh") is not None:
                    zh[k] = r["zh"]
    return {k: (jp[k], zh[k]) for k in jp if k in zh}


def lint(data_dir, rules=None):
    rows = load(data_dir)
    out = {}
    for name in (rules or RULES):
        _, pred = RULES[name]
        out[name] = [(k, *rows[k]) for k in sorted(rows, key=str) if pred(*rows[k])]
    return out


def render(res) -> str:
    L = ["# polish.md 可检测细则清点", "",
         "⚠ **命中不等于有错**——本清单里的每一条都要人看过原文才能定，",
         "本模块从不写任何文件。能检测 ≠ 能自动改。", ""]
    for name, hits in res.items():
        L.append(f"## {name} —— {RULES[name][0]}")
        L.append(f"命中 **{len(hits)}** 行")
        L.append("")
        for k, jp, zh in hits:
            L.append(f"- `[{k}]`")
            L.append(f"  - jp `{jp}`")
            L.append(f"  - zh `{zh}`")
        L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="polish.md 可机械检测细则的全库清点（只读）")
    ap.add_argument("--data-dir", required=True, help="车道 data/ 目录")
    ap.add_argument("--rule", action="append", choices=sorted(RULES),
                    help="只跑指定规则；可重复。缺省跑全部")
    ap.add_argument("--out", help="把报告同时写到文件")
    a = ap.parse_args(argv)

    res = lint(a.data_dir, a.rule)
    txt = render(res)
    print(txt)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
    return 0            # 恒 0：台账不是闸，见模块 docstring


if __name__ == "__main__":
    raise SystemExit(main())
