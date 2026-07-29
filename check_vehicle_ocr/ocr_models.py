"""Pinned OCR model profiles used by the packaged local runtime.

The profile definitions are deliberately independent from the UI and from
PaddleOCR.  This keeps a model selection deterministic, lets the model
registry retain an older profile for rollback, and prevents a package update
from silently selecting a different upstream default.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrModelProfile:
    """A compatible detection/recognition model pair."""

    profile_id: str
    display_name: str
    family: str
    detection_model: str
    recognition_model: str
    tier: str


PP_OCRV5_MOBILE = OcrModelProfile(
    profile_id="pp-ocrv5-mobile",
    display_name="PP-OCRv5 Mobile (bản dự phòng)",
    family="PP-OCRv5",
    detection_model="PP-OCRv5_mobile_det",
    recognition_model="en_PP-OCRv5_mobile_rec",
    tier="legacy",
)
PP_OCRV6_TINY = OcrModelProfile(
    profile_id="pp-ocrv6-tiny",
    display_name="PP-OCRv6 Tiny (tiết kiệm tài nguyên)",
    family="PP-OCRv6",
    detection_model="PP-OCRv6_tiny_det",
    recognition_model="PP-OCRv6_tiny_rec",
    tier="tiny",
)
PP_OCRV6_SMALL = OcrModelProfile(
    profile_id="pp-ocrv6-small",
    display_name="PP-OCRv6 Small",
    family="PP-OCRv6",
    detection_model="PP-OCRv6_small_det",
    recognition_model="PP-OCRv6_small_rec",
    tier="small",
)
PP_OCRV6_MEDIUM = OcrModelProfile(
    profile_id="pp-ocrv6-medium",
    display_name="PP-OCRv6 Medium (tùy chọn nâng cao)",
    family="PP-OCRv6",
    detection_model="PP-OCRv6_medium_det",
    recognition_model="PP-OCRv6_medium_rec",
    tier="medium",
)

MODEL_PROFILES: tuple[OcrModelProfile, ...] = (
    PP_OCRV6_SMALL,
    PP_OCRV6_TINY,
    PP_OCRV6_MEDIUM,
    PP_OCRV5_MOBILE,
)
DEFAULT_MODEL_PROFILE = PP_OCRV6_SMALL


def profile_for_models(detection_model: str, recognition_model: str) -> OcrModelProfile | None:
    """Return a known profile only for an exact model pair."""

    for profile in MODEL_PROFILES:
        if profile.detection_model == detection_model and profile.recognition_model == recognition_model:
            return profile
    return None


def profile_by_id(profile_id: str | None) -> OcrModelProfile | None:
    candidate = str(profile_id or "").strip().lower()
    return next((profile for profile in MODEL_PROFILES if profile.profile_id == candidate), None)
