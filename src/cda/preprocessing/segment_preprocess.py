# src/cda/preprocessing/segment_preprocess.py
"""
cda.preprocessing.segment_preprocess
====================================
Take a raw concatenated segment DataFrame and produce a clean,
solver-ready DataFrame with:

  • smoothed velocity / power / incline
  • humidity-corrected air density
  • airspeed from dynamic pressure
  • estimated wind
  • kinetic + potential power columns

The function is **pure**: it returns a new DataFrame;
it never mutates the caller's copy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

from ..cyclist.cyclist import Cyclist
from ..physics.constants import G
from ..physics.energy    import kinetic_power, potential_power
from ..physics.air_density import calculate_air_density


# ── Butterworth helper ───────────────────────────────────────────────

def _butter(
    data:    np.ndarray | pd.Series,
    cutoff:  float = 0.01,     # normalised 0-1  (1 = Nyquist)
    order:   int   = 1,
    fs:      float = 1.0,      # sampling rate  Hz
) -> np.ndarray:
    """
    Zero-phase Butterworth low-pass filter.
    Falls back to the original signal if it is too short.
    """
    arr = np.asarray(data, dtype=np.float64)
    n   = len(arr)
    nyq = fs / 2.0

     # guard: need at least (order+1) samples for filtfilt
    if n <= 2 * order + 1:
        return arr

    wn = np.clip(cutoff, 1e-6, 0.999)
    b, a = butter(order, wn, btype="low", fs=fs)
    return filtfilt(b, a, arr)


# ── main entry point ─────────────────────────────────────────────────

def preprocess_segment(
    df:          pd.DataFrame,
    cyclist:     Cyclist,
    dt:          float    = 1.0,
    cfg:         "PreprocCfg" | None = None,
) -> pd.DataFrame:
    """
    Clean a concatenated multi-segment DataFrame and add all derived
    columns needed by the physics / solver layer.

    Parameters
    ----------
    df      : raw DataFrame from ``group_and_merge``.
    cyclist : the Cyclist dataclass.
    dt      : mean time step (s).  Auto-estimated from ``SECS`` if ≤ 0.
    cfg     : optional ``PreprocCfg`` for Butterworth parameters.
              If *None*, sensible defaults are used.

    Returns
    -------
    pd.DataFrame  – new, with smoothed + derived columns.
    """
    df = df.copy().reset_index(drop=True)
    fs = 1.0 / dt if dt > 0 else 1.0

     # pull cutoffs from cfg or use defaults
    cut_v   = 0.01
    cut_p   = 0.01
    cut_inc = 0.20
    cut_env = 0.10
    cut_as  = 0.01
    b_order = 1
    if cfg is not None:
        cut_v   = getattr(cfg, "butter_cutoff_velocity",  0.01)
        cut_p   = getattr(cfg, "butter_cutoff_power",     0.01)
        cut_inc = getattr(cfg, "butter_cutoff_incline",   0.20)
        cut_env = getattr(cfg, "butter_cutoff_env",       0.10)
        cut_as  = getattr(cfg, "butter_cutoff_airspeed",  0.01)
        b_order = getattr(cfg, "butter_order",            1)

     # ── 1  velocity (km/h → m/s, then smooth) ─────────────────────
    if "v" not in df.columns:
        df["v"] = df["speed"].to_numpy() / 3.6       # km/h → m/s
    if "velocity_smoothed" not in df.columns:
        df["velocity_smoothed"] = _butter(df["v"], cutoff=cut_v,
                                          order=b_order, fs=fs)

     # ── 2  power (smooth) ─────────────────────────────────────────
    if "power_smoothed" not in df.columns:
        df["power_smoothed"] = _butter(df["power"], cutoff=cut_p,
                                       order=b_order, fs=fs)

     # ── 3  kinetic + potential energy powers ──────────────────────
    if "power_kinetic" not in df.columns:
        df["power_kinetic"] = kinetic_power(
            cyclist.effective_mass,
            df["velocity_smoothed"].to_numpy(),
            dt,
        )

    if "power_potential" not in df.columns:
        if "altitude" in df.columns:
            alt_sm = _butter(df["altitude"], cutoff=cut_v,
                             order=b_order, fs=fs)
        else:
            alt_sm = np.zeros(len(df))
        df["power_potential"] = potential_power(
            cyclist.total_mass, G, alt_sm, dt
        )

     # ── 4  incline ────────────────────────────────────────────────
    if "incline_angle" not in df.columns:
        df["incline_angle"] = 0.0
    df["incline_angle"] = _butter(
        df["incline_angle"], cutoff=cut_inc, order=2, fs=fs
    )
    if "incline_rad" not in df.columns:
        df["incline_rad"] = np.deg2rad(df["incline_angle"])

     # ── 5  air density (humidity-corrected) ───────────────────────
    if "temperature" in df.columns:
        df["temperature"] = _butter(df["temperature"],
                                    cutoff=cut_env, order=b_order, fs=fs)
    if "pressure" not in df.columns and "airpressure" in df.columns:
        df["pressure"] = df["airpressure"]
    if "pressure" in df.columns:
        df["pressure"] = _butter(df["pressure"],
                                 cutoff=cut_env, order=b_order, fs=fs)

    if "humidity" in df.columns:
        df["relative_humidity"] = df["humidity"]
    elif "relative_humidity" not in df.columns:
        df["relative_humidity"] = 50.0

    if "density" not in df.columns:
        df["density"] = calculate_air_density(
            df["temperature"].to_numpy(),
            df["pressure"].to_numpy(),
            df["relative_humidity"].to_numpy(),
        )

     # ── 6  airspeed from dynamic pressure ─────────────────────────
    if "airspeed_filtered" not in df.columns:
        if "dyn_press" in df.columns:
            rho_safe = df["density"].clip(lower=0.1).to_numpy()
            df["airspeed_from_pressure"] = (
                np.sqrt(2.0 * df["dyn_press"].to_numpy() / 100.0 / rho_safe)
            )
            df["airspeed_filtered"] = _butter(
                df["airspeed_from_pressure"],
                cutoff=cut_as, order=b_order, fs=fs,
            )
        else:
            df["airspeed_filtered"] = df["velocity_smoothed"].copy()

     # ── 7  wind estimate ──────────────────────────────────────────
    if "wind_estimated" not in df.columns:
        df["wind_estimated"] = (
            df["airspeed_filtered"] - df["velocity_smoothed"]
        )
    if "v_wind" not in df.columns:
        df["v_wind"] = df.get(
            "wind",
            df.get("wind_estimated", pd.Series(np.zeros(len(df)))),
        )
    df["v_wind"] = df["v_wind"].fillna(0.0)

    return df
