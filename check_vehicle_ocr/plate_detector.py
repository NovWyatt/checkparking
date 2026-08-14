"""Compatibility façade for the bundled local plate detector.

``detect_plate_candidates_onnx`` is retained as the internal call name so
older worker/test code stays compatible.  Its implementation is now the
Apache-2.0 OpenCV Zoo YuNet model bundled with the application; it never
downloads an unverified detector at scan time.
"""

from __future__ import annotations

import numpy as np

from .models import PlateCandidate
from .opencv_yunet_detector import detect_plate_candidates_yunet, yunet_detector_error


def detect_plate_candidates_onnx(
    image_bgr: np.ndarray,
    *,
    max_candidates: int = 8,
    confidence_threshold: float = 0.25,
) -> list[PlateCandidate]:
    return detect_plate_candidates_yunet(
        image_bgr,
        max_candidates=max_candidates,
        confidence_threshold=confidence_threshold,
    )


def onnx_detector_error() -> str:
    """Backward-compatible error accessor for detector-first callers."""

    return yunet_detector_error()
