"""Pure plate-likeness and ranking rules for detector-first OCR.

These rules deliberately reject arbitrary scene text before it can become a
plate, a review item, an Excel row, or an AI request.  They do not correct
ambiguous glyphs: OCR suggestions remain suggestions until an operator edits
the value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import PlateCandidate
from .plate_formatting import PlateFormatStatus, PlateType, clean_plate_for_formatting, format_plate


_TIMESTAMP = (
    re.compile(r"^20\d{6,12}$"),
    re.compile(r"^\d{8,14}$"),
)
_OVERLAY_WORDS = frozenset({"DIEMDANH", "TIMEMARK", "TIMESTAMP", "DATE", "TIME", "NGAY", "THANG", "THG"})


@dataclass(frozen=True)
class CandidateAssessment:
    accepted: bool
    cleaned_text: str
    score: float
    reason: str
    is_special: bool
    format_status: PlateFormatStatus


def is_plate_like_candidate(text: object) -> bool:
    """Return true only for a minimally plausible Vietnamese registration ID.

    A non-standard registration can still pass, but a timestamp, address,
    watermark, one-character OCR result, or a generic word cannot be promoted
    to the special-plate workflow merely because it missed a strict formatter.
    """

    cleaned = clean_plate_for_formatting(text)
    if not 7 <= len(cleaned) <= 12:
        return False
    if not cleaned.startswith(tuple(str(number) for number in range(10))):
        return False
    if any(pattern.fullmatch(cleaned) for pattern in _TIMESTAMP):
        return False
    if any(word in cleaned for word in _OVERLAY_WORDS):
        return False

    digits = sum(character.isdigit() for character in cleaned)
    letters = sum(character.isalpha() for character in cleaned)
    if digits < 5 or letters < 1:
        return False
    # Registration IDs start with a two-digit province code.  It is important
    # not to accept strings like C-F453-BE, even after separators are removed.
    return cleaned[:2].isdigit()


def assess_plate_candidate(
    candidate: PlateCandidate,
    *,
    plate_type: PlateType,
    image_size: tuple[int, int],
) -> CandidateAssessment:
    """Score a candidate without accepting scene text as a plate.

    The score is intentionally explainable and deterministic.  It combines
    detector evidence, OCR confidence, strict formatter evidence and crop
    geometry; full-scene OCR always receives a material penalty.
    """

    raw = candidate.raw_text or candidate.text or candidate.normalized_text
    cleaned = clean_plate_for_formatting(raw)
    if not is_plate_like_candidate(cleaned):
        return CandidateAssessment(
            accepted=False,
            cleaned_text=cleaned,
            score=0.0,
            reason="OCR không có cấu trúc giống biển số; đã loại nhiễu.",
            is_special=False,
            format_status=PlateFormatStatus.REJECTED_NOISE,
        )

    decision = format_plate(raw, plate_type)
    width, height = image_size
    x, y, box_width, box_height = candidate.bbox
    aspect = box_width / max(1.0, float(box_height))
    area_ratio = (box_width * box_height) / max(1.0, float(width * height))
    detector = max(0.0, min(100.0, candidate.detector_confidence or candidate.score))
    ocr = max(0.0, min(100.0, candidate.confidence))

    score = (ocr * 0.56) + (detector * 0.24)
    if 0.7 <= aspect <= 7.2:
        score += 8.0
    else:
        score -= 14.0
    if 0.00005 <= area_ratio <= 0.20:
        score += 4.0
    else:
        score -= 8.0
    if decision.format_status is PlateFormatStatus.FORMATTED:
        score += 18.0
    elif decision.format_status is PlateFormatStatus.SPECIAL_OR_UNKNOWN:
        score -= 5.0
    if candidate.ambiguity_flags:
        score -= min(10.0, float(len(candidate.ambiguity_flags)) * 3.0)
    if "full_scene" in candidate.source:
        score -= 22.0
    if "fallback" in candidate.source:
        score -= 8.0
    if y + box_height / 2 > height * 0.86 and area_ratio < 0.025:
        score -= 18.0

    is_special = decision.format_status is PlateFormatStatus.SPECIAL_OR_UNKNOWN
    reason = "Khớp mẫu biển số đã chọn." if not is_special else "Có cấu trúc giống biển số nhưng không khớp mẫu đã chọn."
    return CandidateAssessment(
        accepted=True,
        cleaned_text=cleaned,
        score=round(max(0.0, score), 2),
        reason=reason,
        is_special=is_special,
        format_status=decision.format_status,
    )


def choose_primary_candidates(
    candidates: list[PlateCandidate],
    *,
    allow_multiple: bool,
    score_margin: float = 9.0,
) -> tuple[list[PlateCandidate], list[PlateCandidate], str]:
    """Keep one clear primary candidate by default.

    Multiple output plates require distinct physical detector boxes.  Weak or
    overlapping candidates stay debug-only so they cannot inflate totals.
    """

    if not candidates:
        return [], [], "Không có candidate đạt điều kiện plate-like."
    ordered = sorted(candidates, key=lambda item: item.selection_score, reverse=True)
    primary = [ordered[0]]
    rejected = list(ordered[1:])
    if allow_multiple:
        for candidate in ordered[1:]:
            if any(_iou(candidate.bbox, kept.bbox) >= 0.30 for kept in primary):
                continue
            if candidate.selection_score < primary[0].selection_score - score_margin:
                continue
            primary.append(candidate)
            rejected.remove(candidate)
    reason = primary[0].selection_reason or "Điểm detector/OCR/format cao nhất."
    return primary, rejected, reason


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left, top = max(ax, bx), max(ay, by)
    right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    intersection = max(0, right - left) * max(0, bottom - top)
    union = (aw * ah) + (bw * bh) - intersection
    return intersection / union if union else 0.0
