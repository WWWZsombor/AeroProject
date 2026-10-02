# src/cda/physics/__init__.py
"""
cda.physics
===========
Pure-math package.  No I/O, no pandas, no plotting.
Every function is a scalar or element-wise numpy operation.
"""

from .constants   import G, R_DRY, R_VAPOR
from .forces      import drag_force, rolling_force, gravity_force
from .energy      import kinetic_power, potential_power
from .air_density import calculate_air_density
from .equations   import assemble_power_balance

__all__ = [
    "G", "R_DRY", "R_VAPOR",
    "drag_force", "rolling_force", "gravity_force",
    "kinetic_power", "potential_power",
    "calculate_air_density",
    "assemble_power_balance",
]
