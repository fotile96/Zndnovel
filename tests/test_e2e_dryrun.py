"""端到端 dry-run：build_context → 假草稿 → check_batch，在真实 data/ 上跑通整条回路。

注意：本测试会写真实的 work/ctx/batch_1/ 与 work/out/batch_1.draft.jsonl（不是
tmp_path 隔离的临时文件）——这是 build_context.py / check_batch.py 的既有行为
（两者都固定写 REPO/work/ 下的路径，不接受输出目录参数）。work/ 已在 .gitignore，
产物不入库；tmp_path fixture 参数保留只是未被使用。
"""
import json, re, subprocess, sys
from tools.pipelib import REPO, WORK, read_jsonl

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
    r = subprocess.run([sys.executable, "tools/build_context.py",
                        "--batch", "1", "--profile", "cc", "--jp-fallback"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    src = read_jsonl(WORK / "ctx" / "batch_1" / "source.jsonl")
    draft = [{"id": row["id"], "zh": _placeholder(row["jp"])} for row in src]
    (WORK / "out").mkdir(parents=True, exist_ok=True)
    (WORK / "out" / "batch_1.draft.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in draft) + "\n",
        encoding="utf-8")
    r2 = subprocess.run([sys.executable, "tools/check_batch.py", "--batch", "1"],
                        cwd=REPO, capture_output=True, text=True)
    # 占位译文可能触发软警但硬规则应可通过（【】/符号照抄自 jp）
    assert r2.returncode == 0, r2.stdout + r2.stderr
