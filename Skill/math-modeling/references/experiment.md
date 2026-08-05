# Experiment — Audit, baseline, loop, freeze

**Role:** Algorithm engineer + experiment manager.  
**KPI:** Reproducible `results/`, gated comparison tables, `Freeze.md`.  
**Do not:** Flashy models without baseline; rewrite numbers for narrative; infinite module stacking.

> Complexity is driven by problem complexity.  
> **Baseline First:** cheapest model first; then ask where gains come from.

Load in **S2** (and on Judge/Critic rewind into experiments).

---

## Data Audit → `DataAudit.md`

1. n, dim, time span, missing/zero/outlier  
2. Sample grain vs label grain  
3. Statement validity rules (e.g. composition sum band) codifiable?  
4. Compositional / hierarchical / panel / text structure  
5. **Leakage surface:** future info, proxy labels, duplicate rows  
6. Enough descriptive stats to answer “can data support the ask?”

Incomplete audit → no formal complex training.

---

## Baseline First

| Type | Required cheap baseline (examples) |
|------|-------------------------------------|
| Predict | mean/naive → linear/ARIMA → RF → last: LSTM/TFT/Transformer |
| Evaluate | equal or given weights → entropy/PCA+TOPSIS |
| Optimize | greedy/relaxed LP → MILP → swarm last |
| Mechanism | corr/contingency/univariate → multivariate/DID |
| Classify | majority / single threshold → Logistic/tree → RF |

**Forbidden cold start:** Transformer, TFT, heavy ensembles, “innovation stacks” with no baseline.

### Baseline Gate (before complex model in main text)

1. Beat the simple model?  
2. By how much (same preregistered metric, side-by-side)?  
3. Gain from structure vs leakage/overfit?  
4. If complex fails or gain not worth it — **fall back to baseline** as main model?

Unanswered → complex model out of main text (appendix max).

---

## Experiment loop

- Fixed seeds; log deps; all runs (pass/fail) under `results/`  
- Shared metric definitions with Architect preregistration  
- Per scheme: primary/secondary + ≥1 diagnostic  
- Smoke extremes: key params →0 / boundary / heavy noise  

### Leakage scan

```markdown
## 数据泄漏扫描
1. 特征是否含未来信息？
2. 训练/测试是否污染（时序随机划分？重复样本？）
3. 标准化/编码是否在全量上 fit 再划分？
4. 目标编码 / 人工标签是否泄漏？
5. 时序是否 TimeSeriesSplit / 滚动持出？（禁止随机 train_test_split）
结论：通过 / 不通过（不通过则结果作废）
```

### Complexity budget

| Module | Claimed problem | Extra assumptions | Metric Δ | Cost | Δ if deleted |
|--------|-----------------|-------------------|----------|------|--------------|
| … | … | … | … | … | … |

Unchanged after delete → remove module. No “LightGBM+SHAP+LSTM+Transformer+Attention” as depth without per-module rows.

Per scheme: ≥2 on-the-spot critique questions (or mark for red-team).

---

## Pareto (anti infinite tune)

Dimensions (weights declared up front): **accuracy × interpretability × stability × complexity↓**

```markdown
## Pareto 决策
- M0：（精度, 解释, 稳定, 复杂度）
- M1：（…）
- M1 支配 M0？是 / 否
- 否 → 拒绝升级；记录不采用原因
- 是 → 可升级；保留 Failure Modes
```

Stop: two consecutive non-dominating candidates, or Δ accuracy < δ while hurting interpretability/stability/complexity → **Model Freeze**.

Bad results: bug → leakage → assumptions → baseline. Never fix with prose only.

---

## Model Freeze → `Freeze.md`

Required before S4 final narrative:

```markdown
# Model Freeze
- freeze_id：
- 日期/时间：
- 模型版本（名称与代码哈希或路径）：
- 数据版本（文件与筛选规则）：
- 参数与随机种子：
- 预注册评价指标与数值：
- 基线对照数值：
- 泄漏扫描：通过
- 复杂度审计：已附
- Pareto：当前支配者
- 明示局限：
```

After freeze: no changing model/split/metric/cherry-picked run for polish.  
Must change experiments → revoke freeze, new `freeze_id`, mark old card void.

---

## Handoff package

`results/` index, baseline vs candidates, leakage + complexity, ablation/sensitivity raw, `Freeze.md`.

### Autonomy

Silent disk progress; two Pareto stalls → auto Freeze → Writer.  
Critic/Judge revoke: experiment rewind ≤ **1** (see skill budgets). Unfixable env → hard block.
