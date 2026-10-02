"""Shared fixtures: small synthetic rides with a known CdA."""

import numpy as np
import pandas as pd
import pytest

from cda.cyclist.cyclist import Cyclist
from cda.physics.constants import G

TRUE_CDA = 0.25
RHO = 1.20
V = 13.0           # m/s
DT = 0.25          # s  (4 Hz, like the Notio)


@pytest.fixture
def cyclist():
    return Cyclist()


def make_segment(cyclist, n=240, v=V, headwind=0.0, cda=TRUE_CDA, t0=100.0):
    """Constant-speed, flat 4 Hz segment whose power follows the physics."""
    secs = t0 + DT * np.arange(n)
    p_aero = 0.5 * RHO * cda * (v + headwind) ** 2 * v
    p_roll = cyclist.c_rr * cyclist.total_mass * G * v
    dyn_press_raw = 0.5 * RHO * (v + headwind) ** 2 * 100.0  # 0.01 Pa units
    return pd.DataFrame({
        "SECS": secs,
        "speed": np.full(n, v * 3.6),                         # km/h
        "power": np.full(n, p_aero + p_roll),
        "altitude": np.full(n, 10.0),
        "temperature": np.full(n, 20.0),
        "pressure": np.full(n, 101325.0),
        "humidity": np.full(n, 50.0),
        "dyn_press": np.full(n, dyn_press_raw),
    })
