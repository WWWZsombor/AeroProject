import numpy as np
import pandas as pd
import pytest

from cda.physics.air_density import calculate_air_density
from cda.physics.equations import assemble_power_balance
from cda.pipeline.config_loader import AirspeedCalibrationCfg, AppConfig, VelodromeCfg
from cda.pipeline.preprocess_stage import preprocess_test, wind_runs
from cda.preprocessing import (
    AirspeedCalibration, detect_bends, fit_airspeed_calibration, flag_bends,
    preprocess_segment, resolve_airspeed_calibration, select_speed, wheel_speed,
)
from conftest import make_segment, DT, RHO

FS = 1.0 / DT


# ── speed sources ────────────────────────────────────────────────────

def test_wheel_speed_formula():
    # 90 rpm · ratio 4 · 2.1 m = 12.6 m/s
    assert wheel_speed(90, 4.0, 2.1) == pytest.approx(12.6)


def test_select_speed_sources(cyclist):
    seg = make_segment(cyclist, v=13.0)
    seg["cadence"] = 13.0 * 60 / (4.0 * 2.095) * 1.0      # consistent with ratio 4
    kw = dict(gear_ratio=4.0, wheel_circumference=2.095)
    assert np.allclose(select_speed(seg, "sensor", **kw)["v"], 13.0)
    assert np.allclose(select_speed(seg, "wheel", **kw)["v"], 13.0)
    seg["cadence"] *= 1.04                                   # wheel 4 % faster
    both = select_speed(seg, "both", **kw)
    assert np.allclose(both["v"], 13.0 * 1.02)
    assert np.allclose(both["v_wheel"], 13.0 * 1.04)


def test_select_speed_needs_cadence(cyclist):
    with pytest.raises(ValueError, match="cadence"):
        select_speed(make_segment(cyclist), "wheel", 4.0, 2.095)


# ── bends ────────────────────────────────────────────────────────────

def _yaw_frame(cyclist, bend_from=240, bend_to=480, n=960, yaw=35.0):
    seg = make_segment(cyclist, n=n)
    seg["v"] = 13.0
    seg["gyrZ"] = 0.0
    seg.loc[bend_from:bend_to - 1, "gyrZ"] = yaw
    return seg


def test_detect_bends():
    yaw = np.zeros(400); yaw[100:200] = 40.0
    smooth, bend = detect_bends(yaw, FS, 15.0, 1.0)
    assert bend[120:180].all() and not bend[:90].any() and not bend[210:].any()


def test_bend_handling_modes(cyclist):
    df = _yaw_frame(cyclist)
    ex = flag_bends(df, VelodromeCfg(bend_handling="exclude"), FS)
    assert not ex["valid"].iloc[260:460].any() and ex["valid"].iloc[:200].all()
    assert (ex["load_factor"] == 1.0).all()

    co = flag_bends(df, VelodromeCfg(bend_handling="correct"), FS)
    assert co["valid"].all()
    a_c = 13.0 * np.deg2rad(35.0)                            # ≈ 7.9 m/s²
    assert co["load_factor"].iloc[300] == pytest.approx(np.sqrt(1 + (a_c / 9.80665) ** 2), rel=1e-3)
    assert co["load_factor"].iloc[50] == pytest.approx(1.0)

    ke = flag_bends(df, VelodromeCfg(bend_handling="keep"), FS)
    assert ke["valid"].all() and (ke["load_factor"] == 1.0).all()


def test_short_straights_are_excluded(cyclist):
    df = _yaw_frame(cyclist, 0, 960)                          # all bend ...
    df.loc[100:107, "gyrZ"] = 0.0                              # ... 2 s straight
    out = flag_bends(df, VelodromeCfg(bend_handling="exclude", min_straight_sec=3.0), FS)
    assert not out["valid"].any()


def test_missing_yaw_column_means_all_straight(cyclist):
    out = flag_bends(make_segment(cyclist).assign(v=13.0), VelodromeCfg(), FS)
    assert out["valid"].all() and not out["is_bend"].any()


def test_load_factor_raises_rolling_resistance(cyclist):
    pp = preprocess_segment(make_segment(cyclist), cyclist, dt=DT)
    base = assemble_power_balance(pp, cyclist, dt=DT)
    pp["load_factor"] = 1.5
    bent = assemble_power_balance(pp, cyclist, dt=DT)
    assert np.allclose(bent["F_rolling"], 1.5 * base["F_rolling"])


# ── airspeed calibration: per setup ──────────────────────────────────

def _ride(gain, n=2400, seed=0, speeds=(10.0, 12.0, 14.0, 13.0)):
    """Ride at several steady speeds; raw pitot airspeed = true / gain."""
    rng = np.random.default_rng(seed)
    v = np.repeat(speeds, n // len(speeds))
    df = pd.DataFrame({
        "SECS": np.arange(n) * DT, "v": v,
        "temperature": 20.0, "pressure": 101325.0, "humidity": 50.0,
    })
    rho = calculate_air_density(df.temperature.values, df.pressure.values, df.humidity.values)
    raw = v / gain + rng.normal(0, 0.02, n)
    df["dyn_press"] = 0.5 * rho * raw ** 2 * 100.0
    return df


@pytest.mark.parametrize("gain", [0.93, 1.0, 1.08])
def test_fit_recovers_setup_gain(gain):
    cfg = AirspeedCalibrationCfg()
    cal = fit_airspeed_calibration(_ride(gain), cfg, "setup", FS)
    assert cal.method == "fit" and cal.offset == 0.0
    assert cal.scale == pytest.approx(gain, rel=0.01)
    assert cal.rmse_after < cal.rmse_before or gain == 1.0


def test_each_setup_gets_its_own_calibration():
    cfg = AirspeedCalibrationCfg()
    a = resolve_airspeed_calibration(_ride(0.95), cfg, "A", FS)
    b = resolve_airspeed_calibration(_ride(1.07), cfg, "B", FS)
    assert a.scale == pytest.approx(0.95, rel=0.01) and b.scale == pytest.approx(1.07, rel=0.01)
    assert (a.setup, b.setup) == ("A", "B")


def test_override_wins_over_fit_and_none_is_identity():
    ride = _ride(0.95)
    cfg = AirspeedCalibrationCfg(overrides={"A": {"scale": 1.2, "offset": 0.1}})
    cal = resolve_airspeed_calibration(ride, cfg, "A", FS)
    assert (cal.method, cal.scale, cal.offset) == ("override", 1.2, 0.1)
    other = resolve_airspeed_calibration(ride, cfg, "B", FS)    # no override for B → fitted
    assert other.method == "fit"
    ident = resolve_airspeed_calibration(ride, AirspeedCalibrationCfg(method="none"), "B", FS)
    assert (ident.method, ident.scale, ident.offset) == ("identity", 1.0, 0.0)


def test_scale_offset_needs_speed_range():
    narrow = _ride(1.05).assign(v=lambda d: 13.0 + 0.0 * d.v)    # constant speed
    narrow["dyn_press"] = 0.5 * 1.2 * (13.0 / 1.05) ** 2 * 100
    cfg = AirspeedCalibrationCfg(fit="scale_offset")
    assert fit_airspeed_calibration(narrow, cfg, "s", FS).fit == "scale"      # fallback
    wide = fit_airspeed_calibration(_ride(1.05), cfg, "s", FS)
    assert wide.fit == "scale_offset"


def test_straight_mask_and_too_few_points():
    ride = _ride(1.05)
    mask = np.zeros(len(ride), dtype=bool); mask[:10] = True
    cal = fit_airspeed_calibration(ride, AirspeedCalibrationCfg(), "s", FS, straight=mask)
    assert cal.method == "fit-failed" and cal.scale == 1.0


def test_calibration_apply():
    cal = AirspeedCalibration(scale=1.1, offset=-0.5)
    assert cal.apply(np.array([10.0]))[0] == pytest.approx(10.5)


# ── stage: runs + calibration through preprocess_test ───────────────

def _cfg(tmp_path, extra=""):
    p = tmp_path / "c.yaml"
    p.write_text("mode: velodrome\n" + extra)
    return AppConfig.from_yaml(p)


def _full_ride(gain, cyclist):
    df = _ride(gain, n=1200, speeds=(11.0, 13.0, 14.0, 13.0))
    return df.assign(speed=df["v"] * 3.6, power=300.0, altitude=10.0, gyrZ=0.0)


def test_preprocess_test_runs_and_calibration(tmp_path, cyclist):
    cfg = _cfg(tmp_path)
    assert wind_runs(cfg) == ("no_wind", "with_wind")
    full = _full_ride(1.06, cyclist)
    seg = full.iloc[900:1140].reset_index(drop=True)          # steady 13 m/s part
    runs, cals = preprocess_test("A", [seg], full, cfg, cyclist)
    assert cals[0].scale == pytest.approx(1.06, rel=0.01)
    assert (runs["no_wind"]["v_wind"] == 0).all()
    # calibrated sensor reads ground speed → remaining wind ≈ 0
    assert abs(runs["with_wind"]["v_wind"].mean()) < 0.1
    assert runs["with_wind"]["valid"].all()


def test_segment_scope_calibrates_each_segment(tmp_path, cyclist):
    cfg = _cfg(tmp_path, "airspeed_calibration:\n  scope: segment\n  min_points: 20\n")
    full = _full_ride(1.06, cyclist)
    segs = [full.iloc[0:300].reset_index(drop=True), full.iloc[600:900].reset_index(drop=True)]
    _, cals = preprocess_test("A", segs, full, cfg, cyclist)
    assert [c.setup for c in cals] == ["A/seg0", "A/seg1"]


def test_field_mode_runs(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text("mode: field\nfield:\n  wind_source: none\n")
    assert wind_runs(AppConfig.from_yaml(p)) == ("no_wind",)
