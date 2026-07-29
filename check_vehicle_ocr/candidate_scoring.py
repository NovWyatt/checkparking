"""Conservative PaddleOCR/Tesseract candidate comparison.

The helper never invents characters and treats conflicting engines as a review
signal unless one candidate has a materially stronger strict-format score.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import PlateCandidate
from .plate_formatting import PlateFormatStatus, PlateType, clean_plate_for_formatting, format_plate


@dataclass(frozen=True)
class EngineSelection:
    engine: str
    reason: str
    confidence: float
    needs_review: bool


def choose_engine_candidate(
    paddle_text: str,
    paddle_confidence: float,
    tesseract_text: str,
    tesseract_confidence: float,
    plate_type: PlateType = PlateType.NONE,
) -> EngineSelection:
    """Choose only when the evidence is clear; otherwise require review."""

    paddle_cleaned = clean_plate_for_formatting(paddle_text)
    tesseract_cleaned = clean_plate_for_formatting(tesseract_text)
    if paddle_cleaned and paddle_cleaned == tesseract_cleaned:
        return EngineSelection("paddle+tesseract", "Hai công cụ cho cùng kết quả.", min(100.0, max(paddle_confidence, tesseract_confidence) + 6.0), False)
    paddle_score = _candidate_score(paddle_text, paddle_confidence, plate_type)
    tesseract_score = _candidate_score(tesseract_text, tesseract_confidence, plate_type)
    if tesseract_cleaned and tesseract_score >= paddle_score + 12.0:
        return EngineSelection("tesseract", "Tesseract có điểm tin cậy và mẫu biển số tốt hơn rõ rệt.", tesseract_confidence, False)
    if paddle_cleaned and paddle_score >= tesseract_score + 12.0:
        return EngineSelection("paddleocr", "PaddleOCR có điểm tin cậy và mẫu biển số tốt hơn rõ rệt.", paddle_confidence, False)
    if paddle_cleaned:
        return EngineSelection("paddleocr", "Hai công cụ khác nhau; giữ PaddleOCR và yêu cầu kiểm tra.", paddle_confidence, True)
    if tesseract_cleaned:
        return EngineSelection("tesseract", "PaddleOCR không có kết quả rõ; dùng Tesseract và yêu cầu kiểm tra.", tesseract_confidence, True)
    return EngineSelection("none", "Cả hai công cụ không tạo được biển số hợp lệ.", 0.0, True)


def apply_fallback_selection(
    paddle_result,
    tesseract_result,
    plate_type: PlateType = PlateType.NONE,
):
    """Merge an optional Tesseract result without discarding engine evidence."""

    paddle_plates = list(paddle_result.plates)
    tesseract_plates = list(tesseract_result.plates)
    for index, paddle_plate in enumerate(paddle_plates):
        tess_plate = tesseract_plates[index] if index < len(tesseract_plates) else None
        _record_paddle(paddle_plate)
        if tess_plate is None:
            paddle_plate.selected_engine = "paddleocr"
            paddle_plate.selection_reason = "Không có candidate Tesseract tương ứng."
            continue
        _record_tesseract(paddle_plate, tess_plate)
        selection = choose_engine_candidate(
            paddle_plate.paddle_candidate,
            paddle_plate.paddle_confidence,
            paddle_plate.tesseract_candidate,
            paddle_plate.tesseract_confidence,
            plate_type,
        )
        paddle_plate.selected_engine = selection.engine
        paddle_plate.selection_reason = selection.reason
        paddle_plate.confidence = selection.confidence
        paddle_plate.needs_review = bool(paddle_plate.needs_review or selection.needs_review)
        if selection.engine == "tesseract":
            _copy_candidate_text(paddle_plate, tess_plate)
        elif selection.engine == "paddle+tesseract":
            paddle_plate.suggested_texts = list(dict.fromkeys([*paddle_plate.suggested_texts, tess_plate.text, tess_plate.normalized_text]))

    for tess_plate in tesseract_plates[len(paddle_plates) :]:
        _record_tesseract(tess_plate, tess_plate)
        tess_plate.source = "tesseract_fallback"
        tess_plate.selected_engine = "tesseract"
        tess_plate.selection_reason = "PaddleOCR không có candidate tương ứng."
        tess_plate.needs_review = True
        paddle_result.plates.append(tess_plate)

    paddle_result.warnings = list(dict.fromkeys([*paddle_result.warnings, "Đã dùng Tesseract dự phòng cho kết quả cần kiểm tra."]))
    return paddle_result


def _candidate_score(text: str, confidence: float, plate_type: PlateType) -> float:
    cleaned = clean_plate_for_formatting(text)
    if not cleaned:
        return -100.0
    score = max(0.0, min(100.0, float(confidence)))
    if 7 <= len(cleaned) <= 10:
        score += 5.0
    decision = format_plate(text, plate_type)
    if plate_type is not PlateType.NONE:
        score += 16.0 if decision.format_status is PlateFormatStatus.FORMATTED else -12.0
    return score


def _record_paddle(plate: PlateCandidate) -> None:
    plate.paddle_raw = plate.paddle_raw or plate.raw_text
    plate.paddle_candidate = plate.paddle_candidate or plate.normalized_text or plate.text
    plate.paddle_confidence = plate.paddle_confidence or plate.confidence


def _record_tesseract(target: PlateCandidate, source: PlateCandidate) -> None:
    target.tesseract_raw = source.raw_text
    target.tesseract_candidate = source.normalized_text or source.text
    target.tesseract_confidence = source.confidence


def _copy_candidate_text(target: PlateCandidate, source: PlateCandidate) -> None:
    target.text = source.text
    target.cleaned_text = source.cleaned_text
    target.normalized_text = source.normalized_text
    target.raw_text = source.raw_text
    target.suggested_texts = list(dict.fromkeys([*target.suggested_texts, *source.suggested_texts]))
    target.ambiguity_flags = list(dict.fromkeys([*target.ambiguity_flags, *source.ambiguity_flags]))
    target.readable = source.readable
