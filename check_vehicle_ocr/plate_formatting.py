"""Deterministic, batch-selected Vietnamese plate formatting.

This module deliberately knows nothing about Tkinter, OCR engines or Excel.
It only accepts a user-selected plate type and formats the three narrowly
defined standard patterns supported by the operator workflow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class PlateType(StrEnum):
    """Operator-selected type for one batch of images."""

    MOTORCYCLE = "MOTORCYCLE"
    CAR = "CAR"
    NONE = "NONE"


class PlateFormatStatus(StrEnum):
    FORMATTED = "FORMATTED"
    SPECIAL_OR_UNKNOWN = "SPECIAL_OR_UNKNOWN"
    # Backward-compatible symbolic name for persisted v1.8/v1.9 sessions.
    UNMATCHED = SPECIAL_OR_UNKNOWN
    REJECTED_NOISE = "REJECTED_NOISE"
    MANUAL = "MANUAL"
    DISABLED = "DISABLED"


class DetectedPlateFormat(StrEnum):
    MOTORCYCLE_LETTER_DIGIT = "MOTORCYCLE_LETTER_DIGIT"
    MOTORCYCLE_TWO_LETTERS = "MOTORCYCLE_TWO_LETTERS"
    CAR_STANDARD = "CAR_STANDARD"
    SPECIAL_OR_UNKNOWN = "SPECIAL_OR_UNKNOWN"
    NONE = "NONE"


@dataclass(frozen=True)
class PlateFormatResult:
    """The complete formatting decision, without modifying OCR data."""

    raw_text: str
    cleaned_text: str
    formatted_text: str
    export_text: str
    selected_plate_type: PlateType
    detected_format: DetectedPlateFormat
    format_status: PlateFormatStatus
    format_reason: str
    needs_review: bool
    manual_correction: str = ""


_MOTORCYCLE_LETTER_DIGIT = re.compile(r"^(\d{2})([A-Z])(\d)(\d{4,5})$")
_MOTORCYCLE_TWO_LETTERS = re.compile(r"^(\d{2})([A-Z]{2})(\d{4,5})$")
_CAR_STANDARD = re.compile(r"^(\d{2})([A-Z])(\d{4,5})$")


def coerce_plate_type(value: PlateType | str | None) -> PlateType:
    """Return a safe plate type for persisted legacy and UI values."""

    if isinstance(value, PlateType):
        return value
    try:
        return PlateType(str(value or "").strip().upper())
    except ValueError:
        return PlateType.NONE


def clean_plate_for_formatting(text: object) -> str:
    """Return the strict comparison form without guessing ambiguous glyphs.

    Only ASCII Latin letters and digits participate in an automatic format.
    In particular, this function never changes ``O`` to ``0`` or similar OCR
    ambiguities; suggestions remain a review-only OCR concern.
    """

    upper = str(text or "").upper()
    return "".join(character for character in upper if "A" <= character <= "Z" or "0" <= character <= "9")


def format_motorcycle_plate(text: object) -> PlateFormatResult:
    """Format only the two approved motorcycle patterns."""

    return _format_with_type(str(text or ""), PlateType.MOTORCYCLE)


def format_car_plate(text: object) -> PlateFormatResult:
    """Format only the approved car pattern."""

    return _format_with_type(str(text or ""), PlateType.CAR)


def format_plate(text: object, selected_plate_type: PlateType | str | None) -> PlateFormatResult:
    """Format *text* only when the explicitly selected batch type matches."""

    raw_text = str(text or "")
    plate_type = coerce_plate_type(selected_plate_type)
    if plate_type is PlateType.NONE:
        return PlateFormatResult(
            raw_text=raw_text,
            cleaned_text=clean_plate_for_formatting(raw_text),
            formatted_text="",
            export_text=raw_text,
            selected_plate_type=plate_type,
            detected_format=DetectedPlateFormat.NONE,
            format_status=PlateFormatStatus.DISABLED,
            format_reason="Không tự định dạng theo lựa chọn của batch.",
            needs_review=False,
        )
    return _format_with_type(raw_text, plate_type)


def reformat_manual_correction(manual_correction: object, selected_plate_type: PlateType | str | None) -> PlateFormatResult:
    """Apply the same exact rules to an operator's manual correction.

    A matching correction is marked ``MANUAL`` and exported in its canonical
    form. A nonmatching correction is retained character-for-character and
    remains in the special/review group rather than being forced into a rule.
    """

    correction = str(manual_correction or "")
    result = format_plate(correction, selected_plate_type)
    if not correction:
        return result
    if result.format_status is PlateFormatStatus.FORMATTED:
        return PlateFormatResult(
            raw_text=result.raw_text,
            cleaned_text=result.cleaned_text,
            formatted_text=result.formatted_text,
            export_text=result.formatted_text,
            selected_plate_type=result.selected_plate_type,
            detected_format=result.detected_format,
            format_status=PlateFormatStatus.MANUAL,
            format_reason="Đã sửa tay và định dạng theo mẫu đã chọn.",
            needs_review=False,
            manual_correction=correction,
        )
    if result.format_status is PlateFormatStatus.DISABLED:
        return PlateFormatResult(
            raw_text=result.raw_text,
            cleaned_text=result.cleaned_text,
            formatted_text="",
            export_text=correction,
            selected_plate_type=result.selected_plate_type,
            detected_format=DetectedPlateFormat.NONE,
            format_status=PlateFormatStatus.MANUAL,
            format_reason="Đã sửa tay; batch không tự định dạng.",
            needs_review=False,
            manual_correction=correction,
        )
    return PlateFormatResult(
        raw_text=result.raw_text,
        cleaned_text=result.cleaned_text,
        formatted_text="",
        export_text=correction,
        selected_plate_type=result.selected_plate_type,
        detected_format=DetectedPlateFormat.SPECIAL_OR_UNKNOWN,
        format_status=PlateFormatStatus.SPECIAL_OR_UNKNOWN,
        format_reason=_unmatched_reason(result.selected_plate_type),
        needs_review=True,
        manual_correction=correction,
    )


def _format_with_type(raw_text: str, plate_type: PlateType) -> PlateFormatResult:
    cleaned_text = clean_plate_for_formatting(raw_text)
    if plate_type is PlateType.MOTORCYCLE:
        match = _MOTORCYCLE_LETTER_DIGIT.fullmatch(cleaned_text)
        if match:
            province, letter, digit, serial = match.groups()
            return _formatted_result(
                raw_text,
                cleaned_text,
                plate_type,
                DetectedPlateFormat.MOTORCYCLE_LETTER_DIGIT,
                f"{province}{letter}{digit}-{serial}",
                "Đã định dạng theo mẫu xe máy một chữ và một số.",
            )
        match = _MOTORCYCLE_TWO_LETTERS.fullmatch(cleaned_text)
        if match:
            province, letters, serial = match.groups()
            return _formatted_result(
                raw_text,
                cleaned_text,
                plate_type,
                DetectedPlateFormat.MOTORCYCLE_TWO_LETTERS,
                f"{province}{letters}-{serial}",
                "Đã định dạng theo mẫu xe máy hai chữ.",
            )
    elif plate_type is PlateType.CAR:
        match = _CAR_STANDARD.fullmatch(cleaned_text)
        if match:
            province, letter, serial = match.groups()
            return _formatted_result(
                raw_text,
                cleaned_text,
                plate_type,
                DetectedPlateFormat.CAR_STANDARD,
                f"{province}{letter}-{serial}",
                "Đã định dạng theo mẫu ô tô.",
            )

    return PlateFormatResult(
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        formatted_text="",
        export_text=raw_text,
        selected_plate_type=plate_type,
        detected_format=DetectedPlateFormat.SPECIAL_OR_UNKNOWN,
        format_status=PlateFormatStatus.UNMATCHED,
        format_reason=_unmatched_reason(plate_type),
        needs_review=True,
    )


def _formatted_result(
    raw_text: str,
    cleaned_text: str,
    plate_type: PlateType,
    detected_format: DetectedPlateFormat,
    formatted_text: str,
    reason: str,
) -> PlateFormatResult:
    return PlateFormatResult(
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        formatted_text=formatted_text,
        export_text=formatted_text,
        selected_plate_type=plate_type,
        detected_format=detected_format,
        format_status=PlateFormatStatus.FORMATTED,
        format_reason=reason,
        needs_review=False,
    )


def _unmatched_reason(plate_type: PlateType) -> str:
    if plate_type is PlateType.MOTORCYCLE:
        return "Biển số không khớp mẫu xe máy đã chọn."
    if plate_type is PlateType.CAR:
        return "Biển số không khớp mẫu ô tô đã chọn."
    return "Biển số không khớp mẫu định dạng đã chọn."
