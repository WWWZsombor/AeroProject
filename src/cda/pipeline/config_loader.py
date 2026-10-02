# src/cda/pipeline/config_loader.py
"""
Read a YAML config (e.g. config/default.yaml) → one frozen AppConfig dataclass.
No other module in the project opens a YAML file.

A config file may inherit from another one with a top-level ``extends:``
key (path relative to the file); the child is deep-merged over the parent,
so ``config/field.yaml`` only has to list what differs from the default.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import yaml

MODES            = ("velodrome", "field")
WIND_RUNS        = ("no_wind", "with_wind")
SPEED_SOURCES    = ("sensor", "wheel", "both")
BEND_HANDLING    = ("exclude", "correct", "keep")
WIND_SOURCES     = ("airspeed", "none")
INCLINE_SOURCES  = ("altitude", "imu", "none")
BOOTSTRAP_METHODS = ("block", "residual")
REPORT_FORMATS   = ("html", "pdf")


# ── helpers for the new (strict) sections ────────────────────────────

def _check_choice(name: str, value, allowed: tuple) -> None:
    if value not in allowed:
        raise ValueError(
            f"config: {name} = {value!r} is not valid; choose one of {list(allowed)}"
        )


def _strict_from_dict(cls, section: str, d: dict) -> dict:
    """
    Return the kwargs for ``cls(**kwargs)`` from the YAML dict *d*.
    Unknown keys raise (a typo in the YAML must not silently fall back to
    a default); list values become tuples (frozen dataclasses stay hashable).
    """
    names = {f.name for f in dataclasses.fields(cls)}
    unknown = sorted(set(d) - names)
    if unknown:
        raise ValueError(
            f"config: unknown key(s) {unknown} in '{section}'; "
            f"allowed: {sorted(names)}"
        )
    return {k: tuple(v) if isinstance(v, list) else v for k, v in d.items()}


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
    output_report:       str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "PathsCfg":
        return cls(
            output_report=d.get("output_report", ""),
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
    calibrate_altitude:      bool  = False
    speed_correction:        float = 1.0
    # Butterworth cut-off frequencies in Hz (fs = 1/dt, 4 Hz for Notio data)
    butter_cutoff_velocity:  float = 0.01
    butter_cutoff_power:     float = 0.01
    butter_cutoff_incline:   float = 0.20
    butter_cutoff_env:       float = 0.10
    butter_cutoff_airspeed:  float = 0.01
    butter_order:            int   = 1

    @classmethod
    def from_dict(cls, d: dict) -> "PreprocCfg":
        return cls(
            calibrate_altitude=bool(d.get("calibrate_altitude", False)),
            speed_correction=float(d.get("speed_correction", 1.0)),
            butter_cutoff_velocity=float(d.get("butter_cutoff_velocity", 0.01)),
            butter_cutoff_power=float(d.get("butter_cutoff_power", 0.01)),
            butter_cutoff_incline=float(d.get("butter_cutoff_incline", 0.20)),
            butter_cutoff_env=float(d.get("butter_cutoff_env", 0.10)),
            butter_cutoff_airspeed=float(d.get("butter_cutoff_airspeed", 0.01)),
            butter_order=int(d.get("butter_order", 1)),
          )


# ── mode-specific sections ───────────────────────────────────────────

@dataclass(frozen=True)
class VelodromeCfg:
    """Used when ``mode: velodrome``."""
    wind_runs:              tuple = ("no_wind", "with_wind")
    speed_source:           str   = "sensor"    # sensor | wheel | both
    chainring_teeth:        int   = 60          # fixed gear
    cog_teeth:              int   = 15
    yaw_rate_column:        str   = "gyrZ"      # vertical-axis gyro, deg/s
    yaw_rate_threshold_dps: float = 15.0        # |yaw rate| above → bend
    yaw_smoothing_sec:      float = 1.0
    min_straight_sec:       float = 3.0
    bend_handling:          str   = "exclude"   # exclude | correct | keep

    def __post_init__(self):
        if not self.wind_runs:
            raise ValueError("config: velodrome.wind_runs must not be empty")
        for run in self.wind_runs:
            _check_choice("velodrome.wind_runs[]", run, WIND_RUNS)
        _check_choice("velodrome.speed_source", self.speed_source, SPEED_SOURCES)
        _check_choice("velodrome.bend_handling", self.bend_handling, BEND_HANDLING)
        if self.chainring_teeth <= 0 or self.cog_teeth <= 0:
            raise ValueError("config: velodrome gear teeth must be > 0")

    @property
    def gear_ratio(self) -> float:
        """Wheel revolutions per crank revolution (fixed gear)."""
        return self.chainring_teeth / self.cog_teeth

    @classmethod
    def from_dict(cls, d: dict) -> "VelodromeCfg":
        return cls(**_strict_from_dict(cls, "velodrome", d))


@dataclass(frozen=True)
class FieldCfg:
    """Used when ``mode: field``."""
    wind_source:     str = "airspeed"           # airspeed | none
    incline_source:  str = "altitude"           # altitude | imu | none

    def __post_init__(self):
        _check_choice("field.wind_source", self.wind_source, WIND_SOURCES)
        _check_choice("field.incline_source", self.incline_source, INCLINE_SOURCES)

    @classmethod
    def from_dict(cls, d: dict) -> "FieldCfg":
        return cls(**_strict_from_dict(cls, "field", d))


@dataclass(frozen=True)
class AirspeedCalibrationCfg:
    """
    Per-setup calibration of the pitot airspeed against ground speed
    (``v_air = scale · v_raw + offset``).  One setup = one measurement file.
    """
    method:       str   = "auto"        # auto (fit) | none (identity)
    fit:          str   = "scale"       # scale | scale_offset
    scope:        str   = "test"        # test (one per file) | segment
    smoothing_hz: float = 0.20          # low-pass for the fit signals
    min_speed:    float = 8.0           # m/s   fit only above
    max_accel:    float = 0.10          # m/s²  fit only on steady speed
    min_points:   int   = 40            # samples needed for a fit
    min_range:    float = 3.0           # m/s   steady-speed range for an offset
    overrides:    dict  = dc_field(default_factory=dict)   # {test_id: {scale, offset}}

    def __post_init__(self):
        _check_choice("airspeed_calibration.method", self.method, ("auto", "none"))
        _check_choice("airspeed_calibration.fit", self.fit, ("scale", "scale_offset"))
        _check_choice("airspeed_calibration.scope", self.scope, ("test", "segment"))
        for setup, o in self.overrides.items():
            bad = sorted(set(o or {}) - {"scale", "offset"})
            if bad:
                raise ValueError(
                    f"config: airspeed_calibration.overrides[{setup!r}] has unknown "
                    f"key(s) {bad}; allowed: ['offset', 'scale']"
                )

    @classmethod
    def from_dict(cls, d: dict) -> "AirspeedCalibrationCfg":
        kw = _strict_from_dict(cls, "airspeed_calibration", d)
        kw["overrides"] = {str(k): dict(v or {}) for k, v in kw.get("overrides", {}).items()}
        return cls(**kw)


# ── solver / uncertainty / report ────────────────────────────────────

@dataclass(frozen=True)
class SolverCfg:
    """Which CdA solvers run and their hyper-parameters (CdA only)."""
    enabled:     tuple = ("ols", "chung", "kalman", "gp")
    cda_initial: float = 0.30                   # m²
    cda_bounds:  tuple = (0.05, 1.00)           # m²
    # per-solver hyper-parameters, keyed by solver name (free-form)
    options:     dict  = dc_field(default_factory=dict)

    def __post_init__(self):
        if not self.enabled:
            raise ValueError("config: solver.enabled must list at least one solver")
        lo, hi = self.cda_bounds
        if not lo < hi:
            raise ValueError(f"config: solver.cda_bounds must be [low, high], got {self.cda_bounds}")
        if not lo <= self.cda_initial <= hi:
            raise ValueError("config: solver.cda_initial must lie inside solver.cda_bounds")
        stray = sorted(set(self.options) - set(self.enabled))
        if stray:
            raise ValueError(f"config: solver.options for solver(s) not in solver.enabled: {stray}")

    @classmethod
    def from_dict(cls, d: dict) -> "SolverCfg":
        return cls(**_strict_from_dict(cls, "solver", d))


@dataclass(frozen=True)
class UncertaintyCfg:
    confidence_level:     float = 0.95
    analytic_ci:          bool  = True          # CI from the solver itself
    bootstrap:            bool  = True          # resample residuals
    bootstrap_method:     str   = "block"       # block | residual
    bootstrap_block_sec:  float = 5.0           # keeps residual autocorrelation
    bootstrap_samples:    int   = 1000
    monte_carlo:          bool  = True          # perturb the sensor inputs
    monte_carlo_samples:  int   = 1000
    noise_speed_std:      float = 0.05          # m/s
    noise_power_rel_std:  float = 0.02          # fraction of power
    noise_density_rel_std: float = 0.005        # fraction of ρ
    noise_airspeed_std:   float = 0.10          # m/s
    seed:                 int   = 42

    def __post_init__(self):
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("config: uncertainty.confidence_level must be in (0, 1)")
        _check_choice("uncertainty.bootstrap_method", self.bootstrap_method, BOOTSTRAP_METHODS)
        if self.bootstrap_samples < 1 or self.monte_carlo_samples < 1:
            raise ValueError("config: uncertainty sample counts must be >= 1")

    @classmethod
    def from_dict(cls, d: dict) -> "UncertaintyCfg":
        return cls(**_strict_from_dict(cls, "uncertainty", d))


@dataclass(frozen=True)
class ReportCfg:
    enabled:        bool  = True
    formats:        tuple = ("html", "pdf")
    title:          str   = "CdA estimation report"
    include_config: bool  = True                # config + cyclist summary
    figure_dpi:     int   = 150

    def __post_init__(self):
        for fmt in self.formats:
            _check_choice("report.formats[]", fmt, REPORT_FORMATS)

    @classmethod
    def from_dict(cls, d: dict) -> "ReportCfg":
        return cls(**_strict_from_dict(cls, "report", d))


# ── YAML loading with ``extends`` ────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_raw(path: Path, _chain: tuple = ()) -> dict:
    path = Path(path).resolve()
    if path in _chain:
        raise ValueError(f"config: circular 'extends' at {path}")
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    parent = raw.pop("extends", None)
    if parent is None:
        return raw
    return _deep_merge(_load_raw(path.parent / parent, _chain + (path,)), raw)


@dataclass(frozen=True)
class AppConfig:
    mode:          str            = "velodrome"
    paths:         PathsCfg       = dc_field(default_factory=PathsCfg)
    cyclist:       CyclistCfg     = dc_field(default_factory=CyclistCfg)
    segment:       SegmentCfg     = dc_field(default_factory=SegmentCfg)
    preprocessing: PreprocCfg     = dc_field(default_factory=PreprocCfg)
    airspeed_calibration: AirspeedCalibrationCfg = dc_field(default_factory=AirspeedCalibrationCfg)
    velodrome:     VelodromeCfg   = dc_field(default_factory=VelodromeCfg)
    field:         FieldCfg       = dc_field(default_factory=FieldCfg)
    solver:        SolverCfg      = dc_field(default_factory=SolverCfg)
    uncertainty:   UncertaintyCfg = dc_field(default_factory=UncertaintyCfg)
    report:        ReportCfg      = dc_field(default_factory=ReportCfg)
    plot:          PlotCfg        = dc_field(default_factory=PlotCfg)

    def __post_init__(self):
        _check_choice("mode", self.mode, MODES)

    @property
    def mode_cfg(self):
        """The mode-specific section that is active for ``self.mode``."""
        return self.velodrome if self.mode == "velodrome" else self.field

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "AppConfig":
        raw = _load_raw(Path(yaml_path))

        return cls(
            mode=str(raw.get("mode", "velodrome")),
            paths=PathsCfg.from_dict(raw.get("paths", {})),
            cyclist=CyclistCfg.from_dict(raw.get("cyclist", {})),
            segment=SegmentCfg.from_dict(raw.get("segment", {})),
            preprocessing=PreprocCfg.from_dict(raw.get("preprocessing", {})),
            airspeed_calibration=AirspeedCalibrationCfg.from_dict(
                raw.get("airspeed_calibration", {})),
            velodrome=VelodromeCfg.from_dict(raw.get("velodrome", {})),
            field=FieldCfg.from_dict(raw.get("field", {})),
            solver=SolverCfg.from_dict(raw.get("solver", {})),
            uncertainty=UncertaintyCfg.from_dict(raw.get("uncertainty", {})),
            report=ReportCfg.from_dict(raw.get("report", {})),
            plot=PlotCfg.from_dict(raw.get("plot", {})),
          )
