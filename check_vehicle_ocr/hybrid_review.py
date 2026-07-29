"""Deterministic policy helpers for PaddleOCR plus optional AI review.

The helpers deliberately contain no provider, Tkinter, or OCR-engine code.
This keeps the decision to share an image with an online provider auditable
and fully testable without a network connection.
"""

from __future__ import annotations

from enum import StrEnum

from .models import ImageResult
from .plate_formatting import PlateFormatStatus


class AiReviewPolicy(StrEnum):
    """The three operator-visible levels of online review."""

    UNREADABLE_ONLY = "unreadable_only"
    NEEDS_REVIEW = "needs_review"
    ALL_IMAGES = "all_images"


def coerce_ai_review_policy(value: object) -> AiReviewPolicy:
    try:
        return AiReviewPolicy(str(value or "").strip())
    except ValueError:
        return AiReviewPolicy.NEEDS_REVIEW


def result_has_readable_plate(result: ImageResult) -> bool:
    return any(plate.readable and plate.final_text for plate in result.plates)


def should_send_to_ai(
    result: ImageResult,
    policy: AiReviewPolicy | str | None,
    *,
    confidence_threshold: float,
) -> tuple[bool, str]:
    """Return a conservative online-review decision and human-readable reason.

    A clear, high-confidence plate is never uploaded under the default
    policy.  The broad "all images" option remains explicit and is the only
    mode which intentionally uploads clear results.
    """

    selected = coerce_ai_review_policy(policy)
    if selected is AiReviewPolicy.ALL_IMAGES:
        return True, "Người dùng chọn AI kiểm tra tất cả ảnh."

    readable = result_has_readable_plate(result)
    if not readable:
        return True, "PaddleOCR chưa đọc được biển số rõ ràng."
    if selected is AiReviewPolicy.UNREADABLE_ONLY:
        return False, "PaddleOCR đã đọc được biển số."

    for plate in result.plates:
        if not plate.readable:
            continue
        if plate.needs_review:
            return True, "Kết quả OCR cần kiểm tra thêm."
        if plate.format_status is PlateFormatStatus.UNMATCHED:
            return True, "Biển số không khớp mẫu đã chọn."
        if plate.confidence < confidence_threshold:
            return True, "Độ tin cậy OCR thấp hơn ngưỡng đã chọn."
        suggestions = {value.strip().upper() for value in plate.suggested_texts if value.strip()}
        if len(suggestions) > 1 or plate.ambiguity_flags:
            return True, "Có nhiều kết quả OCR mâu thuẫn."
    if result.status != "OK":
        return True, "PaddleOCR chưa hoàn tất nhận diện."
    return False, "PaddleOCR đọc rõ với độ tin cậy cao."
