#!/usr/bin/env python3
"""
Shared plotting style for the 2016A mooring figures.

One place to register a CJK font, fix the palette, and provide the small drawing
primitives (water column, seabed, buoy, annotation callouts) that several
figures reuse, so every panel in the paper looks like it came from one document.
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle
import numpy as np

CJK_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]

# Muted, print-safe palette: deep navy for the baseline, teal / amber / clay for
# the contrasts, crimson reserved for constraint limits and the recommendation.
NAVY = "#1b3a5c"
TEAL = "#12836f"
AMBER = "#d99114"
CLAY = "#b4553a"
PLUM = "#6b4a8a"
SLATE = "#5a6b7a"
CRIMSON = "#b3243b"
SEA = "#cfe3ef"
SEA_DEEP = "#aecfe3"
SAND = "#c9b189"
GRID = "#c9d3da"

SERIES = [NAVY, TEAL, AMBER, CLAY, PLUM, SLATE]
CHAIN_COLORS = {"I": SLATE, "II": NAVY, "III": TEAL, "IV": AMBER, "V": CLAY}


def use_style() -> str | None:
    name = None
    for p in CJK_CANDIDATES:
        if os.path.exists(p):
            try:
                font_manager.fontManager.addfont(p)
                name = font_manager.FontProperties(fname=p).get_name()
                break
            except Exception:
                continue
    rc = {
        "axes.unicode_minus": False,
        "axes.edgecolor": "#4a5a66",
        "axes.linewidth": 0.9,
        "axes.labelcolor": "#22303a",
        "axes.titlesize": 11.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "grid.alpha": 0.8,
        "xtick.color": "#3a4a56",
        "ytick.color": "#3a4a56",
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": True,
        "legend.framealpha": 0.92,
        "legend.edgecolor": GRID,
        "legend.fontsize": 8.5,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.dpi": 200,
        "figure.dpi": 110,
        "lines.linewidth": 1.9,
        "lines.solid_capstyle": "round",
        "font.size": 10,
    }
    if name:
        rc["font.family"] = "sans-serif"
        rc["font.sans-serif"] = [name, "DejaVu Sans"]
    plt.rcParams.update(rc)
    return name


def finish(ax, title: str | None = None, xlabel: str | None = None, ylabel: str | None = None,
           legend_loc: str | None = "best", legend_ncol: int = 1):
    """Common axis polish: hide the top/right spines, set labels, place a legend."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if title:
        ax.set_title(title, pad=8)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if legend_loc and ax.get_legend_handles_labels()[0]:
        ax.legend(loc=legend_loc, ncol=legend_ncol)
    return ax


def draw_sea(ax, x0: float, x1: float, surface: float, bed: float = 0.0,
             label_surface: str = "海面", label_bed: str = "海床"):
    """Water column with a shaded body, a wavy surface line and a hatched bed."""
    ax.add_patch(Rectangle((x0, bed), x1 - x0, surface - bed, facecolor=SEA,
                           edgecolor="none", zorder=0, alpha=0.75))
    xs = np.linspace(x0, x1, 400)
    ax.plot(xs, surface + 0.045 * (surface - bed) / 18 * np.sin(2 * np.pi * xs / max(x1 - x0, 1e-9) * 6),
            color="#4f88ad", lw=1.4, zorder=1)
    ax.axhline(bed, color="#8a7550", lw=1.4, zorder=1)
    ax.add_patch(Rectangle((x0, bed - 0.06 * (surface - bed)), x1 - x0, 0.06 * (surface - bed),
                           facecolor=SAND, edgecolor="none", hatch="////", alpha=0.55, zorder=0))
    ax.annotate(label_surface, xy=(x0 + 0.012 * (x1 - x0), surface), xytext=(0, 4),
                textcoords="offset points", fontsize=8.5, color="#3d6d8c")
    ax.annotate(label_bed, xy=(x0 + 0.012 * (x1 - x0), bed), xytext=(0, -12),
                textcoords="offset points", fontsize=8.5, color="#7a6540")


def draw_buoy(ax, x: float, waterline: float, draft: float, height: float = 2.0,
              width: float = 2.0, color: str = NAVY, alpha: float = 0.9):
    """Buoy as a split rectangle so the draft is legible at a glance."""
    ax.add_patch(Rectangle((x - width / 2, waterline), width, height - draft,
                           facecolor="white", edgecolor=color, lw=1.6, zorder=4))
    ax.add_patch(Rectangle((x - width / 2, waterline - draft), width, draft,
                           facecolor=color, edgecolor=color, lw=1.2, alpha=alpha * 0.45, zorder=4))


def arrow(ax, xy_from, xy_to, color: str = CRIMSON, text: str | None = None,
          lw: float = 1.6, fontsize: float = 9, text_offset=(4, 4), style: str = "-|>"):
    ax.annotate("", xy=xy_to, xytext=xy_from,
                arrowprops=dict(arrowstyle=style, color=color, lw=lw, shrinkA=0, shrinkB=0))
    if text:
        ax.annotate(text, xy=xy_to, xytext=text_offset, textcoords="offset points",
                    color=color, fontsize=fontsize, fontweight="bold")


def callout(ax, xy, text: str, xytext, color: str = "#2c3b46", fontsize: float = 8.5):
    ax.annotate(text, xy=xy, xytext=xytext, textcoords="offset points", fontsize=fontsize,
                color=color, ha="left",
                bbox=dict(boxstyle="round,pad=0.32", fc="white", ec=GRID, lw=0.7, alpha=0.95),
                arrowprops=dict(arrowstyle="-", color=SLATE, lw=0.8,
                                connectionstyle="arc3,rad=0.15"))


def limit_line(ax, y: float, text: str, color: str = CRIMSON, ls: str = "--", x: float = 0.985):
    ax.axhline(y, color=color, ls=ls, lw=1.2, zorder=2)
    ax.annotate(text, xy=(x, y), xycoords=ax.get_yaxis_transform(), xytext=(0, 3),
                textcoords="offset points", ha="right", color=color, fontsize=8.5,
                fontweight="bold")


def panel_tag(ax, tag: str):
    ax.annotate(tag, xy=(0, 1), xycoords="axes fraction", xytext=(-30, 12),
                textcoords="offset points", fontsize=12, fontweight="bold", color="#22303a")


def savefig(fig, path: str, note: str | None = None):
    if note:
        fig.text(0.995, 0.005, note, ha="right", va="bottom", fontsize=7.2, color=SLATE)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", os.path.basename(path))
