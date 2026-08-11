# 论文编译说明

主交付：`paper.tex` → `paper.pdf`（XeLaTeX + ctex）。

```bash
# 依赖：texlive-xetex、ctex、siunitx、booktabs 等
cd work/2016A-mooring/paper
xelatex paper.tex
xelatex paper.tex
```

图源：`figures/*.png`（由 `../code/make_figures.py` 生成后复制）。  
Markdown 底稿：`main.md`（与 TeX 数值一致，Freeze `2016A-mooring-F1`）。
