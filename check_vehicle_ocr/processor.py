from __future__ import annotations

import re
import hashlib
import time
from pathlib import Path

import cv2
import numpy as np

from .image_io import load_image, save_crop
from .models import ExpectedPlateCount, ImageResult, PlateCandidate, coerce_expected_plate_count
from .ocr import TesseractOcrEngine, is_timestamp_like, looks_like_plate, plate_text_metadata
from .plate_detector import detect_plate_candidates_onnx, onnx_detector_error
from .plate_formatting import PlateFormatStatus, PlateType, coerce_plate_type, has_standard_vietnam_plate_shape
from .plate_selection import assess_plate_candidate, choose_primary_candidates


_STAGE_TIMING_KEYS = (
    "file_read_ms",
    "exif_ms",
    "decode_ms",
    "resize_ms",
    "detector_ms",
    "detector_postprocess_ms",
    "crop_ms",
    "paddle_det_ms",
    "paddle_rec_ms",
    "paddle_total_ms",
    "formatting_ms",
    "tesseract_ms",
    "candidate_filter_ms",
    "scoring_ms",
    "thumbnail_ms",
    "result_event_ms",
    "ui_render_ms",
    "total_ms",
)

_FAST_BALANCED_LONGEST_EDGE = 1280


def _prepare_stage_timings(stage_timings: dict[str, float] | None) -> None:
    if stage_timings is None:
        return
    for key in _STAGE_TIMING_KEYS:
        stage_timings.setdefault(key, 0.0)


def _record_stage_ms(stage_timings: dict[str, float] | None, key: str, started_at: float) -> None:
    if stage_timings is not None:
        stage_timings[key] = stage_timings.get(key, 0.0) + (time.perf_counter() - started_at) * 1000


def _restore_result_geometry(
    result: ImageResult,
    *,
    original_size: tuple[int, int],
    inverse_scale: float,
) -> None:
    if inverse_scale == 1.0:
        return
    original_width, original_height = original_size
    result.width = original_width
    result.height = original_height
    seen: set[int] = set()
    for candidate in [*result.plates, *result.rejected_candidates]:
        if id(candidate) in seen:
            continue
        seen.add(id(candidate))
        x, y, width, height = candidate.bbox
        left = max(0, min(original_width - 1, round(x * inverse_scale)))
        top = max(0, min(original_height - 1, round(y * inverse_scale)))
        right = max(left + 1, min(original_width, round((x + width) * inverse_scale)))
        bottom = max(top + 1, min(original_height, round((y + height) * inverse_scale)))
        candidate.bbox = (left, top, right - left, bottom - top)


def blur_score(image_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def detect_plate_candidates(image_bgr: np.ndarray, max_candidates: int = 12) -> list[PlateCandidate]:
    original_height, original_width = image_bgr.shape[:2]
    scale = min(1.0, 1600.0 / max(original_width, original_height))
    if scale < 1.0:
        resized = cv2.resize(image_bgr, (int(original_width * scale), int(original_height * scale)), interpolation=cv2.INTER_AREA)
    else:
        resized = image_bgr.copy()

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    blurred = cv2.GaussianBlur(clahe, (5, 5), 0)
    sobel_x = cv2.Sobel(blurred, cv2.CV_16S, 1, 0, ksize=3)
    abs_sobel_x = cv2.convertScaleAbs(sobel_x)

    kernel_width = max(25, int(resized.shape[1] / 45))
    rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 5))
    closed = cv2.morphologyEx(abs_sobel_x, cv2.MORPH_CLOSE, rect_kernel)
    _, thresh = cv2.threshold(closed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3)), iterations=1)
    thresh = cv2.erode(thresh, None, iterations=1)
    thresh = cv2.dilate(thresh, None, iterations=2)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[PlateCandidate] = []
    resized_area = resized.shape[0] * resized.shape[1]

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < 50 or h < 15:
            continue

        aspect = w / max(h, 1)
        area = w * h
        area_ratio = area / max(resized_area, 1)
        if _looks_like_timestamp_region(x, y, w, h, resized.shape[1], resized.shape[0], aspect, area_ratio):
            continue
        if not (1.4 <= aspect <= 6.8) or not (0.00025 <= area_ratio <= 0.18):
            continue

        contour_area = cv2.contourArea(contour)
        rectangularity = contour_area / max(area, 1)
        if rectangularity < 0.22:
            continue

        aspect_score = 1.0 - min(abs(aspect - 3.4) / 3.4, 1.0)
        area_score = min(area_ratio / 0.02, 1.0)
        vertical_score = 1.0 - abs((y + h / 2) / max(resized.shape[0], 1) - 0.58)
        score = (aspect_score * 45) + (rectangularity * 25) + (area_score * 20) + (vertical_score * 10)

        pad_x = int(w * 0.08)
        pad_y = int(h * 0.22)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(resized.shape[1], x + w + pad_x)
        y2 = min(resized.shape[0], y + h + pad_y)

        if scale < 1.0:
            x1 = int(x1 / scale)
            y1 = int(y1 / scale)
            x2 = int(x2 / scale)
            y2 = int(y2 / scale)

        candidates.append(PlateCandidate(bbox=(x1, y1, max(1, x2 - x1), max(1, y2 - y1)), score=score, source="first_pass"))

    return _non_max_suppression(sorted(candidates, key=lambda item: item.score, reverse=True), max_candidates)


def detect_plate_candidates_second_pass(image_bgr: np.ndarray, max_candidates: int = 12) -> list[PlateCandidate]:
    original_height, original_width = image_bgr.shape[:2]
    scale = min(1.0, 1500.0 / max(original_width, original_height))
    if scale < 1.0:
        resized = cv2.resize(image_bgr, (int(original_width * scale), int(original_height * scale)), interpolation=cv2.INTER_AREA)
    else:
        resized = image_bgr.copy()

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 45, 45)
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (31, 7)))
    grad = cv2.Sobel(blackhat, cv2.CV_16S, 1, 0, ksize=3)
    grad = cv2.convertScaleAbs(grad)
    grad = cv2.GaussianBlur(grad, (5, 5), 0)
    _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (35, 7)), iterations=1)
    thresh = cv2.dilate(thresh, None, iterations=1)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    resized_area = resized.shape[0] * resized.shape[1]
    candidates: list[PlateCandidate] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < 45 or h < 14:
            continue

        aspect = w / max(h, 1)
        area = w * h
        area_ratio = area / max(resized_area, 1)
        if _looks_like_timestamp_region(x, y, w, h, resized.shape[1], resized.shape[0], aspect, area_ratio):
            continue
        if not (0.85 <= aspect <= 7.4) or not (0.0002 <= area_ratio <= 0.20):
            continue

        rectangularity = cv2.contourArea(contour) / max(area, 1)
        if rectangularity < 0.16:
            continue

        pad_x = int(w * 0.10)
        pad_y = int(h * 0.28)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(resized.shape[1], x + w + pad_x)
        y2 = min(resized.shape[0], y + h + pad_y)
        if scale < 1.0:
            x1 = int(x1 / scale)
            y1 = int(y1 / scale)
            x2 = int(x2 / scale)
            y2 = int(y2 / scale)

        target_aspect = 1.35 if aspect < 1.8 else 3.2
        score = (rectangularity * 35) + ((1.0 - min(abs(aspect - target_aspect) / target_aspect, 1.0)) * 45) + 10
        candidates.append(PlateCandidate(bbox=(x1, y1, max(1, x2 - x1), max(1, y2 - y1)), score=score, source="second_pass"))

    return _non_max_suppression(sorted(candidates, key=lambda item: item.score, reverse=True), max_candidates)


def detect_plate_outline_candidates(image_bgr: np.ndarray, max_candidates: int = 8) -> list[PlateCandidate]:
    original_height, original_width = image_bgr.shape[:2]
    scale = min(1.0, 1500.0 / max(original_width, original_height))
    if scale < 1.0:
        resized = cv2.resize(image_bgr, (int(original_width * scale), int(original_height * scale)), interpolation=cv2.INTER_AREA)
    else:
        resized = image_bgr.copy()

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 40, 140)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (31, 9)), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    resized_area = resized.shape[0] * resized.shape[1]
    candidates: list[PlateCandidate] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < 65 or h < 24:
            continue

        aspect = w / max(h, 1)
        area_ratio = (w * h) / max(resized_area, 1)
        if _looks_like_timestamp_region(x, y, w, h, resized.shape[1], resized.shape[0], aspect, area_ratio):
            continue
        if not (0.9 <= aspect <= 6.8) or not (0.00045 <= area_ratio <= 0.22):
            continue

        x1 = max(0, x - int(w * 0.05))
        y1 = max(0, y - int(h * 0.12))
        x2 = min(resized.shape[1], x + w + int(w * 0.05))
        y2 = min(resized.shape[0], y + h + int(h * 0.12))
        if scale < 1.0:
            x1 = int(x1 / scale)
            y1 = int(y1 / scale)
            x2 = int(x2 / scale)
            y2 = int(y2 / scale)

        target_aspect = 1.35 if aspect < 1.8 else 3.3
        score = 64 + (1.0 - min(abs(aspect - target_aspect) / target_aspect, 1.0)) * 30
        candidates.append(PlateCandidate(bbox=(x1, y1, max(1, x2 - x1), max(1, y2 - y1)), score=score, source="outline_pass"))

    return _non_max_suppression(sorted(candidates, key=lambda item: item.score, reverse=True), max_candidates)


def fallback_candidates(image_bgr: np.ndarray) -> list[PlateCandidate]:
    height, width = image_bgr.shape[:2]
    rois = [
        (int(width * 0.10), int(height * 0.22), int(width * 0.80), int(height * 0.50), 12.0, "fallback_center"),
        (int(width * 0.08), int(height * 0.45), int(width * 0.84), int(height * 0.38), 10.0, "fallback_lower"),
        (int(width * 0.04), int(height * 0.34), int(width * 0.46), int(height * 0.44), 8.0, "fallback_left"),
        (int(width * 0.50), int(height * 0.34), int(width * 0.46), int(height * 0.44), 8.0, "fallback_right"),
    ]
    return [
        PlateCandidate(bbox=(x, y, max(1, w), max(1, h)), score=score, source=source)
        for x, y, w, h, score, source in rois
        if w > 0 and h > 0
    ]


def _legacy_process_image(
    image_path: Path,
    crop_dir: Path,
    ocr_engine: TesseractOcrEngine,
    blur_threshold: float = 80.0,
    confidence_threshold: float = 40.0,
    paddle_scan_mode: str = "balanced",
    image_bgr: np.ndarray | None = None,
    image_size: tuple[int, int] | None = None,
) -> ImageResult:
    if image_bgr is None:
        try:
            image_bgr, (width, height) = load_image(image_path)
        except Exception as exc:
            return ImageResult(image_path=image_path, status="ERROR", reason="Không đọc được file ảnh", error=str(exc))
    else:
        if image_size is None:
            height, width = image_bgr.shape[:2]
        else:
            width, height = image_size

    sharpness = blur_score(image_bgr)
    warnings: list[str] = []
    if sharpness < blur_threshold:
        warnings.append(f"Ảnh mờ, blur={sharpness:.1f} < {blur_threshold:.1f}")

    region_reader = getattr(ocr_engine, "read_plate_regions", None)
    can_read_regions = callable(region_reader)
    batch_region_reader = getattr(ocr_engine, "read_plate_regions_batch", None)
    fast_region_mode = can_read_regions and callable(batch_region_reader)
    paddle_mode = _normalize_paddle_scan_mode(paddle_scan_mode)

    if fast_region_mode:
        detector_candidates = (
            detect_plate_candidates_onnx(
                image_bgr,
                max_candidates=_onnx_detector_limit(paddle_mode),
                confidence_threshold=_onnx_detector_confidence(paddle_mode),
            )
            if _should_run_initial_onnx_detector(paddle_mode)
            else []
        )
        detector_error = onnx_detector_error()
        if detector_error:
            warnings.append(f"Không dùng được detector biển số; tiếp tục OCR fallback: {detector_error}")
        scene_candidates = [PlateCandidate(bbox=(0, 0, width, height), score=14.0, source="fallback_full_scene")]
        fallback_pool = fallback_candidates(image_bgr)[:1]
        if detector_candidates:
            candidates = _non_max_suppression(
                sorted([*detector_candidates, *fallback_pool, *scene_candidates], key=lambda item: item.score, reverse=True),
                _onnx_detector_limit(paddle_mode) + 2,
            )
        else:
            candidates = [*scene_candidates, *fallback_pool]
        detected_count = len(candidates)
    else:
        detector_candidates = []
        first_pass = detect_plate_candidates(image_bgr, max_candidates=10)
        second_pass = detect_plate_candidates_second_pass(image_bgr, max_candidates=10)
        outline_pass = detect_plate_outline_candidates(image_bgr, max_candidates=8)
        detected_candidates = _non_max_suppression(
            sorted([*first_pass, *second_pass, *outline_pass], key=lambda item: item.score, reverse=True),
            16,
        )
        detected_count = len(detected_candidates)
        scene_candidates = [PlateCandidate(bbox=(0, 0, width, height), score=6.0, source="fallback_full_scene")] if can_read_regions else []
        candidates = _non_max_suppression(
            sorted([*detected_candidates, *fallback_candidates(image_bgr), *scene_candidates], key=lambda item: item.score, reverse=True),
            18,
        )

    readable: list[PlateCandidate] = []
    uncertain: list[PlateCandidate] = []
    seen_plates: set[str] = set()
    best_failed: PlateCandidate | None = None

    def record_attempt(candidate: PlateCandidate, attempt) -> bool:
        nonlocal best_failed
        candidate.text = attempt.text
        cleaned_text, suggested_texts, ambiguity_flags, needs_review = plate_text_metadata(attempt.raw_text or attempt.text)
        candidate.cleaned_text = attempt.cleaned_text or cleaned_text
        candidate.normalized_text = attempt.normalized_text or candidate.cleaned_text
        candidate.suggested_texts = list(attempt.suggested_texts or suggested_texts)
        candidate.ambiguity_flags = list(attempt.ambiguity_flags or ambiguity_flags)
        candidate.needs_review = bool(attempt.needs_review or needs_review)
        candidate.confidence = attempt.confidence
        candidate.raw_text = attempt.raw_text
        if attempt.engine == "paddleocr":
            candidate.paddle_raw = attempt.raw_text
            candidate.paddle_candidate = candidate.normalized_text or attempt.text
            candidate.paddle_confidence = attempt.confidence
            candidate.selected_engine = "paddleocr"
            candidate.selection_reason = "Kết quả PaddleOCR ban đầu."
        elif attempt.engine == "tesseract":
            candidate.tesseract_raw = attempt.raw_text
            candidate.tesseract_candidate = candidate.normalized_text or attempt.text
            candidate.tesseract_confidence = attempt.confidence
            candidate.selected_engine = "tesseract"
            candidate.selection_reason = "Kết quả Tesseract."

        if is_timestamp_like(candidate.raw_text) or is_timestamp_like(candidate.text) or is_timestamp_like(candidate.normalized_text):
            candidate.reason = "Bỏ qua vì giống timestamp/time mark trên ảnh"
            return False

        if candidate.normalized_text and looks_like_plate(candidate.normalized_text) and candidate.confidence >= confidence_threshold:
            overlapping_plate = _find_overlapping_plate_variant(candidate, readable)
            if overlapping_plate is None:
                overlapping_plate = _find_overlapping_plate_conflict(candidate, readable)
            if overlapping_plate:
                if _prefer_plate_candidate(candidate, overlapping_plate):
                    overlapping_plate.readable = False
                    readable.remove(overlapping_plate)
                    seen_plates.discard(overlapping_plate.normalized_text)
                else:
                    return False
            if candidate.normalized_text not in seen_plates:
                candidate.readable = True
                seen_plates.add(candidate.normalized_text)
                readable.append(candidate)
                return True
            return False

        candidate.reason = "OCR thấp tin cậy hoặc không ra biển số"
        if best_failed is None or candidate.confidence > best_failed.confidence:
            best_failed = candidate
        if candidate.confidence >= 20 or candidate.text:
            uncertain.append(candidate)
            return True
        return False

    if can_read_regions and callable(batch_region_reader):
        prepared_candidates: list[dict[str, object]] = []
        def prepare_candidate(index: int, candidate: PlateCandidate, *, mask_timestamp: bool) -> dict[str, object] | None:
            can_contain_multiple = _can_contain_multiple_plates(candidate.bbox, width, height, candidate.source)
            x, y, w, h = candidate.bbox
            crop = image_bgr[y : y + h, x : x + w]
            if crop.size == 0:
                return None
            crop_for_ocr = _mask_timestamp_overlay(crop, candidate.bbox, width, height) if mask_timestamp and can_contain_multiple else crop
            return {
                "index": index,
                "candidate": candidate,
                "crop": crop_for_ocr,
                "can_contain_multiple": can_contain_multiple,
                "recorded_region": False,
            }

        for index, candidate in enumerate(candidates, start=1):
            prepared = prepare_candidate(index, candidate, mask_timestamp=True)
            if prepared is not None:
                prepared_candidates.append(prepared)

        def process_region_records(prepared: dict[str, object], region_records) -> None:
            candidate = prepared["candidate"]
            if paddle_mode != "thorough" and bool(prepared["can_contain_multiple"]) and readable:
                return
            if paddle_mode != "thorough" and bool(prepared["can_contain_multiple"]):
                region_records = list(region_records or [])[:1]
            crop_for_ocr = prepared["crop"]
            index = int(prepared["index"])
            x, y, _w, _h = candidate.bbox
            for region_index, (local_bbox, attempt) in enumerate(region_records, start=1):
                rx, ry, rw, rh = local_bbox
                global_bbox = (x + rx, y + ry, max(1, rw), max(1, rh))
                region_candidate = PlateCandidate(
                    bbox=global_bbox,
                    score=max(candidate.score, attempt.confidence),
                    source=f"{candidate.source}:{attempt.preprocess or 'paddle_region'}",
                )
                crop_name = f"{_safe_stem(image_path.stem)}_{_path_hash(image_path)}_{index:02d}_{region_index:02d}_{_safe_stem(region_candidate.source)}.jpg"
                region_candidate.crop_path = crop_dir / crop_name
                region_crop = crop_for_ocr[max(0, ry) : max(0, ry) + max(1, rh), max(0, rx) : max(0, rx) + max(1, rw)]
                if region_crop.size:
                    save_crop(region_crop, region_candidate.crop_path)
                if record_attempt(region_candidate, attempt):
                    prepared["recorded_region"] = True

        def run_region_batch(items: list[dict[str, object]], detector_limit_side_len: int | None = None, detector_limit_type: str | None = None) -> None:
            if not items:
                return
            crops = [item["crop"] for item in items]
            try:
                batches = batch_region_reader(
                    crops,
                    detector_limit_side_len=detector_limit_side_len,
                    detector_limit_type=detector_limit_type,
                )
            except TypeError:
                batches = [region_reader(crop) for crop in crops]
            for item, region_records in zip(items, batches or [], strict=False):
                process_region_records(item, region_records)

        small_candidates = [item for item in prepared_candidates if not bool(item["can_contain_multiple"])]
        large_candidates = [item for item in prepared_candidates if bool(item["can_contain_multiple"])]
        run_region_batch(small_candidates)
        if _should_run_initial_large_regions(readable, detector_candidates, sharpness, blur_threshold, paddle_mode):
            primary_large_candidates = large_candidates if paddle_mode == "thorough" else large_candidates[:1]
            run_region_batch(primary_large_candidates, detector_limit_side_len=960, detector_limit_type="max")
            if not readable and paddle_mode != "thorough":
                run_region_batch(large_candidates[1:], detector_limit_side_len=960, detector_limit_type="max")

        if _should_run_onnx_rescue(readable, uncertain, detector_candidates, sharpness, blur_threshold, paddle_mode):
            onnx_offset = len(prepared_candidates) + 1
            detector_candidates = detect_plate_candidates_onnx(
                image_bgr,
                max_candidates=_onnx_detector_limit(paddle_mode),
                confidence_threshold=_onnx_detector_confidence(paddle_mode),
            )
            detector_error = onnx_detector_error()
            if detector_error and not any("detector biển số" in warning for warning in warnings):
                warnings.append(f"Không dùng được detector biển số; tiếp tục OCR fallback: {detector_error}")
            onnx_prepared = [
                prepared
                for index, candidate in enumerate(detector_candidates, start=onnx_offset)
                if (prepared := prepare_candidate(index, candidate, mask_timestamp=True)) is not None
            ]
            run_region_batch(onnx_prepared, detector_limit_side_len=704, detector_limit_type="max")

        focus_rescue_ran = False
        if fast_region_mode and _should_run_paddle_core_rescue(readable, uncertain, sharpness, blur_threshold, paddle_mode):
            rescue_offset = len(prepared_candidates) + 1
            rescue_core = _paddle_rescue_core_candidates(image_bgr, include_sides=paddle_mode == "thorough")
            rescue_prepared = [
                prepared
                for index, candidate in enumerate(rescue_core, start=rescue_offset)
                if (prepared := prepare_candidate(index, candidate, mask_timestamp=True)) is not None
            ]
            run_region_batch(rescue_prepared, detector_limit_side_len=960, detector_limit_type="max")

            if _should_run_paddle_focus_rescue(readable, uncertain, sharpness, blur_threshold, paddle_mode):
                focus_offset = rescue_offset + len(rescue_prepared)
                focus_prepared = [
                    prepared
                    for index, candidate in enumerate(
                        _paddle_focus_tile_candidates(width, height, thorough=paddle_mode == "thorough"),
                        start=focus_offset,
                    )
                    if (prepared := prepare_candidate(index, candidate, mask_timestamp=True)) is not None
                ]
                focus_limit = 768 if paddle_mode in {"fast", "thorough"} else 704
                run_region_batch(focus_prepared, detector_limit_side_len=focus_limit, detector_limit_type="max")
                focus_rescue_ran = True

        if (
            fast_region_mode
            and not focus_rescue_ran
            and _should_run_paddle_focus_rescue(readable, uncertain, sharpness, blur_threshold, paddle_mode)
        ):
            focus_offset = len(prepared_candidates) + 1
            focus_prepared = [
                prepared
                for index, candidate in enumerate(
                    _paddle_focus_tile_candidates(width, height, thorough=paddle_mode == "thorough"),
                    start=focus_offset,
                )
                if (prepared := prepare_candidate(index, candidate, mask_timestamp=True)) is not None
            ]
            focus_limit = 768 if paddle_mode == "thorough" else 704
            run_region_batch(focus_prepared, detector_limit_side_len=focus_limit, detector_limit_type="max")

        variant_reader = getattr(ocr_engine, "read_plate_variants", None)
        single_fallback_budget = 2 if not readable else 1
        for prepared in prepared_candidates:
            if single_fallback_budget <= 0:
                break
            if bool(prepared["recorded_region"]) or bool(prepared["can_contain_multiple"]):
                continue
            candidate = prepared["candidate"]
            if readable and any(_overlap_ratio(candidate.bbox, existing.bbox) > 0.45 for existing in readable):
                continue
            crop_for_ocr = prepared["crop"]
            index = int(prepared["index"])
            crop_name = f"{_safe_stem(image_path.stem)}_{_path_hash(image_path)}_{index:02d}_{_safe_stem(candidate.source)}.jpg"
            candidate.crop_path = crop_dir / crop_name
            save_crop(crop_for_ocr, candidate.crop_path)
            if callable(variant_reader):
                attempt = variant_reader(crop_for_ocr)
            else:
                attempt = ocr_engine.read_plate(crop_for_ocr)
            record_attempt(candidate, attempt)
            single_fallback_budget -= 1
    else:
        for index, candidate in enumerate(candidates, start=1):
            can_contain_multiple = _can_contain_multiple_plates(candidate.bbox, width, height, candidate.source)
            if readable and not can_contain_multiple and any(_overlap_ratio(candidate.bbox, existing.bbox) > 0.45 for existing in readable):
                continue

            x, y, w, h = candidate.bbox
            crop = image_bgr[y : y + h, x : x + w]
            if crop.size == 0:
                continue

            crop_for_ocr = _mask_timestamp_overlay(crop, candidate.bbox, width, height) if can_contain_multiple else crop

            if can_read_regions:
                region_records = region_reader(crop_for_ocr)
                recorded_region = False
                for region_index, (local_bbox, attempt) in enumerate(region_records, start=1):
                    rx, ry, rw, rh = local_bbox
                    global_bbox = (x + rx, y + ry, max(1, rw), max(1, rh))
                    region_candidate = PlateCandidate(
                        bbox=global_bbox,
                        score=max(candidate.score, attempt.confidence),
                        source=f"{candidate.source}:{attempt.preprocess or 'paddle_region'}",
                    )
                    crop_name = f"{_safe_stem(image_path.stem)}_{_path_hash(image_path)}_{index:02d}_{region_index:02d}_{_safe_stem(region_candidate.source)}.jpg"
                    region_candidate.crop_path = crop_dir / crop_name
                    region_crop = crop_for_ocr[max(0, ry) : max(0, ry) + max(1, rh), max(0, rx) : max(0, rx) + max(1, rw)]
                    if region_crop.size:
                        save_crop(region_crop, region_candidate.crop_path)
                    if record_attempt(region_candidate, attempt):
                        recorded_region = True
                if recorded_region or can_contain_multiple:
                    continue

            crop_name = f"{_safe_stem(image_path.stem)}_{_path_hash(image_path)}_{index:02d}_{_safe_stem(candidate.source)}.jpg"
            candidate.crop_path = crop_dir / crop_name
            save_crop(crop_for_ocr, candidate.crop_path)

            attempt = ocr_engine.read_plate(crop_for_ocr)
            record_attempt(candidate, attempt)

    readable = _filter_readable_plates(readable, width, height, paddle_mode)
    if readable:
        reason = "Đọc được biển số"
        status = "OK"
        if warnings:
            reason += "; cần đối chiếu vì ảnh mờ"
        review_plates = [*readable]
        for candidate in sorted(uncertain, key=lambda item: item.confidence, reverse=True):
            if len(review_plates) >= len(readable) + 3:
                break
            if all(_iou(candidate.bbox, existing.bbox) < 0.35 for existing in review_plates):
                review_plates.append(candidate)
        return ImageResult(
            image_path=image_path,
            status=status,
            reason=reason,
            blur_score=sharpness,
            width=width,
            height=height,
            candidate_count=detected_count,
            plates=review_plates,
            warnings=warnings,
        )

    if sharpness < blur_threshold:
        status = "BLURRY"
        reason = "Ảnh mờ và không đọc được biển số"
    elif detected_count == 0:
        status = "UNREADABLE"
        reason = "Không tìm thấy vùng nghi biển số"
    else:
        status = "UNREADABLE"
        reason = "Có vùng nghi biển số nhưng OCR không đủ tin cậy"

    plates = sorted(uncertain, key=lambda item: item.confidence, reverse=True)[:3]
    if not plates and best_failed:
        plates = [best_failed]
    return ImageResult(
        image_path=image_path,
        status=status,
        reason=reason,
        blur_score=sharpness,
        width=width,
        height=height,
        candidate_count=detected_count,
        plates=plates,
        warnings=warnings,
    )


def _safe_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "image"


def _expanded_detector_crop(image_bgr: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    """Return one modestly larger crop for a failed compact detector crop."""

    image_height, image_width = image_bgr.shape[:2]
    x, y, width, height = bbox
    pad_x = max(3, round(width * 0.11))
    pad_y = max(3, round(height * 0.12))
    left = max(0, x - pad_x)
    top = max(0, y - pad_y)
    right = min(image_width, x + width + pad_x)
    bottom = min(image_height, y + height + pad_y)
    return image_bgr[top:bottom, left:right]


def _path_hash(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:8]


def _looks_like_timestamp_region(x: int, y: int, w: int, h: int, image_width: int, image_height: int, aspect: float, area_ratio: float) -> bool:
    center_x = x + (w / 2)
    center_y = y + (h / 2)
    in_corner_x = center_x < image_width * 0.34 or center_x > image_width * 0.66
    in_timestamp_band = center_y < image_height * 0.20 or center_y > image_height * 0.78
    is_small_text = h < image_height * 0.065 and area_ratio < 0.025
    is_date_like_shape = aspect > 4.2 and area_ratio < 0.035
    return in_corner_x and in_timestamp_band and (is_small_text or is_date_like_shape)


def _can_contain_multiple_plates(bbox: tuple[int, int, int, int], image_width: int, image_height: int, source: str) -> bool:
    _x, _y, w, h = bbox
    area_ratio = (w * h) / max(1, image_width * image_height)
    return source.startswith("fallback") or area_ratio >= 0.08


def _normalize_paddle_scan_mode(value: str) -> str:
    text = str(value or "").strip().casefold()
    if text in {"fast", "nhanh"}:
        return "fast"
    if text in {"thorough", "careful", "deep", "ky", "kỹ", "quet ky", "quét kỹ"}:
        return "thorough"
    return "balanced"


def _onnx_detector_limit(scan_mode: str) -> int:
    if scan_mode == "fast":
        return 5
    if scan_mode == "thorough":
        return 12
    return 8


def _onnx_detector_confidence(scan_mode: str) -> float:
    if scan_mode == "fast":
        return 0.30
    if scan_mode == "thorough":
        return 0.20
    return 0.25


def _should_run_initial_onnx_detector(scan_mode: str) -> bool:
    return scan_mode == "thorough"


def _should_run_onnx_rescue(
    readable: list[PlateCandidate],
    uncertain: list[PlateCandidate],
    detector_candidates: list[PlateCandidate],
    sharpness: float,
    blur_threshold: float,
    scan_mode: str,
) -> bool:
    if detector_candidates or scan_mode == "fast":
        return False
    if scan_mode == "thorough":
        return True
    if readable:
        return False
    if not _sharp_enough_for_extra_paddle_pass(sharpness, blur_threshold):
        return False
    return len(uncertain) >= 1


def _should_run_initial_large_regions(
    readable: list[PlateCandidate],
    detector_candidates: list[PlateCandidate],
    sharpness: float,
    blur_threshold: float,
    scan_mode: str,
) -> bool:
    if not detector_candidates:
        return True
    if scan_mode == "thorough":
        return True
    if not readable:
        return True
    if scan_mode == "fast":
        return False
    expected_from_detector = min(2, len(detector_candidates))
    return len(readable) < expected_from_detector and _sharp_enough_for_extra_paddle_pass(sharpness, blur_threshold)


def _sharp_enough_for_extra_paddle_pass(sharpness: float, blur_threshold: float) -> bool:
    return sharpness >= max(42.0, blur_threshold * 0.52)


def _should_run_paddle_core_rescue(
    readable: list[PlateCandidate],
    uncertain: list[PlateCandidate],
    sharpness: float,
    blur_threshold: float,
    scan_mode: str,
) -> bool:
    if not readable:
        return True
    if scan_mode == "fast":
        return False
    if scan_mode == "thorough":
        return False
    if scan_mode != "thorough":
        return False
    if not _sharp_enough_for_extra_paddle_pass(sharpness, blur_threshold):
        return False
    return len(readable) < 4


def _should_run_paddle_focus_rescue(
    readable: list[PlateCandidate],
    uncertain: list[PlateCandidate],
    sharpness: float,
    blur_threshold: float,
    scan_mode: str,
) -> bool:
    if scan_mode == "fast":
        return not readable
    if not _sharp_enough_for_extra_paddle_pass(sharpness, blur_threshold):
        return False
    if scan_mode == "thorough":
        return not readable
    if not readable:
        return True
    return False


def _filter_readable_plates(
    plates: list[PlateCandidate],
    image_width: int,
    image_height: int,
    scan_mode: str,
) -> list[PlateCandidate]:
    if len(plates) <= 1:
        return plates

    candidates: list[PlateCandidate] = []
    for plate in plates:
        if not _looks_like_overlay_ocr_plate(plate, image_width, image_height):
            candidates.append(plate)
        else:
            plate.readable = False

    if len(candidates) <= 1:
        return candidates

    ordered = sorted(candidates, key=lambda item: item.confidence, reverse=True)
    best = ordered[0]
    filtered = [best]
    for plate in ordered[1:]:
        if any(_overlap_ratio(plate.bbox, kept.bbox) >= 0.55 or _iou(plate.bbox, kept.bbox) >= 0.35 for kept in filtered):
            plate.readable = False
            continue
        if _same_plate_variant(plate.normalized_text, best.normalized_text) or _plate_texts_are_close(plate.normalized_text, best.normalized_text):
            plate.readable = False
            continue
        if scan_mode == "thorough" and _looks_like_rescue_noise(plate, best, image_width, image_height):
            plate.readable = False
            continue
        filtered.append(plate)

    return sorted(filtered, key=lambda item: plates.index(item))


def _looks_like_overlay_ocr_plate(plate: PlateCandidate, image_width: int, image_height: int) -> bool:
    x, y, w, h = plate.bbox
    area_ratio = (w * h) / max(1, image_width * image_height)
    aspect = w / max(1, h)
    if _looks_like_timestamp_region(x, y, w, h, image_width, image_height, aspect, area_ratio):
        return True

    center_y = y + h / 2
    if center_y > image_height * 0.76 and area_ratio < 0.09:
        return True

    center_x = x + w / 2
    if center_x > image_width * 0.82 and h > w * 1.35:
        return True

    return False


def _looks_like_rescue_noise(
    plate: PlateCandidate,
    best: PlateCandidate,
    image_width: int,
    image_height: int,
) -> bool:
    noisy_source = any(token in plate.source for token in ("fallback_full_scene", "rescue_full", "rescue_focus_tile", "unmasked"))
    if not noisy_source:
        return False

    if plate.confidence <= best.confidence - 8.0:
        return True

    x, y, w, h = plate.bbox
    area_ratio = (w * h) / max(1, image_width * image_height)
    aspect = w / max(1, h)
    if area_ratio < 0.001 or area_ratio > 0.12:
        return True
    if not (0.75 <= aspect <= 7.0):
        return True

    bx, by, bw, bh = best.bbox
    center_distance = abs((x + w / 2) - (bx + bw / 2)) + abs((y + h / 2) - (by + bh / 2))
    if center_distance < max(image_width, image_height) * 0.10:
        return True

    return False


def _paddle_rescue_core_candidates(image_bgr: np.ndarray, *, include_sides: bool = False) -> list[PlateCandidate]:
    height, width = image_bgr.shape[:2]
    broad = fallback_candidates(image_bgr)
    rescue = [PlateCandidate(bbox=(0, 0, width, height), score=9.0, source="rescue_full_unmasked")]
    limit = 4 if include_sides else 2
    for candidate in broad[:limit]:
        rescue.append(PlateCandidate(bbox=candidate.bbox, score=candidate.score, source=f"rescue_{candidate.source}_unmasked"))
    return rescue


def _paddle_focus_tile_candidates(image_width: int, image_height: int, *, thorough: bool = False) -> list[PlateCandidate]:
    tile_width = int(image_width * 0.38)
    tile_height = int(image_height * 0.34)
    candidates: list[PlateCandidate] = []
    y_fractions = (0.16, 0.38, 0.56) if thorough else (0.16, 0.38)
    for y_fraction in y_fractions:
        for x_fraction in (0.04, 0.31, 0.58):
            x = min(max(0, int(image_width * x_fraction)), max(0, image_width - tile_width))
            y = min(max(0, int(image_height * y_fraction)), max(0, image_height - tile_height))
            candidates.append(
                PlateCandidate(
                    bbox=(x, y, max(1, tile_width), max(1, tile_height)),
                    score=7.0,
                    source="rescue_focus_tile",
                )
            )
    return candidates


def _find_overlapping_plate_variant(candidate: PlateCandidate, existing_plates: list[PlateCandidate]) -> PlateCandidate | None:
    for existing in existing_plates:
        if not _same_plate_variant(candidate.normalized_text, existing.normalized_text):
            continue
        if _overlap_ratio(candidate.bbox, existing.bbox) >= 0.25 or _iou(candidate.bbox, existing.bbox) >= 0.18:
            return existing
    return None


def _find_overlapping_plate_conflict(candidate: PlateCandidate, existing_plates: list[PlateCandidate]) -> PlateCandidate | None:
    for existing in existing_plates:
        if _overlap_ratio(candidate.bbox, existing.bbox) < 0.35 and _iou(candidate.bbox, existing.bbox) < 0.20:
            continue
        if _plate_texts_are_close(candidate.normalized_text, existing.normalized_text):
            return existing
    return None


def _same_plate_variant(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    return len(shorter) >= 6 and shorter in longer


def _plate_texts_are_close(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) < 6 or len(b) < 6:
        return False
    if a[:2] != b[:2]:
        return False
    max_distance = 1 if max(len(a), len(b)) <= 7 else 2
    return _bounded_edit_distance(a, b, max_distance) <= max_distance


def _bounded_edit_distance(a: str, b: str, max_distance: int) -> int:
    if abs(len(a) - len(b)) > max_distance:
        return max_distance + 1
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        row_min = i
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            value = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            current.append(value)
            row_min = min(row_min, value)
        if row_min > max_distance:
            return max_distance + 1
        previous = current
    return previous[-1]


def _prefer_plate_candidate(candidate: PlateCandidate, existing: PlateCandidate) -> bool:
    length_gain = len(candidate.normalized_text) - len(existing.normalized_text)
    if length_gain >= 2:
        return True
    if length_gain <= -2:
        return False
    return candidate.confidence > existing.confidence + 3.0


def _mask_timestamp_overlay(crop_bgr: np.ndarray, bbox: tuple[int, int, int, int], image_width: int, image_height: int) -> np.ndarray:
    if crop_bgr.size == 0:
        return crop_bgr

    masked = crop_bgr.copy()
    overlay_regions = [
        (0, int(image_height * 0.76), int(image_width * 0.58), int(image_height * 0.24)),
        (int(image_width * 0.58), int(image_height * 0.76), int(image_width * 0.42), int(image_height * 0.24)),
        (0, 0, int(image_width * 0.55), int(image_height * 0.16)),
        (int(image_width * 0.45), 0, int(image_width * 0.55), int(image_height * 0.16)),
    ]

    x, y, w, h = bbox
    fill_color = tuple(int(value) for value in np.median(masked.reshape(-1, 3), axis=0))
    for ox, oy, ow, oh in overlay_regions:
        ix1 = max(x, ox)
        iy1 = max(y, oy)
        ix2 = min(x + w, ox + ow)
        iy2 = min(y + h, oy + oh)
        if ix2 <= ix1 or iy2 <= iy1:
            continue
        local_x1 = max(0, ix1 - x)
        local_y1 = max(0, iy1 - y)
        local_x2 = min(w, ix2 - x)
        local_y2 = min(h, iy2 - y)
        if local_x2 > local_x1 and local_y2 > local_y1:
            cv2.rectangle(masked, (local_x1, local_y1), (local_x2, local_y2), fill_color, thickness=-1)
    return masked


def process_image(
    image_path: Path,
    crop_dir: Path,
    ocr_engine: TesseractOcrEngine,
    blur_threshold: float = 80.0,
    confidence_threshold: float = 40.0,
    paddle_scan_mode: str = "balanced",
    image_bgr: np.ndarray | None = None,
    image_size: tuple[int, int] | None = None,
    selected_plate_type: PlateType | str | None = PlateType.NONE,
    expected_plate_count: ExpectedPlateCount | str | None = ExpectedPlateCount.ONE,
    stage_timings: dict[str, float] | None = None,
) -> ImageResult:
    """Run the bounded detector-first local OCR pipeline.

    Previous releases sent full images and broad rescue tiles through PaddleOCR
    before a valid plate was selected.  Camera overlays then became false
    plate candidates.  This path treats plate detection as the gate: FAST and
    BALANCED OCR only a few detector crops and stop as soon as one clear plate
    is found.  A full-scene Paddle pass is a single, bounded fallback only.
    """

    pipeline_started = time.perf_counter()
    _prepare_stage_timings(stage_timings)
    original_size = (0, 0)
    inverse_working_scale = 1.0

    def finish(result: ImageResult) -> ImageResult:
        _restore_result_geometry(result, original_size=original_size, inverse_scale=inverse_working_scale)
        if stage_timings is not None:
            stage_timings["total_ms"] = (time.perf_counter() - pipeline_started) * 1000
        return result

    if image_bgr is None:
        try:
            image_bgr, (width, height) = load_image(image_path, stage_timings=stage_timings)
        except Exception as exc:
            return finish(ImageResult(image_path=image_path, status="ERROR", reason="Không đọc được file ảnh", error=str(exc)))
    elif image_size is None:
        height, width = image_bgr.shape[:2]
    else:
        width, height = image_size

    selected_type = coerce_plate_type(selected_plate_type)
    expected_count = coerce_expected_plate_count(expected_plate_count)
    scan_mode = _normalize_paddle_scan_mode(paddle_scan_mode)
    original_size = (width, height)
    if scan_mode in {"fast", "balanced"} and max(width, height) > _FAST_BALANCED_LONGEST_EDGE:
        resize_started = time.perf_counter()
        working_scale = _FAST_BALANCED_LONGEST_EDGE / max(width, height)
        width = max(1, round(width * working_scale))
        height = max(1, round(height * working_scale))
        image_bgr = cv2.resize(image_bgr, (width, height), interpolation=cv2.INTER_AREA)
        inverse_working_scale = 1.0 / working_scale
        _record_stage_ms(stage_timings, "resize_ms", resize_started)
    sharpness = blur_score(image_bgr)
    warnings = [f"Ảnh mờ, blur={sharpness:.1f} < {blur_threshold:.1f}"] if sharpness < blur_threshold else []
    metrics: dict[str, int | float | str] = {
        "detector_calls": 0,
        "crop_ocr_calls": 0,
        "full_scene_ocr_calls": 0,
        "small_verification_ocr_calls": 0,
        "tesseract_calls": 0,
        "ai_calls": 0,
        "candidates_before_filter": 0,
        "candidates_after_filter": 0,
        "selected_candidate_reason": "",
    }
    rejected: list[PlateCandidate] = []
    accepted: list[PlateCandidate] = []

    detector_candidates = _detector_first_regions(image_bgr, scan_mode, metrics, stage_timings=stage_timings)
    crop_limit = 2 if scan_mode == "fast" else (3 if scan_mode == "balanced" else 6)
    region_reader = getattr(ocr_engine, "read_plate_regions", None)
    fast_verification_reader = getattr(ocr_engine, "read_plate_regions_fast_verification", None)
    variant_reader = getattr(ocr_engine, "read_plate_variants", None)
    can_read_regions = callable(region_reader)

    def record_attempt(
        detector_candidate: PlateCandidate,
        attempt,
        *,
        source: str,
        bbox: tuple[int, int, int, int] | None = None,
        crop_path: Path | None = None,
    ) -> PlateCandidate:
        metrics["candidates_before_filter"] = int(metrics["candidates_before_filter"]) + 1
        candidate = PlateCandidate(
            bbox=bbox or detector_candidate.bbox,
            score=detector_candidate.score,
            source=source,
            crop_path=crop_path,
            text=attempt.text or attempt.raw_text,
            raw_text=attempt.raw_text or attempt.text,
            normalized_text=attempt.normalized_text,
            cleaned_text=attempt.cleaned_text,
            suggested_texts=list(attempt.suggested_texts),
            ambiguity_flags=list(attempt.ambiguity_flags),
            confidence=float(attempt.confidence or 0.0),
            detector_confidence=detector_candidate.detector_confidence or detector_candidate.score,
            selected_engine=attempt.engine or "paddleocr",
        )
        filter_started = time.perf_counter()
        assessment = assess_plate_candidate(candidate, plate_type=selected_type, image_size=(width, height))
        _record_stage_ms(stage_timings, "candidate_filter_ms", filter_started)
        candidate.cleaned_text = assessment.cleaned_text
        candidate.normalized_text = assessment.cleaned_text
        candidate.selection_score = assessment.score
        candidate.score = assessment.score
        candidate.selection_reason = assessment.reason
        if not assessment.accepted:
            candidate.readable = False
            candidate.candidate_status = PlateFormatStatus.REJECTED_NOISE.value
            candidate.format_status = PlateFormatStatus.REJECTED_NOISE
            candidate.reason = assessment.reason
            candidate.rejected_reason = assessment.reason
            rejected.append(candidate)
            return candidate

        candidate.ocr_needs_review = bool(candidate.ambiguity_flags)
        formatting_started = time.perf_counter()
        decision = candidate.apply_plate_formatting(selected_type)
        _record_stage_ms(stage_timings, "formatting_ms", formatting_started)
        candidate.candidate_status = decision.format_status.value
        candidate.needs_review = bool(
            candidate.ambiguity_flags
            or candidate.confidence < confidence_threshold
            or decision.format_status is PlateFormatStatus.SPECIAL_OR_UNKNOWN
        )
        candidate.readable = True
        metrics["candidates_after_filter"] = int(metrics["candidates_after_filter"]) + 1
        accepted.append(candidate)
        return candidate

    def is_early_exit(candidate: PlateCandidate) -> bool:
        if candidate.candidate_status == PlateFormatStatus.REJECTED_NOISE.value:
            return False
        if candidate.confidence < confidence_threshold:
            return False
        return candidate.format_status in {PlateFormatStatus.FORMATTED, PlateFormatStatus.DISABLED}

    for index, detector_candidate in enumerate(detector_candidates[:crop_limit], start=1):
        x, y, box_width, box_height = detector_candidate.bbox
        crop_started = time.perf_counter()
        crop = image_bgr[y : y + box_height, x : x + box_width]
        if crop.size == 0:
            _record_stage_ms(stage_timings, "crop_ms", crop_started)
            continue
        crop_path = crop_dir / f"{_safe_stem(image_path.stem)}_{_path_hash(image_path)}_{index:02d}_detector.jpg"
        save_crop(crop, crop_path)
        _record_stage_ms(stage_timings, "crop_ms", crop_started)
        crop_accepted: list[PlateCandidate] = []
        if can_read_regions:
            metrics["crop_ocr_calls"] = int(metrics["crop_ocr_calls"]) + 1
            paddle_started = time.perf_counter()
            region_attempts = region_reader(crop) or []
            _record_stage_ms(stage_timings, "paddle_total_ms", paddle_started)
            for _local_bbox, attempt in region_attempts:
                candidate = record_attempt(
                    detector_candidate,
                    attempt,
                    source=f"detector_crop:{detector_candidate.source}",
                    crop_path=crop_path,
                )
                if candidate.readable:
                    crop_accepted.append(candidate)

        single_reader = getattr(ocr_engine, "read_plate", None)
        if not crop_accepted and (callable(variant_reader) or callable(single_reader)):
            metrics["crop_ocr_calls"] = int(metrics["crop_ocr_calls"]) + 1
            if not can_read_regions:
                metrics["tesseract_calls"] = int(metrics["tesseract_calls"]) + 1
            fallback_started = time.perf_counter()
            attempt = variant_reader(crop) if callable(variant_reader) else single_reader(crop)
            _record_stage_ms(stage_timings, "paddle_total_ms" if can_read_regions else "tesseract_ms", fallback_started)
            candidate = record_attempt(
                detector_candidate,
                attempt,
                source=f"detector_crop:{detector_candidate.source}",
                crop_path=crop_path,
            )
            if candidate.readable:
                crop_accepted.append(candidate)

        # YuNet's compact detector can make a slightly tight crop on a
        # strongly lit or partially occluded plate.  Retry one larger crop
        # only when Tiny has not produced any standard plate shape yet.
        if (
            scan_mode == "fast"
            and crop_accepted
            and not any(has_standard_vietnam_plate_shape(candidate.raw_text or candidate.text) for candidate in crop_accepted)
            and detector_candidate.source.startswith("opencv_yunet_plate")
            and can_read_regions
        ):
            expanded_crop = _expanded_detector_crop(image_bgr, detector_candidate.bbox)
            if expanded_crop.size and expanded_crop.shape != crop.shape:
                metrics["crop_ocr_calls"] = int(metrics["crop_ocr_calls"]) + 1
                expanded_started = time.perf_counter()
                expanded_attempts = region_reader(expanded_crop) or []
                _record_stage_ms(stage_timings, "paddle_total_ms", expanded_started)
                for _local_bbox, attempt in expanded_attempts:
                    candidate = record_attempt(
                        detector_candidate,
                        attempt,
                        source=f"detector_crop_expanded:{detector_candidate.source}",
                        crop_path=crop_path,
                    )
                    if candidate.readable:
                        crop_accepted.append(candidate)

        # Tiny is normally much faster than Small.  Verify one crop only if
        # Tiny cannot produce a standard Vietnamese plate shape, or when the
        # bundled YuNet detector marks the plate as strongly rotated.  The
        # latter condition prevents a high-confidence Tiny misread from
        # suppressing the more robust Small verifier.
        if (
            scan_mode == "fast"
            and crop_accepted
            and callable(fast_verification_reader)
            and (
                not any(has_standard_vietnam_plate_shape(candidate.raw_text or candidate.text) for candidate in crop_accepted)
                or detector_candidate.source.endswith("_high_rotation")
            )
        ):
            metrics["small_verification_ocr_calls"] = int(metrics["small_verification_ocr_calls"]) + 1
            verification_started = time.perf_counter()
            verification_attempts = fast_verification_reader(crop) or []
            _record_stage_ms(stage_timings, "paddle_total_ms", verification_started)
            for _local_bbox, attempt in verification_attempts:
                candidate = record_attempt(
                    detector_candidate,
                    attempt,
                    source=f"detector_crop_verified_small:{detector_candidate.source}",
                    crop_path=crop_path,
                )
                if candidate.readable:
                    candidate.selection_score += 0.01
                    candidate.score = candidate.selection_score
                    crop_accepted.append(candidate)

        if expected_count is ExpectedPlateCount.ONE and crop_accepted:
            best_crop = max(crop_accepted, key=lambda item: item.selection_score)
            if scan_mode == "fast" or (scan_mode == "balanced" and is_early_exit(best_crop)):
                break

    # Full-scene OCR is a last resort for Paddle only. A plate-like crop below
    # the confidence threshold is not considered a successful crop: every mode
    # may make one bounded fallback attempt when no detector crop is accepted.
    # Tesseract must never inspect a complete phone photo because overlays
    # dominate its output.
    has_sufficient_crop_candidate = any(is_early_exit(candidate) for candidate in accepted)
    if not has_sufficient_crop_candidate and can_read_regions:
        metrics["full_scene_ocr_calls"] = int(metrics["full_scene_ocr_calls"]) + 1
        full_scene = PlateCandidate(bbox=(0, 0, width, height), score=0.0, source="full_scene_fallback")
        paddle_started = time.perf_counter()
        full_scene_attempts = region_reader(image_bgr) or []
        _record_stage_ms(stage_timings, "paddle_total_ms", paddle_started)
        for local_bbox, attempt in full_scene_attempts:
            lx, ly, lw, lh = local_bbox
            record_attempt(
                full_scene,
                attempt,
                source="full_scene_fallback",
                bbox=(max(0, lx), max(0, ly), max(1, lw), max(1, lh)),
            )

    if not accepted and can_read_regions:
        for center_y_fraction, center_height_fraction in ((0.30, 0.28), (0.35, 0.30)):
            if accepted:
                break
            center_width = max(1, round(width * 0.54))
            center_height = max(1, round(height * center_height_fraction))
            center_x = max(0, min(width - center_width, round(width * 0.23)))
            center_y = max(0, min(height - center_height, round(height * center_y_fraction)))
            center_crop = image_bgr[center_y : center_y + center_height, center_x : center_x + center_width]
            if center_crop.size:
                metrics["crop_ocr_calls"] = int(metrics["crop_ocr_calls"]) + 1
                center_candidate = PlateCandidate(
                    bbox=(center_x, center_y, center_width, center_height),
                    score=0.0,
                    source="center_rescue_fallback",
                )
                center_started = time.perf_counter()
                center_attempts = region_reader(
                    center_crop,
                    detector_limit_side_len=960,
                    detector_limit_type="max",
                ) or []
                _record_stage_ms(stage_timings, "paddle_total_ms", center_started)
                for local_bbox, attempt in center_attempts:
                    lx, ly, lw, lh = local_bbox
                    record_attempt(
                        center_candidate,
                        attempt,
                        source="center_rescue_fallback",
                        bbox=(center_x + max(0, lx), center_y + max(0, ly), max(1, lw), max(1, lh)),
                    )

    scoring_started = time.perf_counter()
    primary, discarded, selected_reason = choose_primary_candidates(
        accepted,
        allow_multiple=expected_count is ExpectedPlateCount.MULTIPLE,
    )
    _record_stage_ms(stage_timings, "scoring_ms", scoring_started)
    for candidate in discarded:
        candidate.candidate_status = "NOT_SELECTED"
        candidate.rejected_reason = "Candidate yếu hơn hoặc không thuộc một vùng biển vật lý riêng."
        candidate.reason = candidate.rejected_reason
        rejected.append(candidate)

    metrics["selected_candidate_reason"] = selected_reason
    if primary:
        for candidate in primary:
            candidate.selection_reason = selected_reason if candidate is primary[0] else candidate.selection_reason
        return finish(ImageResult(
            image_path=image_path,
            status="OK",
            reason="Đã nhận diện biển số từ vùng detector.",
            blur_score=sharpness,
            width=width,
            height=height,
            candidate_count=len(detector_candidates),
            plates=primary,
            warnings=warnings,
            selected_plate_type=selected_type,
            expected_plate_count=expected_count,
            rejected_candidates=rejected,
            pipeline_metrics=metrics,
            selected_candidate_reason=selected_reason,
        ))

    status = "BLURRY" if sharpness < blur_threshold else "UNREADABLE"
    reason = "Ảnh mờ và không đọc được biển số." if status == "BLURRY" else "Không có candidate biển số hợp lệ sau detector-first OCR."
    return finish(ImageResult(
        image_path=image_path,
        status=status,
        reason=reason,
        blur_score=sharpness,
        width=width,
        height=height,
        candidate_count=len(detector_candidates),
        warnings=warnings,
        selected_plate_type=selected_type,
        expected_plate_count=expected_count,
        rejected_candidates=rejected,
        pipeline_metrics=metrics,
        selected_candidate_reason=selected_reason,
    ))


def _detector_first_regions(
    image_bgr: np.ndarray,
    scan_mode: str,
    metrics: dict[str, int | float | str],
    *,
    stage_timings: dict[str, float] | None = None,
) -> list[PlateCandidate]:
    """Return only physical plate regions, sorted and de-duplicated."""

    metrics["detector_calls"] = int(metrics["detector_calls"]) + 1
    detector_started = time.perf_counter()
    onnx = detect_plate_candidates_onnx(
        image_bgr,
        max_candidates=_onnx_detector_limit(scan_mode),
        confidence_threshold=_onnx_detector_confidence(scan_mode),
    )
    _record_stage_ms(stage_timings, "detector_ms", detector_started)
    if onnx:
        for candidate in onnx:
            candidate.detector_confidence = candidate.score
        postprocess_started = time.perf_counter()
        selected = _non_max_suppression(onnx, _onnx_detector_limit(scan_mode))
        _record_stage_ms(stage_timings, "detector_postprocess_ms", postprocess_started)
        return selected

    # The classical detector is offline and bounded.  It is used only when the
    # ONNX plate detector is unavailable or returns no physical plate region.
    metrics["detector_calls"] = int(metrics["detector_calls"]) + 3
    detector_started = time.perf_counter()
    classical = [
        *detect_plate_candidates(image_bgr, max_candidates=4),
        *detect_plate_candidates_second_pass(image_bgr, max_candidates=4),
        *detect_plate_outline_candidates(image_bgr, max_candidates=3),
    ]
    _record_stage_ms(stage_timings, "detector_ms", detector_started)
    limit = 2 if scan_mode == "fast" else (3 if scan_mode == "balanced" else 6)
    postprocess_started = time.perf_counter()
    regions = _non_max_suppression(sorted(classical, key=lambda item: item.score, reverse=True), limit)
    _record_stage_ms(stage_timings, "detector_postprocess_ms", postprocess_started)
    for candidate in regions:
        candidate.detector_confidence = candidate.score
        candidate.source = f"classical_plate_detector:{candidate.source}"
    return regions


def _non_max_suppression(candidates: list[PlateCandidate], limit: int) -> list[PlateCandidate]:
    selected: list[PlateCandidate] = []
    for candidate in candidates:
        if all(_iou(candidate.bbox, existing.bbox) < 0.35 for existing in selected):
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


def _overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    smaller_area = max(1, min(aw * ah, bw * bh))
    return inter_area / smaller_area
