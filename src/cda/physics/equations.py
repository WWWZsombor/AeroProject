# src/cda/physics/equations.py
"""
Assemble the full power-balance system.

    P_measured
      = P_aero       + P_rolling + P_gravity + P_kinetic + P_potential
      = ½ρ·CdA·v_r²·v + c_rr·m·g·cosθ·v + m·g·sinθ·v
        + d/dt(½m_eff·v²) + m·g·dh/dt

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
        v_wind      – wind speed           m/s  (headwind +, tailwind −)
        incline_rad – road incline         rad
        altitude    – elevation            m
        density     – air density          kg/m³

    Added output columns:
        F_drag        N
        F_rolling     N
        F_gravity     N
        P_aero        W
        P_rolling     W
        P_gravity     W
        P_kinetic     W
        P_potential   W
        P_residual    W   (= power − P_kin − P_pot − P_rolling − P_gravity)
        P_aero_model  W   (using cda_guess, for sanity checking)
    """
    df = df.copy()

    v      = df["v"].to_numpy()
    power  = df["power"].to_numpy()
    v_wind = df["v_wind"].to_numpy()
    theta  = df["incline_rad"].to_numpy()
    alt    = df.get("altitude", pd.Series(np.zeros(len(df)))).to_numpy()
    rho    = df["density"].to_numpy()

     # relative air speed  (headwind adds, tailwind subtracts)
    v_rel = v + v_wind

     # ── forces ────────────────────────────────────────────────────
    df["F_drag"]    = drag_force(rho, cda_guess, v_rel)
    df["F_rolling"] = rolling_force(cyclist.c_rr, cyclist.total_mass, G, theta)
    df["F_gravity"] = gravity_force(cyclist.total_mass, G, theta)

     # ── powers ────────────────────────────────────────────────────
    df["P_aero"]      = df["F_drag"] * v                    # W
    df["P_rolling"]   = df["F_rolling"] * v                 # W
    df["P_gravity"]   = df["F_gravity"] * v                 # W
    df["P_kinetic"]   = kinetic_power(cyclist.effective_mass, v, dt)
    df["P_potential"] = potential_power(cyclist.total_mass,  G, alt, dt)

     # ── residual  (what a solver will match against P_aero) ───────
    df["P_residual"] = (
        power
        - df["P_kinetic"].to_numpy()
        - df["P_potential"].to_numpy()
        - df["P_rolling"].to_numpy()
        - df["P_gravity"].to_numpy()
    )

     # sanity check: predicted aero power with the guess value
    df["P_aero_model"] = 0.5 * rho * cda_guess * v_rel ** 2 * v

    return df
