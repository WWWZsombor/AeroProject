# src/cda/utils/io.py
"""
cda.utils.io
============
Read one JSON measurement file → RawRideData.
Write the per-domain segment CSVs and the combined (ride + bcvx) CSV.
No physics, no plotting, no segment-finding.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import pandas as pd


# ── typed container ──────────────────────────────────────────────────

@dataclass
class RawRideData:
    """Everything parsed from one JSON measurement file."""
    test_id:      str
    cda_df:       pd.DataFrame
    ride_df:      pd.DataFrame
    bcvx_df:      pd.DataFrame
    intervals_df: pd.DataFrame
    source_path:  str = ""


# ── public: read ─────────────────────────────────────────────────────

def load_ride_json(json_path: str, test_id: str) -> RawRideData:
    """Open one JSON file, return a filled RawRideData."""
    with open(json_path, "r", encoding="utf-8-sig") as fh:
        raw = json.load(fh)

    ride = raw["RIDE"]

    intervals_df = pd.DataFrame(ride.get("INTERVALS", []))
    cda_df, ride_df, bcvx_df = _process_xdata(ride.get("XDATA", []))

    return RawRideData(
        test_id=test_id,
        cda_df=cda_df,
        ride_df=ride_df,
        bcvx_df=bcvx_df,
        intervals_df=intervals_df,
        source_path=os.path.abspath(json_path),
    )


# ── public: write ────────────────────────────────────────────────────

def save_segment_csvs(
    cda_df: pd.DataFrame,
    ride_df: pd.DataFrame,
    bcvx_df: pd.DataFrame,
    out_dir: str,
    test_id: str,
    segment_idx: int,
) -> dict[str, str]:
    """Write the three CSVs for one segment; return the paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = {
        "cda":  os.path.join(out_dir, f"{test_id}_cda_{segment_idx}.csv"),
        "ride": os.path.join(out_dir, f"{test_id}_ride_{segment_idx}.csv"),
        "bcvx": os.path.join(out_dir, f"{test_id}_bcvx_{segment_idx}.csv"),
    }
    cda_df.to_csv(paths["cda"],  index=False)
    ride_df.to_csv(paths["ride"], index=False)
    bcvx_df.to_csv(paths["bcvx"], index=False)
    return paths


# ── internal helpers ─────────────────────────────────────────────────

def _process_xdata(data_xdata: list):
    """Split the flat XDATA list into the three domain DataFrames."""
    df = pd.DataFrame(data_xdata)
    cda_df  = _get_all_samples(df, "CDAData")
    ride_df = _get_all_samples(df, "RideData")
    bcvx_df = _get_all_samples(df, "BCVX")
    return cda_df, ride_df, bcvx_df


# ── internal helper ──────────────────────────────────────────────────

def _get_all_samples(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """
    Flatten nested SAMPLES / VALUES for one domain into a wide DataFrame.

    Expected JSON shape for one row in the XDATA table::

        {
          "NAME":    "BCVX",
          "VALUES":  ["col1", "col2", …],       ← column-name list
          "SAMPLES": [                           ← list of *chunks*
              [                                   ← each chunk is a list of
                {"TIME": 0.0,  "VALUES": […]},   ←   record-dicts
                {"TIME": 0.1,  "VALUES": […]},
                …
              ],
              [                                   ← next chunk
                {"TIME": 120.0, "VALUES": […]},
                …
              ]
          ]
        }
    """
    subset = df[df["NAME"] == name]
    if subset.empty:
        return pd.DataFrame()

    # column names come from the top-level VALUES field
    col_names   = subset["VALUES"].iloc[0]
    flat_cols   = [c[0] if isinstance(c, list) else c for c in col_names]

    # each element of SAMPLES is a *list of record-dicts*
    # → pd.DataFrame(item) turns it into a proper DataFrame first
    result_dfs = []
    for item in subset["SAMPLES"]:
        df_item = pd.DataFrame(item)                       # ← the key line
        values_col = df_item["VALUES"].tolist()
        new_df   = pd.DataFrame(values_col, columns=flat_cols)
        merged   = pd.concat([df_item.drop("VALUES", axis=1), new_df],
                             axis=1)
        result_dfs.append(merged)

    if not result_dfs:
        return pd.DataFrame()

    return pd.concat(result_dfs, ignore_index=True)


def merge_ride_bcvx(
    ride_df: pd.DataFrame,
    bcvx_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge the two 4 Hz domains of one segment onto a single time grid.

    Both domains are sampled at the same ``SECS`` stamps, so an inner join
    produces a gap-free frame (no NaN rows).  The 1 Hz ``CDAData`` domain
    (device-computed CdA and friends) is deliberately **not** merged.

    Column rules for names present in both domains
    (``KM``, ``temperature``, ``power``, ``cadence``, gears, ``speed``):

    * the RideData column wins, because RideData carries SI units;
    * except ``speed``: the BCVX column (km/h) is kept as ``speed`` – the
      unit used by the segment finder and the preprocessing step – and the
      RideData column (m/s) is kept as ``speed_ride``.

    Returns a new DataFrame sorted by ``SECS``.
    """
    ride = ride_df.rename(columns={"speed": "speed_ride"})
    extra = [c for c in bcvx_df.columns
             if c == "SECS" or c == "speed" or c not in ride.columns]
    merged = ride.merge(bcvx_df[extra], on="SECS", how="inner")
    return merged.sort_values("SECS").reset_index(drop=True)


def save_combined_csvs(
    ride_df:     pd.DataFrame,
    bcvx_df:     pd.DataFrame,
    out_dir:     str,
    test_id:     str,
    segment_idx: int,
) -> str:
    """
    Merge RideData + BCVX of one segment (see :func:`merge_ride_bcvx`)
    and write ``{test_id}_combined_{idx}.csv``.  This is the file that
    ``preprocess_segment`` consumes.

    Returns the path to the written file.
    """
    os.makedirs(out_dir, exist_ok=True)
    merged = merge_ride_bcvx(ride_df, bcvx_df)
    path = os.path.join(out_dir, f"{test_id}_combined_{segment_idx}.csv")
    merged.to_csv(path, index=False)
    return path


def remove_segment_csvs(out_dir: str, test_id: str) -> int:
    """
    Delete earlier ``{test_id}_{cda|ride|bcvx|combined}_{idx}.csv`` files
    so a re-run with fewer segments leaves no stale files behind.
    Returns the number of files removed.
    """
    if not os.path.isdir(out_dir):
        return 0
    pattern = re.compile(
        rf"^{re.escape(test_id)}_(cda|ride|bcvx|combined)_\d+\.csv$"
    )
    removed = 0
    for name in os.listdir(out_dir):
        if pattern.match(name):
            os.remove(os.path.join(out_dir, name))
            removed += 1
    return removed
