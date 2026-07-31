### Task 8: prompts 三件（真实全文入库）

**Files:**
- Create: `prompts/translator_cc.md`、`prompts/reviewer_cc.md`、`prompts/api_system.md`

**Step 概要：**

- [ ] **Step 1**：`translator_cc.md` 全文（要点必须含：译者人设=本作骨架译者；先读 work/ctx/batch_N 三件；全知纪律引用 style.md；控制码硬规则（`_n/_r` 总量差≤2、ruby、【】按 speakers.json、≪≫≦≧○■ 保留）；输出 `work/out/batch_N.draft.jsonl` 行 `{"id","zh"}` 且 id 集合=source；**允许用工具**：rg forward.jsonl 查既有译法、查 analysis/text_digest 语境、看该场景 CG/立绘图；返回前自跑 `check_batch --batch N` 到 PASS；禁止 git commit；术语提案写入 `data/notes/<chapter>.md` 尾部）。
- [ ] **Step 2**：`reviewer_cc.md` 全文（对照 source jp 逐行挑刺：术语漂移/剧透措辞/控制码/口调表偏离；输出 verdict 列表 `{"id","verdict":"keep|fix","zh":…,"reason":…}` 到 `work/out/batch_N.review.jsonl`；不改 draft 本体）。
- [ ] **Step 3**：`api_system.md` 全文（api 后端 system 指令：revise 档按 keep/fix 输出、none 档全量输出；JSON lines 格式契约；控制码规则同上）。
- [ ] **Step 4**：`git add prompts/ && git commit -m "feat: 翻译/评审/API 三份 prompt 模板"`

（三份模板的完整文案由执行者按上述要点撰写并在 PR 描述里贴出给用户过目——模板是 P2 试点的调参对象，首版不追求完美。）

---

