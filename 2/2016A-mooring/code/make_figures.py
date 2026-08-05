#!/usr/bin/env python3
"""Generate Chinese-labeled figures for 2016A mooring results (rev2)."""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

# Register an available CJK font file explicitly (Noto CJK TTC).
_CJK_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
_CJK_FONT = None
for _p in _CJK_CANDIDATES:
    if os.path.exists(_p):
        try:
            font_manager.fontManager.addfont(_p)
            _CJK_FONT = font_manager.FontProperties(fname=_p).get_name()
            break
        except Exception:
            continue
if _CJK_FONT:
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [_CJK_FONT, "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, os.path.dirname(__file__))
from mooring_solve import solve_static, result_to_public

ROOT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(ROOT, exist_ok=True)


def plot_system_shapes():
    fig, ax = plt.subplots(figsize=(9, 5.5))
    cases = [
        (12.0, 1200.0, 0.0, "C0", "-", "12 m/s，球 1200 kg"),
        (24.0, 1200.0, 0.0, "C1", "-", "24 m/s，球 1200 kg"),
        (36.0, 1200.0, 0.0, "C2", "-", "36 m/s，球 1200 kg"),
    ]
    # Q2 optimized mass from metrics if present
    opt_m = 2238.0
    metrics_path = os.path.join(ROOT, "metrics.json")
    if os.path.exists(metrics_path):
        with open(metrics_path, encoding="utf-8") as f:
            report = json.load(f)
        if report.get("q2_ball_search_A", {}).get("found"):
            opt_m = report["q2_ball_search_A"]["best"]["ball_mass"]
    cases.append((36.0, opt_m, 0.0, "C3", "--", f"36 m/s，球 {opt_m:.0f} kg（Q2）"))

    for v, m, vc, color, ls, label in cases:
        r = solve_static(v, 18.0, m, "II", 22.05, family="A", v_cur=vc)
        ax.plot(r.system_x, r.system_y, color=color, ls=ls, lw=2, label=label)
        # mark barrel segment roughly: after buoy(3 pts) + 4 pipes
        if len(r.system_x) > 8:
            ax.scatter([r.system_x[7]], [r.system_y[7]], color=color, s=18, zorder=3)

    ax.axhline(0.0, color="k", lw=1.2, alpha=0.7)
    ax.text(0.02, 0.15, "海床", transform=ax.get_yaxis_transform(), fontsize=9)
    ax.set_xlabel("水平位移（自浮标轴，m）")
    ax.set_ylabel("距海床高度（m）")
    ax.set_title("系泊系统整体构型（水深 18 m，II 型链）")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "fig_chain_shape.png"), dpi=150)
    plt.close(fig)


def plot_ball_sweep():
    ms = np.linspace(1200, 4000, 57)
    barrels, anchors, swims = [], [], []
    for m in ms:
        r = solve_static(36.0, 18.0, float(m), "II", 22.05, family="A")
        barrels.append(r.barrel_angle_deg if r.ok else np.nan)
        anchors.append(r.anchor_angle_deg if r.ok else np.nan)
        swims.append(r.swim_radius if r.ok else np.nan)
    fig, ax1 = plt.subplots(figsize=(8.5, 4.8))
    ax1.plot(ms, barrels, label="钢桶倾角")
    ax1.plot(ms, anchors, label="锚端–海床夹角")
    ax1.axhline(5, color="gray", ls="--", lw=1, label="钢桶 5° 限")
    ax1.axhline(16, color="black", ls=":", lw=1, label="锚端 16° 限")
    ax1.set_xlabel("重物球质量（kg）")
    ax1.set_ylabel("角度（°）")
    ax2 = ax1.twinx()
    ax2.plot(ms, swims, "C2", alpha=0.75, label="游动半径")
    ax2.set_ylabel("游动半径（m）")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)
    ax1.set_title("问题2：风速 36 m/s，水深 18 m，II 型链 22.05 m")
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "fig_ball_sweep.png"), dpi=150)
    plt.close(fig)


def plot_family_contrast():
    rows = []
    for v in [12, 24, 36]:
        for fam in ["A", "B"]:
            r = solve_static(float(v), 18.0, 1200.0, "II", 22.05, family=fam)
            rows.append(result_to_public(r))
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.6))
    metrics = ["barrel_angle_deg", "anchor_angle_deg", "swim_radius_m"]
    titles = ["钢桶倾角（°）", "锚端夹角（°）", "游动半径（m）"]
    for ax, met, title in zip(axes, metrics, titles):
        for fam, marker, name in [("A", "o", "离散链 A"), ("B", "s", "悬链 B")]:
            xs = [r["v_wind"] for r in rows if r["family"] == fam]
            ys = [r[met] for r in rows if r["family"] == fam]
            ax.plot(xs, ys, marker=marker, label=name)
        ax.set_xlabel("风速（m/s）")
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("族对照：离散链 A vs 连续悬链 B（球重 1200 kg）")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "fig_family_contrast.png"), dpi=150)
    plt.close(fig)


def plot_q3_scenarios(design):
    if not design or not design.get("best_train_rows"):
        return
    rows = design["best_train_rows"]
    labels = [f"h={r['depth']:g}\nvw={r['v_wind']:g}\nvc={r['v_cur']:g}" for r in rows]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(rows))
    ax.bar(x - 0.15, [r["barrel_angle_deg"] for r in rows], 0.3, label="钢桶倾角")
    ax.bar(x + 0.15, [r["anchor_angle_deg"] for r in rows], 0.3, label="锚端夹角")
    ax.axhline(5, color="gray", ls="--", lw=1, label="硬约束 5°")
    ax.axhline(4, color="C0", ls=":", lw=1, alpha=0.7, label="软裕度 4°")
    ax.axhline(16, color="black", ls=":", lw=1, label="硬约束 16°")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("角度（°）")
    b = design["best"]
    ax.set_title(
        f"问题3推荐方案 {b['chain_type']}型 L={b['chain_length']} m（{b.get('n_links','?')}节）"
        f" 球={b['ball_mass']} kg（训练情景）"
    )
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "fig_q3_scenarios.png"), dpi=150)
    plt.close(fig)


def plot_pareto(design):
    front = (design or {}).get("pareto_front") or []
    if len(front) < 2:
        return
    fig, ax = plt.subplots(figsize=(7.5, 5))
    sw = [p["mean_swim"] for p in front]
    dr = [p["mean_draft"] for p in front]
    ms = [p["ball_mass"] for p in front]
    sc = ax.scatter(sw, dr, c=ms, cmap="viridis", s=55, edgecolors="k", linewidths=0.4)
    cb = fig.colorbar(sc, ax=ax)
    cb.set_label("重物球质量（kg）")
    best = design.get("best")
    if best:
        ax.scatter(
            [best["mean_swim"]],
            [best["mean_draft"]],
            s=140,
            marker="*",
            c="crimson",
            label="推荐方案",
            zorder=5,
        )
    for p in front:
        ax.annotate(
            f"{p['chain_type']}/{p['chain_length']:.2f}/{int(p['ball_mass'])}",
            (p["mean_swim"], p["mean_draft"]),
            fontsize=6,
            alpha=0.75,
            textcoords="offset points",
            xytext=(4, 4),
        )
    ax.set_xlabel("训练情景平均游动半径（m）")
    ax.set_ylabel("训练情景平均吃水（m）")
    ax.set_title("问题3 可行设计 Pareto 前沿（最小化游动半径/吃水/球重/最劣倾角）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "fig_q3_pareto.png"), dpi=150)
    plt.close(fig)


def main():
    plot_system_shapes()
    plot_ball_sweep()
    plot_family_contrast()
    metrics_path = os.path.join(ROOT, "metrics.json")
    if os.path.exists(metrics_path):
        with open(metrics_path, encoding="utf-8") as f:
            report = json.load(f)
        design = report.get("q3_design")
        plot_q3_scenarios(design)
        plot_pareto(design)
    print("figures written to", ROOT)


if __name__ == "__main__":
    main()
