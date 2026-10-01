# src/cda/postprocessing/plotting.py
"""
cda.postprocessing.plotting
===========================
Cyberpunk-styled, time-sorted segment overview.

Colour logic
------------
  gaps / before / after segments   →  dark grey   (#5a5a5a)
  segment k  (0-indexed, earliest first)  →  palette[k]

  If show_glow is True, each segment is drawn twice:
     pass 1  – thick, alpha 0.18   (the "halo")
     pass 2  – normal, alpha 1.0    (the core line)
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from cda.pipeline.config_loader import PlotCfg


# ── fixed colours ────────────────────────────────────────────────────

_COLOR_BG    = "#0d1117"
_COLOR_AXIS  = "#c9d1d9"
_COLOR_GRID  = "#21262d"
_COLOR_SPINE = "#30363d"
_COLOR_GAP   = "#5a5a5a"      # grey for gaps / pre / post segments


# ── public API ───────────────────────────────────────────────────────

def plot_segments(
    results:  list[tuple[pd.DataFrame, list[tuple[float, float]], str]],
    out_dir:  str,
    cfg:      PlotCfg,
    filename: str = "segments",
) -> list[str]:
    if not results:
        print("plot_segments: no results, skipping.")
        return []

    n_rows = len(results)
    fig, axes = plt.subplots(
        nrows=n_rows, ncols=1,
        figsize=(cfg.fig_width, cfg.fig_height_per_row * n_rows),
        squeeze=False,
     )
    fig.patch.set_facecolor(_COLOR_BG)

    for ax, (df, segments, test_id) in zip(axes[:, 0], results):
         _draw_one_row(ax, df, segments, test_id, cfg)

    fig.subplots_adjust(
        hspace=0.35, wspace=0.08,
        left=0.07, right=0.95,
        top=0.94, bottom=0.06,
     )

    os.makedirs(out_dir, exist_ok=True)
    written = []
    for fmt in cfg.formats:
        path = os.path.join(out_dir, f"{filename}.{fmt}")
        fig.savefig(path, dpi=cfg.dpi, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        written.append(path)

    plt.close(fig)
    print(f"plot_segments: saved → {written}")
    return written


# ── one subplot ───────────────────────────────────────────────────────

def _draw_one_row(
    ax:       plt.Axes,
    df:       pd.DataFrame,
    segments: list[tuple[float, float]],   # already time-sorted
    test_id:  str,
    cfg:      PlotCfg,
) -> None:
    ax.set_facecolor(_COLOR_BG)

    times  = df["SECS"].values
    speeds = df["speed"].values * cfg.speed_factor

     # ensure chronological order
    segments = sorted(segments, key=lambda s: s[0])

     # assign palette colours: seg_0 → palette[0], seg_1 → palette[1], …
    n_seg = len(segments)
    seg_colors = [cfg.palette[i % len(cfg.palette)] for i in range(n_seg)]

     # ── build the full list of (t0, t1, color, is_segment) chunks ──
    #   before  seg_0   →  grey
    #   seg_0           →  palette[0]
    #   gap             →  grey
    #   seg_1           →  palette[1]
    #   …
    #   after  seg_n    →  grey
    t_first = float(times[0])
    t_last   = float(times[-1])
    prev_t   = t_first
    chunks: list[tuple[float, float, str, bool]] = []

    for i, (seg_start, seg_end) in enumerate(segments):
         # gap / initial section
        chunks.append((prev_t, seg_start, _COLOR_GAP, False))
         # segment
        chunks.append((seg_start, seg_end, seg_colors[i], True))
        prev_t = seg_end

     # tail
    chunks.append((prev_t, t_last, _COLOR_GAP, False))

     # ── draw ──────────────────────────────────────────────────────
    for t0, t1, color, is_seg in chunks:
        mask = (times >= t0) & (times <= t1)
        if mask.sum() < 2:
            continue

        if is_seg and cfg.show_glow:
             # pass 1: wide, very transparent  →  neon halo
            ax.plot(
                times[mask], speeds[mask],
                color=color,
                linewidth=cfg.line_width_seg * 4.0,
                alpha=0.15,
                solid_capstyle="round",
                zorder=2,
             )

         # pass 2 (or only pass for gaps): the actual line
        ax.plot(
            times[mask], speeds[mask],
            color=color,
            linewidth=cfg.line_width_seg if is_seg else cfg.line_width_base,
            alpha=1.0,
            solid_capstyle="round",
            zorder=3 if is_seg else 2,
         )

     # ── segment boundary ticks ────────────────────────────────────
    for t0, t1 in segments:
        ax.axvline(t0, color="#ffffff22", linewidth=0.5,
                   linestyle="--", zorder=4)
        ax.axvline(t1, color="#ffffff22", linewidth=0.5,
                   linestyle="--", zorder=4)

     # ── labels ────────────────────────────────────────────────────
    if cfg.show_segment_labels:
        for i, (t0, t1) in enumerate(segments):
            mid = (t0 + t1) / 2.0
            idx = int(np.argmin(np.abs(times - mid)))
            y   = float(speeds[idx])
            color = seg_colors[i]
            ax.annotate(
                f"seg_{i}",
                xy=(mid, y),
                fontsize=8,
                color=color,
                fontweight="bold",
                ha="center", va="bottom",
                xytext=(0, 7),
                textcoords="offset points",
                zorder=5,
             )

     # ── cosmetics ─────────────────────────────────────────────────
    _style_axes(ax, test_id, speeds, times)

     # small colour key in the corner
    _add_color_key(ax, n_seg, seg_colors)


# ── helpers ───────────────────────────────────────────────────────────

def _style_axes(
    ax:     plt.Axes,
    test_id: str,
    speeds: np.ndarray,
    times:  np.ndarray,
) -> None:
    ax.set_facecolor(_COLOR_BG)
    ax.set_title(
        test_id, color=_COLOR_AXIS,
        fontsize=11, fontweight="bold", loc="left", pad=8,
     )
    ax.set_ylabel("Speed  (km/h)", color=_COLOR_AXIS, fontsize=9)
    ax.set_xlabel("Time  (s)",      color=_COLOR_AXIS, fontsize=9)
    ax.tick_params(colors=_COLOR_AXIS, labelsize=8)
    ax.grid(True, color=_COLOR_GRID, linewidth=0.4, alpha=0.6)

    for spine in ax.spines.values():
        spine.set_color(_COLOR_SPINE)
        spine.set_linewidth(0.6)

     # x-tick labels as minutes
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x / 60:.1f}")
     )

     # y padding
    y_lo, y_hi = float(speeds.min()), float(speeds.max())
    pad = (y_hi - y_lo) * 0.08 or 0.5
    ax.set_ylim(y_lo - pad, y_hi + pad)


def _add_color_key(
    ax:       plt.Axes,
    n_seg:    int,
    colors:   list[str],
) -> None:
    """Tiny legend in the top-right corner of the subplot."""
    y_pos = 0.96
    for i in range(n_seg):
        ax.plot(
            [0.90], [y_pos - i * 0.04],
            transform=ax.transAxes,
            color=colors[i],
            linewidth=4,
            solid_capstyle="round",
            clip_on=False,
            zorder=6,
        )
        ax.text(
             0.905, y_pos - i * 0.04,
            f"seg_{i}",
            transform=ax.transAxes,
            fontsize=7,
            color=colors[i],
            va="center",
            ha="left",
            clip_on=False,
            zorder=6,
         )
