#!/usr/bin/env python3
"""
2016 National MCM Problem A — Mooring system statics.
Families:
  A: discrete rigid-link chain + rigid pipes/barrel (baseline)
  B: continuous catenary chain + rigid pipes/barrel
  C: design search wrapping A
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------- physical constants & geometry ----------------
G = 9.8
RHO = 1025.0
RHO_STEEL = 7850.0

BUOY_D = 2.0
BUOY_H = 2.0
BUOY_M = 1000.0
BUOY_R = 1.0

PIPE_N = 4
PIPE_L = 1.0
PIPE_R = 0.025
PIPE_M = 10.0

BARREL_L = 1.0
BARREL_R = 0.15
BARREL_M = 100.0

ANCHOR_M = 600.0

CHAIN_CATALOG = {
    "I": {"pitch": 0.078, "mu": 3.2},
    "II": {"pitch": 0.105, "mu": 7.0},
    "III": {"pitch": 0.120, "mu": 12.5},
    "IV": {"pitch": 0.150, "mu": 19.5},
    "V": {"pitch": 0.180, "mu": 28.12},
}

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT_DIR, exist_ok=True)


def net_weight(mass: float, volume: float) -> float:
    """Net downward force in water (N)."""
    return mass * G - RHO * G * volume


def pipe_vol() -> float:
    return math.pi * PIPE_R**2 * PIPE_L


def barrel_vol() -> float:
    return math.pi * BARREL_R**2 * BARREL_L


def ball_vol(mass: float) -> float:
    return mass / RHO_STEEL


def chain_unit_net(mu: float) -> float:
    """Net downward force per meter of chain in water (N/m)."""
    vol_per_m = mu / RHO_STEEL
    return mu * G - RHO * G * vol_per_m


def wind_force(draft: float, v_wind: float) -> float:
    freeboard = max(BUOY_H - draft, 0.0)
    s = BUOY_D * freeboard
    return 0.625 * s * v_wind**2


def current_force_cylinder(radius: float, length: float, tilt_from_vert: float, v_cur: float) -> float:
    """Approx projected area: diameter * (L cos θ) for vertical extent facing flow; use frontal width*height."""
    # Frontal projection ≈ (2r) * (L * cosθ) when upright contribution dominates; for tilted cylinder
    # projected area normal to horizontal current ≈ 2r * L * cos(θ) + π r^2 * sin(θ) (end)
    a = 2 * radius * length * abs(math.cos(tilt_from_vert)) + math.pi * radius**2 * abs(math.sin(tilt_from_vert))
    return 374.0 * a * v_cur**2


def buoy_current_force(draft: float, v_cur: float) -> float:
    # submerged cylinder facing current
    s = BUOY_D * draft
    return 374.0 * s * v_cur**2


@dataclass
class SegmentState:
    name: str
    length: float
    angle_from_vert_deg: float
    dx: float
    dy: float  # vertical downward span


@dataclass
class SolveResult:
    ok: bool
    message: str
    draft: float
    H: float
    swim_radius: float
    anchor_angle_deg: float  # with seabed
    barrel_angle_deg: float
    pipe_angles_deg: List[float]
    grounded_length: float
    suspended_chain: float
    chain_x: List[float]
    chain_y: List[float]
    family: str
    v_wind: float
    v_cur: float
    depth: float
    ball_mass: float
    chain_type: str
    chain_length: float
    meta: Dict

    def metrics(self) -> Dict:
        return {
            "ok": self.ok,
            "draft": self.draft,
            "swim_radius": self.swim_radius,
            "anchor_angle_deg": self.anchor_angle_deg,
            "barrel_angle_deg": self.barrel_angle_deg,
            "pipe_angles_deg": self.pipe_angles_deg,
            "grounded_length": self.grounded_length,
            "H": self.H,
            "message": self.message,
        }


def rigid_angle(H: float, V_upper: float, G_net: float) -> Tuple[float, float]:
    """Return (theta_rad from vertical, V_lower)."""
    denom = V_upper - 0.5 * G_net
    if denom <= 1e-9:
        theta = math.pi / 2 - 1e-6
    else:
        theta = math.atan(H / denom)
    V_lower = V_upper - G_net
    return theta, V_lower


def propagate_rigids(H: float, V0: float, ball_mass: float):
    G_pipe = net_weight(PIPE_M, pipe_vol())
    G_barrel = net_weight(BARREL_M, barrel_vol())
    G_ball = net_weight(ball_mass, ball_vol(ball_mass))

    segs: List[SegmentState] = []
    V = V0
    angles = []
    for i in range(PIPE_N):
        th, V = rigid_angle(H, V, G_pipe)
        angles.append(math.degrees(th))
        segs.append(
            SegmentState(
                f"pipe{i+1}",
                PIPE_L,
                math.degrees(th),
                PIPE_L * math.sin(th),
                PIPE_L * math.cos(th),
            )
        )
    th_b, V = rigid_angle(H, V, G_barrel)
    segs.append(
        SegmentState("barrel", BARREL_L, math.degrees(th_b), BARREL_L * math.sin(th_b), BARREL_L * math.cos(th_b))
    )
    # ball concentrated
    V_chain_top = V - G_ball
    return segs, angles, math.degrees(th_b), V_chain_top, G_pipe, G_barrel, G_ball


def chain_discrete(H: float, V_top: float, length: float, pitch: float, mu: float):
    """Integrate discrete links top→bottom. Returns xs, ys (y downward from chain top), alpha_anchor_deg, V_end, ok."""
    w_link = chain_unit_net(mu) * pitch  # net weight per link
    n = max(int(round(length / pitch)), 1)
    # redistribute exact length
    link_l = length / n
    w_link = chain_unit_net(mu) * link_l

    xs = [0.0]
    ys = [0.0]
    V = V_top
    x = 0.0
    y = 0.0
    last_alpha = 0.0
    for _ in range(n):
        # link as rigid with weight at... use same formula: V_upper at top of link
        if V - 0.5 * w_link <= 1e-12:
            # nearly horizontal / buckling of vertical capacity
            th = math.pi / 2 - 1e-6
        else:
            th = math.atan(H / (V - 0.5 * w_link))
        # th from vertical; alpha from horizontal = pi/2 - th? Wait:
        # theta from vertical: 0=upright. Angle with seabed (horizontal) = pi/2 - theta only if...
        # angle of link above horizontal α = π/2 - th, so when th~π/2, α~0.
        alpha = math.pi / 2 - th
        last_alpha = alpha
        x += link_l * math.sin(th)
        y += link_l * math.cos(th)
        xs.append(x)
        ys.append(y)
        V = V - w_link
    return xs, ys, math.degrees(last_alpha), V, n


def chain_catenary(H: float, V_top: float, length: float, mu: float, npts: int = 400):
    """
    Uniform heavy chain: integrate ds with local angle from horizontal α=atan(V/H),
    V decreasing by w*ds. y positive downward from chain top.
    """
    w = chain_unit_net(mu)  # N/m
    npts = max(npts, 50)
    ds = length / npts
    xs = [0.0]
    ys = [0.0]
    V = V_top
    x = 0.0
    y = 0.0
    alpha_end = 0.0
    for _ in range(npts):
        V_mid = V - 0.5 * w * ds
        if H < 1e-12:
            alpha = math.pi / 2
        else:
            alpha = math.atan2(max(V_mid, 0.0), H)  # from horizontal
        x += ds * math.cos(alpha)
        y += ds * math.sin(alpha)
        V -= w * ds
        xs.append(x)
        ys.append(y)
        alpha_end = alpha
    if V <= 0:
        alpha_end = 0.0
    else:
        alpha_end = math.atan2(V, H)
    return xs, ys, math.degrees(alpha_end), V

def chain_with_grounding(H: float, V_top: float, length: float, pitch: float, mu: float, family: str):
    """
    If V_top < w*L, part of chain is grounded (趴链): suspended length Ls = V_top/w, anchor angle=0.
    If V_top >= w*L, fully suspended; anchor angle from end tension.
    """
    w = chain_unit_net(mu)
    W_all = w * length
    if V_top < 0:
        return None
    if V_top >= W_all - 1e-8:
        # fully suspended
        grounded = 0.0
        Ls = length
        if family == "A":
            xs, ys, alpha, V_end, _ = chain_discrete(H, V_top, Ls, pitch, mu)
        else:
            xs, ys, alpha, V_end = chain_catenary(H, V_top, Ls, mu)
        return xs, ys, alpha, grounded, Ls, V_end
    else:
        # grounded
        Ls = V_top / w if w > 0 else 0.0
        Ls = min(max(Ls, 0.0), length)
        grounded = length - Ls
        if Ls < 1e-6:
            return [0.0], [0.0], 0.0, grounded, 0.0, 0.0
        if family == "A":
            xs, ys, alpha, V_end, _ = chain_discrete(H, V_top, Ls, pitch, mu)
        else:
            xs, ys, alpha, V_end = chain_catenary(H, V_top, Ls, mu)
        # liftoff angle should be ~0; grounded extension adds horizontal length
        xs = list(xs)
        ys = list(ys)
        if grounded > 0 and xs:
            xs.append(xs[-1] + grounded)
            ys.append(ys[-1])
        return xs, ys, 0.0, grounded, Ls, 0.0


def vertical_rigid_span(segs: List[SegmentState]) -> float:
    return sum(s.dy for s in segs)


def horizontal_rigid_span(segs: List[SegmentState]) -> float:
    return sum(s.dx for s in segs)


def solve_static(
    v_wind: float,
    depth: float,
    ball_mass: float,
    chain_type: str,
    chain_length: float,
    family: str = "A",
    v_cur: float = 0.0,
    draft_guess: Optional[float] = None,
) -> SolveResult:
    cat = CHAIN_CATALOG[chain_type]
    mu, pitch = cat["mu"], cat["pitch"]

    G_pipe = net_weight(PIPE_M, pipe_vol())
    G_barrel = net_weight(BARREL_M, barrel_vol())
    G_ball = net_weight(ball_mass, ball_vol(ball_mass))
    G_rigids = PIPE_N * G_pipe + G_barrel + G_ball
    w = chain_unit_net(mu)

    def objective(d: float) -> Tuple[float, Optional[dict]]:
        if d <= 0.05 or d > BUOY_H - 1e-6:
            return 1e6, None
        B = RHO * G * math.pi * BUOY_R**2 * d
        Wbuoy = BUOY_M * G
        V0 = B - Wbuoy
        if V0 <= 1.0:
            return 1e6, None

        # Horizontal load: wind + current on buoy + approx current on rigids (iterate once)
        H = wind_force(d, v_wind) + buoy_current_force(d, v_cur)
        segs, pipe_angles, barrel_ang, V_chain, *_ = propagate_rigids(H, V0, ball_mass)
        # add current on pipes/barrel approximately using angles
        if v_cur > 0:
            H_extra = 0.0
            for s in segs:
                if s.name.startswith("pipe"):
                    H_extra += current_force_cylinder(PIPE_R, PIPE_L, math.radians(s.angle_from_vert_deg), v_cur)
                elif s.name == "barrel":
                    H_extra += current_force_cylinder(BARREL_R, BARREL_L, math.radians(s.angle_from_vert_deg), v_cur)
            H2 = wind_force(d, v_wind) + buoy_current_force(d, v_cur) + H_extra
            segs, pipe_angles, barrel_ang, V_chain, *_ = propagate_rigids(H2, V0, ball_mass)
            H = H2

        if V_chain < -1e-6:
            return 1e6, None

        ch = chain_with_grounding(H, V_chain, chain_length, pitch, mu, family)
        if ch is None:
            return 1e6, None
        xs, ys, alpha, grounded, Ls, V_end = ch
        chain_vert = ys[-1] if ys else 0.0
        total_vert = vertical_rigid_span(segs) + chain_vert
        target = depth - d
        err = total_vert - target
        info = dict(
            d=d,
            H=H,
            segs=segs,
            pipe_angles=pipe_angles,
            barrel_ang=barrel_ang,
            V_chain=V_chain,
            xs=xs,
            ys=ys,
            alpha=alpha,
            grounded=grounded,
            Ls=Ls,
            V_end=V_end,
            total_vert=total_vert,
            target=target,
            swim=horizontal_rigid_span(segs) + (xs[-1] if xs else 0.0),
        )
        return err, info

    # bracket draft
    ds = np.linspace(0.2, 1.95, 80)
    vals = []
    infos = []
    for d in ds:
        e, info = objective(float(d))
        vals.append(e)
        infos.append(info)
    # find sign change
    best = None
    for i in range(len(ds) - 1):
        if infos[i] is None or infos[i + 1] is None:
            continue
        if vals[i] == 1e6 or vals[i + 1] == 1e6:
            continue
        if vals[i] * vals[i + 1] <= 0:
            lo, hi = float(ds[i]), float(ds[i + 1])
            info_mid = None
            for _ in range(50):
                mid = 0.5 * (lo + hi)
                e, info_mid = objective(mid)
                if info_mid is None or e == 1e6:
                    lo = mid
                    continue
                if vals[i] < 0:
                    # not reliable; use e sign
                    pass
                if e * vals[i] <= 0:
                    hi = mid
                else:
                    lo = mid
            best = info_mid
            break
    if best is None:
        # pick minimal |err|
        idx = int(np.argmin([abs(v) if infos[j] is not None else 1e9 for j, v in enumerate(vals)]))
        best = infos[idx]
        if best is None or abs(vals[idx]) > 0.25:
            return SolveResult(
                False,
                f"no depth match, best|err|={abs(vals[idx]) if best else 'NA'}",
                float(ds[idx]),
                0,
                0,
                0,
                0,
                [],
                0,
                0,
                [],
                [],
                family,
                v_wind,
                v_cur,
                depth,
                ball_mass,
                chain_type,
                chain_length,
                {},
            )

    return SolveResult(
        ok=True,
        message="ok",
        draft=best["d"],
        H=best["H"],
        swim_radius=best["swim"],
        anchor_angle_deg=best["alpha"],
        barrel_angle_deg=best["barrel_ang"],
        pipe_angles_deg=best["pipe_angles"],
        grounded_length=best["grounded"],
        suspended_chain=best["Ls"],
        chain_x=best["xs"],
        chain_y=best["ys"],
        family=family,
        v_wind=v_wind,
        v_cur=v_cur,
        depth=depth,
        ball_mass=ball_mass,
        chain_type=chain_type,
        chain_length=chain_length,
        meta={"V_chain": best["V_chain"], "V_end": best["V_end"], "total_vert": best["total_vert"], "target": best["target"]},
    )


def result_to_public(r: SolveResult) -> Dict:
    d = {
        "ok": r.ok,
        "message": r.message,
        "family": r.family,
        "v_wind": r.v_wind,
        "v_cur": r.v_cur,
        "depth": r.depth,
        "ball_mass": r.ball_mass,
        "chain_type": r.chain_type,
        "chain_length": r.chain_length,
        "draft_m": round(r.draft, 4),
        "swim_radius_m": round(r.swim_radius, 4),
        "anchor_angle_deg": round(r.anchor_angle_deg, 4),
        "barrel_angle_deg": round(r.barrel_angle_deg, 4),
        "pipe_angles_deg": [round(a, 4) for a in r.pipe_angles_deg],
        "grounded_length_m": round(r.grounded_length, 4),
        "suspended_chain_m": round(r.suspended_chain, 4),
        "H_N": round(r.H, 2),
        "constraint_anchor_ok": r.anchor_angle_deg <= 16.0 + 1e-6,
        "constraint_barrel_ok": r.barrel_angle_deg <= 5.0 + 1e-6,
    }
    return d


def run_q1_q2():
    rows = []
    for fam in ["A", "B"]:
        for v in [12.0, 24.0, 36.0]:
            r = solve_static(v, 18.0, 1200.0, "II", 22.05, family=fam)
            rows.append(result_to_public(r))
    return rows


def search_ball_mass(
    v_wind: float,
    depth: float,
    chain_type: str,
    chain_length: float,
    family: str = "A",
    v_cur: float = 0.0,
    m_lo: float = 500.0,
    m_hi: float = 5000.0,
    barrel_lim: float = 5.0,
    anchor_lim: float = 16.0,
) -> Dict:
    """Find minimal ball mass meeting constraints (Q2 intent); report swim/draft at that point."""
    grid = np.linspace(m_lo, m_hi, 181)
    feasible = []
    all_rows = []
    for m in grid:
        r = solve_static(v_wind, depth, float(m), chain_type, chain_length, family=family, v_cur=v_cur)
        pub = result_to_public(r)
        all_rows.append(pub)
        if r.ok and r.barrel_angle_deg <= barrel_lim and r.anchor_angle_deg <= anchor_lim:
            feasible.append(pub)
    if not feasible:
        return {"found": False, "scan": all_rows[-20:]}
    # Q2: minimal mass satisfying hard constraints
    feasible.sort(key=lambda x: (x["ball_mass"], x["swim_radius_m"], x["draft_m"]))
    best = feasible[0]
    m0 = best["ball_mass"]
    refined = []
    for m in np.linspace(max(m_lo, m0 - 80), min(m_hi, m0 + 80), 81):
        r = solve_static(v_wind, depth, float(m), chain_type, chain_length, family=family, v_cur=v_cur)
        pub = result_to_public(r)
        if r.ok and r.barrel_angle_deg <= barrel_lim and r.anchor_angle_deg <= anchor_lim:
            refined.append(pub)
    if refined:
        refined.sort(key=lambda x: (x["ball_mass"], x["swim_radius_m"], x["draft_m"]))
        best = refined[0]
    # also record a swim-oriented feasible point for Pareto contrast
    by_swim = sorted(feasible, key=lambda x: (x["swim_radius_m"], x["draft_m"], x["ball_mass"]))[0]
    return {"found": True, "best": best, "best_by_swim": by_swim, "n_feasible": len(feasible)}


def design_q3(family: str = "A"):
    """
    Search chain type × length × ball mass over representative scenarios.
    Hold-out: some scenarios only for evaluation.
    """
    train = [
        {"depth": 16.0, "v_wind": 36.0, "v_cur": 1.5},
        {"depth": 18.0, "v_wind": 36.0, "v_cur": 1.5},
        {"depth": 20.0, "v_wind": 36.0, "v_cur": 1.5},
        {"depth": 18.0, "v_wind": 24.0, "v_cur": 1.0},
        {"depth": 16.0, "v_wind": 36.0, "v_cur": 0.0},
    ]
    holdout = [
        {"depth": 17.0, "v_wind": 30.0, "v_cur": 1.2},
        {"depth": 19.0, "v_wind": 36.0, "v_cur": 0.8},
        {"depth": 20.0, "v_wind": 12.0, "v_cur": 1.5},
    ]

    candidates = []
    for ctype in ["II", "III", "IV", "V"]:
        for L in [20.0, 22.05, 24.0, 26.0, 28.0, 30.0]:
            for mball in [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500]:
                candidates.append((ctype, float(L), float(mball)))

    def eval_design(ctype, L, mball, scenarios):
        rows = []
        for sc in scenarios:
            r = solve_static(sc["v_wind"], sc["depth"], mball, ctype, L, family=family, v_cur=sc["v_cur"])
            rows.append(result_to_public(r))
        ok_all = all(x["ok"] and x["constraint_anchor_ok"] and x["constraint_barrel_ok"] for x in rows)
        worst_barrel = max(x["barrel_angle_deg"] for x in rows)
        worst_anchor = max(x["anchor_angle_deg"] for x in rows)
        mean_swim = float(np.mean([x["swim_radius_m"] for x in rows if x["ok"]] or [1e9]))
        mean_draft = float(np.mean([x["draft_m"] for x in rows if x["ok"]] or [1e9]))
        return {
            "chain_type": ctype,
            "chain_length": L,
            "ball_mass": mball,
            "ok_all": ok_all,
            "worst_barrel": worst_barrel,
            "worst_anchor": worst_anchor,
            "mean_swim": mean_swim,
            "mean_draft": mean_draft,
            "rows": rows,
        }

    scored = []
    for ctype, L, mball in candidates:
        ev = eval_design(ctype, L, mball, train)
        if ev and ev["ok_all"]:
            scored.append(ev)

    if not scored:
        relaxed = []
        for ctype, L, mball in candidates:
            ev = eval_design(ctype, L, mball, train)
            if ev and all(x["ok"] and x["constraint_anchor_ok"] for x in ev["rows"]):
                relaxed.append(ev)
        relaxed.sort(key=lambda e: (e["worst_barrel"], e["mean_swim"], e["mean_draft"], e["ball_mass"]))
        best = relaxed[0] if relaxed else None
        note = "no fully feasible on train; took anchor-feasible min barrel"
    else:
        scored.sort(key=lambda e: (e["mean_swim"], e["mean_draft"], e["ball_mass"], e["worst_barrel"]))
        best = scored[0]
        note = f"fully feasible designs: {len(scored)}"

    # secondary: lightest feasible and shortest-swim top3
    top3 = []
    if scored:
        top3 = [
            {k: e[k] for k in e if k != "rows"}
            for e in sorted(scored, key=lambda e: (e["mean_swim"], e["ball_mass"]))[:3]
        ]

    holdout_eval = None
    if best:
        holdout_eval = eval_design(best["chain_type"], best["chain_length"], best["ball_mass"], holdout)
        if holdout_eval:
            holdout_eval = {k: holdout_eval[k] for k in holdout_eval}

    return {
        "note": note,
        "n_feasible_train": len(scored),
        "best": {k: best[k] for k in best if k != "rows"} if best else None,
        "best_train_rows": best["rows"] if best else None,
        "top3": top3,
        "holdout": holdout_eval,
    }


def ablation_ball_buoyancy():
    """Compare with/without ball buoyancy by temporarily scaling steel density."""
    global RHO_STEEL
    rows = []
    for label, rho_s in [("with_ball_buoyancy", 7850.0), ("no_ball_buoyancy", 1e12)]:
        old = RHO_STEEL
        RHO_STEEL = rho_s
        r = solve_static(24.0, 18.0, 1200.0, "II", 22.05, family="A")
        RHO_STEEL = old
        pub = result_to_public(r)
        pub["ablation"] = label
        rows.append(pub)
    return rows


def sensitivity_rho():
    rows = []
    global RHO
    for rho in [1020.0, 1025.0, 1030.0]:
        old = RHO
        RHO = rho
        r = solve_static(24.0, 18.0, 1200.0, "II", 22.05, family="A")
        RHO = old
        pub = result_to_public(r)
        pub["rho"] = rho
        rows.append(pub)
    return rows


def main():
    report = {}
    print("Running Q1/Q2 fixed-ball comparisons...")
    report["q1_q2_fixed_ball"] = run_q1_q2()

    print("Searching ball mass for 36 m/s ...")
    report["q2_ball_search_A"] = search_ball_mass(36.0, 18.0, "II", 22.05, family="A")
    report["q2_ball_search_B"] = search_ball_mass(36.0, 18.0, "II", 22.05, family="B")

    print("Family contrast at 12/24...")
    contrast = []
    for v in [12.0, 24.0]:
        for fam in ["A", "B"]:
            contrast.append(result_to_public(solve_static(v, 18.0, 1200.0, "II", 22.05, family=fam)))
    report["family_contrast"] = contrast

    print("Ablation / sensitivity...")
    report["ablation_ball_buoyancy"] = ablation_ball_buoyancy()
    report["sensitivity_rho"] = sensitivity_rho()

    print("Q3 design search...")
    report["q3_design"] = design_q3("A")

    # save chain shape sample
    shapes = {}
    for v in [12.0, 24.0, 36.0]:
        r = solve_static(v, 18.0, 1200.0, "II", 22.05, family="A")
        shapes[f"v{int(v)}"] = {
            "draft": r.draft,
            "chain_x": r.chain_x[:: max(1, len(r.chain_x)//50)],
            "chain_y": r.chain_y[:: max(1, len(r.chain_y)//50)],
            **result_to_public(r),
        }
    # also shape for optimized ball if found
    if report["q2_ball_search_A"].get("found"):
        m = report["q2_ball_search_A"]["best"]["ball_mass"]
        r = solve_static(36.0, 18.0, m, "II", 22.05, family="A")
        shapes["v36_optball"] = {
            "chain_x": r.chain_x[:: max(1, len(r.chain_x)//50)],
            "chain_y": r.chain_y[:: max(1, len(r.chain_y)//50)],
            **result_to_public(r),
        }
    report["shapes"] = shapes

    out = os.path.join(OUT_DIR, "metrics.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Wrote", out)

    # concise table
    print("\n=== Q1/Q2 summary (family A, ball=1200) ===")
    for row in report["q1_q2_fixed_ball"]:
        if row["family"] == "A":
            print(
                f"v={row['v_wind']}: draft={row['draft_m']}, swim={row['swim_radius_m']}, "
                f"barrel={row['barrel_angle_deg']}, anchor={row['anchor_angle_deg']}, "
                f"pipes={row['pipe_angles_deg']}, grounded={row['grounded_length_m']}"
            )
    if report["q2_ball_search_A"].get("found"):
        b = report["q2_ball_search_A"]["best"]
        print("\nQ2 opt ball A:", b)
    print("\nQ3 best:", report["q3_design"].get("best"))


if __name__ == "__main__":
    main()
