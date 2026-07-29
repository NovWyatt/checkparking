from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .plate_formatting import (
    DetectedPlateFormat,
    PlateFormatResult,
    PlateFormatStatus,
    PlateType,
    coerce_plate_type,
    format_plate,
    reformat_manual_correction,
)


@dataclass
class OcrAttempt:
    text: str = ""
    cleaned_text: str = ""
    normalized_text: str = ""
    suggested_texts: list[str] = field(default_factory=list)
    ambiguity_flags: list[str] = field(default_factory=list)
    needs_review: bool = False
    confidence: float = 0.0
    raw_text: str = ""
    engine: str = ""
    preprocess: str = ""


@dataclass
class PlateCandidate:
    bbox: tuple[int, int, int, int]
    score: float
    source: str = "detected"
    crop_path: Path | None = None
    text: str = ""
    cleaned_text: str = ""
    normalized_text: str = ""
    suggested_texts: list[str] = field(default_factory=list)
    ambiguity_flags: list[str] = field(default_factory=list)
    needs_review: bool = False
    confidence: float = 0.0
    raw_text: str = ""
    readable: bool = False
    reason: str = ""
    review_approved: bool = False
    corrected_text: str = ""
    formatted_text: str = ""
    export_text: str = ""
    selected_plate_type: PlateType = PlateType.NONE
    detected_format: DetectedPlateFormat = DetectedPlateFormat.NONE
    format_status: PlateFormatStatus = PlateFormatStatus.DISABLED
    format_reason: str = ""
    manual_correction: str = ""
    ocr_needs_review: bool | None = None

    @property
    def final_text(self) -> str:
        if self.export_text:
            return self.export_text
        if self.manual_correction:
            return self.manual_correction
        if self.corrected_text:
            return self.corrected_text
        return self.text or ""

    def apply_plate_formatting(self, selected_plate_type: PlateType | str | None) -> PlateFormatResult:
        """Apply a batch's formatter without mutating raw OCR text.

        ``corrected_text`` remains a compatibility mirror for older sessions;
        new code uses ``manual_correction`` and ``export_text`` explicitly.
        """

        plate_type = coerce_plate_type(selected_plate_type)
        if self.ocr_needs_review is None:
            self.ocr_needs_review = bool(self.needs_review)
        if not self.manual_correction and self.corrected_text and self.corrected_text != self.text:
            self.manual_correction = self.corrected_text
        if self.manual_correction:
            decision = reformat_manual_correction(self.manual_correction, plate_type)
        else:
            # OCR engines historically placed a display-oriented string in
            # ``text``. Prefer the original OCR text for a strict formatter so
            # a legacy broad display formatter cannot turn a special plate into
            # a standard one before this operator-selected step.
            source_text = self.raw_text or self.text
            decision = format_plate(source_text, plate_type)
        self.cleaned_text = decision.cleaned_text
        self.formatted_text = decision.formatted_text
        self.export_text = decision.export_text
        self.selected_plate_type = decision.selected_plate_type
        self.detected_format = decision.detected_format
        self.format_status = decision.format_status
        self.format_reason = decision.format_reason
        self.needs_review = False if self.review_approved else bool(self.ocr_needs_review or decision.needs_review)
        return decision

    def set_manual_correction(self, value: str, selected_plate_type: PlateType | str | None) -> PlateFormatResult:
        """Store an operator edit exactly, then run only the pure formatter."""

        self.manual_correction = value
        self.corrected_text = value
        return self.apply_plate_formatting(selected_plate_type)


@dataclass
class ImageResult:
    image_path: Path
    status: str
    reason: str
    blur_score: float = 0.0
    width: int = 0
    height: int = 0
    candidate_count: int = 0
    plates: list[PlateCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    batch_id: str = ""
    selected_plate_type: PlateType = PlateType.NONE
    batch_started_at: str = ""
    batch_total_images: int = 0

    @property
    def plate_texts(self) -> list[str]:
        return [plate.final_text for plate in self.plates if (plate.readable or plate.review_approved) and plate.final_text]


@dataclass(frozen=True)
class BatchSession:
    """Formatting-relevant metadata captured when a batch starts."""

    batch_id: str
    selected_plate_type: PlateType
    started_at: str
    total_images: int
