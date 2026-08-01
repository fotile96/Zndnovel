### Task 5: opus/fable 车道 v7 再冻结（P3 首次段边界版本切换）

**Files:**
- Modify: `pilot/lanes/pilot-manifest.json`（lane_setup 重写）、`pilot/lanes/*/lane.json`（不变）、车道 `skeleton//glossary/` 冻结拷贝（gitignore，不入库）
- 记录: `.superpowers/sdd/2026-07-31-p2-pilot-opus-run/progress.md` 尾部追记

**Interfaces:**
- Consumes: `tools/lane_setup.py --lane L --model M --effort E --append-model-id A --force` 与 `--lane L --verify`；漂移安全检查脚本（handoff-task46.md §环境重建的哈希比对，此处复用其逻辑）。
- Produces: 两条车道冻结拷贝更新到 v7（anchors 122 条、active 24 条、glossary.v7），manifest 记录新哈希。**b36 起的批次在 v7 基准下生产**；b1–35 在 v6 下生产的事实由 progress.md 追记留痕（spec §2「manifest 记录每批版本号」在现阶段以「段边界＝版本切换点＝git 留痕」满足，不改 manifest schema——YAGNI，等真出现段中切换需求再说）。

- [ ] **Step 1: 漂移预检（确认漂移恰为 v7 召回令五文件）**

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
Expected: `OK`。若 assert 失败——有 v7 之外的未知改动，**停止本任务**，人工比对后再继续。

- [ ] **Step 2: 双车道 --force 重建 + verify**

```bash
uv run python tools/lane_setup.py --lane opus  --model opus  --effort max  --append-model-id claude-opus-5  --force
uv run python tools/lane_setup.py --lane fable --model fable --effort high --append-model-id claude-fable-5 --force
uv run python tools/lane_setup.py --lane opus --verify
uv run python tools/lane_setup.py --lane fable --verify
```
Expected: 两次 verify 均「冻结校验：无漂移」。

- [ ] **Step 3: 冻结内容抽验**

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
Expected: OK。

- [ ] **Step 4: 台账追记 + commit**

在 `.superpowers/sdd/2026-07-31-p2-pilot-opus-run/progress.md` 尾部追加一节（原文照录）：

```markdown
## P3 点火：车道 v7 再冻结（2026-08-02 之后的首个工作日执行）

P3 首次段边界版本切换：b1–35 在 v6 冻结下生产（证据链见上文），b36 起在 v7 下生产。
漂移预检确认仓库侧漂移恰为 v7 召回令三项（anchors/active/glossary_max），双车道
`lane_setup --force` 重建后 verify 无漂移；冻结内容抽验（寝癖=睡翘、十円玉、锚点
122 条含 8478/15775）通过。fable 车道同步冻到 v7（P4 启动时将再冻至 v8）。
```

```bash
uv run pytest -q   # 期望仍全绿
git add pilot/lanes/pilot-manifest.json .superpowers/sdd/2026-07-31-p2-pilot-opus-run/progress.md
git commit -m "chore: 车道再冻结至 glossary v7（P3 首次段边界版本切换）"
```

---

