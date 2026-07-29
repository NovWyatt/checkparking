from __future__ import annotations

import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .models import OcrAttempt

try:
    import pytesseract
    from pytesseract import Output
except Exception:
    pytesseract = None
    Output = None


PLATE_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-."
DIGIT_FIX = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6"})
LETTER_FIX = str.maketrans({"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"})
AMBIGUOUS_TO_DIGIT = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6"}
TIMESTAMP_PATTERNS = [
    re.compile(r"\b20\d{2}[-. ]\d{1,2}[-. ]\d{1,2}\b"),
    re.compile(r"\b\d{1,2}[-. ]\d{1,2}[-. ]20\d{2}\b"),
    re.compile(r"\b\d{1,2}[:.]\d{2}([:.]\d{2})?\b"),
    re.compile(r"\b\d{1,2}\s*(THANG|THG)\s*\d{1,2},?\s*20\d{2}\b"),
]


def runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def find_tesseract(custom_path: str | Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if custom_path:
        candidates.append(Path(custom_path))

    env_path = os.environ.get("CHECK_VEHICLE_TESSERACT")
    if env_path:
        candidates.append(Path(env_path))

    base = runtime_base_dir()
    pyinstaller_internal = Path(getattr(sys, "_MEIPASS", base))
    candidates.extend(
        [
            pyinstaller_internal / "tesseract" / "tesseract.exe",
            base / "_internal" / "tesseract" / "tesseract.exe",
            base / "tesseract" / "tesseract.exe",
            base / "vendor" / "tesseract" / "tesseract.exe",
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ]
    )

    which_path = shutil.which("tesseract")
    if which_path:
        candidates.append(Path(which_path))

    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate.resolve()
    return None


def clean_text(text: str) -> str:
    text = strip_diacritics(text).upper().replace("\n", " ")
    return re.sub(r"[^A-Z0-9]", "", text)


def clean_display_text(text: str) -> str:
    text = strip_diacritics(text).upper().replace("\n", " ")
    text = re.sub(r"[^A-Z0-9.\-\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .-")


def strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    stripped = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return stripped.replace("\u0110", "D").replace("\u0111", "d")


def normalize_plate_text(text: str) -> str:
    return clean_text(text)


def plate_text_metadata(text: str, max_suggestions: int = 5) -> tuple[str, list[str], list[str], bool]:
    """Return cleaned OCR text and bounded, review-only ambiguity suggestions."""
    cleaned = clean_text(text)
    if not cleaned:
        return "", [], [], False

    suggestions: list[str] = []
    flags: list[str] = []
    for index, char in enumerate(cleaned):
        replacement = AMBIGUOUS_TO_DIGIT.get(char)
        if replacement is None:
            continue
        flags.append(f"{char}_OR_{replacement}@{index + 1}")
        suggestion = f"{cleaned[:index]}{replacement}{cleaned[index + 1:]}"
        if suggestion != cleaned and suggestion not in suggestions:
            suggestions.append(suggestion)
        if len(suggestions) >= max(0, max_suggestions):
            break
    return cleaned, suggestions[: max(0, max_suggestions)], flags[: max(0, max_suggestions)], bool(flags)


def is_timestamp_like(text: str) -> bool:
    raw_display = strip_diacritics(text).upper().replace("\n", " ")
    display = clean_display_text(text)
    normalized = clean_text(display)
    if not raw_display.strip() or not normalized:
        return False
    if re.fullmatch(r"\s*\d{1,2}[:.]\d{2}([:.]\d{2})?\s*", raw_display):
        return True
    if any(pattern.search(raw_display) or pattern.search(display) for pattern in TIMESTAMP_PATTERNS):
        return True
    if re.fullmatch(r"\d{4}", normalized):
        hour = int(normalized[:2])
        minute = int(normalized[2:])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return True
    if re.search(r"\d{1,2}(THANG|THG)\d{1,2}20\d{2}", normalized):
        return True
    if any(word in normalized for word in ("THANG", "THG", "NGAY", "DATE", "TIME", "TIMESTAMP")):
        digits = sum(char.isdigit() for char in normalized)
        if digits >= 3:
            return True

    digits = sum(char.isdigit() for char in normalized)
    letters = sum(char.isalpha() for char in normalized)
    if letters == 0 and digits >= 6:
        return True
    if re.match(r"^20\d{6,12}$", normalized):
        return True
    return False


def looks_like_plate(text: str) -> bool:
    if is_timestamp_like(text):
        return False

    normalized = normalize_plate_text(text)
    if any(word in normalized for word in ("THANG", "THG", "NGAY", "DATE", "TIME", "TIMESTAMP")):
        return False
    if not (6 <= len(normalized) <= 11):
        return False

    digits = sum(char.isdigit() for char in normalized)
    letters = sum(char.isalpha() for char in normalized)
    if digits < 4 or letters < 1:
        return False

    return bool(re.match(r"^\d{2}[A-Z0-9]{1,4}\d{4,6}$", normalized))


def has_plausible_display_format(text: str) -> bool:
    display = clean_display_text(text)
    patterns = [
        r"^\d{2}-[A-Z]\d\s+\d{3}\.\d{2,3}$",
        r"^\d{2}[A-Z]{1,3}-\d{3}\.\d{2,3}$",
        r"^\d{2}[A-Z]{1,3}\s+\d{3}\.\d{2,3}$",
        r"^\d{2}-[A-Z0-9]{1,4}\s+\d{4,6}$",
        r"^\d{2}[A-Z]{1,3}-\d{4,6}$",
    ]
    return any(re.match(pattern, display) for pattern in patterns)


def plate_quality_score(text: str, ocr_confidence: float) -> float:
    if is_timestamp_like(text):
        return 0.0

    normalized = normalize_plate_text(text)
    if not normalized or not looks_like_plate(normalized):
        return 0.0

    score = max(0.0, min(100.0, ocr_confidence)) * 0.65
    digits = sum(char.isdigit() for char in normalized)
    letters = sum(char.isalpha() for char in normalized)

    if 6 <= len(normalized) <= 10:
        score += 10
    if digits >= 4:
        score += 8
    if letters >= 1:
        score += 6
    if re.match(r"^\d{2}[A-Z]{1,3}\d{4,6}$", normalized):
        score += 18
    elif re.match(r"^\d{2}[A-Z0-9]{1,4}\d{4,6}$", normalized):
        score += 10

    return max(0.0, min(100.0, score))


def format_vietnam_plate(text: str) -> str:
    display = clean_display_text(text)
    if is_timestamp_like(display):
        return ""

    if re.search(r"[-.\s]", display) and looks_like_plate(display) and has_plausible_display_format(display):
        return display

    normalized = normalize_plate_text(display)
    motorcycle_match = re.match(r"^(\d{2})([A-Z]\d)(\d{5})$", normalized)
    if motorcycle_match:
        province, series, serial = motorcycle_match.groups()
        return f"{province}-{series} {serial[:3]}.{serial[3:]}"

    car_match = re.match(r"^(\d{2})([A-Z]{1,3})(\d{5,6})$", normalized)
    if car_match:
        province, series, serial = car_match.groups()
        return f"{province}{series}-{serial[:3]}.{serial[3:]}"

    general_match = re.match(r"^(\d{2})([A-Z0-9]{1,4})(\d{4,6})$", normalized)
    if not general_match:
        return normalized

    province, series, serial = general_match.groups()
    if len(serial) >= 5:
        serial = f"{serial[:3]}.{serial[3:]}"
    return f"{province}-{series} {serial}" if any(char.isdigit() for char in series) else f"{province}{series}-{serial}"


class TesseractOcrEngine:
    def __init__(self, custom_path: str | Path | None = None, confidence_threshold: float = 40.0):
        self.confidence_threshold = confidence_threshold
        self.tesseract_path = find_tesseract(custom_path)
        self.reason = ""

        if pytesseract is None:
            self.reason = "Python package pytesseract chưa được cài."
            return

        if self.tesseract_path is None:
            self.reason = "Không tìm thấy tesseract.exe."
            return

        for tessdata in (self.tesseract_path.parent / "tessdata", self.tesseract_path.parent.parent / "tessdata"):
            if (tessdata / "eng.traineddata").is_file():
                os.environ["TESSDATA_PREFIX"] = str(tessdata)
                break
        pytesseract.pytesseract.tesseract_cmd = str(self.tesseract_path)

    @property
    def available(self) -> bool:
        return pytesseract is not None and self.tesseract_path is not None

    def read_plate(self, crop_bgr: np.ndarray) -> OcrAttempt:
        if not self.available:
            return OcrAttempt(engine="tesseract", raw_text=self.reason)

        attempts: list[OcrAttempt] = []
        variants = dict(self._preprocess_variants(crop_bgr))
        fast_plan = (("sharp", 6), ("sharp", 7), ("otsu", 6), ("adaptive", 6))

        for name, psm in fast_plan:
            prepared = variants.get(name)
            if prepared is None:
                continue
            attempt = self._read_string_once(prepared, name, psm)
            attempts.append(attempt)
            if attempt.confidence >= self.confidence_threshold:
                return attempt

        best_fast = max(attempts, key=lambda attempt: attempt.confidence, default=OcrAttempt(engine="tesseract"))
        if best_fast.confidence >= max(20.0, self.confidence_threshold - 12.0):
            return best_fast

        for name, psm in (("clahe", 6), ("gray", 6), ("otsu_inv", 6), ("adaptive_inv", 6), ("sharp", 13)):
            prepared = variants.get(name)
            if prepared is None:
                continue
            attempts.append(self._read_once(prepared, name, psm))

        return max(
            attempts,
            key=lambda attempt: attempt.confidence,
            default=OcrAttempt(engine="tesseract"),
        )

    def _read_string_once(self, gray_or_bgr: np.ndarray, preprocess_name: str, psm: int) -> OcrAttempt:
        config = f"--oem 3 --psm {psm} -c tessedit_char_whitelist={PLATE_WHITELIST}"
        image = self._to_pil(gray_or_bgr)
        try:
            raw_text = pytesseract.image_to_string(image, config=config).strip()
        except Exception as exc:
            return OcrAttempt(engine="tesseract", preprocess=f"{preprocess_name}/psm{psm}", raw_text=str(exc))

        display_text = format_vietnam_plate(raw_text)
        normalized = normalize_plate_text(display_text)
        confidence = plate_quality_score(display_text or normalized, 88.0 if display_text else 0.0)
        return OcrAttempt(
            text=display_text,
            normalized_text=normalized,
            confidence=confidence,
            raw_text=raw_text,
            engine="tesseract",
            preprocess=f"{preprocess_name}/psm{psm}",
        )

    def _read_once(self, gray_or_bgr: np.ndarray, preprocess_name: str, psm: int) -> OcrAttempt:
        config = f"--oem 3 --psm {psm} -c tessedit_char_whitelist={PLATE_WHITELIST}"
        image = self._to_pil(gray_or_bgr)

        try:
            data = pytesseract.image_to_data(image, config=config, output_type=Output.DICT)
        except Exception as exc:
            return OcrAttempt(engine="tesseract", preprocess=preprocess_name, raw_text=str(exc))

        words: list[str] = []
        confidences: list[float] = []
        for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
            cleaned_word = text.strip()
            try:
                conf_value = float(conf)
            except (TypeError, ValueError):
                conf_value = -1.0
            if cleaned_word and conf_value >= 0:
                words.append(cleaned_word)
                confidences.append(conf_value)

        raw_text = " ".join(words)
        confidence = sum(confidences) / len(confidences) if confidences else 0.0

        if not raw_text:
            try:
                raw_text = pytesseract.image_to_string(image, config=config).strip()
            except Exception:
                raw_text = ""

        display_text = format_vietnam_plate(raw_text)
        normalized = normalize_plate_text(display_text)
        quality = plate_quality_score(display_text or normalized, confidence)
        return OcrAttempt(
            text=display_text,
            normalized_text=normalized,
            confidence=quality,
            raw_text=raw_text,
            engine="tesseract",
            preprocess=f"{preprocess_name}/psm{psm}",
        )

    @staticmethod
    def _to_pil(image: np.ndarray) -> Image.Image:
        if len(image.shape) == 2:
            return Image.fromarray(image)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    @staticmethod
    def _preprocess_variants(crop_bgr: np.ndarray) -> list[tuple[str, np.ndarray]]:
        if crop_bgr.size == 0:
            return []

        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape[:2]
        scale = max(1.0, 120 / max(height, 1))
        scale = min(scale, 2.2, 1400 / max(width, 1))
        resized = cv2.resize(gray, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_CUBIC)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(resized)
        blur = cv2.GaussianBlur(clahe, (0, 0), 1.0)
        sharp = cv2.addWeighted(clahe, 1.55, blur, -0.55, 0)
        denoised = cv2.bilateralFilter(clahe, 9, 75, 75)
        _, otsu = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        adaptive = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9)

        variants = [
            ("gray", resized),
            ("clahe", clahe),
            ("sharp", sharp),
            ("otsu", otsu),
            ("otsu_inv", cv2.bitwise_not(otsu)),
            ("adaptive", adaptive),
            ("adaptive_inv", cv2.bitwise_not(adaptive)),
        ]
        return variants
