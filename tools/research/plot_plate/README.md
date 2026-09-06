# tools/research/plot_plate — `png/plot/` 缩略图「干净底板」重建研究

> 研究脚本，**不在构建链路上**。产出与结论见 `docs/ops/plot-plate-research-2026-09-07.md`。
> 依赖 numpy（未入 pyproject，用 `uv run --with numpy python …` 临时带入）。

| 脚本 | 做什么 | 产物 |
|---|---|---|
| `plot_recon.py` | 模块：场景函数图层操作解析（`parse_ops`/`state_after`）、合成（`compose`）、BILINEAR 缩到 82×48（`thumb`）、无字行最小二乘色调拟合（`fit`）、卡→场景表 | — |
| `survey.py` | 195 卡普查：配方合成在场景内各状态取最优 vs 暴力单图（全部 bg/event） | `build/research/plot_plate/survey.json` |
| `refine.py` | 对带立绘的难例做变体+位置坐标下降（先跑 survey） | `build/research/plot_plate/refine.json` |
| `probe_drive.py` | PPSSPP：直入场景后按时间序列截图（`build_disc.py --profile test --mode scene --scene <id>`） | `build/emu/drives/plot_probe/` |
| `walk_drive.py` | PPSSPP：直入场景逐句 CIRCLE 推进截图（建议加 `--no-cards`，否则先弹跳过询问） | `build/emu/drives/plot_walk/` |

```bash
uv run --with numpy python tools/research/plot_plate/survey.py > build/research/plot_plate/survey.txt
uv run --with numpy python tools/research/plot_plate/refine.py
```

判据口径：RMSE 只在**无字行**上算（标题 ≤7 字取 y≥14，≥8 字取 y≥26），色调按 `y = g·x + o` 逐格拟合；
sheet 本身是 256 色板，同一张图的量化地板约 RMSE 4。
