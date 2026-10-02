# AeroProject – Cyclist CdA Measurement Pipeline

> **Status:** active development · **checkpoint v0.2**
> Python 3.9 · conda · single-config-file driven

AeroProject processes raw cycling-ergometer measurement files (JSON) to
extract the cyclist's **Coefficient of Drag × Frontal Area (CdA)**.
The pipeline reads one or more JSON files, cleans the signal, locates the
most consistent speed / power windows, groups the per-segment CSVs back into
per-ride DataFrames, pre-processes them with a physical model, and renders a
cyberpunk-styled overview figure.

---

## Table of Contents

- [1 – Pipeline Overview](#1--pipeline-overview)
- [2 – Project Structure](#2--project-structure)
- [3 – Installation](#3--installation)
- [4 – Configuration](#4--configuration)
- [5 – Usage](#5--usage)
- [6 – Module Reference](#6--module-reference)
  - [6.1 `cda.cyclist`](#61-cdacyclist)
  - [6.2 `cda.physics`](#62-cdaphysics)
  - [6.3 `cda.preprocessing`](#63-cdapreprocessing)
  - [6.4 `cda.postprocessing`](#64-cdapostprocessing)
  - [6.5 `cda.utils.io`](#65-cdautilsio)
  - [6.6 `cda.pipeline`](#66-cdapipeline)
- [7 – Preprocessed Output Schema](#7--preprocessed-output-schema)
- [8 – Plotting](#8--plotting)
- [9 – Development](#9--development)
- [10 – Roadmap](#10--roadmap)
- [11 – Dependencies](#11--dependencies)
- [12 – License](#12--license)

---

## 1 – Pipeline Overview

```text
config/default.yaml
        │
        ▼
AppConfig ──► CyclistCfg ──► Cyclist (physical parameters)
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│  STAGE 1 – per JSON file                                   │
│                                                            │
│  io.load_ride_json                                         │
│        │                                                   │
│        ▼                                                   │
│  calibration (optional, YAML-gated)                        │
│        │                                                   │
│        ▼                                                   │
│  speed_correction                                          │
│        │                                                   │
│        ▼                                                   │
│  SegmentFinder.find ──► [(t₀,t₁), …]  time-sorted          │
│        │                                                   │
│        ▼                                                   │
│  io.save_segment_csvs + io.save_combined_csvs              │
│                                                            │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────┐
│  STAGE 2 – per test_id, after all JSONs processed          │
│                                                            │
│  file_grouping.group_files_by_type(output_csv)             │
│        │                                                   │
│        ▼                                                   │
│  file_grouping.load_and_merge ──► merged DataFrame         │
│        │                                                   │
│        ▼                                                   │
│  preprocess_segment(df, cyclist, dt, cfg)                  │
│        │                                                   │
│        ├── butter (v, P, incline, T, p, airspeed)          │
│        ├── physics.energy (P_kinetic, P_potential)         │
│        ├── physics.air_density (humidity-corrected ρ)      │
│        ├── wind estimate (airspeed − groundspeed)          │
│        │                                                   │
│        ▼                                                   │
│  preprocessed CSV → output_preprocessed/                   │
│                                                            │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────┐
│  STAGE 3 – visualisation                                   │
│                                                            │
│  plot_segments ──► segments.png / .svg                     │
│                                                            │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────┐
│  FUTURE – cda.solvers (NOT yet implemented)                │
│                                                            │
│  input : preprocessed DataFrame + Cyclist                  │
│  task  : fit CdA (and optionally c_rr)                     │
│  model : P_residual = ½ρ·CdA·v_rel²·v + noise              │
└────────────────────────────────────────────────────────────┘
```

**Design rule:** every tunable parameter lives in `config/default.yaml`.
No hard-coded paths, thresholds, masses, or colours exist in the Python source.

---

## 2 – Project Structure

```text
AeroProject/
│
├── run.py                        # zero-install launcher
├── pyproject.toml                # package metadata + build config
├── .gitignore
├── README.md                     # ← this file
│
├── config/
│   └── default.yaml              # single source of truth
│
├── test/
│   └── input_file/               # measurement JSON files
│       ├── ride_01.json
│       ├── ride_02.json
│       └── processed/            # per-segment + combined CSVs
│
├── output/
│   └── output/
│       ├── segments.png          # overview figure
│       ├── segments.svg
│       └── preprocessed/         # clean, solver-ready DataFrames
│
├── scripts/
│   └── test_load.py              # dev smoke-test
│
└── src/cda/
    ├── __init__.py               # version = "0.2.0"
    │
    ├── cyclist/                  # NEW (v0.2)
    │   ├── __init__.py
    │   └── cyclist.py            # Cyclist dataclass
    │
    ├── physics/                  # NEW (v0.2)
    │   ├── __init__.py
    │   ├── constants.py          # G, R_DRY, R_VAPOR, poly coeffs
    │   ├── forces.py             # drag, rolling, gravity
    │   ├── energy.py             # kinetic, potential power
    │   ├── air_density.py        # humidity-corrected ρ
    │   └── equations.py          # assemble_power_balance
    │
    ├── preprocessing/
    │   ├── __init__.py           # updated exports
    │   ├── calibration.py        # accel · altitude · low-pass
    │   ├── segment_finder.py     # SegmentFinder · SegmentConfig
    │   ├── segment_preprocess.py # NEW: preprocess_segment + butter
    │   └── file_grouping.py      # NEW: group + merge by test_id
    │
    ├── postprocessing/
    │   ├── __init__.py
    │   └── plotting.py           # cyberpunk segment overview
    │
    ├── pipeline/
    │   ├── __init__.py
    │   ├── config_loader.py      # AppConfig + CyclistCfg + PreprocCfg
    │   └── main.py               # 3-stage orchestrator
    │
    └── utils/
        ├── __init__.py
        └── io.py                 # load_ride_json · save* · combined*
```

---

## 3 – Installation

### Option A – Editable install (recommended)

```bash
cd AeroProject
conda activate aero_env

pip install -e . --no-build-isolation
```

`--no-build-isolation` avoids a known Python 3.9 + setuptools conflict.
After this, `import cda` works from any directory.

### Option B – Zero-install

```bash
python run.py config/default.yaml
```

`run.py` injects `src/` into `sys.path` before importing.

### Verify

```bash
python -c "import cda; print(cda.__version__)"
# expected:  0.2.0
```

---

## 4 – Configuration

All parameters are in `config/default.yaml`. To run a different test, copy the
file, edit the copy, and point the command at it. No Python file is touched.

### 4.1 Full `default.yaml`

```yaml
# ───────────────────────────────────────────────────────────────────
#  AeroProject  ·  checkpoint v0.2
# ───────────────────────────────────────────────────────────────────

paths:
  raw_data:              /…/AeroProject/test/input_file
  output_csv:            /…/AeroProject/test/input_file/processed
  output_plots:          /…/AeroProject/test/output
  output_preprocessed:   /…/AeroProject/test/output/preprocessed

# ── physical model of the cyclist + bike ────────────────────────────
cyclist:
  body_mass:             72.0        # kg
  bike_weight:           8.5         # kg
  wheel_mass:            0.90        # kg  per wheel
  n_wheels:              2
  wheel_circumference:   2.095       # m   (700 × 25 c)
  tyre_crr:              0.004       # –   rolling-resistance coefficient
  aerodynamic_position:  dropbar     # dropbar | bars | tuck

# ── segment selection ───────────────────────────────────────────────
segment:
  interval_length_sec:   60
  min_speed:             45
  max_speed:             55
  segment_num:           4
  cost_speed:            0.5
  cost_power:            0.5

# ── preprocessing ───────────────────────────────────────────────────
preprocessing:
  calibrate_accelerometer: false
  calibrate_altitude:      false
  speed_correction:        1.0
  butter_cutoff_velocity:  0.01
  butter_cutoff_power:     0.01
  butter_cutoff_incline:   0.20
  butter_cutoff_env:       0.10
  butter_cutoff_airspeed:  0.01
  butter_order:            1

# ── plot ────────────────────────────────────────────────────────────
plot:
  speed_factor:          1.0
  fig_width:             12
  fig_height_per_row:    3.2
  dpi:                   150
  formats:               ["png", "svg"]
  show_segment_labels:   true
  show_glow:             true
  line_width_base:       1.0
  line_width_seg:        2.2
  palette:
    - "#00f0ff"          # seg_0  neon cyan
    - "#ff2d78"          # seg_1  neon pink
    - "#ff8c00"          # seg_2  neon orange
    - "#b026ff"          # seg_3  electric purple
    - "#39ff14"          # seg_4  neon green   (spare)
    - "#ffea00"          # seg_5  neon yellow  (spare)
# ───────────────────────────────────────────────────────────────────
```

### 4.2 Configuration cheatsheet

| Goal                             | YAML key to edit                              |
|----------------------------------|-----------------------------------------------|
| Fewer / more segments            | `segment.segment_num`                         |
| Longer / shorter windows         | `segment.interval_length_sec`                 |
| Speed data in m/s                | `plot.speed_factor: 3.6`                      |
| Disable glow                     | `plot.show_glow: false`                       |
| Swap a segment colour            | change the hex value in `plot.palette`        |
| Heavier rider                    | `cyclist.body_mass: 78.0`                     |
| Different tyre CRR               | `cyclist.tyre_crr: 0.006`                     |
| Enable accelerometer calibration | `preprocessing.calibrate_accelerometer: true` |
| Change filter aggressiveness     | `preprocessing.butter_cutoff_velocity`        |
| Different output folder          | `paths.output_preprocessed`                   |

---

## 5 – Usage

All three commands produce the same output.

```bash
# A – module call  (after pip install -e .)
python -m cda.pipeline.main config/default.yaml

# B – zero-install
python run.py config/default.yaml

# C – dev smoke-test
python scripts/test_load.py
```

### Expected terminal output

```text
14:32:01  INFO     cda.pipeline.main  v0.2   –  starting …
14:32:01  INFO     AppConfig
          paths.raw_data       = /…/AeroProject/test/input_file
          paths.output_csv     = /…/AeroProject/test/input_file/processed
          paths.output_plots   = /…/AeroProject/test/output
          paths.output_preproc = /…/AeroProject/test/output/preprocessed
          cyclist              = CyclistCfg(body_mass=72.0, …)
          segment              = SegmentCfg(interval_length_sec=60.0, …)
          preprocessing        = PreprocCfg(calibrate_accelerometer=False, …)
14:32:01  INFO     Cyclist
          body_mass          = 72.0 kg
          bike_weight        = 8.5 kg
          total_mass         = 80.5 kg
          wheel_radius       = 0.3332 m
          rotational_inertia = 0.0797 kg·m²
          effective_mass     = 82.3 kg
          c_rr               = 0.0040
          position           = dropbar
14:32:01  INFO     Found 2 JSON file(s).
14:32:01  INFO      ============================================================
14:32:01  INFO     Processing    ride_01.json    (test_id = ride_01)
14:32:01  INFO       loaded   cda=(3200,6)  ride=(3200,12)  bcvx=(3200,15)
14:32:01  INFO       accelerometer calibration skipped
14:32:01  INFO       altitude correction skipped
14:32:01  INFO       speed correction = 1.0 (no change)
14:32:02  INFO       segments (4, time-sorted):
14:32:02  INFO         seg_0     [    45.2 –    105.2 s]
14:32:02  INFO         seg_1     [   123.0 –    183.0 s]
14:32:02  INFO         seg_2     [   261.4 –    321.4 s]
14:32:02  INFO         seg_3     [   387.0 –    447.0 s]
14:32:02  INFO       seg_0   →   …/processed/ride_01_bcvx_0.csv   (+ combined)
14:32:02  INFO       seg_1   →   …/processed/ride_01_bcvx_1.csv   (+ combined)
14:32:02  INFO       seg_2   →   …/processed/ride_01_bcvx_2.csv   (+ combined)
14:32:02  INFO       seg_3   →   …/processed/ride_01_bcvx_3.csv   (+ combined)
14:32:02  INFO      ============================================================
14:32:02  INFO     Processing    ride_02.json    (test_id = ride_02)
          …
14:32:03  INFO      ============================================================
14:32:03  INFO     Grouping + preprocessing combined CSVs …
14:32:03  INFO       ride_01   rows=240   dt=1.000 s
14:32:03  INFO         →  …/preprocessed/ride_01_preprocessed.csv
14:32:03  INFO       ride_02   rows=180   dt=1.000 s
14:32:03  INFO         →  …/preprocessed/ride_02_preprocessed.csv
plot_segments: saved → ['…/output/segments.png', '…/output/segments.svg']
14:32:03  INFO      Done.     20 file(s) written in total.

20 file(s) written.
     /…/processed/ride_01_cda_0.csv
     /…/processed/ride_01_ride_0.csv
     /…/processed/ride_01_bcvx_0.csv
     /…/processed/ride_01_combined_0.csv
     …
     /…/preprocessed/ride_01_preprocessed.csv
     /…/preprocessed/ride_02_preprocessed.csv
     /…/output/segments.png
     /…/output/segments.svg
```

---

## 6 – Module Reference

### 6.1 `cda.cyclist`

**File:** `src/cda/cyclist/cyclist.py`

A frozen `@dataclass` carrying every physical parameter of the cyclist + bicycle
system. Created once from the YAML, passed to physics and (future) solver code.
Never mutated.

```python
from cda.cyclist import Cyclist

cyc = Cyclist.from_config_dict(cfg.cyclist.__dict__)
# or
cyc = Cyclist(body_mass=75.0, bike_weight=8.0, tyre_crr=0.006)
```

| Attribute              | Type    | Default     | Description                    |
|------------------------|---------|-------------|--------------------------------|
| `body_mass`            | `float` | `72.0`      | Rider mass (kg)                |
| `bike_weight`          | `float` | `8.5`       | Bicycle mass (kg)              |
| `wheel_mass`           | `float` | `0.90`      | Mass of one wheel (kg)         |
| `n_wheels`             | `int`   | `2`         | Number of wheels               |
| `wheel_circumference`  | `float` | `2.095`     | Rolling circumference (m)      |
| `tyre_crr`             | `float` | `0.004`     | Rolling-resistance coefficient |
| `aerodynamic_position` | `str`   | `"dropbar"` | `dropbar` · `bars` · `tuck`    |

| Derived property     | Formula                  | Unit  |
|----------------------|--------------------------|-------|
| `total_mass`         | body + bike              | kg    |
| `wheel_radius`       | C / 2π                   | m     |
| `rotational_inertia` | n · m_w · r² (thin-ring) | kg·m² |
| `effective_mass`     | total_mass + I / r²      | kg    |
| `c_rr`               | alias for `tyre_crr`     | –     |

`effective_mass` is used for `E_kin = ½ m_eff v²` so that the rotational energy
of the wheels is accounted for.

### 6.2 `cda.physics`

**Files:** `constants.py`, `forces.py`, `energy.py`, `air_density.py`, `equations.py`

Pure-math package. No I/O, no pandas, no plotting. Every function is
element-wise numpy.

#### Constants

| Name      | Value     | Description                           |
|-----------|-----------|---------------------------------------|
| `G`       | `9.80665` | Standard gravity (m/s²)               |
| `R_DRY`   | `287.05`  | Gas constant, dry air (J/(kg·K))      |
| `R_VAPOR` | `461.495` | Gas constant, water vapour (J/(kg·K)) |

#### Forces

```text
F_drag    = ½ · ρ · CdA · v_rel²
F_rolling = c_rr · m · g · cos(θ)
F_gravity = m · g · sin(θ)
```

#### Energy powers

```text
P_kinetic   = d/dt (½ · m_eff · v²)
P_potential = d/dt (m · g · h)
```

#### Air density

Full humidity-corrected density from temperature, pressure, relative humidity.
Polynomial saturation-pressure model (9th order, °C → mbar → Pa).
Reference: <https://wahiduddin.net/calc/density_altitude.htm>

#### `assemble_power_balance(df, cyclist, dt, cda_guess)`

Returns a new DataFrame with one column per power component:

| Added column   | Unit | Meaning                                    |
|----------------|------|--------------------------------------------|
| `F_drag`       | N    | ½ρ·CdA_guess·v_rel²                        |
| `F_rolling`    | N    | c_rr·m·g·cosθ                              |
| `F_gravity`    | N    | m·g·sinθ                                   |
| `P_aero`       | W    | F_drag · v                                 |
| `P_rolling`    | W    | F_rolling · v                              |
| `P_gravity`    | W    | F_gravity · v                              |
| `P_kinetic`    | W    | dE_kin/dt                                  |
| `P_potential`  | W    | dE_pot/dt                                  |
| `P_residual`   | W    | P_measured − P_kin − P_pot − P_rr − P_grav |
| `P_aero_model` | W    | ½ρ·CdA_guess·v_rel²·v (sanity check)       |

`P_residual` is the column a future solver will fit to extract CdA.

### 6.3 `cda.preprocessing`

#### `calibration.py` (unchanged from v0.1)

| Function                                   | Role                         |
|--------------------------------------------|------------------------------|
| `apply_accelerometer_calibration(bcvx_df)` | 3-axis linear fit, overwrite |
| `correct_altitude(bcvx_df, zero_offset)`   | Remove median drift          |
| `filter_speed_lowpass(df)`                 | Low-pass on speed            |

All pure: DataFrame in → new DataFrame out. Called only when the YAML flag is `true`.

#### `segment_finder.py` (unchanged from v0.1)

| Class / Function                            | Role                                      |
|---------------------------------------------|-------------------------------------------|
| `SegmentConfig`                             | Dataclass: window, speed bounds, costs, N |
| `SegmentFinder(cfg).find(bcvx_df)`          | → `list[(start, stop)]`, time-sorted      |
| `filter_dataframe_by_time(df, t0, t1, col)` | Slice by time                             |

**Algorithm:** slide window → filter by speed range → normalise σ → weighted
cost → pick N cheapest non-overlapping → sort by start time.

#### `segment_preprocess.py` (NEW)

| Function                                   | Role                            |
|--------------------------------------------|---------------------------------|
| `_butter(data, cutoff, order, fs)`         | Zero-phase Butterworth low-pass |
| `preprocess_segment(df, cyclist, dt, cfg)` | Full clean + derive             |

`preprocess_segment` produces, in order:

1. `velocity_smoothed` – butter(0.01) of v in m/s
2. `power_smoothed` – butter(0.01) of pedal power
3. `power_kinetic` – d/dt(½ m_eff v²)
4. `power_potential` – d/dt(m g h)
5. `incline_rad` – butter(0.20) of incline, converted to radians
6. `density` – humidity-corrected air density
7. `airspeed_filtered` – butter(√(2·dp/100/ρ))
8. `v_wind` – `airspeed_filtered − velocity_smoothed`

#### `file_grouping.py` (NEW)

| Function                      | Role                                               |
|-------------------------------|----------------------------------------------------|
| `group_files_by_type(folder)` | Scan `*.csv`, group by `(test_id, domain)`         |
| `load_and_merge(groups)`      | Concat segments, merge cda + ride + bcvx on `SECS` |

File naming convention (set by `io.save_segment_csvs` / `save_combined_csvs`):

```text
{test_id}_cda_{idx}.csv
{test_id}_ride_{idx}.csv
{test_id}_bcvx_{idx}.csv
{test_id}_combined_{idx}.csv
```

### 6.4 `cda.postprocessing`

| Function                                         | Role               |
|--------------------------------------------------|--------------------|
| `plot_segments(results, out_dir, cfg, filename)` | One figure, N rows |

Cyberpunk palette, neon glow, dark background. See [8 – Plotting](#8--plotting).

### 6.5 `cda.utils.io`

| Function                                                 | Role                               |
|----------------------------------------------------------|------------------------------------|
| `load_ride_json(path, test_id)`                          | JSON → `RawRideData`               |
| `save_segment_csvs(cda, ride, bcvx, out_dir, tid, idx)`  | 3 separate CSVs                    |
| `save_combined_csvs(cda, ride, bcvx, out_dir, tid, idx)` | 1 merged CSV                       |
| `_process_xdata(xdata)`                                  | Split flat XDATA into 3 DataFrames |
| `_get_all_samples(df, name)`                             | Flatten nested SAMPLES / VALUES    |

**Rule:** `io.py` imports only `json`, `os`, `pandas`. It never touches physics,
plotting, or config.

### 6.6 `cda.pipeline`

#### `config_loader.py`

| Dataclass    | YAML section                                            |
|--------------|---------------------------------------------------------|
| `PathsCfg`   | `paths`                                                 |
| `CyclistCfg` | `cyclist` ← **NEW**                                     |
| `SegmentCfg` | `segment`                                               |
| `PreprocCfg` | `preprocessing` (extended with Butterworth params)      |
| `PlotCfg`    | `plot`                                                  |
| `AppConfig`  | all of the above; loaded by `AppConfig.from_yaml(path)` |

All dataclasses are **frozen** (immutable). `from_dict` classmethods map YAML
keys → dataclass fields with defaults.

#### `main.py`

`main(yaml_path)` orchestrates three stages:

| Stage | What                                 | Output                                                  |
|-------|--------------------------------------|---------------------------------------------------------|
| 1     | JSON → clean → segment → CSVs        | `{tid}_{domain}_{idx}.csv` + `{tid}_combined_{idx}.csv` |
| 2     | Group → merge → `preprocess_segment` | `{tid}_preprocessed.csv`                                |
| 3     | `plot_segments`                      | `segments.png` / `.svg`                                 |

Returns `{"preprocessed": {tid: df}, "cyclist": Cyclist, "all_written": [paths]}`.

The file is under 130 lines and contains no physics, no matplotlib, no
file-path literals.

---

## 7 – Preprocessed Output Schema

Each `{test_id}_preprocessed.csv` contains:

| Column              | Unit  | Source                                  |
|---------------------|-------|-----------------------------------------|
| `SECS`              | s     | raw time axis                           |
| `speed`             | km/h  | raw (after `speed_correction`)          |
| `v`                 | m/s   | `speed / 3.6`                           |
| `velocity_smoothed` | m/s   | butter(0.01)                            |
| `power`             | W     | raw pedal power                         |
| `power_smoothed`    | W     | butter(0.01)                            |
| `altitude`          | m     | raw or butter-smoothed                  |
| `temperature`       | °C    | butter(0.10)                            |
| `pressure`          | Pa    | butter(0.10)                            |
| `relative_humidity` | %     | from humidity                           |
| `density`           | kg/m³ | humidity-corrected                      |
| `dyn_press`         | Pa    | from `ride_df`                          |
| `airspeed_filtered` | m/s   | butter(√(2·dp/100/ρ))                   |
| `v_wind`            | m/s   | `airspeed_filtered − velocity_smoothed` |
| `incline_angle`     | °     | butter(0.20, order 2)                   |
| `incline_rad`       | rad   | `deg2rad(incline_angle)`                |
| `power_kinetic`     | W     | d/dt(½ m_eff v²)                        |
| `power_potential`   | W     | d/dt(m g h)                             |

This is the solver-ready schema. A future `cda.solvers` module will consume
these columns plus a `Cyclist` object without needing to re-read any raw data.

---

## 8 – Plotting

The segment overview figure is saved to `paths.output_plots` as `segments.png`
and `segments.svg`.

Each row shows one ride. The speed trace is colour-coded:

```text
time ────────────────────────────────────────────────────────────►
      │  grey   │   ━━ seg_0 ━━  │  grey  │   ━━ seg_1 ━━  │  grey  │ …
      │         │   neon cyan    │        │   neon pink    │        │
      └─────────┴────────────────┴────────┴────────────────┴────────┘
```

- No green initial segment. Pre-first-segment region is dark grey.
- `seg_0` is the earliest window (guaranteed by the time-sort).
- Neon glow: each segment drawn twice (wide + transparent halo, then core).
- Tiny colour key in the top-right corner of each subplot.
- All visual parameters live in `config/default.yaml` → `plot:`.

---

## 9 – Development

### Adding a new preprocessing step

1. Implement a pure function in `preprocessing/`.
2. Export it from `preprocessing/__init__.py`.
3. Add a flag to `config/default.yaml` under `preprocessing:`.
4. Add the flag to `PreprocCfg` in `config_loader.py`.
5. Call it inside `preprocess_segment()`, gated by the flag.

No existing module needs to change.

### Adding a new solver (future)

1. Create `solvers/my_solver.py` inheriting `BaseSolver`.
2. Register it in `solvers/registry.py`.
3. Add its key to `config/default.yaml` under a new `solver:` section.
4. Call it in `main.py` Stage 2, after `preprocess_segment`.

### Running tests

```bash
pytest tests/ -v
```

---

## 10 – Roadmap

The following are planned and **not yet implemented**:

- [ ] `cda.solvers/` – `BaseSolver` ABC + `LinearRegressionSolver`, `NonlinearFitSolver`, `KalmanFilterSolver`
- [ ] `cda.solvers/registry.py` – solver name → class factory
- [ ] `cda.postprocessing/statistics.py` – confidence intervals, R², residuals
- [ ] `cda.postprocessing/report.py` – LaTeX / HTML summary
- [ ] `tests/` – unit tests mirroring `src/cda/`
- [ ] `docs/architecture.md` – full dependency-graph and data-flow diagram
- [ ] CI: GitHub Actions running `pytest` on every push
- [ ] `cda.cyclist` – add `frontal_area_prior`, `cadence`, `gear_ratio` when power-meter data becomes available

---

## 11 – Dependencies

| Package      | Purpose                                           |
|--------------|---------------------------------------------------|
| `numpy`      | array math, gradient, filtering                   |
| `pandas`     | DataFrame I/O, time slicing, merge                |
| `scipy`      | Butterworth filter, future nonlinear optimisation |
| `matplotlib` | segment overview plots                            |
| `pyyaml`     | config parsing                                    |

Python ≥ 3.9. Developed and tested with conda environment `aero_env`.

---

## 12 – License

Internal research project. No external distribution intended at this stage.

---

*Checkpoint v0.2 – Cyclist · Physics · Preprocessing. Next: solvers.*
