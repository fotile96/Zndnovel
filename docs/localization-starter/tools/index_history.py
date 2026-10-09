#!/usr/bin/env python3
"""Export reachable commit metadata and per-commit file changes (stdlib only).

This is an evidence index, not an automated semantic review of every diff.
Merge changes are measured against the first parent; ordinary commits against
their parent; root commits against the empty tree. Renames use Git detection.
"""
import argparse
import collections
import json
import subprocess
from pathlib import Path


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def changes(repo, commit, parents):
    args = ["diff-tree", "--no-commit-id", "-r", "-M", "--name-status", "-z"]
    args += [parents[0], commit] if parents else ["--root", commit]
    tokens = git(repo, *args).decode("utf-8", "surrogateescape").split("\0")
    result = []
    i = 0
    while i < len(tokens) and tokens[i]:
        status, path = tokens[i:i + 2]
        i += 2
        item = {"status": status, "path": path}
        if status[0] in "RC":
            item["old_path"] = path
            item["path"] = tokens[i]
            i += 1
        result.append(item)
    return result


def spec(path):
    return path.endswith(".md") and (
        "/specs/" in path or "/bake-specs/" in path or
        Path(path).stem.endswith(("-spec", "-design", "-runbook")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    revision = git(args.repo, "rev-parse", "--verify", args.revision + "^{commit}").decode().strip()
    commits = git(args.repo, "rev-list", "--reverse", "--topo-order", revision).decode().splitlines()
    records = []
    for commit in commits:
        fields = git(args.repo, "show", "-s", "--format=%H%x00%P%x00%aI%x00%cI%x00%s", commit).decode().rstrip("\n").split("\0")
        sha, parent_text, authored, committed, subject = fields
        parents = parent_text.split()
        files = changes(args.repo, sha, parents)
        records.append({"sha": sha, "parents": parents, "authored": authored,
                        "committed": committed, "subject": subject, "files": files,
                        "specs_added": [f["path"] for f in files if f["status"] == "A" and spec(f["path"])],
                        "tools_added": [f["path"] for f in files if f["status"] == "A" and f["path"].startswith("tools/") and f["path"].endswith((".py", ".sh", ".js", ".html"))]})
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "commits.json").write_text(json.dumps({"revision": revision, "order": "reverse topological", "merge_diff": "first parent", "commits": records}, ensure_ascii=False, indent=2) + "\n")
    lines = ["# 逐 commit 证据索引", "", f"固定基线：`{revision}`；共 {len(records)} 个 reachable commit，含 merge。", "",
             "按反向拓扑顺序列出；日期为作者日期，不是投入工时。变更按父提交对比，merge 按第一父提交；A/M/D/R 为 Git 状态。", "",
             "每项的‘做了什么’保留提交标题；规格/工装新增来自真实文件增量，完整路径状态见 commits.json。它不是逐 diff 语义审计。", "",
             "查看细节：`git show <sha> -- <path>`。历史路径可能已迁移或删除。", ""]
    for n, r in enumerate(records, 1):
        lines += [f"## {n:04d} · {r['sha'][:7]} · {r['authored'][:10]}", "", r["subject"], ""]
        counts = collections.Counter(f["path"].split("/")[0] for f in r["files"])
        lines += [f"- 变更：{len(r['files'])} 个路径；" + "、".join(f"{k} {v}" for k, v in sorted(counts.items())),
                  "- 新增规格/运行手册：" + ("、".join(f"`{p}`" for p in r["specs_added"]) or "无"),
                  "- 新增工装入口/模块：" + ("、".join(f"`{p}`" for p in r["tools_added"]) or "无")]
        focus = [f for f in r["files"] if f["path"].startswith(("tools/", "prompts/", "config/", "docs/superpowers/specs/", "docs/superpowers/plans/")) and not f["path"].lower().endswith((".png", ".jpg", ".pdf"))]
        if focus:
            lines += ["- 相关实现/计划变更：" + "、".join(f"{f['status']} `{f['path']}`" for f in focus)]
        lines += [""]
    (args.out / "commit-index.md").write_text("\n".join(lines))
    additions = ["# 规格与工装新增时间表", "", "仅列实际 A 状态；后续修改请按路径查完整索引。规格识别按路径/文件名，实施计划列在逐提交索引中。", "", "| 日期 | commit | 类别 | 路径 |", "|---|---|---|---|"]
    for r in records:
        for key, label in [("specs_added", "规格/手册"), ("tools_added", "工装")]:
            additions += [f"| {r['authored'][:10]} | `{r['sha'][:7]}` | {label} | `{p}` |" for p in r[key]]
    (args.out / "additions.md").write_text("\n".join(additions) + "\n")
    print(json.dumps({"revision": revision, "commits": len(records), "file_changes": sum(len(r["files"]) for r in records), "spec_additions": sum(len(r["specs_added"]) for r in records), "tool_additions": sum(len(r["tools_added"]) for r in records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
