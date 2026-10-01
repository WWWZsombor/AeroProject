"""
cda.preprocessing
=================
One-call entry point so the pipeline stays a 3-liner.
"""
from .calibration import (
    correct_altitude,
)
from .segment_finder import SegmentFinder, SegmentConfig, filter_dataframe_by_time

__all__ = [
    "correct_altitude",
    "SegmentFinder",
    "SegmentConfig",
    "filter_dataframe_by_time",
]
