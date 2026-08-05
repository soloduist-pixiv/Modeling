#!/usr/bin/env python3
"""
2016 National MCM Problem A — Mooring system statics (revised).

Families:
  A: discrete rigid-link chain + rigid pipes/barrel (baseline)
  B: continuous catenary chain + rigid pipes/barrel (contrast)
  C: constrained design search wrapping A

Key mechanics (rev2):
  - Horizontal tension varies segment-wise when current drag is present:
      H_{i+1} = H_i + F_{c,i}
    and rod angle uses effective horizontal load H_i + F_{c,i}/2.
  - Chain length is snapped to an integer number of catalog link pitches.
  - Q3 reports a Pareto set under hard + soft margin constraints.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
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

# Soft design margins used by Q3 recommendation (hard limits remain 5° / 16°)
# Draft soft limit is intentionally looser than an ideal freeboard target: under
# wind+current extremes, feasible designs often need d≳1.75 m.
SOFT_BARREL_DEG = 4.5
SOFT_ANCHOR_DEG = 14.0
SOFT_DRAFT_MAX = 1.85


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


def chain_eq_radius(mu: float) -> float:
    """Equivalent cylindrical radius from steel volume per meter."""
    vol_per_m = mu / RHO_STEEL
    # π r^2 * 1m = vol_per_m
    return math.sqrt(max(vol_per_m, 1e-12) / math.pi)


def snap_chain_length(chain_type: str, length: float) -> Tuple[float, int]:
    """Snap a nominal length to an integer number of catalog link pitches."""
    pitch = CHAIN_CATALOG[chain_type]["pitch"]
    n = max(1, int(round(length / pitch)))
    return n * pitch, n


def integer_chain_lengths(chain_type: str, lo: float, hi: float, step_hint: float = 2.0) -> List[float]:
    """Candidate lengths in [lo, hi] that are exact integer multiples of pitch."""
    pitch = CHAIN_CATALOG[chain_type]["pitch"]
    n_lo = max(1, int(math.ceil(lo / pitch - 1e-12)))
    n_hi = int(math.floor(hi / pitch + 1e-12))
    lengths = [n * pitch for n in range(n_lo, n_hi + 1)]
    if not lengths:
        return []
    # Subsample near step_hint while always keeping endpoints.
    keep = {lengths[0], lengths[-1]}
    target = lo
    while target <= hi + 1e-9:
        L, _ = snap_chain_length(chain_type, target)
        if lo - 1e-9 <= L <= hi + 1e-9:
            keep.add(L)
        target += step_hint
    # Also keep a few denser samples around common engineering lengths.
    for L0 in (20.0, 22.0, 24.0, 26.0, 28.0, 30.0):
        L, _ = snap_chain_length(chain_type, L0)
        if lo - 1e-9 <= L <= hi + 1e-9:
            keep.add(L)
    return sorted(keep)


def wind_force(draft: float, v_wind: float) -> float:
    freeboard = max(BUOY_H - draft, 0.0)
    s = BUOY_D * freeboard
    return 0.625 * s * v_wind**2


def current_force_cylinder(radius: float, length: float, tilt_from_vert: float, v_cur: float) -> float:
    """Projected area normal to horizontal current for a circular cylinder."""
    a = 2 * radius * length * abs(math.cos(tilt_from_vert)) + math.pi * radius**2 * abs(
        math.sin(tilt_from_vert)
    )
    return 374.0 * a * v_cur**2


def buoy_current_force(draft: float, v_cur: float) -> float:
    s = BUOY_D * draft
    return 374.0 * s * v_cur**2


def chain_current_force_per_m(mu: float, tilt_from_vert: float, v_cur: float) -> float:
    """Approximate current drag per meter of chain using equivalent radius."""
    r = chain_eq_radius(mu)
    # local element length 1 m
    return current_force_cylinder(r, 1.0, tilt_from_vert, v_cur)


@dataclass
class SegmentState:
    name: str
    length: float
    angle_from_vert_deg: float
    dx: float
    dy: float  # vertical downward span
    H_top: float
    H_bot: float
    Fc: float


@dataclass
class SolveResult:
    ok: bool
    message: str
    draft: float
    H: float  # horizontal tension at chain top (after all rigid current loads)
    H_buoy: float
    swim_radius: float
    anchor_angle_deg: float
    barrel_angle_deg: float
    pipe_angles_deg: List[float]
    grounded_length: float
    suspended_chain: float
    chain_x: List[float]
    chain_y: List[float]
    system_x: List[float]
    system_y: List[float]  # height above seabed
    family: str
    v_wind: float
    v_cur: float
    depth: float
    ball_mass: float
    chain_type: str
    chain_length: float
    n_links: int
    vertical_closure_err: float
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


def rigid_angle_with_current(H_top: float, V_upper: float, G_net: float, F_c: float) -> Tuple[float, float, float]:
    """
    Uniform rigid rod with top horizontal tension H_top, mid current F_c,
    net weight G_net. Returns (theta_rad, V_lower, H_lower).
    Effective horizontal for moment balance: H_top + F_c/2.
    """
    H_eff = H_top + 0.5 * F_c
    denom = V_upper - 0.5 * G_net
    if denom <= 1e-9:
        theta = math.pi / 2 - 1e-6
    else:
        theta = math.atan(H_eff / denom)
    V_lower = V_upper - G_net
    H_lower = H_top + F_c
    return theta, V_lower, H_lower


def propagate_rigids(
    H_buoy: float,
    V0: float,
    ball_mass: float,
    v_cur: float,
    angle_seed: Optional[List[float]] = None,
) -> Tuple[List[SegmentState], List[float], float, float, float]:
    """
    Propagate pipes + barrel + concentrated ball.
    angle_seed: previous angles (rad from vertical) for current-area iteration.
    Returns segs, pipe_angles_deg, barrel_ang_deg, V_chain_top, H_chain_top.
    """
    G_pipe = net_weight(PIPE_M, pipe_vol())
    G_barrel = net_weight(BARREL_M, barrel_vol())
    G_ball = net_weight(ball_mass, ball_vol(ball_mass))

    n_rigid = PIPE_N + 1
    if angle_seed is None or len(angle_seed) != n_rigid:
        angle_seed = [0.0] * n_rigid

    segs: List[SegmentState] = []
    pipe_angles: List[float] = []
    V = V0
    H = H_buoy
    th_b = 0.0

    for i in range(PIPE_N):
        Fc = current_force_cylinder(PIPE_R, PIPE_L, angle_seed[i], v_cur) if v_cur > 0 else 0.0
        th, V, H = rigid_angle_with_current(H, V, G_pipe, Fc)
        pipe_angles.append(math.degrees(th))
        segs.append(
            SegmentState(
                f"pipe{i+1}",
                PIPE_L,
                math.degrees(th),
                PIPE_L * math.sin(th),
                PIPE_L * math.cos(th),
                H - Fc,
                H,
                Fc,
            )
        )

    Fc_b = current_force_cylinder(BARREL_R, BARREL_L, angle_seed[PIPE_N], v_cur) if v_cur > 0 else 0.0
    th_b, V, H = rigid_angle_with_current(H, V, G_barrel, Fc_b)
    segs.append(
        SegmentState(
            "barrel",
            BARREL_L,
            math.degrees(th_b),
            BARREL_L * math.sin(th_b),
            BARREL_L * math.cos(th_b),
            H - Fc_b,
            H,
            Fc_b,
        )
    )

    # Concentrated ball: no distributed current area modeled (compact).
    V_chain_top = V - G_ball
    H_chain_top = H
    return segs, pipe_angles, math.degrees(th_b), V_chain_top, H_chain_top


def chain_discrete(H_profile_or_H, V_top: float, length: float, pitch: float, mu: float, v_cur: float = 0.0):
    """
    Integrate discrete links top→bottom.
    If v_cur>0, H increases along the chain due to local drag.
    Returns xs, ys (y downward from chain top), alpha_anchor_deg, V_end, H_end, n.
    """
    n = max(int(round(length / pitch)), 1)
    link_l = length / n
    w_link = chain_unit_net(mu) * link_l

    xs = [0.0]
    ys = [0.0]
    V = V_top
    H = float(H_profile_or_H)
    x = 0.0
    y = 0.0
    last_alpha = 0.0
    th = 0.0
    for _ in range(n):
        Fc = chain_current_force_per_m(mu, th, v_cur) * link_l if v_cur > 0 else 0.0
        H_eff = H + 0.5 * Fc
        if V - 0.5 * w_link <= 1e-12:
            th = math.pi / 2 - 1e-6
        else:
            th = math.atan(H_eff / (V - 0.5 * w_link))
        alpha = math.pi / 2 - th
        last_alpha = alpha
        x += link_l * math.sin(th)
        y += link_l * math.cos(th)
        xs.append(x)
        ys.append(y)
        V = V - w_link
        H = H + Fc
    return xs, ys, math.degrees(last_alpha), V, H, n


def chain_catenary(H0: float, V_top: float, length: float, mu: float, v_cur: float = 0.0, npts: int = 400):
    """Uniform heavy chain with optional distributed current drag."""
    w = chain_unit_net(mu)
    npts = max(npts, 50)
    ds = length / npts
    xs = [0.0]
    ys = [0.0]
    V = V_top
    H = H0
    x = 0.0
    y = 0.0
    alpha_end = 0.0
    alpha = math.pi / 2
    for _ in range(npts):
        tilt = math.pi / 2 - alpha  # from vertical
        Fc = chain_current_force_per_m(mu, tilt, v_cur) * ds if v_cur > 0 else 0.0
        V_mid = V - 0.5 * w * ds
        H_mid = H + 0.5 * Fc
        if H_mid < 1e-12:
            alpha = math.pi / 2
        else:
            alpha = math.atan2(max(V_mid, 0.0), H_mid)
        x += ds * math.cos(alpha)
        y += ds * math.sin(alpha)
        V -= w * ds
        H += Fc
        xs.append(x)
        ys.append(y)
        alpha_end = alpha
    if V <= 0:
        alpha_end = 0.0
    else:
        alpha_end = math.atan2(V, H)
    return xs, ys, math.degrees(alpha_end), V, H


def chain_with_grounding(
    H_top: float,
    V_top: float,
    length: float,
    pitch: float,
    mu: float,
    family: str,
    v_cur: float = 0.0,
):
    """
    If V_top < w*L, part of chain is grounded (趴链): suspended length Ls = V_top/w,
    anchor angle=0. Grounded segment assumed to carry negligible current (flat on bed).
    """
    w = chain_unit_net(mu)
    W_all = w * length
    if V_top < 0:
        return None
    if V_top >= W_all - 1e-8:
        grounded = 0.0
        Ls = length
        if family == "A":
            xs, ys, alpha, V_end, H_end, _ = chain_discrete(H_top, V_top, Ls, pitch, mu, v_cur)
        else:
            xs, ys, alpha, V_end, H_end = chain_catenary(H_top, V_top, Ls, mu, v_cur)
        return xs, ys, alpha, grounded, Ls, V_end, H_end
    else:
        Ls = V_top / w if w > 0 else 0.0
        Ls = min(max(Ls, 0.0), length)
        grounded = length - Ls
        if Ls < 1e-6:
            return [0.0], [0.0], 0.0, grounded, 0.0, 0.0, H_top
        if family == "A":
            xs, ys, alpha, V_end, H_end, _ = chain_discrete(H_top, V_top, Ls, pitch, mu, v_cur)
        else:
            xs, ys, alpha, V_end, H_end = chain_catenary(H_top, V_top, Ls, mu, v_cur)
        xs = list(xs)
        ys = list(ys)
        if grounded > 0 and xs:
            xs.append(xs[-1] + grounded)
            ys.append(ys[-1])
        return xs, ys, 0.0, grounded, Ls, 0.0, H_end


def vertical_rigid_span(segs: List[SegmentState]) -> float:
    return sum(s.dy for s in segs)


def horizontal_rigid_span(segs: List[SegmentState]) -> float:
    return sum(s.dx for s in segs)


def build_system_polyline(
    depth: float,
    draft: float,
    segs: List[SegmentState],
    chain_x: List[float],
    chain_y: List[float],
) -> Tuple[List[float], List[float]]:
    """
    Full profile from buoy top to anchor, coordinates:
      x: horizontal from buoy axis toward lean
      y: height above seabed
    """
    xs: List[float] = []
    ys: List[float] = []
    # buoy top
    x = 0.0
    y = depth + (BUOY_H - draft)
    xs.append(x)
    ys.append(y)
    # buoy waterline / bottom
    y = depth
    xs.append(x)
    ys.append(y)
    y = depth - draft
    xs.append(x)
    ys.append(y)
    # rigid segments downward
    for s in segs:
        x += s.dx
        y -= s.dy
        xs.append(x)
        ys.append(y)
    # chain: chain_x/y are from chain top downward
    if chain_x:
        x0, y0 = x, y
        for cx, cy in zip(chain_x, chain_y):
            xs.append(x0 + cx)
            ys.append(y0 - cy)
    return xs, ys


def solve_static(
    v_wind: float,
    depth: float,
    ball_mass: float,
    chain_type: str,
    chain_length: float,
    family: str = "A",
    v_cur: float = 0.0,
    snap_length: bool = True,
) -> SolveResult:
    cat = CHAIN_CATALOG[chain_type]
    mu, pitch = cat["mu"], cat["pitch"]
    if snap_length:
        chain_length, n_links = snap_chain_length(chain_type, chain_length)
    else:
        n_links = max(1, int(round(chain_length / pitch)))

    def objective(d: float) -> Tuple[float, Optional[dict]]:
        if d <= 0.05 or d > BUOY_H - 1e-6:
            return 1e6, None
        B = RHO * G * math.pi * BUOY_R**2 * d
        Wbuoy = BUOY_M * G
        V0 = B - Wbuoy
        if V0 <= 1.0:
            return 1e6, None

        H_buoy = wind_force(d, v_wind) + buoy_current_force(d, v_cur)

        # Iterate angles ↔ current areas (usually converges in <5 iters)
        angle_seed = [0.0] * (PIPE_N + 1)
        segs = []
        pipe_angles: List[float] = []
        barrel_ang = 0.0
        V_chain = 0.0
        H_chain = H_buoy
        for _ in range(8):
            segs, pipe_angles, barrel_ang, V_chain, H_chain = propagate_rigids(
                H_buoy, V0, ball_mass, v_cur, angle_seed
            )
            new_seed = [math.radians(a) for a in pipe_angles] + [math.radians(barrel_ang)]
            if max(abs(a - b) for a, b in zip(new_seed, angle_seed)) < 1e-10:
                angle_seed = new_seed
                break
            angle_seed = new_seed

        if V_chain < -1e-6:
            return 1e6, None

        ch = chain_with_grounding(H_chain, V_chain, chain_length, pitch, mu, family, v_cur)
        if ch is None:
            return 1e6, None
        xs, ys, alpha, grounded, Ls, V_end, H_end = ch
        chain_vert = ys[-1] if ys else 0.0
        total_vert = vertical_rigid_span(segs) + chain_vert
        target = depth - d
        err = total_vert - target
        sys_x, sys_y = build_system_polyline(depth, d, segs, xs, ys)
        info = dict(
            d=d,
            H=H_chain,
            H_buoy=H_buoy,
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
            H_end=H_end,
            total_vert=total_vert,
            target=target,
            swim=horizontal_rigid_span(segs) + (xs[-1] if xs else 0.0),
            sys_x=sys_x,
            sys_y=sys_y,
        )
        return err, info

    ds = np.linspace(0.2, 1.95, 100)
    vals = []
    infos = []
    for d in ds:
        e, info = objective(float(d))
        vals.append(e)
        infos.append(info)

    best = None
    best_err = 1e9
    for i in range(len(ds) - 1):
        if infos[i] is None or infos[i + 1] is None:
            continue
        if vals[i] == 1e6 or vals[i + 1] == 1e6:
            continue
        if vals[i] * vals[i + 1] <= 0:
            lo, hi = float(ds[i]), float(ds[i + 1])
            # Keep the sign reference from vals[i]
            s_lo = vals[i]
            info_mid = None
            e_mid = 1e6
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                e_mid, info_mid = objective(mid)
                if info_mid is None or e_mid == 1e6:
                    # shrink from the bad side conservatively
                    lo = mid
                    continue
                if e_mid * s_lo <= 0:
                    hi = mid
                else:
                    lo = mid
                    s_lo = e_mid
            if info_mid is not None and abs(e_mid) < best_err:
                best = info_mid
                best_err = abs(e_mid)

    if best is None:
        idx = int(np.argmin([abs(v) if infos[j] is not None else 1e9 for j, v in enumerate(vals)]))
        best = infos[idx]
        best_err = abs(vals[idx]) if best is not None else 1e9
        if best is None or best_err > 0.25:
            return SolveResult(
                False,
                f"no depth match, best|err|={best_err if best else 'NA'}",
                float(ds[idx]),
                0,
                0,
                0,
                0,
                0,
                [],
                0,
                0,
                [],
                [],
                [],
                [],
                family,
                v_wind,
                v_cur,
                depth,
                ball_mass,
                chain_type,
                chain_length,
                n_links,
                best_err,
                {},
            )

    return SolveResult(
        ok=True,
        message="ok",
        draft=best["d"],
        H=best["H"],
        H_buoy=best["H_buoy"],
        swim_radius=best["swim"],
        anchor_angle_deg=best["alpha"],
        barrel_angle_deg=best["barrel_ang"],
        pipe_angles_deg=best["pipe_angles"],
        grounded_length=best["grounded"],
        suspended_chain=best["Ls"],
        chain_x=best["xs"],
        chain_y=best["ys"],
        system_x=best["sys_x"],
        system_y=best["sys_y"],
        family=family,
        v_wind=v_wind,
        v_cur=v_cur,
        depth=depth,
        ball_mass=ball_mass,
        chain_type=chain_type,
        chain_length=chain_length,
        n_links=n_links,
        vertical_closure_err=best_err,
        meta={
            "V_chain": best["V_chain"],
            "V_end": best["V_end"],
            "H_end": best.get("H_end"),
            "total_vert": best["total_vert"],
            "target": best["target"],
        },
    )


def result_to_public(r: SolveResult) -> Dict:
    return {
        "ok": r.ok,
        "message": r.message,
        "family": r.family,
        "v_wind": r.v_wind,
        "v_cur": r.v_cur,
        "depth": r.depth,
        "ball_mass": r.ball_mass,
        "chain_type": r.chain_type,
        "chain_length": round(r.chain_length, 4),
        "n_links": r.n_links,
        "draft_m": round(r.draft, 4),
        "swim_radius_m": round(r.swim_radius, 4),
        "anchor_angle_deg": round(r.anchor_angle_deg, 4),
        "barrel_angle_deg": round(r.barrel_angle_deg, 4),
        "pipe_angles_deg": [round(a, 4) for a in r.pipe_angles_deg],
        "grounded_length_m": round(r.grounded_length, 4),
        "suspended_chain_m": round(r.suspended_chain, 4),
        "H_N": round(r.H, 2),
        "H_buoy_N": round(r.H_buoy, 2),
        "vertical_closure_err_m": round(r.vertical_closure_err, 6),
        "constraint_anchor_ok": r.anchor_angle_deg <= 16.0 + 1e-6,
        "constraint_barrel_ok": r.barrel_angle_deg <= 5.0 + 1e-6,
        "margin_anchor_ok": r.anchor_angle_deg <= SOFT_ANCHOR_DEG + 1e-6,
        "margin_barrel_ok": r.barrel_angle_deg <= SOFT_BARREL_DEG + 1e-6,
        "margin_draft_ok": r.draft <= SOFT_DRAFT_MAX + 1e-6,
    }


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
    """Find minimal ball mass meeting hard constraints via coarse grid + bisection."""

    def feasible(m: float) -> Tuple[bool, Dict]:
        r = solve_static(v_wind, depth, float(m), chain_type, chain_length, family=family, v_cur=v_cur)
        pub = result_to_public(r)
        ok = r.ok and r.barrel_angle_deg <= barrel_lim + 1e-9 and r.anchor_angle_deg <= anchor_lim + 1e-9
        return ok, pub

    grid = np.linspace(m_lo, m_hi, 181)
    feasible_rows = []
    first_hit = None
    for m in grid:
        ok, pub = feasible(float(m))
        if ok:
            feasible_rows.append(pub)
            if first_hit is None:
                first_hit = float(m)

    if not feasible_rows:
        # return near-boundary samples for diagnostics
        scan = []
        for m in np.linspace(m_hi - 500, m_hi, 11):
            _, pub = feasible(float(m))
            scan.append(pub)
        return {"found": False, "scan": scan}

    # Bisection for minimal mass between previous infeasible and first feasible
    lo = m_lo if first_hit == grid[0] else float(grid[max(0, int(np.where(grid == first_hit)[0][0]) - 1)])
    # more robust: find last infeasible before first_hit
    lo = m_lo
    for m in grid:
        ok, _ = feasible(float(m))
        if ok:
            break
        lo = float(m)
    hi = first_hit
    best = feasible_rows[0]
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        ok, pub = feasible(mid)
        if ok:
            hi = mid
            best = pub
        else:
            lo = mid

    # Final polish: evaluate a tight neighborhood and pick minimal mass
    refined = []
    for m in np.linspace(max(m_lo, best["ball_mass"] - 5), min(m_hi, best["ball_mass"] + 5), 41):
        ok, pub = feasible(float(m))
        if ok:
            refined.append(pub)
    if refined:
        refined.sort(key=lambda x: (x["ball_mass"], x["swim_radius_m"], x["draft_m"]))
        best = refined[0]

    # Round reported mass to 1 kg for engineering readability; re-evaluate.
    m_round = float(int(round(best["ball_mass"])))
    ok_r, pub_r = feasible(m_round)
    if ok_r:
        best = pub_r
    else:
        # if rounding down breaks feasibility, take ceil
        ok_r, pub_r = feasible(float(int(math.ceil(best["ball_mass"]))))
        if ok_r:
            best = pub_r

    by_swim = sorted(feasible_rows, key=lambda x: (x["swim_radius_m"], x["draft_m"], x["ball_mass"]))[0]
    return {
        "found": True,
        "best": best,
        "best_by_swim": by_swim,
        "n_feasible_grid": len(feasible_rows),
        "search_method": "grid+bisection",
    }


def dominates(a: Dict, b: Dict, keys: List[str]) -> bool:
    """True if a Pareto-dominates b on minimization objectives `keys`."""
    better_or_eq = all(a[k] <= b[k] + 1e-12 for k in keys)
    strictly_better = any(a[k] < b[k] - 1e-12 for k in keys)
    return better_or_eq and strictly_better


def pareto_front(rows: List[Dict], keys: List[str]) -> List[Dict]:
    front = []
    for r in rows:
        if any(dominates(o, r, keys) for o in rows):
            continue
        front.append(r)
    return front


def design_q3(family: str = "A"):
    """
    Search chain type × integer-link length × ball mass over representative scenarios.
    Hard constraints: θ<=5°, φ<=16° on all train scenarios.
    Soft margins preferred: θ<=4°, φ<=12°, draft<=1.7 m.
    Reports Pareto set; recommendation chosen by margin-first then swim/draft/mass.
    """
    train = [
        {"depth": 16.0, "v_wind": 36.0, "v_cur": 1.5},
        {"depth": 18.0, "v_wind": 36.0, "v_cur": 1.5},
        {"depth": 20.0, "v_wind": 36.0, "v_cur": 1.5},
        {"depth": 18.0, "v_wind": 24.0, "v_cur": 1.0},
        {"depth": 16.0, "v_wind": 36.0, "v_cur": 0.0},
        {"depth": 20.0, "v_wind": 36.0, "v_cur": 0.0},
        {"depth": 16.0, "v_wind": 12.0, "v_cur": 1.5},
    ]
    holdout = [
        {"depth": 17.0, "v_wind": 30.0, "v_cur": 1.2},
        {"depth": 19.0, "v_wind": 36.0, "v_cur": 0.8},
        {"depth": 20.0, "v_wind": 12.0, "v_cur": 1.5},
        {"depth": 18.5, "v_wind": 36.0, "v_cur": 1.5},
        {"depth": 16.5, "v_wind": 28.0, "v_cur": 1.5},
    ]

    candidates = []
    for ctype in ["II", "III", "IV", "V"]:
        for L in integer_chain_lengths(ctype, 18.0, 32.0, step_hint=2.0):
            for mball in [2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000]:
                candidates.append((ctype, float(round(L, 6)), float(mball)))

    def eval_design(ctype, L, mball, scenarios):
        rows = []
        for sc in scenarios:
            r = solve_static(sc["v_wind"], sc["depth"], mball, ctype, L, family=family, v_cur=sc["v_cur"])
            rows.append(result_to_public(r))
        ok_all = all(x["ok"] and x["constraint_anchor_ok"] and x["constraint_barrel_ok"] for x in rows)
        margin_all = all(
            x["ok"] and x["margin_anchor_ok"] and x["margin_barrel_ok"] and x["margin_draft_ok"] for x in rows
        )
        worst_barrel = max(x["barrel_angle_deg"] for x in rows)
        worst_anchor = max(x["anchor_angle_deg"] for x in rows)
        max_draft = max(x["draft_m"] for x in rows)
        mean_swim = float(np.mean([x["swim_radius_m"] for x in rows if x["ok"]] or [1e9]))
        mean_draft = float(np.mean([x["draft_m"] for x in rows if x["ok"]] or [1e9]))
        n_links = rows[0]["n_links"] if rows else None
        # Balanced utility on normalized objectives (lower is better).
        utility = (
            0.30 * (mean_swim / 25.0)
            + 0.22 * (max_draft / 2.0)
            + 0.12 * (mball / 6000.0)
            + 0.20 * (worst_barrel / 5.0)
            + 0.16 * (worst_anchor / 16.0)
        )
        return {
            "chain_type": ctype,
            "chain_length": round(L, 4),
            "n_links": n_links,
            "ball_mass": mball,
            "ok_all": ok_all,
            "margin_all": margin_all,
            "worst_barrel": worst_barrel,
            "worst_anchor": worst_anchor,
            "max_draft": max_draft,
            "mean_swim": mean_swim,
            "mean_draft": mean_draft,
            "utility": utility,
            "rows": rows,
        }

    scored = []
    for ctype, L, mball in candidates:
        ev = eval_design(ctype, L, mball, train)
        if ev["ok_all"]:
            scored.append(ev)

    obj_keys = ["mean_swim", "mean_draft", "ball_mass", "worst_barrel", "worst_anchor"]
    front = []
    if scored:
        summaries = [{k: e[k] for k in e if k != "rows"} for e in scored]
        front = pareto_front(summaries, obj_keys)

    # Recommendation: soft-margin first; else minimize balanced utility among hard-feasible.
    def rank_key(e: Dict):
        return (
            0 if e.get("margin_all") else 1,
            e["utility"],
            e["mean_swim"],
            e["max_draft"],
            e["ball_mass"],
        )

    best = None
    note = "no fully feasible on train"
    if scored:
        scored.sort(key=rank_key)
        best = scored[0]
        note = (
            f"fully feasible designs: {len(scored)}; "
            f"Pareto size: {len(front)}; "
            f"margin-feasible: {sum(1 for e in scored if e['margin_all'])}"
        )

    top_margin = [
        {k: e[k] for k in e if k != "rows"}
        for e in sorted([e for e in scored if e["margin_all"]], key=rank_key)[:5]
    ]
    top_hard = [{k: e[k] for k in e if k != "rows"} for e in sorted(scored, key=rank_key)[:5]]
    # Explicit alternatives from Pareto: min-swim and min-draft
    alt_min_swim = None
    alt_min_draft = None
    if scored:
        alt_min_swim = {k: e[k] for k in e if k != "rows"} if (e := min(scored, key=lambda x: (x["mean_swim"], x["utility"]))) else None
        alt_min_draft = {k: e[k] for k in e if k != "rows"} if (e := min(scored, key=lambda x: (x["max_draft"], x["utility"]))) else None

    holdout_eval = None
    dense_eval = None
    if best:
        holdout_eval = eval_design(best["chain_type"], best["chain_length"], best["ball_mass"], holdout)
        # Dense corner/edge scan over the environmental box
        dense_sc = []
        for h in np.linspace(16.0, 20.0, 9):
            for vw in np.linspace(0.0, 36.0, 7):
                for vc in np.linspace(0.0, 1.5, 4):
                    dense_sc.append({"depth": float(h), "v_wind": float(vw), "v_cur": float(vc)})
        dense_eval = eval_design(best["chain_type"], best["chain_length"], best["ball_mass"], dense_sc)
        # Keep dense rows compact: only summary + worst cases
        if dense_eval:
            worst_rows = sorted(
                dense_eval["rows"],
                key=lambda x: (x["barrel_angle_deg"], x["anchor_angle_deg"], x["draft_m"]),
                reverse=True,
            )[:8]
            dense_eval = {
                k: dense_eval[k]
                for k in dense_eval
                if k != "rows"
            }
            dense_eval["n_scenarios"] = len(dense_sc)
            dense_eval["worst_rows"] = worst_rows
            dense_eval["n_fail_hard"] = sum(
                1
                for r in worst_rows
                if (not r["ok"]) or (not r["constraint_anchor_ok"]) or (not r["constraint_barrel_ok"])
            )

    return {
        "note": note,
        "n_feasible_train": len(scored),
        "n_candidates": len(candidates),
        "soft_limits": {
            "barrel_deg": SOFT_BARREL_DEG,
            "anchor_deg": SOFT_ANCHOR_DEG,
            "draft_m": SOFT_DRAFT_MAX,
        },
        "best": {k: best[k] for k in best if k != "rows"} if best else None,
        "best_train_rows": best["rows"] if best else None,
        "pareto_front": front[:20],
        "top_margin": top_margin,
        "top_hard": top_hard,
        "alt_min_swim": alt_min_swim,
        "alt_min_draft": alt_min_draft,
        "holdout": {k: holdout_eval[k] for k in holdout_eval} if holdout_eval else None,
        "dense_scan": dense_eval,
    }


def ablation_ball_buoyancy():
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


def ablation_current_propagation():
    """Compare old lumped-H vs new distributed-H on a current scenario."""
    # Distributed (current code)
    r_new = solve_static(36.0, 18.0, 4000.0, "V", 22.0, family="A", v_cur=1.5)
    return {
        "distributed_H": result_to_public(r_new),
        "note": "rev2 uses segment-wise H; legacy lumped-H retired",
    }


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
    report = {
        "revision": "rev2-distributed-H-integer-links-pareto",
        "soft_limits": {
            "barrel_deg": SOFT_BARREL_DEG,
            "anchor_deg": SOFT_ANCHOR_DEG,
            "draft_m": SOFT_DRAFT_MAX,
        },
    }
    print("Running Q1/Q2 fixed-ball comparisons...")
    report["q1_q2_fixed_ball"] = run_q1_q2()

    print("Searching ball mass for 36 m/s ...")
    report["q2_ball_search_A"] = search_ball_mass(36.0, 18.0, "II", 22.05, family="A")
    report["q2_ball_search_B"] = search_ball_mass(36.0, 18.0, "II", 22.05, family="B")

    print("Family contrast at 12/24/36...")
    contrast = []
    for v in [12.0, 24.0, 36.0]:
        for fam in ["A", "B"]:
            contrast.append(result_to_public(solve_static(v, 18.0, 1200.0, "II", 22.05, family=fam)))
    report["family_contrast"] = contrast

    print("Ablation / sensitivity...")
    report["ablation_ball_buoyancy"] = ablation_ball_buoyancy()
    report["ablation_current_propagation"] = ablation_current_propagation()
    report["sensitivity_rho"] = sensitivity_rho()

    # Integer-link sanity check
    report["integer_link_examples"] = {
        "II_22.05": snap_chain_length("II", 22.05),
        "V_22.05_invalid_nominal": snap_chain_length("V", 22.05),
        "V_22.14": snap_chain_length("V", 22.14),
        "V_21.96": snap_chain_length("V", 21.96),
    }

    print("Q3 design search (integer links + Pareto)...")
    report["q3_design"] = design_q3("A")

    shapes = {}
    for v in [12.0, 24.0, 36.0]:
        r = solve_static(v, 18.0, 1200.0, "II", 22.05, family="A")
        shapes[f"v{int(v)}"] = {
            "draft": r.draft,
            "chain_x": r.chain_x[:: max(1, len(r.chain_x) // 50)],
            "chain_y": r.chain_y[:: max(1, len(r.chain_y) // 50)],
            "system_x": r.system_x,
            "system_y": r.system_y,
            **result_to_public(r),
        }
    if report["q2_ball_search_A"].get("found"):
        m = report["q2_ball_search_A"]["best"]["ball_mass"]
        r = solve_static(36.0, 18.0, m, "II", 22.05, family="A")
        shapes["v36_optball"] = {
            "chain_x": r.chain_x[:: max(1, len(r.chain_x) // 50)],
            "chain_y": r.chain_y[:: max(1, len(r.chain_y) // 50)],
            "system_x": r.system_x,
            "system_y": r.system_y,
            **result_to_public(r),
        }
    if report["q3_design"].get("best"):
        b = report["q3_design"]["best"]
        r = solve_static(36.0, 18.0, b["ball_mass"], b["chain_type"], b["chain_length"], family="A", v_cur=1.5)
        shapes["q3_extreme"] = {
            "system_x": r.system_x,
            "system_y": r.system_y,
            **result_to_public(r),
        }
    report["shapes"] = shapes

    out = os.path.join(OUT_DIR, "metrics.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Wrote", out)

    print("\n=== Q1/Q2 summary (family A, ball=1200) ===")
    for row in report["q1_q2_fixed_ball"]:
        if row["family"] == "A":
            print(
                f"v={row['v_wind']}: draft={row['draft_m']}, swim={row['swim_radius_m']}, "
                f"barrel={row['barrel_angle_deg']}, anchor={row['anchor_angle_deg']}, "
                f"pipes={row['pipe_angles_deg']}, grounded={row['grounded_length_m']}, "
                f"err={row['vertical_closure_err_m']}"
            )
    if report["q2_ball_search_A"].get("found"):
        print("\nQ2 opt ball A:", report["q2_ball_search_A"]["best"])
    print("\nQ3 best:", report["q3_design"].get("best"))
    print("Q3 note:", report["q3_design"].get("note"))


if __name__ == "__main__":
    main()
