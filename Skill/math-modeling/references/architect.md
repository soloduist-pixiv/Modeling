# Architect — Problem analysis & solution space

**Role:** Modeling architect. Read the problem correctly; classify types; keep the menu inside valid mechanism families.  
**Do not:** Pretend experiments ran; pick a single “advanced” model this stage; write paper conclusions.

Load this file in **S1** (and when refreshing attribution questions mid-S2/S3).

---

## Problem understanding → `MyThought.md`

1. **Goal** — what to deliver (values, ranking, policy, class, explanation…)  
2. **Constraints** — statement hard constraints + resource limits  
3. **Data** — what exists / what does not (never conclude on missing variables)  
4. **Hidden assumptions** — list as “to test”  
5. **Success criteria** — preregister primary/secondary metrics, Pareto weights intent, threshold δ  
6. **答題清单** — each subquestion → a checkable deliverable  

Principle: simple-but-explained first — can a minimal model answer the statement?

---

## Problem Classifier

Classify **per atomic subquestion** before “at least three schemes.”

| Type | Typical ask | Candidate families (must cross families) | Audit focus |
|------|-------------|------------------------------------------|-------------|
| **A Predict** | forecast / missing | naive/mean; linear·ARIMA·Prophet; trees; sequence DL last | **time leakage**, holdout |
| **B Evaluate** | rank / score | equal weights; entropy/CV; AHP (justify subjectivity); PCA+TOPSIS | weight stability |
| **C Optimize** | min/max / schedule | greedy/analytic; LP/MILP; metaheuristics | real constraints, feasibility |
| **D Mechanism** | association / effect | contingency/correlation; regression; quasi-exp; structural | correlation≠causation |
| **E Classify** | type / identity | threshold rules; LDA/Logistic; trees/RF | interpretability vs black box |
| **F Association** | variable network | Spearman; partial corr; compositional CLR | spurious composition corr |
| **G Simulation** | process dynamics | ODE/diff eq; CA/Agent; Monte Carlo | identifiability, validation data |

```markdown
## 题型分类
- 原子问题 Q1：类型 X；答題交付物：…
- 候选池（跨族）：族1 … / 族2 … / 族3 …
- 禁止的伪三方案示例：…
- 本题审查重点：…
```

### Fake-triple blacklist

- Linear / Ridge / Lasso  
- RF / XGBoost / LightGBM with no mechanism difference  
- Same evaluation method, only aggregator changed  
- Three DL variants with no baseline  

---

## Three-family menu

Pick **≥3 different mechanism families**:

| Seat | Meaning |
|------|---------|
| A | Baseline family (aligned with Experiment baseline) |
| B | Classic improvement targeting A’s clear flaw |
| C | Contrast family (another tool or simpler tier; innovation must state gain hypothesis vs A/B) |

```markdown
### 方案 X（机制族：…）
- 回答题面哪一问：
- 核心假设：
- 方法：
- 相对基线拟解决的问题：
- 固有局限：
- Failure Modes：
- 复杂度预估：低/中/高
- 若失败是否退回基线：是
```

---

## Attribution question list (before comparing results)

1. If A and B diverge on the primary metric, suspect first: assumption / features / leakage / objective?  
2. Which extreme should make them agree? Which disagree?  
3. After deleting statement-unnecessary modules, can we still answer the question?

After results:

> Name **which assumption / step / data use** caused the split; support with sensitivity or ablation.

Decision line:

> Deepen __ because attribution shows __; keep __ as paper contrast in section __.

---

## Handoff to Experiment

Bundle: types + 答題清单, preregistered metrics δ, baseline suggestion, three-family menu + Failure Modes, attribution list.  
No typed 答題清单 → **no** complex-model experiments.

### Autonomy

Write artifacts and hand off immediately. Mutually exclusive readings → escalate **hard block** once; otherwise do not ask which scheme to pick.
