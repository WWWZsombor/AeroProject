# src/cda/preprocessing/airspeed_calibration.py
"""
cda.preprocessing.airspeed_calibration
======================================
Per-setup calibration of the pitot airspeed against ground speed.

Why per setup: the flow around the sensor changes with the rider position
and the equipment, so the sensor gain is different for every setup.  One
setup = one measurement file (``test_id``); the calibration is therefore
fitted separately for each file (or for each segment, ``scope: segment``).

Model
-----
    v_air = scale · v_air_raw + offset

fitted by least squares so that, on **steady straights**, the calibrated
airspeed equals the ground speed (no-wind assumption: velodrome, or a loop /
out-and-back field ride whose mean wind is ≈ 0).  After the fit the mean
``v_wind = v_air − v`` is ≈ 0 and only the *fluctuating* part of the wind
remains, which is what the "with wind" run uses.

``fit: scale`` (default) fits ``offset = 0``.  ``fit: scale_offset`` also fits
the offset, but only if the steady speed range is wide enough
(``min_range``); otherwise scale and offset cannot be separated and the fit
falls back to scale only.

Manual values per setup (``overrides:`` in the YAML) always win over the fit.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .signals import _butter, air_state

log = logging.getLogger("cda.preprocessing.airspeed_calibration")


@dataclass(frozen=True)
class AirspeedCalibration:
    """Calibration of one setup:  ``v_air = scale · v_air_raw + offset``."""
    scale:       float = 1.0
    offset:      float = 0.0          # m/s
    setup:       str   = ""           # test_id (+ "/seg<i>" for scope: segment)
    method:      str   = "identity"   # identity | fit | override | fit-failed
    fit:         str   = ""           # scale | scale_offset (when method == fit)
    n_points:    int   = 0
    rmse_before: float = float("nan")  # m/s, |v_air_raw − v| on the fit points
    rmse_after:  float = float("nan")  # m/s, |v_air_cal − v|

    def apply(self, v_air_raw: np.ndarray) -> np.ndarray:
        """Calibrated airspeed (m/s)."""
        return self.scale * np.asarray(v_air_raw, dtype=float) + self.offset

    def to_dict(self) -> dict:
        return asdict(self)


def fit_airspeed_calibration(
    df:       pd.DataFrame,
    cfg,                                   # AirspeedCalibrationCfg
    setup:    str,
    fs:       float,
    straight: np.ndarray | None = None,    # bool mask; None = all samples
    cut_env:  float = 0.10,
    order:    int   = 1,
) -> AirspeedCalibration:
    """
    Fit the calibration of one setup from a frame with ``v`` (m/s, ground
    speed), ``dyn_press``, ``temperature``, ``pressure`` [, ``humidity``].

    Both signals are low-passed identically (``cfg.smoothing_hz``); only
    samples that are fast (``min_speed``), steady (``|dv/dt| ≤ max_accel``)
    and on a straight are used.  If too few samples qualify, a warning is
    logged and the identity calibration is returned (method ``fit-failed``).
    """
    _, v_raw = air_state(df, fs, cut_env=cut_env, order=order)
    v_ref    = df["v"].to_numpy(dtype=float)
    v_ref_s  = _butter(v_ref, cutoff=cfg.smoothing_hz, order=order, fs=fs)
    v_raw_s  = _butter(v_raw, cutoff=cfg.smoothing_hz, order=order, fs=fs)
    accel    = np.gradient(v_ref_s, 1.0 / fs)

    mask = (
        np.isfinite(v_raw_s) & np.isfinite(v_ref_s)
        & (v_ref_s > cfg.min_speed) & (np.abs(accel) <= cfg.max_accel)
    )
    if straight is not None:
        mask &= np.asarray(straight, dtype=bool)

    n = int(mask.sum())
    if n < cfg.min_points:
        log.warning("airspeed calibration [%s]: only %d usable samples "
                    "(need %d) – using identity", setup, n, cfg.min_points)
        return AirspeedCalibration(setup=setup, method="fit-failed", n_points=n)

    x, y = v_raw_s[mask], v_ref_s[mask]
    fit = cfg.fit
    if fit == "scale_offset":
        lo, hi = np.percentile(x, [5, 95])
        if hi - lo < cfg.min_range:
            log.warning("airspeed calibration [%s]: steady speed range %.2f m/s "
                        "< min_range %.2f – offset not identifiable, fitting scale only",
                        setup, hi - lo, cfg.min_range)
            fit = "scale"
    if fit == "scale_offset":
        scale, offset = np.polyfit(x, y, 1)
    else:
        scale, offset = float(np.dot(x, y) / np.dot(x, x)), 0.0

    cal = AirspeedCalibration(
        scale=float(scale), offset=float(offset), setup=setup, method="fit",
        fit=fit, n_points=n,
        rmse_before=float(np.sqrt(np.mean((x - y) ** 2))),
        rmse_after=float(np.sqrt(np.mean((scale * x + offset - y) ** 2))),
    )
    log.info("airspeed calibration [%s]: scale=%.4f offset=%+.3f m/s "
             "(n=%d, rmse %.3f → %.3f m/s)", setup, cal.scale, cal.offset,
             n, cal.rmse_before, cal.rmse_after)
    return cal


def resolve_airspeed_calibration(
    df:       pd.DataFrame,
    cfg,                                   # AirspeedCalibrationCfg
    test_id:  str,
    fs:       float,
    straight: np.ndarray | None = None,
    label:    str | None = None,
    cut_env:  float = 0.10,
    order:    int   = 1,
) -> AirspeedCalibration:
    """
    Calibration for one setup, by priority:
    1. manual ``overrides[test_id]``  →  method ``override``
    2. ``method: auto``               →  least-squares fit
    3. ``method: none``               →  identity
    """
    label = label or test_id
    if test_id in cfg.overrides:
        o = cfg.overrides[test_id]
        cal = AirspeedCalibration(scale=float(o.get("scale", 1.0)),
                                  offset=float(o.get("offset", 0.0)),
                                  setup=label, method="override")
        log.info("airspeed calibration [%s]: manual override scale=%.4f offset=%+.3f",
                 label, cal.scale, cal.offset)
        return cal
    if cfg.method == "none":
        return AirspeedCalibration(setup=label, method="identity")
    return fit_airspeed_calibration(df, cfg, label, fs, straight, cut_env, order)
