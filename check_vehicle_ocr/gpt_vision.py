from __future__ import annotations

import base64
import json
import os
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
from PIL import Image, ImageOps

from .image_io import load_image
from .models import ImageResult, PlateCandidate
from .ocr import clean_display_text, format_vietnam_plate, is_timestamp_like, looks_like_plate, normalize_plate_text
from .processor import (
    blur_score,
    detect_plate_candidates,
    detect_plate_candidates_second_pass,
    detect_plate_outline_candidates,
    fallback_candidates,
)

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


DEFAULT_GPT_MODEL = "gpt-4.1"
GPT_MODEL_CHOICES = ("gpt-4.1", "gpt-4.1-mini", "gpt-5.5", "gpt-5.1", "gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-4o")

GPT_PLATE_PROMPT = """Analyze this vehicle photo and extract every visible vehicle license plate.

Return ONLY valid JSON in this exact shape:
{
  "plates": [
    {
      "plate": "70-K1 247.11",
      "confidence": 0.0,
      "vehicle": "motorbike|car|truck|unknown",
      "visibility": "clear|blurry|partial|blocked|unknown",
      "note": "short Vietnamese note"
    }
  ],
  "image_blurry": false,
  "needs_review": true,
  "notes": "short Vietnamese note"
}

Rules:
- Read only license plates on vehicles.
- Image 1 is the original photo. Any later images are close-up candidate plate crops from the same photo.
- Use all images together, merge duplicates, and return each physical license plate only once.
- Ignore camera timestamps, date/time overlays, watermarks, GPS text, filenames, UI text, and any text that is not on a vehicle plate.
- Specifically reject phone/camera time marks such as "26 Thang 5, 2026", "2026-05-26", or "10:18:14" even if they are sharp and high contrast.
- Preserve the exact plate formatting when visible: dash, spaces, and dots. Example: "70-K1 247.11".
- Do not invent a plate. If one character is uncertain, keep the best visible reading and lower confidence.
- Prefer Vietnamese vehicle plate conventions when separators are unclear:
  * Motorbike style: "70-K1 247.11"
  * Car style: "30A-123.45"
- If a separator is visible but OCR is uncertain, keep your best separator placement and set confidence lower.
- If multiple vehicles or multiple plates appear, return all visible plates.
- If no plate is readable, return an empty plates array and explain why in notes.
- confidence must be 0 to 100.
"""

GPT_RESPONSE_FORMAT = {
    "format": {
        "type": "json_schema",
        "name": "vehicle_plate_scan",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "plates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "plate": {"type": "string"},
                            "confidence": {"type": "number"},
                            "vehicle": {"type": "string", "enum": ["motorbike", "car", "truck", "unknown"]},
                            "visibility": {"type": "string", "enum": ["clear", "blurry", "partial", "blocked", "unknown"]},
                            "note": {"type": "string"},
                        },
                        "required": ["plate", "confidence", "vehicle", "visibility", "note"],
                    },
                },
                "image_blurry": {"type": "boolean"},
                "needs_review": {"type": "boolean"},
                "notes": {"type": "string"},
            },
            "required": ["plates", "image_blurry", "needs_review", "notes"],
        },
    }
}


class GptVisionEngine:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0):
        self.api_key = (api_key or os.environ.get("OPENAI_API_KEY") or "").strip()
        self.model = (model or DEFAULT_GPT_MODEL).strip()
        self.timeout = timeout
        self.reason = ""
        self.last_model_used = self.model

        if OpenAI is None:
            self.client = None
            self.reason = "Python package openai chưa được cài."
            return
        if not self.api_key:
            self.client = None
            self.reason = "Chưa có OPENAI_API_KEY."
            return

        self.client = OpenAI(api_key=self.api_key, timeout=timeout)

    @property
    def available(self) -> bool:
        return self.client is not None

    def analyze_image(self, image_path: Path, blur_threshold: float = 80.0) -> ImageResult:
        try:
            image_bgr, (width, height) = load_image(image_path)
            sharpness = blur_score(image_bgr)
        except Exception as exc:
            return ImageResult(image_path=image_path, status="ERROR", reason="Không đọc được file ảnh", error=str(exc))

        warnings: list[str] = []
        if sharpness < blur_threshold:
            warnings.append(f"Ảnh mờ, blur={sharpness:.1f} < {blur_threshold:.1f}")

        if not self.available:
            return ImageResult(
                image_path=image_path,
                status="ERROR",
                reason="GPT Vision chưa sẵn sàng",
                blur_score=sharpness,
                width=width,
                height=height,
                warnings=warnings,
                error=self.reason,
            )

        try:
            payload = self._call_model(image_path, image_bgr)
        except Exception as exc:
            return ImageResult(
                image_path=image_path,
                status="ERROR",
                reason="GPT Vision lỗi khi phân tích ảnh",
                blur_score=sharpness,
                width=width,
                height=height,
                warnings=warnings,
                error=str(exc),
            )

        if payload.get("image_blurry"):
            warnings.append("GPT đánh dấu ảnh mờ/khó đọc")

        plates: list[PlateCandidate] = []
        seen: set[str] = set()
        for index, item in enumerate(payload.get("plates", []), start=1):
            plate_text = self._plate_text_from_item(item)
            if not plate_text or is_timestamp_like(plate_text):
                continue

            normalized = normalize_plate_text(plate_text)
            if not normalized or not looks_like_plate(normalized):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)

            confidence = self._confidence_from_item(item)
            note = str(item.get("note", "") or "").strip()
            vehicle = str(item.get("vehicle", "") or "").strip()
            visibility = str(item.get("visibility", "") or "").strip()
            reason = "; ".join(part for part in [vehicle, visibility, note] if part)
            source = f"gpt_vision:{self.last_model_used}" if self.last_model_used else "gpt_vision"

            plates.append(
                PlateCandidate(
                    bbox=(0, 0, width, height),
                    score=confidence,
                    source=source,
                    text=plate_text,
                    normalized_text=normalized,
                    confidence=confidence,
                    raw_text=json.dumps(item, ensure_ascii=False),
                    readable=bool(plate_text),
                    reason=reason,
                )
            )

        notes = str(payload.get("notes", "") or "").strip()
        if plates:
            status = "OK"
            reason = "GPT Vision đọc được biển số"
        elif sharpness < blur_threshold or payload.get("image_blurry"):
            status = "BLURRY"
            reason = notes or "GPT Vision không đọc được vì ảnh mờ"
        else:
            status = "UNREADABLE"
            reason = notes or "GPT Vision không thấy biển số đọc được"

        return ImageResult(
            image_path=image_path,
            status=status,
            reason=reason,
            blur_score=sharpness,
            width=width,
            height=height,
            candidate_count=len(plates),
            plates=plates,
            warnings=warnings,
        )

    def _call_model(self, image_path: Path, image_bgr) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": GPT_PLATE_PROMPT}]
        content.append({"type": "input_image", "image_url": _bgr_image_to_data_url(image_bgr), "detail": "high"})
        for data_url in _candidate_crop_data_urls(image_bgr):
            content.append({"type": "input_image", "image_url": data_url, "detail": "high"})

        last_error: Exception | None = None
        for model_name in self._model_retry_order():
            self.last_model_used = model_name
            for attempt in range(3):
                try:
                    response = self._create_response(model_name, content, use_schema=True)
                    return _parse_json_response(response.output_text)
                except Exception as exc:
                    last_error = exc
                    if _should_retry_without_schema(exc):
                        response = self._create_response(model_name, content, use_schema=False)
                        return _parse_json_response(response.output_text)
                    if _is_model_access_error(exc):
                        break
                    if not _is_transient_error(exc) or attempt >= 2:
                        raise
                    time.sleep(1.2 * (attempt + 1))

        if last_error:
            raise last_error
        raise RuntimeError("GPT Vision không có model khả dụng.")

    def _create_response(self, model_name: str, content: list[dict[str, Any]], use_schema: bool):
        kwargs: dict[str, Any] = {
            "model": model_name,
            "input": [{"role": "user", "content": content}],
            "max_output_tokens": 900,
        }
        if use_schema:
            kwargs["text"] = GPT_RESPONSE_FORMAT
        if model_name in {"gpt-5.5", "gpt-5.1", "gpt-5", "gpt-5-mini", "gpt-5-nano"}:
            kwargs["reasoning"] = {"effort": "minimal"}
        return self.client.responses.create(**kwargs)

    def _model_retry_order(self) -> list[str]:
        candidates = [self.model, "gpt-4.1", "gpt-4.1-mini", "gpt-5.5", "gpt-5.1", "gpt-5", "gpt-4o"]
        ordered: list[str] = []
        for candidate in candidates:
            candidate = candidate.strip()
            if candidate and candidate not in ordered:
                ordered.append(candidate)
        return ordered

    @staticmethod
    def _plate_text_from_item(item: dict[str, Any]) -> str:
        raw_value = str(item.get("plate", "") or "").strip()
        display = clean_display_text(raw_value)
        if not display:
            return ""
        formatted = format_vietnam_plate(display)
        return formatted or display

    @staticmethod
    def _confidence_from_item(item: dict[str, Any]) -> float:
        try:
            value = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            return 0.0
        if value <= 1.0:
            value *= 100.0
        return max(0.0, min(100.0, value))


def _image_to_data_url(image_path: Path, max_side: int = 2000, quality: int = 90) -> str:
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        return _pil_image_to_data_url(image, max_side=max_side, quality=quality)


def _bgr_image_to_data_url(image_bgr, max_side: int = 2000, quality: int = 90) -> str:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    return _pil_image_to_data_url(Image.fromarray(rgb), max_side=max_side, quality=quality)


def _pil_image_to_data_url(image: Image.Image, max_side: int, quality: int, min_short_side: int = 0) -> str:
    width, height = image.size
    longest = max(width, height)
    shortest = min(width, height)
    scale = min(1.0, max_side / max(longest, 1))
    if min_short_side and shortest < min_short_side:
        scale = min(max_side / max(longest, 1), max(scale, min_short_side / max(shortest, 1)))
    if abs(scale - 1.0) > 0.01:
        image = image.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _candidate_crop_data_urls(image_bgr, max_crops: int = 4) -> list[str]:
    try:
        first = detect_plate_candidates(image_bgr, max_candidates=8)
        second = detect_plate_candidates_second_pass(image_bgr, max_candidates=8)
        outline = detect_plate_outline_candidates(image_bgr, max_candidates=6)
        fallback = fallback_candidates(image_bgr)
    except Exception:
        return []

    candidates: list[PlateCandidate] = []
    ranked = sorted([*first, *second, *outline, *fallback], key=lambda item: item.score, reverse=True)
    for candidate in ranked:
        if all(_iou(candidate.bbox, existing.bbox) < 0.45 for existing in candidates):
            candidates.append(candidate)
            if len(candidates) >= max_crops:
                break

    height, width = image_bgr.shape[:2]
    data_urls: list[str] = []
    for candidate in candidates:
        x, y, w, h = candidate.bbox
        pad_x = int(w * 0.18)
        pad_y = int(h * 0.35)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(width, x + w + pad_x)
        y2 = min(height, y + h + pad_y)
        crop = image_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        data_urls.append(_pil_image_to_data_url(Image.fromarray(rgb), max_side=1000, quality=94, min_short_side=260))
    return data_urls


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2 = ax + aw
    ay2 = ay + ah
    bx2 = bx + bw
    by2 = by + bh
    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    union = aw * ah + bw * bh - inter_area
    return inter_area / union if union else 0.0


def _should_retry_without_schema(exc: Exception) -> bool:
    message = str(exc).lower()
    return "json_schema" in message or "text.format" in message or "schema" in message


def _is_model_access_error(exc: Exception) -> bool:
    message = str(exc).lower()
    model_words = ("model_not_found", "does not exist", "not found", "invalid model", "access", "permission")
    return any(word in message for word in model_words) and not _is_transient_error(exc)


def _is_transient_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(word in message for word in ("rate limit", "429", "timeout", "temporarily", "server error", "503", "502", "500"))


def _parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(f"GPT không trả JSON hợp lệ: {text[:300]}")
        parsed = json.loads(cleaned[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("GPT JSON không phải object.")
    parsed.setdefault("plates", [])
    if not isinstance(parsed["plates"], list):
        parsed["plates"] = []
    return parsed
