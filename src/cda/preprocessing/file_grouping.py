# src/cda/preprocessing/file_grouping.py
"""
cda.preprocessing.file_grouping
================================
Scan a folder for the per-segment CSVs written by ``utils.io`` and group
them back into per-ride lists of segment DataFrames.

File naming convention:
    {test_id}_cda_{idx}.csv       raw 1 Hz device domain   (not used downstream)
    {test_id}_ride_{idx}.csv      raw 4 Hz RideData
    {test_id}_bcvx_{idx}.csv      raw 4 Hz BCVX
    {test_id}_combined_{idx}.csv  ride + bcvx on one 4 Hz grid  (consumed here)
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
from collections import defaultdict

import pandas as pd

_DOMAINS = ("combined", "bcvx", "ride", "cda")


# ── public API ───────────────────────────────────────────────────────

def group_files_by_type(
    main_folder: str | Path,
    test_ids:    Iterable[str] | None = None,
) -> dict[str, dict[str, list[str]]]:
    """
    Scan *main_folder* for ``*.csv`` files and group them by
    (test_id, domain).  If *test_ids* is given, files of any other
    test_id (e.g. stale outputs of earlier runs) are ignored.

    Returns
    -------
    dict
        {
          "ride_01": {
              "combined": ["/…/ride_01_combined_0.csv", …],
              "bcvx": ["/…/ride_01_bcvx_0.csv", "/…/ride_01_bcvx_1.csv"],
              "ride": ["/…/ride_01_ride_0.csv", …],
              "cda":  ["/…/ride_01_cda_0.csv",  …],
          },
          "ride_02": {…},
        }
    """
    main_folder = Path(main_folder)
    wanted = set(test_ids) if test_ids is not None else None
    groups: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for fp in sorted(main_folder.glob("*.csv")):
        name = fp.name          # e.g.  ride_01_bcvx_2.csv

        # split on the domain tag
        for domain in _DOMAINS:
            tag = f"_{domain}_"
            if tag in name:
                test_id = name.split(tag)[0]
                if wanted is None or test_id in wanted:
                    groups[test_id][domain].append(str(fp))
                break

     # sort each list by the numeric suffix
    for tid in groups:
        for dom in groups[tid]:
            groups[tid][dom].sort(
                key=lambda p: int(Path(p).stem.split("_")[-1])
            )

    return dict(groups)


def load_segments(
    file_groups: dict[str, dict[str, list[str]]],
) -> dict[str, list[pd.DataFrame]]:
    """
    Load the ``combined`` CSV of every segment, keeping the segments apart.

    Segments are separate time windows with gaps between them, so they are
    **never** concatenated here: filtering or differentiating across a gap
    would create artefacts.  Each frame is already on a gap-free 4 Hz grid.

    Returns
    -------
    dict[str, list[pd.DataFrame]]
        {test_id: [segment_0_df, segment_1_df, …]}  (time-sorted)
    """
    return {
        test_id: [pd.read_csv(p) for p in domains["combined"]]
        for test_id, domains in file_groups.items()
        if domains.get("combined")
    }
