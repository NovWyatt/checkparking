"""Bundled Apache-2.0 YuNet license-plate detector.

The ONNX model and the decoding approach originate from OpenCV Zoo's
``models/license_plate_detection_yunet`` directory.  The bundled model,
license text, source commit and SHA-256 are recorded under
``models/opencv_yunet``.
"""

from __future__ import annotations

import math
import sys
import threading
from pathlib import Path

import cv2
import numpy as np

from .models import PlateCandidate


MODEL_DIRECTORY = "opencv_yunet"
MODEL_FILENAME = "license_plate_detection_lpd_yunet_2023mar.onnx"
_INPUT_LONG_EDGE = 640
_CONFIDENCE_FLOOR = 0.18
_HIGH_ROTATION_DEGREES = 35.0
_DETECTOR_LOCK = threading.Lock()
_DETECTOR: "YuNetPlateDetector | None" = None
_DETECTOR_ATTEMPTED = False
_DETECTOR_ERROR = ""


def detect_plate_candidates_yunet(
    image_bgr: np.ndarray,
    *,
    max_candidates: int = 8,
    confidence_threshold: float = 0.25,
) -> list[PlateCandidate]:
    """Detect plate crops with the bundled, offline YuNet model."""

    detector = _get_detector()
    if detector is None or image_bgr.size == 0:
        return []
    return detector.detect(
        image_bgr,
        max_candidates=max_candidates,
        confidence_threshold=confidence_threshold,
    )


def yunet_detector_error() -> str:
    return _DETECTOR_ERROR


def bundled_yunet_model_path() -> Path | None:
    """Return the packaged model path without network access."""

    roots: list[Path] = []
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        roots.append(Path(frozen_root))
    roots.append(Path(__file__).resolve().parents[1])
    for root in roots:
        path = root / "models" / MODEL_DIRECTORY / MODEL_FILENAME
        if path.is_file():
            return path
    return None


def _get_detector() -> "YuNetPlateDetector | None":
    global _DETECTOR, _DETECTOR_ATTEMPTED, _DETECTOR_ERROR
    if _DETECTOR is not None:
        return _DETECTOR
    if _DETECTOR_ATTEMPTED:
        return None

    with _DETECTOR_LOCK:
        if _DETECTOR is not None:
            return _DETECTOR
        if _DETECTOR_ATTEMPTED:
            return None
        _DETECTOR_ATTEMPTED = True
        path = bundled_yunet_model_path()
        if path is None:
            _DETECTOR_ERROR = "Thiếu model detector YuNet được đóng gói; tiếp tục detector dự phòng cục bộ."
            return None
        try:
            _DETECTOR = YuNetPlateDetector(path)
            _DETECTOR_ERROR = ""
        except Exception as exc:
            _DETECTOR_ERROR = f"Không khởi tạo được detector YuNet: {exc}"
            _DETECTOR = None
        return _DETECTOR


class YuNetPlateDetector:
    """Small OpenCV DNN wrapper for the Apache-2.0 YuNet ONNX model."""

    def __init__(self, model_path: Path) -> None:
        self._network = cv2.dnn.readNetFromONNX(str(model_path))
        self._priors_by_size: dict[tuple[int, int], np.ndarray] = {}

    def detect(
        self,
        image_bgr: np.ndarray,
        *,
        max_candidates: int,
        confidence_threshold: float,
    ) -> list[PlateCandidate]:
        height, width = image_bgr.shape[:2]
        target_width, target_height = _detector_input_size(width, height)
        resized = cv2.resize(
            image_bgr,
            (target_width, target_height),
            interpolation=cv2.INTER_AREA if target_width < width or target_height < height else cv2.INTER_LINEAR,
        )
        blob = cv2.dnn.blobFromImage(resized)
        self._network.setInput(blob)
        loc, conf, iou = self._network.forward(["loc", "conf", "iou"])
        records = _decode_yunet(loc, conf, iou, self._priors(target_width, target_height), target_width, target_height)
        scale_x = width / target_width
        scale_y = height / target_height
        candidates: list[PlateCandidate] = []
        floor = max(_CONFIDENCE_FLOOR, float(confidence_threshold))
        for record in sorted(records, key=lambda item: float(item[-1]), reverse=True):
            confidence = float(record[-1])
            if confidence < floor:
                continue
            points = record[:8].reshape(4, 2).astype(np.float32)
            points[:, 0] *= scale_x
            points[:, 1] *= scale_y
            candidate = _candidate_from_points(points, confidence, width, height)
            if candidate is None:
                continue
            if any(_iou(candidate.bbox, previous.bbox) >= 0.30 for previous in candidates):
                continue
            candidates.append(candidate)
            if len(candidates) >= max_candidates:
                break
        return candidates

    def _priors(self, width: int, height: int) -> np.ndarray:
        key = (width, height)
        if key not in self._priors_by_size:
            self._priors_by_size[key] = _generate_priors(width, height)
        return self._priors_by_size[key]


def _detector_input_size(width: int, height: int) -> tuple[int, int]:
    scale = min(1.0, _INPUT_LONG_EDGE / max(width, height))
    target_width = max(32, round((width * scale) / 32) * 32)
    target_height = max(32, round((height * scale) / 32) * 32)
    return target_width, target_height


def _generate_priors(width: int, height: int) -> np.ndarray:
    min_sizes = ((10, 16, 24), (32, 48), (64, 96), (128, 192, 256))
    steps = (8, 16, 32, 64)
    feature_maps = (
        (height // 8, width // 8),
        (height // 16, width // 16),
        (height // 32, width // 32),
        (height // 64, width // 64),
    )
    priors: list[tuple[float, float, float, float]] = []
    for (feature_height, feature_width), sizes, step in zip(feature_maps, min_sizes, steps, strict=True):
        for row in range(feature_height):
            for column in range(feature_width):
                for size in sizes:
                    priors.append(
                        (
                            (column + 0.5) * step / width,
                            (row + 0.5) * step / height,
                            size / width,
                            size / height,
                        )
                    )
    return np.asarray(priors, dtype=np.float32)


def _decode_yunet(
    loc: np.ndarray,
    conf: np.ndarray,
    iou: np.ndarray,
    priors: np.ndarray,
    width: int,
    height: int,
) -> np.ndarray:
    loc = np.asarray(loc).reshape(-1, 14)
    conf = np.asarray(conf).reshape(-1, 2)
    iou = np.asarray(iou).reshape(-1, 1)
    count = min(len(loc), len(conf), len(iou), len(priors))
    loc, conf, iou, priors = loc[:count], conf[:count], iou[:count], priors[:count]
    scores = np.sqrt(np.clip(conf[:, 1], 0.0, 1.0) * np.clip(iou[:, 0], 0.0, 1.0))
    points = np.hstack(
        (
            (priors[:, 0:2] + loc[:, 4:6] * 0.1 * priors[:, 2:4]) * (width, height),
            (priors[:, 0:2] + loc[:, 6:8] * 0.1 * priors[:, 2:4]) * (width, height),
            (priors[:, 0:2] + loc[:, 10:12] * 0.1 * priors[:, 2:4]) * (width, height),
            (priors[:, 0:2] + loc[:, 12:14] * 0.1 * priors[:, 2:4]) * (width, height),
            scores[:, np.newaxis],
        )
    )
    return points


def _candidate_from_points(
    points: np.ndarray,
    confidence: float,
    image_width: int,
    image_height: int,
) -> PlateCandidate | None:
    x1, y1 = np.min(points, axis=0).astype(int)
    x2, y2 = np.max(points, axis=0).astype(int)
    x1 = max(0, min(int(x1), image_width - 1))
    y1 = max(0, min(int(y1), image_height - 1))
    x2 = max(0, min(int(x2), image_width))
    y2 = max(0, min(int(y2), image_height))
    if x2 <= x1 or y2 <= y1:
        return None

    box_width = x2 - x1
    box_height = y2 - y1
    if box_width < 18 or box_height < 8:
        return None
    aspect = box_width / max(box_height, 1)
    area_ratio = (box_width * box_height) / max(1, image_width * image_height)
    if not (0.45 <= aspect <= 8.5) or not (0.00003 <= area_ratio <= 0.22):
        return None

    pad_x = max(3, int(box_width * 0.14))
    pad_y = max(4, int(box_height * 0.34))
    crop_x1 = max(0, x1 - pad_x)
    crop_y1 = max(0, y1 - pad_y)
    crop_x2 = min(image_width, x2 + pad_x)
    crop_y2 = min(image_height, y2 + pad_y)
    rotation = _rotation_degrees(points)
    source = "opencv_yunet_plate"
    if rotation >= _HIGH_ROTATION_DEGREES:
        source += "_high_rotation"
    return PlateCandidate(
        bbox=(crop_x1, crop_y1, max(1, crop_x2 - crop_x1), max(1, crop_y2 - crop_y1)),
        score=82.0 + min(18.0, confidence * 18.0),
        detector_confidence=82.0 + min(18.0, confidence * 18.0),
        source=source,
    )


def _rotation_degrees(points: np.ndarray) -> float:
    center = np.mean(points, axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    ordered = points[np.argsort(angles)]
    start = int(np.argmin(ordered[:, 0] + ordered[:, 1]))
    ordered = np.roll(ordered, -start, axis=0)
    top_edge = ordered[1] - ordered[0]
    angle = abs(math.degrees(math.atan2(float(top_edge[1]), float(top_edge[0]))))
    return min(angle, abs(180.0 - angle))


def _iou(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> float:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    intersection_left = max(lx, rx)
    intersection_top = max(ly, ry)
    intersection_right = min(lx + lw, rx + rw)
    intersection_bottom = min(ly + lh, ry + rh)
    intersection = max(0, intersection_right - intersection_left) * max(0, intersection_bottom - intersection_top)
    union = (lw * lh) + (rw * rh) - intersection
    return intersection / union if union else 0.0
