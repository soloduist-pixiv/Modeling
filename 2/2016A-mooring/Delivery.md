# Delivery.md — 终稿包（F2 修订）

## 一页过程摘要

对 2016 国赛 A 题系泊系统，在 F1 基础上完成力学与设计修订（F2）：分段水平张力递推、整数链节、Q3 Pareto + 软裕度 + 稠密扫描，并润色论文。主结论：Q1 给出 12/24 m/s 全套状态；Q2 最小球重 **2238 kg**；Q3 推荐 **IV / 28.05 m（187 节）/ 5000 kg**。

## 六件套索引

| # | 交付物 | 路径 |
|---|--------|------|
| 1 | 全文 | `paper/main.md` |
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
| 无 Freeze 外改数 | 是 | F2 |
| 无完美/绝对用语 | 是 | |

Budgets: write_round=5/5  experiment_rewind=1/1（本轮为力学修正回跳）

## 复现

```bash
cd 2/2016A-mooring
python3 code/mooring_solve.py      # 同时写出 metrics.json 与 results_tables.xlsx
python3 code/make_figures.py
python3 code/export_xlsx.py       # 若仅需重导 Excel
cd paper && xelatex paper.tex && xelatex paper.tex
```

排版论文：`paper/paper.tex` → `paper/paper.pdf`；结果表：`results/results_tables.xlsx`。
