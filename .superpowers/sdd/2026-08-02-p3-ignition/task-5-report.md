# Task 5 执行报告：opus/fable 车道 v7 再冻结

状态：**DONE**
commit：`a4fb603`

## Step 1：漂移预检

命令（逐字执行 brief 给定脚本）：

```bash
uv run python -c "
import sys, json, re; sys.path.insert(0,'.')
from tools.pipelib import REPO, sha256_file
rec=json.load(open('pilot/lanes/pilot-manifest.json',encoding='utf-8'))['lanes']['opus']
gmax=max((int(re.search(r'v(\d+)',p.stem).group(1)),p) for p in (REPO/'glossary').glob('glossary.v*.yaml'))[1]
now={'batches':sha256_file(REPO/'data'/'batches.jsonl'),'cards_zh':sha256_file(REPO/'skeleton'/'cards.zh.yaml'),
     'anchors':sha256_file(REPO/'skeleton'/'anchors.yaml'),'active':sha256_file(REPO/'glossary'/'active.json'),
     'glossary_max':sha256_file(gmax)}
bad=sorted(k for k,v in now.items() if v!=rec[k])
print('漂移字段:', bad)
assert bad==['active','anchors','glossary_max'], '漂移超出 v7 召回令范围，停下人工核查'
print('OK：恰为 v7 召回令三项（batches/cards_zh 未动），可安全 --force')
"
```

实际输出：

```
漂移字段: ['active', 'anchors', 'glossary_max']
OK：恰为 v7 召回令三项（batches/cards_zh 未动），可安全 --force
```

**结论：漂移恰为 v7 召回令三项（anchors/active/glossary_max），batches/cards_zh 未动，assert 通过，可安全 --force。** 未触发 BLOCKED 条件，继续 Step 2。

## Step 2：双车道 --force 重建 + verify

命令：

```bash
uv run python tools/lane_setup.py --lane opus  --model opus  --effort max  --append-model-id claude-opus-5  --force
uv run python tools/lane_setup.py --lane fable --model fable --effort high --append-model-id claude-fable-5 --force
uv run python tools/lane_setup.py --lane opus --verify
uv run python tools/lane_setup.py --lane fable --verify
```

实际输出：

```
/Users/fotile96/Zndnovel/pilot/lanes/opus: 车道就绪，冻结哈希已记入 /Users/fotile96/Zndnovel/pilot/lanes/pilot-manifest.json
/Users/fotile96/Zndnovel/pilot/lanes/fable: 车道就绪，冻结哈希已记入 /Users/fotile96/Zndnovel/pilot/lanes/pilot-manifest.json
冻结校验：无漂移
冻结校验：无漂移
```

**两次 verify 均为「冻结校验：无漂移」，与 Expected 一致。**

## Step 3：冻结内容抽验

命令：

```bash
uv run python -c "
import json, yaml
a=json.load(open('pilot/lanes/opus/glossary/active.json',encoding='utf-8'))
assert a['寝癖']=='睡翘' and a['十円玉']=='十日元硬币', a.get('寝癖')
d=yaml.safe_load(open('pilot/lanes/opus/skeleton/anchors.yaml',encoding='utf-8'))
ids=[i['id'] for c in d for i in c['items']]
assert 8478 in ids and 15775 in ids and len(ids)==122
print('车道 v7 冻结内容抽验 OK')
"
```

实际输出：

```
车道 v7 冻结内容抽验 OK
```

## Step 4：台账追记 + commit

- 在 `.superpowers/sdd/2026-07-31-p2-pilot-opus-run/progress.md` **尾部**（原文件末尾，即 batch 1 细节小节之后）原文照录追加了 brief 给定的「## P3 点火：车道 v7 再冻结」一节，未改动该文件已有的任何内容（仅追加，diff 为 +8/-1，其中 -1 是文件末尾原本缺失换行符的自然结果）。
- `uv run pytest -q` 实际输出：`219 passed in 1.39s`（与已知基线 219 一致，未变化）。
- `git status --short` 提交前只显示两处改动：
  ```
   M .superpowers/sdd/2026-07-31-p2-pilot-opus-run/progress.md
   M pilot/lanes/pilot-manifest.json
  ```
  未产生任何 `tools/`、`tests/`、代码类变更。
- `git add pilot/lanes/pilot-manifest.json .superpowers/sdd/2026-07-31-p2-pilot-opus-run/progress.md`：命令行提示了一条 "The following paths are ignored by one of your .gitignore files" 的 hint（对 `.superpowers/sdd/2026-07-31-p2-pilot-opus-run` 目录本身，因为 `.superpowers/` 整体 gitignore），但 `progress.md` 早已被 git 跟踪（历史上 `git add -f` 过），`git status`/`git diff --cached --stat` 确认两个文件都已正确进入暂存区（未使用 `-f`，按 brief 预期路径）：
  ```
   .superpowers/sdd/2026-07-31-p2-pilot-opus-run/progress.md | 7 +++++++
   pilot/lanes/pilot-manifest.json                           | 2 +-
   2 files changed, 8 insertions(+), 1 deletion(-)
  ```
- 提交：`git commit -m "chore: 车道再冻结至 glossary v7（P3 首次段边界版本切换）"` → commit `a4fb603`。
- 提交后 `git status --short` 输出为空（working tree clean）。

## 偏差与处理

无偏差。所有步骤按 brief 逐字执行，assert/expected 全部满足，未触发任何 BLOCKED 分支。`git add -A`/`git add .` 均未使用，仅按 brief 指定的两个路径提交。车道内 gitignore 的 `skeleton/`/`glossary/`/`work/` 冻结拷贝按预期被 `--force` 重写，未进入本次 commit。
