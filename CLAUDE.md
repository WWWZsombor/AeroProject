# AeroProject – CLAUDE.md

End-to-end cyclist CdA estimator: Notio JSON → segments → preprocessing → solvers → uncertainty → HTML/PDF report.
README.md holds the current project status; update it at each milestone.

## Environment / commands
- Python 3.9, conda env `aero_env`. Install: `pip install -e . --no-build-isolation`
- Run: `python run.py config/<file>.yaml` or `python -m cda.pipeline.main config/<file>.yaml`
- Tests: `pip install -e .[dev] --no-build-isolation`, then `pytest tests/ -v` (synthetic ground-truth tests must pass before committing solver changes)
- Interface is CLI + YAML only (no GUI for now).

## Architecture rules
- Everything tunable lives in YAML (`config/`); no hard-coded paths, thresholds, masses or colours in code.
  Only `pipeline/config_loader.py` reads YAML; config objects are frozen dataclasses.
  `config/default.yaml` is the full reference; `velodrome.yaml` / `field.yaml` use `extends:` and list only differences.
  New config keys: add to the dataclass + `default.yaml`; unknown keys and invalid choices must raise a clear error.
- Layers: `utils/io` (json/pandas only) · `physics` (pure numpy, no I/O/pandas) · `preprocessing` · `solvers`
  · `postprocessing` (statistics, plots, report) · `pipeline` (thin orchestration only).
- Calculations are pure functions: DataFrame/array in → new object out; never mutate inputs.
- Solvers implement `BaseSolver`, are registered in `solvers/registry.py`, are selected in YAML, and return a
  `SolverResult` (CdA, uncertainty/distribution, diagnostics). Solve CdA only.
  Planned solvers: OLS, Chung (virtual elevation), Kalman filter, Gaussian-process regression; others welcome.
- Every solver reports uncertainty: analytic CI where available, plus bootstrap/Monte Carlo distribution.
  Results are compared in a cross-solver agreement table.
- Report code only consumes the serialisable `RunResult`; no calculation inside HTML/PDF code. HTML is the
  primary report (self-contained, embedded plots); PDF is generated from the same data (CLI flag).
- `mode: velodrome | field` is chosen in YAML only; mode differences live in config + preprocessing, not forks.
  - velodrome: runs with and without wind; speed also from cadence × fixed gear ratio × wheel circumference;
    separate straights from bends (high-g) via gyro/IMU (`valid` column; solvers use valid rows only).
  - Airspeed calibration is PER SETUP (one fit per measurement file, overrides per test_id in YAML): flow at the
    sensor depends on position/equipment. Never reuse one global scale/offset.
  - field: wind from airspeed sensor, incline/altitude included in the power balance.
- Device-computed CdA columns (rawCDA, ekfCDA, CDA) are ignored: never an input, never a reference.

## Units & data conventions
- SI inside physics/solvers (m/s, W, Pa, kg/m³, rad). BCVX `speed` is km/h, RideData `speed` is m/s – convert once, early.
- Wind: `v_rel = v + v_wind`, `v_wind` = headwind component. Keep this convention consistent and tested.
- Never filter across segment gaps; filter per segment on one uniform time grid (no NaN-heavy 1 Hz/4 Hz merges).

## Code style
- `from __future__ import annotations`; Python 3.9-compatible type hints; NumPy-style docstrings with units.
  Every function states what it computes, the equation, and units – calculations must be easy to follow.
- Match surrounding style: snake_case, `Cfg` suffix for config classes, `_private` helpers, `logging` (not print).
- Plot style: dark cyberpunk palette taken from YAML (`plot.palette`).

## Testing
- Unit tests in `tests/` mirror `src/cda/`.
- Synthetic ground-truth rides (known CdA + noise/wind) validate every solver.

## Git / housekeeping
- Plain sentence-case commit messages, one milestone per commit.
- Do not commit generated data (`output/`, `processed/`, output CSVs, `__pycache__`, `.DS_Store`, egg-info).
- Do not commit or push unless asked.

## Known issues / open points
- Steps 0–2 done (foundation, config, velodrome preprocessing + per-setup airspeed calibration). `solver`/`uncertainty`/`report` and `field.incline_source` are parsed but not used yet.
- Wheel speed (cadence × gear) deviates 2–4 % from sensor speed in some segments (steady ones match at ratio 4.00); default speed_source stays `sensor`.
- `config/field.yaml` segment values are user-edited placeholders (test data is velodrome-like, ~47 km/h).
- Step 0 done (clean per-segment 4 Hz grid, wind sign, calibration, relative paths, tests).
- `incline_angle` is not in the data → 0 (field mode needs incline from altitude/IMU).
- Airspeed calibration assumes zero mean wind; scale-only by default (offset not identifiable at ~13 m/s steady speed).
- Drivetrain loss is not modelled (pedal power is used as wheel power).
- Generated/cached files committed earlier are still tracked: `git rm -r --cached` them (pyc, egg-info, .DS_Store).
