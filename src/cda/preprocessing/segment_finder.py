# src/cda/preprocessing/segment_finder.py
"""Find N non-overlapping windows with the smallest combined speed + power std."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .calibration import filter_speed_lowpass


@dataclass
class SegmentConfig:
    interval_length_sec: float = 60.0
    min_speed:           float = 44.0
    max_speed:           float = 55.0
    segment_num:         int   = 4
    cost_speed:          float = 0.5
    cost_power:          float = 0.5


class SegmentFinder:
    def __init__(self, config: SegmentConfig | None = None):
        self.cfg = config or SegmentConfig()

    def find(self, bcvx_df: pd.DataFrame) -> list[tuple[float, float]]:
        df = bcvx_df.sort_values("SECS").reset_index(drop=True)
        df["speed"] = filter_speed_lowpass(df)

        dt = df["SECS"].diff().median()
        if pd.isna(dt) or dt <= 0:
            raise ValueError("Invalid or non-uniform time series.")

        window_size = int(self.cfg.interval_length_sec / dt)
        candidates = self._collect_candidates(df, window_size)
        self._attach_costs(candidates)
        return self._select_non_overlapping(df, candidates)

    # ── private ──────────────────────────────────────────────────────

    def _collect_candidates(self, df: pd.DataFrame, window_size: int):
        out = []
        for i in range(len(df) - window_size):
            w = df.iloc[i : i + window_size]
            if w["speed"].mean() >= self.cfg.min_speed and \
               w["speed"].max()  <= self.cfg.max_speed:
                out.append({
                    "start_idx": i,
                    "end_idx":   i + window_size,
                    "speed_std": w["speed"].std(),
                    "power_std": w["power"].std(),
                })
        if len(out) < self.cfg.segment_num:
            raise ValueError("Not enough valid intervals found.")
        return out

    def _attach_costs(self, candidates: list[dict]) -> None:
        s_vals = [c["speed_std"] for c in candidates]
        p_vals = [c["power_std"] for c in candidates]
        s_range = max(s_vals) - min(s_vals) or 1e-8
        p_range = max(p_vals) - min(p_vals) or 1e-8
        for c in candidates:
            s_n = (c["speed_std"] - min(s_vals)) / s_range
            p_n = (c["power_std"] - min(p_vals)) / p_range
            c["cost"] = self.cfg.cost_speed * s_n + self.cfg.cost_power * p_n

    def _select_non_overlapping(
        self, df: pd.DataFrame, candidates: list[dict]
    ) -> list[tuple[float, float]]:
        candidates.sort(key=lambda c: c["cost"])
        selected: list[tuple[float, float]] = []
        used: list[tuple[int, int]] = []

        for c in candidates:
            if any(c["start_idx"] < e and c["end_idx"] > s for s, e in used):
                continue
            t0 = float(df.iloc[c["start_idx"]]["SECS"])
            t1 = float(df.iloc[c["end_idx"] - 1]["SECS"])
            selected.append((t0, t1))
            used.append((c["start_idx"], c["end_idx"]))
            if len(selected) == self.cfg.segment_num:
                break

        if len(selected) < self.cfg.segment_num:
            raise ValueError(
                f"Could not find {self.cfg.segment_num} non-overlapping intervals."
            )
        return selected


# ── small slice helper ───────────────────────────────────────────────

def filter_dataframe_by_time(
    df: pd.DataFrame,
    start_time: float,
    stop_time:  float,
    time_column: str = "SECS",
) -> pd.DataFrame:
    mask = (df[time_column] >= start_time) & (df[time_column] <= stop_time)
    return df.loc[mask].reset_index(drop=True)
