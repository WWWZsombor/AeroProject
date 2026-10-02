import numpy as np
import pandas as pd

from cda.preprocessing import (
    preprocess_segment, group_files_by_type, load_segments, correct_altitude,
)
from cda.physics.equations import assemble_power_balance
from cda.utils.io import merge_ride_bcvx, save_combined_csvs, remove_segment_csvs
from conftest import make_segment, TRUE_CDA, DT


def test_speed_converted_once_to_ms(cyclist):
    pp = preprocess_segment(make_segment(cyclist, v=13.0), cyclist, dt=DT)
    assert np.allclose(pp["v"], 13.0)
    assert not pp.isna().any().any()


def test_wind_sign_headwind_positive(cyclist):
    pp = preprocess_segment(make_segment(cyclist, headwind=2.0), cyclist, dt=DT)
    assert pp["v_wind"].mean() > 0            # airspeed > ground speed
    pp = preprocess_segment(make_segment(cyclist, headwind=-2.0), cyclist, dt=DT)
    assert pp["v_wind"].mean() < 0


def test_device_wind_column_is_ignored(cyclist):
    seg = make_segment(cyclist)
    seg["wind"] = 5.0
    pp = preprocess_segment(seg, cyclist, dt=DT)
    assert abs(pp["v_wind"].mean()) < 0.05


def test_preprocess_is_pure(cyclist):
    seg = make_segment(cyclist)
    before = seg.copy()
    preprocess_segment(seg, cyclist, dt=DT)
    pd.testing.assert_frame_equal(seg, before)


def test_power_balance_recovers_true_cda(cyclist):
    """residual power = aero power  →  residual / (½ρ v³) = CdA."""
    for headwind in (0.0, 1.5):
        pp = preprocess_segment(make_segment(cyclist, headwind=headwind),
                                cyclist, dt=DT)
        bal = assemble_power_balance(pp, cyclist, dt=DT, cda_guess=TRUE_CDA)
        mid = bal.iloc[20:-20]
        assert np.allclose(mid["P_residual"], mid["P_aero_model"], rtol=0.02)


def test_climb_not_double_counted(cyclist):
    seg = make_segment(cyclist)
    grade = 0.03
    seg["altitude"] = 10.0 + grade * 13.0 * (seg["SECS"] - seg["SECS"].iloc[0])
    seg["power"] += cyclist.total_mass * 9.80665 * grade * 13.0
    seg["incline_angle"] = np.degrees(np.arctan(grade))
    pp = preprocess_segment(seg, cyclist, dt=DT)
    bal = assemble_power_balance(pp, cyclist, dt=DT, cda_guess=TRUE_CDA)
    mid = bal.iloc[20:-20]
    assert np.allclose(mid["P_residual"], mid["P_aero_model"], rtol=0.05)


def test_merge_ride_bcvx_is_gap_free():
    secs = np.arange(0, 10, 0.25)
    ride = pd.DataFrame({"SECS": secs, "KM": 1.0, "power": 300, "speed": 13.0})
    bcvx = pd.DataFrame({"SECS": secs, "KM": 2.0, "power": 300,
                         "speed": 46.8, "humidity": 45.0})
    m = merge_ride_bcvx(ride, bcvx)
    assert len(m) == len(secs) and not m.isna().any().any()
    assert (m["speed"] == 46.8).all() and (m["speed_ride"] == 13.0).all()
    assert (m["KM"] == 1.0).all() and "humidity" in m


def test_group_and_load_segments_keep_segments_apart(tmp_path, cyclist):
    for idx, t0 in enumerate((100.0, 300.0)):
        seg = make_segment(cyclist, t0=t0)
        ride = seg.rename(columns={"speed": "speed"})
        save_combined_csvs(ride, seg, str(tmp_path), "ride_a", idx)
    save_combined_csvs(ride, seg, str(tmp_path), "stale", 0)

    groups = group_files_by_type(tmp_path, ["ride_a"])
    assert list(groups) == ["ride_a"]
    segs = load_segments(groups)["ride_a"]
    assert [s["SECS"].iloc[0] for s in segs] == [100.0, 300.0]

    assert remove_segment_csvs(str(tmp_path), "ride_a") == 2
    assert (tmp_path / "stale_combined_0.csv").exists()


def test_correct_altitude_removes_linear_drift():
    n = 200
    df = pd.DataFrame({"SECS": np.arange(n) / 4.0,
                       "KM": np.linspace(0, 1, n),
                       "altitude": 5.0 + np.linspace(0, 3, n)})   # pure drift
    out = correct_altitude(df)
    assert np.ptp(out["altitude"]) < 0.5
    assert list(df["altitude"][:2]) == [5.0, 5.0 + 3 / (n - 1)]   # input untouched
