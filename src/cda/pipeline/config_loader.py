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
class PathsCfg:
    raw_data:            str = ""
    output_csv:          str = ""
    output_plots:        str = ""
    output_preprocessed: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "PathsCfg":
        return cls(
            raw_data=d.get("raw_data", ""),
            output_csv=d.get("output_csv", ""),
            output_plots=d.get("output_plots", ""),
            output_preprocessed=d.get("output_preprocessed", ""),
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
        


# ── add these dataclasses ────────────────────────────────────────────

@dataclass(frozen=True)
class CyclistCfg:
    body_mass:           float = 72.0
    bike_weight:         float = 8.5
    wheel_mass:          float = 0.90
    n_wheels:            int   = 2
    wheel_circumference: float = 2.095
    tyre_crr:            float = 0.004
    aerodynamic_position: str  = "dropbar"

    @classmethod
    def from_dict(cls, d: dict) -> "CyclistCfg":
        return cls(
            body_mass=float(d.get("body_mass", 72.0)),
            bike_weight=float(d.get("bike_weight", 8.5)),
            wheel_mass=float(d.get("wheel_mass", 0.90)),
            n_wheels=int(d.get("n_wheels", 2)),
            wheel_circumference=float(d.get("wheel_circumference", 2.095)),
            tyre_crr=float(d.get("tyre_crr", 0.004)),
            aerodynamic_position=str(d.get("aerodynamic_position", "dropbar")),
          )


@dataclass(frozen=True)
class PreprocCfg:
    calibrate_accelerometer: bool  = False
    calibrate_altitude:      bool  = False
    speed_correction:        float = 1.0
    # Butterworth parameters
    butter_cutoff_velocity:  float = 0.01
    butter_cutoff_power:     float = 0.01
    butter_cutoff_incline:   float = 0.20
    butter_cutoff_env:       float = 0.10
    butter_cutoff_airspeed:  float = 0.01
    butter_order:            int   = 1

    @classmethod
    def from_dict(cls, d: dict) -> "PreprocCfg":
        return cls(
            calibrate_accelerometer=bool(d.get("calibrate_accelerometer", False)),
            calibrate_altitude=bool(d.get("calibrate_altitude", False)),
            speed_correction=float(d.get("speed_correction", 1.0)),
            butter_cutoff_velocity=float(d.get("butter_cutoff_velocity", 0.01)),
            butter_cutoff_power=float(d.get("butter_cutoff_power", 0.01)),
            butter_cutoff_incline=float(d.get("butter_cutoff_incline", 0.20)),
            butter_cutoff_env=float(d.get("butter_cutoff_env", 0.10)),
            butter_cutoff_airspeed=float(d.get("butter_cutoff_airspeed", 0.01)),
            butter_order=int(d.get("butter_order", 1)),
          )


@dataclass(frozen=True)
class AppConfig:
    paths:         PathsCfg    = field(default_factory=PathsCfg)
    cyclist:       CyclistCfg  = field(default_factory=CyclistCfg)    # NEW
    segment:       SegmentCfg  = field(default_factory=SegmentCfg)
    preprocessing: PreprocCfg  = field(default_factory=PreprocCfg)
    plot:          PlotCfg     = field(default_factory=PlotCfg)

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "AppConfig":
        with open(yaml_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        return cls(
            paths=PathsCfg.from_dict(raw.get("paths", {})),
            cyclist=CyclistCfg.from_dict(raw.get("cyclist", {})),      # NEW
            segment=SegmentCfg.from_dict(raw.get("segment", {})),
            preprocessing=PreprocCfg.from_dict(raw.get("preprocessing", {})),
            plot=PlotCfg.from_dict(raw.get("plot", {})),
          )
