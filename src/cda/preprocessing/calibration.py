"""
cda.preprocessing.calibration
=============================
Signal cleaning that happens **before** segment selection.
Each function is *pure*: DataFrame in → DataFrame out.
"""

from __future__ import annotations

import pandas as pd


# ── altitude correction ──────────────────────────────────────────────

def correct_altitude(
    bcvx_df: pd.DataFrame,
    zero_offset: float = 0.0,
) -> pd.DataFrame:
    """
    Remove a slow-drifting median offset from the altitude channel.
    Pure: returns a new DataFrame, never mutates the caller's copy.
    """
    bcvx_df = bcvx_df.copy()
    bcvx_df["altitude"] = bcvx_df["altitude"] - _median_offset(bcvx_df, zero_offset)
    return bcvx_df


def _median_offset(df: pd.DataFrame, zero_offset: float = 0.0, n_points: int = 20) -> pd.DataFrame:
    """
    Corrects altitude drift in cycling data using start/end medians and applies zero-offset shift.
    Ensures constant altitude when KM is not changing.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ['SECS','KM','altitude']
    zero_offset : float, optional
        Reference altitude value. The starting altitude is shifted to this level.
        Example: if first altitude is 105 and zero_offset=100,
                 all values are shifted down by 5.
    n_points : int, optional
        Number of points to use for computing start/end median altitudes.
        Default is 20.

    Returns
    -------
    df : pd.DataFrame
        With new column 'corrected_altitude'
    """
    df = df.copy()

    secs = df["SECS"].to_numpy()
    km = df["KM"].to_numpy()
    alt = df["altitude"].to_numpy()

    # --- Step 1: Apply zero offset shift ---
    shift = alt[0] - zero_offset
    alt = alt - shift   # now starting altitude equals zero_offset

    # --- Step 2: Ensure KM actually changes ---
    start_idx = 0
    end_idx = len(km) - 1
    if km[end_idx] == km[start_idx]:
        # No movement -> just apply offset
        df["corrected_altitude"] = alt
        return df

    # --- Step 3: Use median of first/last n_points for drift correction ---
    alt_start = np.median(alt[start_idx:start_idx+n_points])
    alt_end = np.median(alt[end_idx-n_points+1:end_idx+1])

    drift = alt_end - alt_start
    km_range = km[end_idx] - km[start_idx]
    correction = (km - km[start_idx]) / km_range * drift

    corrected_alt = alt - correction

    # --- Step 4: Handle stops (flat KM, but SECS increasing) ---
    corrected_alt_final = corrected_alt.copy()
    for i in range(1, len(corrected_alt_final)):
        if km[i] == km[i-1]:
            corrected_alt_final[i] = corrected_alt_final[i-1]

    # --- Step 5: Store result ---
    df["corrected_altitude"] = corrected_alt_final

    return df


# ── speed low-pass (used inside SegmentFinder) ──────────────────────

import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt

def filter_speed_lowpass(df, speed_col='speed', cutoff=0.1, fs=4, order=1):
    """
    Applies a Butterworth low-pass filter to the speed signal.
    
    Parameters:
    - df: Pandas DataFrame with speed data
    - speed_col: name of the speed column (default: 'speed')
    - cutoff: cutoff frequency in Hz (lower = smoother). Must be < fs/2.
    - fs: sampling frequency in Hz (e.g., 4 for 4 Hz)
    - order: filter order (higher = sharper cutoff)
    
    Returns:
    - Filtered speed signal as a Pandas Series
    """
    speed = df[speed_col].copy().astype(float)

    # Remove clearly invalid values first
    speed[(speed <= 0) | (~np.isfinite(speed))] = np.nan

    # Interpolate NaNs before filtering (or use forward fill, if preferred)
    speed_filled = speed.interpolate(limit_direction='both')

    # Normalize cutoff frequency
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq

    # Create Butterworth filter
    b, a = butter(order, normal_cutoff, btype='low', analog=False)

    # Apply zero-phase filter
    filtered = filtfilt(b, a, speed_filled)

    return pd.Series(filtered, index=df.index)
