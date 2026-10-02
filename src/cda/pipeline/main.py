# src/cda/pipeline/main.py
"""
cda.pipeline.main  ·  checkpoint v0.2
=====================================
Full pipeline:
  JSON  →  segment  →  CSVs  →  group  →  preprocess (per segment)  →  (future: solve)
"""

from __future__ import annotations

import dataclasses
import glob
import json
import logging
import os
import sys

import pandas as pd

from cda.cyclist.cyclist import Cyclist
from cda.utils.io import (
    load_ride_json,
    merge_ride_bcvx,
    remove_segment_csvs,
    save_segment_csvs,
    save_combined_csvs,
)
from cda.preprocessing import (
    SegmentFinder,
    SegmentConfig,
    filter_dataframe_by_time,
    group_files_by_type,
    load_segments,
)
from cda.postprocessing import plot_segments
from cda.pipeline.config_loader import AppConfig, PathsCfg
from cda.pipeline.preprocess_stage import preprocess_test

log = logging.getLogger("cda.pipeline")


# ── public entry point ───────────────────────────────────────────────

def main(yaml_path: str = "config/default.yaml") -> dict:
    project_root = _find_project_root()
    yaml_path    = _resolve_path(yaml_path, project_root)

    cfg     = AppConfig.from_yaml(yaml_path)
    cfg     = dataclasses.replace(
        cfg, paths=_resolve_paths(cfg.paths, project_root)
    )
    cyclist = Cyclist.from_config_dict(cfg.cyclist.__dict__)

    log.info("\n%s", cfg)
    log.info("mode = %s   active section: %s", cfg.mode, cfg.mode_cfg)
    log.info("solvers = %s   (solve / uncertainty / report stages: not implemented yet)",
             ", ".join(cfg.solver.enabled))
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
    full_rides: dict[str, pd.DataFrame] = {}

    for json_path in json_files:
        test_id = _test_id(json_path)
        log.info("=" * 60)
        log.info("Processing    %s    (test_id = %s)",
                 os.path.basename(json_path), test_id)

        written, plot_tuple, full_df = _process_json(
            json_path, test_id, cfg, cyclist, finder
        )
        all_written.extend(written)
        plot_results.append(plot_tuple)
        full_rides[test_id] = full_df

     # ── stage 2: per setup – calibrate airspeed, preprocess segments ─
    log.info("=" * 60)
    log.info("Loading + preprocessing segments …")

    test_ids    = [_test_id(p) for p in json_files]
    file_groups = group_files_by_type(cfg.paths.output_csv, test_ids)
    segments_by_test = load_segments(file_groups)

    preprocessed: dict[str, dict[str, pd.DataFrame]] = {}
    calibrations: dict[str, list] = {}
    os.makedirs(cfg.paths.output_preprocessed, exist_ok=True)
    for test_id, seg_dfs in segments_by_test.items():
        runs, cals = preprocess_test(
            test_id, seg_dfs, full_rides[test_id], cfg, cyclist
        )
        preprocessed[test_id] = runs
        calibrations[test_id] = cals

        for run, df_run in runs.items():
            out_path = os.path.join(cfg.paths.output_preprocessed,
                                    f"{test_id}_preprocessed_{run}.csv")
            df_run.to_csv(out_path, index=False)
            log.info("    →  %s", out_path)
            all_written.append(out_path)

        cal_path = os.path.join(cfg.paths.output_preprocessed,
                                f"{test_id}_airspeed_calibration.json")
        with open(cal_path, "w", encoding="utf-8") as fh:
            json.dump({"setup": test_id, "scope": cfg.airspeed_calibration.scope,
                       "calibrations": [c.to_dict() for c in cals]}, fh, indent=2)
        all_written.append(cal_path)

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

    return {"preprocessed": preprocessed, "calibrations": calibrations,
            "cyclist": cyclist, "all_written": all_written}


# ── per-file processing ──────────────────────────────────────────────

def _process_json(
    json_path: str,
    test_id:   str,
    cfg:       AppConfig,
    cyclist:   Cyclist,
    finder:    SegmentFinder,
) -> tuple[list[str], tuple, pd.DataFrame]:
        # 1 ── READ
    data = load_ride_json(json_path, test_id)
    bcvx_df = data.bcvx_df
    log.info("  loaded   cda=%s  ride=%s  bcvx=%s",
             data.cda_df.shape, data.ride_df.shape, bcvx_df.shape)

        # 2 ── CLEAN
    if cfg.preprocessing.calibrate_altitude:
        from cda.preprocessing import correct_altitude
        bcvx_df = correct_altitude(bcvx_df, zero_offset=0.0)
        log.info("  altitude corrected")
    else:
        log.info("  altitude correction skipped")

        # 3 ── SPEED CORRECTION
    sc = cfg.preprocessing.speed_correction
    if sc != 1.0:
        bcvx_df = bcvx_df.copy()
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
    remove_segment_csvs(cfg.paths.output_csv, test_id)
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
            ride_filt, bcvx_filt,
            out_dir=cfg.paths.output_csv,
            test_id=test_id,
            segment_idx=idx,
        )
        written.extend(paths.values())
        written.append(combined_path)
        log.info("  seg_%d   →   %s   (+ combined)",
                 idx, paths["bcvx"])

    full_df = merge_ride_bcvx(data.ride_df, bcvx_df)   # whole ride, 4 Hz
    return written, (bcvx_df, segments, test_id), full_df


# ── helpers (unchanged) ──────────────────────────────────────────────

def _find_project_root() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        d = os.path.dirname(d)
        if os.path.isdir(os.path.join(d, "config")):
            return d
    return os.getcwd()


def _resolve_path(path: str, root: str) -> str:
    if not path or os.path.isabs(path):
        return path
    return os.path.join(root, path)


def _resolve_paths(paths: PathsCfg, root: str) -> PathsCfg:
    """Make every relative path of the config absolute (relative to *root*)."""
    return PathsCfg(**{
        f.name: _resolve_path(getattr(paths, f.name), root)
        for f in dataclasses.fields(paths)
    })


def _test_id(json_path: str) -> str:
    return os.path.splitext(os.path.basename(json_path))[0]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s   %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
      )
    print("cda.pipeline.main  v0.2   –  starting …")
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "config/default.yaml"
    main(yaml_path=yaml_path)
