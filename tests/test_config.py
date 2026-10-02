import os

import pytest
import yaml

from cda.pipeline.config_loader import AppConfig, SolverCfg, VelodromeCfg

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def _write(tmp_path, text, name="c.yaml"):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


@pytest.mark.parametrize("name,mode", [("default.yaml", "velodrome"),
                                       ("velodrome.yaml", "velodrome"),
                                       ("field.yaml", "field")])
def test_shipped_configs_load(name, mode):
    cfg = AppConfig.from_yaml(os.path.join(CONFIG_DIR, name))
    assert cfg.mode == mode
    assert cfg.solver.enabled == ("ols", "chung", "kalman", "gp")
    assert cfg.mode_cfg is (cfg.velodrome if mode == "velodrome" else cfg.field)


def test_extends_overrides_only_what_differs():
    base = AppConfig.from_yaml(os.path.join(CONFIG_DIR, "default.yaml"))
    fld = AppConfig.from_yaml(os.path.join(CONFIG_DIR, "field.yaml"))
    assert fld.mode == "field" and base.mode == "velodrome"
    assert fld.segment.min_speed != base.segment.min_speed      # overridden in field.yaml
    assert fld.segment.segment_num == base.segment.segment_num  # inherited
    assert fld.cyclist == base.cyclist           # inherited untouched
    assert fld.plot == base.plot


def test_extends_cycle_is_detected(tmp_path):
    _write(tmp_path, "extends: b.yaml\n", "a.yaml")
    _write(tmp_path, "extends: a.yaml\n", "b.yaml")
    with pytest.raises(ValueError, match="circular"):
        AppConfig.from_yaml(tmp_path / "a.yaml")


@pytest.mark.parametrize("text,match", [
    ("mode: swimming\n", "mode"),
    ("solver:\n  enabled: []\n", "at least one"),
    ("solver:\n  cda_initial: 2.0\n", "cda_bounds"),
    ("solver:\n  enabled: [ols]\n  options: {kalman: {}}\n", "not in solver.enabled"),
    ("solver:\n  enable: [ols]\n", "unknown key"),            # typo
    ("uncertainty:\n  confidence_level: 95\n", "confidence_level"),
    ("uncertainty:\n  bootstrap_method: fancy\n", "bootstrap_method"),
    ("velodrome:\n  bend_handling: ignore\n", "bend_handling"),
    ("velodrome:\n  wind_runs: [gale]\n", "wind_runs"),
    ("field:\n  incline_source: gps\n", "incline_source"),
    ("report:\n  formats: [docx]\n", "formats"),
])
def test_invalid_config_gives_clear_error(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        AppConfig.from_yaml(_write(tmp_path, text))


def test_gear_ratio():
    assert VelodromeCfg(chainring_teeth=60, cog_teeth=15).gear_ratio == 4.0


@pytest.mark.parametrize("text,match", [
    ("airspeed_calibration:\n  method: magic\n", "method"),
    ("airspeed_calibration:\n  fit: cubic\n", "fit"),
    ("airspeed_calibration:\n  scope: ride\n", "scope"),
    ("airspeed_calibration:\n  overrides:\n    A: {gain: 1.1}\n", "unknown key"),
    ("airspeed_calibration:\n  scale: 1.1\n", "unknown key"),
])
def test_invalid_airspeed_calibration_config(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        AppConfig.from_yaml(_write(tmp_path, text))


def test_airspeed_overrides_are_per_setup(tmp_path):
    cfg = AppConfig.from_yaml(_write(
        tmp_path, "airspeed_calibration:\n  overrides:\n    A: {scale: 1.05}\n    B: {scale: 0.97, offset: 0.2}\n"))
    assert cfg.airspeed_calibration.overrides["A"] == {"scale": 1.05}
    assert cfg.airspeed_calibration.overrides["B"]["offset"] == 0.2
