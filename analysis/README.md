# analysis/ — 脚本分析产物归档

2026-07-30 全量通读 `lua_scripts/` 时生成的机械提取产物，供翻译工具开发与后续会话直接查阅（免于重读 3.6MB lua）。全部可由 `tools/` 下脚本从 lua 源一键重新生成，lua 有改动后应重跑。

| 文件 | 生成命令 | 内容 |
|---|---|---|
| `dag_all.txt` | `python3 tools/extract_dag.py > analysis/dag_all.txt` | 全部 23 个章节剧本 `main()` 调度器的场景图：每个场景节点的标题、转移、选择支（选项图片=>返回值）、routeHas/持卡条件、跨文件 RUN、ayanoTime 耗时、GAMEOVER/COMPLETE、听场景自动入手的关键词卡（GET_CARD）。**这是剧情 DAG 的机器可读权威快照。** |
| `crd_summary.txt` | `python3 tools/extract_crd.py > analysis/crd_summary.txt` | 196 个卡片谜题脚本一览：STUB 与否、前置卡（req）、答案卡（answersCmp 中 ≥2 的项）、获得卡（gets）、触发的 `_f` 章（runs）、做卡成功提示语（MSG）。 |
| `text_digest/` (228 个 .txt) | `python3 tools/extract_text.py` | 每个 lua 一份纯文本摘要：`### 函数名` 分节 + `[语音ID]文本` 的 vms 行 + `**CARD-GET:` 提示 + `== BEGIN` 场景头，滤除全部演出指令。共 17995 行，覆盖 16749 条 vms 文本，是人读剧情/喂 LLM 的首选形态（注意：`_n`/`_r`/ruby 等控制码保留原样）。 |

阅读顺序建议（剧情理解用）：`snr_s0_10_f`（序章）→ 各 `snr_s*_10_s`（故事层）→ 各 `_f`（现实层）→ `snr_s7_10_f`（真相章）→ `snr_s8_10_f` → `snr_e1_10_s` / `snr_e2_10_*`。世界观与 DAG 规则总述见仓库根 `CLAUDE.md`。
