# -*- coding: utf-8 -*-
"""
2022 高教社杯 CUMCM C题：古代玻璃制品的成分分析与鉴别
完整求解流水线：预处理 → 问题1–4 → 图表与结果表
（出版级绘图风格 + FDR / bootstrap / CLR 零值处理）
"""
from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import Ellipse
from scipy import stats
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import squareform
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    adjusted_rand_score,
    balanced_accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    silhouette_score,
)
from sklearn.model_selection import LeaveOneGroupOut, LeaveOneOut, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

warnings.filterwarnings("ignore")

# ---------------- paths & style ----------------
ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parents[2] / "C题" / "附件.xlsx"
FIG = ROOT / "figures"
RES = ROOT / "results"
FIG.mkdir(parents=True, exist_ok=True)
RES.mkdir(parents=True, exist_ok=True)

# Nature-figure inspired palette (colorblind-friendly pair for 高钾/铅钡)
C_K = "#0F4D92"       # 高钾
C_PB = "#B64342"      # 铅钡
C_UW = "#3775BA"      # 无风化
C_W = "#E28E2C"       # 风化
C_NEUT = "#4D4D4D"
C_GRID = "#E8E8E8"

mpl.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 9,
    "axes.titlesize": 11,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.8,
    "axes.edgecolor": C_NEUT,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "legend.frameon": False,
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
})
sns.set_theme(style="ticks", font="Microsoft YaHei")

COMPS = [
    "二氧化硅(SiO2)",
    "氧化钠(Na2O)",
    "氧化钾(K2O)",
    "氧化钙(CaO)",
    "氧化镁(MgO)",
    "氧化铝(Al2O3)",
    "氧化铁(Fe2O3)",
    "氧化铜(CuO)",
    "氧化铅(PbO)",
    "氧化钡(BaO)",
    "五氧化二磷(P2O5)",
    "氧化锶(SrO)",
    "氧化锡(SnO2)",
    "二氧化硫(SO2)",
]
SHORT = {
    "二氧化硅(SiO2)": "SiO2",
    "氧化钠(Na2O)": "Na2O",
    "氧化钾(K2O)": "K2O",
    "氧化钙(CaO)": "CaO",
    "氧化镁(MgO)": "MgO",
    "氧化铝(Al2O3)": "Al2O3",
    "氧化铁(Fe2O3)": "Fe2O3",
    "氧化铜(CuO)": "CuO",
    "氧化铅(PbO)": "PbO",
    "氧化钡(BaO)": "BaO",
    "五氧化二磷(P2O5)": "P2O5",
    "氧化锶(SrO)": "SrO",
    "氧化锡(SnO2)": "SnO2",
    "二氧化硫(SO2)": "SO2",
}


def savefig(name: str):
    plt.savefig(FIG / name, dpi=300, facecolor="white")
    plt.close()
    print(f"  [fig] {name}")


def style_ax(ax):
    ax.tick_params(width=0.7, length=3)
    ax.grid(False)


def bh_fdr(pvals: np.ndarray) -> np.ndarray:
    """Benjamini–Hochberg FDR adjusted p-values."""
    p = np.asarray(pvals, dtype=float)
    out = np.full_like(p, np.nan, dtype=float)
    mask = np.isfinite(p)
    if mask.sum() == 0:
        return out
    pv = p[mask]
    n = len(pv)
    order = np.argsort(pv)
    ranked = pv[order]
    adj = ranked * n / (np.arange(1, n + 1))
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    tmp = np.empty(n)
    tmp[order] = adj
    out[mask] = tmp
    return out


def estimate_replacement(X: np.ndarray) -> np.ndarray:
    """按成分估计未检出值：取该成分最小正检出值的一半。"""
    X = np.asarray(X, dtype=float)
    repl = np.empty(X.shape[1], dtype=float)
    for j in range(X.shape[1]):
        positive = X[:, j][X[:, j] > 0]
        repl[j] = positive.min() / 2 if len(positive) else 1e-4
    return np.clip(repl, 1e-4, 0.5)


def close_composition(X: np.ndarray, total: float = 100.0) -> np.ndarray:
    """闭合到给定总量；成分分析只使用相对比例。"""
    X = np.clip(np.asarray(X, dtype=float), 0, None)
    sums = X.sum(axis=1, keepdims=True)
    if np.any(sums <= 0):
        raise ValueError("存在成分总和为 0 的样本，无法闭合")
    return X / sums * total


def clr_transform(
    X: np.ndarray, replacement: np.ndarray | float | None = None
) -> np.ndarray:
    """
    CLR after multiplicative zero replacement.
    Zeros (未检出) are replaced by eps (近似检测限/2 的下界)，再闭合后取中心对数比。
    """
    X = np.clip(np.asarray(X, dtype=float), 0, None)
    if replacement is None:
        replacement = estimate_replacement(X)
    X = np.where(X > 0, X, replacement)
    X = X / X.sum(axis=1, keepdims=True)
    logX = np.log(X)
    return logX - logX.mean(axis=1, keepdims=True)


def artifact_weather_units(valid: pd.DataFrame) -> pd.DataFrame:
    """同一文物、同一风化状态的重复采样先取均值，避免伪重复。"""
    meta = ["文物编号", "类型", "风化标签"]
    out = valid.groupby(meta, as_index=False)[COMPS].mean()
    out["成分总和"] = out[COMPS].sum(axis=1)
    return out


def artifact_units(valid: pd.DataFrame) -> pd.DataFrame:
    """构造文物级分析单元，防止多采样点文物被过度加权。

    风化标签优先取表单1的文物级「表面风化」，避免把编号49/50这类
    “风化点+未风化点”先多数票混成单一采样标签后再做层内置换。
    若上游已做风化校正，成分均值应在校正后的数据上计算。
    """
    comp = valid.groupby(["文物编号", "类型"], as_index=False)[COMPS].mean()
    if "表面风化" in valid.columns and valid["表面风化"].notna().any():
        weather = (
            valid.groupby(["文物编号", "类型"], as_index=False)["表面风化"]
            .agg(lambda s: s.dropna().iloc[0] if s.notna().any() else "风化")
            .rename(columns={"表面风化": "风化标签"})
        )
    else:
        weather = (
            valid.groupby(["文物编号", "类型"])["风化标签"]
            .agg(lambda s: "风化" if (s == "风化").mean() >= 0.5 else "无风化")
            .reset_index(name="风化标签")
        )
    out = comp.merge(weather, on=["文物编号", "类型"], how="left")
    out["成分总和"] = out[COMPS].sum(axis=1)
    return out


def inverse_clr(Z: np.ndarray, total: np.ndarray | float = 100.0) -> np.ndarray:
    """将 CLR 坐标稳定地映回闭合成分。"""
    Z = np.asarray(Z, dtype=float)
    E = np.exp(Z - Z.max(axis=1, keepdims=True))
    closed = E / E.sum(axis=1, keepdims=True)
    total_arr = np.asarray(total, dtype=float)
    if total_arr.ndim == 0:
        return closed * float(total_arr)
    return closed * total_arr.reshape(-1, 1)


def weather_correct_data(data: pd.DataFrame, weather_models: dict) -> pd.DataFrame:
    """按已知类型将风化点映射到收缩后的平均风化前 CLR 状态。"""
    out = data.copy()
    for typ, model in weather_models.items():
        mask = out["类型"].eq(typ) & out["风化标签"].eq("风化")
        if not mask.any():
            continue
        X = out.loc[mask, COMPS].values
        totals = out.loc[mask, COMPS].sum(axis=1).values
        Z = clr_transform(X, model["replacement"]) - model["delta_clr"]
        out.loc[mask, COMPS] = inverse_clr(Z, totals)
    out["成分总和"] = out[COMPS].sum(axis=1)
    return out


def confidence_ellipse(x, y, ax, n_std=1.96, **kwargs):
    if len(x) < 3:
        return
    cov = np.cov(x, y)
    if cov.ndim < 2 or np.any(~np.isfinite(cov)):
        return
    vals, vecs = np.linalg.eigh(cov)
    order = vals.argsort()[::-1]
    vals, vecs = vals[order], vecs[:, order]
    theta = np.degrees(np.arctan2(*vecs[:, 0][::-1]))
    w, h = 2 * n_std * np.sqrt(np.maximum(vals, 0))
    ell = Ellipse(xy=(np.mean(x), np.mean(y)), width=w, height=h,
                  angle=theta, **kwargs)
    ax.add_patch(ell)


def annot_heatmap(ax, data, fmt=".2f", thr=0.55):
    """Adaptive text color for heatmap cells."""
    arr = np.asarray(data, dtype=float)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            v = arr[i, j]
            if not np.isfinite(v):
                continue
            color = "white" if abs(v) >= thr else C_NEUT
            ax.text(j + 0.5, i + 0.5, format(v, fmt),
                    ha="center", va="center", color=color, fontsize=7)


# ==================== 0. preprocess ====================
def load_and_clean():
    form1 = pd.read_excel(DATA, sheet_name="表单1")
    form2 = pd.read_excel(DATA, sheet_name="表单2")
    form3 = pd.read_excel(DATA, sheet_name="表单3")

    form2 = form2.copy()
    form2[COMPS] = form2[COMPS].fillna(0.0)
    form2["成分总和"] = form2[COMPS].sum(axis=1)
    form2["有效"] = form2["成分总和"].between(85, 105)

    def parse_id(s):
        s = str(s).strip()
        match = re.match(r"^(\d+)", s)
        artifact_id = int(match.group(1)) if match else np.nan
        flag = "普通"
        if "未风化点" in s:
            flag = "未风化点"
        elif "严重风化点" in s:
            flag = "严重风化点"
        elif "部位1" in s:
            flag = "部位1"
        elif "部位2" in s:
            flag = "部位2"
        return artifact_id, flag

    parsed = form2["文物采样点"].apply(parse_id)
    form2["文物编号"] = parsed.apply(lambda x: x[0]).astype(int)
    form2["采样标记"] = parsed.apply(lambda x: x[1])

    merged = form2.merge(form1, on="文物编号", how="left")

    weather = merged["表面风化"].copy()
    weather = weather.where(merged["采样标记"] != "严重风化点", "风化")
    weather = weather.where(merged["采样标记"] != "未风化点", "无风化")
    merged["风化标签"] = weather

    form3 = form3.copy()
    form3[COMPS] = form3[COMPS].fillna(0.0)
    form3["成分总和"] = form3[COMPS].sum(axis=1)
    form3["有效"] = form3["成分总和"].between(85, 105)

    valid = merged[merged["有效"]].copy()
    valid.to_csv(RES / "cleaned_merged.csv", index=False, encoding="utf-8-sig")
    form3.to_csv(RES / "form3_filled.csv", index=False, encoding="utf-8-sig")

    print(f"[0] 表单2原始 {len(form2)} 行，有效 {merged['有效'].sum()} 行")
    print(f"    无效样本：{list(merged.loc[~merged['有效'], '文物采样点'])}")
    return form1, merged, valid, form3


# ==================== 1. problem 1 ====================
def cramers_v(table: pd.DataFrame) -> float:
    chi2 = stats.chi2_contingency(table.values, correction=False)[0]
    n = table.values.sum()
    r, k = table.shape
    return float(np.sqrt(chi2 / (n * (min(r, k) - 1)))) if min(r, k) > 1 else 0.0


def bootstrap_factor(a, b, n_boot=1000, seed=42):
    """Bootstrap CI for mean(b)/mean(a)."""
    rng = np.random.default_rng(seed)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ratios = []
    for _ in range(n_boot):
        ma = rng.choice(a, size=len(a), replace=True).mean()
        mb = rng.choice(b, size=len(b), replace=True).mean()
        if ma > 1e-9:
            ratios.append(mb / ma)
    if not ratios:
        return np.nan, np.nan, np.nan
    return float(np.mean(ratios)), float(np.percentile(ratios, 2.5)), float(np.percentile(ratios, 97.5))


def contingency_permutation_p(x, y, n_perm=9999, seed=42) -> float:
    """固定边际、置换风化标签的列联表检验，适用于稀疏颜色格。"""
    x_code, _ = pd.factorize(x)
    y_code, _ = pd.factorize(y)
    r, k = x_code.max() + 1, y_code.max() + 1

    def statistic(yc):
        table = np.zeros((r, k), dtype=float)
        np.add.at(table, (x_code, yc), 1)
        expected = np.outer(table.sum(axis=1), table.sum(axis=0)) / table.sum()
        return float(np.sum((table - expected) ** 2 / np.where(expected > 0, expected, 1)))

    observed = statistic(y_code)
    rng = np.random.default_rng(seed)
    exceed = sum(statistic(rng.permutation(y_code)) >= observed - 1e-12 for _ in range(n_perm))
    return float((exceed + 1) / (n_perm + 1))


def problem1(form1: pd.DataFrame, valid: pd.DataFrame):
    print("\n===== 问题1 =====")
    assoc_rows = []
    analysis = artifact_weather_units(valid)
    state_count = analysis.groupby("文物编号")["风化标签"].nunique()
    mixed_ids = state_count[state_count > 1].index
    inference = analysis[~analysis["文物编号"].isin(mixed_ids)].copy()

    for col in ["类型", "纹饰", "颜色"]:
        sub = form1.dropna(subset=[col, "表面风化"]).copy()
        ct = pd.crosstab(sub[col], sub["表面风化"])
        ct.to_csv(RES / f"p1_crosstab_{col}.csv", encoding="utf-8-sig")
        if ct.shape[0] >= 2 and ct.shape[1] >= 2:
            chi2, p_asymptotic, dof, expected = stats.chi2_contingency(ct, correction=False)
            p_perm = contingency_permutation_p(sub[col].values, sub["表面风化"].values)
            p_fisher = (
                float(stats.fisher_exact(ct.values).pvalue)
                if ct.shape == (2, 2) else np.nan
            )
            p = p_fisher if np.isfinite(p_fisher) else p_perm
            v = cramers_v(ct)
            sparse = bool((expected < 5).mean() > 0.2 or (expected < 1).any())
        else:
            chi2 = p = p_asymptotic = p_perm = p_fisher = dof = v = np.nan
            sparse = True
        assoc_rows.append(
            {
                "因素": col,
                "卡方": chi2,
                "自由度": dof,
                "p值": p,
                "p值_渐近卡方": p_asymptotic,
                "p值_置换": p_perm,
                "p值_Fisher_2x2": p_fisher,
                "稀疏列联表": sparse,
                "CramerV": v,
                "样本量": len(sub),
            }
        )
        print(f"  {col}: chi2={chi2:.4f}, robust-p={p:.4g}, V={v:.4f}")

        fig, ax = plt.subplots(figsize=(6.2, 3.8))
        ct2 = ct.reindex(columns=["无风化", "风化"]).fillna(0)
        ct2.plot(kind="bar", stacked=True, ax=ax, color=[C_UW, C_W],
                 edgecolor="white", width=0.72, legend=True)
        ax.set_xlabel(col)
        ax.set_ylabel("文物数量")
        ax.set_title(f"表面风化与{col}的列联分布")
        ax.legend(title="表面风化")
        ax.tick_params(axis="x", rotation=0 if col != "颜色" else 35)
        style_ax(ax)
        savefig(f"fig1_1_weather_{col}.png")

    pd.DataFrame(assoc_rows).to_csv(RES / "p1_association.csv", index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.6), sharey=True)
    for ax, typ, color in zip(axes, ["高钾", "铅钡"], [C_K, C_PB]):
        sub = form1[form1["类型"] == typ]
        counts = sub["表面风化"].value_counts().reindex(["无风化", "风化"]).fillna(0)
        bars = ax.bar(counts.index, counts.values, color=[C_UW, C_W],
                      edgecolor="white", width=0.55)
        ax.set_title(f"{typ}玻璃 (n={len(sub)})", color=color, fontweight="bold")
        ax.set_ylabel("数量" if typ == "高钾" else "")
        for i, v in enumerate(counts.values):
            ax.text(i, v + 0.25, str(int(v)), ha="center", fontsize=9, color=C_NEUT)
        rate = counts["风化"] / len(sub) if len(sub) else 0
        ax.text(0.5, 0.92, f"风化率 {rate:.0%}", transform=ax.transAxes,
                ha="center", fontsize=8, color=C_NEUT)
        style_ax(ax)
    fig.suptitle("分类型表面风化计数", y=1.02, fontsize=11)
    savefig("fig1_2_type_weather_count.png")

    stats_rows = []
    mean_tables = {}
    for typ in ["高钾", "铅钡"]:
        sub = analysis[analysis["类型"] == typ]
        infer_sub = inference[inference["类型"] == typ]
        means = sub.groupby("风化标签")[COMPS].mean()
        means.to_csv(RES / f"p1_mean_{typ}.csv", encoding="utf-8-sig")
        mean_tables[typ] = means

        # dual-panel mean comparison
        major = ["二氧化硅(SiO2)"]
        minor = ["氧化钾(K2O)", "氧化钙(CaO)", "氧化铝(Al2O3)",
                 "氧化铅(PbO)", "氧化钡(BaO)", "五氧化二磷(P2O5)", "氧化铜(CuO)"]
        fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.8),
                                 gridspec_kw={"width_ratios": [1, 2.2]})
        for ax, comps, title in zip(
            axes,
            [major, minor],
            ["主成分", "助熔/着色成分（放大）"],
        ):
            labels = [SHORT[c] for c in comps]
            x = np.arange(len(comps))
            w = 0.36
            yu = [means.loc["无风化", c] if "无风化" in means.index else 0 for c in comps]
            yw = [means.loc["风化", c] if "风化" in means.index else 0 for c in comps]
            ax.bar(x - w / 2, yu, w, label="无风化", color=C_UW, edgecolor="white")
            ax.bar(x + w / 2, yw, w, label="风化", color=C_W, edgecolor="white")
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=30, ha="right")
            ax.set_ylabel("平均含量 (%)")
            ax.set_title(title, fontsize=10)
            style_ax(ax)
            if ax is axes[0]:
                ax.legend(loc="upper left")
        fig.suptitle(f"{typ}玻璃：有无风化化学成分均值对比", y=1.02, fontsize=11)
        savefig(f"fig1_3_mean_{typ}.png")

        for c in COMPS:
            a = infer_sub.loc[infer_sub["风化标签"] == "无风化", c].values
            b = infer_sub.loc[infer_sub["风化标签"] == "风化", c].values
            det_u = float((a > 0).mean()) if len(a) else np.nan
            det_w = float((b > 0).mean()) if len(b) else np.nan
            if len(a) >= 2 and len(b) >= 2:
                u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            else:
                u, p = np.nan, np.nan
            ma, mb = float(np.mean(a)) if len(a) else np.nan, float(np.mean(b)) if len(b) else np.nan
            rate = (mb - ma) / ma if ma and ma > 1e-9 else np.nan
            factor = mb / ma if ma and ma > 1e-9 else np.nan
            boot_mean, ci_lo, ci_hi = (np.nan, np.nan, np.nan)
            if len(a) >= 2 and len(b) >= 2 and ma > 1e-9:
                boot_mean, ci_lo, ci_hi = bootstrap_factor(a, b)
            # unstable if low detection or extreme/wide CI
            unstable = bool(
                (det_u < 0.3 and det_w < 0.3)
                or (pd.notna(factor) and (factor <= 0 or factor > 8))
                or (pd.notna(ci_hi) and pd.notna(ci_lo) and (ci_hi - ci_lo) > 10)
            )
            stats_rows.append(
                {
                    "类型": typ,
                    "成分": SHORT[c],
                    "无风化均值": ma,
                    "风化均值": mb,
                    "无风化检出率": det_u,
                    "风化检出率": det_w,
                    "差值": mb - ma if pd.notna(ma) else np.nan,
                    "相对变化率": rate,
                    "风化系数": factor,
                    "风化系数_boot": boot_mean,
                    "风化系数_CI低": ci_lo,
                    "风化系数_CI高": ci_hi,
                    "MannWhitney_U": u,
                    "p值": p,
                    "不稳定": unstable,
                }
            )

    stats_df = pd.DataFrame(stats_rows)
    # FDR within each type
    for typ in ["高钾", "铅钡"]:
        m = stats_df["类型"] == typ
        stats_df.loc[m, "p_FDR"] = bh_fdr(stats_df.loc[m, "p值"].values)
    stats_df["显著_FDR<0.05"] = stats_df["p_FDR"] < 0.05
    stats_df["显著(p<0.05)"] = stats_df["p值"] < 0.05
    stats_df.to_csv(RES / "p1_component_stats.csv", index=False, encoding="utf-8-sig")

    # weathering factor heatmap: log2(f), center 0; mask unstable
    piv = stats_df.pivot(index="成分", columns="类型", values="风化系数")
    unstable_mask = stats_df.pivot(index="成分", columns="类型", values="不稳定").astype(bool)
    # sort by max |log2 f| among stable
    logf = np.log2(piv.clip(lower=1e-3))
    score = logf.abs().max(axis=1)
    order = score.sort_values(ascending=False).index
    piv = piv.loc[order]
    unstable_mask = unstable_mask.loc[order]
    logf = logf.loc[order]

    fig, ax = plt.subplots(figsize=(4.8, 6.2))
    plot_data = logf.mask(unstable_mask)
    sns.heatmap(
        plot_data, annot=False, cmap="RdBu_r", center=0, ax=ax,
        vmin=-3, vmax=3, cbar_kws={"label": r"$\log_2$(风化系数)"},
        linewidths=0.6, linecolor="white",
    )
    # annotate
    for i, comp in enumerate(piv.index):
        for j, typ in enumerate(piv.columns):
            if bool(unstable_mask.loc[comp, typ]):
                ax.text(j + 0.5, i + 0.5, "—", ha="center", va="center",
                        color=C_NEUT, fontsize=8)
            else:
                v = piv.loc[comp, typ]
                lv = logf.loc[comp, typ]
                color = "white" if abs(lv) >= 1.2 else C_NEUT
                ax.text(j + 0.5, i + 0.5, f"{v:.2f}", ha="center", va="center",
                        color=color, fontsize=7.5)
    ax.set_title("风化系数（以 1 为中性；不稳定项已掩码）")
    ax.set_xlabel("类型")
    ax.set_ylabel("成分")
    savefig("fig1_4_weather_factor.png")

    # 描述性倍数保留用于解释；预测改用 CLR 均值位移，避免逐成分相除后再
    # 强行闭合造成的几何不一致。位移按有效样本量做轻度收缩，降低小样本过拟合。
    factors = {}
    weather_models = {}
    for typ in ["高钾", "铅钡"]:
        sub = stats_df[stats_df["类型"] == typ].set_index("成分")
        fac = {}
        for c in COMPS:
            f = sub.loc[SHORT[c], "风化系数"]
            unstable = bool(sub.loc[SHORT[c], "不稳定"])
            if unstable or pd.isna(f) or f <= 0 or f > 50:
                f = 1.0
            fac[c] = float(f)
        factors[typ] = fac

        units = analysis[analysis["类型"] == typ]
        replacement = estimate_replacement(units[COMPS].values)
        Z = clr_transform(units[COMPS].values, replacement)
        is_w = units["风化标签"].eq("风化").values
        if is_w.sum() < 2 or (~is_w).sum() < 2:
            raise ValueError(f"{typ}风化/无风化文物级样本不足，无法估计风化位移")
        delta_raw = Z[is_w].mean(axis=0) - Z[~is_w].mean(axis=0)
        n_eff = 2.0 / (1.0 / is_w.sum() + 1.0 / (~is_w).sum())
        shrink = n_eff / (n_eff + 4.0)
        delta = delta_raw * shrink
        weather_models[typ] = {
            "replacement": replacement,
            "delta_clr": delta,
            "shrinkage": float(shrink),
            "n_weathered": int(is_w.sum()),
            "n_unweathered": int((~is_w).sum()),
        }

    with open(RES / "p1_weather_factors.json", "w", encoding="utf-8") as f:
        json.dump({k: {SHORT[kk]: vv for kk, vv in v.items()} for k, v in factors.items()},
                  f, ensure_ascii=False, indent=2)

    weathered = valid[valid["风化标签"] == "风化"].copy()
    pred_rows = []
    for _, row in weathered.iterrows():
        typ = row["类型"]
        model = weather_models[typ]
        z_w = clr_transform(
            row[COMPS].values.astype(float).reshape(1, -1),
            model["replacement"],
        )
        target = row["成分总和"] if row["成分总和"] > 0 else 100.0
        raw = inverse_clr(z_w - model["delta_clr"], target)[0]
        rec = {
            "文物采样点": row["文物采样点"],
            "文物编号": row["文物编号"],
            "类型": typ,
            "采样标记": row["采样标记"],
        }
        for c, v in zip(COMPS, raw):
            rec[SHORT[c] + "_预测风化前"] = v
            rec[SHORT[c] + "_风化检测"] = row[c]
        pred_rows.append(rec)

    pred_df = pd.DataFrame(pred_rows)
    pred_df.to_csv(RES / "p1_predict_preweather.csv", index=False, encoding="utf-8-sig")

    severe = weathered[weathered["采样标记"] == "严重风化点"]
    if len(severe) == 0:
        severe = weathered.head(4)
    else:
        severe = severe.head(4)

    key_show = ["二氧化硅(SiO2)", "氧化钾(K2O)", "氧化铅(PbO)", "氧化钡(BaO)",
                "五氧化二磷(P2O5)", "氧化钙(CaO)"]
    n = min(4, len(severe))
    if n > 0:
        fig, axes = plt.subplots(1, n, figsize=(3.0 * n, 3.6), sharey=True)
        if n == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, severe.iterrows()):
            model = weather_models[row["类型"]]
            z_w = clr_transform(
                row[COMPS].values.astype(float).reshape(1, -1),
                model["replacement"],
            )
            pred_all = inverse_clr(z_w - model["delta_clr"], row["成分总和"])[0]
            raw = np.array([pred_all[COMPS.index(c)] for c in key_show])
            x = np.arange(len(key_show))
            w = 0.35
            ax.bar(x - w / 2, [row[c] for c in key_show], w, label="风化检测", color=C_W)
            ax.bar(x + w / 2, raw, w, label="预测风化前", color=C_UW)
            ax.set_xticks(x)
            ax.set_xticklabels([SHORT[c] for c in key_show], rotation=45, ha="right")
            ax.set_title(str(row["文物采样点"]), fontsize=9)
            style_ax(ax)
        axes[0].set_ylabel("含量 (%)")
        axes[-1].legend(loc="upper right", fontsize=7)
        fig.suptitle("风化点检测值与预测风化前成分对比", y=1.03, fontsize=11)
        savefig("fig1_5_preweather_pred.png")

    print(f"  已预测 {len(pred_df)} 个风化点的风化前成分")
    print(f"  FDR 显著成分数: {int(stats_df['显著_FDR<0.05'].sum())} / {len(stats_df)}")
    weather_json = {
        typ: {
            "replacement": {
                SHORT[c]: float(v)
                for c, v in zip(COMPS, model["replacement"])
            },
            "delta_clr": {
                SHORT[c]: float(v)
                for c, v in zip(COMPS, model["delta_clr"])
            },
            "shrinkage": model["shrinkage"],
            "n_weathered": model["n_weathered"],
            "n_unweathered": model["n_unweathered"],
        }
        for typ, model in weather_models.items()
    }
    with open(RES / "p1_weather_clr_model.json", "w", encoding="utf-8") as f:
        json.dump(weather_json, f, ensure_ascii=False, indent=2)
    return weather_models, stats_df


# ==================== 2. problem 2 ====================
def fit_type_ensemble(X: np.ndarray, y: np.ndarray) -> dict:
    """拟合原始成分 RF 与 CLR-Logistic 的等权集成。"""
    replacement = estimate_replacement(X)
    scaler = StandardScaler().fit(clr_transform(X, replacement))
    lr = LogisticRegression(
        max_iter=3000, class_weight="balanced", C=0.5, random_state=42
    )
    lr.fit(scaler.transform(clr_transform(X, replacement)), y)
    rf = RandomForestClassifier(
        n_estimators=300,
        min_samples_leaf=2,
        max_features="sqrt",
        random_state=42,
        class_weight="balanced_subsample",
        n_jobs=-1,
    )
    rf.fit(X, y)
    return {
        "rf": rf,
        "lr": lr,
        "replacement": replacement,
        "scaler": scaler,
    }


def predict_type_support(model: dict, X: np.ndarray) -> np.ndarray:
    """返回铅钡模型支持度；它是集成分数，不冒充严格校准概率。"""
    p_rf = model["rf"].predict_proba(X)[:, 1]
    Z = model["scaler"].transform(clr_transform(X, model["replacement"]))
    p_lr = model["lr"].predict_proba(Z)[:, 1]
    return (p_rf + p_lr) / 2


def select_marker_threshold(score: np.ndarray, y: np.ndarray) -> float:
    """仅在训练集内按平衡准确率选择 PbO+BaO 阈值。"""
    vals = np.unique(np.asarray(score, dtype=float))
    candidates = (
        np.array([vals[0] - 1e-9, vals[0] + 1e-9])
        if len(vals) == 1
        else np.r_[vals[0] - 1e-9, (vals[:-1] + vals[1:]) / 2, vals[-1] + 1e-9]
    )
    ranked = []
    for threshold in candidates:
        pred = (score >= threshold).astype(int)
        ranked.append((balanced_accuracy_score(y, pred), accuracy_score(y, pred), threshold))
    return float(max(ranked, key=lambda item: (item[0], item[1], -item[2]))[2])


def validation_metrics(y: np.ndarray, pred: np.ndarray, support=None) -> dict:
    out = {
        "准确率": float(accuracy_score(y, pred)),
        "平衡准确率": float(balanced_accuracy_score(y, pred)),
        "宏F1": float(f1_score(y, pred, average="macro")),
        "MCC": float(matthews_corrcoef(y, pred)),
    }
    if support is not None:
        out["Brier分数"] = float(brier_score_loss(y, support))
    return out


def problem2(valid: pd.DataFrame, weather_models: dict):
    print("\n===== 问题2 =====")
    units = artifact_weather_units(valid)
    X = units[COMPS].values
    y = (units["类型"] == "铅钡").astype(int).values
    groups = units["文物编号"].values
    feature_names = [SHORT[c] for c in COMPS]

    # 所有泛化指标均按文物留一；同一文物的多个点绝不跨训练/验证集。
    logo = LeaveOneGroupOut()
    ensemble_oof = np.zeros(len(units), dtype=float)
    dt_oof = np.zeros(len(units), dtype=int)
    threshold_oof = np.zeros(len(units), dtype=int)
    for train, test in logo.split(X, y, groups):
        fold_model = fit_type_ensemble(X[train], y[train])
        ensemble_oof[test] = predict_type_support(fold_model, X[test])

        fold_tree = DecisionTreeClassifier(
            max_depth=3, min_samples_leaf=3, class_weight="balanced", random_state=42
        )
        fold_tree.fit(X[train], y[train])
        dt_oof[test] = fold_tree.predict(X[test])

        train_score = (
            units.iloc[train]["氧化铅(PbO)"].values
            + units.iloc[train]["氧化钡(BaO)"].values
        )
        test_score = (
            units.iloc[test]["氧化铅(PbO)"].values
            + units.iloc[test]["氧化钡(BaO)"].values
        )
        fold_threshold = select_marker_threshold(train_score, y[train])
        threshold_oof[test] = (test_score >= fold_threshold).astype(int)

    ensemble_pred = (ensemble_oof >= 0.5).astype(int)
    ensemble_metrics = validation_metrics(y, ensemble_pred, ensemble_oof)
    tree_metrics = validation_metrics(y, dt_oof)
    threshold_metrics = validation_metrics(y, threshold_oof)

    dt = DecisionTreeClassifier(max_depth=3, min_samples_leaf=3, random_state=42)
    acc = tree_metrics["准确率"]
    print(f"  决策树按文物留一准确率: {acc:.4f}")
    print(classification_report(y, dt_oof, target_names=["高钾", "铅钡"]))

    dt.fit(X, y)
    rules = export_text(dt, feature_names=feature_names)
    (RES / "p2_decision_tree_rules.txt").write_text(rules, encoding="utf-8")
    print(rules)

    type_model = fit_type_ensemble(X, y)
    rf = type_model["rf"]
    rf_acc = ensemble_metrics["准确率"]
    imp = pd.DataFrame({"成分": feature_names, "重要性": rf.feature_importances_}).sort_values(
        "重要性", ascending=False
    )
    imp.to_csv(RES / "p2_feature_importance.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    imp_plot = imp.head(10).iloc[::-1]
    ax.barh(imp_plot["成分"], imp_plot["重要性"], color=C_K, edgecolor="white", height=0.7)
    ax.set_xlabel("重要性")
    ax.set_title("随机森林特征重要性（高钾 vs 铅钡）")
    style_ax(ax)
    savefig("fig2_1_feature_importance.png")

    # PCA with ellipses + note on variance
    Xs = StandardScaler().fit_transform(X)
    pca = PCA(n_components=2, random_state=42)
    Z = pca.fit_transform(Xs)
    fig, ax = plt.subplots(figsize=(5.8, 4.8))
    for label, name, color in [(0, "高钾", C_K), (1, "铅钡", C_PB)]:
        m = y == label
        ax.scatter(Z[m, 0], Z[m, 1], c=color, label=name, s=42, alpha=0.85,
                   edgecolors="white", linewidths=0.6, zorder=3)
        confidence_ellipse(Z[m, 0], Z[m, 1], ax, n_std=1.96,
                           facecolor=color, alpha=0.12, edgecolor=color, lw=1.2)
    var1, var2 = pca.explained_variance_ratio_[:2] * 100
    ax.set_xlabel(f"PC1 ({var1:.1f}%)")
    ax.set_ylabel(f"PC2 ({var2:.1f}%)")
    ax.set_title(f"两类玻璃 PCA 投影（累计 {var1+var2:.1f}%）")
    ax.legend(loc="best")
    # top loadings annotation
    load = pd.DataFrame(pca.components_.T, index=feature_names, columns=["PC1", "PC2"])
    top1 = load["PC1"].abs().sort_values(ascending=False).head(3).index.tolist()
    ax.text(0.02, 0.02, f"PC1 主载荷: {', '.join(top1)}", transform=ax.transAxes,
            fontsize=7, color=C_NEUT)
    style_ax(ax)
    savefig("fig2_2_pca_types.png")
    load.to_csv(RES / "p2_pca_loadings.csv", encoding="utf-8-sig")

    units = units.copy()
    units["PbO_BaO"] = units["氧化铅(PbO)"] + units["氧化钡(BaO)"]
    best_thr = select_marker_threshold(units["PbO_BaO"].values, y)
    best_acc = threshold_metrics["准确率"]

    rule_summary = {
        "验证方案": "按文物编号留一（同一文物的多采样点不跨折）",
        "决策树分组LOO": tree_metrics,
        "集成模型分组LOO": ensemble_metrics,
        "阈值规则嵌套分组LOO": threshold_metrics,
        "决策树分组LOO准确率": float(acc),
        "集成模型分组LOO准确率": float(rf_acc),
        "关键成分": imp.head(5)["成分"].tolist(),
        "经验阈值说明": "铅钡玻璃通常 PbO+BaO 显著偏高；高钾玻璃 SiO2、K2O 相对更高",
        "PbO+BaO最优阈值": float(best_thr),
        "PbO+BaO阈值准确率": float(best_acc),
        "PCA累计方差PC1+PC2": float(var1 + var2),
        "PC1主载荷": top1,
    }
    with open(RES / "p2_class_rules.json", "w", encoding="utf-8") as f:
        json.dump(rule_summary, f, ensure_ascii=False, indent=2)

    # method comparison bar
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    methods = ["PbO+BaO\n阈值", "决策树", "RF+CLR-Logistic\n集成"]
    accs = [best_acc, acc, rf_acc]
    colors = [C_PB, C_K, "#7C6CCF"]
    bars = ax.bar(methods, accs, color=colors, edgecolor="white", width=0.65)
    ax.set_ylim(0.85, 1.02)
    ax.set_ylabel("留一法准确率")
    ax.set_title("分类方法对照")
    for b, a in zip(bars, accs):
        ax.text(b.get_x() + b.get_width() / 2, a + 0.005, f"{a:.1%}",
                ha="center", fontsize=8)
    style_ax(ax)
    savefig("fig2_9_method_compare.png")

    # scatter with shaded regions + outliers
    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    xmax = max(units["PbO_BaO"].max() * 1.05, best_thr * 3)
    ax.axvspan(0, best_thr, color=C_K, alpha=0.08, label=None)
    ax.axvspan(best_thr, xmax, color=C_PB, alpha=0.08, label=None)
    for label, name, color in [(0, "高钾", C_K), (1, "铅钡", C_PB)]:
        m = y == label
        ax.scatter(
            units.loc[m, "PbO_BaO"], units.loc[m, "氧化钾(K2O)"],
            c=color, label=name, s=48, alpha=0.88, edgecolors="white", linewidths=0.6, zorder=3,
        )
    ax.axvline(best_thr, color=C_NEUT, ls="--", lw=1.2,
               label=f"阈值 τ={best_thr:.2f}")
    # annotate high-K outliers with high PbO+BaO
    outliers = units[(units["类型"] == "高钾") & (units["PbO_BaO"] > best_thr)]
    for _, r in outliers.iterrows():
        ax.annotate(
            str(r["文物采样点"]),
            (r["PbO_BaO"], r["氧化钾(K2O)"]),
            textcoords="offset points", xytext=(6, 4), fontsize=7, color=C_K,
        )
    ax.set_xlim(-1, xmax)
    ax.set_xlabel("PbO + BaO (%)")
    ax.set_ylabel("K2O (%)")
    ax.set_title("两类玻璃关键成分散点与可解释阈值")
    ax.legend(loc="upper right")
    ax.text(0.02, 0.96, f"阈值准确率 {best_acc:.1%}", transform=ax.transAxes,
            va="top", fontsize=8, color=C_NEUT)
    style_ax(ax)
    savefig("fig2_3_scatter_rule.png")

    subclass_all = []
    cluster_models = {}
    corrected_valid = weather_correct_data(valid, weather_models)
    for typ in ["高钾", "铅钡"]:
        sub = artifact_units(corrected_valid)
        sub = sub[sub["类型"] == typ].copy()
        sub["文物采样点"] = sub["文物编号"].astype(str)
        if typ == "高钾":
            feats = ["二氧化硅(SiO2)", "氧化钾(K2O)", "氧化钙(CaO)", "氧化铝(Al2O3)",
                     "氧化铁(Fe2O3)", "五氧化二磷(P2O5)"]
            key_feats = ["二氧化硅(SiO2)", "氧化钾(K2O)", "氧化钙(CaO)"]
            prefer_k = 3
            min_size = 2
            # 高钾样本少：关键成分 KMeans 与 CLR-Ward 对照
        else:
            feats = ["二氧化硅(SiO2)", "氧化铅(PbO)", "氧化钡(BaO)", "氧化钙(CaO)",
                     "氧化铝(Al2O3)", "五氧化二磷(P2O5)"]
            key_feats = ["二氧化硅(SiO2)", "氧化铅(PbO)", "氧化钡(BaO)"]
            prefer_k = 3
            min_size = 3

        Xsub = sub[feats].values
        Xkey = StandardScaler().fit_transform(sub[key_feats].values)
        replacement = estimate_replacement(Xsub)
        scaler_sub = StandardScaler().fit(clr_transform(Xsub, replacement))
        Xstd = scaler_sub.transform(clr_transform(Xsub, replacement))

        sil_scores = {}
        candidates = []
        max_k_exclusive = 4 if typ == "高钾" else 5
        for k in range(2, min(max_k_exclusive, len(sub))):
            for name, Xuse in [("ward_clr", Xstd)]:
                lab = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(Xuse)
                sizes = np.bincount(lab, minlength=k)
                if sizes.min() < min_size:
                    continue
                sil = float(silhouette_score(Xstd, lab))
                score = sil
                candidates.append((score, sil, k, name, lab, sizes.tolist()))
                sil_scores[f"{name}_k{k}"] = sil

        if not candidates:
            best_k = 2
            labels = AgglomerativeClustering(
                n_clusters=best_k, linkage="ward"
            ).fit_predict(Xstd)
            sil_scores = {
                "ward_clr_k2": float(silhouette_score(Xstd, labels))
            }
        else:
            candidates.sort(key=lambda t: t[0], reverse=True)
            _, sil, best_k, method, labels, sizes = candidates[0]
            print(f"  {typ}: best={method}, k={best_k}, sil={sil:.3f}, sizes={sizes}")

        print(f"  {typ}: 最终 k={best_k}, 簇规模={np.bincount(labels).tolist()}")
        sub = sub.copy()
        tmp = sub.copy()
        tmp["_lab"] = labels
        order = tmp.groupby("_lab")["二氧化硅(SiO2)"].mean().sort_values(ascending=False).index.tolist()
        remap = {old: new for new, old in enumerate(order)}
        labels = np.array([remap[i] for i in labels])
        sub["亚类"] = [f"{typ}-亚类{i+1}" for i in labels]

        centers = sub.groupby("亚类")[feats].mean()
        centers.to_csv(RES / f"p2_subclass_centers_{typ}.csv", encoding="utf-8-sig")
        center_model = pd.DataFrame(Xstd, index=sub.index).groupby(sub["亚类"]).mean()

        # weathering overlap by subclass
        weather_ct = pd.crosstab(sub["亚类"], sub["风化标签"])
        weather_ct.to_csv(RES / f"p2_subclass_weather_{typ}.csv", encoding="utf-8-sig")

        Zlink = linkage(Xstd, method="ward")
        fig, ax = plt.subplots(figsize=(9.5, 3.6))
        dendrogram(Zlink, labels=sub["文物采样点"].astype(str).tolist(),
                   leaf_rotation=90, ax=ax, color_threshold=0.7 * max(Zlink[:, 2]))
        ax.set_title(f"{typ}玻璃层次聚类树状图 (Ward, CLR)")
        ax.set_ylabel("距离")
        style_ax(ax)
        savefig(f"fig2_4_dendrogram_{typ}.png")

        Zp = PCA(n_components=2, random_state=42).fit_transform(Xstd)
        fig, ax = plt.subplots(figsize=(5.6, 4.6))
        palette = [C_K, "#42949E", C_PB, "#7C6CCF"]
        for i, lab in enumerate(sorted(sub["亚类"].unique())):
            m = sub["亚类"] == lab
            ax.scatter(Zp[m, 0], Zp[m, 1], label=lab, s=52, alpha=0.88,
                       c=palette[i % len(palette)], edgecolors="white", linewidths=0.6)
            confidence_ellipse(Zp[m, 0], Zp[m, 1], ax, facecolor=palette[i % len(palette)],
                               alpha=0.10, edgecolor=palette[i % len(palette)], lw=1.0)
        ax.set_xlabel("PC1 (CLR)")
        ax.set_ylabel("PC2 (CLR)")
        ax.set_title(f"{typ}玻璃亚类 PCA (k={best_k})")
        ax.legend(fontsize=7, loc="best")
        style_ax(ax)
        savefig(f"fig2_5_subclass_pca_{typ}.png")

        show = [SHORT[c] for c in feats]
        center_short = centers.copy()
        center_short.columns = show
        fig, ax = plt.subplots(figsize=(7.5, 4.0))
        center_short.T.plot(kind="bar", ax=ax,
                            color=[palette[i % len(palette)] for i in range(len(center_short))],
                            edgecolor="white", width=0.78)
        ax.set_ylabel("均值 (%)")
        ax.set_title(f"{typ}玻璃各亚类成分均值")
        ax.tick_params(axis="x", rotation=30)
        ax.legend(fontsize=7, title=None)
        style_ax(ax)
        savefig(f"fig2_6_subclass_means_{typ}.png")

        rng = np.random.default_rng(42)
        aris = []
        for sigma in [0.01, 0.03, 0.05, 0.08, 0.10]:
            ar_list = []
            for _ in range(30):
                noise = rng.normal(0, sigma, size=Xsub.shape)
                Xn = np.clip(Xsub * (1 + noise), 0, None)
                Xn = clr_transform(Xn, replacement)
                Xn = scaler_sub.transform(Xn)
                lab_n = AgglomerativeClustering(n_clusters=best_k, linkage="ward").fit_predict(Xn)
                ar_list.append(adjusted_rand_score(labels, lab_n))
            aris.append({"类型": typ, "相对扰动sigma": sigma, "ARI均值": float(np.mean(ar_list)),
                         "ARI标准差": float(np.std(ar_list))})
        pd.DataFrame(aris).to_csv(RES / f"p2_sensitivity_{typ}.csv", index=False, encoding="utf-8-sig")

        fig, ax = plt.subplots(figsize=(5.2, 3.5))
        adf = pd.DataFrame(aris)
        ax.errorbar(adf["相对扰动sigma"], adf["ARI均值"], yerr=adf["ARI标准差"],
                    marker="o", capsize=3, color=C_K if typ == "高钾" else C_PB,
                    lw=1.5, markersize=6)
        ax.set_xlabel("相对扰动强度 σ")
        ax.set_ylabel("与原划分的 ARI")
        ax.set_title(f"{typ}玻璃亚类划分敏感性")
        ax.set_ylim(0, 1.05)
        style_ax(ax)
        savefig(f"fig2_7_sensitivity_{typ}.png")

        for _, r in sub.iterrows():
            subclass_all.append(
                {
                    "文物采样点": r["文物采样点"],
                    "文物编号": r["文物编号"],
                    "类型": typ,
                    "亚类": r["亚类"],
                    "表面风化": r["风化标签"],
                }
            )

        cluster_models[typ] = {
            "k": best_k,
            "feats": feats,
            "centers": centers,
            "centers_model": center_model,
            "replacement": replacement,
            "scaler": scaler_sub,
            "labels": labels,
            "silhouette": sil_scores,
            "silhouette_best": float(silhouette_score(Xstd, labels)),
            "Xstd_ref": Xstd,
            "sub_index": sub.index.tolist(),
            "sub_data": sub.copy(),
            "weather_ct": weather_ct,
            "weather_model": weather_models[typ],
        }

        by_k = {}
        for key, val in sil_scores.items():
            if "_k" in key:
                kk = int(key.split("_k")[-1])
                by_k[kk] = max(by_k.get(kk, -1), val)
        if by_k:
            fig, ax = plt.subplots(figsize=(4.8, 3.3))
            ks = sorted(by_k)
            ax.plot(ks, [by_k[k] for k in ks], "o-", color=C_PB if typ == "铅钡" else C_K,
                    lw=1.6, markersize=7)
            ax.axvline(best_k, color=C_NEUT, ls="--", lw=1.1, label=f"选定 k={best_k}")
            ax.set_xlabel("聚类数 k")
            ax.set_ylabel("轮廓系数")
            ax.set_title(f"{typ}玻璃：轮廓系数选 k")
            ax.legend()
            style_ax(ax)
            savefig(f"fig2_8_silhouette_{typ}.png")

    subclass_df = pd.DataFrame(subclass_all)
    subclass_df.to_csv(RES / "p2_subclass_assignment.csv", index=False, encoding="utf-8-sig")

    reason = []
    for typ in ["高钾", "铅钡"]:
        sub = cluster_models[typ]["sub_data"].copy()
        feats = cluster_models[typ]["feats"]
        overall_raw = sub[feats].var().mean()
        within_raw = sub.groupby("亚类")[feats].var().mean().mean()
        reason.append({"类型": typ, "总体平均方差": overall_raw, "亚类内平均方差": within_raw,
                       "方差削减比": 1 - within_raw / overall_raw if overall_raw > 0 else np.nan,
                       "最优k": cluster_models[typ]["k"],
                       "最大轮廓系数": cluster_models[typ]["silhouette_best"]})
    pd.DataFrame(reason).to_csv(RES / "p2_合理性.csv", index=False, encoding="utf-8-sig")

    type_model["training_units"] = units
    type_model["oof_support"] = ensemble_oof
    type_model["oof_pred"] = ensemble_pred
    type_model["oof_y"] = y
    type_model["oof_groups"] = groups
    return type_model, dt, cluster_models, subclass_df, rule_summary


# ==================== 3. problem 3 ====================
def problem3(valid: pd.DataFrame, form3: pd.DataFrame, type_model: dict,
             cluster_models: dict, rule_summary: dict):
    print("\n===== 问题3 =====")
    X3 = form3[COMPS].values
    support = predict_type_support(type_model, X3)
    pred = (support >= 0.5).astype(int)
    thr = rule_summary["PbO+BaO最优阈值"]
    pbo_bao = form3["氧化铅(PbO)"].values + form3["氧化钡(BaO)"].values
    thr_pred = (pbo_bao >= thr).astype(int)

    # 文物级 bootstrap 同时反映训练样本选择与模型不确定性。
    train = type_model["training_units"]
    group_ids = train["文物编号"].unique()
    rng = np.random.default_rng(2022)
    boot_support = []
    for _ in range(200):
        sampled = rng.choice(group_ids, size=len(group_ids), replace=True)
        parts = [train[train["文物编号"] == gid] for gid in sampled]
        boot = pd.concat(parts, ignore_index=True)
        yb = (boot["类型"] == "铅钡").astype(int).values
        model_b = fit_type_ensemble(boot[COMPS].values, yb)
        boot_support.append(predict_type_support(model_b, X3))
    boot_support = np.asarray(boot_support)
    support_lo = np.percentile(boot_support, 2.5, axis=0)
    support_hi = np.percentile(boot_support, 97.5, axis=0)
    boot_agree = np.mean((boot_support >= 0.5) == pred, axis=0)

    # 适用域：未知样本到预测类别训练样本的最近 CLR 标准化距离，
    # 与训练集中“异文物同类最近邻距离”比较。
    train_X = train[COMPS].values
    train_Z = type_model["scaler"].transform(
        clr_transform(train_X, type_model["replacement"])
    )
    test_Z = type_model["scaler"].transform(
        clr_transform(X3, type_model["replacement"])
    )
    train_y = (train["类型"] == "铅钡").astype(int).values
    train_groups = train["文物编号"].values
    ref_dist = {0: [], 1: []}
    for i in range(len(train)):
        eligible = (train_y == train_y[i]) & (train_groups != train_groups[i])
        ref_dist[train_y[i]].append(
            float(np.linalg.norm(train_Z[eligible] - train_Z[i], axis=1).min())
        )

    rows = []
    for i, row in form3.iterrows():
        typ = "铅钡" if pred[i] == 1 else "高钾"
        thr_typ = "铅钡" if thr_pred[i] == 1 else "高钾"
        feats = cluster_models[typ]["feats"]
        centers_model = cluster_models[typ]["centers_model"]
        row_composition = row[COMPS].values.astype(float).reshape(1, -1)
        if row["表面风化"] == "风化":
            weather_model = cluster_models[typ]["weather_model"]
            z = clr_transform(row_composition, weather_model["replacement"])
            row_composition = inverse_clr(
                z - weather_model["delta_clr"], row["成分总和"]
            )
        corrected = {
            c: row_composition[0, j] for j, c in enumerate(COMPS)
        }
        x_model = cluster_models[typ]["scaler"].transform(
            clr_transform(
                np.array([[corrected[c] for c in feats]], dtype=float),
                cluster_models[typ]["replacement"],
            )
        )[0]
        dists = ((centers_model.values - x_model) ** 2).sum(axis=1)
        j = int(np.argmin(dists))
        sub_name = centers_model.index[j]
        eligible = train_y == pred[i]
        domain_dist = float(np.linalg.norm(train_Z[eligible] - test_Z[i], axis=1).min())
        domain_pct = float(
            100 * np.mean(np.asarray(ref_dist[pred[i]]) <= domain_dist)
        )
        rows.append(
            {
                "文物编号": row["文物编号"],
                "表面风化": row["表面风化"],
                "预测类型": typ,
                "阈值规则类型": thr_typ,
                "规则一致": typ == thr_typ,
                "铅钡支持度": float(support[i]),
                "铅钡支持度95%下限": float(support_lo[i]),
                "铅钡支持度95%上限": float(support_hi[i]),
                "bootstrap判别一致率": float(boot_agree[i]),
                "高钾支持度": float(1 - support[i]),
                "PbO_BaO": float(pbo_bao[i]),
                "预测亚类": sub_name,
                "CLR空间亚类质心距离": float(np.sqrt(dists[j])),
                "适用域最近邻距离": domain_dist,
                "适用域距离百分位": domain_pct,
                "超出适用域": bool(domain_pct > 97.5),
                "成分总和": row["成分总和"],
                "有效": bool(row["有效"]),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(RES / "p3_prediction.csv", index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    x = np.arange(len(out))
    ax.bar(x, out["高钾支持度"], label="高钾", color=C_K, edgecolor="white")
    ax.bar(x, out["铅钡支持度"], bottom=out["高钾支持度"], label="铅钡", color=C_PB, edgecolor="white")
    ax.errorbar(
        x,
        out["铅钡支持度"],
        yerr=np.vstack([
            np.maximum(out["铅钡支持度"] - out["铅钡支持度95%下限"], 0),
            np.maximum(out["铅钡支持度95%上限"] - out["铅钡支持度"], 0),
        ]),
        fmt="none", ecolor=C_NEUT, capsize=2, lw=0.8,
    )
    ax.axhline(0.5, color=C_NEUT, ls=":", lw=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(out["文物编号"])
    ax.set_ylabel("模型支持度")
    ax.set_title("表单3未知样品类别支持度（误差线：文物 bootstrap 95%区间）")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right")
    style_ax(ax)
    savefig("fig3_1_predict_proba.png")

    rng = np.random.default_rng(0)
    sens_rows = []
    for sigma in [0.01, 0.03, 0.05, 0.08, 0.10, 0.15]:
        flip = np.zeros(len(form3))
        conf = []
        for _ in range(100):
            noise = rng.normal(0, sigma, size=X3.shape)
            Xn = np.clip(X3 * (1 + noise), 0, None)
            sn = predict_type_support(type_model, Xn)
            pn = (sn >= 0.5).astype(int)
            flip += (pn != pred).astype(float)
            conf.append(np.maximum(sn, 1 - sn))
        flip_rate = flip / 100
        for i in range(len(form3)):
            sens_rows.append(
                {
                    "文物编号": form3.iloc[i]["文物编号"],
                    "sigma": sigma,
                    "翻转率": float(flip_rate[i]),
                    "平均最大支持度": float(np.mean([c[i] for c in conf])),
                }
            )
    sens = pd.DataFrame(sens_rows)
    sens.to_csv(RES / "p3_sensitivity.csv", index=False, encoding="utf-8-sig")

    piv = sens.pivot(index="文物编号", columns="sigma", values="翻转率")
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    sns.heatmap(piv, annot=True, fmt=".2f", cmap="YlOrRd", ax=ax, vmin=0, vmax=0.5,
                linewidths=0.5, linecolor="white",
                cbar_kws={"label": "翻转率"})
    ax.set_title("类别预测敏感性：扰动下翻转率")
    ax.set_xlabel("相对扰动 σ")
    savefig("fig3_2_sensitivity_flip.png")

    loo_pred = type_model["oof_pred"]
    y = type_model["oof_y"]
    cm = confusion_matrix(y, loo_pred)
    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=["高钾", "铅钡"], yticklabels=["高钾", "铅钡"], ax=ax,
                linewidths=0.8, linecolor="white", cbar=False,
                annot_kws={"fontsize": 14})
    ax.set_xlabel("预测")
    ax.set_ylabel("真实")
    ax.set_title(f"按文物分组留一验证 (acc={(loo_pred==y).mean():.1%})")
    savefig("fig3_3_loo_cm.png")

    return out


# ==================== 4. problem 4 ====================
def problem4(valid: pd.DataFrame, weather_models: dict):
    print("\n===== 问题4 =====")
    # 先逐采样点校正风化，再合并为一个文物级组成；不能先跨风化状态平均。
    data = artifact_units(weather_correct_data(valid, weather_models))
    groups = {
        typ: data[data["类型"] == typ].copy()
        for typ in ["高钾", "铅钡"]
    }
    raw_groups = {
        typ: valid[valid["类型"] == typ]
        for typ in ["高钾", "铅钡"]
    }
    keep = [
        c for c in COMPS
        if all((raw_groups[t][c] > 0).mean() >= 0.20
               and raw_groups[t][c].std() > 0.05
               for t in groups)
    ]
    labels = [SHORT[c] for c in keep]
    replacement = estimate_replacement(data[keep].values)

    def residual_log(sub: pd.DataFrame) -> np.ndarray:
        X = np.where(sub[keep].values > 0, sub[keep].values, replacement)
        L = np.log(close_composition(X, 1.0))
        weather = sub["风化标签"].eq("风化").astype(int).values
        R = L.copy()
        for level in np.unique(weather):
            idx = weather == level
            R[idx] -= R[idx].mean(axis=0, keepdims=True)
        return R

    def rho_matrix(R: np.ndarray) -> np.ndarray:
        cov = np.cov(R, rowvar=False)
        var = np.diag(cov)
        denom = var[:, None] + var[None, :]
        rho = np.divide(2 * cov, denom, out=np.zeros_like(cov), where=denom > 0)
        np.fill_diagonal(rho, 1.0)
        return rho

    results = {}
    rho_mats = {}
    spearman_mats = {}
    rng = np.random.default_rng(42)
    for typ, sub in groups.items():
        R = residual_log(sub)
        rho = rho_matrix(R)
        spearman = np.asarray(stats.spearmanr(sub[keep], axis=0).statistic)
        rho_df = pd.DataFrame(rho, index=labels, columns=labels)
        sp_df = pd.DataFrame(spearman, index=labels, columns=labels)
        rho_mats[typ], spearman_mats[typ] = rho_df, sp_df
        rho_df.to_csv(RES / f"p4_proportionality_{typ}.csv", encoding="utf-8-sig")
        sp_df.to_csv(RES / f"p4_corr_{typ}.csv", encoding="utf-8-sig")

        rows = []
        for i in range(len(keep)):
            for j in range(i + 1, len(keep)):
                obs = rho[i, j]
                perm = np.empty(499)
                weather_level = sub["风化标签"].to_numpy()
                for b in range(len(perm)):
                    Rp = R.copy()
                    for level in np.unique(weather_level):
                        idx = np.flatnonzero(weather_level == level)
                        Rp[idx, j] = rng.permutation(Rp[idx, j])
                    perm[b] = rho_matrix(Rp)[i, j]
                p = (1 + np.sum(np.abs(perm) >= abs(obs))) / (len(perm) + 1)
                boots = np.empty(500)
                for b in range(len(boots)):
                    idx = rng.integers(0, len(sub), len(sub))
                    boots[b] = rho_matrix(R[idx])[i, j]
                rows.append({
                    "类型": typ,
                    "成分1": labels[i],
                    "成分2": labels[j],
                    "比例协调系数rho": float(obs),
                    "rho_CI低": float(np.percentile(boots, 2.5)),
                    "rho_CI高": float(np.percentile(boots, 97.5)),
                    "p值_置换": float(p),
                    "Spearman_r_原始": float(spearman[i, j]),
                })
        pairs = pd.DataFrame(rows)
        pairs["p_FDR"] = bh_fdr(pairs["p值_置换"].values)
        pairs["稳健关联"] = (pairs["rho_CI低"] > 0) | (pairs["rho_CI高"] < 0)
        results[typ] = pairs

        fig, ax = plt.subplots(figsize=(6.8, 5.8))
        mask = np.triu(np.ones_like(rho, dtype=bool), k=1)
        sns.heatmap(rho_df, mask=mask, cmap="RdBu_r", center=0, vmin=-1, vmax=1,
                    square=True, ax=ax, linewidths=0.4, linecolor="white",
                    cbar_kws={"label": "比例协调系数 ρ"})
        annot_heatmap(ax, np.where(mask, np.nan, rho), thr=0.55)
        ax.set_title(f"{typ}玻璃：控制风化后的成分比例协调")
        savefig(f"fig4_1_corr_{typ}.png")

        fig, ax = plt.subplots(figsize=(6.8, 5.8))
        sns.heatmap(sp_df, mask=mask, cmap="RdBu_r", center=0, vmin=-1, vmax=1,
                    square=True, ax=ax, linewidths=0.4, linecolor="white",
                    cbar_kws={"label": "原始 Spearman r"})
        annot_heatmap(ax, np.where(mask, np.nan, spearman), thr=0.55)
        ax.set_title(f"{typ}玻璃：原始 Spearman 相关（敏感性对照）")
        savefig(f"fig4_2_clr_corr_{typ}.png")

    all_pairs = pd.concat(results.values(), ignore_index=True)
    all_pairs.to_csv(RES / "p4_all_pairs.csv", index=False, encoding="utf-8-sig")
    diff = rho_mats["高钾"] - rho_mats["铅钡"]
    diff.to_csv(RES / "p4_corr_diff.csv", encoding="utf-8-sig")
    iu = np.triu_indices(len(keep), k=1)
    obs_stat = float(np.linalg.norm(diff.values[iu]))

    # 正确的组间检验：在每个风化层内整体置换“类型”标签，保持样本量和
    # 类型×风化构成；每次重算两个完整关联矩阵，而非打乱矩阵元素。
    observed_pair_diff = diff.values[iu]
    perm_stats = np.empty(999)
    perm_pair_diff = np.empty((999, len(observed_pair_diff)))
    original_type = data["类型"].to_numpy()
    weather = data["风化标签"].to_numpy()
    for b in range(999):
        perm_type = original_type.copy()
        for level in np.unique(weather):
            idx = np.flatnonzero(weather == level)
            perm_type[idx] = rng.permutation(perm_type[idx])
        mats = []
        for typ in ["高钾", "铅钡"]:
            subp = data.loc[perm_type == typ].copy()
            mats.append(rho_matrix(residual_log(subp)))
        dp = (mats[0] - mats[1])[iu]
        perm_pair_diff[b] = dp
        perm_stats[b] = np.linalg.norm(dp)
    global_p = float((1 + np.sum(perm_stats >= obs_stat)) / 1000)
    pair_p = (1 + np.sum(np.abs(perm_pair_diff) >= np.abs(observed_pair_diff), axis=0)) / 1000

    differential = []
    for k, (i, j) in enumerate(zip(*iu)):
        differential.append({
            "成分1": labels[i],
            "成分2": labels[j],
            "高钾rho": float(rho_mats["高钾"].iloc[i, j]),
            "铅钡rho": float(rho_mats["铅钡"].iloc[i, j]),
            "Delta_rho_高钾减铅钡": float(observed_pair_diff[k]),
            "p值_分层置换": float(pair_p[k]),
        })
    differential = pd.DataFrame(differential)
    differential["p_FDR"] = bh_fdr(differential["p值_分层置换"].values)
    differential.to_csv(RES / "p4_differential_pairs.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(6.8, 5.8))
    sns.heatmap(diff, cmap="PuOr", center=0, vmin=-1.5, vmax=1.5, square=True,
                ax=ax, linewidths=0.4, linecolor="white",
                cbar_kws={"label": "Δρ (高钾−铅钡)"})
    annot_heatmap(ax, diff.values, thr=0.55)
    ax.set_title(f"比例协调结构差异（分层置换 p={global_p:.3f}）")
    savefig("fig4_3_corr_diff.png")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    for ax, typ, color in zip(axes, ["高钾", "铅钡"], [C_K, C_PB]):
        strong = results[typ].copy()
        strong["abs_rho"] = strong["比例协调系数rho"].abs()
        strong = strong.sort_values("abs_rho", ascending=False).head(8)
        pair_labels = strong["成分1"] + "–" + strong["成分2"]
        bar_colors = [C_PB if v < 0 else C_K for v in strong["比例协调系数rho"]]
        ax.barh(pair_labels[::-1], strong["比例协调系数rho"].values[::-1],
                color=bar_colors[::-1], edgecolor="white", height=0.7)
        ax.axvline(0, color=C_NEUT, lw=0.8)
        ax.set_xlabel("比例协调系数 ρ")
        ax.set_title(f"{typ}玻璃 |ρ| Top8", color=color, fontweight="bold")
        style_ax(ax)
    fig.suptitle("控制风化后的主要成分关联", y=1.02, fontsize=11)
    savefig("fig4_4_top_pairs.png")

    summary = {
        "分析单元": "文物级均值（同一文物多采样点不重复计权）",
        "主指标": "控制风化状态后的比例协调系数rho",
        "共同成分数": len(keep),
        "组间差异统计量": obs_stat,
        "组间分层置换p值": global_p,
        "组间检验解释": (
            "p<0.05，支持两类关联结构存在总体差异"
            if global_p < 0.05 else
            "当前样本不足以在0.05水平确认两类关联结构总体不同"
        ),
        "FDR显著差异成分对数": int((differential["p_FDR"] < 0.05).sum()),
        "高钾主要关联": results["高钾"].assign(
            abs_rho=lambda d: d["比例协调系数rho"].abs()
        ).sort_values("abs_rho", ascending=False).head(5).to_dict("records"),
        "铅钡主要关联": results["铅钡"].assign(
            abs_rho=lambda d: d["比例协调系数rho"].abs()
        ).sort_values("abs_rho", ascending=False).head(5).to_dict("records"),
    }
    with open(RES / "p4_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=float)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    return summary


# ==================== main ====================
def main():
    for legacy in [
        "p4_clr_corr_高钾.csv", "p4_clr_corr_铅钡.csv",
        "p4_corr_pval_高钾.csv", "p4_corr_pval_铅钡.csv",
        "p4_corr_pval_fdr_高钾.csv", "p4_corr_pval_fdr_铅钡.csv",
    ]:
        (RES / legacy).unlink(missing_ok=True)
    form1, merged, valid, form3 = load_and_clean()
    weather_models, stats_df = problem1(form1, valid)
    type_model, dt, cluster_models, subclass_df, rule_summary = problem2(
        valid, weather_models
    )
    pred3 = problem3(valid, form3, type_model, cluster_models, rule_summary)
    summary4 = problem4(valid, weather_models)

    overview = {
        "有效采样点数": int(len(valid)),
        "无效采样点": merged.loc[~merged["有效"], "文物采样点"].tolist(),
        "高钾样本数": int((valid["类型"] == "高钾").sum()),
        "铅钡样本数": int((valid["类型"] == "铅钡").sum()),
        "分类规则": rule_summary,
        "表单3预测": pred3.to_dict("records"),
        "问题4摘要": summary4,
        "亚类计数": {
            f"{a}|{b}": int(v)
            for (a, b), v in subclass_df.groupby(["类型", "亚类"]).size().items()
        },
        "FDR显著成分": stats_df[stats_df["显著_FDR<0.05"]][["类型", "成分", "风化系数", "p_FDR"]]
        .to_dict("records"),
    }
    with open(RES / "overview.json", "w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2, default=str)
    print("\n[DONE] 全部结果已写入", RES)
    print("[DONE] 全部图片已写入", FIG)


if __name__ == "__main__":
    main()
