# 终稿包 — 2016A 系泊系统

## 交付清单

| # | 文件 | 说明 |
|---|------|------|
| 1 | `paper/main.md` | 完整论文 |
| 2 | `Freeze.md` + `results/` | 冻结模型与数值 |
| 3 | `NarrativeAudit.md` | 叙事审计（通过） |
| 4 | `DefectMap.md` | 缺陷→局限映射 |
| 5 | `JudgeReport.md` | 评审（通过） |
| 6 | 本文件 | 包索引 |

## 核心结论（一页）

- **题1**：12 m/s → 钢桶 1.11°，半径 14.34 m；24 m/s → 4.44°，17.53 m
- **题2**：36 m/s 需重物球 **1973 kg**
- **题3**：推荐 **V 型链 26 m + 球 4500 kg**

## 复现

```bash
pip install numpy scipy pymupdf
cd work/2_系泊系统/code && python3 mooring_solver.py
```

## 过程摘要

S1 问题分析 → S2 M0/M1/M2 实验 → S3 红队+Pareto 冻结 → S4 论文五轮 → S5 打包。
