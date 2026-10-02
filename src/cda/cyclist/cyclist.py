# src/cda/cyclist/cyclist.py
"""
cda.cyclist
===========
Single dataclass that carries every physical parameter of the
cyclist + bike system.  Used by:

  • physics.equations   – to assemble the power-balance system
  • preprocessing.segment_preprocess  – to compute E_kin, E_pot
  • (future) solvers     – to know m, c_rr, wheel_r before solving

The class is a **frozen dataclass**:  create it once, pass it around,
never mutate it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


# ── public ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Cyclist:
    """
    Physical model of the cyclist + bicycle system.

    Parameters
    ----------
    body_mass : float
        Mass of the cyclist in kg.
    bike_weight : float
        Mass of the bicycle (frame + drivetrain + everything) in kg.
    wheel_mass : float
        Mass of **one** wheel (rim + tyre + hub + spokes) in kg.
    n_wheels : int
        Number of wheels (normally 2).
    wheel_circumference : float
        Rolling circumference of one wheel in metres.
    tyre_crr : float
        Rolling-resistance coefficient of the tyre (dimensionless).
    aerodynamic_position : str
        One of {"dropbar", "bars", "tuck"}.
        Used later by solvers as a prior or label.
    """

    # ── primary inputs ──────────────────────────────────────────────
    body_mass:           float = 72.0
    bike_weight:         float = 8.5
    wheel_mass:          float = 0.90
    n_wheels:            int   = 2
    wheel_circumference: float = 2.095
    tyre_crr:            float = 0.004
    aerodynamic_position: str  = "dropbar"

    # ── derived (computed, never set by the user) ───────────────────

    @property
    def total_mass(self) -> float:
        """Translational mass of the system (kg)."""
        return self.body_mass + self.bike_weight

    @property
    def wheel_radius(self) -> float:
        """Mean rolling radius of one wheel (m)."""
        return self.wheel_circumference / (2.0 * math.pi)

    @property
    def rotational_inertia(self) -> float:
        """
        Total rotational moment of inertia of all wheels (kg·m²).
        Thin-ring (annulus) approximation:  I = n · m_w · r²
        """
        return self.n_wheels * self.wheel_mass * self.wheel_radius ** 2

    @property
    def effective_mass(self) -> float:
        """
        Equivalent translational mass that includes the rotational
        contribution of the wheels, suitable for E_kin = ½ m_eff v².

            m_eff = m_total + I / r²   (thin-ring)
                  = m_total + n · m_w
        """
        return self.total_mass + self.rotational_inertia / self.wheel_radius ** 2

    @property
    def c_rr(self) -> float:
        """Convenience alias – total rolling-resistance coefficient."""
        return self.tyre_crr

    # ── class factory ───────────────────────────────────────────────

    @classmethod
    def from_config_dict(cls, d: dict) -> "Cyclist":
        """Create from a flat dict (the ``cyclist`` block of the YAML)."""
        return cls(
            body_mass=float(d.get("body_mass", 72.0)),
            bike_weight=float(d.get("bike_weight", 8.5)),
            wheel_mass=float(d.get("wheel_mass", 0.90)),
            n_wheels=int(d.get("n_wheels", 2)),
            wheel_circumference=float(d.get("wheel_circumference", 2.095)),
            tyre_crr=float(d.get("tyre_crr", 0.004)),
            aerodynamic_position=str(d.get("aerodynamic_position", "dropbar")),
         )

    # ── repr ────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Cyclist\n"
            f"  body_mass          = {self.body_mass:.1f} kg\n"
            f"  bike_weight        = {self.bike_weight:.1f} kg\n"
            f"  total_mass         = {self.total_mass:.1f} kg\n"
            f"  wheel_mass         = {self.wheel_mass:.2f} kg ×{self.n_wheels}\n"
            f"  wheel_radius       = {self.wheel_radius:.4f} m\n"
            f"  rotational_inertia = {self.rotational_inertia:.4f} kg·m²\n"
            f"  effective_mass     = {self.effective_mass:.1f} kg\n"
            f"  c_rr               = {self.c_rr:.4f}\n"
            f"  position           = {self.aerodynamic_position}"
         )
