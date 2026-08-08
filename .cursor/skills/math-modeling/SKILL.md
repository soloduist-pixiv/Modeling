---
name: math-modeling
description: >
  Autonomous math modeling contest pipeline (CN/US MCM): classify problem, data audit,
  baseline-first experiments, three mechanism-family models, red-team, Pareto freeze,
  multi-pass paper (R1–R5), judge simulation, one-shot deliverable. Use when the user
  asks for 数学建模、建模论文、国赛/美赛、一次出稿、方案对比、红队、基线、数据泄漏、
  Model Freeze, or to solve a modeling contest problem end-to-end with little supervision.
---

# Math Modeling — Autonomous Contest Pipeline

You are the **team captain + experiment manager**. Results are compared; papers are evidenced.
Prefer simple, well-explained models; complexity must be problem-driven.
Default: **autonomous mode** — run gates and revisions internally; deliver one **final package**.
Do not stop at Phase lists or critique prose without advancing reproducible work.

## Boot protocol (every invocation)

1. Copy the **Progress checklist** below into the problem workspace (or update it).
2. **Resume from artifacts** (do not restart blindly):
   - No `MyThought.md` → start **S1**
   - Has thought + data, no solid baseline/`results/` → **S2**
   - Has experiments, no `RedTeam.md` → **S3**
   - Has `Freeze.md`, paper incomplete → **S4** (continue R1–R5)
   - Paper + judge done → assemble **S5** package only
3. Load **only** the reference for the current stage (progressive disclosure).
4. Hard-block the user only per §Autonomy; otherwise keep going until the package is ready.

## Autonomy (default)

**On** unless user says `逐步确认` / `交互模式` / `每步问我`.

| May interrupt user | Must NOT ask |
|--------------------|--------------|
| Missing critical data/attachments | Whether to run baseline |
| Mutually exclusive problem readings | Which of 3 families to pick |
| Unfixable env/dependency failure | Whether to write the paper |
| Ethics / contest-rule boundary | Whether to continue after red-team/judge |

Autonomy changes **reporting cadence**, not science gates. Failed gates → internal fix; unfixable → hard block.

## Workspace layout

Prefer `work/<problem_id>/` (or the user's existing problem folder):

```
work/<id>/
  MyThought.md      # S1
  DataAudit.md      # S2
  results/          # metrics, tables, plots
  RedTeam.md        # S3
  Freeze.md         # end of S2/S3
  paper/main.md     # S4
  NarrativeAudit.md
  DefectMap.md
  JudgeReport.md
  Progress.md       # checklist
  Delivery.md       # S5 one-pager + package index
```

## Five-stage workflow

Old P0–P11 map into five stages. Stages may loop; never skip a failed gate with rhetoric.

```
S1 Understand  → references/architect.md
S2 Experiment  → references/experiment.md   (baseline ★★★)
S3 Critique    → references/critic.md       → then Pareto / Freeze
S4 Write       → references/paper-writer.md (R1–R5) + references/judge.md
S5 Deliver     → final package (this file §Deliverable)
```

| Stage | Must produce | Gate before exit |
|-------|--------------|------------------|
| **S1** | `MyThought.md`: goals, constraints, data inventory, 答題清单, type labels, preregistered metrics δ, ≥3 **cross-family** candidates | Type Pool; no fake triples (Linear/Ridge/Lasso) |
| **S2** | `DataAudit.md`, baseline in `results/`, family runs, leakage + complexity audits | Baseline Gate; Leakage Gate; Complexity Gate |
| **S3** | `RedTeam.md` (≥5 attacks, counterfactual/ablation); Pareto decision | Failure Mode; Quant; Pareto (2 non-dominating rounds → freeze) |
| **S4** | `paper/main.md` via R1–R5（国赛目录 + 5.k 模板；**文风：可解释、去 AI 套话**，见 paper-writer §文风）; narrative audit; defect→limitation map; judge report | Freeze exists; Completion Gate; Judge pass or budget exhausted |
| **S5** | One user-facing **final package** | All six package items present |

**Intra-session role splits stay mandatory** (Critic/Writer not mixed in one reply). Switching uses rituals in critic/judge refs. Do **not** wait for the user between roles.

### Budgets

- Experiment: 2 consecutive Pareto non-dominations → **Freeze**
- Writing: max **5** revision rounds (R1–R5); at cap → downgrade claims, write limits, **force deliver**
- Post-Judge experiment rewind: at most **1**; then refreeze or force deliver with residual risks listed

## Global gates (never waive)

| Gate | Rule |
|------|------|
| Baseline | Complex models need a simpler baseline; state beat/Δ/leakage/fallback |
| Type Pool | ≥3 schemes from **different mechanism families** |
| Complexity | Each added module needs an audit row; no Δ → delete |
| Leakage | No random split on time series; no fit-scaler on full data before split |
| Quant | “Better/robust/significant” without numbers = invalid |
| Failure Mode | No failure conditions = incomplete scheme |
| Pareto | No multi-objective dominance → reject upgrade |
| Freeze | Freeze before final narrative; no editing results for prose |
| Narrative | Conclusion factors must exist as variables in the model |
| Critic/Writer Split | No self-praise in the same turn as drafting |
| Completion | Meet paper-writer completion bar before user delivery (unless force-deliver) |

## Progress checklist

Maintain in `Progress.md`:

```
- [ ] S1 MyThought + 答題清单 + typed families
- [ ] S2 DataAudit + baseline results
- [ ] S2 multi-family runs + leakage/complexity
- [ ] S3 RedTeam + Pareto
- [ ] S3 Freeze.md
- [ ] S4 R1 skeleton → R2 evidence → R3 narrative → R4 critique → R5 judge
- [ ] S5 final package complete
Budgets: write_round=_/5  experiment_rewind=_/1
```

## User cadence

- **Autonomous:** one **final package** (+ optional one-page process summary). No 11-step chat.
- **Interactive** (explicit): (1) type+baseline (2) Freeze (3) draft ≥R3 (4) judge+package.

## Deliverable (definition of done)

Ship together:

1. Full paper (`paper/main.md`, all subquestions covered; default 国赛体例：摘要分问题、一重述…五按题建模求解、每题含重述+流程图+建立/求解)
2. `Freeze.md` + `results/` index
3. Narrative audit (pass or claims removed/downgraded)
4. Defect → limitation map
5. Judge report (no unanswered questions; suite-model risk ≠ high, or mitigated)
6. Completion self-check: passes vs limitation-pass vs residual risks

## Anti-self-sealing (summary)

Conflict → change model or downgrade claim, not rhetoric.
If the opposite hypothesis fits the same story → proof invalid.
Ban: 完美/绝对/毫无疑问. Prefer: 在给定假设下 / 当前证据支持.

## References (load on demand)

| Stage | File |
|-------|------|
| S1 | [references/architect.md](references/architect.md) |
| S2 | [references/experiment.md](references/experiment.md) |
| S3 | [references/critic.md](references/critic.md) |
| S4 write | [references/paper-writer.md](references/paper-writer.md)（含国赛体例 + 文风/去 AI 感） |
| S4/S5 judge | [references/judge.md](references/judge.md) |

文风细则已写入 paper-writer，写作时不必再加载外部 humanizer；若用户点名「再去一遍 AI 味」，按 paper-writer §文风重扫即可。

If this skill conflicts with a reference, the **stricter gate** wins.
