"""端到端 dry-run：build_context → 假草稿 → check_batch，在真实 data/ 上跑通整条回路。

Critical 1 修复轮：work/ 产物通过 ZND_WORK 环境变量重定向到 tmp_path（见
tools/pipelib.py 的 DATA/WORK 环境变量覆盖 + tools/build_context.py 消费
pipelib.WORK 而非固定的 repo/"work"），本测试因此完全 hermetic，不再写真实
work/ 树。ZND_DATA 刻意不设置——两个子进程仍读真实 data/ledger.jsonl、
data/batches.jsonl 等，这条测试的价值就在于跑真实数据，不是构造的小样本。
"""
import json, os, re, subprocess, sys
from tools.pipelib import REPO, read_jsonl

SPEAKERS = json.loads((REPO / "glossary" / "speakers.json").read_text(encoding="utf-8"))
SPEAKER = re.compile(r"^【([^】]*)】")

def _placeholder(jp: str) -> str:
    """假译文：行首【说话人】按 speakers.json 映射成译名（R2b 的硬性要求，
    是这份假草稿里唯一真正的“翻译”动作），占位标记插在其后，正文原样照抄
    （保住 R2a ruby 与 R2c 符号）。计划原文写的是 `"【占位】" + jp`，实测在真实
    数据上硬失败 R2b 151 条（双层【】）→ 改为标记后置又剩 19 条（非恒等映射的
    说话人：私→我、教師→教师），故补上这一次映射——三轮裁决详见 task-11-report.md。
    """
    m = SPEAKER.match(jp)
    if not m:
        return f"〔占位〕{jp}"
    name = SPEAKERS.get(m.group(1), m.group(1))
    return f"【{name}】〔占位〕{jp[m.end():]}"

def test_batch1_context_and_fake_roundtrip(tmp_path):
    # env= 会整体替换子进程环境，务必基于 os.environ 展开，不能只传 ZND_WORK 一项。
    env = {**os.environ, "ZND_WORK": str(tmp_path)}
    r = subprocess.run([sys.executable, "tools/build_context.py",
                        "--batch", "1", "--profile", "cc", "--jp-fallback"],
                       cwd=REPO, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    src = read_jsonl(tmp_path / "ctx" / "batch_1" / "source.jsonl")
    draft = [{"id": row["id"], "zh": _placeholder(row["jp"])} for row in src]
    (tmp_path / "out").mkdir(parents=True, exist_ok=True)
    (tmp_path / "out" / "batch_1.draft.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in draft) + "\n",
        encoding="utf-8")
    r2 = subprocess.run([sys.executable, "tools/check_batch.py", "--batch", "1"],
                        cwd=REPO, capture_output=True, text=True, env=env)
    # 占位译文可能触发软警但硬规则应可通过（【】/符号照抄自 jp）
    assert r2.returncode == 0, r2.stdout + r2.stderr
