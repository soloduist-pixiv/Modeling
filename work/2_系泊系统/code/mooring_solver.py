"""2016A 系泊系统 — 张力传播 + 悬链线."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from scipy.optimize import brentq

G = 9.8
RHO = 1025.0
BUOY_R, BUOY_H, BUOY_M = 1.0, 2.0, 1000.0
PIPE_L, PIPE_D, PIPE_M = 1.0, 0.05, 10.0
BARREL_L, BARREL_D, BARREL_M = 1.0, 0.30, 100.0
N_PIPES = 4
CHAIN_TYPES = {"I": (78, 3.2), "II": (105, 7.0), "III": (120, 12.5), "IV": (150, 19.5), "V": (180, 28.12)}


@dataclass
class MooringConfig:
    water_depth: float = 18.0
    chain_type: str = "II"
    chain_length: float = 22.05
    ball_mass: float = 1200.0
    wind_speed: float = 12.0
    current_speed: float = 0.0


@dataclass
class MooringResult:
    draft: float
    excursion_radius: float
    barrel_angle_deg: float
    pipe_angles_deg: List[float]
    anchor_angle_deg: float
    chain_on_bottom_m: float
    chain_suspended_m: float
    horizontal_force_N: float
    converged: bool
    message: str = ""


def wind_f(a: float, v: float) -> float:
    return 0.625 * a * v * v


def cur_f(a: float, v: float) -> float:
    return 374.0 * a * v * v


def buoy_f(r: float, lsub: float) -> float:
    return RHO * G * math.pi * r * r * max(0.0, lsub)


def seg_w(mass: float, r: float, L: float, ztop: float, zbot: float, wz: float) -> float:
    sub = max(0.0, min(L, wz - zbot))
    return mass * G - buoy_f(r, sub)


def seg_ext(mass: float, r: float, L: float, ztop: float, zbot: float, wz: float, vw: float, vc: float) -> Tuple[float, float]:
    sub = max(0.0, min(L, wz - zbot))
    exp = max(0.0, min(L, ztop - wz))
    fw = wind_f(2 * r * exp, vw)
    fc = cur_f(2 * r * sub, vc)
    return fw, fc


def catenary(h: float, H: float, w: float, Ltot: float) -> Tuple[float, float, float, float]:
    """锚链：海床贴底段 + 悬空悬链线，或锚点抬升."""
    if h <= 1e-6:
        return 0.0, Ltot, 0.0, 0.0
    a = H / w

    def height(x: float) -> float:
        return a * (math.cosh(x / a) - 1)

    def arc(x: float) -> float:
        return a * math.sinh(x / a)

    # 全部链长用于贴底抬升悬链（切线水平）时的最大高度与跨度
    x_full = a * math.asinh(Ltot / a)
    h_full = height(x_full)

    if h_full + 1e-6 >= h:
        # 可达：求满足高度的悬空段
        try:
            x_need = brentq(lambda x: height(x) - h, 1e-8, max(x_full, 1.0))
        except ValueError:
            x_need = x_full
        s_need = arc(x_need)
        if s_need <= Ltot + 1e-6:
            lflat = max(0.0, Ltot - s_need)
            return lflat + x_need, lflat, s_need, 0.0
        return x_full, 0.0, Ltot, 0.0

    # 高度略超满链悬空能力（<3%）：仍用满链贴底抬升模型（工程上常见）
    if h <= h_full * 1.03:
        return x_full, 0.0, Ltot, 0.0

    # 满链悬空仍不足高度：锚点抬升角 alpha
    def falpha(al: float) -> float:
        u = math.asinh(math.tan(al))
        xe = a * (math.asinh(math.sinh(u) + h / a) - u)
        return a * (math.sinh(u + xe / a) - math.sinh(u)) - Ltot

    try:
        al = brentq(falpha, 1e-8, math.radians(89))
    except ValueError:
        al = math.radians(16)
    u = math.asinh(math.tan(al))
    xe = a * (math.asinh(math.sinh(u) + h / a) - u)
    return xe, 0.0, Ltot, math.degrees(al)


def solve_mooring(cfg: MooringConfig) -> MooringResult:
    _, wc = CHAIN_TYPES[cfg.chain_type]
    weff = wc * G
    wz = cfg.water_depth
    segs = [(PIPE_M, PIPE_D / 2, PIPE_L)] * N_PIPES + [(BARREL_M, BARREL_D / 2, BARREL_L)]

    def evaluate(draft: float) -> Optional[dict]:
        if draft <= 0.05 or draft >= BUOY_H - 0.05:
            return None

        z = wz - draft
        x = 0.0
        angles: List[float] = []

        # 总水平外力（张力沿系泊线恒定）
        H = wind_f(2 * BUOY_R * (BUOY_H - draft), cfg.wind_speed) + cur_f(2 * BUOY_R * draft, cfg.current_speed)
        zc = z
        for mass, r, L in segs:
            ztop, zbot = zc, zc - L
            fw, fc = seg_ext(mass, r, L, ztop, zbot, wz, cfg.wind_speed, cfg.current_speed)
            H += fw + fc
            zc -= L

        bup = RHO * G * math.pi * BUOY_R * BUOY_R * draft
        V = bup - BUOY_M * G

        for mass, r, L in segs:
            ztop, zbot = z, z - L
            th = math.degrees(math.atan(H / max(V, 1e-6)))
            angles.append(th)
            w = seg_w(mass, r, L, ztop, zbot, wz)
            V = V - w * math.cos(math.radians(th))
            x += L * math.sin(math.radians(th))
            z -= L * math.cos(math.radians(th))

        z_chain = z
        h_lift = z_chain
        if h_lift < 0.2:
            return None

        xchain, lflat, larc, aang = catenary(h_lift, H, weff, cfg.chain_length)
        V = V - cfg.ball_mass * G
        return dict(
            draft=draft,
            angles=angles,
            H=H,
            V_end=V,
            xtot=x + xchain,
            h_lift=h_lift,
            aang=aang,
            lflat=lflat,
            larc=larc,
            err=abs(V),
        )

    best = None
    for d in np.linspace(0.3, 1.9, 200):
        st = evaluate(float(d))
        if st and (best is None or st["err"] < best["err"]):
            best = st

    if best is None:
        return MooringResult(0, 0, 0, [0] * 4, 0, 0, 0, 0, False, "no_solution")

    try:
        d_star = brentq(lambda d: evaluate(d)["V_end"], 0.3, 1.9)
        st = evaluate(d_star) or best
    except Exception:
        st = best

    barrel = st["angles"][-1]
    pipes = list(reversed(st["angles"][:-1]))
    return MooringResult(
        draft=st["draft"],
        excursion_radius=st["xtot"],
        barrel_angle_deg=barrel,
        pipe_angles_deg=pipes,
        anchor_angle_deg=st["aang"],
        chain_on_bottom_m=st["lflat"],
        chain_suspended_m=st["larc"],
        horizontal_force_N=st["H"],
        converged=st["err"] < 50,
        message="ok",
    )


def optimize_ball_mass(cfg: MooringConfig) -> Tuple[float, MooringResult]:
    lo, hi = 1200.0, 4500.0

    def ok(m: float) -> bool:
        r = solve_mooring(MooringConfig(**{**asdict(cfg), "ball_mass": m}))
        return r.converged and r.barrel_angle_deg <= 5.0 and r.anchor_angle_deg <= 16.0

    while hi <= 8000 and not ok(hi):
        hi += 500
    if not ok(hi):
        return hi, solve_mooring(MooringConfig(**{**asdict(cfg), "ball_mass": hi}))
    while hi - lo > 0.5:
        mid = (lo + hi) / 2
        (lo, hi) = (lo, mid) if ok(mid) else (mid, hi)
    return hi, solve_mooring(MooringConfig(**{**asdict(cfg), "ball_mass": hi}))


def to_dict(r: MooringResult, c: MooringConfig) -> dict:
    return {
        "config": asdict(c),
        "draft_m": round(r.draft, 4),
        "excursion_radius_m": round(r.excursion_radius, 4),
        "barrel_angle_deg": round(r.barrel_angle_deg, 4),
        "pipe_angles_deg_bottom_to_top": [round(a, 4) for a in r.pipe_angles_deg],
        "anchor_angle_deg": round(r.anchor_angle_deg, 4),
        "chain_on_bottom_m": round(r.chain_on_bottom_m, 4),
        "chain_suspended_m": round(r.chain_suspended_m, 4),
        "horizontal_force_N": round(r.horizontal_force_N, 2),
        "converged": r.converged,
    }


def run_all(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    p1 = {f"wind_{v}ms": to_dict(solve_mooring(MooringConfig(wind_speed=float(v))), MooringConfig(wind_speed=float(v))) for v in (12, 24)}
    for k, v in p1.items():
        print(k, json.dumps(v, ensure_ascii=False))

    c36 = MooringConfig(wind_speed=36.0)
    m, ropt = optimize_ball_mass(c36)
    p2 = {"before": to_dict(solve_mooring(c36), c36), "optimal_ball_mass_kg": m, "after": to_dict(ropt, MooringConfig(**{**asdict(c36), "ball_mass": m}))}
    print("p2", json.dumps(p2, ensure_ascii=False))

    designs = []
    for ct in ["III", "IV", "V"]:
        for cl in [26.0, 28.0, 30.0, 32.0]:
            for bm in [4000, 4500, 5000]:
                worst = dict(barrel=0.0, anchor=0.0, excursion=0.0, draft=0.0)
                ok = True
                for d in [16, 18, 20]:
                    for w in [12, 24, 36]:
                        for cur in [0, 0.75, 1.5]:
                            r = solve_mooring(MooringConfig(d, ct, cl, bm, w, cur))
                            if not r.converged or r.barrel_angle_deg > 5 or r.anchor_angle_deg > 16:
                                ok = False
                                break
                            worst["barrel"] = max(worst["barrel"], r.barrel_angle_deg)
                            worst["anchor"] = max(worst["anchor"], r.anchor_angle_deg)
                            worst["excursion"] = max(worst["excursion"], r.excursion_radius)
                            worst["draft"] = max(worst["draft"], r.draft)
                        if not ok:
                            break
                    if not ok:
                        break
                designs.append({"chain_type": ct, "chain_length": cl, "ball_mass": bm, "feasible": ok, "worst": worst})

    feas = sorted([d for d in designs if d["feasible"]], key=lambda z: (z["worst"]["excursion"], z["worst"]["draft"], z["worst"]["barrel"]))
    p3 = {"feasible_count": len(feas), "recommended": feas[0] if feas else None, "top5": feas[:5]}
    if feas:
        rec = feas[0]
        p3["samples"] = []
        for d, w, cur in [(16, 36, 1.5), (18, 36, 1.5), (20, 36, 1.5), (18, 12, 0), (20, 24, 0.75)]:
            c = MooringConfig(d, rec["chain_type"], rec["chain_length"], rec["ball_mass"], w, cur)
            p3["samples"].append({"case": {"depth": d, "wind": w, "current": cur}, "result": to_dict(solve_mooring(c), c)})

    (out / "p1_results.json").write_text(json.dumps(p1, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "p2_results.json").write_text(json.dumps(p2, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "p3_design.json").write_text(json.dumps(p3, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run_all(Path(__file__).resolve().parents[1] / "results")
