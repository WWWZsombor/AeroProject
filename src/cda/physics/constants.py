# src/cda/physics/constants.py
"""Physical constants used across the project."""

# Standard gravity  (m / s²)
G:       float = 9.80665

# Specific gas constant – dry air   (J / (kg · K))
R_DRY:   float = 287.05

# Specific gas constant – water vapour   (J / (kg · K))
R_VAPOR: float = 461.495

# Saturation-pressure polynomial coefficients (mbar, °C)
# Source:  https://wahiduddin.net/calc/density_altitude.htm
_ES_COEFFS: list[tuple[float, float]] = [
    (  0.99999683,           0),
    ( -0.90826951e-2,       1),
    (  0.78736169e-4,       2),
    ( -0.61117958e-6,       3),
    (  0.43884187e-8,       4),
    ( -0.29883885e-10,      5),
    (  0.21874425e-12,      6),
    ( -0.17892321e-14,      7),
    (  0.11112018e-16,      8),
    ( -0.30994571e-19,      9),
]
_ES_BASE: float = 6.1078   # mbar
