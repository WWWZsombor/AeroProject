# src/cda/physics/equations.py
"""
Assemble the full power-balance system.

    P_measured
      = P_aero        + P_rolling      + P_kinetic          + P_potential
      = ½ρ·CdA·v_r²·v + c_rr·m·g·cosθ·v + d/dt(½m_eff·v²)   + m·g·dh/dt

``P_potential`` (from the altitude trace) and ``P_gravity`` (= m·g·sinθ·v,
from the incline) describe the SAME physical effect.  Only one may be
subtracted from the measured power, otherwise the climb is counted twice;
the balance uses ``P_potential`` and keeps ``P_gravity`` as a cross-check.

The **unknown** is CdA (and optionally c_rr).
This module prepares the *known* side of the equation for a future solver.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..cyclist.cyclist import Cyclist
from .constants  import G
from .forces     import drag_force, rolling_force, gravity_force
from .energy     import kinetic_power, potential_power


def assemble_power_balance(
    df:        pd.DataFrame,
    cyclist:   Cyclist,
    dt:        float = 1.0,
    cda_guess: float = 0.35,
) -> pd.DataFrame:
    """
    Return a **new** DataFrame with one column per power component
    plus a residual column that a future solver will fit.

    Required input columns (must exist in *df*):
        v           – ground speed         m/s
        power       – measured pedal power W
        v_wind      – headwind component   m/s  (headwind +, tailwind −)
                      ``v_rel = v + v_wind``  (same convention as
                      ``preprocess_segment``)
        incline_rad – road incline         rad
        altitude    – elevation            m
        density     – air density          kg/m³

    Added output columns:
        F_drag        N
        F_rolling     N   (× ``load_factor`` if present)
        F_gravity     N
        P_aero        W
        P_rolling     W
        P_gravity     W   (cross-check of P_potential, not subtracted)
        P_kinetic     W   (reuses ``power_kinetic``   if present)
        P_potential   W   (reuses ``power_potential`` if present)
        P_residual    W   (= power − P_kin − P_pot − P_rolling)
        P_aero_model  W   (using cda_guess, for sanity checking)
    """
    df = df.copy()

    v      = df["v"].to_numpy()
    power  = df["power"].to_numpy()
    v_wind = df["v_wind"].to_numpy()
    theta  = df["incline_rad"].to_numpy()
    rho    = df["density"].to_numpy()

     # relative air speed  (headwind adds, tailwind subtracts)
    v_rel = v + v_wind

     # ── forces ────────────────────────────────────────────────────
    df["F_drag"]    = drag_force(rho, cda_guess, v_rel)
    # bend correction: tyre load grows with the centripetal acceleration
    # (``load_factor`` from preprocessing.bends; 1 on the straights / if absent)
    load = df["load_factor"].to_numpy() if "load_factor" in df.columns else 1.0
    df["F_rolling"] = load * rolling_force(cyclist.c_rr, cyclist.total_mass, G, theta)
    df["F_gravity"] = gravity_force(cyclist.total_mass, G, theta)

     # ── powers ────────────────────────────────────────────────────
    df["P_aero"]      = df["F_drag"] * v                    # W
    df["P_rolling"]   = df["F_rolling"] * v                 # W
    df["P_gravity"]   = df["F_gravity"] * v                 # W
    if "power_kinetic" in df.columns:        # smoothed, from preprocessing
        df["P_kinetic"] = df["power_kinetic"]
    else:
        df["P_kinetic"] = kinetic_power(cyclist.effective_mass, v, dt)
    if "power_potential" in df.columns:
        df["P_potential"] = df["power_potential"]
    else:
        alt = (df["altitude"].to_numpy() if "altitude" in df.columns
               else np.zeros(len(df)))
        df["P_potential"] = potential_power(cyclist.total_mass, G, alt, dt)

     # ── residual  (what a solver will match against P_aero) ───────
    df["P_residual"] = (
        power
        - df["P_kinetic"].to_numpy()
        - df["P_potential"].to_numpy()
        - df["P_rolling"].to_numpy()
    )

     # sanity check: predicted aero power with the guess value
    df["P_aero_model"] = 0.5 * rho * cda_guess * v_rel ** 2 * v

    return df
