# Delivery.md — 终稿包

## 一页过程摘要

对 2016 国赛 A 题系泊系统，完成 S1–S5 自治管线：三类跨族方案（离散静力 / 悬链对照 / 约束网格）→ 基线实验与 hold-out → 红队与 Freeze `2016A-mooring-F1` → 论文 R1–R5。主结论：Q1 给出 12/24 m/s 全套状态；Q2 最小球重约 2238 kg；Q3 推荐 V/22.05 m/5000 kg。

## 六件套索引

| # | 交付物 | 路径 |
|---|--------|------|
| 1 | 全文（LaTeX + PDF + Markdown） | `paper/paper.tex`，`paper/paper.pdf`，`paper/main.md` |
| 2 | Freeze + results | `Freeze.md`, `results/` |
| 3 | 叙事审计 | `NarrativeAudit.md` |
| 4 | 缺陷–局限映射 | `DefectMap.md` |
| 5 | 评委报告 | `JudgeReport.md` |
| 6 | 完成度自检 | 见下 |

## 完成度自检

| 门槛项 | 通过 | 备注 |
|--------|------|------|
| 每子问有节+可追溯数 | 是 | §5.1–5.3 |
| 摘要含方法+主数+局限 | 是 | |
| 基线对照 | 是 | A vs B |
| 假设+放松后果 | 是 | §三 |
| Checks≥2 | 是 | §六 |
| 优缺非只扬 | 是 | §七 |
| 叙事审计干净 | 是 | |
| Judge 通过 | 是 | 套模风险低 |
| 无 Freeze 外改数 | 是 | |
| 无完美/绝对用语 | 是 | |

Budgets: write_round=5/5  experiment_rewind=0/1

## 复现

```bash
cd work/2016A-mooring
python3 code/mooring_solve.py
python3 code/make_figures.py
python3 code/cross_branch_supplement.py   # 可选：对照/27工况复核
cd paper && xelatex paper.tex && xelatex paper.tex
```

## 图表清单（已编入 `paper.tex`）

| 类型 | 文件 / 表号 |
|------|-------------|
| 图 | `fig_chain_shape` 锚链形状；`fig_family_contrast` 族对照；`fig_ball_sweep` 球重扫描；`fig_q3_scenarios` 问题3情景 |
| 表 | 答題清单、方案池、Q1状态、钢管倾角、Q2球重、Q3情景、Pareto备选、符号表 |
