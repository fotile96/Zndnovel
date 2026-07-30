# skeleton/ — 翻译骨架（P0 产物，冻结后 tag skeleton-v1）

- `cards.jp/batch_XX.yaml`   卡面日文转写分批文件（P0 计划·规程 A 产出）
- `cards.jp.yaml`            合并后的转写总表（Task 13 生成）
- `cards.zh/batch_XX.yaml`   中文卡组分批文件（规程 B 产出）
- `cards.zh.yaml`            合并后的中文卡组（Task 18 生成；卡面图片汉化的文案源）
- `anchors.yaml`             伏笔锚点行：`[{chapter, items: [{id, jp, zh, recall}]}]`

条目 schema 见各批文件头注释与 `docs/superpowers/plans/2026-07-30-p0-skeleton.md`。
skeleton-v1 冻结后的一切修改需升版本号并评估受影响的已译内容（见 spec §4）。
