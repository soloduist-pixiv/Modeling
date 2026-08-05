# NarrativeAudit.md — F3

结论因子核验（每条论文主张 → 支撑变量 → 证据位置）：

| 结论 | 模型变量 | 证据 | 状态 |
|------|----------|------|------|
| Q1 12/24 m/s 的倾角、链形、吃水、游动区域 | θ, φ, grounded, d, R | `q1_q2_fixed_ball` / 表 1 | 通过 |
| 24→36 m/s 时 φ 从 4.66° 跳到 20.96° 是趴链耗尽所致 | grounded_length | `q1_q2_fixed_ball` 中趴链 6.25→0→0 | 通过 |
| Q2 最小球重 2238 kg，φ 为紧约束 | ball_mass, θ, φ | `q2_ball_search_A.binding="anchor"` | 通过 |
| Q2 数值应读作 "2.24 t 量级" | 离散偏差 0.101° | `grid_refinement` Richardson | 通过 |
| 球阻力与整条链的阻力同量级（678 vs 768 N） | F_ball, H_end−H | 图 3b 及其数据源 | 通过 |
| 球阻力只改 φ 不改 θ | ablation | `ablation_ball_drag`：Δφ=2.35°，Δθ=0.06° | 通过 |
| 吃水下界 1.643 m 与链型/链长/球重无关 | `draft_bound_for_barrel` | 命题 4.6 证明 + 图 5b 数值重合 | 通过 |
| S1 吃水 1.686 m 距下界仅 4.3 cm | max_draft vs bound | `q3_design.best` + `analytic_draft_bound` | 通过 |
| 前沿上所有方案吃水只差 2.4 cm | max_draft | `alt_min_draft` 1.668 vs `alt_min_swim` 1.692 | 通过 |
| 最劣角点归约成立 | 单调性 + 稠密扫描 | `monotonicity` 表 + `dense_hard_fail=0`，最劣值一致 | 通过 |
| S1 夺魁率仅 17.3%，非唯一最优 | win_rate | `ranked_pareto` | 通过（措辞已弱化） |
| S1 在参数扰动下满足率仅 32.5% | reliability | `verification.reliability` | 通过 |
| S1′ 4930 kg 使满足率达 98.8% | reliability_based | `verification.reliability_based` | 通过 |
| S2 干舷 0.777 m，包络内 θ≤5° 占 82.1% | envelope | `q3_relaxed.best.envelope` | 通过 |
| 加重球不显著增大游动半径 | 反事实 | `q2_ball_sweep`：R 仅变 16% 且非单调 | 通过 |
| 守恒残差 <1e-9 | residual | 每条 `result_to_public.residual` | 通过 |

## 措辞检查

- 未使用"完美""绝对""最优解唯一"等表述；S1 一律称"名义最优 / TOPSIS 首位"。
- 三处主动弱化：Q2 有效数字、S1 夺魁率、S1 干舷可用性。
- 无 Freeze 外改数：正文全部数值可在 `results/metrics.json` 中按键名定位。
- 图文一致性：F2 中"推荐点在 Pareto 图上被支配"的图文矛盾已消除（改画真实取舍面）。
