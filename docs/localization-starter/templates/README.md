# 复制到下一项目的模板

这些是需要填写/实现的数据契约，不是可直接驱动本仓库现有命令的配置。`scene-packet.example.json` 和 `records.example.jsonl` 是虚构示例，没有真实采证；示例中的 hash/path 必须替换，不能当作已验证素材。

按 [第二版执行手册](../runbook-v2.md)开工时，先用 [开工任务书](v2/start-work.md)和 [项目控制表](v2/project-control.yaml)，再填 [试点记录](v2/pilot-record.md)。[编辑判例](v2/editorial-case.yaml)与[叙事约束示例](v2/narrative-constraint.example.yaml)分别记录语言取舍和叙事关系。根目录模板继续作为基础数据示例；`project.yaml` 是第一版配置骨架，不与第二版控制表同时维护为两个权威来源。

建议新仓库结构：

```text
source/                   原作只读基座或受指纹约束的外部路径
assets/                   原始图像/声音与清单
adapters/<engine>/        提取、语义解码、回写、运行取证
spec/project.yaml         范围与验收
data/source.jsonl         文本账本
data/scenes.jsonl         场景与分支/条件
data/occurrences.jsonl    每次运行的文本出现
data/families.jsonl       回声/术语/相似句关系
data/forward.jsonl        已接受初译
data/patches.jsonl        已裁决修订
data/effective.jsonl      可再生现行译文
glossary/                 术语、口调、风格、知识边界与版本
evidence/<run>/           日志、帧、短片、存档指纹与运行清单
contexts/<batch>/         不可变输入包与 manifest
candidates/<run>/         已封卷候选
decisions/                裁决与来源链
build/test/               测试产物
build/release/            发布产物与来源清单
```

小项目可先只实现 source、scene packet、forward、patches、effective、evidence 与一个人工裁决表。新项目无需空建所有目录。

| 文件 | 用途 |
|---|---|
| [project.yaml](project.yaml) | 范围、引擎、规则与验收配置骨架 |
| [scene-packet.example.json](scene-packet.example.json) | 带事实/推测/未知和玩家知识的场景包 |
| [records.example.jsonl](records.example.jsonl) | source/candidate/decision/patch 的关联示例 |
| [prompts.md](prompts.md) | 理解、初译、复核、验收四种任务模板 |
| [handoff.md](handoff.md) | 会话交接与恢复 |
| [acceptance.md](acceptance.md) | 试点/发版验收记录 |

最小实现合同：

- `extract(base)` 确定性地产出 source 与位置映射；未支持语法返回 unknown。
- `context(text_ids, occurrence, rules_revision)` 产出输入包及文件 hash 清单。
- `validate(candidate, context)` 返回规则状态、分母与证据；缺输入不能按 pass。
- `accept(validated_package)` 检查完成回执、内容 hash 与 expected-effective-hash，单写者落库。
- `resolve(source, forward, patches)` 纯函数；无译文、陈旧源版本和撤回分别处理。
- `export(base, effective, profile)` 原子写新产物；不改基座，不改未经授权的控制语义。
- `verify(build, checkpoints)` 产出平台/版本/路径覆盖与运行证据。

合同本身是新工程的接口目标，不意味着已经有对应 CLI。先实现一个引擎、一个场景，再泛化。

样例采用 `source_hash` 约束源版本、`baseline_hash` 约束候选所见旧译、`candidate_revision` 约束封卷版本。显示字符串生成后另记 occurrence；不以插值后的动态字符串取代原始模板。

候选状态建议：draft → sealed → validated → decided → accepted/rejected/deferred。accepted 后更改生成新事件；旧决定不被悄悄重写。
