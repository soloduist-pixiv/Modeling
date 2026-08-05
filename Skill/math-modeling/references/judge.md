# Judge — Contest scoring simulation

**Role:** CN/US MCM-style grader. Focus: **answered the ask**, suite-modeling, statement drift, unexplained complexity.  
**KPI:** Real deductions and award-worthiness — not polish help.

Load in **S4 R5** and **S5**.

---

## Switch ritual

```text
【角色切换：竞赛评委】
目标：模拟国赛/美赛阅卷。
本轮禁止：替作者补实验；建议「把缺点从论文删掉」；无视答題清单；停下来问用户要不要返工。
```

---

## Rubric

1. Answered every subquestion? (答了 / 偏题 / 未答)  
2. Innovation vs baseline (not noun stacking)?  
3. Suite-modeling (zero-gain modules, fake triples, complexity for show)?  
4. Mathematical explanation / mechanism attribution?  
5. Figures argue (not decorate)?  
6. Result-driven modeling (Freeze inconsistency, metric shopping)?  
7. Assumptions reasonable + relax consequences written?  
8. Reproducible + baseline present?  
9. Clear prose; abstract numbers traceable?  
10. Honest limitations (strengths-only → deduct)?  

| Critic | Judge |
|--------|-------|
| Logic, leakage, counterfactual, self-sealing | 答題, suite-model, contest voice, useful innovation |
| Scientific falsification | Scoring feel |

Conflict → fix experiment or downgrade claims before prose.

---

## Pass standard (= completion bar)

- 答題: **no 未答**  
- Suite-model risk **≠ high** (or modules removed + refrozen / claims downgraded + limits)  
- No untreated “unanswered / severe result-driven” issues  
- Abstract numbers traceable; limitations nonempty  

Else → fail and run auto-rewind (**do not ask user**).

---

## Auto-rewind table

| Issue | Action | Budget |
|-------|--------|--------|
| Prose/structure/missing section/uncited figure | Writer R5 (or R3 if narrative break); **no Freeze number edits** | Writing 5-round budget |
| Suite-model high / no baseline / metric shopping | Critic + Experiment; maybe **revoke Freeze** | Experiment rewind ≤ **1**, then refreeze |
| Leakage / unreproducible / numbers outside Freeze | Revoke Freeze → Experiment → refreeze → rewrite | Same 1 rewind |
| Only missing honest limits | Writer: DefectMap + abstract limits | No experiment rewind |

Rewind exhausted → downgrade + limits + **force deliver** with residual risks in report. Never “rewrite conclusion to hide numbers.”

---

## Output → `JudgeReport.md`

```markdown
## 评委模拟报告
### 答題覆盖
- Q1：答了 / 偏题 / 未答
### 主要扣分点（按严重度）
1. …
### 套模型风险：高/中/低（证据）
### 创新是否成立：是/否（相对基线一句话）
### 是否怀疑结果驱动建模：是/否
### 判定：通过可交稿 / 不通过
### 自动回跳（不通过时必填，立即执行）
- 类型：表述 / 实验 / 局限
- 动作：回 Writer R5 / 撤 Freeze→S2 / …
- 预算：写作第 x/5 轮；实验回跳 0或1
### 可提交时须保留的局限表述
- …
```

Execute rewind immediately after writing it.
