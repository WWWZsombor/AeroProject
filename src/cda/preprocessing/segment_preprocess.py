# src/cda/preprocessing/segment_preprocess.py
"""
cda.preprocessing.segment_preprocess
====================================
Take ONE segment DataFrame (4 Hz, gap-free, from ``combined`` CSV) and
produce a clean, solver-ready DataFrame with:

  • smoothed velocity / power / incline
  • humidity-corrected air density
  • airspeed from dynamic pressure
  • estimated wind  (headwind component, + = headwind)
  • kinetic + potential power columns

The function is **pure**: it returns a new DataFrame;
it never mutates the caller's copy.

Call it once per segment: filtering and differentiating across the time
gap between two segments would create artefacts.

Conventions
-----------
* ``speed``  is BCVX ground speed in km/h  → converted once to ``v`` (m/s).
* ``dyn_press`` is the RideData ``airpressure`` channel: dynamic pressure
  in units of 0.01 Pa (hence the ``/ 100`` below).
* The pitot airspeed is calibrated per setup:
  ``v_air = scale · v_air_raw + offset`` (see ``airspeed_calibration``).
* ``v_wind`` = ``airspeed − ground speed`` = headwind component (m/s),
  positive for a headwind.  The relative air speed is ``v + v_wind``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..cyclist.cyclist import Cyclist
from ..physics.constants import G
from ..physics.energy    import kinetic_power, potential_power
from .airspeed_calibration import AirspeedCalibration
from .signals import _butter, air_state


# ── main entry point ─────────────────────────────────────────────────

def preprocess_segment(
    df:          pd.DataFrame,
    cyclist:     Cyclist,
    dt:          float    = 1.0,
    cfg:         "PreprocCfg" | None = None,
    calibration: "AirspeedCalibration" | None = None,
    wind_enabled: bool    = True,
) -> pd.DataFrame:
    """
    Clean a concatenated multi-segment DataFrame and add all derived
    columns needed by the physics / solver layer.

    Parameters
    ----------
    df      : ONE segment from ``load_segments`` (needs ``speed`` km/h,
              ``power``; optional ``altitude``, ``temperature``,
              ``pressure``, ``humidity``, ``dyn_press``).
    cyclist : the Cyclist dataclass.
    dt      : time step (s).  Auto-estimated from ``SECS`` if ≤ 0.
    cfg     : optional ``PreprocCfg`` for Butterworth parameters.
              If *None*, sensible defaults are used.
    calibration : airspeed calibration of THIS setup (scale / offset);
              identity if *None*.
    wind_enabled : if False, ``v_wind`` is forced to 0 (no-wind run).

    Returns
    -------
    pd.DataFrame  – new, with smoothed + derived columns.
    """
    df = df.copy().reset_index(drop=True)
    if dt <= 0:
        dt = float(df["SECS"].diff().median())
    fs = 1.0 / dt

     # pull cutoffs (Hz) from cfg or use defaults
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

     # ── 5  air density (humidity-corrected) + raw pitot airspeed ──
    rho, v_air_raw = air_state(df, fs, cut_env=cut_env, order=b_order)
    df["temperature"] = _butter(df["temperature"], cutoff=cut_env,
                                order=b_order, fs=fs)
    df["pressure"]    = _butter(df["pressure"], cutoff=cut_env,
                                order=b_order, fs=fs)
    if "humidity" in df.columns:
        df["relative_humidity"] = df["humidity"]
    elif "relative_humidity" not in df.columns:
        df["relative_humidity"] = 50.0
    df["density"] = rho

     # ── 6  airspeed: calibrate, then low-pass ─────────────────────
     #    v_air = scale · v_air_raw + offset   (per setup, see
     #    ``airspeed_calibration``); identity if no calibration is given.
    if "dyn_press" in df.columns:
        cal = calibration if calibration is not None else AirspeedCalibration()
        df["airspeed_raw"]          = v_air_raw
        df["airspeed_from_pressure"] = cal.apply(v_air_raw)
        df["airspeed_filtered"] = _butter(
            df["airspeed_from_pressure"], cutoff=cut_as, order=b_order, fs=fs,
        )
    else:
        df["airspeed_filtered"] = df["velocity_smoothed"].copy()

     # ── 7  wind estimate (headwind component, + = headwind) ───────
     # Derived from the calibrated airspeed sensor; device-computed wind
     # columns are ignored.  ``wind_enabled=False`` (the velodrome
     # "no_wind" run) forces v_wind = 0.
    df["wind_estimated"] = df["airspeed_filtered"] - df["velocity_smoothed"]
    if wind_enabled:
        df["v_wind"] = df["wind_estimated"].fillna(0.0)
    else:
        df["v_wind"] = 0.0

    return df
