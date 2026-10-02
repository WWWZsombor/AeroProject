# src/cda/preprocessing/speed.py
"""
cda.preprocessing.speed
=======================
Ground-speed sources.  On a fixed-gear track bike the wheel speed follows
from the cadence, so it is a second, independent speed measurement:

    v_wheel = cadence / 60 · (chainring / cog) · wheel_circumference     m/s
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger("cda.preprocessing.speed")

REL_DIFF_WARN = 0.02       # warn if the two sources differ by more than 2 %


def wheel_speed(
    cadence_rpm:         np.ndarray | pd.Series,   # crank cadence      rev/min
    gear_ratio:          float,                    # chainring / cog    –
    wheel_circumference: float,                    # rolling circumference  m
) -> np.ndarray:
    """Ground speed from cadence on a fixed gear (m/s)."""
    return (np.asarray(cadence_rpm, dtype=float) / 60.0
            * gear_ratio * wheel_circumference)


def select_speed(
    df:                  pd.DataFrame,
    source:              str,
    gear_ratio:          float,
    wheel_circumference: float,
) -> pd.DataFrame:
    """
    Add the ground-speed columns and set ``v`` (m/s) from the chosen source.

    Adds ``v_sensor`` (= ``speed`` km/h / 3.6), ``v_wheel`` (needs
    ``cadence``) and ``v``:

    * ``sensor`` – ``v = v_sensor``
    * ``wheel``  – ``v = v_wheel``
    * ``both``   – ``v = (v_sensor + v_wheel) / 2``

    A warning is logged when the two sources disagree by more than 2 % on
    average (wrong gear teeth or wheel circumference?).  Pure: returns a copy.
    """
    df = df.copy()
    df["v_sensor"] = df["speed"].to_numpy(dtype=float) / 3.6
    if source == "sensor":
        df["v"] = df["v_sensor"]
        return df

    if "cadence" not in df.columns:
        raise ValueError(f"speed_source '{source}' needs a 'cadence' column")
    df["v_wheel"] = wheel_speed(df["cadence"], gear_ratio, wheel_circumference)

    moving = (df["v_sensor"] > 5.0) & (df["cadence"] > 0)     # riding, pedalling
    if moving.any():
        rel = float((df.loc[moving, "v_wheel"] / df.loc[moving, "v_sensor"]).mean() - 1.0)
        log.info("speed sources: mean(v_wheel / v_sensor) − 1 = %+.2f %%", 100 * rel)
        if abs(rel) > REL_DIFF_WARN:
            log.warning("wheel speed differs from sensor speed by %+.1f %% – "
                        "check velodrome.chainring_teeth / cog_teeth and "
                        "cyclist.wheel_circumference", 100 * rel)

    df["v"] = df["v_wheel"] if source == "wheel" else 0.5 * (df["v_sensor"] + df["v_wheel"])
    return df
