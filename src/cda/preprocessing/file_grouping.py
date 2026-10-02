# src/cda/preprocessing/file_grouping.py
"""
cda.preprocessing.file_grouping
================================
Scan a folder for the per-segment CSVs written by ``io.save_segment_csvs``
and group them back into per-ride DataFrames.

File naming convention (set by io.save_segment_csvs):
    {test_id}_cda_{idx}.csv
    {test_id}_ride_{idx}.csv
    {test_id}_bcvx_{idx}.csv
"""

from __future__ import annotations

from pathlib import Path
from collections import defaultdict

import pandas as pd


# ── public API ───────────────────────────────────────────────────────

def group_files_by_type(
    main_folder: str | Path,
) -> dict[str, dict[str, list[str]]]:
    """
    Scan *main_folder* for ``*.csv`` files and group them by
    (test_id, domain).

    Returns
    -------
    dict
        {
          "ride_01": {
              "bcvx": ["/…/ride_01_bcvx_0.csv", "/…/ride_01_bcvx_1.csv"],
              "ride": ["/…/ride_01_ride_0.csv", …],
              "cda":  ["/…/ride_01_cda_0.csv",  …],
          },
          "ride_02": {…},
        }
    """
    main_folder = Path(main_folder)
    groups: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for fp in sorted(main_folder.glob("*.csv")):
        name = fp.name          # e.g.  ride_01_bcvx_2.csv

        # split on the domain tag
        for domain in ("bcvx", "ride", "cda"):
            tag = f"_{domain}_"
            if tag in name:
                test_id = name.split(tag)[0]
                groups[test_id][domain].append(str(fp))
                break

     # sort each list by the numeric suffix
    for tid in groups:
        for dom in groups[tid]:
            groups[tid][dom].sort(
                key=lambda p: int(Path(p).stem.split("_")[-1])
            )

    return dict(groups)


def load_and_merge(
    file_groups: dict[str, dict[str, list[str]]],
) -> dict[str, pd.DataFrame]:
    """
    For every test_id, load all segment CSVs for each domain,
    concatenate along time, and merge cda + ride + bcvx on ``SECS``.

    Returns
    -------
    dict[str, pd.DataFrame]
        {test_id: merged_df}
    """
    merged: dict[str, pd.DataFrame] = {}

    for test_id, domains in file_groups.items():
        frames: dict[str, pd.DataFrame] = {}

        for domain, paths in domains.items():
            chunks = [pd.read_csv(p) for p in paths]
            frames[domain] = pd.concat(chunks, ignore_index=True)

        # merge on SECS (outer join to keep all rows)
        merged_df = None
        for domain in ("cda", "ride", "bcvx"):
            if domain not in frames:
                continue
            df = frames[domain]
            if merged_df is None:
                merged_df = df.copy()
            else:
                # avoid duplicate column names
                overlap = merged_df.columns.intersection(df.columns)
                extra = [c for c in df.columns if c not in overlap]
                merged_df = merged_df.merge(
                    df[["SECS"] + extra],
                    on="SECS",
                    how="outer",
                )

        if merged_df is not None:
            merged_df = merged_df.sort_values("SECS").reset_index(drop=True)
            merged[test_id] = merged_df

    return merged
