from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


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

    @property
    def final_text(self) -> str:
        return (self.corrected_text or self.text or "").strip()


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

    @property
    def plate_texts(self) -> list[str]:
        return [plate.final_text for plate in self.plates if (plate.readable or plate.review_approved) and plate.final_text]
