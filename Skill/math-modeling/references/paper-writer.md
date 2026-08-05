# Paper Writer — R1–R5 & completion bar

**Role:** Author. Narrate **frozen** evidence only.  
**Forbidden:** Silent metric edits; conclusions citing variables not in the model; final draft without Freeze.

Contest axes: reasonable assumptions, targeted innovation vs baseline, correct reproducible results, clear writing — **no credit for needless complexity**.

**Autonomy:** R1→R5 in one session; no “should I revise?”. Cap 5 rounds → downgrade + limits + **force deliver**.

Load in **S4**. For R5, also load [judge.md](judge.md).

---

## Preconditions

- [ ] `Freeze.md` exists (else back to Experiment)  
- [ ] 答題清单 finalized  
- [ ] `RedTeam.md` exists (open items → limitations)  

---

## Narrative consistency audit

```
研究问题 → 变量 → 模型 → 结果 → 结论
```

```markdown
## 叙事一致性审计
| 结论句中的声称 | 变量存在？ | 进入模型？ | 表/图指针 | 通过？ |
|----------------|------------|------------|-----------|--------|
| … | … | … | … | 否→删除 |

规则：变量未体现 → 禁止写该结论。
```

Map every subquestion to a section + evidence. Save as `NarrativeAudit.md`.

---

## Mandatory passes R1–R5

No self-praise in the same turn as drafting. Use Critic/Judge rituals when switching.

| Pass | Action | Exit check |
|------|--------|------------|
| **R1 Skeleton** | Full TOC from 答題清单; Freeze number/figure placeholders | Every subquestion has a section |
| **R2 Evidence** | Tables first; all primary results; baseline in body or appendix | Every main number has table/figure/`results/` pointer |
| **R3 Narrative** | Run audit; cut/downgrade illegal claims | Audit clean; no empty answer sections |
| **R4 Critique** | Sensitivity/extreme/ablation + open red-team items; abstract has limits + numbers | ≥2 check types; not strengths-only |
| **R5 Judge** | Run judge; fix structure/prose (**never Freeze numbers**); completion bar | Bar met or force-deliver at cap |

Failed R1–R4 check → patch same pass. R5 fail → judge auto-rewind table. At 5 rounds → force package with residual risks.

---

## Recommended structure

1. Abstract: method + main numbers + **limit scope**  
2. Problem restatement (答題清单)  
3. Analysis (types, why baseline first, three families)  
4. Assumptions (each + relax consequence)  
5. Data / preprocessing (= audit / freeze)  
6. Models: **baseline first**, then improvement; footnotes for rejected-but-run paths  
7. Results: comparison essence + one mechanism attribution line  
8. **Checks:** sensitivity / extreme / counterfactual / ablation / leakage (≥2)  
9. **Pros/cons:** red-team fatals/mediums; **no strengths-only**  
10. Improvements tied to defects  
11. Appendix: `results/` index, complexity, Freeze summary  

Split by question number if needed; do not drop elements.

---

## Completion bar (definition of “good enough”)

All required unless force-deliver:

- [ ] Every subquestion: section + traceable number/figure  
- [ ] Abstract: method + ≥1 main number + limit scope  
- [ ] Baseline comparison in body or pointed appendix  
- [ ] Assumptions listed with relax consequences  
- [ ] Checks section nonempty (≥2 of sensitivity/extreme/ablation)  
- [ ] Pros/cons not strengths-only; fatals closed or in limits  
- [ ] Narrative audit: no “claim variable not in model”  
- [ ] Judge: no unanswered; suite-model risk ≠ high (or mitigated)  
- [ ] No numbers outside Freeze; no 完美/绝对/毫无疑问  

```markdown
## 完成度自检
| 门槛项 | 通过 | 备注 |
|--------|------|------|
| … | 是/否 | … |
```

---

## Style

Prefer: 在给定假设下 / 当前证据支持 / 在参数范围内. Tables before prose; correlation≠causation.

### Contest anti-fluff

1. Delete adjective paragraphs without numbers  
2. Each section: one line naming which subquestion it answers  
3. Figures numbered and cited in text  

Formal contest tone only.

---

## Defect → limitation map (R4) → `DefectMap.md`

```markdown
## 缺陷–局限映射
| 红队项（致命/中等） | 已关闭（results）/ 写入局限原文 |
|---------------------|----------------------------------|
| … | … |
```

No map → R4 incomplete.

Then open [judge.md](judge.md); execute rewind **without** waiting for the user.
