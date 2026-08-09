# Paper Writer — R1–R5 & completion bar

**Role:** Author. Narrate **frozen** evidence only.  
**Forbidden:** Silent metric edits; conclusions citing variables not in the model; final draft without Freeze.

Contest axes: reasonable assumptions, targeted innovation vs baseline, correct reproducible results, clear writing — **no credit for needless complexity**.

**Autonomy:** R1→R5 in one session; no “should I revise?”. Cap 5 rounds → downgrade + limits + **force deliver**.

Load in **S4**. For R5, also load [judge.md](judge.md).

**Paper format (default):** 国赛中文报告体例（参考样卷 A066 类结构）。除非用户指定美赛 IMRaD / 其他模板，一律按下方 **§Paper format** 写入 **`paper/paper.tex`**，并编译为 **`paper/paper.pdf`**。**不生成 `paper/main.md`。**

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

Map every subquestion to a **五、** 下的 `5.k` 节 + evidence. Save as `NarrativeAudit.md`.

---

## Mandatory passes R1–R5

No self-praise in the same turn as drafting. Use Critic/Judge rituals when switching.

| Pass | Action | Exit check |
|------|--------|------------|
| **R1 Skeleton** | Full TOC per §Paper format; each `5.k` has 重述占位 + 流程图占位 + 建立/求解小节 | Every subquestion has `5.k` |
| **R2 Evidence** | Tables/figures first; Freeze 数字填入 `paper.tex`；算法步骤与结果表到位；**首次编译** | Every main number has 表/图/`results/` pointer; `paper.pdf` builds |
| **R3 Narrative** | Run audit; cut/downgrade illegal claims；按 §文风 去 AI 感并补解释句 | Audit clean; no empty `5.k`; 文风自检通过 |
| **R4 Critique** | 模型检验/灵敏度等 + 优缺点/改进；摘要含局限与主数字 | ≥2 check types; not strengths-only |
| **R5 Judge** | Run judge; fix structure/prose (**never Freeze numbers**); 再扫一遍 AI 套话；**终稿编译**；completion bar | Bar met or force-deliver at cap; `paper.pdf` final |

Failed R1–R4 check → patch same pass. R5 fail → judge auto-rewind table. At 5 rounds → force package with residual risks.

---

## Paper format（国赛默认）

### 全篇目录骨架

一级标题用中文序号；问题分析与建模求解用 `x.y` / `x.y.z`。

```text
摘要
  · 背景一句
  ·「针对问题一/二/…」分段：方法要点 + 主结果数字（可加粗）+ 表/文件指针
  · 关键词：3–6 个
一、问题重述
  1.1 问题背景
  1.2 问题提出（按答題清单列问题一…；条件与求解目标写清）
二、模型假设（编号列表；每条可附「若放松则…」）
三、符号说明（三线表：符号 | 说明 | 单位）
四、问题分析
  4.1 问题一的分析
  4.2 问题二的分析
  …
五、模型的建立与求解
  5.1 问题一模型的建立与求解   ← 强制用下方「单问题模板」
  5.2 问题二…
  …
六、模型的检验与灵敏度分析（可并入各题 5.k.4；若合并则本章写总览）
七、模型评价
  7.1 优点
  7.2 缺点 / 局限（必须含红队未关闭项）
八、模型的改进与推广
参考文献
附录（代码要点、results/ 索引、复杂度审计、Freeze 摘要、被否方案脚注）
```

元素映射（旧清单 → 本章）：基线对比与三机制族 → 写入「四、」动机与「五、」各题建立；Checks → `5.k.4` 或「六、」；Pros/cons →「七、」；Improvements →「八、」。**不得因改目录丢掉这些内容。**

### 单问题模板（五、核心；强制）

每个小问 `5.k` **必须**按此骨架展开（无数据/无可检项时，`5.k.4` 可标「本节从略」并说明原因）：

```text
5.k 问题k模型的建立与求解
  ├─ 开篇重述段：明确本问要对哪几个分析点作答；声明「后面一个模型对应几个分析点」
  ├─ 图：问题k流程图（总流程；先图后文引用）
  ├─ 5.k.1 ***模型的建立
  │     ● 对××的分析
  │         公式推导与过程（配图）
  │     ● 对××的分析
  │         公式推导与过程（配图）
  ├─ 5.k.2 ***模型的建立     （本问有多个并列/递进模型时继续 5.k.3…）
  │     ● …
  ├─ 5.k.m 模型的求解
  │     算法步骤框（Step1…）+ 主结果表述 + 三线表/关键图
  └─ 5.k.(m+1) 模型的检验（可选：灵敏度 / 极值 / 消融 / 对照基线）
```

**开篇重述段写法：** 用 1 段话复述本问已知条件与求解目标，**点名**后续分析点（如「导弹运动 / 无人机运动 / 有效遮蔽判定」），并说明各子模型与分析点的对应关系。不要空泛写「下面建立模型」。

**模型建立小节：** 标题写成具体模型名（如「单无人机投弹模型的建立」「有效遮蔽模型的建立」），不要只写「模型一」。其下用 `● **对××的分析**` 切分分析点；复杂过程用 **Step1 / Step2** 或 **Case 1 / Case 2**。

**求解小节：** 先给简短求解思路，再给「算法步骤」分步（可置于分隔线框内），最后给出 **Freeze 内** 主数字，并用表/图固化（如「表 x 问题k有效指标」）。

### 排版与写作约定

| 元素 | 约定 |
|------|------|
| 公式 | 独立成行、全文顺序编号 `(1)(2)…`；文中用「式 (n)」回引 |
| 图 | 「图 n 标题」居中置于图下；**先有图再在正文引用**；流程图优先于长段文字 |
| 表 | 三线表；「表 n 标题」；主结果必须上表或可追溯到 `results/` |
| 分析点 | `● **…分析**`；优化模型内可用 `(1) 目标函数 (2) 约束 (3) 模型建立` |
| 基线 | 复杂模型前先给可复现基线或特例（可放在该问建立段首或求解对照表） |
| 摘要 | 按问题分段；每段至少 1 个主数字 + 方法关键词；文末写局限范围 |
| 代码 | 主体写清算法步骤；大段代码放附录，正文只引用关键实现 |

### 最小可交卷检查（结构层）

- [ ] 有摘要（分问题）+ 关键词  
- [ ] 一～四齐全；符号表非空  
- [ ] 每个小问均有 `5.k`，且含：重述段、流程图、≥1 个「建立」、1 个「求解」  
- [ ] 建立小节内分析点用 `●` 切开，关键推导有公式编号与配图  
- [ ] 七、含非空缺点/局限；八、改进与缺陷对应  
- [ ] `paper/paper.pdf` 编译成功（无未定义引用/缺失图片的致命错误）

---

## LaTeX 产出与编译

### 文件约定

| 路径 | 说明 |
|------|------|
| `paper/paper.tex` | **唯一正文源**；所有章节、公式、表图引用写在此 |
| `paper/paper.pdf` | 交稿 PDF；S4 结束前必须存在且可打开 |
| `../results/` | 图文件默认目录（`\graphicspath{{../results/}}`） |

**禁止：** 另写 `paper/main.md` 作为正文；审计类文件（`NarrativeAudit.md` 等）仍可用 Markdown。

### 编译命令（默认）

在 `paper/` 目录执行两次（交叉引用与目录）：

```bash
cd paper
xelatex -interaction=nonstopmode paper.tex
xelatex -interaction=nonstopmode paper.tex
```

等价：`latexmk -xelatex -interaction=nonstopmode paper.tex`（若环境有 latexmk）。

**编译失败：** 修 `paper.tex`（缺图→补图或改路径；缺包→补 `\usepackage`；Overfull→改表格/换行），不得用「只有 tex 没有 pdf」交 S5。

### 推荐导言区（国赛中文）

新建 `paper.tex` 时从下列骨架起步（可按题微调；与仓库 `2/2016A-mooring/paper/paper.tex` 同族）：

```latex
% !TEX program = xelatex
\documentclass[UTF8,a4paper,zihao=-4]{ctexart}
\usepackage[margin=2.2cm]{geometry}
\usepackage{amsmath,amssymb,bm,amsthm}
\usepackage{graphicx,booktabs,tabularx,multirow}
\usepackage{siunitx,caption,subcaption,float}
\usepackage{hyperref,xcolor,enumitem,setspace}
\graphicspath{{../results/}}
\sisetup{detect-all=true}
\hypersetup{colorlinks=true,linkcolor=black,citecolor=black,urlcolor=blue!50!black}
```

正文结构用 `\section` / `\subsection` / `\subsubsection`；**不要**手写「一、」「5.1」纯文本标题（交给 ctex 自动编号）。

### 国赛目录 → LaTeX 映射

| 报告章节 | LaTeX |
|----------|--------|
| 摘要 + 关键词 | `\begin{abstract}...\end{abstract}`；关键词用 `\noindent\textbf{关键词：}...` |
| 一、问题重述 | `\section{问题重述}`；`\subsection{问题背景}` / `\subsection{问题提出}` |
| 二、模型假设 | `\section{模型假设}`；`\begin{enumerate}` 编号假设 |
| 三、符号说明 | `\section{符号说明}`；`booktabs` 三线表 |
| 四、问题分析 | `\section{问题分析}`；`\subsection{问题一的分析}` … |
| 五、模型的建立与求解 | `\section{模型的建立与求解}` |
| 5.k 问题 k | `\subsection{问题k模型的建立与求解}\label{sec:qk}` |
| 5.k.1 某模型建立 | `\subsubsection{...模型的建立}` |
| 5.k.m 求解 | `\subsubsection{模型的求解}` |
| 5.k.(m+1) 检验 | `\subsubsection{模型的检验}`（可选） |
| 六、检验与灵敏度 | `\section{模型的检验与灵敏度分析}`（或并入各题检验小节） |
| 七、模型评价 | `\section{模型评价}`；`\subsection{优点}` / `\subsection{缺点与局限}` |
| 八、改进与推广 | `\section{模型的改进与推广}` |
| 参考文献 | `\begin{thebibliography}` 或 `biblatex` |
| 附录 | `\appendix` + `\section{...}` |

### 常用环境对照

| 写作元素 | LaTeX 写法 |
|----------|------------|
| 分析点 `● 对××的分析` | `\begin{itemize}[leftmargin=*]\item \textbf{对××的分析}：...` |
| 编号公式 | `\begin{equation}...\label{eq:tag}\end{equation}`；正文 `式~\eqref{eq:tag}` |
| 流程图/示意图 | `\begin{figure}[htbp]\centering\includegraphics[width=...]{fig_...}\caption{问题一流程图}\label{fig:q1flow}\end{figure}` |
| 三线表 | `tabular` + `\toprule\midrule\bottomrule`；`\caption` + `\label{tab:...}` |
| 算法步骤框 | `\begin{center}\fbox{\begin{minipage}{0.92\textwidth}\textbf{算法步骤}\\ Step1: ...\end{minipage}}\end{center}` 或 `description` 环境 |
| Step / Case | `\paragraph{Step1：...}` 或 `\textbf{Case 1.}` |
| 单位与数字 | `siunitx`：`\SI{1.391}{s}`、`\num{1.391}` |
| 相对路径插图 | 图文件放 `results/`，tex 中只写文件名 |

### 插图与表格纪律

- 图在 `results/` 生成（Python 等），tex **只引用**；R2 前确保文件存在  
- 每张图/表在正文至少引用一次（`图~\ref{...}` / `表~\ref{...}`）  
- 流程图优先：每题 `5.k` 至少 1 张总流程图（可用 drawio / matplotlib / mermaid 导出 PDF 或 PNG）

---

## Completion bar (definition of “good enough”)

All required unless force-deliver:

- [ ] Every subquestion: `5.k` + traceable number/figure  
- [ ] Abstract: method + ≥1 main number per major question + limit scope  
- [ ] Baseline comparison in body or pointed appendix  
- [ ] Assumptions listed with relax consequences  
- [ ] Checks nonempty（`5.k.4` 或「六、」；≥2 of sensitivity/extreme/ablation）  
- [ ] Pros/cons not strengths-only; fatals closed or in limits  
- [ ] Narrative audit: no “claim variable not in model”  
- [ ] Judge: no unanswered; suite-model risk ≠ high (or mitigated)  
- [ ] No numbers outside Freeze; no 完美/绝对/毫无疑问  
- [ ] Structure matches §Paper format（或用户显式指定的替代模板）  
- [ ] `paper/paper.pdf` 存在且由当前 `paper.tex` 编译生成  
- [ ] 文风：无高频 AI 套话；关键公式前有解释；朗读不拗口  

```markdown
## 完成度自检
| 门槛项 | 通过 | 备注 |
|--------|------|------|
| … | 是/否 | … |
```

---

## 文风：可读、可解释、去 AI 感

默认正式竞赛语气，但**必须好读、能跟推导**。写法对齐 humanizer 去痕原则，并针对建模论文加「解释句」。不要写成宣传稿，也不要写成只有公式的黑箱。

### 解释性（要写清楚）

每个关键推导块按顺序写，缺一不可：

1. **目的一句**：这段在求什么 / 回答答題清单哪一点  
2. **直觉或物理含义一两句**：变量怎么进模型、为何这样建（可用「直观上…」「也就是说…」）  
3. **公式**（编号）  
4. **回扣**：式中符号与已知条件、单位、下一步怎么用  

求解段同样：先说算法在干什么，再 Step；结果数字后用一句说明「这个数表示什么、相对基线如何」。

四、问题分析：每题写清「已知什么 → 难在哪里 → 打算建什么模型」，避免空泛「下面进行分析」。

### 去 AI 感（禁止 / 慎用）

**禁用或尽量不用：** 此外、综上所述、值得注意的是、至关重要、深入探讨、彰显、凸显、赋能、闭环、维度、格局、落地、赛道、不仅…而且…、这不仅仅是…而是…、标志着、奠定基础、发挥着关键作用、为…提供了有力支撑。

**禁止：** 空洞褒扬（「本模型科学合理」「具有重要意义」）；三段式排比凑字；破折号制造金句；整段加粗；表情符号；聊天腔（「希望对您有帮助」）。

**句式：** 长短交错；能用「是/有/令」就不用「作为…的体现」；两项并列优于硬凑三项；同一概念不要换一堆同义词。

**语气：** 用「在给定假设下 / 当前证据支持 / 在参数范围内」限定结论；承认局限写具体条件，不写「尽管存在挑战，未来依然广阔」。

### 改写对照（建模语境）

差：
> 此外，该模型作为问题求解的关键环节，不仅能够有效刻画系统行为，而且为后续优化奠定坚实基础，彰显了方法的科学性与合理性。

好：
> 先由受力平衡写出缆绳张力随深度的关系（式 3）。得到张力后，再把它代入偏航约束，才能进入问题二的优化。

差：
> 值得注意的是，粒子群算法能够高效求解该复杂优化问题。

好：
> 决策变量有 8 个且目标不可微，本文用粒子群搜索；种群与迭代次数见附录，最优适应度曲线见图 n。

### Contest anti-fluff

1. 无数字、无机制的形容词段直接删  
2. 每个 `5.k` 开篇点明本问答題点；每个建立小节点明对应分析点  
3. 图有编号且正文引用  
4. 优缺点分章写；禁止「完美模型」式自我表扬  
5. R3/R5 交稿前用本节清单扫一遍正文  

### 文风自检（R3 出口）

- [ ] 连续三句是否同长同构？打断一句  
- [ ] 是否出现禁用套话？删或改成具体动作/数字  
- [ ] 每个主公式前是否有「目的 + 含义」？  
- [ ] 结果段是否只有表没有「数字含义」句？补一句  
- [ ] 大声读是否像通知/宣传稿？改成说明文

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
