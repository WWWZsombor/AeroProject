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
from .airspeed_calibration import (
    AirspeedCalibration,
    fit_airspeed_calibration,
    resolve_airspeed_calibration,
)
from .bends              import flag_bends, straight_mask, detect_bends
from .speed              import select_speed, wheel_speed
from .file_grouping      import (
    group_files_by_type,
    load_segments,
)

__all__ = [
     # airspeed calibration (per setup)
    "AirspeedCalibration",
    "fit_airspeed_calibration",
    "resolve_airspeed_calibration",
     # velodrome helpers
    "flag_bends",
    "straight_mask",
    "detect_bends",
    "select_speed",
    "wheel_speed",
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
    "load_segments",
]
