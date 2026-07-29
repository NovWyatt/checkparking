from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .models import OcrAttempt
from .ocr_models import DEFAULT_MODEL_PROFILE, PP_OCRV6_TINY
from .ocr import format_vietnam_plate, is_timestamp_like, looks_like_plate, normalize_plate_text, plate_quality_score


# PaddlePaddle 3.x CPU inference can trip a oneDNN PIR conversion bug on Windows.
# This env flag must be set before PaddleOCR initializes its predictors.
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

try:
    from paddleocr import PaddleOCR
except Exception:
    PaddleOCR = None


_PADDLE_LOCK = threading.Lock()
_PADDLE_OCR: Any | None = None
_PADDLE_INIT_ERROR = ""
# PP-OCRv6 Small passed the project synthetic staging checks on Windows CPU.
# The versioned model registry can explicitly select Tiny, Medium or the
# retained PP-OCRv5 pair for a subsequent launch without changing this default.
_TEXT_DETECTION_MODEL_NAME = DEFAULT_MODEL_PROFILE.detection_model
_TEXT_RECOGNITION_MODEL_NAME = DEFAULT_MODEL_PROFILE.recognition_model


class PaddleOcrEngine:
    def __init__(self, confidence_threshold: float = 25.0):
        self.confidence_threshold = confidence_threshold
        self.reason = ""
        if PaddleOCR is None:
            self.reason = "Python package paddleocr/paddlepaddle chưa được cài."

    @property
    def available(self) -> bool:
        if PaddleOCR is None:
            return False
        try:
            _get_ocr()
        except Exception as exc:
            self.reason = f"PaddleOCR chưa sẵn sàng: {exc}"
            return False
        return True

    def read_plate(self, crop_bgr: np.ndarray) -> OcrAttempt:
        if PaddleOCR is None:
            return OcrAttempt(engine="paddleocr", raw_text=self.reason)
        if crop_bgr.size == 0:
            return OcrAttempt(engine="paddleocr", raw_text="Empty crop")

        region_attempts = [attempt for _bbox, attempt in self.read_plate_regions(crop_bgr)]
        if region_attempts:
            return max(region_attempts, key=lambda item: item.confidence)

        return self.read_plate_variants(crop_bgr)

    def read_plate_variants(self, crop_bgr: np.ndarray) -> OcrAttempt:
        if PaddleOCR is None:
            return OcrAttempt(engine="paddleocr", raw_text=self.reason)
        if crop_bgr.size == 0:
            return OcrAttempt(engine="paddleocr", raw_text="Empty crop")

        try:
            ocr = _get_ocr()
        except Exception as exc:
            return OcrAttempt(engine="paddleocr", raw_text=str(exc))

        attempts: list[OcrAttempt] = []
        for preprocess_name, image_rgb in _preprocess_variants(crop_bgr):
            try:
                result = ocr.predict(image_rgb)
            except Exception as exc:
                attempts.append(OcrAttempt(engine="paddleocr", preprocess=preprocess_name, raw_text=str(exc)))
                continue
            attempts.append(_attempt_from_result(result, preprocess_name))

        return max(attempts, key=lambda item: item.confidence, default=OcrAttempt(engine="paddleocr"))

    def read_plate_regions(
        self,
        crop_bgr: np.ndarray,
        *,
        detector_limit_side_len: int | None = None,
        detector_limit_type: str | None = None,
    ) -> list[tuple[tuple[int, int, int, int], OcrAttempt]]:
        if PaddleOCR is None or crop_bgr.size == 0:
            return []
        try:
            ocr = _get_ocr()
            kwargs = _predict_kwargs(detector_limit_side_len, detector_limit_type)
            result = ocr.predict(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB), **kwargs)
        except Exception:
            return []
        return _region_attempts_from_result(result)

    def read_plate_regions_batch(
        self,
        crops_bgr: list[np.ndarray],
        *,
        detector_limit_side_len: int | None = None,
        detector_limit_type: str | None = None,
    ) -> list[list[tuple[tuple[int, int, int, int], OcrAttempt]]]:
        if PaddleOCR is None or not crops_bgr:
            return [[] for _crop in crops_bgr]

        valid_indices: list[int] = []
        rgb_images: list[np.ndarray] = []
        for index, crop_bgr in enumerate(crops_bgr):
            if crop_bgr.size == 0:
                continue
            valid_indices.append(index)
            rgb_images.append(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))

        output: list[list[tuple[tuple[int, int, int, int], OcrAttempt]]] = [[] for _crop in crops_bgr]
        if not rgb_images:
            return output

        try:
            ocr = _get_ocr()
            kwargs = _predict_kwargs(detector_limit_side_len, detector_limit_type)
            results = ocr.predict(rgb_images, **kwargs)
        except Exception:
            return output

        for source_index, result in zip(valid_indices, results or [], strict=False):
            output[source_index] = _region_attempts_from_result([result])
        return output


def _get_ocr():
    global _PADDLE_OCR, _PADDLE_INIT_ERROR
    if _PADDLE_OCR is not None:
        return _PADDLE_OCR
    if _PADDLE_INIT_ERROR:
        raise RuntimeError(_PADDLE_INIT_ERROR)

    with _PADDLE_LOCK:
        if _PADDLE_OCR is not None:
            return _PADDLE_OCR
        try:
            detection_model, recognition_model = _selected_model_names()
            bundled_model_dirs = _bundled_model_dirs(detection_model, recognition_model)
            _PADDLE_OCR = _create_ocr(bundled_model_dirs, detection_model, recognition_model)
        except Exception as exc:
            # A selected staged model is never allowed to brick local OCR.
            # Roll it back atomically and try the bundled/cache models once.
            # This guard runs only during initialization, before a shared OCR
            # instance is exposed to worker threads.
            if _has_active_staged_model():
                try:
                    from .model_registry import ModelRuntimeManager

                    ModelRuntimeManager().rollback()
                    _PADDLE_OCR = _create_ocr(
                        _bundled_model_dirs(detection_model, recognition_model, include_active=False),
                        detection_model,
                        recognition_model,
                    )
                    return _PADDLE_OCR
                except Exception:
                    pass
            _PADDLE_INIT_ERROR = str(exc)
            raise
    return _PADDLE_OCR


def _create_ocr(model_dirs: dict[str, str], detection_model: str = _TEXT_DETECTION_MODEL_NAME, recognition_model: str = _TEXT_RECOGNITION_MODEL_NAME):
    return PaddleOCR(
        text_detection_model_name=detection_model,
        text_detection_model_dir=model_dirs.get(detection_model),
        text_recognition_model_name=recognition_model,
        text_recognition_model_dir=model_dirs.get(recognition_model),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_det_limit_side_len=768,
        text_det_limit_type="min",
        text_rec_score_thresh=0.1,
    )


def _selected_model_names() -> tuple[str, str]:
    """Use only an accepted explicit selection; otherwise use v6 Small."""

    try:
        from .model_registry import ModelRuntimeManager

        selected = ModelRuntimeManager().active_model_selection()
        if selected:
            return selected
    except Exception:
        pass
    try:
        from .config import load_settings

        if str(load_settings().get("performance_preset") or "").upper() == "LOW_MEMORY":
            return PP_OCRV6_TINY.detection_model, PP_OCRV6_TINY.recognition_model
    except Exception:
        pass
    return _TEXT_DETECTION_MODEL_NAME, _TEXT_RECOGNITION_MODEL_NAME


def current_model_selection() -> tuple[str, str]:
    """Public, side-effect-free runtime model selection for status screens."""

    return _selected_model_names()


def _bundled_model_dirs(
    detection_model: str = _TEXT_DETECTION_MODEL_NAME,
    recognition_model: str = _TEXT_RECOGNITION_MODEL_NAME,
    *,
    include_active: bool = True,
) -> dict[str, str]:
    roots = []
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        roots.append(Path(frozen_root))
    roots.append(Path(__file__).resolve().parents[1])
    roots.append(Path.home() / ".paddlex")

    found: dict[str, str] = {}
    if include_active:
        try:
            from .model_registry import active_model_dirs

            found.update(active_model_dirs())
        except Exception:
            pass
    for root in roots:
        official_models = root / "models" / "paddleocr"
        if not official_models.exists():
            official_models = root / "official_models"
        for model_name in (detection_model, recognition_model):
            if model_name in found:
                continue
            model_dir = official_models / model_name
            if _is_valid_paddle_model_dir(model_dir):
                found[model_name] = str(model_dir)
    return found


def _has_active_staged_model() -> bool:
    try:
        from .model_registry import active_model_dirs

        return bool(active_model_dirs())
    except Exception:
        return False


def _is_valid_paddle_model_dir(model_dir: Path) -> bool:
    if not model_dir.is_dir():
        return False
    if not (model_dir / "inference.yml").exists():
        return False
    return any(model_dir.glob("*.pdmodel")) or any(model_dir.glob("*.json"))


def _predict_kwargs(detector_limit_side_len: int | None, detector_limit_type: str | None) -> dict[str, object]:
    kwargs: dict[str, object] = {}
    if detector_limit_side_len:
        kwargs["text_det_limit_side_len"] = int(detector_limit_side_len)
    if detector_limit_type:
        kwargs["text_det_limit_type"] = detector_limit_type
    return kwargs


def _attempt_from_result(result, preprocess_name: str) -> OcrAttempt:
    raw_groups: list[str] = []
    scored_texts: list[tuple[str, float]] = []

    for item in result or []:
        texts = list(_result_get(item, "rec_texts") or [])
        scores = list(_result_get(item, "rec_scores") or [])
        if texts:
            raw_groups.append(" ".join(str(text) for text in texts))
        for text, score in zip(texts, scores, strict=False):
            try:
                score_value = float(score) * 100.0
            except (TypeError, ValueError):
                score_value = 0.0
            scored_texts.append((str(text), score_value))

    raw_text = " | ".join(raw_groups)
    candidates = _candidate_strings(scored_texts)
    best = OcrAttempt(engine="paddleocr", preprocess=preprocess_name, raw_text=raw_text)
    for candidate_text, ocr_confidence in candidates:
        display_text = format_vietnam_plate(candidate_text)
        normalized = normalize_plate_text(display_text or candidate_text)
        quality = plate_quality_score(display_text or normalized, ocr_confidence)
        if quality > best.confidence:
            best = OcrAttempt(
                text=display_text,
                normalized_text=normalized,
                confidence=quality,
                # Keep the exact winning candidate.  The aggregate OCR group
                # may contain unrelated scene text and must not be used as a
                # plate's immutable raw value or strict batch formatter input.
                raw_text=candidate_text,
                engine="paddleocr",
                preprocess=preprocess_name,
            )
    return best


def _region_attempts_from_result(result) -> list[tuple[tuple[int, int, int, int], OcrAttempt]]:
    lines: list[dict[str, Any]] = []
    for item in result or []:
        texts = list(_result_get(item, "rec_texts") or [])
        scores = list(_result_get(item, "rec_scores") or [])
        boxes = _boxes_from_result(item)
        for index, text in enumerate(texts):
            clean = str(text).strip()
            if not clean or _is_noise_line(clean):
                continue
            score = _score_at(scores, index)
            box = boxes[index] if index < len(boxes) else (0, 0, 1, 1)
            lines.append({"text": clean, "score": score, "bbox": box})

    candidates: list[tuple[tuple[int, int, int, int], OcrAttempt]] = []
    for line in lines:
        candidates.append(_make_region_attempt([line], "paddle_region"))

    ordered = sorted(lines, key=lambda line: (line["bbox"][1], line["bbox"][0]))
    for index, first in enumerate(ordered):
        for second in ordered[index + 1 : index + 4]:
            if _can_group_plate_lines(first["bbox"], second["bbox"]):
                candidates.append(_make_region_attempt([first, second], "paddle_region_group"))
                for third in ordered[index + 2 : index + 6]:
                    if third is second:
                        continue
                    if _can_group_plate_lines(second["bbox"], third["bbox"]):
                        candidates.append(_make_region_attempt([first, second, third], "paddle_region_group3"))

    best_by_plate: dict[str, tuple[tuple[int, int, int, int], OcrAttempt]] = {}
    for bbox, attempt in candidates:
        if not attempt.normalized_text or not looks_like_plate(attempt.normalized_text):
            continue
        if is_timestamp_like(attempt.raw_text) or is_timestamp_like(attempt.text):
            continue
        previous = best_by_plate.get(attempt.normalized_text)
        if previous is None or attempt.confidence > previous[1].confidence:
            best_by_plate[attempt.normalized_text] = (bbox, attempt)

    return sorted(best_by_plate.values(), key=lambda item: item[1].confidence, reverse=True)


def _is_noise_line(text: str) -> bool:
    if is_timestamp_like(text):
        return True
    normalized = normalize_plate_text(text)
    return normalized in {"TIMEMARK", "CHAN", "THUC", "CHANTHUC"}


def _make_region_attempt(lines: list[dict[str, Any]], preprocess: str) -> tuple[tuple[int, int, int, int], OcrAttempt]:
    text = " ".join(line["text"] for line in lines)
    confidence = sum(float(line["score"]) for line in lines) / max(1, len(lines))
    display_text = format_vietnam_plate(text)
    normalized = normalize_plate_text(display_text or text)
    quality = plate_quality_score(display_text or normalized, confidence)
    bbox = _union_boxes([line["bbox"] for line in lines])
    return (
        bbox,
        OcrAttempt(
            text=display_text,
            normalized_text=normalized,
            confidence=quality,
            raw_text=text,
            engine="paddleocr",
            preprocess=preprocess,
        ),
    )


def _boxes_from_result(item) -> list[tuple[int, int, int, int]]:
    boxes = _result_get(item, "rec_boxes")
    if boxes is not None:
        return [_box_tuple(box) for box in list(boxes)]

    polys = _result_get(item, "rec_polys") or _result_get(item, "dt_polys") or []
    return [_poly_to_box(poly) for poly in list(polys)]


def _score_at(scores: list[Any], index: int) -> float:
    try:
        return float(scores[index]) * 100.0
    except (IndexError, TypeError, ValueError):
        return 0.0


def _box_tuple(box) -> tuple[int, int, int, int]:
    values = [int(float(value)) for value in list(box)]
    if len(values) >= 4:
        x1, y1, x2, y2 = values[:4]
        return (min(x1, x2), min(y1, y2), max(1, abs(x2 - x1)), max(1, abs(y2 - y1)))
    return (0, 0, 1, 1)


def _poly_to_box(poly) -> tuple[int, int, int, int]:
    points = np.asarray(poly).reshape(-1, 2)
    x1 = int(np.min(points[:, 0]))
    y1 = int(np.min(points[:, 1]))
    x2 = int(np.max(points[:, 0]))
    y2 = int(np.max(points[:, 1]))
    return (x1, y1, max(1, x2 - x1), max(1, y2 - y1))


def _union_boxes(boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    x1 = min(box[0] for box in boxes)
    y1 = min(box[1] for box in boxes)
    x2 = max(box[0] + box[2] for box in boxes)
    y2 = max(box[1] + box[3] for box in boxes)
    return (x1, y1, max(1, x2 - x1), max(1, y2 - y1))


def _can_group_plate_lines(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if by <= ay:
        return False

    vertical_gap = by - (ay + ah)
    if vertical_gap > max(ah, bh) * 0.95:
        return False

    ax2 = ax + aw
    bx2 = bx + bw
    horizontal_overlap = max(0, min(ax2, bx2) - max(ax, bx)) / max(1, min(aw, bw))
    center_distance = abs((ax + aw / 2) - (bx + bw / 2))
    return horizontal_overlap >= 0.18 or center_distance <= max(aw, bw) * 0.72


def _candidate_strings(scored_texts: list[tuple[str, float]]) -> list[tuple[str, float]]:
    if not scored_texts:
        return []

    candidates = [(text, score) for text, score in scored_texts if text.strip()]
    texts = [text for text, _score in candidates]
    if len(texts) > 1:
        avg_score = sum(score for _text, score in candidates) / len(candidates)
        candidates.append((" ".join(texts), avg_score))
        candidates.append(("".join(texts), avg_score))
    return candidates


def _result_get(item, key: str):
    if isinstance(item, dict):
        return item.get(key)
    getter = getattr(item, "get", None)
    if callable(getter):
        return getter(key)
    return getattr(item, key, None)


def _preprocess_variants(crop_bgr: np.ndarray) -> list[tuple[str, np.ndarray]]:
    height, width = crop_bgr.shape[:2]
    scale = max(1.0, 150 / max(height, 1))
    scale = min(scale, 3.0, 1300 / max(width, 1))
    if abs(scale - 1.0) > 0.01:
        resized = cv2.resize(crop_bgr, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_CUBIC)
    else:
        resized = crop_bgr.copy()

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    blur = cv2.GaussianBlur(clahe, (0, 0), 1.0)
    sharp = cv2.addWeighted(clahe, 1.65, blur, -0.65, 0)

    return [
        ("rgb", cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)),
        ("sharp", cv2.cvtColor(sharp, cv2.COLOR_GRAY2RGB)),
    ]
