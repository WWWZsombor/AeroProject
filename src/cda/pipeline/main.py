# src/cda/pipeline/main.py
"""
cda.pipeline.main  ·  checkpoint v0.2
=====================================
Full pipeline:
  JSON  →  segment  →  CSVs  →  group  →  preprocess  →  (future: solve)
"""

from __future__ import annotations

import glob
import logging
import os
import sys

import pandas as pd

from cda.cyclist.cyclist import Cyclist
from cda.utils.io import (
    load_ride_json,
    save_segment_csvs,
    save_combined_csvs,
)
from cda.preprocessing import (
    SegmentFinder,
    SegmentConfig,
    filter_dataframe_by_time,
    preprocess_segment,
    group_files_by_type,
    load_and_merge,
)
from cda.postprocessing import plot_segments
from cda.pipeline.config_loader import AppConfig

log = logging.getLogger("cda.pipeline")


# ── public entry point ───────────────────────────────────────────────

def main(yaml_path: str = "config/default.yaml") -> dict:
    project_root = _find_project_root()
    yaml_path    = _resolve_path(yaml_path, project_root)

    cfg     = AppConfig.from_yaml(yaml_path)
    cyclist = Cyclist.from_config_dict(cfg.cyclist.__dict__)

    log.info("\n%s", cfg)
    log.info("\n%s", cyclist)

     # ── stage 1: JSON → segments → CSVs ────────────────────────────
    json_files = sorted(glob.glob(os.path.join(cfg.paths.raw_data, "*.json")))
    if not json_files:
        log.error("No .json files found in %s", cfg.paths.raw_data)
        return {}

    log.info("Found %d JSON file(s).", len(json_files))

    seg_cfg = SegmentConfig(
        interval_length_sec=cfg.segment.interval_length_sec,
        min_speed=cfg.segment.min_speed,
        max_speed=cfg.segment.max_speed,
        segment_num=cfg.segment.segment_num,
        cost_speed=cfg.segment.cost_speed,
        cost_power=cfg.segment.cost_power,
      )
    finder = SegmentFinder(seg_cfg)

    all_written: list[str] = []
    plot_results: list[tuple[pd.DataFrame, list, str]] = []

    for json_path in json_files:
        test_id = os.path.splitext(os.path.basename(json_path))[0]
        log.info("=" * 60)
        log.info("Processing    %s    (test_id = %s)",
                 os.path.basename(json_path), test_id)

        written, plot_tuple = _process_json(
            json_path, test_id, cfg, cyclist, finder
        )
        all_written.extend(written)
        plot_results.append(plot_tuple)

     # ── stage 2: group + merge + preprocess ────────────────────────
    log.info("=" * 60)
    log.info("Grouping + preprocessing combined CSVs …")

    file_groups = group_files_by_type(cfg.paths.output_csv)
    merged_dfs  = load_and_merge(file_groups)

    preprocessed: dict[str, pd.DataFrame] = {}
    for test_id, df in merged_dfs.items():
        # auto-estimate dt
        dt = df["SECS"].diff().median()
        if pd.isna(dt) or dt <= 0:
            dt = 1.0
        log.info("  %s   rows=%d   dt=%.3f s",
                 test_id, len(df), dt)

        df_pp = preprocess_segment(df, cyclist, dt=dt, cfg=cfg.preprocessing)
        preprocessed[test_id] = df_pp

        # save preprocessed
        os.makedirs(cfg.paths.output_preprocessed, exist_ok=True)
        out_path = os.path.join(
            cfg.paths.output_preprocessed,
            f"{test_id}_preprocessed.csv",
        )
        df_pp.to_csv(out_path, index=False)
        log.info("    →  %s", out_path)
        all_written.append(out_path)

     # ── stage 3: plot ──────────────────────────────────────────────
    fig_paths = plot_segments(
        results=plot_results,
        out_dir=cfg.paths.output_plots,
        cfg=cfg.plot,
        filename="segments",
      )
    all_written.extend(fig_paths)

    log.info("=" * 60)
    log.info("Done.     %d file(s) written in total.", len(all_written))

    print(f"\n{len(all_written)} file(s) written.")
    for p in all_written:
        print(f"    {p}")

    return {"preprocessed": preprocessed, "cyclist": cyclist,
            "all_written": all_written}


# ── per-file processing ──────────────────────────────────────────────

def _process_json(
    json_path: str,
    test_id:   str,
    cfg:       AppConfig,
    cyclist:   Cyclist,
    finder:    SegmentFinder,
) -> tuple[list[str], tuple]:
        # 1 ── READ
    data = load_ride_json(json_path, test_id)
    bcvx_df = data.bcvx_df
    log.info("  loaded   cda=%s  ride=%s  bcvx=%s",
             data.cda_df.shape, data.ride_df.shape, bcvx_df.shape)

        # 2 ── CLEAN
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

        # 3 ── SPEED CORRECTION
    sc = cfg.preprocessing.speed_correction
    if sc != 1.0:
        bcvx_df["speed"] = bcvx_df["speed"] * sc
        log.info("  speed × %.4f", sc)
    else:
        log.info("  speed correction = 1.0 (no change)")

        # 4 ── cross-domain column
    data.ride_df["dyn_press"] = data.ride_df["airpressure"]

        # 5 ── SEGMENT
    segments = sorted(finder.find(bcvx_df), key=lambda s: s[0])
    log.info("  segments (%d, time-sorted):", len(segments))
    for i, (t0, t1) in enumerate(segments):
        log.info("    seg_%d    [%7.1f – %7.1f s]", i, t0, t1)

        # 6 ── SLICE + WRITE (separate + combined)
    written: list[str] = []
    for idx, (t0, t1) in enumerate(segments):
        cda_filt      = filter_dataframe_by_time(data.cda_df,  t0, t1)
        ride_filt     = filter_dataframe_by_time(data.ride_df, t0, t1)
        bcvx_filt     = filter_dataframe_by_time(bcvx_df,      t0, t1)

        paths = save_segment_csvs(
            cda_filt, ride_filt, bcvx_filt,
            out_dir=cfg.paths.output_csv,
            test_id=test_id,
            segment_idx=idx,
        )
        combined_path = save_combined_csvs(
            cda_filt, ride_filt, bcvx_filt,
            out_dir=cfg.paths.output_csv,
            test_id=test_id,
            segment_idx=idx,
        )
        written.extend(paths.values())
        written.append(combined_path)
        log.info("  seg_%d   →   %s   (+ combined)",
                 idx, paths["bcvx"])

    return written, (bcvx_df, segments, test_id)


# ── helpers (unchanged) ──────────────────────────────────────────────

def _find_project_root() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        d = os.path.dirname(d)
        if os.path.isdir(os.path.join(d, "config")):
            return d
    return os.getcwd()


def _resolve_path(path: str, root: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(root, path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s   %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
      )
    print("cda.pipeline.main  v0.2   –  starting …")
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "config/default.yaml"
    main(yaml_path=yaml_path)
