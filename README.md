# AeroProject – Cyclist CdA Measurement

> **Status:** active development · checkpoint v0.1
> Python 3.9 · conda · single-config-file driven

AeroProject processes raw cycling-ergometer measurement files (JSON) to
extract the cyclist's **Coefficient of Drag × Frontal Area (CdA)**.
The pipeline reads one or more JSON files from a data folder, cleans the
signal, locates the most consistent speed/power windows, writes per-segment
CSVs, and renders a cyberpunk-styled overview figure.

---

## Table of Contents

- [Pipeline Overview](#pipeline-overview)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Module Reference](#module-reference)
- [Plotting](#plotting)
- [Development](#development)
- [Roadmap](#roadmap)
- [Dependencies](#dependencies)
- [License](#license)

---

## Pipeline Overview

```text
config/default.yaml
        │
        ▼
┌─────────────┐
│   config    │  parse YAML → frozen AppConfig dataclass
│   loader    │  (paths, segment params, preprocessing flags, plot style)
└─────┬───────┘
      │
      ▼
┌─────────────┐
│  glob *.json│  discover every measurement file in paths.raw_data
│  in raw_dir │  test_id = filename without ".json"
└─────┬───────┘
      │
      ▼  for each JSON file
┌─────────────┐
│   io.load   │  open JSON → parse RIDE.XDATA → three DataFrames
│  ride_json  │  cda_df · ride_df · bcvx_df
└─────┬───────┘
      │
      ▼
┌─────────────┐
│ preprocess  │  accelerometer calibration (optional)
│ (optional)  │  altitude median correction (optional)
└─────┬───────┘
      │
      ▼
┌─────────────┐
│    speed    │  speed × speed_correction (from YAML)
│ correction  │
└─────┬───────┘
      │
      ▼
┌─────────────┐
│  Segment    │  find N non-overlapping windows with the
│  Finder     │  smallest normalised speed + power σ
│             │  sorted by start time → seg_0 = earliest
└─────┬───────┘
      │
      ▼
┌─────────────┐
│   slice +   │  filter cda_df / ride_df / bcvx_df per window
│  save CSVs  │  → paths.output_csv / {test_id}_{domain}_{idx}.csv
└─────┬───────┘
      │
      ▼  after all files
┌─────────────┐
│    plot     │  one row per ride, cyberpunk palette,
│  segments   │  neon glow, dark background
│             │  → paths.output_plots / segments.png|svg
└─────────────┘
```

**Design rule:** every tunable parameter lives in `config/default.yaml`.
No hard-coded paths, thresholds, or colours exist in the Python source.

---

## Project Structure

```text
AeroProject/
│
├── run.py                      # zero-install launcher (no pip install needed)
├── pyproject.toml              # package metadata + build config
├── .gitignore
├── README.md                   # ← this file
│
├── config/
│   └── default.yaml            # single source of truth for every parameter
│
├── test/
│   └── input_file/             # measurement JSON files live here
│       ├── ride_01.json
│       ├── ride_02.json
│       └── processed/          # per-segment CSVs are written here
│
├── output/
│   └── output/                 # segment overview figures (png / svg)
│
├── scripts/
│   └── test_load.py            # dev smoke-test (bypasses config if needed)
│
└── src/
    └── cda/
        ├── __init__.py
        │
        ├── utils/
        │   ├── __init__.py
        │   └── io.py                   # JSON read · CSV write
        │
        ├── preprocessing/
        │   ├── __init__.py
        │   ├── calibration.py          # accel · altitude · low-pass
        │   └── segment_finder.py       # SegmentFinder · SegmentConfig
        │
        ├── postprocessing/
        │   ├── __init__.py
        │   └── plotting.py             # cyberpunk segment overview
        │
        └── pipeline/
            ├── __init__.py
            ├── config_loader.py        # YAML → frozen dataclasses
            └── main.py                 # orchestrator (< 80 lines)
```

---

## Installation

### Option A – Editable install (recommended)

```bash
cd AeroProject
conda activate aero_env                 # or create a new env:
# conda create -n aero_env python=3.9 && conda activate aero_env

pip install -e . --no-build-isolation
```

After this, the package `cda` is importable from anywhere in the shell.

### Option B – Zero-install

No install step. The root-level `run.py` injects `src/` into `sys.path`
automatically. See [Usage](#usage).

### Verify

```bash
python -c "import cda; print(cda.__version__)"
# expected: 0.1.0
```

---

## Configuration

Every run is controlled by **one YAML file**. The default location is
`config/default.yaml`; a different file can be passed as a CLI argument.

### `config/default.yaml`

```yaml
paths:
  raw_data:        /absolute/path/to/input_folder
  output_csv:      /absolute/path/to/processed
  output_plots:    /absolute/path/to/output

segment:
  interval_length_sec: 60
  min_speed:           45
  max_speed:           55
  segment_num:         4
  cost_speed:          0.5
  cost_power:          0.5

preprocessing:
  calibrate_accelerometer: false
  calibrate_altitude:      false
  speed_correction:        1.0

plot:
  speed_factor:        1.0          # 1.0 if data is km/h; 3.6 if m/s
  fig_width:           12
  fig_height_per_row:  3.2
  dpi:                 150
  formats:             ["png", "svg"]
  show_segment_labels: true
  show_glow:           true
  line_width_base:     1.0
  line_width_seg:      2.2
  palette:
    - "#00f0ff"          # seg_0  neon cyan
    - "#ff2d78"          # seg_1  neon pink
    - "#ff8c00"          # seg_2  neon orange
    - "#b026ff"          # seg_3  electric purple
    - "#39ff14"          # seg_4  neon green  (spare)
    - "#ffea00"          # seg_5  neon yellow (spare)
```

### Changing a test configuration

Edit only the YAML. No Python file is touched.

| Goal                          | YAML change                                      |
|-------------------------------|--------------------------------------------------|
| Fewer / more segments         | `segment.segment_num: 2`                         |
| Longer windows                | `segment.interval_length_sec: 120`               |
| Speed data is in m/s          | `plot.speed_factor: 3.6`                         |
| Disable glow effect           | `plot.show_glow: false`                          |
| Swap a colour                 | change the hex value in `plot.palette`           |
| Add accelerometer calibration | `preprocessing.calibrate_accelerometer: true`    |

---

## Usage

All three commands produce the same output.

### A – Module call (after `pip install -e .`)

```bash
python -m cda.pipeline.main config/default.yaml
```

### B – Root launcher (no install required)

```bash
python run.py config/default.yaml
```

### C – Dev smoke-test

```bash
python scripts/test_load.py
```

### Expected terminal output

```text
14:32:01  INFO      cda.pipeline.main   –  starting…
14:32:01  INFO      AppConfig
          paths.raw_data      = /…/AeroProject/test/input_file
          paths.output_csv    = /…/AeroProject/test/input_file/processed
          paths.output_plots  = /…/AeroProject/test/output
          segment             = SegmentCfg(interval_length_sec=60.0, …)
          preprocessing       = PreprocCfg(calibrate_accelerometer=False, …)
14:32:01  INFO      Found 2 JSON file(s) to process.
14:32:01  INFO      ============================================================
14:32:01  INFO      Processing    ride_01.json    (test_id = ride_01)
14:32:01  INFO        loaded   cda=(3200, 6)  ride=(3200, 12)  bcvx=(3200, 15)
14:32:01  INFO        accelerometer calibration skipped
14:32:01  INFO        altitude correction skipped
14:32:01  INFO        speed correction = 1.0 (no change)
14:32:02  INFO        segments (4, time-sorted):
14:32:02  INFO          seg_0    [   45.2 –   105.2 s]
14:32:02  INFO          seg_1    [  123.0 –   183.0 s]
14:32:02  INFO          seg_2    [  261.4 –   321.4 s]
14:32:02  INFO          seg_3    [  387.0 –   447.0 s]
14:32:02  INFO        seg_0    →    …/processed/ride_01_bcvx_0.csv
14:32:02  INFO        seg_1    →    …/processed/ride_01_bcvx_1.csv
14:32:02  INFO        seg_2    →    …/processed/ride_01_bcvx_2.csv
14:32:02  INFO        seg_3    →    …/processed/ride_01_bcvx_3.csv
14:32:02  INFO      ============================================================
14:32:02  INFO      Processing    ride_02.json    (test_id = ride_02)
          …
plot_segments: saved → ['…/output/segments.png', '…/output/segments.svg']
14:32:03  INFO      Done.    14 file(s) written in total.

14 file(s) written.
    /…/processed/ride_01_cda_0.csv
    /…/processed/ride_01_ride_0.csv
    /…/processed/ride_01_bcvx_0.csv
    …
    /…/output/segments.png
    /…/output/segments.svg
```

---

## Module Reference

### `cda.utils.io`

| Function                                                     | Role                                                        |
|--------------------------------------------------------------|-------------------------------------------------------------|
| `load_ride_json(path, test_id)`                              | Open one JSON → `RawRideData(cda_df, ride_df, bcvx_df, …)`  |
| `save_segment_csvs(cda, ride, bcvx, out_dir, test_id, idx)`  | Write three CSVs                                            |
| `_process_xdata(xdata)`                                      | Split the flat XDATA list into the three domain DataFrames  |
| `_get_all_samples(df, name)`                                 | Flatten nested SAMPLES / VALUES into a wide DataFrame       |

**Rule:** this module imports only `json`, `os`, `pandas`.
It never touches physics, plotting, or config.

### `cda.preprocessing`

#### `calibration.py`

| Function                                  | Role                                         |
|-------------------------------------------|----------------------------------------------|
| `apply_accelerometer_calibration(bcvx_df)`| Linear-fit 3-axis accel, overwrite in-place  |
| `correct_altitude(bcvx_df, zero_offset)`  | Remove slow median drift from altitude       |
| `filter_speed_lowpass(df)`                | Low-pass filter on the speed channel         |

All functions are pure: DataFrame in → new DataFrame out. They are called
only when the corresponding YAML flag is `true`.

#### `segment_finder.py`

| Class / Function                          | Role                                                                                         |
|-------------------------------------------|----------------------------------------------------------------------------------------------|
| `SegmentConfig`                           | Dataclass: `interval_length_sec`, `min_speed`, `max_speed`, `segment_num`, `cost_speed`, `cost_power` |
| `SegmentFinder(cfg).find(bcvx_df)`        | Return `list[(start, stop)]`, time-sorted                                                    |
| `filter_dataframe_by_time(df, t0, t1, col)` | Slice a DataFrame by time window                                                           |

**Algorithm:**

1. Low-pass filter the speed column.
2. Slide a window of `interval_length_sec` across the time series.
3. Keep windows where `avg_speed ∈ [min_speed, max_speed]` and `max_speed_in_window ≤ max_speed`.
4. Normalise `speed_std` and `power_std` to [0, 1].
5. Cost = `cost_speed · s_norm + cost_power · p_norm`.
6. Pick the N cheapest non-overlapping windows.
7. Sort by start time → `seg_0` is always the earliest.

### `cda.postprocessing.plotting`

| Function                                      | Role                                    |
|-----------------------------------------------|-----------------------------------------|
| `plot_segments(results, out_dir, cfg, filename)` | One figure, N rows, one row per ride |

**Visual style:**

- Dark background (`#0d1117`, GitHub-dark).
- Gaps / pre-first / post-last: dark grey (`#5a5a5a`).
- Segment *k* (0-indexed, time-sorted): `palette[k]` from the YAML.
- Neon glow: each segment drawn twice (wide + transparent halo, then core).
- Tiny colour key in the top-right corner of each subplot.
- X-axis in minutes, Y-axis in km/h.

### `cda.pipeline`

#### `config_loader.py`

| Dataclass     | YAML section                                       |
|---------------|----------------------------------------------------|
| `PathsCfg`    | `paths`                                            |
| `SegmentCfg`  | `segment`                                          |
| `PreprocCfg`  | `preprocessing`                                    |
| `PlotCfg`     | `plot` (includes `palette` list)                   |
| `AppConfig`   | all of the above; loaded by `AppConfig.from_yaml(path)` |

All dataclasses are **frozen** (immutable). `from_dict` classmethods map
YAML keys → dataclass fields with defaults.

#### `main.py`

`main(yaml_path)` is the only orchestration function. It:

1. Reads the YAML → `AppConfig`.
2. Globs `*.json` in `paths.raw_data`.
3. For each file: load → clean → speed-correct → segment → write CSVs.
4. Calls `plot_segments()` once with all results.
5. Returns the full list of written file paths.

The file is under 80 lines. It contains no physics, no matplotlib, no
file-path literals.

---

## Plotting

The segment overview figure is saved to `paths.output_plots` as
`segments.png` and `segments.svg` (configurable via `plot.formats`).

Each row shows one ride. The speed trace is colour-coded:

```text
time ───────────────────────────────────────────────────────►
      │  grey  │  ━━ seg_0 ━━  │  grey  │  ━━ seg_1 ━━  │  grey  │ …
      │        │  neon cyan    │        │  neon pink    │        │
      └────────┴───────────────┴────────┴───────────────┴────────┘
```

- No green initial segment. The pre-first-segment region is dark grey.
- `seg_0` is the earliest window in time (guaranteed by the sort).
- The colour palette is read from `config/default.yaml` → `plot.palette`.
- Glow is controlled by `plot.show_glow` (default `true`).

---

## Development

### Quick smoke-test

```bash
python scripts/test_load.py
```

This script lives in `scripts/` and is **not** part of the importable
package. It can be edited freely with hard-coded paths for debugging.

### Adding a new preprocessing step

1. Implement a pure function in `preprocessing/calibration.py` (or a new file in `preprocessing/`).
2. Export it from `preprocessing/__init__.py`.
3. Add a flag to `config/default.yaml` under `preprocessing:`.
4. Add the flag to `PreprocCfg` in `config_loader.py`.
5. Call it in `_process_one()` in `main.py`, guarded by the flag.

No existing module needs to change.

### Adding a new solver (future)

1. Create `solvers/my_solver.py` inheriting `BaseSolver`.
2. Register it in `solvers/registry.py`.
3. Add its key to `config/default.yaml` under a new `solver:` section.
4. Call it in `main.py` after the segmentation step.

---

## Roadmap

The following are planned and **not yet implemented**:

- [ ] `cda.physics/` – assembled drag / rolling / gravity equations
- [ ] `cda.cyclist/` – `Cyclist` dataclass (mass, C_rr, wheel radius, posture)
- [ ] `cda.solvers/` – `BaseSolver` ABC + `LinearRegressionSolver`, `NonlinearFitSolver`, `KalmanFilterSolver`
- [ ] `cda.postprocessing/statistics.py` – confidence intervals, R², residuals
- [ ] `cda.postprocessing/report.py` – optional LaTeX / HTML summary
- [ ] `tests/` – unit tests mirroring `src/cda/`
- [ ] `docs/architecture.md` – full dependency-graph and data-flow diagram
- [ ] CI: GitHub Actions running `pytest` on every push

---

## Dependencies

| Package      | Purpose                                  |
|--------------|------------------------------------------|
| `numpy`      | array math, low-pass filter              |
| `pandas`     | DataFrame I/O, time slicing              |
| `scipy`      | nonlinear optimisation (future solvers)  |
| `matplotlib` | segment overview plots                   |
| `pyyaml`     | config parsing                           |

Python ≥ 3.9. Developed and tested with conda environment `aero_env`.

### Configuration cheatsheet

| File                   | What it controls                                                  |
|------------------------|-------------------------------------------------------------------|
| `config/default.yaml`  | **Everything.** Paths, segments, preprocessing, plot style.       |
| `pyproject.toml`       | Package name, version, build system. Rarely edited.               |
| `run.py`               | Entry point. Contains one `sys.path` line. Never edit.            |

To run a completely different test, copy `default.yaml` to
`config/ride_02_fast.yaml`, edit the copy, and run:

```bash
python run.py config/ride_02_fast.yaml
```

The original config is never touched.

---

## License

Internal research project. No external distribution intended at this stage.
