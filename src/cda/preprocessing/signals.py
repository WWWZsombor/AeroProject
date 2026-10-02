# src/cda/preprocessing/signals.py
"""
cda.preprocessing.signals
=========================
Small signal helpers shared by the segment preprocessing and the airspeed
calibration, so both derive the air state in exactly the same way.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

from ..physics.air_density import calculate_air_density


# ── Butterworth helper ───────────────────────────────────────────────

def _butter(
    data:    np.ndarray | pd.Series,
    cutoff:  float = 0.01,     # cut-off frequency  Hz
    order:   int   = 1,
    fs:      float = 1.0,      # sampling rate      Hz
) -> np.ndarray:
    """
    Zero-phase Butterworth low-pass filter.

    *cutoff* is a frequency in Hz (it must stay below the Nyquist
    frequency ``fs / 2``; larger values are clipped just below it).
    Falls back to the original signal if it is too short.
    """
    arr = np.asarray(data, dtype=np.float64)
    n   = len(arr)
    nyq = fs / 2.0

     # guard: need at least (order+1) samples for filtfilt
    if n <= 2 * order + 1:
        return arr

    wn = float(np.clip(cutoff, 1e-6, 0.999 * nyq))
    b, a = butter(order, wn, btype="low", fs=fs)
    # Odd-extension padding as long as the filter's time constant (capped
    # by the data length) so that slow trends such as a linear altitude
    # ramp are not distorted at the segment edges.
    padlen = min(n - 1, int(round(fs / wn)))
    return filtfilt(b, a, arr, padlen=padlen)


# ── air state ────────────────────────────────────────────────────────

def air_state(
    df:      pd.DataFrame,
    fs:      float,
    cut_env: float = 0.10,
    order:   int   = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Air density and *uncalibrated* pitot airspeed of one frame.

    Needs ``temperature`` (°C), ``pressure`` (Pa, static) and ``dyn_press``
    (RideData ``airpressure``, units of 0.01 Pa).  ``humidity`` (%) is
    optional (50 % if missing).

        ρ         = humidity-corrected air density           kg/m³
        v_air_raw = sqrt(2 · dyn_press / 100 / ρ)            m/s

    Negative dynamic pressure (sensor zero noise) is clipped to 0.
    Temperature and static pressure are low-passed at *cut_env* (Hz).
    """
    temp = _butter(df["temperature"], cutoff=cut_env, order=order, fs=fs)
    pres = _butter(df["pressure"],    cutoff=cut_env, order=order, fs=fs)
    hum  = (df["humidity"].to_numpy(dtype=float) if "humidity" in df.columns
            else np.full(len(df), 50.0))
    rho  = calculate_air_density(temp, pres, hum)
    if "dyn_press" in df.columns:
        dp = np.clip(df["dyn_press"].to_numpy(dtype=float), 0.0, None)
        v_air_raw = np.sqrt(2.0 * dp / 100.0 / np.clip(rho, 0.1, None))
    else:
        v_air_raw = np.full(len(df), np.nan)
    return rho, v_air_raw
