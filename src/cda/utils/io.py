# src/cda/io.py
"""
cda.io
======
Read one JSON measurement file → RawRideData.
Write the three segment CSVs.
No physics, no plotting, no segment-finding.
"""

from __future__ import annotations

import json
import os
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


def save_combined_csvs(
    cda_df:     pd.DataFrame,
    ride_df:    pd.DataFrame,
    bcvx_df:    pd.DataFrame,
    out_dir:    str,
    test_id:    str,
    segment_idx: int,
) -> str:
    """
    Merge the three domain DataFrames on ``SECS`` and write a single
    CSV that contains every column.  This is the file that
    ``preprocess_segment`` consumes.

    Returns the path to the written file.
    """
    os.makedirs(out_dir, exist_ok=True)

     # outer merge on time
    merged = cda_df.merge(ride_df, on="SECS", how="outer",
                          suffixes=("_cda", "_ride"))
    merged = merged.merge(bcvx_df, on="SECS", how="outer",
                          suffixes=("_cda", "_bcvx"))
    merged = merged.sort_values("SECS").reset_index(drop=True)

    fname = f"{test_id}_combined_{segment_idx}.csv"
    path  = os.path.join(out_dir, fname)
    merged.to_csv(path, index=False)
    return path


