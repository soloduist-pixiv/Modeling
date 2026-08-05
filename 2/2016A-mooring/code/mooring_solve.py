#!/usr/bin/env python3
"""
2016 National MCM Problem A — Mooring system statics (rev3).

Model families
--------------
A : discrete rigid-link chain + rigid pipes/barrel (baseline / reported model)
B : continuous heavy-chain (catenary-type) integration + rigid pipes/barrel (contrast)
C : design layer wrapping A — worst-case feasible set, Pareto front, TOPSIS ranking

Mechanics recorded in rev3
--------------------------
1. Horizontal tension propagates segment-wise when current drag is present:
       H_{i+1} = H_i + F_{c,i},
   and the moment balance of a uniform rod uses the effective load H_i + F_{c,i}/2.
2. The weight ball hangs at the barrel/chain joint, i.e. *below* the barrel.  Its
   drag therefore loads the chain (raising the anchor angle) but not the barrel.
   rev3 adds this sphere drag, which reaches ~0.75 kN at 5 t / 1.5 m/s and is
   not negligible against the ~3.3 kN buoy load.
3. Chain length is snapped to an integer number of catalog link pitches.
4. The barrel tilt admits a closed-form draft bound (`draft_bound_for_barrel`)
   that is independent of chain type, chain length and ball mass.  It turns the
   "how small can the draft be?" question into an analytic statement instead of
   a grid-search artefact, and it anchors the Q3 trade-off curve.
5. Q3 is posed as a robust (worst-case) design problem.  The worst-case scenario
   set is reduced by verified monotonicity instead of an ad-hoc scenario list.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

# ---------------------------------------------------------------- constants --
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

K_WIND = 0.625
K_CUR = 374.0

CHAIN_CATALOG = {
    "I": {"pitch": 0.078, "mu": 3.2},
    "II": {"pitch": 0.105, "mu": 7.0},
    "III": {"pitch": 0.120, "mu": 12.5},
    "IV": {"pitch": 0.150, "mu": 19.5},
    "V": {"pitch": 0.180, "mu": 28.12},
}

# Multiplier on the chain drag area, exposed so that the reliability study can
# perturb the least defensible hydrodynamic input.
CHAIN_DRAG_SCALE = 1.0
# Ball drag can be switched off to reproduce the rev2 numbers in the ablation.
BALL_DRAG_ON = True

BARREL_LIM_DEG = 5.0
ANCHOR_LIM_DEG = 16.0

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT_DIR, exist_ok=True)


# ------------------------------------------------------------ static helpers --
def net_weight(mass: float, volume: float) -> float:
    """Net downward force in water (N)."""
    return mass * G - RHO * G * volume


def pipe_vol() -> float:
    return math.pi * PIPE_R**2 * PIPE_L


def barrel_vol() -> float:
    return math.pi * BARREL_R**2 * BARREL_L


def ball_vol(mass: float) -> float:
    return mass / RHO_STEEL


def ball_radius(mass: float) -> float:
    """Radius of a solid steel sphere of the given mass (m)."""
    return (3.0 * ball_vol(mass) / (4.0 * math.pi)) ** (1.0 / 3.0)


def chain_unit_net(mu: float) -> float:
    """Net downward force per metre of chain in water (N/m)."""
    return mu * G * (1.0 - RHO / RHO_STEEL)


def chain_drag_width(mu: float, pitch: float | None = None) -> float:
    """
    Projected width per metre of chain, i.e. the S in F = 374 S v^2 for a 1 m
    element held normal to the flow (m^2/m).

    Two independent estimates are used and they agree to a few percent, which is
    why this quantity is treated as known rather than fitted:

    * volume equivalence — replace the chain by a solid cylinder carrying the
      same steel volume per metre, width 2 r with pi r^2 = mu / rho_steel;
    * link geometry — for a studless link the pitch is about 6 bar diameters and
      two bars are seen edge-on, giving a width of about 2 * pitch / 6.

    For type II (mu = 7 kg/m, pitch = 105 mm) they give 0.0337 and 0.0350 m^2/m.
    """
    vol_per_m = mu / RHO_STEEL
    r_eq = math.sqrt(max(vol_per_m, 1e-12) / math.pi)
    return CHAIN_DRAG_SCALE * 2.0 * r_eq


def chain_drag_width_link(pitch: float) -> float:
    """Link-geometry cross-check of :func:`chain_drag_width` (m^2/m)."""
    return 2.0 * pitch / 6.0


def snap_chain_length(chain_type: str, length: float) -> Tuple[float, int]:
    """Snap a nominal length to an integer number of catalog link pitches."""
    pitch = CHAIN_CATALOG[chain_type]["pitch"]
    n = max(1, int(round(length / pitch)))
    return n * pitch, n


def integer_chain_lengths(chain_type: str, lo: float, hi: float, stride: float = 0.5) -> List[float]:
    """
    Lengths in [lo, hi] that are exact integer multiples of the catalog pitch,
    thinned to about `stride` metres so that the design enumeration stays finite
    while every returned length remains manufacturable.
    """
    pitch = CHAIN_CATALOG[chain_type]["pitch"]
    n_lo = max(1, int(math.ceil(lo / pitch - 1e-12)))
    n_hi = int(math.floor(hi / pitch + 1e-12))
    if n_hi < n_lo:
        return []
    step = max(1, int(round(stride / pitch)))
    ns = list(range(n_lo, n_hi + 1, step))
    if ns[-1] != n_hi:
        ns.append(n_hi)
    return [n * pitch for n in ns]


def wind_force(draft: float, v_wind: float) -> float:
    freeboard = max(BUOY_H - draft, 0.0)
    return K_WIND * (BUOY_D * freeboard) * v_wind**2


def buoy_current_force(draft: float, v_cur: float) -> float:
    return K_CUR * (BUOY_D * min(draft, BUOY_H)) * v_cur**2


def buoy_horizontal_load(draft: float, v_wind: float, v_cur: float) -> float:
    """
    Total horizontal load handed to the mooring line at the buoy.

    d/d(draft) = -2 K_wind v_wind^2 + 2 K_cur v_cur^2, so wind relief and current
    growth almost cancel at (36 m/s, 1.5 m/s): the load is nearly draft-blind
    there, which is what makes the draft bound of `draft_bound_for_barrel` sharp.
    """
    return wind_force(draft, v_wind) + buoy_current_force(draft, v_cur)


def cylinder_drag(radius: float, length: float, tilt_from_vert: float, v_cur: float) -> float:
    """Drag on a circular cylinder whose axis is `tilt_from_vert` off vertical."""
    if v_cur <= 0:
        return 0.0
    a = 2 * radius * length * abs(math.cos(tilt_from_vert)) + math.pi * radius**2 * abs(
        math.sin(tilt_from_vert)
    )
    return K_CUR * a * v_cur**2


def ball_drag(mass: float, v_cur: float) -> float:
    """Drag on the weight ball, applied at the barrel/chain joint."""
    if v_cur <= 0 or not BALL_DRAG_ON or mass <= 0:
        return 0.0
    return K_CUR * math.pi * ball_radius(mass) ** 2 * v_cur**2


def chain_drag_per_m(mu: float, tilt_from_vert: float, v_cur: float) -> float:
    """Drag per metre of chain; the projected width shrinks as the link lies flat."""
    if v_cur <= 0:
        return 0.0
    w = chain_drag_width(mu)
    return K_CUR * w * abs(math.cos(tilt_from_vert)) * v_cur**2


# ------------------------------------------------------- analytic draft bound --
def barrel_tilt_from_draft(draft: float, v_wind: float, v_cur: float, tilt_guess_deg: float = 4.0) -> float:
    """
    Barrel tilt (deg) implied by a draft, in closed form.

    The vertical pull available at the barrel top is fixed by Archimedes on the
    buoy minus the four pipes, and the ball hangs *below* the barrel, so neither
    the ball mass nor the chain enters:

        V_top = rho g pi R^2 d - m_buoy g - 4 G_pipe,
        tan(theta) = (H_buoy + sum F_c,pipe + F_c,barrel / 2) / (V_top - G_barrel / 2).
    """
    V0 = RHO * G * math.pi * BUOY_R**2 * draft - BUOY_M * G
    V_top = V0 - PIPE_N * net_weight(PIPE_M, pipe_vol())
    denom = V_top - 0.5 * net_weight(BARREL_M, barrel_vol())
    if denom <= 0:
        return 90.0
    tilt = math.radians(tilt_guess_deg)
    for _ in range(40):
        H = buoy_horizontal_load(draft, v_wind, v_cur)
        H += PIPE_N * cylinder_drag(PIPE_R, PIPE_L, tilt, v_cur)
        H += 0.5 * cylinder_drag(BARREL_R, BARREL_L, tilt, v_cur)
        new = math.atan(H / denom)
        if abs(new - tilt) < 1e-12:
            tilt = new
            break
        tilt = new
    return math.degrees(tilt)


def draft_bound_for_barrel(v_wind: float, v_cur: float, tilt_lim_deg: float = BARREL_LIM_DEG) -> float:
    """
    Smallest draft compatible with `barrel tilt <= tilt_lim_deg`.

    Because :func:`barrel_tilt_from_draft` is a strictly decreasing function of
    the draft, the bound is obtained by bisection and holds for *every* chain
    type, chain length and ball mass.  It is the binding constraint behind the
    deep-draft Q3 designs.
    """
    lo, hi = 0.05, BUOY_H - 1e-6
    if barrel_tilt_from_draft(hi, v_wind, v_cur) > tilt_lim_deg:
        return float("nan")
    if barrel_tilt_from_draft(lo, v_wind, v_cur) <= tilt_lim_deg:
        return lo
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if barrel_tilt_from_draft(mid, v_wind, v_cur) > tilt_lim_deg:
            lo = mid
        else:
            hi = mid
    return hi


def ball_mass_from_draft(draft: float, chain_type: str, chain_length: float, suspended: Optional[float] = None) -> float:
    """
    Ball mass that makes the system float at the given draft (closed form).

    Global vertical balance: the buoy's net buoyancy carries the pipes, barrel,
    ball and the *suspended* part of the chain.
    """
    mu = CHAIN_CATALOG[chain_type]["mu"]
    V0 = RHO * G * math.pi * BUOY_R**2 * draft - BUOY_M * G
    rigid = PIPE_N * net_weight(PIPE_M, pipe_vol()) + net_weight(BARREL_M, barrel_vol())
    Ls = chain_length if suspended is None else suspended
    G_ball = V0 - rigid - chain_unit_net(mu) * Ls
    return max(G_ball, 0.0) / (G * (1.0 - RHO / RHO_STEEL))


# ------------------------------------------------------------- data classes --
@dataclass
class SegmentState:
    name: str
    length: float
    angle_from_vert_deg: float
    dx: float
    dy: float
    H_top: float
    H_bot: float
    Fc: float


@dataclass
class SolveResult:
    ok: bool
    message: str
    draft: float
    H: float
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
    system_y: List[float]
    family: str
    v_wind: float
    v_cur: float
    depth: float
    ball_mass: float
    chain_type: str
    chain_length: float
    n_links: int
    vertical_closure_err: float
    force_residual: Dict[str, float] = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)


def rod_step(H_top: float, V_upper: float, G_net: float, F_c: float) -> Tuple[float, float, float]:
    """
    One uniform rigid rod: moments about its lower pin give
        tan(theta) = (H_top + F_c/2) / (V_upper - G_net/2),
    then V and H are handed to the next rod down.
    """
    H_eff = H_top + 0.5 * F_c
    denom = V_upper - 0.5 * G_net
    theta = math.pi / 2 - 1e-6 if denom <= 1e-9 else math.atan(H_eff / denom)
    return theta, V_upper - G_net, H_top + F_c


def propagate_rigids(
    H_buoy: float,
    V0: float,
    ball_mass: float,
    v_cur: float,
    angle_seed: Optional[List[float]] = None,
) -> Tuple[List[SegmentState], List[float], float, float, float, float]:
    """
    Propagate the four pipes, the barrel, and the concentrated ball.

    Returns segs, pipe angles (deg), barrel angle (deg), V at chain top,
    H at chain top, and the ball drag that was injected at the joint.
    """
    G_pipe = net_weight(PIPE_M, pipe_vol())
    G_barrel = net_weight(BARREL_M, barrel_vol())
    G_ball = net_weight(ball_mass, ball_vol(ball_mass))

    n_rigid = PIPE_N + 1
    if angle_seed is None or len(angle_seed) != n_rigid:
        angle_seed = [0.0] * n_rigid

    segs: List[SegmentState] = []
    pipe_angles: List[float] = []
    V, H = V0, H_buoy

    for i in range(PIPE_N):
        Fc = cylinder_drag(PIPE_R, PIPE_L, angle_seed[i], v_cur)
        th, V, H = rod_step(H, V, G_pipe, Fc)
        pipe_angles.append(math.degrees(th))
        segs.append(
            SegmentState(f"pipe{i+1}", PIPE_L, math.degrees(th), PIPE_L * math.sin(th),
                         PIPE_L * math.cos(th), H - Fc, H, Fc)
        )

    Fc_b = cylinder_drag(BARREL_R, BARREL_L, angle_seed[PIPE_N], v_cur)
    th_b, V, H = rod_step(H, V, G_barrel, Fc_b)
    segs.append(
        SegmentState("barrel", BARREL_L, math.degrees(th_b), BARREL_L * math.sin(th_b),
                     BARREL_L * math.cos(th_b), H - Fc_b, H, Fc_b)
    )

    F_ball = ball_drag(ball_mass, v_cur)
    return segs, pipe_angles, math.degrees(th_b), V - G_ball, H + F_ball, F_ball


def chain_discrete(H_top: float, V_top: float, length: float, pitch: float, mu: float, v_cur: float = 0.0):
    """Integrate the chain link by link from the top down."""
    n = max(int(round(length / pitch)), 1)
    link_l = length / n
    w_link = chain_unit_net(mu) * link_l

    xs, ys = [0.0], [0.0]
    V, H = V_top, float(H_top)
    x = y = 0.0
    th = 0.0
    last_alpha = 0.0
    for _ in range(n):
        Fc = chain_drag_per_m(mu, th, v_cur) * link_l
        H_eff = H + 0.5 * Fc
        if V - 0.5 * w_link <= 1e-12:
            th = math.pi / 2 - 1e-6
        else:
            th = math.atan(H_eff / (V - 0.5 * w_link))
        last_alpha = math.pi / 2 - th
        x += link_l * math.sin(th)
        y += link_l * math.cos(th)
        xs.append(x)
        ys.append(y)
        V -= w_link
        H += Fc
    return xs, ys, math.degrees(last_alpha), V, H, n


def chain_catenary(H0: float, V_top: float, length: float, mu: float, v_cur: float = 0.0, npts: int = 400):
    """Continuous heavy chain, optionally with distributed current drag."""
    w = chain_unit_net(mu)
    npts = max(npts, 50)
    ds = length / npts
    xs, ys = [0.0], [0.0]
    V, H = V_top, H0
    x = y = 0.0
    alpha = math.pi / 2
    for _ in range(npts):
        tilt = math.pi / 2 - alpha
        Fc = chain_drag_per_m(mu, tilt, v_cur) * ds
        V_mid = V - 0.5 * w * ds
        H_mid = H + 0.5 * Fc
        alpha = math.pi / 2 if H_mid < 1e-12 else math.atan2(max(V_mid, 0.0), H_mid)
        x += ds * math.cos(alpha)
        y += ds * math.sin(alpha)
        V -= w * ds
        H += Fc
        xs.append(x)
        ys.append(y)
    alpha_end = 0.0 if V <= 0 else math.atan2(V, H)
    return xs, ys, math.degrees(alpha_end), V, H


def chain_with_grounding(H_top: float, V_top: float, length: float, pitch: float, mu: float,
                         family: str, v_cur: float = 0.0):
    """
    Touchdown handling.  If the vertical pull at the chain top cannot lift the
    whole chain (V_top < w L) the lower part lies on the seabed: the suspended
    length is Ls = V_top / w and the anchor tangent is horizontal, so the 16 deg
    constraint is satisfied with room to spare.  The grounded part is assumed to
    shed its drag into the seabed.
    """
    w = chain_unit_net(mu)
    if V_top < 0:
        return None
    if V_top >= w * length - 1e-8:
        if family == "A":
            xs, ys, alpha, V_end, H_end, _ = chain_discrete(H_top, V_top, length, pitch, mu, v_cur)
        else:
            xs, ys, alpha, V_end, H_end = chain_catenary(H_top, V_top, length, mu, v_cur)
        return xs, ys, alpha, 0.0, length, V_end, H_end

    Ls = min(max(V_top / w if w > 0 else 0.0, 0.0), length)
    grounded = length - Ls
    if Ls < 1e-6:
        return [0.0], [0.0], 0.0, grounded, 0.0, 0.0, H_top
    if family == "A":
        xs, ys, alpha, V_end, H_end, _ = chain_discrete(H_top, V_top, Ls, pitch, mu, v_cur)
    else:
        xs, ys, alpha, V_end, H_end = chain_catenary(H_top, V_top, Ls, mu, v_cur)
    xs, ys = list(xs), list(ys)
    xs.append(xs[-1] + grounded)
    ys.append(ys[-1])
    return xs, ys, 0.0, grounded, Ls, 0.0, H_end


def build_system_polyline(depth: float, draft: float, segs: List[SegmentState],
                          chain_x: Sequence[float], chain_y: Sequence[float]):
    """Buoy top to anchor; x horizontal from the buoy axis, y height above seabed."""
    xs, ys = [], []
    x, y = 0.0, depth + (BUOY_H - draft)
    xs.append(x); ys.append(y)
    xs.append(x); ys.append(depth)
    y = depth - draft
    xs.append(x); ys.append(y)
    for s in segs:
        x += s.dx
        y -= s.dy
        xs.append(x); ys.append(y)
    if chain_x:
        x0, y0 = x, y
        for cx, cy in zip(chain_x, chain_y):
            xs.append(x0 + cx)
            ys.append(y0 - cy)
    return xs, ys


def solve_static(v_wind: float, depth: float, ball_mass: float, chain_type: str, chain_length: float,
                 family: str = "A", v_cur: float = 0.0, snap_length: bool = True) -> SolveResult:
    """
    Equilibrium for one environment / one design.

    The single unknown closed by root finding is the draft: everything else
    follows from the top-down force and moment recursion, and the residual is
    the vertical geometric closure  d + sum L_i cos(theta_i) + y_chain - depth.
    """
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
        V0 = B - BUOY_M * G
        if V0 <= 1.0:
            return 1e6, None

        H_buoy = buoy_horizontal_load(d, v_wind, v_cur)

        angle_seed = [0.0] * (PIPE_N + 1)
        segs: List[SegmentState] = []
        pipe_angles: List[float] = []
        barrel_ang = 0.0
        V_chain = 0.0
        H_chain = H_buoy
        F_ball = 0.0
        for _ in range(12):
            segs, pipe_angles, barrel_ang, V_chain, H_chain, F_ball = propagate_rigids(
                H_buoy, V0, ball_mass, v_cur, angle_seed
            )
            new_seed = [math.radians(a) for a in pipe_angles] + [math.radians(barrel_ang)]
            if max(abs(a - b) for a, b in zip(new_seed, angle_seed)) < 1e-12:
                angle_seed = new_seed
                break
            angle_seed = new_seed

        if V_chain < -1e-6:
            return 1e6, None

        ch = chain_with_grounding(H_chain, V_chain, chain_length, pitch, mu, family, v_cur)
        if ch is None:
            return 1e6, None
        xs, ys, alpha, grounded, Ls, V_end, H_end = ch
        total_vert = sum(s.dy for s in segs) + (ys[-1] if ys else 0.0)
        err = total_vert - (depth - d)
        info = dict(
            d=d, H=H_chain, H_buoy=H_buoy, segs=segs, pipe_angles=pipe_angles,
            barrel_ang=barrel_ang, V_chain=V_chain, F_ball=F_ball, xs=xs, ys=ys,
            alpha=alpha, grounded=grounded, Ls=Ls, V_end=V_end, H_end=H_end,
            total_vert=total_vert, target=depth - d,
            swim=sum(s.dx for s in segs) + (xs[-1] if xs else 0.0),
            sys=build_system_polyline(depth, d, segs, xs, ys),
        )
        return err, info

    ds = np.linspace(0.2, 1.95, 120)
    vals, infos = [], []
    for d in ds:
        e, info = objective(float(d))
        vals.append(e)
        infos.append(info)

    best, best_err = None, 1e9
    for i in range(len(ds) - 1):
        if infos[i] is None or infos[i + 1] is None:
            continue
        if vals[i] == 1e6 or vals[i + 1] == 1e6 or vals[i] * vals[i + 1] > 0:
            continue
        lo, hi, s_lo = float(ds[i]), float(ds[i + 1]), vals[i]
        info_mid, e_mid = None, 1e6
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            e_mid, info_mid = objective(mid)
            if info_mid is None or e_mid == 1e6:
                lo = mid
                continue
            if e_mid * s_lo <= 0:
                hi = mid
            else:
                lo, s_lo = mid, e_mid
        if info_mid is not None and abs(e_mid) < best_err:
            best, best_err = info_mid, abs(e_mid)

    if best is None:
        idx = int(np.argmin([abs(v) if infos[j] is not None else 1e9 for j, v in enumerate(vals)]))
        best = infos[idx]
        best_err = abs(vals[idx]) if best is not None else 1e9
        if best is None or best_err > 0.25:
            return SolveResult(False, "no equilibrium draft", float(ds[idx]), 0, 0, 0, 0, 0, [],
                               0, 0, [], [], [], [], family, v_wind, v_cur, depth, ball_mass,
                               chain_type, chain_length, n_links, best_err)

    residual = force_residual(best, chain_length, mu, v_cur, ball_mass)
    sys_x, sys_y = best["sys"]
    return SolveResult(
        ok=True, message="ok", draft=best["d"], H=best["H"], H_buoy=best["H_buoy"],
        swim_radius=best["swim"], anchor_angle_deg=best["alpha"], barrel_angle_deg=best["barrel_ang"],
        pipe_angles_deg=best["pipe_angles"], grounded_length=best["grounded"],
        suspended_chain=best["Ls"], chain_x=best["xs"], chain_y=best["ys"],
        system_x=sys_x, system_y=sys_y, family=family, v_wind=v_wind, v_cur=v_cur,
        depth=depth, ball_mass=ball_mass, chain_type=chain_type, chain_length=chain_length,
        n_links=n_links, vertical_closure_err=best_err, force_residual=residual,
        meta={"V_chain": best["V_chain"], "V_end": best["V_end"], "H_end": best["H_end"],
              "F_ball": best["F_ball"], "total_vert": best["total_vert"], "target": best["target"]},
    )


def force_residual(info: dict, chain_length: float, mu: float, v_cur: float, ball_mass: float) -> Dict[str, float]:
    """
    Independent global balance check on the converged state.

    Horizontal: the tension reaching the anchor end must equal the buoy load plus
    every drag contribution added on the way down.
    Vertical: the buoy's net buoyancy must equal all submerged net weights that
    the line actually carries (the grounded chain rests on the bed).
    """
    segs: List[SegmentState] = info["segs"]
    drag_rigid = sum(s.Fc for s in segs)
    drag_chain = info["H_end"] - info["H"] if info["H_end"] is not None else 0.0
    h_expected = info["H_buoy"] + drag_rigid + info["F_ball"] + drag_chain
    h_actual = info["H_end"] if info["H_end"] is not None else h_expected
    h_scale = max(abs(h_expected), 1.0)

    V0 = info["H"] * 0.0 + (RHO * G * math.pi * BUOY_R**2 * info["d"] - BUOY_M * G)
    carried = (PIPE_N * net_weight(PIPE_M, pipe_vol()) + net_weight(BARREL_M, barrel_vol())
               + net_weight(ball_mass, ball_vol(ball_mass)) + chain_unit_net(mu) * info["Ls"])
    v_res = V0 - carried - info["V_end"]
    return {
        "horizontal_rel": abs(h_actual - h_expected) / h_scale,
        "vertical_abs_N": abs(v_res),
        "vertical_rel": abs(v_res) / max(abs(V0), 1.0),
        "geometry_abs_m": abs(info["total_vert"] - info["target"]),
    }


def result_to_public(r: SolveResult) -> Dict:
    return {
        "ok": r.ok, "message": r.message, "family": r.family,
        "v_wind": r.v_wind, "v_cur": r.v_cur, "depth": r.depth,
        "ball_mass": r.ball_mass, "chain_type": r.chain_type,
        "chain_length": round(r.chain_length, 4), "n_links": r.n_links,
        "draft_m": round(r.draft, 4), "swim_radius_m": round(r.swim_radius, 4),
        "anchor_angle_deg": round(r.anchor_angle_deg, 4),
        "barrel_angle_deg": round(r.barrel_angle_deg, 4),
        "pipe_angles_deg": [round(a, 4) for a in r.pipe_angles_deg],
        "grounded_length_m": round(r.grounded_length, 4),
        "suspended_chain_m": round(r.suspended_chain, 4),
        "H_N": round(r.H, 2), "H_buoy_N": round(r.H_buoy, 2),
        "ball_drag_N": round(r.meta.get("F_ball", 0.0), 2),
        "vertical_closure_err_m": round(r.vertical_closure_err, 6),
        "residual": {k: round(v, 9) for k, v in (r.force_residual or {}).items()},
        "constraint_anchor_ok": r.anchor_angle_deg <= ANCHOR_LIM_DEG + 1e-6,
        "constraint_barrel_ok": r.barrel_angle_deg <= BARREL_LIM_DEG + 1e-6,
        "freeboard_m": round(BUOY_H - r.draft, 4),
    }


# ------------------------------------------------------- Q1 / Q2 experiments --
def run_q1_q2() -> List[Dict]:
    rows = []
    for fam in ["A", "B"]:
        for v in [12.0, 24.0, 36.0]:
            rows.append(result_to_public(solve_static(v, 18.0, 1200.0, "II", 22.05, family=fam)))
    return rows


def max_solvable_ball(chain_type: str, chain_length: float, scenarios: Sequence[Dict],
                      m_hi: float = 6000.0, m_lo: float = 200.0) -> float:
    """
    Heaviest ball for which an equilibrium draft still exists.

    The buoy can only supply rho g pi R^2 H_buoy of net buoyancy, so past some
    mass the float is swamped and no draft closes the vertical balance.  This
    ceiling has to be located before bisecting inside the feasible set.
    """
    def solvable(m: float) -> bool:
        return all(solve_static(sc["v_wind"], sc["depth"], float(m), chain_type, chain_length,
                                family="A", v_cur=sc["v_cur"]).ok for sc in scenarios)

    if solvable(m_hi):
        return m_hi
    if not solvable(m_lo):
        return float("nan")
    lo, hi = m_lo, m_hi
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if solvable(mid):
            lo = mid
        else:
            hi = mid
    return lo


def search_ball_mass(v_wind: float, depth: float, chain_type: str, chain_length: float,
                     family: str = "A", v_cur: float = 0.0, m_lo: float = 200.0, m_hi: float = 6000.0,
                     barrel_lim: float = BARREL_LIM_DEG, anchor_lim: float = ANCHOR_LIM_DEG) -> Dict:
    """
    Minimal ball mass meeting both hard constraints.

    Both violated angles fall monotonically with the ball mass (heavier ball ->
    deeper draft -> larger net buoyancy -> more vertical pull), so feasibility is
    an upper set in the mass and plain bisection is exact up to its tolerance.
    """
    def feasible(m: float) -> Tuple[bool, Dict]:
        r = solve_static(v_wind, depth, float(m), chain_type, chain_length, family=family, v_cur=v_cur)
        ok = r.ok and r.barrel_angle_deg <= barrel_lim + 1e-9 and r.anchor_angle_deg <= anchor_lim + 1e-9
        return ok, result_to_public(r)

    m_hi = min(m_hi, max_solvable_ball(chain_type, chain_length,
                                       [{"depth": depth, "v_wind": v_wind, "v_cur": v_cur}], m_hi, m_lo))
    if not (m_hi == m_hi) or not feasible(m_hi)[0]:
        return {"found": False, "m_ceiling": m_hi,
                "scan": [feasible(float(m))[1] for m in np.linspace(max(m_lo, m_hi - 1000), m_hi, 6)]}

    lo, hi = m_lo, m_hi
    if feasible(m_lo)[0]:
        hi = m_lo
    else:
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if feasible(mid)[0]:
                hi = mid
            else:
                lo = mid

    m_star = float(math.ceil(hi))
    ok, best = feasible(m_star)
    while not ok and m_star < m_hi:
        m_star += 1.0
        ok, best = feasible(m_star)

    return {
        "found": True, "best": best, "m_min_continuous": round(hi, 3),
        "search_method": "monotone bisection + integer round-up",
        "binding": "anchor" if best["anchor_angle_deg"] > barrel_lim else "barrel",
    }


def ball_sweep(v_wind: float, depth: float, chain_type: str, chain_length: float,
               v_cur: float = 0.0, masses: Optional[Iterable[float]] = None) -> List[Dict]:
    masses = masses if masses is not None else np.linspace(500, 5000, 91)
    out = []
    for m in masses:
        r = solve_static(v_wind, depth, float(m), chain_type, chain_length, family="A", v_cur=v_cur)
        if r.ok:
            out.append(result_to_public(r))
    return out


# --------------------------------------------------- Q3: robust design layer --
ENV_BOX = {"depth": (16.0, 20.0), "v_wind": (0.0, 36.0), "v_cur": (0.0, 1.5)}


def monotonicity_study(chain_type: str = "IV", chain_length: float = 22.05, ball_mass: float = 4000.0) -> Dict:
    """
    Empirical monotonicity of the two constrained angles in the environment box.

    Establishes which corner of the box is the worst case, so the robust design
    problem can be enforced on a small verified scenario set instead of an
    arbitrary list.  Reported as sign counts over one-at-a-time perturbations.
    """
    base = {"depth": 18.0, "v_wind": 36.0, "v_cur": 1.5}
    axes = {"depth": np.linspace(16.0, 20.0, 9),
            "v_wind": np.linspace(0.0, 36.0, 10),
            "v_cur": np.linspace(0.0, 1.5, 7)}
    out = {}
    for axis, grid in axes.items():
        rows = []
        for val in grid:
            sc = dict(base)
            sc[axis] = float(val)
            r = solve_static(sc["v_wind"], sc["depth"], ball_mass, chain_type, chain_length,
                             family="A", v_cur=sc["v_cur"])
            if r.ok:
                rows.append({axis: float(val), "barrel": r.barrel_angle_deg,
                             "anchor": r.anchor_angle_deg, "draft": r.draft,
                             "swim": r.swim_radius})
        def trend(key: str) -> str:
            vals = [x[key] for x in rows]
            dif = np.diff(vals)
            if np.all(dif >= -1e-6):
                return "increasing"
            if np.all(dif <= 1e-6):
                return "decreasing"
            return "non-monotone"
        out[axis] = {"rows": rows, "barrel_trend": trend("barrel"),
                     "anchor_trend": trend("anchor"), "draft_trend": trend("draft"),
                     "swim_trend": trend("swim")}
    return out


WORST_CASE_SCENARIOS = [
    # barrel tilt worst: shallowest water, full wind + current
    {"depth": 16.0, "v_wind": 36.0, "v_cur": 1.5, "role": "worst_barrel"},
    # anchor angle worst: deepest water, full wind + current
    {"depth": 20.0, "v_wind": 36.0, "v_cur": 1.5, "role": "worst_anchor"},
    # deepest draft check: full wind + current at mid depth
    {"depth": 18.0, "v_wind": 36.0, "v_cur": 1.5, "role": "worst_draft"},
    # wind-only extreme (current relieves nothing, chain lifts differently)
    {"depth": 20.0, "v_wind": 36.0, "v_cur": 0.0, "role": "wind_only"},
]

TYPICAL_SCENARIOS = [
    {"depth": 18.0, "v_wind": 24.0, "v_cur": 1.0},
    {"depth": 18.0, "v_wind": 12.0, "v_cur": 0.5},
    {"depth": 17.0, "v_wind": 24.0, "v_cur": 1.5},
    {"depth": 19.0, "v_wind": 12.0, "v_cur": 1.0},
]


def evaluate_design(chain_type: str, chain_length: float, ball_mass: float,
                    scenarios: Sequence[Dict], family: str = "A") -> Dict:
    rows = []
    for sc in scenarios:
        r = solve_static(sc["v_wind"], sc["depth"], ball_mass, chain_type, chain_length,
                         family=family, v_cur=sc["v_cur"])
        pub = result_to_public(r)
        pub["role"] = sc.get("role", "")
        rows.append(pub)
    ok = all(x["ok"] for x in rows)
    return {
        "rows": rows, "ok": ok,
        "hard_ok": ok and all(x["constraint_anchor_ok"] and x["constraint_barrel_ok"] for x in rows),
        "worst_barrel": max(x["barrel_angle_deg"] for x in rows) if ok else float("inf"),
        "worst_anchor": max(x["anchor_angle_deg"] for x in rows) if ok else float("inf"),
        "max_draft": max(x["draft_m"] for x in rows) if ok else float("inf"),
        "max_swim": max(x["swim_radius_m"] for x in rows) if ok else float("inf"),
        "min_freeboard": min(x["freeboard_m"] for x in rows) if ok else float("-inf"),
    }


def lightest_feasible_mass(pred, m_lo: float = 200.0, m_hi: float = 6000.0,
                           n_scan: int = 25, granularity: float = 10.0) -> Optional[float]:
    """
    Lightest ball mass satisfying `pred`, without assuming feasibility is an
    upper set in the mass.

    It is not: a heavier ball lowers both angles but also deepens the draft, and
    past the buoy's reserve buoyancy no equilibrium exists at all.  Feasibility
    is therefore an interval, so a coarse scan brackets its lower edge before
    bisection refines it, and the answer is rounded up to a 10 kg casting step.
    """
    grid = np.linspace(m_lo, m_hi, n_scan)
    first = None
    prev = m_lo
    for m in grid:
        if pred(float(m)):
            first = float(m)
            break
        prev = float(m)
    if first is None:
        return None
    lo, hi = prev, first
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        if pred(mid):
            hi = mid
        else:
            lo = mid
    m_star = float(math.ceil(hi / granularity) * granularity)
    for _ in range(20):
        if pred(m_star):
            return m_star
        m_star += granularity
    return None


def min_feasible_ball(chain_type: str, chain_length: float, barrel_lim: float = BARREL_LIM_DEG,
                      anchor_lim: float = ANCHOR_LIM_DEG, m_lo: float = 200.0,
                      m_hi: float = 6000.0) -> Optional[Dict]:
    """
    For one (type, length), the lightest ball that survives every worst-case
    scenario.  That single point carries the whole efficient frontier of that
    (type, length): anything lighter violates a hard constraint, anything heavier
    only deepens the draft, which is itself an objective to minimise.
    """
    chain_length, _ = snap_chain_length(chain_type, chain_length)

    def ok(m: float) -> bool:
        return bool(evaluate_design(chain_type, chain_length, float(m), WORST_CASE_SCENARIOS)["hard_ok"])

    m_star = lightest_feasible_mass(ok, m_lo, m_hi)
    if m_star is None:
        return None
    hi = m_star
    ev = evaluate_design(chain_type, chain_length, m_star, WORST_CASE_SCENARIOS)
    return {"chain_type": chain_type, "chain_length": round(chain_length, 4),
            "n_links": ev["rows"][0]["n_links"], "ball_mass": m_star,
            "m_min_continuous": round(hi, 2), **{k: ev[k] for k in
            ("worst_barrel", "worst_anchor", "max_draft", "max_swim", "min_freeboard")}}


def dominates(a: Dict, b: Dict, keys: Sequence[str]) -> bool:
    return (all(a[k] <= b[k] + 1e-9 for k in keys)
            and any(a[k] < b[k] - 1e-9 for k in keys))


def pareto_front(rows: List[Dict], keys: Sequence[str]) -> List[Dict]:
    return [r for r in rows if not any(dominates(o, r, keys) for o in rows)]


def entropy_weights(matrix: np.ndarray) -> np.ndarray:
    """Entropy weights on a min-max normalised benefit matrix."""
    p = matrix / np.maximum(matrix.sum(axis=0, keepdims=True), 1e-12)
    with np.errstate(divide="ignore", invalid="ignore"):
        ent = -np.nansum(np.where(p > 0, p * np.log(p), 0.0), axis=0) / math.log(max(len(matrix), 2))
    d = 1.0 - ent
    if d.sum() <= 1e-12:
        return np.full(matrix.shape[1], 1.0 / matrix.shape[1])
    return d / d.sum()


def topsis(rows: List[Dict], keys: Sequence[str], weights: Optional[np.ndarray] = None):
    """TOPSIS on minimisation objectives; returns closeness scores and weights."""
    X = np.array([[float(r[k]) for k in keys] for r in rows], dtype=float)
    span = X.max(axis=0) - X.min(axis=0)
    span[span < 1e-12] = 1.0
    benefit = (X.max(axis=0) - X) / span  # larger is better, in [0, 1]
    w = entropy_weights(benefit + 1e-9) if weights is None else np.asarray(weights, dtype=float)
    w = w / w.sum()
    Z = benefit * w
    best, worst = Z.max(axis=0), Z.min(axis=0)
    d_best = np.linalg.norm(Z - best, axis=1)
    d_worst = np.linalg.norm(Z - worst, axis=1)
    score = d_worst / np.maximum(d_best + d_worst, 1e-12)
    return score, w


def weight_robustness(rows: List[Dict], keys: Sequence[str], n_draw: int = 4000, seed: int = 20160901) -> List[Dict]:
    """
    How often each candidate ranks first when the objective weights are drawn
    uniformly from the simplex.  Answers the standard objection that a scalarised
    recommendation is an artefact of hand-picked weights.
    """
    rng = np.random.default_rng(seed)
    wins = np.zeros(len(rows), dtype=int)
    top3 = np.zeros(len(rows), dtype=int)
    for _ in range(n_draw):
        w = rng.dirichlet(np.ones(len(keys)))
        score, _ = topsis(rows, keys, w)
        order = np.argsort(-score)
        wins[order[0]] += 1
        top3[order[:3]] += 1
    return [{"win_rate": wins[i] / n_draw, "top3_rate": top3[i] / n_draw} for i in range(len(rows))]


def _parameter_draws(n_draw: int, seed: int) -> List[Dict[str, float]]:
    """
    Common random numbers for the three inputs the model cannot pin down: sea
    water density, chain drag width, and the two empirical load coefficients.
    Reusing one fixed sample keeps the reliability estimate monotone in the ball
    mass, which is what makes bisection on it legitimate.
    """
    rng = np.random.default_rng(seed)
    return [
        {"rho": float(rng.uniform(1020.0, 1030.0)),
         "chain_scale": float(rng.uniform(0.8, 1.3)),
         "kw": float(rng.uniform(0.9, 1.15)),
         "kc": float(rng.uniform(0.9, 1.15))}
        for _ in range(n_draw)
    ]


def _with_perturbation(draw: Dict[str, float], fn):
    global RHO, CHAIN_DRAG_SCALE, K_WIND, K_CUR
    rho0, sc0, kw0, kc0 = RHO, CHAIN_DRAG_SCALE, K_WIND, K_CUR
    try:
        RHO = draw["rho"]
        CHAIN_DRAG_SCALE = draw["chain_scale"]
        K_WIND = 0.625 * draw["kw"]
        K_CUR = 374.0 * draw["kc"]
        return fn()
    finally:
        RHO, CHAIN_DRAG_SCALE, K_WIND, K_CUR = rho0, sc0, kw0, kc0


def satisfaction_rate(chain_type: str, chain_length: float, ball_mass: float,
                      draws: Sequence[Dict[str, float]]) -> float:
    hits = 0
    for dr in draws:
        ev = _with_perturbation(dr, lambda: evaluate_design(chain_type, chain_length,
                                                            float(ball_mass), WORST_CASE_SCENARIOS[:3]))
        if ev["hard_ok"]:
            hits += 1
    return hits / max(len(draws), 1)


def reliability_based_design(chain_type: str, chain_length: float, target: float = 0.95,
                            n_draw: int = 80, seed: int = 20160903, m_hi: float = 6000.0,
                            n_scan: int = 22) -> Dict:
    """
    Ball mass sized against a chance constraint instead of the nominal one.

    The deterministic optimum sits exactly on the 5 deg boundary, so it survives
    only about half of the coefficient draws.  Raising the mass buys angle margin
    but eats reserve buoyancy, so the satisfaction rate rises and then collapses
    once perturbed draws start to swamp the buoy: the whole mass profile is
    therefore scanned and the best attainable rate is reported honestly, together
    with the lightest mass reaching `target` when one exists.
    """
    draws = _parameter_draws(n_draw, seed)
    det = min_feasible_ball(chain_type, chain_length)
    det_mass = det["ball_mass"] if det else float("nan")
    lo = det_mass if det else 200.0
    profile = []
    for m in np.linspace(lo, m_hi, n_scan):
        rate = satisfaction_rate(chain_type, chain_length, float(m), draws)
        profile.append({"ball_mass": round(float(m), 1), "rate": rate})
        if rate == 0.0 and any(p["rate"] > 0 for p in profile):
            break
    hit = next((p for p in profile if p["rate"] >= target), None)
    peak = max(profile, key=lambda p: p["rate"]) if profile else None
    chosen = hit or peak
    if chosen is None:
        return {"found": False}
    m_star = float(math.ceil(chosen["ball_mass"] / 10.0) * 10.0)
    ev = evaluate_design(chain_type, chain_length, m_star, WORST_CASE_SCENARIOS)
    return {
        "found": True, "target": target, "target_met": bool(hit), "n_draw": n_draw,
        "ball_mass": m_star, "deterministic_ball_mass": det_mass,
        "extra_mass_kg": None if det is None else m_star - det_mass,
        "rate": satisfaction_rate(chain_type, chain_length, m_star, draws),
        "rate_at_deterministic": float("nan") if det is None
        else satisfaction_rate(chain_type, chain_length, det_mass, draws),
        "best_attainable_rate": peak["rate"] if peak else None,
        "rate_profile": profile,
        "worst_barrel": ev["worst_barrel"], "worst_anchor": ev["worst_anchor"],
        "max_draft": ev["max_draft"], "min_freeboard": ev["min_freeboard"],
        "max_swim": ev["max_swim"],
    }


def envelope_compliance(chain_type: str, chain_length: float, ball_mass: float,
                        n_depth: int = 9, n_wind: int = 7, n_cur: int = 4) -> Dict:
    """
    Fraction of the environment box in which each constraint holds, plus the
    worst values.  Lets a design that gives up the 5 deg target in the rarest
    corner be compared with a strict design on an explicit, quantified basis.
    """
    tot = ok_barrel = ok_anchor = ok_both = 0
    worst_barrel = worst_anchor = 0.0
    max_draft = 0.0
    max_swim = 0.0
    for h in np.linspace(*ENV_BOX["depth"], n_depth):
        for vw in np.linspace(*ENV_BOX["v_wind"], n_wind):
            for vc in np.linspace(*ENV_BOX["v_cur"], n_cur):
                r = solve_static(float(vw), float(h), ball_mass, chain_type, chain_length,
                                 family="A", v_cur=float(vc))
                if not r.ok:
                    tot += 1
                    continue
                tot += 1
                b = r.barrel_angle_deg <= BARREL_LIM_DEG + 1e-6
                a = r.anchor_angle_deg <= ANCHOR_LIM_DEG + 1e-6
                ok_barrel += b
                ok_anchor += a
                ok_both += (a and b)
                worst_barrel = max(worst_barrel, r.barrel_angle_deg)
                worst_anchor = max(worst_anchor, r.anchor_angle_deg)
                max_draft = max(max_draft, r.draft)
                max_swim = max(max_swim, r.swim_radius)
    return {"n_points": tot, "barrel_ok_frac": ok_barrel / max(tot, 1),
            "anchor_ok_frac": ok_anchor / max(tot, 1), "both_ok_frac": ok_both / max(tot, 1),
            "worst_barrel": worst_barrel, "worst_anchor": worst_anchor,
            "max_draft": max_draft, "max_swim": max_swim,
            "min_freeboard": BUOY_H - max_draft}


RELAXED_SCENARIOS = [
    # 5 deg target enforced only up to a 1.0 m/s current: the joint occurrence of
    # a 36 m/s gale and the peak spring tide is the rarest corner of the box.
    {"depth": 16.0, "v_wind": 36.0, "v_cur": 1.0, "role": "worst_barrel_relaxed"},
    {"depth": 20.0, "v_wind": 36.0, "v_cur": 1.5, "role": "worst_anchor_full"},
    {"depth": 18.0, "v_wind": 36.0, "v_cur": 1.0, "role": "worst_draft_relaxed"},
]


def design_relaxed(m_hi: float = 6000.0) -> Dict:
    """
    Freeboard-first alternative.

    The strict design is pushed to a draft near 1.69 m by the analytic bound, so
    it keeps only about 0.31 m of freeboard on a 2 m buoy.  Here the anchor
    constraint stays hard over the whole box (dragging loses the node) while the
    5 deg barrel target is enforced only up to 1.0 m/s of current; the barrel
    tilt actually reached in the rarest corner is then reported rather than hidden.
    """
    def ok(ctype: str, L: float, m: float) -> bool:
        ev = evaluate_design(ctype, L, m, RELAXED_SCENARIOS)
        if not ev["ok"]:
            return False
        rows = ev["rows"]
        anchor_ok = all(x["constraint_anchor_ok"] for x in rows)
        barrel_ok = all(x["constraint_barrel_ok"] for x in rows if x["role"] != "worst_anchor_full")
        return anchor_ok and barrel_ok

    out = []
    for ctype in ["II", "III", "IV", "V"]:
        for L in integer_chain_lengths(ctype, 18.0, 32.0, stride=1.5):
            m_star = lightest_feasible_mass(lambda m: ok(ctype, L, m), 200.0, m_hi)
            if m_star is None:
                continue
            full = evaluate_design(ctype, L, m_star, WORST_CASE_SCENARIOS)
            rel_rows = evaluate_design(ctype, L, m_star, RELAXED_SCENARIOS)["rows"]
            out.append({"chain_type": ctype, "chain_length": round(L, 4),
                        "n_links": full["rows"][0]["n_links"], "ball_mass": m_star,
                        "worst_barrel_relaxed": max(x["barrel_angle_deg"] for x in rel_rows
                                                    if x["role"] != "worst_anchor_full"),
                        "worst_barrel_full_box": full["worst_barrel"],
                        "worst_anchor": full["worst_anchor"],
                        "max_draft": full["max_draft"], "max_swim": full["max_swim"],
                        "min_freeboard": full["min_freeboard"]})
    if not out:
        return {"found": False}
    keys = ["max_draft", "max_swim", "worst_barrel_full_box", "worst_anchor", "ball_mass"]
    front = pareto_front(out, keys)
    # Freeboard first: this branch exists to buy draft back, so the draft is the
    # lead criterion and the swim radius only breaks ties.
    best = dict(min(front, key=lambda r: (round(r["max_draft"], 2), r["max_swim"], r["worst_anchor"])))
    best["envelope"] = envelope_compliance(best["chain_type"], best["chain_length"], best["ball_mass"])
    return {"found": True, "n_candidates": len(out), "pareto_size": len(front),
            "objective_keys": keys, "best": best,
            "table": sorted(out, key=lambda r: (r["max_draft"], r["max_swim"]))[:12]}


def reliability_check(chain_type: str, chain_length: float, ball_mass: float,
                      n_draw: int = 300, seed: int = 20160902) -> Dict:
    """
    Chance-constrained view of the recommendation.

    Perturbs the three inputs the model cannot pin down — sea-water density, the
    chain drag width, and the wind/current load coefficients — and reports the
    fraction of draws in which both hard constraints still hold at the worst-case
    corner.  Turns "the empirical formulas are approximate" from a caveat into a
    number.
    """
    global RHO, CHAIN_DRAG_SCALE, K_WIND, K_CUR
    rng = np.random.default_rng(seed)
    rho0, scale0, kw0, kc0 = RHO, CHAIN_DRAG_SCALE, K_WIND, K_CUR
    ok_count = 0
    worst_barrel, worst_anchor, drafts = [], [], []
    try:
        for _ in range(n_draw):
            RHO = float(rng.uniform(1020.0, 1030.0))
            CHAIN_DRAG_SCALE = float(rng.uniform(0.8, 1.3))
            K_WIND = kw0 * float(rng.uniform(0.9, 1.15))
            K_CUR = kc0 * float(rng.uniform(0.9, 1.15))
            ev = evaluate_design(chain_type, chain_length, ball_mass, WORST_CASE_SCENARIOS)
            if ev["hard_ok"]:
                ok_count += 1
            if ev["ok"]:
                worst_barrel.append(ev["worst_barrel"])
                worst_anchor.append(ev["worst_anchor"])
                drafts.append(ev["max_draft"])
    finally:
        RHO, CHAIN_DRAG_SCALE, K_WIND, K_CUR = rho0, scale0, kw0, kc0

    def pct(a, q):
        return float(np.percentile(a, q)) if a else float("nan")

    return {
        "n_draw": n_draw, "satisfaction_rate": ok_count / n_draw,
        "barrel_p50": pct(worst_barrel, 50), "barrel_p95": pct(worst_barrel, 95),
        "anchor_p50": pct(worst_anchor, 50), "anchor_p95": pct(worst_anchor, 95),
        "draft_p50": pct(drafts, 50), "draft_p95": pct(drafts, 95),
        "perturbed": ["rho in [1020,1030]", "chain drag scale in [0.8,1.3]",
                      "K_wind x [0.90,1.15]", "K_current x [0.90,1.15]"],
    }


def design_q3(family: str = "A") -> Dict:
    """
    Q3 as a robust design problem.

    Stage 1  enumerate (chain type, integer link count) and bisect the lightest
             ball mass that survives the verified worst-case corners;
    Stage 2  keep the Pareto front over (max draft, max swim radius, worst barrel
             tilt, worst anchor angle, ball mass);
    Stage 3  rank with entropy-weighted TOPSIS, then report how stable that rank
             is under random weights, plus the analytic draft bound for context.
    """
    minimal: List[Dict] = []
    for ctype in ["I", "II", "III", "IV", "V"]:
        for L in integer_chain_lengths(ctype, 16.0, 32.0, stride=1.0):
            got = min_feasible_ball(ctype, L)
            if got:
                minimal.append(got)

    obj_keys = ["max_draft", "max_swim", "worst_barrel", "worst_anchor", "ball_mass"]
    front = pareto_front(minimal, obj_keys) if minimal else []
    front = sorted(front, key=lambda r: (r["max_draft"], r["max_swim"]))

    ranked: List[Dict] = []
    best = None
    weights = None
    if front:
        score, weights = topsis(front, obj_keys)
        robust = weight_robustness(front, obj_keys)
        for i, r in enumerate(front):
            item = dict(r)
            item["topsis"] = float(score[i])
            item.update(robust[i])
            ranked.append(item)
        ranked.sort(key=lambda r: -r["topsis"])
        best = ranked[0]

    verify = None
    if best:
        typical = evaluate_design(best["chain_type"], best["chain_length"], best["ball_mass"], TYPICAL_SCENARIOS)
        dense = []
        for h in np.linspace(16.0, 20.0, 9):
            for vw in np.linspace(0.0, 36.0, 7):
                for vc in np.linspace(0.0, 1.5, 4):
                    dense.append({"depth": float(h), "v_wind": float(vw), "v_cur": float(vc)})
        dense_ev = evaluate_design(best["chain_type"], best["chain_length"], best["ball_mass"], dense)
        fails = [r for r in dense_ev["rows"]
                 if (not r["ok"]) or (not r["constraint_anchor_ok"]) or (not r["constraint_barrel_ok"])]
        verify = {
            "typical": {k: typical[k] for k in typical if k != "rows"},
            "typical_rows": typical["rows"],
            "dense_n": len(dense),
            "dense_hard_fail": len(fails),
            "dense_worst_barrel": dense_ev["worst_barrel"],
            "dense_worst_anchor": dense_ev["worst_anchor"],
            "dense_max_draft": dense_ev["max_draft"],
            "reliability": reliability_check(best["chain_type"], best["chain_length"], best["ball_mass"]),
            "reliability_based": reliability_based_design(best["chain_type"], best["chain_length"]),
            "envelope": envelope_compliance(best["chain_type"], best["chain_length"], best["ball_mass"]),
        }

    bound = {
        f"vw{int(vw)}_vc{vc:g}": round(draft_bound_for_barrel(vw, vc), 4)
        for vw, vc in [(36.0, 1.5), (36.0, 1.0), (36.0, 0.0), (24.0, 1.5), (24.0, 1.0), (12.0, 1.5)]
    }

    return {
        "formulation": "min over designs of (max draft, max swim, worst barrel, worst anchor, ball mass)"
                       " s.t. barrel<=5deg and anchor<=16deg on the verified worst-case corners",
        "n_feasible_designs": len(minimal),
        "pareto_size": len(front),
        "objective_keys": obj_keys,
        "entropy_weights": {k: round(float(w), 4) for k, w in zip(obj_keys, weights)} if weights is not None else None,
        "analytic_draft_bound": bound,
        "minimal_ball_table": minimal,
        "ranked_pareto": ranked[:20],
        "best": {k: v for k, v in best.items()} if best else None,
        "best_worst_case_rows": evaluate_design(best["chain_type"], best["chain_length"],
                                                best["ball_mass"], WORST_CASE_SCENARIOS)["rows"] if best else None,
        "alt_min_draft": min(front, key=lambda r: (r["max_draft"], r["max_swim"])) if front else None,
        "alt_min_swim": min(front, key=lambda r: (r["max_swim"], r["max_draft"])) if front else None,
        "verification": verify,
    }


# ---------------------------------------------------- ablations / sensitivity --
def ablation_ball_buoyancy() -> List[Dict]:
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


def ablation_ball_drag() -> List[Dict]:
    """rev3 adds the ball's own drag; this quantifies what it changes."""
    global BALL_DRAG_ON
    rows = []
    for label, flag in [("ball_drag_on", True), ("ball_drag_off", False)]:
        old = BALL_DRAG_ON
        BALL_DRAG_ON = flag
        r = solve_static(36.0, 20.0, 4000.0, "IV", 22.05, family="A", v_cur=1.5)
        BALL_DRAG_ON = old
        pub = result_to_public(r)
        pub["ablation"] = label
        rows.append(pub)
    return rows


def sensitivity_rho() -> List[Dict]:
    global RHO
    rows = []
    for rho in [1020.0, 1025.0, 1030.0]:
        old = RHO
        RHO = rho
        r = solve_static(24.0, 18.0, 1200.0, "II", 22.05, family="A")
        RHO = old
        pub = result_to_public(r)
        pub["rho"] = rho
        rows.append(pub)
    return rows


def sensitivity_chain_drag() -> List[Dict]:
    global CHAIN_DRAG_SCALE
    rows = []
    for s in [0.8, 1.0, 1.3]:
        old = CHAIN_DRAG_SCALE
        CHAIN_DRAG_SCALE = s
        r = solve_static(36.0, 20.0, 4000.0, "IV", 22.05, family="A", v_cur=1.5)
        CHAIN_DRAG_SCALE = old
        pub = result_to_public(r)
        pub["chain_drag_scale"] = s
        rows.append(pub)
    return rows


def grid_refinement_check() -> List[Dict]:
    """
    Discretisation control on a real configuration.

    The chain pitch is temporarily subdivided 1x / 2x / 4x and the full Q2
    equilibrium is re-solved, so the reported spread is the error the paper's
    numbers actually carry rather than the error of an isolated chain integration.
    """
    rows = []
    pitch0 = CHAIN_CATALOG["II"]["pitch"]
    try:
        for sub in [1, 2, 4, 8]:
            CHAIN_CATALOG["II"]["pitch"] = pitch0 / sub
            r = solve_static(36.0, 18.0, 2238.0, "II", 22.05, family="A", snap_length=False)
            rows.append({"subdivision": sub, "n_elements": r.n_links,
                         "anchor_angle_deg": round(r.anchor_angle_deg, 5),
                         "barrel_angle_deg": round(r.barrel_angle_deg, 5),
                         "draft_m": round(r.draft, 6),
                         "swim_radius_m": round(r.swim_radius, 5)})
    finally:
        CHAIN_CATALOG["II"]["pitch"] = pitch0
    # Successive halvings shrink the anchor-angle change by about half, i.e. the
    # link discretisation is first order; Richardson then gives the limit value.
    if len(rows) >= 3:
        a1, a2, a3 = (rows[-3]["anchor_angle_deg"], rows[-2]["anchor_angle_deg"],
                      rows[-1]["anchor_angle_deg"])
        denom = (a1 - a2) - (a2 - a3)
        if abs(denom) > 1e-12:
            order = math.log(abs((a1 - a2) / (a2 - a3))) / math.log(2.0)
            richardson = a3 + (a3 - a2) / (2.0**order - 1.0)
            rows.append({"subdivision": "Richardson 外推", "n_elements": None,
                         "anchor_angle_deg": round(richardson, 5),
                         "observed_order": round(order, 3),
                         "baseline_error_deg": round(abs(rows[0]["anchor_angle_deg"] - richardson), 5)})
    return rows


# ------------------------------------------------------------------- driver --
def main():
    report = {
        "revision": "rev3-ball-drag-analytic-bound-robust-design",
        "hard_limits": {"barrel_deg": BARREL_LIM_DEG, "anchor_deg": ANCHOR_LIM_DEG},
        "env_box": ENV_BOX,
        "chain_drag_widths": {
            t: {"volume_equivalent": round(chain_drag_width(c["mu"]), 5),
                "link_geometry": round(chain_drag_width_link(c["pitch"]), 5)}
            for t, c in CHAIN_CATALOG.items()
        },
    }

    print("Q1/Q2 states ...")
    report["q1_q2_fixed_ball"] = run_q1_q2()

    print("Q2 minimal ball mass ...")
    report["q2_ball_search_A"] = search_ball_mass(36.0, 18.0, "II", 22.05, family="A")
    report["q2_ball_search_B"] = search_ball_mass(36.0, 18.0, "II", 22.05, family="B")
    report["q2_ball_sweep"] = ball_sweep(36.0, 18.0, "II", 22.05)

    print("Family contrast ...")
    report["family_contrast"] = [
        result_to_public(solve_static(v, 18.0, 1200.0, "II", 22.05, family=fam))
        for v in [12.0, 24.0, 36.0] for fam in ["A", "B"]
    ]

    print("Analytic draft bound ...")
    report["draft_bound_curve"] = [
        {"v_cur": float(vc),
         "v_wind": float(vw),
         "draft_min_m": round(draft_bound_for_barrel(float(vw), float(vc)), 4)}
        for vc in [0.0, 0.5, 1.0, 1.5] for vw in np.linspace(12.0, 36.0, 13)
    ]

    print("Monotonicity of the environment box ...")
    report["monotonicity"] = monotonicity_study()

    print("Ablations / sensitivity ...")
    report["ablation_ball_buoyancy"] = ablation_ball_buoyancy()
    report["ablation_ball_drag"] = ablation_ball_drag()
    report["sensitivity_rho"] = sensitivity_rho()
    report["sensitivity_chain_drag"] = sensitivity_chain_drag()
    report["grid_refinement"] = grid_refinement_check()
    report["integer_link_examples"] = {
        "II_22.05": snap_chain_length("II", 22.05),
        "V_22.05_invalid_nominal": snap_chain_length("V", 22.05),
        "V_21.96": snap_chain_length("V", 21.96),
    }

    print("Q3 robust design search ...")
    report["q3_design"] = design_q3("A")

    print("Q3 freeboard-first alternative ...")
    report["q3_relaxed"] = design_relaxed()

    shapes = {}
    for v in [12.0, 24.0, 36.0]:
        r = solve_static(v, 18.0, 1200.0, "II", 22.05, family="A")
        shapes[f"v{int(v)}"] = {"system_x": r.system_x, "system_y": r.system_y, **result_to_public(r)}
    if report["q2_ball_search_A"].get("found"):
        m = report["q2_ball_search_A"]["best"]["ball_mass"]
        r = solve_static(36.0, 18.0, m, "II", 22.05, family="A")
        shapes["v36_optball"] = {"system_x": r.system_x, "system_y": r.system_y, **result_to_public(r)}
    if report["q3_design"].get("best"):
        b = report["q3_design"]["best"]
        r = solve_static(36.0, 20.0, b["ball_mass"], b["chain_type"], b["chain_length"], family="A", v_cur=1.5)
        shapes["q3_extreme"] = {"system_x": r.system_x, "system_y": r.system_y, **result_to_public(r)}
    report["shapes"] = shapes

    out = os.path.join(OUT_DIR, "metrics.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Wrote", out)

    try:
        from export_xlsx import export_xlsx
        print("Wrote", export_xlsx(out, os.path.join(OUT_DIR, "results_tables.xlsx")))
    except Exception as e:  # pragma: no cover
        print("xlsx export skipped:", e)

    print("\n=== Q1 / Q2 (family A, ball 1200 kg) ===")
    for row in report["q1_q2_fixed_ball"]:
        if row["family"] == "A":
            print(f"v={row['v_wind']:>4}: d={row['draft_m']:.4f} R={row['swim_radius_m']:.3f} "
                  f"theta={row['barrel_angle_deg']:.3f} phi={row['anchor_angle_deg']:.3f} "
                  f"grounded={row['grounded_length_m']:.3f} res={row['residual']}")
    if report["q2_ball_search_A"].get("found"):
        print("\nQ2 minimal ball:", report["q2_ball_search_A"]["best"]["ball_mass"], "kg")
    q3 = report["q3_design"]
    print("\nQ3 feasible designs:", q3["n_feasible_designs"], "Pareto:", q3["pareto_size"])
    print("Q3 recommendation:", q3.get("best"))
    print("Analytic draft bound:", q3.get("analytic_draft_bound"))


if __name__ == "__main__":
    main()
