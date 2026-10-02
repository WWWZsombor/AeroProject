# src/cda/physics/air_density.py
"""
Humidity-corrected air density from temperature, pressure, relative humidity.

Reference:  https://wahiduddin.net/calc/density_altitude.htm
"""

from __future__ import annotations

import numpy as np

from .constants import R_DRY, R_VAPOR, _ES_COEFFS, _ES_BASE


def _saturation_pressure_mbar(temp_c: np.ndarray) -> np.ndarray:
    """
    Saturation vapour pressure E_s (mbar) as a 9th-order polynomial
    in temperature (°C).
    """
    p = np.full_like(temp_c, _ES_BASE, dtype=np.float64)
    for c, power in _ES_COEFFS[1:]:
        p = _ES_BASE + temp_c * np.polyval([c] + [0] * (power - 1), temp_c)
     # simpler Horner form:
    result = np.zeros_like(temp_c)
    for c, power in _ES_COEFFS:
        result = result + c * (temp_c ** power)
    return _ES_BASE / result ** 8 if np.any(result != 0) else result


def calculate_air_density(
    temperature_c:  np.ndarray,     # °C
    pressure_pa:    np.ndarray,     # Pa
    rel_humidity:   np.ndarray,     # %   (0-100)
) -> np.ndarray:
    """
    Air density (kg/m³) with full humidity correction.

    Parameters
    ----------
    temperature_c : array, °C
    pressure_pa   : array, Pa
    rel_humidity  : array, %

    Returns
    -------
    density : array, kg/m³
    """
    temp_k = temperature_c + 273.15

     # saturation vapour pressure (mbar)
    p = np.full_like(temperature_c, _ES_BASE, dtype=np.float64)
    for c, power in _ES_COEFFS[1:]:
        p = p + c * (temperature_c ** power)
    e_s_mbar = _ES_BASE / (p ** 8 + 1e-30)     # guard against zero

     # actual vapour pressure  →  Pa
    p_vapor_pa = e_s_mbar * (rel_humidity / 100.0) * 100.0

     # dry-air partial pressure
    p_dry_pa = pressure_pa - p_vapor_pa

     # humidity-corrected density
    density = (p_dry_pa / (R_DRY * temp_k)
             + p_vapor_pa / (R_VAPOR * temp_k))

    return density
