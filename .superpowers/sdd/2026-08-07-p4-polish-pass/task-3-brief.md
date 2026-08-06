### Task 3: tools/polish_setup.py（SEG 冻结）

**Files:**
- Create: `tools/polish_setup.py`
- Test: `tests/test_polish_setup.py`

**Interfaces:**
- Consumes: `config/segments.yaml`（段表批号）、`data/batches.jsonl`、opus 车道 `ledger.jsonl/forward.jsonl/patches.jsonl/notes/`、`resolve.resolve_map`、`skeleton/anchors.yaml`、`build_context.glossary_version`
- Produces:
  - `setup(label, opus_data, repo=None) -> Path`：建 `pilot/polish/<label>/frozen/` + `manifest.json`
  - frozen 内容：`source.jsonl`（{id, jp, batch}，按段表批号从 ledger 取）、`opus.jsonl`（{id, zh}，resolve 固化）、`locked.json`（锁定 id 清单+来源）、`glossary/`（active.json+voices/+style.md+polish.md+anchors.yaml 拷贝）、`notes/`（该段批号的 notes 拷贝）、`rulings.md`（占位骨架，人工/放大纪要追加）
  - `manifest.json`：`{label, batches, glossary_v, files: {rel: sha256}, opus_at: {forward_lines, patches_lines, forward_sha, patches_sha}, ts}`
  - `verify(label) -> list`（frozen 逐文件哈希 ↔ manifest，漂移清单；空=绿）
  - `locked.json` 判据：段内 id ∩（anchors 全部 item id ∪ opus patches 已有 id）
- CLI: `--seg <label> --opus-data <dir>`、`--verify <label>`

- [ ] **Step 1: 写失败测试**（tmp_path 造 mini 仓：2 批 4 行 ledger、1 条 anchor、1 条 patch）

```python
# tests/test_polish_setup.py 核心断言
def test_setup_freezes_and_locks(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    src = {r["id"] for r in read_jsonl(d / "frozen" / "source.jsonl")}
    assert src == {10, 11, 12, 13}
    locked = json.loads((d / "frozen" / "locked.json").read_text())
    assert set(locked["ids"]) == {11, 13}          # 11=anchor, 13=已有 patch
    assert locked["why"]["11"] == "anchor" and locked["why"]["13"] == "patched"
    m = json.loads((d / "manifest.json").read_text())
    assert m["opus_at"]["patches_lines"] == 1

def test_opus_snapshot_is_resolved(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    opus = {r["id"]: r["zh"] for r in read_jsonl(d / "frozen" / "opus.jsonl")}
    assert opus[13] == "补丁后文本"                 # patch 覆盖 forward

def test_verify_detects_drift(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    assert ps.verify("segX", repo=mini_repo.root) == []
    (d / "frozen" / "opus.jsonl").write_text("坏")
    assert ps.verify("segX", repo=mini_repo.root) != []
```

- [ ] **Step 2: 跑测失败** → **Step 3: 实现**（骨架）

```python
def setup(label, opus_data, repo=None):
    repo = Path(repo or REPO)
    seg = _seg_entry(repo, label)                 # 读 config/segments.yaml
    lo, hi = seg["batches"]
    ids, id2batch = _seg_ids(repo, seg["lane"], lo, hi)     # data/batches.jsonl
    led = {r["id"]: r for r in read_jsonl(Path(opus_data) / "ledger.jsonl")}
    fwd = list(read_jsonl(Path(opus_data) / "forward.jsonl"))
    pat = list(read_jsonl(Path(opus_data) / "patches.jsonl")) if (...).exists() else []
    cur = resolve_map(fwd, pat)
    d = seg_dir(label); fz = d / "frozen"; fz.mkdir(parents=True)
    write_jsonl(fz / "source.jsonl", [{"id": i, "jp": led[i]["jp"], "batch": id2batch[i]} for i in ids])
    write_jsonl(fz / "opus.jsonl", [{"id": i, "zh": cur[i]} for i in ids])
    anchor_ids = _anchor_ids(repo)                # skeleton/anchors.yaml 全部 item id
    patched = {r["id"] for r in pat}
    locked = sorted(set(ids) & (anchor_ids | patched))
    (fz / "locked.json").write_text(dumps_locked(locked, anchor_ids, patched))
    _copy_glossary(repo, fz)                       # active.json/voices/style.md/polish.md/anchors.yaml
    _copy_notes(Path(opus_data) / "notes", fz / "notes", lo, hi)
    (fz / "rulings.md").write_text(f"# {label} 润色裁决与前序纪要\n（追加式）\n")
    manifest = {..., "files": {rel: sha256_file(p) for ...}, "opus_at": {...}}
    (d / "manifest.json").write_text(pipelib.dumps(manifest))
    return d
```
`verify(label)`：重算 frozen 逐文件 sha256 与 manifest 比对，返回漂移相对路径列表。

- [ ] **Step 4: 跑测通过 + 变异**：①locked 漏并 anchor 集；②opus.jsonl 直接抄 forward 不走 resolve；③verify 恒返回 []（三个变异各自必须打红对应测试）。

- [ ] **Step 5: Commit** — `feat: polish_setup——SEG 级冻结+锁定面+opus 固化时点`

---

