# src/cda/physics/forces.py
"""
Three external forces acting on the cyclist-bike system.

All functions accept and return numpy arrays (element-wise).
"""

from __future__ import annotations

import numpy as np


def drag_force(
    rho:      float | np.ndarray,   # air density   kg/m³
    cda:      float,                # Cd · A        m²
    v_rel:    float | np.ndarray,   # relative air speed  m/s  (v_ground + wind)
) -> np.ndarray:
    """
    Aerodynamic drag force (N).

        F_drag = ½ · ρ · CdA · v_rel²
    """
    return 0.5 * rho * cda * v_rel ** 2


def rolling_force(
    c_rr:  float,                # rolling-resistance coefficient  –
    mass:  float,                # total translational mass        kg
    g:     float,                # gravitational acceleration      m/s²
    theta: float | np.ndarray,   # incline angle                  rad
) -> np.ndarray:
    """
    Rolling-resistance force (N).

        F_rr = c_rr · m · g · cos(θ)
    """
    return c_rr * mass * g * np.cos(theta)


def gravity_force(
    mass:  float,                # total translational mass        kg
    g:     float,                # gravitational acceleration      m/s²
    theta: float | np.ndarray,   # incline angle                  rad
) -> np.ndarray:
    """
    Gravity component along the direction of travel (N).
    Positive on an uphill.

        F_gravity = m · g · sin(θ)
    """
    return mass * g * np.sin(theta)
