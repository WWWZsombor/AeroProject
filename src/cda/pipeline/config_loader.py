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
class AppConfig:
    paths:       PathsCfg   = field(default_factory=PathsCfg)
    segment:     SegmentCfg = field(default_factory=SegmentCfg)
    preprocessing: PreprocCfg = field(default_factory=PreprocCfg)

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "AppConfig":
        with open(yaml_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        return cls(
            paths=PathsCfg.from_dict(raw.get("paths", {})),
            segment=SegmentCfg.from_dict(raw.get("segment", {})),
            preprocessing=PreprocCfg.from_dict(raw.get("preprocessing", {})),
        )

    def __repr__(self) -> str:
        return (
            f"AppConfig\n"
            f"  paths.raw_data     = {self.paths.raw_data}\n"
            f"  paths.output_csv   = {self.paths.output_csv}\n"
            f"  paths.output_plots = {self.paths.output_plots}\n"
            f"  segment            = {self.segment}\n"
            f"  preprocessing      = {self.preprocessing}"
        )
