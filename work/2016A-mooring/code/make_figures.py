#!/usr/bin/env python3
"""Generate figures for 2016A mooring results."""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from mooring_solve import solve_static, result_to_public, search_ball_mass

ROOT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(ROOT, exist_ok=True)


def plot_chain_shapes():
    fig, ax = plt.subplots(figsize=(8, 5))
    for v, color in [(12, "C0"), (24, "C1"), (36, "C2")]:
        r = solve_static(v, 18.0, 1200.0, "II", 22.05, family="A")
        # build full profile from buoy bottom: accumulate rigid then chain
        # For illustration plot chain only in seabed frame: x from anchor side
        x = np.array(r.chain_x)
        y = np.array(r.chain_y)
        # y downward from chain top; convert to height above seabed
        # chain top height above seabed ≈ depth - draft - rigid_vert
        # simpler: plot y_down vs x with seabed at max y of suspended+ground
        y_bed = y[-1] if len(y) else 0
        ax.plot(x, y_bed - y, color=color, label=f"v={v} m/s (ball=1200kg)")
    r2 = solve_static(36.0, 18.0, 2300.0, "II", 22.05, family="A")
    x = np.array(r2.chain_x)
    y = np.array(r2.chain_y)
    y_bed = y[-1]
    ax.plot(x, y_bed - y, "C3--", lw=2, label="v=36, ball=2300kg (Q2)")
    ax.set_xlabel("Horizontal distance from chain top (m)")
    ax.set_ylabel("Height above local chain bottom (m)")
    ax.set_title("Anchor chain shape (Family A)")
    ax.legend()
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
    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.plot(ms, barrels, label="barrel angle")
    ax1.plot(ms, anchors, label="anchor-seabed angle")
    ax1.axhline(5, color="gray", ls="--", lw=1, label="5° barrel limit")
    ax1.axhline(16, color="black", ls=":", lw=1, label="16° anchor limit")
    ax1.set_xlabel("Ball mass (kg)")
    ax1.set_ylabel("Angle (deg)")
    ax2 = ax1.twinx()
    ax2.plot(ms, swims, "C2", alpha=0.7, label="swim radius")
    ax2.set_ylabel("Swim radius (m)")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)
    ax1.set_title("Q2: wind 36 m/s, depth 18 m, chain II 22.05 m")
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
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5))
    metrics = ["barrel_angle_deg", "anchor_angle_deg", "swim_radius_m"]
    titles = ["Barrel angle (°)", "Anchor angle (°)", "Swim radius (m)"]
    for ax, met, title in zip(axes, metrics, titles):
        for fam, marker in [("A", "o"), ("B", "s")]:
            xs = [r["v_wind"] for r in rows if r["family"] == fam]
            ys = [r[met] for r in rows if r["family"] == fam]
            ax.plot(xs, ys, marker=marker, label=f"Family {fam}")
        ax.set_xlabel("Wind (m/s)")
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("Family A (discrete) vs B (catenary), ball=1200 kg")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "fig_family_contrast.png"), dpi=150)
    plt.close(fig)


def plot_q3_scenarios(design):
    if not design or not design.get("best_train_rows"):
        return
    rows = design["best_train_rows"]
    labels = [f"h={r['depth']}\nw={r['v_wind']}\nc={r['v_cur']}" for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(rows))
    ax.bar(x - 0.15, [r["barrel_angle_deg"] for r in rows], 0.3, label="barrel°")
    ax.bar(x + 0.15, [r["anchor_angle_deg"] for r in rows], 0.3, label="anchor°")
    ax.axhline(5, color="gray", ls="--", lw=1)
    ax.axhline(16, color="black", ls=":", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("Angle (deg)")
    b = design["best"]
    ax.set_title(f"Q3 design {b['chain_type']} L={b['chain_length']}m ball={b['ball_mass']}kg (train)")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "fig_q3_scenarios.png"), dpi=150)
    plt.close(fig)


def main():
    plot_chain_shapes()
    plot_ball_sweep()
    plot_family_contrast()
    metrics_path = os.path.join(ROOT, "metrics.json")
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            report = json.load(f)
        plot_q3_scenarios(report.get("q3_design"))
    print("figures written to", ROOT)


if __name__ == "__main__":
    main()
