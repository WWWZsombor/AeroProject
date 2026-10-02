# src/cda/preprocessing/bends.py
"""
cda.preprocessing.bends
=======================
Straight / bend classification for velodrome rides from the yaw rate.

In a bend the yaw rate ω is v / R, and the rider/bike is loaded by the
centripetal acceleration a_c = v · ω.  That loads the tyres more than on
the straights and puts the rider in a lean (different yaw/lean → different
CdA), so by default the solvers only use the straights.

Columns added by :func:`flag_bends`:

    yaw_rate_dps      smoothed signed yaw rate                   deg/s
    is_bend           |yaw rate| > threshold
    lateral_accel_g   v · ω / g                                  –
    load_factor       sqrt(1 + (a_c / g)²)  – tyre-load factor; used to scale
                      the rolling resistance when ``bend_handling: correct``,
                      1.0 otherwise
    valid             sample may be used by the solvers
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..physics.constants import G

log = logging.getLogger("cda.preprocessing.bends")


def detect_bends(
    yaw_rate_dps:    np.ndarray | pd.Series,
    fs:              float,
    threshold_dps:   float,
    smoothing_sec:   float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return ``(yaw_smoothed_dps, is_bend)``.  The yaw rate is smoothed with a
    centred moving average of *smoothing_sec*; a sample is a bend when the
    absolute smoothed value exceeds *threshold_dps*.
    """
    win = max(1, int(round(smoothing_sec * fs)))
    yaw = (pd.Series(np.asarray(yaw_rate_dps, dtype=float))
           .rolling(win, center=True, min_periods=1).mean().to_numpy())
    return yaw, np.abs(yaw) > threshold_dps


def _drop_short_runs(ok: np.ndarray, min_len: int) -> np.ndarray:
    """Set to False every run of True shorter than *min_len* samples."""
    ok = ok.copy()
    i, n = 0, len(ok)
    while i < n:
        if ok[i]:
            j = i
            while j < n and ok[j]:
                j += 1
            if j - i < min_len:
                ok[i:j] = False
            i = j
        else:
            i += 1
    return ok


def flag_bends(
    df:    pd.DataFrame,
    cfg,                                   # VelodromeCfg
    fs:    float,
) -> pd.DataFrame:
    """
    Classify every sample of one frame as straight or bend and add the
    columns listed in the module docstring.  Pure: returns a copy.

    ``cfg.bend_handling``:

    * ``exclude`` – bends and straights shorter than ``min_straight_sec``
      are marked ``valid = False``
    * ``correct`` – every sample stays valid; ``load_factor`` scales the
      rolling resistance in the power balance
    * ``keep``    – every sample stays valid, no correction

    Without a yaw-rate column the whole frame is treated as straight.
    """
    df = df.copy()
    n = len(df)
    if cfg.yaw_rate_column not in df.columns:
        log.warning("no '%s' column – treating the whole ride as straight",
                    cfg.yaw_rate_column)
        yaw, bend = np.zeros(n), np.zeros(n, dtype=bool)
    else:
        yaw, bend = detect_bends(df[cfg.yaw_rate_column], fs,
                                 cfg.yaw_rate_threshold_dps, cfg.yaw_smoothing_sec)

    v = df["velocity_smoothed"] if "velocity_smoothed" in df.columns else df["v"]
    a_c = v.to_numpy(dtype=float) * np.deg2rad(yaw)          # m/s²
    df["yaw_rate_dps"]     = yaw
    df["is_bend"]          = bend
    df["lateral_accel_g"]  = a_c / G
    corrected = cfg.bend_handling == "correct"
    df["load_factor"] = np.sqrt(1.0 + (a_c / G) ** 2) if corrected else 1.0

    if cfg.bend_handling == "exclude":
        valid = _drop_short_runs(~bend, int(round(cfg.min_straight_sec * fs)))
    else:
        valid = np.ones(n, dtype=bool)
    df["valid"] = valid
    return df


def straight_mask(df: pd.DataFrame, cfg, fs: float) -> np.ndarray:
    """Boolean mask of straight samples (not a bend) for the calibration fit."""
    if cfg.yaw_rate_column not in df.columns:
        return np.ones(len(df), dtype=bool)
    _, bend = detect_bends(df[cfg.yaw_rate_column], fs,
                           cfg.yaw_rate_threshold_dps, cfg.yaw_smoothing_sec)
    return ~bend
