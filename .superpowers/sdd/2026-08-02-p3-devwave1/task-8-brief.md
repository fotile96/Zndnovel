### Task 8: SEG-1 题库 + 用户抽核 + 连通冒烟

**Files:**
- Create: `config/ayano_qa/seg1-s2.yaml`

**Interfaces:**
- Consumes: `analysis/text_digest/` 中 s2 相关摘要（`snr_s2_10_s.txt`、`snr_s2_10_f.txt` 及 SEG-1 涉及的 crd 摘要）、`analysis/dag_all.txt` s2 节、`CLAUDE.md` s2 章描述、`config/segments.yaml` seg1-s2 的 `review_focus`。
- Produces: 12–15 道剧情理解题，YAML 列表，条目 `{id: q<N>, question, reference, info_point}`。出题纪律：**①答案必须能仅凭「卡组梗概 + s2 段中文正文」推出**（受试者看不到日文原文与其他章正文）；②覆盖 review_focus 列的机关（ナゾトキ 选择迷宫因果、s2s_390 夜晚成立三条件、周末プール/プラネタリウム伏笔、s2f 现实层框架）；③至少 3 题针对「只靠梗概续听的人最容易丢的信息」（指代关系、时间线先后、称呼变化）；④**不得剧透 s2 之后的真相**（题面与标准答案都不得包含 s7f 揭示内容——雪乃、坠楼真相、原型错位等字样一律禁止）。

- [ ] **Step 1: 生成题库**

读上述材料，写 `config/ayano_qa/seg1-s2.yaml`。格式示例（内容按实际材料出，此处仅示意结构）：

```yaml
# 彩野测试题库 · seg1-s2（12–15 题）。出题纪律见 plan Task 8；答案以段内译文+卡组梗概可推为准。
- id: q1
  question: 两人约定周末要去的候选地点有哪两个？最后倾向哪个？
  reference: 游泳池和天象馆（プラネタリウム）……（按译文实际措辞）
  info_point: s2 周末去处伏笔（review_focus 指定项）
```

- [ ] **Step 2: 结构自检**

```bash
uv run python -c "
import yaml
qa=yaml.safe_load(open('config/ayano_qa/seg1-s2.yaml',encoding='utf-8'))
assert 12<=len(qa)<=15, len(qa)
assert all(set(q)>= {'id','question','reference','info_point'} for q in qa)
ids=[q['id'] for q in qa]; assert len(ids)==len(set(ids))
banned=['雪乃','坠楼','原型','佐仓']
joined=str(qa)
assert not any(b in joined for b in banned), '剧透词命中'
print(f'OK：{len(qa)} 题，结构与剧透自检通过')
"
```

- [ ] **Step 3: 用户抽核 gate（不通过不 commit）**

把题库全文呈给用户抽核（题面+标准答案），说明每题对应的 info_point。用户要求修改则改后再呈，通过后才进 Step 4。**这是硬 gate，不得自行放行。**

- [ ] **Step 4: deepseek 连通冒烟（需要 key）**

先确认 key：`uv run python -c "from tools.api_client import load_env; import os; print('key 就绪' if os.environ.get('DEEPSEEK_API_KEY') or load_env().get('DEEPSEEK_API_KEY') else '无 key')"`
- 无 key：向用户要一次（写入仓库根 `.env`：`DEEPSEEK_API_KEY=sk-…`；提醒该文件已 gitignore）。用户暂不提供则本步记「跳过（无 key）」，不阻塞 commit。
- 有 key：`uv run python tools/api_client.py --prompt "回复两个字：连通" --purpose connectivity-smoke`
  Expected: 打印回复与 token 统计；`data/api_ledger.jsonl` 增一行（该文件首次出现，随本任务 commit 入库）。

- [ ] **Step 5: commit**

```bash
git add config/ayano_qa/seg1-s2.yaml
git add data/api_ledger.jsonl   # 仅当 Step 4 实际产生了它
git commit -m "data: 彩野测试 SEG-1 题库（用户抽核通过）+ deepseek 连通冒烟台账"
```

---

## Self-Review 记录

- **Spec 覆盖**：spec §6「1–3 周」行——降噪修理上生产的**代码侧**(T2)、API 管道+彩野测试 v0(T6/T7/T8)、预聚类 helper(T1)、F7(T3)；外加点火终审 parked 两项(T4)与 deferred 测试缺口(T5)。「滚 tag 上生产」本身是段边界运维动作，明确不在本 plan（Global Constraints ④）。
- **占位符**：T3 Step 4 与 T8 Step 1 属「调查后落码/按材料出题」型任务，已给出判据、决策树与结构模板而非 TBD；其余任务代码完整。
- **类型一致性**：`chat()` 签名在 T6 定义与 T7 消费一致（`transport/api_key/ledger_path` 贯穿）；`saturation()` 复用形态与 T1 调用一致；测试计数链 234→238→241→244→248→251→254→257（T3 计数含 1 条 timeline 测试，实际以报告为准）。
- **并行安全逐任务核**：T1/T5/T6/T7 纯新增或测试；T2 只影响钉死面外的 main 副本；T3 有生产安全预检与分支逃生门；T4 向后兼容 + 逐字节回归；T8 纯新数据文件。
