# src/cda/preprocessing/__init__.py

from .calibration        import (
    correct_altitude,
)
from .segment_finder     import (
    SegmentFinder,
    SegmentConfig,
    filter_dataframe_by_time,
)
from .segment_preprocess import (
    preprocess_segment,
    _butter,
)
from .file_grouping      import (
    group_files_by_type,
    load_and_merge,
)

__all__ = [
     # calibration
    "correct_altitude",
     # segment selection
    "SegmentFinder",
    "SegmentConfig",
    "filter_dataframe_by_time",
     # segment preprocessing
    "preprocess_segment",
    "_butter",
     # file grouping
    "group_files_by_type",
    "load_and_merge",
]
