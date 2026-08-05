#!/usr/bin/env python3
"""Cross-check supplements inspired by branch cursor/mooring-system-2016a-47ef."""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from mooring_solve import (
    BUOY_H,
    BUOY_M,
    BUOY_R,
    CHAIN_CATALOG,
    G,
    RHO,
    ball_vol,
    buoy_current_force,
    chain_unit_net,
    net_weight,
    propagate_rigids,
    result_to_public,
    solve_static,
    wind_force,
)

OUT = os.path.join(os.path.dirname(__file__), "..", "results")


def solve_M0_straight_chain(v_wind, depth, ball_mass, chain_type, chain_length, v_cur=0.0):
    """Cheap baseline: rigid pipes/barrel + single straight suspended chain (no catenary)."""
    mu = CHAIN_CATALOG[chain_type]["mu"]
    w = chain_unit_net(mu)
    best = None
    for d in np.linspace(0.2, 1.95, 120):
        B = RHO * G * math.pi * BUOY_R**2 * d
        V0 = B - BUOY_M * G
        if V0 <= 1:
            continue
        H = wind_force(float(d), v_wind) + buoy_current_force(float(d), v_cur)
        segs, pipes, barrel, Vc, *_ = propagate_rigids(H, V0, ball_mass)
        if Vc < 0:
            continue
        if Vc < w * chain_length:
            Ls = Vc / w
            grounded = chain_length - Ls
            denom = Vc - 0.5 * w * Ls
            th = math.atan(H / max(denom, 1e-9))
            chain_vert = Ls * math.cos(th)
            chain_horiz = Ls * math.sin(th) + grounded
            alpha = 0.0
        else:
            grounded = 0.0
            Ls = chain_length
            denom = Vc - 0.5 * w * Ls
            th = math.atan(H / max(denom, 1e-9))
            chain_vert = Ls * math.cos(th)
            chain_horiz = Ls * math.sin(th)
            alpha = math.degrees(math.pi / 2 - th)
        rigid_v = sum(s.dy for s in segs)
        rigid_h = sum(s.dx for s in segs)
        err = abs(rigid_v + chain_vert - (depth - d))
        info = {
            "draft_m": float(d),
            "swim_radius_m": rigid_h + chain_horiz,
            "barrel_angle_deg": barrel,
            "pipe_angles_deg": pipes,
            "anchor_angle_deg": alpha,
            "grounded_length_m": grounded,
            "depth_err_m": err,
            "H_N": H,
        }
        if best is None or err < best["depth_err_m"]:
            best = info
    return best


def full_grid_eval(ctype, L, mball):
    worst = {"barrel": 0.0, "anchor": 0.0, "swim": 0.0, "draft": 0.0}
    fails = []
    n_ok = 0
    rows = []
    for d in [16.0, 18.0, 20.0]:
        for w in [12.0, 24.0, 36.0]:
            for c in [0.0, 0.75, 1.5]:
                r = result_to_public(solve_static(w, d, mball, ctype, L, family="A", v_cur=c))
                ok = r["ok"] and r["constraint_barrel_ok"] and r["constraint_anchor_ok"]
                if ok:
                    n_ok += 1
                else:
                    fails.append(
                        {
                            "depth": d,
                            "wind": w,
                            "current": c,
                            "barrel": r["barrel_angle_deg"],
                            "anchor": r["anchor_angle_deg"],
                            "ok_solve": r["ok"],
                        }
                    )
                if r["ok"]:
                    worst["barrel"] = max(worst["barrel"], r["barrel_angle_deg"])
                    worst["anchor"] = max(worst["anchor"], r["anchor_angle_deg"])
                    worst["swim"] = max(worst["swim"], r["swim_radius_m"])
                    worst["draft"] = max(worst["draft"], r["draft_m"])
                rows.append({"depth": d, "wind": w, "current": c, **r, "pass": ok})
    return {
        "chain_type": ctype,
        "chain_length": L,
        "ball_mass": mball,
        "n_ok": n_ok,
        "n_total": 27,
        "feasible_all": n_ok == 27,
        "worst": {k: round(v, 4) for k, v in worst.items()},
        "fails": fails,
        "rows": rows,
    }


def main():
    report = {"note": "Supplements after reviewing cursor/mooring-system-2016a-47ef"}

    # M0 vs A vs B
    contrast = []
    for v in [12.0, 24.0, 36.0]:
        m0 = solve_M0_straight_chain(v, 18.0, 1200.0, "II", 22.05)
        a = result_to_public(solve_static(v, 18.0, 1200.0, "II", 22.05, family="A"))
        b = result_to_public(solve_static(v, 18.0, 1200.0, "II", 22.05, family="B"))
        contrast.append(
            {
                "v_wind": v,
                "M0_straight": {
                    k: (round(m0[k], 4) if not isinstance(m0[k], list) else [round(x, 4) for x in m0[k]])
                    for k in m0
                },
                "A_discrete": a,
                "B_catenary": b,
                "swim_A_minus_M0_m": round(a["swim_radius_m"] - m0["swim_radius_m"], 4),
            }
        )
    report["M0_vs_A_vs_B"] = contrast

    # Q2 binding: their 1973 vs our 2238 on OUR physics
    q2 = []
    for m in [1973.0, 2100.0, 2238.0, 2300.0]:
        r = result_to_public(solve_static(36.0, 18.0, m, "II", 22.05, family="A"))
        q2.append(r)
    report["q2_mass_crosscheck_on_our_model"] = q2

    # Dense 27-scenario Pareto candidates
    cands = [
        ("ours_primary", "V", 22.05, 5000.0),
        ("ours_lighter_ball", "V", 22.05, 4500.0),
        ("alt_longer_chain_47ef_style", "V", 26.0, 4500.0),
        ("alt_V_26_5000", "V", 26.0, 5000.0),
        ("alt_V_24_4500", "V", 24.0, 4500.0),
    ]
    grids = []
    for name, ct, L, m in cands:
        ev = full_grid_eval(ct, L, m)
        # drop bulky rows from summary file top; keep in separate if needed
        summary = {k: ev[k] for k in ev if k != "rows"}
        summary["label"] = name
        grids.append(summary)
    report["q3_full27_candidates"] = grids

    # Mechanism attribution vs other branch
    report["branch_47ef_diff_notes"] = {
        "their_main_model": "tension propagation θ=arctan(H/V) + analytic catenary cosh; draft by |V_end|~0 after ball, chain weight not in buoy vertical balance",
        "our_main_model": "rigid-rod moment θ=arctan(H/(V-G/2)) + discrete chain; draft closes geometry; chain+ball buoyancy included",
        "their_q2_ball_kg": 1973,
        "our_q2_ball_kg": 2238,
        "why_higher_here": [
            "include ball & chain buoyancy → less net hanging weight per kg ball → need heavier ball for same restoring",
            "include full chain weight in vertical/grounding logic",
            "moment form uses V-G/2 (slightly different θ)",
        ],
        "their_suspicious_36ms_swim": "they report R≈11.9m at 36m/s < R at 24m/s; our R increases with wind (physically expected for fixed chain when fully suspended)",
        "q3_tradeoff": "V/22.05/5000 minimizes worst swim (~19.4m) on our model; V/26/4500 feasible with more grounded chain but worst swim ~23.3m",
    }

    path = os.path.join(OUT, "cross_branch_supplement.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("wrote", path)
    for g in grids:
        print(g["label"], "feasible", g["feasible_all"], "worst", g["worst"])


if __name__ == "__main__":
    main()
