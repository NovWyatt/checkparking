from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import numpy as np

from .config import APP_DIR_NAME
from .models import PlateCandidate


DEFAULT_ONNX_PLATE_MODEL = "yolo-v9-t-384-license-plate-end2end"
DEFAULT_ONNX_PLATE_MODEL_FILE = "yolo-v9-t-384-license-plates-end2end.onnx"
_DETECTOR_LOCK = threading.Lock()
_DETECTOR = None
_DETECTOR_ATTEMPTED = False
_DETECTOR_ERROR = ""


def detect_plate_candidates_onnx(
    image_bgr: np.ndarray,
    *,
    max_candidates: int = 8,
    confidence_threshold: float = 0.25,
) -> list[PlateCandidate]:
    detector = _get_detector()
    if detector is None or image_bgr.size == 0:
        return []

    height, width = image_bgr.shape[:2]
    try:
        detections = detector.predict(image_bgr)
    except Exception:
        return []

    candidates: list[PlateCandidate] = []
    for detection in detections or []:
        confidence = float(getattr(detection, "confidence", 0.0) or 0.0)
        if confidence < confidence_threshold:
            continue

        bbox = getattr(detection, "bounding_box", None)
        if bbox is None:
            continue

        candidate = _candidate_from_bbox(
            int(getattr(bbox, "x1", 0)),
            int(getattr(bbox, "y1", 0)),
            int(getattr(bbox, "x2", 0)),
            int(getattr(bbox, "y2", 0)),
            confidence,
            width,
            height,
        )
        if candidate is not None:
            candidates.append(candidate)

    candidates = sorted(candidates, key=lambda item: item.score, reverse=True)
    return _non_max_suppression(candidates, max_candidates)


def onnx_detector_error() -> str:
    return _DETECTOR_ERROR


def _get_detector():
    global _DETECTOR, _DETECTOR_ATTEMPTED, _DETECTOR_ERROR

    if os.environ.get("CHECK_VEHICLE_DISABLE_ONNX_DETECTOR"):
        return None
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
        try:
            import onnxruntime as ort

            session_options = ort.SessionOptions()
            session_options.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
            session_options.inter_op_num_threads = 1
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            bundled_model = _bundled_model_path()
            if bundled_model is not None:
                from open_image_models.detection.core.yolo_v9.inference import YoloV9ObjectDetector

                _DETECTOR = YoloV9ObjectDetector(
                    model_path=bundled_model,
                    conf_thresh=0.20,
                    class_labels=["License Plate"],
                    providers=["CPUExecutionProvider"],
                    sess_options=session_options,
                )
            else:
                from open_image_models import LicensePlateDetector
                import open_image_models.detection.core.hub as hub

                hub.MODEL_CACHE_DIR = _model_cache_dir()
                _DETECTOR = LicensePlateDetector(
                    detection_model=DEFAULT_ONNX_PLATE_MODEL,
                    conf_thresh=0.20,
                    providers=["CPUExecutionProvider"],
                    sess_options=session_options,
                )
            _DETECTOR_ERROR = ""
        except Exception as exc:
            _DETECTOR_ERROR = str(exc)
            _DETECTOR = None
        return _DETECTOR


def _model_cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_DIR_NAME / "models" / "open-image-models"
    return Path.home() / ".check_vehicle_ocr" / "models" / "open-image-models"


def _bundled_model_path() -> Path | None:
    roots = []
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        roots.append(Path(frozen_root))
    roots.append(Path(__file__).resolve().parents[1])

    for root in roots:
        model_path = root / "models" / "open-image-models" / DEFAULT_ONNX_PLATE_MODEL / DEFAULT_ONNX_PLATE_MODEL_FILE
        if model_path.exists():
            return model_path
    return None


def _candidate_from_bbox(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    confidence: float,
    image_width: int,
    image_height: int,
) -> PlateCandidate | None:
    x1 = max(0, min(x1, image_width - 1))
    y1 = max(0, min(y1, image_height - 1))
    x2 = max(0, min(x2, image_width))
    y2 = max(0, min(y2, image_height))
    if x2 <= x1 or y2 <= y1:
        return None

    width = x2 - x1
    height = y2 - y1
    if width < 18 or height < 8:
        return None

    aspect = width / max(height, 1)
    area_ratio = (width * height) / max(1, image_width * image_height)
    if not (0.45 <= aspect <= 8.5) or not (0.00003 <= area_ratio <= 0.22):
        return None

    pad_x = max(3, int(width * 0.14))
    pad_y = max(4, int(height * 0.34))
    crop_x1 = max(0, x1 - pad_x)
    crop_y1 = max(0, y1 - pad_y)
    crop_x2 = min(image_width, x2 + pad_x)
    crop_y2 = min(image_height, y2 + pad_y)
    crop_width = max(1, crop_x2 - crop_x1)
    crop_height = max(1, crop_y2 - crop_y1)

    score = 82.0 + min(18.0, confidence * 18.0)
    return PlateCandidate(
        bbox=(crop_x1, crop_y1, crop_width, crop_height),
        score=score,
        source="onnx_plate_detector",
    )


def _non_max_suppression(candidates: list[PlateCandidate], limit: int) -> list[PlateCandidate]:
    selected: list[PlateCandidate] = []
    for candidate in candidates:
        if all(_iou(candidate.bbox, existing.bbox) < 0.30 for existing in selected):
            selected.append(candidate)
            if len(selected) >= limit:
                break
    return selected


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    union_area = aw * ah + bw * bh - inter_area
    return inter_area / union_area if union_area else 0.0
