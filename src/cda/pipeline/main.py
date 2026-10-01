# src/cda/pipeline/main.py
"""
Full pipeline driven entirely by a YAML config file.

Flow
----
  glob *.json  in  paths.raw_data
       │
       ▼
  for each json:
     test_id  =  filename without ".json"
     load  →  clean  →  speed_correction  →  segment  →  write CSVs
"""

from __future__ import annotations

import glob
import logging
import os

from cda.utils.io import load_ride_json, save_segment_csvs
from cda.preprocessing import (
    SegmentFinder,
    SegmentConfig,
    filter_dataframe_by_time,
)
from cda.pipeline.config_loader import AppConfig

log = logging.getLogger("cda.pipeline")


# ── public entry point ───────────────────────────────────────────────

def main(yaml_path: str = "config/default.yaml") -> list[str]:
    """
    Read the YAML, process every .json found in paths.raw_data,
    write per-segment CSVs to paths.output_csv.

    Parameters
    ----------
    yaml_path : str, optional
        Path to the configuration YAML.  Default is the repo file.

    Returns
     -------
    List of absolute CSV paths that were written.
    """
    cfg = AppConfig.from_yaml(yaml_path)
    log.info("\n%s", cfg)

     # glob every .json in the raw_data folder
    json_files = sorted(glob.glob(os.path.join(cfg.paths.raw_data, "*.json")))
    if not json_files:
        log.error("No .json files found in %s", cfg.paths.raw_data)
        return []
    log.info("Found %d JSON file(s) to process", len(json_files))

    # build the SegmentFinder once – same config for every file
    seg_cfg  = SegmentConfig(
        interval_length_sec=cfg.segment.interval_length_sec,
        min_speed=cfg.segment.min_speed,
        max_speed=cfg.segment.max_speed,
        segment_num=cfg.segment.segment_num,
        cost_speed=cfg.segment.cost_speed,
        cost_power=cfg.segment.cost_power,
     )
    finder   = SegmentFinder(seg_cfg)

    all_written: list[str] = []

    for json_path in json_files:
        test_id = os.path.splitext(os.path.basename(json_path))[0]
        log.info("=" * 60)
        log.info("Processing  %s   (test_id=%s)", json_path, test_id)

        written = _process_one(
            json_path=json_path,
            test_id=test_id,
            cfg=cfg,
            finder=finder,
        )
        all_written.extend(written)

    log.info("=" * 60)
    log.info("Done.  %d CSV file(s) written in total.", len(all_written))
    return all_written


# ── internal ──────────────────────────────────────────────────────────

def _process_one(
    json_path: str,
    test_id:   str,
    cfg:       AppConfig,
    finder:    SegmentFinder,
) -> list[str]:

     # 1 ── READ
    data = load_ride_json(json_path, test_id)
    bcvx_df = data.bcvx_df
    log.info("  loaded   cda=%s  ride=%s  bcvx=%s",
             data.cda_df.shape, data.ride_df.shape, bcvx_df.shape)

     # 2 ── CLEAN   (driven by YAML flags)
    if cfg.preprocessing.calibrate_accelerometer:
        from cda.preprocessing import apply_accelerometer_calibration
        bcvx_df = apply_accelerometer_calibration(bcvx_df)
        log.info("  accelerometer calibrated")
    else:
        log.info("  accelerometer calibration skipped")

    if cfg.preprocessing.calibrate_altitude:
        from cda.preprocessing import correct_altitude
        bcvx_df = correct_altitude(bcvx_df, zero_offset=0.0)
        log.info("  altitude corrected")
    else:
        log.info("  altitude correction skipped")

     # 3 ── SPEED CORRECTION   (from YAML, not a function arg)
    sc = cfg.preprocessing.speed_correction
    if sc != 1.0:
        bcvx_df["speed"] = bcvx_df["speed"] * sc
        log.info("  speed × %.4f", sc)
    else:
        log.info("  speed correction = 1.0 (no change)")

     # 4 ── cross-domain column the solver needs later
    data.ride_df["dyn_press"] = data.ride_df["airpressure"]

     # 5 ── SEGMENT
    segments = finder.find(bcvx_df)
    log.info("  segments: %s", segments)

     # 6 ── SLICE + WRITE
    written = []
    for idx, (t0, t1) in enumerate(segments):
        cda_filt    = filter_dataframe_by_time(data.cda_df,  t0, t1)
        ride_filt   = filter_dataframe_by_time(data.ride_df, t0, t1)
        bcvx_filt   = filter_dataframe_by_time(bcvx_df,      t0, t1)

        paths = save_segment_csvs(
            cda_filt, ride_filt, bcvx_filt,
            out_dir=cfg.paths.output_csv,
            test_id=test_id,
            segment_idx=idx,
        )
        log.info("  seg %d  [%7.1f – %7.1f s]  →  %s",
                 idx, t0, t1, paths["bcvx"])
        written.extend(paths.values())

    return written


# ── allow  python -m cda.pipeline.main  config/default.yaml  ──────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s   %(levelname)-7s  %(message)s",
    )

    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "config/default.yaml"
    main(yaml_path=yaml_path)
