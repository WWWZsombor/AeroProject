# src/cda/physics/energy.py
"""
Kinetic and potential energy powers.
Computed via the gradient of the energy with respect to time.
"""

from __future__ import annotations

import numpy as np


def kinetic_power(
    m_eff:  float,               # effective mass (incl. rotational)  kg
    v:      np.ndarray,          # ground speed                       m/s
    dt:     float = 1.0,         # time step                          s
) -> np.ndarray:
    """
    Power spent / released by the change in kinetic energy (W).

        E_kin(t) = ½ · m_eff · v²
        P_kin    = dE_kin / dt     (numerical gradient)
    """
    e_kin = 0.5 * m_eff * v ** 2
    return np.gradient(e_kin, dt)


def potential_power(
    mass:     float,             # total translational mass           kg
    g:        float,             # gravitational acceleration         m/s²
    altitude: np.ndarray,        # elevation                          m
    dt:       float = 1.0,       # time step                          s
) -> np.ndarray:
    """
    Power spent / released by the change in gravitational PE (W).

        E_pot(t) = m · g · h
        P_pot    = dE_pot / dt
    """
    e_pot = mass * g * altitude
    return np.gradient(e_pot, dt)
