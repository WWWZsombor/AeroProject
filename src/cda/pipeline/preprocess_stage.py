# src/cda/pipeline/preprocess_stage.py
"""
cda.pipeline.preprocess_stage
=============================
Stage 2 for ONE test (= one setup): speed source → per-setup airspeed
calibration → per-segment preprocessing → straight/bend flags, once for each
wind run.

Runs (one full set of preprocessed segments per run):

* velodrome : ``velodrome.wind_runs``  (``no_wind`` and/or ``with_wind``)
* field     : ``with_wind`` if ``field.wind_source == airspeed``, else ``no_wind``
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..cyclist.cyclist import Cyclist
from ..preprocessing import (
    AirspeedCalibration,
    flag_bends,
    preprocess_segment,
    resolve_airspeed_calibration,
    select_speed,
    straight_mask,
)
from .config_loader import AppConfig

log = logging.getLogger("cda.pipeline")


def wind_runs(cfg: AppConfig) -> tuple[str, ...]:
    """Names of the wind runs to produce for the configured mode."""
    if cfg.mode == "velodrome":
        return tuple(cfg.velodrome.wind_runs)
    return ("with_wind",) if cfg.field.wind_source == "airspeed" else ("no_wind",)


def _speed_args(cfg: AppConfig, cyclist: Cyclist) -> dict:
    if cfg.mode == "velodrome":
        return dict(source=cfg.velodrome.speed_source,
                    gear_ratio=cfg.velodrome.gear_ratio,
                    wheel_circumference=cyclist.wheel_circumference)
    return dict(source="sensor", gear_ratio=1.0,
                wheel_circumference=cyclist.wheel_circumference)


def _fs(df: pd.DataFrame) -> float:
    dt = df["SECS"].diff().median()
    return 1.0 / dt if dt and dt > 0 else 1.0


def _straights(df: pd.DataFrame, cfg: AppConfig, fs: float):
    """Straight-sample mask for the calibration fit (velodrome only)."""
    return straight_mask(df, cfg.velodrome, fs) if cfg.mode == "velodrome" else None


def preprocess_test(
    test_id:  str,
    seg_dfs:  list[pd.DataFrame],
    full_df:  pd.DataFrame,
    cfg:      AppConfig,
    cyclist:  Cyclist,
) -> tuple[dict[str, pd.DataFrame], list[AirspeedCalibration]]:
    """
    Returns ``({run: preprocessed frame of all segments}, [calibrations])``.

    *full_df* is the whole ride (needed for the per-setup calibration with
    ``scope: test``); *seg_dfs* are the selected segments.  The calibration
    list holds one entry (scope ``test``) or one per segment (``segment``).
    """
    speed = _speed_args(cfg, cyclist)
    acfg  = cfg.airspeed_calibration
    pcfg  = cfg.preprocessing

    segs = [select_speed(s, **speed) for s in seg_dfs]

    # ── per-setup airspeed calibration ───────────────────────────────
    if acfg.scope == "test":
        full = select_speed(full_df, **speed)
        fs   = _fs(full)
        cal  = resolve_airspeed_calibration(
            full, acfg, test_id, fs, _straights(full, cfg, fs),
            cut_env=pcfg.butter_cutoff_env, order=pcfg.butter_order,
        )
        cals = [cal]
        seg_cals = [cal] * len(segs)
    else:
        cals = []
        for idx, seg in enumerate(segs):
            fs = _fs(seg)
            cals.append(resolve_airspeed_calibration(
                seg, acfg, test_id, fs, _straights(seg, cfg, fs),
                label=f"{test_id}/seg{idx}",
                cut_env=pcfg.butter_cutoff_env, order=pcfg.butter_order,
            ))
        seg_cals = cals

    # ── per-run, per-segment preprocessing ───────────────────────────
    out: dict[str, pd.DataFrame] = {}
    for run in wind_runs(cfg):
        frames = []
        for idx, (seg, cal) in enumerate(zip(segs, seg_cals)):
            fs = _fs(seg)
            df = preprocess_segment(
                seg, cyclist, dt=1.0 / fs, cfg=pcfg,
                calibration=cal, wind_enabled=(run == "with_wind"),
            )
            if cfg.mode == "velodrome":
                df = flag_bends(df, cfg.velodrome, fs)
            else:
                df["valid"], df["load_factor"] = True, 1.0
            df.insert(0, "segment", idx)
            frames.append(df)
        out[run] = pd.concat(frames, ignore_index=True)
        v = out[run]
        log.info("  %s  run=%-9s segments=%d rows=%d valid=%.0f%%  mean v_wind=%+.3f m/s",
                 test_id, run, len(frames), len(v), 100 * v["valid"].mean(),
                 v["v_wind"].mean())
    return out, cals
