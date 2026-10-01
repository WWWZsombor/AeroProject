# src/cda/pipeline/config_loader.py
"""
Read config/default.yaml → one frozen AppConfig dataclass.
No other module in the project opens a YAML file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


# ── typed config ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class SegmentCfg:
    interval_length_sec: float = 120
    min_speed:           float = 49
    max_speed:           float = 55
    segment_num:         int   = 2
    cost_speed:          float = 0.5
    cost_power:          float = 0.5

    @classmethod
    def from_dict(cls, d: dict) -> "SegmentCfg":
        return cls(
            interval_length_sec=float(d.get("interval_length_sec", 120)),
            min_speed=float(d.get("min_speed", 49)),
            max_speed=float(d.get("max_speed", 55)),
            segment_num=int(d.get("segment_num", 2)),
            cost_speed=float(d.get("cost_speed", 0.5)),
            cost_power=float(d.get("cost_power", 0.5)),
        )


@dataclass(frozen=True)
class PreprocCfg:
    calibrate_accelerometer: bool  = False
    calibrate_altitude:      bool  = False
    speed_correction:        float = 1.0

    @classmethod
    def from_dict(cls, d: dict) -> "PreprocCfg":
        return cls(
            calibrate_accelerometer=bool(d.get("calibrate_accelerometer", False)),
            calibrate_altitude=bool(d.get("calibrate_altitude", False)),
            speed_correction=float(d.get("speed_correction", 1.0)),
        )


@dataclass(frozen=True)
class PathsCfg:
    raw_data:     str = ""
    output_csv:   str = ""
    output_plots: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "PathsCfg":
        return cls(
            raw_data=d.get("raw_data", ""),
            output_csv=d.get("output_csv", ""),
            output_plots=d.get("output_plots", ""),
        )


@dataclass(frozen=True)
class PlotCfg:
    speed_factor:          float   = 1.0
    fig_width:             float   = 12
    fig_height_per_row:    float   = 3.2
    dpi:                   int     = 150
    formats:               tuple   = ("png", "svg")
    show_segment_labels:   bool    = True
    show_glow:             bool    = True          # ← new
    line_width_base:       float   = 1.0
    line_width_seg:        float   = 2.2
    palette:               tuple   = (             # ← new
         "#00f0ff",
         "#ff2d78",
         "#ff8c00",
         "#b026ff",
         "#39ff14",
         "#ffea00",
    )

    @classmethod
    def from_dict(cls, d: dict) -> "PlotCfg":
        fmts  = d.get("formats", ["png", "svg"])
        palette = tuple(d.get("palette", [
            "#00f0ff", "#ff2d78", "#ff8c00",
            "#b026ff", "#39ff14", "#ffea00",
        ]))
        return cls(
            speed_factor=float(d.get("speed_factor", 1.0)),
            fig_width=float(d.get("fig_width", 12)),
            fig_height_per_row=float(d.get("fig_height_per_row", 3.2)),
            dpi=int(d.get("dpi", 150)),
            formats=tuple(fmts),
            show_segment_labels=bool(d.get("show_segment_labels", True)),
            show_glow=bool(d.get("show_glow", True)),
            line_width_base=float(d.get("line_width_base", 1.0)),
            line_width_seg=float(d.get("line_width_seg", 2.2)),
            palette=palette,
         )
        

@dataclass(frozen=True)
class AppConfig:
    paths:         PathsCfg   = field(default_factory=PathsCfg)
    segment:       SegmentCfg = field(default_factory=SegmentCfg)
    preprocessing: PreprocCfg = field(default_factory=PreprocCfg)
    plot:          PlotCfg    = field(default_factory=PlotCfg)     # ← NEW

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "AppConfig":
        with open(yaml_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        return cls(
            paths=PathsCfg.from_dict(raw.get("paths", {})),
            segment=SegmentCfg.from_dict(raw.get("segment", {})),
            preprocessing=PreprocCfg.from_dict(raw.get("preprocessing", {})),
            plot=PlotCfg.from_dict(raw.get("plot", {})),       # ← NEW
        )
