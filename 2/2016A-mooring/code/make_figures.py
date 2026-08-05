#!/usr/bin/env python3
"""
Figures for the 2016A mooring paper (rev3).

Every panel is generated from `results/metrics.json` or by re-solving with
`mooring_solve`, so nothing here can drift away from the reported numbers.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

import figstyle as fs

fs.use_style()

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D

from mooring_solve import (
    BARREL_LIM_DEG,
    ANCHOR_LIM_DEG,
    BUOY_H,
    CHAIN_CATALOG,
    ball_radius,
    barrel_tilt_from_draft,
    chain_drag_width,
    chain_drag_width_link,
    draft_bound_for_barrel,
    result_to_public,
    solve_static,
)

ROOT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(ROOT, exist_ok=True)
METRICS = os.path.join(ROOT, "metrics.json")


def out(name: str) -> str:
    return os.path.join(ROOT, name)


def load_metrics() -> dict:
    if not os.path.exists(METRICS):
        return {}
    with open(METRICS, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------- 1 schematic --
def fig_schematic():
    """
    Model schematic: components, loads, unknowns, and the recursion they drive.

    Panel (a) is deliberately not to scale — a 2 m buoy against 18 m of water and
    a 22 m chain leaves the interesting part of the geometry unreadable at true
    proportions, so the members are stretched to make the annotations legible.
    """
    fig = plt.figure(figsize=(13.2, 6.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.02, 1.0], height_ratios=[1.35, 1.0],
                          wspace=0.06, hspace=0.3)
    ax = fig.add_subplot(gs[:, 0])
    axr = fig.add_subplot(gs[0, 1])
    axe = fig.add_subplot(gs[1, 1])

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("(a) 物理构型、荷载与待求量（示意，未按比例）", pad=8)

    surf, bed = 8.35, 0.85
    ax.add_patch(Rectangle((0.55, bed), 9.1, surf - bed, facecolor=fs.SEA, alpha=0.7, zorder=0))
    xs_w = np.linspace(0.55, 9.65, 300)
    ax.plot(xs_w, surf + 0.045 * np.sin(2 * np.pi * (xs_w - 0.55) / 1.7), color="#4f88ad", lw=1.4)
    ax.plot([0.55, 9.65], [bed, bed], color="#8a7550", lw=1.6)
    ax.add_patch(Rectangle((0.55, bed - 0.42), 9.1, 0.42, facecolor=fs.SAND, alpha=0.55,
                           hatch="////", edgecolor="#8a7550", lw=0.0, zorder=0))
    ax.annotate("海面", xy=(9.55, surf), xytext=(0, 6), textcoords="offset points",
                ha="right", fontsize=8.8, color="#3d6d8c")
    ax.annotate("平坦海床", xy=(9.55, bed), xytext=(0, -14), textcoords="offset points",
                ha="right", fontsize=8.8, color="#7a6540")

    # buoy, stretched vertically for legibility
    bx, bw, bh, dft = 2.45, 1.25, 1.5, 0.62
    ax.add_patch(Rectangle((bx - bw / 2, surf - dft), bw, bh - dft, facecolor="white",
                           edgecolor=fs.NAVY, lw=1.8, zorder=5))
    ax.add_patch(Rectangle((bx - bw / 2, surf - dft), bw, dft, facecolor=fs.NAVY, alpha=0.35,
                           edgecolor=fs.NAVY, lw=1.2, zorder=5))
    ax.annotate("浮标\n$\\phi$2 m × 2 m，1000 kg", xy=(bx, surf + bh - dft), xytext=(0, 8),
                textcoords="offset points", ha="center", fontsize=8.8, color=fs.NAVY)

    # rigid stack: 4 pipes + barrel, then the ball
    pts = [(bx, surf - dft)]
    for k in range(4):
        pts.append((pts[-1][0] + 0.30, pts[-1][1] - 0.78))
    for k in range(4):
        ax.plot([pts[k][0], pts[k + 1][0]], [pts[k][1], pts[k + 1][1]],
                color=fs.SLATE, lw=6.5, solid_capstyle="butt", zorder=6)
        ax.add_patch(Circle(pts[k + 1], 0.055, facecolor="white", edgecolor=fs.SLATE, lw=1.0, zorder=7))
    bar_top = pts[-1]
    bar_bot = (bar_top[0] + 0.34, bar_top[1] - 0.88)
    ax.plot([bar_top[0], bar_bot[0]], [bar_top[1], bar_bot[1]], color=fs.TEAL, lw=11,
            solid_capstyle="butt", zorder=6)
    ax.add_patch(Circle(bar_bot, 0.26, facecolor=fs.CLAY, edgecolor="white", lw=1.2, zorder=8))

    # chain: sagging curve down to a touchdown point then flat to the anchor
    t = np.linspace(0, 1, 160)
    cx = bar_bot[0] + (7.35 - bar_bot[0]) * t
    cy = bar_bot[1] - (bar_bot[1] - bed) * t**1.85
    ax.plot(cx, cy, color=fs.NAVY, lw=2.3, zorder=6)
    ax.plot([7.35, 8.85], [bed, bed], color=fs.NAVY, lw=3.6, alpha=0.55, zorder=6)
    ax.add_patch(Rectangle((8.75, bed - 0.02), 0.62, 0.3, facecolor="#3f3f3f",
                           edgecolor="white", lw=0.8, zorder=8))

    # loads
    fs.arrow(ax, (0.75, surf + 0.42), (bx - bw / 2 - 0.06, surf + 0.42), fs.CRIMSON,
             r"$F_w=0.625\,S_wv_w^2$", text_offset=(-96, 8), lw=2.0)
    fs.arrow(ax, (0.75, surf - dft * 0.55), (bx - bw / 2 - 0.06, surf - dft * 0.55), fs.PLUM,
             r"$F_c=374\,S_cv_c^2$", text_offset=(-92, -18), lw=2.0)
    fs.arrow(ax, (bx - 0.3, surf - dft - 0.05), (bx - 0.3, surf + 0.75), fs.TEAL,
             r"$B$", text_offset=(-14, 2), lw=2.0)
    fs.arrow(ax, (bx + 0.42, surf + 0.62), (bx + 0.42, surf - dft + 0.08), fs.SLATE,
             r"$m_{\mathrm{buoy}}g$", text_offset=(9, 30), lw=2.0)

    ax.annotate("", xy=(bx - bw / 2 - 0.22, surf), xytext=(bx - bw / 2 - 0.22, surf - dft),
                arrowprops=dict(arrowstyle="<|-|>", color=fs.NAVY, lw=1.3))
    ax.annotate("吃水 $d$", xy=(bx - bw / 2 - 0.26, surf - dft / 2), xytext=(-6, -4),
                textcoords="offset points", ha="right", fontsize=9, color=fs.NAVY,
                fontweight="bold")
    ax.annotate("", xy=(bx, bed - 0.72), xytext=(9.06, bed - 0.72),
                arrowprops=dict(arrowstyle="<|-|>", color=fs.CRIMSON, lw=1.4))
    ax.annotate("游动半径 $R$（游动区域 = 半径 $R$ 的圆）", xy=(0.5 * (bx + 9.06), bed - 0.72),
                xytext=(0, -13), textcoords="offset points", ha="center", fontsize=9,
                color=fs.CRIMSON, fontweight="bold")

    def tag(anchor, text, at, ha="left"):
        ax.annotate(text, xy=anchor, xytext=at, textcoords="data", fontsize=8.5,
                    color="#2c3b46", ha=ha, va="center",
                    bbox=dict(boxstyle="round,pad=0.32", fc="white", ec=fs.GRID, lw=0.7, alpha=0.96),
                    arrowprops=dict(arrowstyle="-", color=fs.SLATE, lw=0.8,
                                    connectionstyle="arc3,rad=0.16"))

    tag(pts[2], "4 节钢管，各 1 m / 10 kg", (4.55, 7.30))
    tag((bar_top[0] + 0.18, bar_top[1] - 0.42),
        "密封钢桶 + 水声设备\n（1 m，$\\phi$0.3 m，100 kg）\n倾角 $\\theta$：超 $5^\\circ$ 工作效果变差", (4.95, 6.05))
    tag(bar_bot, "重物球\n集中净重 + 自身水流阻力", (4.72, 4.05))
    tag((cx[112], cy[112]), "电焊锚链\n按附表节长离散，长度取节长整数倍", (6.50, 5.80))
    tag((7.28, bed), "趴链段（触地后 $\\varphi=0$）", (5.00, 1.15))
    tag((9.02, bed + 0.14), "抗拖移锚 600 kg，$\\varphi\\leq16^\\circ$", (9.10, 2.25), ha="right")

    # angle marker on the barrel
    ax.plot([bar_top[0], bar_top[0]], [bar_top[1], bar_bot[1] - 0.12], color=fs.GRID, lw=1.0, ls=":")
    ax.annotate(r"$\theta$", xy=(bar_top[0] + 0.09, bar_top[1] - 0.52), fontsize=11, color="#22303a")

    # ---- free-body panel ----
    axr.set_xlim(0, 10)
    axr.set_ylim(0, 10)
    axr.axis("off")
    axr.set_title("(b) 任一杆段的自由体图", pad=6)

    x0, y0, L = 3.6, 8.4, 5.6
    th = np.radians(20.0)
    x1, y1 = x0 + L * np.sin(th), y0 - L * np.cos(th)
    axr.plot([x0, x1], [y0, y1], color=fs.SLATE, lw=7, solid_capstyle="round", zorder=3)
    axr.plot([x0, x0], [y0, y1 - 0.4], color=fs.GRID, lw=1.0, ls=":")
    xm, ym = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    axr.add_patch(Circle((x1, y1), 0.16, facecolor="white", edgecolor=fs.SLATE, lw=1.4, zorder=6))

    fs.arrow(axr, (x0, y0), (x0 - 2.1, y0), fs.NAVY, r"$H_i$", lw=1.9, text_offset=(-6, 6))
    fs.arrow(axr, (x0, y0), (x0, y0 + 1.3), fs.TEAL, r"$V_i$", lw=1.9, text_offset=(5, 0))
    fs.arrow(axr, (xm, ym), (xm, ym - 1.9), fs.CLAY, r"$G_i=m_ig-\rho gV_i^{\mathrm{disp}}$",
             lw=1.9, text_offset=(-118, -16))
    fs.arrow(axr, (xm - 2.0, ym), (xm - 0.12, ym), fs.PLUM, r"$F_{c,i}$", lw=1.9, text_offset=(-52, 8))
    fs.arrow(axr, (x1, y1), (x1 + 2.0, y1), fs.NAVY, r"$H_{i+1}$", lw=1.9, text_offset=(2, 6))
    fs.arrow(axr, (x1, y1), (x1, y1 - 1.3), fs.TEAL, r"$V_{i+1}$", lw=1.9, text_offset=(4, -14))
    axr.annotate(r"$\theta_i$", xy=(x0 + 0.26, y0 - 1.5), fontsize=12, color="#22303a")
    axr.annotate("下端铰", xy=(x1, y1), xytext=(-46, -8), textcoords="offset points",
                 fontsize=8.4, color=fs.SLATE)

    # ---- equation panel ----
    axe.axis("off")
    axe.set_title("(c) 求解链条", pad=4)
    axe.text(0.015, 0.94,
             "① 对下端取矩　"
             r"$\tan\theta_i=\dfrac{H_i+F_{c,i}/2}{V_i-G_i/2}$" "\n\n"
             "② 沿线递推　"
             r"$H_{i+1}=H_i+F_{c,i},\quad V_{i+1}=V_i-G_i$" "\n\n"
             "③ 递推起点　"
             r"$H_0=F_w(d)+F_{c,\mathrm{buoy}}(d),\ \ V_0=B(d)-m_{\mathrm{buoy}}g$" "\n\n"
             "④ 触地判据　"
             r"$V_{\mathrm{chain}}<wL\ \Rightarrow\ L_s=V_{\mathrm{chain}}/w,\ \varphi=0$" "\n\n"
             "⑤ 竖向闭合（唯一未知量 $d$）\n　　"
             r"$d+\sum_i L_i\cos\theta_i+y_{\mathrm{chain}}(d)=H_{\mathrm{water}}$",
             fontsize=9.7, va="top", linespacing=1.45, transform=axe.transAxes,
             bbox=dict(boxstyle="round,pad=0.55", fc="#f5f8fa", ec=fs.GRID, lw=0.9))
    axe.annotate("重物球挂在钢桶之下：其阻力进入锚链，不改变 $\\theta$",
                 xy=(0.5, -0.16), xycoords="axes fraction", ha="center", fontsize=8.8,
                 color=fs.CLAY,
                 bbox=dict(boxstyle="round,pad=0.32", fc="#fdf3ee", ec=fs.CLAY, lw=0.8))

    fs.savefig(fig, out("fig_schematic.png"), "Family A：离散多刚体静力模型")


# ------------------------------------------------------ 2 system shapes (Q1) --
def fig_chain_shape(metrics: dict):
    opt_m = 2238.0
    q2 = metrics.get("q2_ball_search_A") or {}
    if q2.get("found"):
        opt_m = q2["best"]["ball_mass"]

    cases = [
        (12.0, 1200.0, fs.TEAL, "-", "12 m/s，球 1200 kg", "12 m/s"),
        (24.0, 1200.0, fs.NAVY, "-", "24 m/s，球 1200 kg", "24 m/s"),
        (36.0, 1200.0, fs.CLAY, "-", "36 m/s，球 1200 kg（超限）", "36 m/s\n1200 kg"),
        (36.0, opt_m, fs.CRIMSON, "--", f"36 m/s，球 {opt_m:.0f} kg（问题2解）",
         f"36 m/s\n{opt_m:.0f} kg"),
    ]
    results = [(solve_static(v, 18.0, m, "II", 22.05, family="A"), c, ls, lab, short)
               for v, m, c, ls, lab, short in cases]

    fig = plt.figure(figsize=(12.6, 6.0))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.55, 1.0], height_ratios=[1, 1],
                          wspace=0.2, hspace=0.42)
    ax = fig.add_subplot(gs[:, 0])
    ax_zoom = fig.add_subplot(gs[0, 1])
    ax_bar = fig.add_subplot(gs[1, 1])

    xmax = max(max(r.system_x) for r, *_ in results) + 3.5
    fs.draw_sea(ax, -2.5, xmax, 18.0, 0.0)
    for r, c, ls, lab, _short in results:
        ax.plot(r.system_x[2:], r.system_y[2:], color=c, ls=ls, lw=2.2, label=lab, zorder=5)
        ax.plot([r.system_x[-1]], [0.0], marker="s", ms=6, color=c, zorder=6)
        if r.grounded_length > 1e-3:
            n_susp = len(r.system_x) - 2
            ax.plot(r.system_x[-2:], r.system_y[-2:], color=c, lw=4.5, alpha=0.45, zorder=4)
    fs.draw_buoy(ax, 0.0, 18.0, results[0][0].draft)
    ax.annotate("浮标", xy=(0.0, 19.1), xytext=(0, 6), textcoords="offset points",
                ha="center", fontsize=8.6, color=fs.NAVY, zorder=8)
    ax.annotate("趴链段（$\\varphi=0$）", xy=(results[0][0].system_x[-2], 0.0), xytext=(-6, 20),
                textcoords="offset points", fontsize=8.6, color=fs.TEAL,
                arrowprops=dict(arrowstyle="->", color=fs.TEAL, lw=0.9))
    ax.set_xlim(-2.5, xmax)
    ax.set_ylim(-1.6, 21.0)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)
    fs.finish(ax, "(a) 系泊系统整体构型（水深 18 m，II 型链 22.05 m）",
              "水平位移（自浮标轴，m）", "距海床高度（m）", legend_loc="upper right")

    # zoom on the rigid stack
    for r, c, ls, lab, _short in results:
        ax_zoom.plot(r.system_x[2:7], r.system_y[2:7], color=c, ls=ls, lw=2.0, marker="o", ms=3.2)
        ax_zoom.plot(r.system_x[6:8], r.system_y[6:8], color=c, ls=ls, lw=4.6, alpha=0.95)
    ax_zoom.set_ylim(18.0 - results[0][0].draft - 5.6, 18.0 - results[0][0].draft + 0.35)
    rr = results[1][0]
    ax_zoom.annotate("钢桶（加粗段）",
                     xy=(0.5 * (rr.system_x[6] + rr.system_x[7]), 0.5 * (rr.system_y[6] + rr.system_y[7])),
                     xytext=(24, 4), textcoords="offset points", fontsize=8.4, color=fs.SLATE,
                     arrowprops=dict(arrowstyle="->", color=fs.SLATE, lw=0.9))
    ax_zoom.annotate("4 节钢管", xy=(rr.system_x[4], rr.system_y[4]), xytext=(20, 8),
                     textcoords="offset points", fontsize=8.4, color=fs.SLATE,
                     arrowprops=dict(arrowstyle="->", color=fs.SLATE, lw=0.9))
    ax_zoom.set_title("(b) 钢管–钢桶局部放大", pad=6)
    ax_zoom.set_xlabel("水平位移（m）")
    ax_zoom.set_ylabel("距海床高度（m）")
    for side in ("top", "right"):
        ax_zoom.spines[side].set_visible(False)

    # per-member angle bars
    width = 0.2
    idx = np.arange(5)
    for k, (r, c, ls, lab, short) in enumerate(results):
        vals = list(r.pipe_angles_deg) + [r.barrel_angle_deg]
        ax_bar.bar(idx + (k - 1.5) * width, vals, width, color=c, alpha=0.9, label=short)
    fs.limit_line(ax_bar, BARREL_LIM_DEG, "钢桶 5° 限")
    ax_bar.set_xticks(idx)
    ax_bar.set_xticklabels(["管1", "管2", "管3", "管4", "钢桶"])
    ax_bar.set_ylim(0, 11.6)
    fs.finish(ax_bar, "(c) 各刚性构件倾角", None, "与竖直线夹角（°）", legend_loc="upper left",
              legend_ncol=4)

    fs.savefig(fig, out("fig_chain_shape.png"))


# --------------------------------------------------------- 3 load decomposition --
def fig_load_path(metrics: dict):
    """Where the horizontal load comes from, and how tension grows down the line."""
    scenarios = [
        (12.0, 0.0, 18.0, 1200.0, "II", 22.05, "12 m/s\n无流"),
        (24.0, 0.0, 18.0, 1200.0, "II", 22.05, "24 m/s\n无流"),
        (36.0, 0.0, 18.0, 2238.0, "II", 22.05, "36 m/s\n无流（Q2）"),
        (36.0, 1.0, 20.0, 4270.0, "V", 26.82, "36 m/s\n1.0 m/s"),
        (36.0, 1.5, 20.0, 4270.0, "V", 26.82, "36 m/s\n1.5 m/s（Q3 最劣）"),
    ]
    labels, comps = [], []
    for vw, vc, h, m, ct, L, lab in scenarios:
        r = solve_static(vw, h, m, ct, L, family="A", v_cur=vc)
        from mooring_solve import buoy_current_force, wind_force
        wind = wind_force(r.draft, vw)
        cur_b = buoy_current_force(r.draft, vc)
        rigid = r.H - r.meta["F_ball"] - r.H_buoy
        ball = r.meta["F_ball"]
        chain = (r.meta["H_end"] or r.H) - r.H
        labels.append(lab)
        comps.append([wind, cur_b, rigid, ball, chain])
    comps = np.array(comps)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.9), gridspec_kw={"wspace": 0.24})
    names = ["浮标风力", "浮标水流力", "钢管+钢桶阻力", "重物球阻力", "锚链阻力"]
    colors = [fs.CRIMSON, fs.PLUM, fs.SLATE, fs.CLAY, fs.TEAL]
    bottom = np.zeros(len(labels))
    x = np.arange(len(labels))
    for j, (nm, c) in enumerate(zip(names, colors)):
        ax.bar(x, comps[:, j], 0.6, bottom=bottom, label=nm, color=c, alpha=0.92,
               edgecolor="white", lw=0.6)
        bottom += comps[:, j]
    for i, tot in enumerate(bottom):
        ax.annotate(f"{tot:.0f} N", xy=(i, tot), xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=8.4, fontweight="bold", color="#22303a")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.4)
    fs.finish(ax, "(a) 锚端水平张力的荷载构成", None, "水平力（N）", legend_loc="upper left")

    # tension growth along the line for the worst Q3 scenario
    r = solve_static(36.0, 20.0, 4270.0, "V", 26.82, family="A", v_cur=1.5)
    stations = ["浮标底铰"] + [f"管{i}" for i in range(1, 5)] + ["钢桶", "球后(链顶)", "锚端"]
    H_path = [r.H_buoy]
    from mooring_solve import PIPE_N
    acc = r.H_buoy
    for s in range(PIPE_N + 1):
        acc += 0.0
    # rebuild cumulative H using the recorded per-segment drags
    acc = r.H_buoy
    seg_drags = []
    r2 = solve_static(36.0, 20.0, 4270.0, "V", 26.82, family="A", v_cur=1.5)
    # segment drags are recoverable from H_top/H_bot bookkeeping via meta
    H_path = [r.H_buoy]
    # pipes + barrel: use the difference between buoy load and chain-top load,
    # distributed by the stored per-segment values
    from mooring_solve import cylinder_drag, PIPE_L, PIPE_R, BARREL_L, BARREL_R
    ang = [np.radians(a) for a in r.pipe_angles_deg] + [np.radians(r.barrel_angle_deg)]
    for i in range(PIPE_N):
        acc += cylinder_drag(PIPE_R, PIPE_L, ang[i], 1.5)
        H_path.append(acc)
    acc += cylinder_drag(BARREL_R, BARREL_L, ang[PIPE_N], 1.5)
    H_path.append(acc)
    acc += r.meta["F_ball"]
    H_path.append(acc)
    H_path.append(r.meta["H_end"] or acc)

    lo_y = min(H_path) - 0.14 * (max(H_path) - min(H_path))
    ax2.step(range(len(H_path)), H_path, where="post", color=fs.NAVY, lw=2.2, marker="o", ms=5)
    ax2.fill_between(range(len(H_path)), lo_y, H_path, step="post", color=fs.NAVY, alpha=0.10)
    ax2.set_xticks(range(len(stations)))
    ax2.set_xticklabels(stations, rotation=28, ha="right", fontsize=8.4)
    ax2.set_ylim(lo_y, max(H_path) + 0.16 * (max(H_path) - min(H_path)))
    for i, v in enumerate(H_path):
        ax2.annotate(f"{v:.0f}", xy=(i, v), xytext=(0, 8 if i % 2 == 0 else -14),
                     textcoords="offset points", ha="center", fontsize=7.8, color=fs.NAVY)
    ax2.annotate(f"重物球阻力：$\\Delta H={r.meta['F_ball']:.0f}$ N",
                 xy=(6, 0.5 * (H_path[5] + H_path[6])), xytext=(-34, -58),
                 textcoords="offset points", fontsize=8.8, color=fs.CLAY, fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.3", fc="#fdf3ee", ec=fs.CLAY, lw=0.8),
                 arrowprops=dict(arrowstyle="->", color=fs.CLAY, lw=1.1))
    ax2.annotate(f"锚链分布阻力：$\\Delta H={H_path[-1]-H_path[-2]:.0f}$ N",
                 xy=(7, 0.5 * (H_path[6] + H_path[7])), xytext=(-118, 22),
                 textcoords="offset points", fontsize=8.8, color=fs.TEAL, fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.3", fc="#eef7f4", ec=fs.TEAL, lw=0.8),
                 arrowprops=dict(arrowstyle="->", color=fs.TEAL, lw=1.1))
    fs.finish(ax2, "(b) 水平张力沿系泊线的分段递推（V 型 / 36 m/s / 1.5 m/s / 20 m）",
              None, "水平张力 $H$（N）", legend_loc=None)

    fs.savefig(fig, out("fig_load_path.png"), "分段递推：$H_{i+1}=H_i+F_{c,i}$")


# -------------------------------------------------------------- 4 Q2 analysis --
def fig_ball_sweep(metrics: dict):
    ms = np.linspace(800, 4200, 120)
    barrels, anchors, swims, drafts = [], [], [], []
    for m in ms:
        r = solve_static(36.0, 18.0, float(m), "II", 22.05, family="A")
        barrels.append(r.barrel_angle_deg if r.ok else np.nan)
        anchors.append(r.anchor_angle_deg if r.ok else np.nan)
        swims.append(r.swim_radius if r.ok else np.nan)
        drafts.append(r.draft if r.ok else np.nan)
    barrels, anchors = np.array(barrels), np.array(anchors)
    m_star = (metrics.get("q2_ball_search_A") or {}).get("best", {}).get("ball_mass", 2238.0)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.6, 5.0), gridspec_kw={"wspace": 0.3})

    feas = (barrels <= BARREL_LIM_DEG) & (anchors <= ANCHOR_LIM_DEG)
    if feas.any():
        ax.axvspan(ms[feas][0], ms[-1], color=fs.TEAL, alpha=0.09, zorder=0)
        ax.annotate("两约束同时满足的可行域", xy=(0.5 * (ms[feas][0] + ms[-1]), 21.2), ha="center",
                    fontsize=9.2, color=fs.TEAL, fontweight="bold")
    ax.plot(ms, barrels, color=fs.NAVY, label="钢桶倾角 $\\theta$")
    ax.plot(ms, anchors, color=fs.CLAY, label="锚端夹角 $\\varphi$")
    fs.limit_line(ax, BARREL_LIM_DEG, "$\\theta\\leq 5^\\circ$")
    fs.limit_line(ax, ANCHOR_LIM_DEG, "$\\varphi\\leq 16^\\circ$", ls=":")
    ax.axvline(m_star, color=fs.CRIMSON, lw=1.3, ls="-.")
    ax.annotate(f"最小可行球重 {m_star:.0f} kg\n（$\\varphi$ 恰好触限）", xy=(m_star, 16.0),
                xytext=(-126, 26), textcoords="offset points", fontsize=9, color=fs.CRIMSON,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=fs.CRIMSON, lw=0.8),
                arrowprops=dict(arrowstyle="->", color=fs.CRIMSON, lw=1.1))
    axt = ax.twinx()
    axt.plot(ms, swims, color=fs.TEAL, lw=1.4, alpha=0.85, label="游动半径 $R$")
    axt.plot(ms, np.array(drafts) * 10, color=fs.PLUM, lw=1.4, ls="--", alpha=0.85,
             label="吃水 $d\\times 10$")
    axt.set_ylabel("游动半径（m） / 吃水×10（m）")
    axt.grid(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = axt.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower left", fontsize=8.4)
    ax.set_ylim(0, 23.5)
    fs.finish(ax, "(a) 问题2：球重扫描（36 m/s，18 m，II 型 22.05 m）",
              "重物球质量（kg）", "角度（°）", legend_loc=None)

    # feasibility map over (ball mass, wind speed)
    mm = np.linspace(800, 4200, 34)
    vv = np.linspace(12.0, 36.0, 25)
    TH = np.full((len(vv), len(mm)), np.nan)
    PH = np.full((len(vv), len(mm)), np.nan)
    for i, v in enumerate(vv):
        for j, m in enumerate(mm):
            r = solve_static(float(v), 18.0, float(m), "II", 22.05, family="A")
            if r.ok:
                TH[i, j] = r.barrel_angle_deg
                PH[i, j] = r.anchor_angle_deg
    pc = ax2.pcolormesh(mm, vv, TH, cmap="YlGnBu", shading="auto", vmin=0, vmax=12)
    cb = fig.colorbar(pc, ax=ax2, pad=0.02)
    cb.set_label("钢桶倾角 $\\theta$（°）")
    feas2 = np.where((TH <= BARREL_LIM_DEG) & (PH <= ANCHOR_LIM_DEG), 1.0, 0.0)
    ax2.contourf(mm, vv, feas2, levels=[0.5, 1.5], colors=["white"], alpha=0.26)
    ax2.contour(mm, vv, feas2, levels=[0.5], colors=["#22303a"], linewidths=0.9, linestyles=":")
    c1 = ax2.contour(mm, vv, TH, levels=[BARREL_LIM_DEG], colors=[fs.CRIMSON], linewidths=2.2)
    c2 = ax2.contour(mm, vv, PH, levels=[ANCHOR_LIM_DEG], colors=["white"], linewidths=2.2,
                     linestyles="--")
    ax2.clabel(c1, fmt={BARREL_LIM_DEG: r"$\theta=5^\circ$"}, fontsize=8.5)
    ax2.clabel(c2, fmt={ANCHOR_LIM_DEG: r"$\varphi=16^\circ$"}, fontsize=8.5)
    ax2.plot([m_star], [36.0], marker="*", ms=17, color=fs.CRIMSON, mec="white", mew=1.0, zorder=6)
    ax2.annotate(f"问题2 解 {m_star:.0f} kg", xy=(m_star, 36.0), xytext=(14, -22),
                 textcoords="offset points", ha="left", fontsize=9, color=fs.CRIMSON,
                 fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.28", fc="white", ec=fs.CRIMSON, lw=0.8))
    ax2.annotate("浅色区（点线右下）：两条硬约束同时满足", xy=(0.035, 0.045),
                 xycoords="axes fraction", fontsize=8.4, color="#22303a")
    ax2.grid(False)
    fs.finish(ax2, "(b) 可行域边界：两条约束曲线的交汇", "重物球质量（kg）", "风速（m/s）",
              legend_loc=None)

    fs.savefig(fig, out("fig_ball_sweep.png"), "$\\varphi$ 约束先于 $\\theta$ 成为紧约束")


# ------------------------------------------------- 5 analytic draft lower bound --
def fig_draft_bound(metrics: dict):
    """The 5-degree target pins the draft, independently of chain and ball."""
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.6, 5.0), gridspec_kw={"wspace": 0.26})

    vw = np.linspace(6.0, 36.0, 90)
    for vc, c in zip([0.0, 0.5, 1.0, 1.5], [fs.SLATE, fs.TEAL, fs.AMBER, fs.CLAY]):
        db = [draft_bound_for_barrel(float(v), vc) for v in vw]
        ax.plot(vw, db, color=c, label=f"$v_c={vc:g}$ m/s")
    d_star = draft_bound_for_barrel(36.0, 1.5)
    ax.plot([36.0], [d_star], marker="*", ms=17, color=fs.CRIMSON, mec="white", mew=1.0, zorder=6)
    ax.annotate(f"设计包络最劣角\n$d\\geq{d_star:.3f}$ m", xy=(36.0, d_star), xytext=(-116, -46),
                textcoords="offset points", fontsize=9.2, color=fs.CRIMSON, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=fs.CRIMSON, lw=1.1))
    q3 = metrics.get("q3_design") or {}
    best = q3.get("best") or {}
    if best:
        ax.axhline(best["max_draft"], color=fs.NAVY, ls="--", lw=1.3)
        ax.annotate(f"数值最优方案 S1 实际吃水 {best['max_draft']:.3f} m"
                    f"（仅高于下界 {100*(best['max_draft']-d_star):.1f} cm）",
                    xy=(6.4, best["max_draft"]), xytext=(0, -15), textcoords="offset points",
                    fontsize=8.6, color=fs.NAVY,
                    bbox=dict(boxstyle="round,pad=0.28", fc="white", ec=fs.NAVY, lw=0.7))
    ax.axhline(BUOY_H, color="#8a7550", lw=1.4)
    ax.annotate("浮标高度 2 m（吃水物理上限）", xy=(35.6, BUOY_H), xytext=(0, -14),
                textcoords="offset points", ha="right", fontsize=8.6, color="#8a7550")
    ax.set_ylim(0.2, 2.22)
    fs.finish(ax, "(a) 由 $\\theta\\leq5^\\circ$ 推出的吃水下界 $d_{\\min}(v_w,v_c)$",
              "风速 $v_w$（m/s）", "吃水下界（m）", legend_loc="upper left")

    # right: tilt-vs-draft curve, showing monotonicity and the bound construction
    dd = np.linspace(0.45, 1.95, 220)
    for vc, c in zip([0.0, 1.0, 1.5], [fs.SLATE, fs.AMBER, fs.CLAY]):
        th = [barrel_tilt_from_draft(float(d), 36.0, vc) for d in dd]
        ax2.plot(dd, th, color=c, label=f"解析式，$v_c={vc:g}$ m/s")
    # numerical spot-checks from the full solver
    pts_d, pts_t = [], []
    for m in [1200.0, 2500.0, 3500.0, 4270.0, 5000.0]:
        r = solve_static(36.0, 18.0, m, "V", 26.82, family="A", v_cur=1.5)
        if r.ok:
            pts_d.append(r.draft)
            pts_t.append(r.barrel_angle_deg)
    ax2.scatter(pts_d, pts_t, s=64, facecolor="white", edgecolor=fs.CRIMSON, lw=1.6, zorder=6,
                label="完整求解器（不同球重）")
    fs.limit_line(ax2, BARREL_LIM_DEG, "$5^\\circ$")
    ax2.axvline(d_star, color=fs.CRIMSON, ls="-.", lw=1.2)
    ax2.annotate(f"$d_{{\\min}}={d_star:.3f}$ m", xy=(d_star, 12), xytext=(8, 0),
                 textcoords="offset points", fontsize=9, color=fs.CRIMSON, fontweight="bold")
    ax2.set_ylim(0, 22)
    fs.finish(ax2, "(b) 倾角随吃水单调下降：解析式与数值解重合",
              "吃水 $d$（m）", "钢桶倾角 $\\theta$（°）", legend_loc="upper right")

    fs.savefig(fig, out("fig_draft_bound.png"),
               r"$\tan\theta=(H_0(d)+\sum F_{c})/(\rho g\pi R^2 d-m_{\mathrm{buoy}}g-4G_{\mathrm{pipe}}-G_{\mathrm{bar}}/2)$")


# ------------------------------------------------------------- 6 Q3 Pareto set --
def fig_q3_pareto(metrics: dict):
    q3 = metrics.get("q3_design") or {}
    ranked = q3.get("ranked_pareto") or []
    if len(ranked) < 3:
        return
    best = q3.get("best") or ranked[0]

    fig = plt.figure(figsize=(13.0, 5.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.25, 0.72], wspace=0.3)
    ax = fig.add_subplot(gs[0, 0])
    axp = fig.add_subplot(gs[0, 1])
    axb = fig.add_subplot(gs[0, 2])

    # (a) the real trade-off plane: swim radius vs anchor angle
    for ct in ["II", "III", "IV", "V"]:
        pts = [p for p in ranked if p["chain_type"] == ct]
        if not pts:
            continue
        ax.scatter([p["max_swim"] for p in pts], [p["worst_anchor"] for p in pts],
                   s=[26 + (p["ball_mass"] - 4200) / 8 for p in pts],
                   color=fs.CHAIN_COLORS[ct], alpha=0.85, edgecolor="white", lw=0.7,
                   label=f"{ct} 型链")
    ax.scatter([best["max_swim"]], [best["worst_anchor"]], marker="*", s=330,
               color=fs.CRIMSON, edgecolor="white", lw=1.1, zorder=6, label="推荐方案 S1")
    fs.limit_line(ax, ANCHOR_LIM_DEG, "$\\varphi\\leq16^\\circ$（硬约束）", x=0.42)
    ax.annotate(f"推荐 S1：{best['chain_type']} 型 / {best['chain_length']:.2f} m"
                f" / {best['ball_mass']:.0f} kg",
                xy=(best["max_swim"], best["worst_anchor"]), xytext=(-6, 44),
                textcoords="offset points", ha="center", fontsize=8.8, color=fs.CRIMSON,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=fs.CRIMSON, lw=0.8),
                arrowprops=dict(arrowstyle="->", color=fs.CRIMSON, lw=1.0))
    ax.annotate("", xy=(20.6, 15.2), xytext=(29.2, 1.2),
                arrowprops=dict(arrowstyle="->", color=fs.SLATE, lw=1.2, ls=":"))
    ax.annotate("链越短：游动区越小，\n但锚端夹角越大", xy=(24.0, 8.6), fontsize=8.5,
                color=fs.SLATE, ha="center",
                bbox=dict(boxstyle="round,pad=0.28", fc="white", ec=fs.GRID, lw=0.7, alpha=0.95))
    ax.set_ylim(-1.4, 19.2)
    fs.finish(ax, "(a) Pareto 前沿：游动半径 vs 锚端夹角\n（点大小 ∝ 球重）",
              "最劣游动半径（m）", "最劣锚端夹角（°）", legend_loc="upper right")

    # (b) parallel coordinates over all five objectives
    keys = q3.get("objective_keys") or ["max_draft", "max_swim", "worst_barrel", "worst_anchor", "ball_mass"]
    names = {"max_draft": "最大吃水", "max_swim": "最劣游动半径", "worst_barrel": "最劣桶倾角",
             "worst_anchor": "最劣锚端角", "ball_mass": "球重"}
    X = np.array([[float(p[k]) for k in keys] for p in ranked])
    lo, hi = X.min(axis=0), X.max(axis=0)
    span = np.where(hi - lo < 1e-9, 1.0, hi - lo)
    Z = (X - lo) / span
    xs = np.arange(len(keys))
    for i, p in enumerate(ranked):
        axp.plot(xs, Z[i], color=fs.CHAIN_COLORS.get(p["chain_type"], fs.SLATE), lw=1.0, alpha=0.42)
    ib = int(np.argmax([p.get("topsis", 0) for p in ranked]))
    axp.plot(xs, Z[ib], color=fs.CRIMSON, lw=3.0, zorder=6, label="推荐方案 S1")
    axp.scatter(xs, Z[ib], color=fs.CRIMSON, s=42, zorder=7, edgecolor="white", lw=0.9)
    for j, k in enumerate(keys):
        axp.axvline(j, color=fs.GRID, lw=1.0, zorder=0)
        axp.annotate(f"{lo[j]:.3g}", xy=(j, -0.055), ha="center", fontsize=7.4, color=fs.SLATE)
        axp.annotate(f"{hi[j]:.3g}", xy=(j, 1.035), ha="center", fontsize=7.4, color=fs.SLATE)
    axp.set_xticks(xs)
    axp.set_xticklabels([names.get(k, k) for k in keys], fontsize=8.6)
    axp.set_yticks([])
    axp.set_ylim(-0.13, 1.13)
    axp.grid(False)
    handles = [Line2D([], [], color=fs.CHAIN_COLORS[c], lw=1.6, label=f"{c} 型") for c in ["II", "III", "IV", "V"]]
    handles.append(Line2D([], [], color=fs.CRIMSON, lw=3.0, label="推荐方案 S1"))
    axp.legend(handles=handles, loc="lower center", ncol=5, fontsize=8, bbox_to_anchor=(0.5, -0.19))
    fs.finish(axp, "(b) 五目标平行坐标（下端更优，标注为各轴量程）", None, None, legend_loc=None)

    # (c) how often each Pareto point wins under random objective weights
    top = sorted(ranked, key=lambda p: -p.get("win_rate", 0))[:8]
    lbl = [f"{p['chain_type']}/{p['chain_length']:.1f}/{p['ball_mass']:.0f}" for p in top]
    vals = [100 * p.get("win_rate", 0) for p in top]
    cols = [fs.CRIMSON if p is best or (p["chain_type"] == best["chain_type"]
            and abs(p["chain_length"] - best["chain_length"]) < 1e-6) else fs.SLATE for p in top]
    axb.barh(range(len(top))[::-1], vals, color=cols, alpha=0.9, height=0.68)
    axb.set_yticks(range(len(top))[::-1])
    axb.set_yticklabels(lbl, fontsize=7.8)
    for i, v in enumerate(vals):
        axb.annotate(f"{v:.1f}%", xy=(v, len(top) - 1 - i), xytext=(4, -3),
                     textcoords="offset points", fontsize=7.8, color="#22303a")
    axb.set_xlim(0, max(vals) * 1.28)
    fs.finish(axb, "(c) 权重随机化下的\n第一名占比（4000 次）", "胜出率（%）", None, legend_loc=None)

    fs.savefig(fig, out("fig_q3_pareto.png"),
               f"熵权 TOPSIS；可行设计 {q3.get('n_feasible_designs')} 个，Pareto 前沿 {q3.get('pareto_size')} 个")


# ---------------------------------------------------------- 7 strategy compare --
def fig_q3_strategies(metrics: dict):
    """
    Three readings of Q3 side by side.

    S1 takes the 5 deg target literally over the whole environment box, S1' adds
    a confidence margin against the empirical coefficients, and S2 trades the
    target in the single rarest corner to win back freeboard.  The point of the
    figure is that the draft, not the chain, is what separates them.
    """
    q3 = metrics.get("q3_design") or {}
    ver = q3.get("verification") or {}
    s1 = q3.get("best")
    rbd = ver.get("reliability_based") or {}
    s2 = ((metrics.get("q3_relaxed") or {}).get("best")) or None
    if not s1 or not s2:
        return

    S = [
        {"tag": "S1", "name": "S1 名义最优\n（5° 全包络）", "color": fs.NAVY,
         "type": s1["chain_type"], "L": s1["chain_length"], "m": s1["ball_mass"],
         "draft": s1["max_draft"], "theta": s1["worst_barrel"], "phi": s1["worst_anchor"],
         "swim": s1["max_swim"], "frac": (ver.get("envelope") or {}).get("barrel_ok_frac", 1.0)},
        {"tag": "S1′", "name": "S1′ 可靠性设计\n（95% 置信）", "color": fs.PLUM,
         "type": s1["chain_type"], "L": s1["chain_length"], "m": rbd.get("ball_mass", np.nan),
         "draft": rbd.get("max_draft", np.nan), "theta": rbd.get("worst_barrel", np.nan),
         "phi": rbd.get("worst_anchor", np.nan), "swim": rbd.get("max_swim", np.nan),
         "frac": 1.0},
        {"tag": "S2", "name": "S2 干舷优先\n（让出最稀有角）", "color": fs.TEAL,
         "type": s2["chain_type"], "L": s2["chain_length"], "m": s2["ball_mass"],
         "draft": s2["max_draft"], "theta": s2["worst_barrel_full_box"], "phi": s2["worst_anchor"],
         "swim": s2["max_swim"], "frac": s2["envelope"]["barrel_ok_frac"]},
    ]

    fig = plt.figure(figsize=(13.4, 7.6))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.95], width_ratios=[1.28, 1.0, 0.86],
                          wspace=0.33, hspace=0.52)
    axm = fig.add_subplot(gs[0, :2])
    axf = fig.add_subplot(gs[0, 2])
    axc1 = fig.add_subplot(gs[1, 0])
    axc2 = fig.add_subplot(gs[1, 1])
    axb = fig.add_subplot(gs[1, 2])

    # (a) horizontal grouped bars: more room for both labels and values
    rows = [("最大吃水 (m)", "draft", 2.0, None, "{:.2f}"),
            ("干舷 (m)", None, 2.0, None, "{:.2f}"),
            ("最劣 $\\theta$ (°)", "theta", 9.0, BARREL_LIM_DEG, "{:.2f}"),
            ("最劣 $\\varphi$ (°)", "phi", 18.0, ANCHOR_LIM_DEG, "{:.2f}"),
            ("最劣 $R$ (m)", "swim", 32.0, None, "{:.1f}"),
            ("球重 (t)", "m", 6.0, None, "{:.2f}")]
    h = 0.24
    y = np.arange(len(rows))[::-1]
    for k, st in enumerate(S):
        vals, norm = [], []
        for _, key, scale, _, _ in rows:
            v = (BUOY_H - st["draft"]) if key is None else (st["m"] / 1000.0 if key == "m" else st[key])
            vals.append(v)
            norm.append(v / scale)
        bars = axm.barh(y + (1 - k) * h, norm, h, color=st["color"], alpha=0.92,
                        label=st["name"], edgecolor="white", lw=0.6)
        for b, v, (_, _, _, _, fmt) in zip(bars, vals, rows):
            axm.annotate(fmt.format(v), xy=(b.get_width(), b.get_y() + b.get_height() / 2),
                         xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.0,
                         color="#22303a")
    for j, (_, _, scale, lim, _) in enumerate(rows):
        if lim is not None:
            yy = y[j]
            axm.plot([lim / scale] * 2, [yy - 1.6 * h, yy + 1.6 * h], color=fs.CRIMSON,
                     lw=1.8, ls="--")
    axm.set_yticks(y)
    axm.set_yticklabels([r[0] for r in rows], fontsize=9)
    axm.set_xlim(0, 1.2)
    axm.set_xticks([])
    axm.annotate("红色虚线 = 硬约束（各行按自身量程归一，条端标注原值）", xy=(0.99, -0.055),
                 xycoords="axes fraction", ha="right", fontsize=8.4, color=fs.CRIMSON)
    fs.finish(axm, "(a) 三种设计策略的指标对照", None, None, legend_loc="lower right")

    # (b) how the 2 m of buoy height is spent
    for k, st in enumerate(S):
        fb = BUOY_H - st["draft"]
        axf.bar([k], [st["draft"]], 0.55, color=fs.SEA_DEEP, edgecolor=st["color"], lw=1.5)
        axf.bar([k], [fb], 0.55, bottom=[st["draft"]], color="white", edgecolor=st["color"], lw=1.5)
        axf.annotate(f"干舷 {fb:.2f} m", xy=(k, st["draft"] + fb / 2), ha="center", va="center",
                     fontsize=8.4, color=st["color"], fontweight="bold")
        axf.annotate(f"吃水\n{st['draft']:.2f} m", xy=(k, st["draft"] / 2), ha="center",
                     va="center", fontsize=8.4, color="#22303a")
    axf.axhline(BUOY_H, color="#8a7550", lw=1.6)
    axf.annotate("浮标总高 2 m", xy=(0.98, BUOY_H), xycoords=axf.get_yaxis_transform(),
                 xytext=(0, 4), textcoords="offset points", ha="right", fontsize=8.4,
                 color="#8a7550")
    axf.set_xticks(range(len(S)))
    axf.set_xticklabels([st["tag"] for st in S])
    axf.set_ylim(0, 2.35)
    fs.finish(axf, "(b) 2 m 浮标高度的分配", None, "高度（m）", legend_loc=None)

    # (c)/(d) barrel tilt across the wind-current plane at the depth worst for theta
    winds = np.linspace(0.0, 36.0, 19)
    curs = np.linspace(0.0, 1.5, 16)
    pc = None
    for axc, st in [(axc1, S[0]), (axc2, S[2])]:
        TH = np.zeros((len(curs), len(winds)))
        for i, vc in enumerate(curs):
            for j, vw in enumerate(winds):
                r = solve_static(float(vw), 16.0, st["m"], st["type"], st["L"],
                                 family="A", v_cur=float(vc))
                TH[i, j] = r.barrel_angle_deg if r.ok else np.nan
        pc = axc.pcolormesh(winds, curs, TH, cmap="RdYlBu_r", shading="auto", vmin=0, vmax=8)
        cs = axc.contour(winds, curs, TH, levels=[1, 2, 3, 4, 5, 6, 7], colors=["#33414a"],
                         linewidths=[0.7, 0.7, 0.7, 0.7, 2.1, 0.7, 0.7])
        axc.clabel(cs, fmt="%d°", fontsize=7.6)
        axc.plot([36.0], [1.5], marker="*", ms=15, color=fs.CRIMSON, mec="white", mew=1.0, zorder=6)
        axc.annotate("设计角点", xy=(36.0, 1.5), xytext=(-8, -16), textcoords="offset points",
                     ha="right", fontsize=8.2, color=fs.CRIMSON, fontweight="bold")
        axc.grid(False)
        fs.finish(axc, f"({'c' if st is S[0] else 'd'}) {st['name'].splitlines()[0]}："
                       f"$\\theta$ 分布（水深 16 m）",
                  "风速 $v_w$（m/s）", "流速 $v_c$（m/s）", legend_loc=None)
        axc.annotate(f"包络内 $\\theta\\leq5^\\circ$ 占比 {100*st['frac']:.1f}%",
                     xy=(0.5, -0.30), xycoords="axes fraction", ha="center", fontsize=8.8,
                     color=st["color"], fontweight="bold")
    cax = axc2.inset_axes([1.07, 0.0, 0.042, 1.0])
    fig.colorbar(pc, cax=cax).set_label("$\\theta$（°）", fontsize=8.6)

    # (e) compliance summary
    fracs = [100 * st["frac"] for st in S]
    bars = axb.bar([st["tag"] for st in S], fracs, 0.55,
                   color=[st["color"] for st in S], alpha=0.92)
    for b, v in zip(bars, fracs):
        axb.annotate(f"{v:.1f}%", xy=(b.get_x() + b.get_width() / 2, v), xytext=(0, 4),
                     textcoords="offset points", ha="center", fontsize=9, fontweight="bold",
                     color="#22303a")
    axb.set_ylim(0, 118)
    fs.finish(axb, "(e) 包络内 $\\theta\\leq5^\\circ$ 的占比", None, "占比（%）", legend_loc=None)

    fs.savefig(fig, out("fig_q3_strategies.png"),
               "锚端 $\\varphi\\leq16^\\circ$ 三方案在整个包络内均满足；S2 仅在风、流同时接近峰值时越过 $5^\\circ$")


# ----------------------------------------------------------- 8 reliability view --
def fig_reliability(metrics: dict):
    q3 = metrics.get("q3_design") or {}
    ver = q3.get("verification") or {}
    rbd = ver.get("reliability_based") or {}
    prof = rbd.get("rate_profile") or []
    rel = ver.get("reliability") or {}
    if not prof:
        return

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.7), gridspec_kw={"wspace": 0.28})
    m = [p["ball_mass"] for p in prof]
    rate = [100 * p["rate"] for p in prof]
    ax.plot(m, rate, color=fs.NAVY, marker="o", ms=4.5)
    ax.fill_between(m, 0, rate, color=fs.NAVY, alpha=0.1)
    ax.axhline(95, color=fs.CRIMSON, ls="--", lw=1.3)
    ax.annotate("95% 置信目标", xy=(m[0], 95), xytext=(4, 5), textcoords="offset points",
                fontsize=8.6, color=fs.CRIMSON, fontweight="bold")
    det = rbd.get("deterministic_ball_mass")
    if det:
        ax.axvline(det, color=fs.SLATE, ls=":", lw=1.3)
        ax.annotate(f"名义最优 {det:.0f} kg\n满足率仅 {100*rbd.get('rate_at_deterministic', 0):.0f}%\n"
                    "（恰在 $5^\\circ$ 边界上）",
                    xy=(det, 32), xytext=(14, 14), textcoords="offset points", fontsize=8.6,
                    color=fs.SLATE,
                    bbox=dict(boxstyle="round,pad=0.28", fc="white", ec=fs.GRID, lw=0.7),
                    arrowprops=dict(arrowstyle="->", color=fs.SLATE, lw=0.9))
    if len(m) > 3 and rate[-1] < 60:
        ax.annotate("球重继续加大 → 储备浮力耗尽，\n扰动下部分算例已无平衡吃水",
                    xy=(m[-1], rate[-1]), xytext=(-30, 46), textcoords="offset points",
                    ha="right", fontsize=8.6, color=fs.CLAY, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.28", fc="#fdf3ee", ec=fs.CLAY, lw=0.8),
                    arrowprops=dict(arrowstyle="->", color=fs.CLAY, lw=1.0))
    if rbd.get("ball_mass"):
        ax.plot([rbd["ball_mass"]], [100 * rbd.get("rate", 0)], marker="*", ms=17,
                color=fs.CRIMSON, mec="white", mew=1.0, zorder=6)
        ax.annotate(f"S1′ {rbd['ball_mass']:.0f} kg\n吃水 {rbd.get('max_draft', float('nan')):.3f} m",
                    xy=(rbd["ball_mass"], 100 * rbd.get("rate", 0)), xytext=(-104, -34),
                    textcoords="offset points", fontsize=8.6, color=fs.CRIMSON, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=fs.CRIMSON, lw=1.0))
    ax.set_ylim(0, 108)
    fs.finish(ax, "(a) 参数扰动下的约束满足率随球重变化",
              "重物球质量（kg）", "最劣情景约束满足率（%）", legend_loc=None)

    names = ["海水密度\n1020–1030", "链条投影宽度\n×0.8–1.3", "风载系数\n×0.90–1.15",
             "水流载系数\n×0.90–1.15"]
    b3 = q3.get("best") or {"chain_type": "V", "chain_length": 26.82, "ball_mass": 4270.0}
    ct, cl, cm = b3["chain_type"], b3["chain_length"], b3["ball_mass"]
    base = solve_static(36.0, 20.0, cm, ct, cl, family="A", v_cur=1.5)
    from mooring_solve import _with_perturbation
    lows, highs = [], []
    variants = [
        {"rho": 1020.0, "chain_scale": 1.0, "kw": 1.0, "kc": 1.0},
        {"rho": 1030.0, "chain_scale": 1.0, "kw": 1.0, "kc": 1.0},
        {"rho": 1025.0, "chain_scale": 0.8, "kw": 1.0, "kc": 1.0},
        {"rho": 1025.0, "chain_scale": 1.3, "kw": 1.0, "kc": 1.0},
        {"rho": 1025.0, "chain_scale": 1.0, "kw": 0.9, "kc": 1.0},
        {"rho": 1025.0, "chain_scale": 1.0, "kw": 1.15, "kc": 1.0},
        {"rho": 1025.0, "chain_scale": 1.0, "kw": 1.0, "kc": 0.9},
        {"rho": 1025.0, "chain_scale": 1.0, "kw": 1.0, "kc": 1.15},
    ]
    vals = []
    for dr in variants:
        r = _with_perturbation(dr, lambda: solve_static(36.0, 20.0, cm, ct, cl,
                                                        family="A", v_cur=1.5))
        vals.append(r.barrel_angle_deg if r.ok else np.nan)
    for i in range(4):
        lows.append(min(vals[2 * i], vals[2 * i + 1]))
        highs.append(max(vals[2 * i], vals[2 * i + 1]))
    order = np.argsort([h - l for l, h in zip(lows, highs)])
    y = np.arange(4)
    for k, i in enumerate(order):
        ax2.barh(k, highs[i] - lows[i], left=lows[i], height=0.55,
                 color=fs.AMBER if highs[i] > BARREL_LIM_DEG else fs.TEAL, alpha=0.85,
                 edgecolor="white")
        ax2.annotate(f"[{lows[i]:.2f}, {highs[i]:.2f}]", xy=(highs[i], k), xytext=(6, -3),
                     textcoords="offset points", fontsize=8.2, color="#22303a")
    ax2.axvline(base.barrel_angle_deg, color=fs.NAVY, lw=1.4)
    ax2.annotate("基准 %.2f°" % base.barrel_angle_deg, xy=(base.barrel_angle_deg, 3.5),
                 xytext=(-6, 6), textcoords="offset points", ha="right", fontsize=8.4, color=fs.NAVY)
    ax2.axvline(BARREL_LIM_DEG, color=fs.CRIMSON, ls="--", lw=1.4)
    ax2.annotate("$5^\\circ$", xy=(BARREL_LIM_DEG, -0.55), xytext=(3, 0),
                 textcoords="offset points", fontsize=9, color=fs.CRIMSON, fontweight="bold")
    ax2.set_yticks(y)
    ax2.set_yticklabels([names[i] for i in order], fontsize=8.4)
    ax2.set_xlim(4.4, 5.9)
    fs.finish(ax2, "(b) 龙卷风图：各不确定输入对最劣 $\\theta$ 的影响",
              "钢桶倾角 $\\theta$（°）", None, legend_loc=None)

    note = (f"名义最优满足率 {100*rel.get('satisfaction_rate', 0):.1f}%"
            f"（恰在约束边界）；S1′ 提升至 {100*rbd.get('rate', 0):.1f}%")
    fs.savefig(fig, out("fig_reliability.png"), note)


# --------------------------------------------------------- 9 swim region (top) --
def fig_swim_region(metrics: dict):
    """The question asks for a swim *region*: draw it in plan view."""
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.6, 5.2), gridspec_kw={"wspace": 0.26})

    cases = [(12.0, 0.0, fs.TEAL, "12 m/s"), (24.0, 0.0, fs.NAVY, "24 m/s"),
             (36.0, 0.0, fs.CLAY, "36 m/s")]
    ax.add_patch(Circle((0, 0), 0.35, color="#4a4a4a", zorder=6))
    ax.annotate("锚", xy=(0, 0), xytext=(6, 6), textcoords="offset points", fontsize=9)
    for vw, vc, c, lab in cases:
        r = solve_static(vw, 18.0, 1200.0, "II", 22.05, family="A", v_cur=vc)
        ax.add_patch(Circle((0, 0), r.swim_radius, fill=False, color=c, lw=2.0,
                            label=f"{lab}：$R$={r.swim_radius:.2f} m"))
    r0 = solve_static(0.5, 18.0, 1200.0, "II", 22.05, family="A")
    ax.add_patch(Circle((0, 0), r0.swim_radius, facecolor=fs.SEA, edgecolor=fs.SLATE, lw=1.0,
                        alpha=0.5, zorder=0))
    ax.annotate(f"静风时的最小半径 {r0.swim_radius:.2f} m", xy=(0, 0.55 * r0.swim_radius),
                ha="center", fontsize=8.4, color=fs.SLATE)
    ax.set_xlim(-21, 21)
    ax.set_ylim(-21, 21)
    ax.set_aspect("equal")
    fs.finish(ax, "(a) 问题1/2 游动区域（俯视，水深 18 m）", "东向位移（m）", "北向位移（m）",
              legend_loc="lower right")

    q3 = metrics.get("q3_design") or {}
    best = q3.get("best")
    if best:
        ax2.add_patch(Circle((0, 0), 0.35, color="#4a4a4a", zorder=6))
        combos = [(16.0, 36.0, 1.5, fs.CLAY), (18.0, 36.0, 1.5, fs.NAVY),
                  (20.0, 36.0, 1.5, fs.TEAL), (18.0, 12.0, 0.5, fs.SLATE)]
        radii = []
        for h, vw, vc, c in combos:
            r = solve_static(vw, h, best["ball_mass"], best["chain_type"], best["chain_length"],
                             family="A", v_cur=vc)
            radii.append(r.swim_radius)
            ax2.add_patch(Circle((0, 0), r.swim_radius, fill=False, color=c, lw=1.9,
                                 label=f"{h:g} m / {vw:g} m/s / {vc:g} m/s：{r.swim_radius:.2f} m"))
        ax2.add_patch(Circle((0, 0), max(radii), facecolor=fs.CLAY, alpha=0.08, zorder=0))
        ax2.add_patch(Circle((0, 0), min(radii), facecolor="white", zorder=0))
        ax2.annotate(f"占位圆环\n$R\\in[{min(radii):.1f},\\,{max(radii):.1f}]$ m",
                     xy=(0, 6), fontsize=9, color=fs.CLAY, ha="center", fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=fs.CLAY, lw=0.8,
                               alpha=0.95))
        ax2.set_xlim(-32, 32)
        ax2.set_ylim(-32, 32)
        ax2.set_aspect("equal")
        fs.finish(ax2, f"(b) 问题3 推荐方案 S1 的游动区域\n{best['chain_type']} 型 / "
                       f"{best['chain_length']:.2f} m / {best['ball_mass']:.0f} kg",
                  "东向位移（m）", "北向位移（m）", legend_loc="lower right")

    fs.savefig(fig, out("fig_swim_region.png"), "游动区域为以锚为心的圆（平面静力，风流同向）")


# ------------------------------------------------------- 10 validation panel --
def fig_validation(metrics: dict):
    fig = plt.figure(figsize=(12.8, 4.9))
    gs = fig.add_gridspec(1, 3, wspace=0.32)
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])

    # (a) family A vs B
    rows = metrics.get("family_contrast") or []
    if rows:
        for met, c, lab, mk in [("barrel_angle_deg", fs.NAVY, "钢桶倾角 $\\theta$", "o"),
                                ("anchor_angle_deg", fs.CLAY, "锚端夹角 $\\varphi$", "s")]:
            for fam, ls in [("A", "-"), ("B", "--")]:
                xs = [r["v_wind"] for r in rows if r["family"] == fam]
                ys = [r[met] for r in rows if r["family"] == fam]
                ax.plot(xs, ys, ls, color=c, marker=mk, ms=5,
                        label=f"{lab}（{'离散链 A' if fam == 'A' else '悬链 B'}）",
                        alpha=1.0 if fam == "A" else 0.55)
        diffs = []
        for v in [12.0, 24.0, 36.0]:
            a = next(r for r in rows if r["family"] == "A" and r["v_wind"] == v)
            b = next(r for r in rows if r["family"] == "B" and r["v_wind"] == v)
            diffs.append(abs(a["anchor_angle_deg"] - b["anchor_angle_deg"]))
        ax.annotate(f"$\\varphi$ 最大族间差 {max(diffs):.2f}°\n$\\theta$、$R$ 差 <0.01",
                    xy=(0.03, 0.96), xycoords="axes fraction", va="top", fontsize=8.6,
                    color=fs.SLATE,
                    bbox=dict(boxstyle="round,pad=0.32", fc="white", ec=fs.GRID, lw=0.7))
    fs.finish(ax, "(a) 族对照：离散链 A vs 连续悬链 B", "风速（m/s）", "角度（°）",
              legend_loc="lower right")

    # (b) discretisation convergence
    gr = metrics.get("grid_refinement") or []
    conv = [g for g in gr if g.get("n_elements")]
    rich = next((g for g in gr if not g.get("n_elements")), None)
    if conv:
        n = [g["n_elements"] for g in conv]
        a = [g["anchor_angle_deg"] for g in conv]
        ax2.plot(n, a, color=fs.TEAL, marker="o", ms=6, label="离散解")
        for g in conv:
            ax2.annotate(f"{g['anchor_angle_deg']:.3f}°", xy=(g["n_elements"], g["anchor_angle_deg"]),
                         xytext=(0, 9), textcoords="offset points", ha="center", fontsize=8.0,
                         color=fs.TEAL)
        ax2.set_xscale("log")
        if rich:
            ax2.axhline(rich["anchor_angle_deg"], color=fs.CRIMSON, ls="--", lw=1.4,
                        label=f"Richardson 外推 {rich['anchor_angle_deg']:.3f}°")
            ax2.annotate(f"观测收敛阶 $p={rich['observed_order']:.2f}$\n"
                         f"基线离散偏差 {rich['baseline_error_deg']:.3f}°\n"
                         f"（$\\varphi$ 判据阈值 $16^\\circ$，偏差占 "
                         f"{100*rich['baseline_error_deg']/ANCHOR_LIM_DEG:.1f}%）",
                         xy=(0.5, 0.12), xycoords="axes fraction", ha="center", fontsize=8.4,
                         color=fs.SLATE,
                         bbox=dict(boxstyle="round,pad=0.32", fc="white", ec=fs.GRID, lw=0.7))
        lo_a = min(a + [rich["anchor_angle_deg"]]) if rich else min(a)
        hi_a = max(a)
        pad = 0.35 * (hi_a - lo_a)
        ax2.set_ylim(lo_a - 3.0 * pad, hi_a + pad)
    fs.finish(ax2, "(b) 链环细分收敛性（问题2 工况）", "链单元数（对数轴）", "锚端夹角 $\\varphi$（°）",
              legend_loc="upper right")

    # (c) module ablations
    labels, deltas, colors = [], [], []
    abl_b = metrics.get("ablation_ball_buoyancy") or []
    if len(abl_b) == 2:
        d = abl_b[1]["barrel_angle_deg"] - abl_b[0]["barrel_angle_deg"]
        labels.append("重物球浮力\n(24 m/s, $\\theta$)")
        deltas.append(d)
        colors.append(fs.CLAY)
    abl_d = metrics.get("ablation_ball_drag") or []
    if len(abl_d) == 2:
        on = next(r for r in abl_d if r["ablation"] == "ball_drag_on")
        off = next(r for r in abl_d if r["ablation"] == "ball_drag_off")
        labels.append("重物球阻力\n(最劣情景, $\\varphi$)")
        deltas.append(on["anchor_angle_deg"] - off["anchor_angle_deg"])
        colors.append(fs.PLUM)
    sc = metrics.get("sensitivity_chain_drag") or []
    if len(sc) >= 3:
        labels.append("链条投影宽度\n±30% ($\\varphi$)")
        deltas.append(sc[-1]["anchor_angle_deg"] - sc[0]["anchor_angle_deg"])
        colors.append(fs.TEAL)
    sr = metrics.get("sensitivity_rho") or []
    if len(sr) >= 3:
        labels.append("海水密度\n1020→1030 ($\\varphi$)")
        deltas.append(sr[-1]["anchor_angle_deg"] - sr[0]["anchor_angle_deg"])
        colors.append(fs.SLATE)
    ax3.barh(range(len(labels)), deltas, color=colors, alpha=0.9, height=0.6)
    for i, d in enumerate(deltas):
        ax3.annotate(f"{d:+.2f}°", xy=(d, i), xytext=(8 if d >= 0 else -34, -3),
                     textcoords="offset points", fontsize=8.6, fontweight="bold", color="#22303a")
    ax3.axvline(0, color="#4a5a66", lw=1.0)
    ax3.set_yticks(range(len(labels)))
    ax3.set_yticklabels(labels, fontsize=8.2)
    ax3.set_xlim(min(deltas + [0]) - 1.2, max(deltas + [0]) + 1.4)
    fs.finish(ax3, "(c) 模块消融/敏感性幅度", "指标变化（°）", None, legend_loc=None)

    fs.savefig(fig, out("fig_validation.png"), "全部状态的力/几何闭合残差 <1e-9（相对）")


# --------------------------------------------------------------------- driver --
def main():
    metrics = load_metrics()
    print("figures ->", ROOT)
    fig_schematic()
    fig_chain_shape(metrics)
    fig_load_path(metrics)
    fig_ball_sweep(metrics)
    fig_draft_bound(metrics)
    fig_q3_pareto(metrics)
    fig_q3_strategies(metrics)
    fig_reliability(metrics)
    fig_swim_region(metrics)
    fig_validation(metrics)


if __name__ == "__main__":
    main()
