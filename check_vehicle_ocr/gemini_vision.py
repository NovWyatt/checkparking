from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .gpt_vision import GPT_PLATE_PROMPT, _bgr_image_to_data_url, _candidate_crop_data_urls, _parse_json_response
from .image_io import load_image
from .models import ImageResult, PlateCandidate
from .ocr import clean_display_text, format_vietnam_plate, is_timestamp_like, looks_like_plate, normalize_plate_text
from .processor import blur_score


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MODEL_CHOICES = ("gemini-2.5-flash", "gemini-2.5-pro", "gemini-3-flash-preview", "gemini-2.5-flash-lite")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_AUTO_APPROVE_CONFIDENCE = 72.0
GEMINI_MIN_REQUEST_INTERVAL_SECONDS = 4.0

_GEMINI_REQUEST_LOCK = threading.Lock()
_GEMINI_LAST_REQUEST_AT = 0.0

GEMINI_RESPONSE_SCHEMA = {
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
}


class GeminiVisionEngine:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0):
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
        self.model = (model or DEFAULT_GEMINI_MODEL).strip()
        self.timeout = timeout
        self.reason = ""
        self.last_model_used = self.model
        if not self.api_key:
            self.reason = "Chưa có GEMINI_API_KEY."

    @property
    def available(self) -> bool:
        return bool(self.api_key)

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
                reason="Gemini Vision chưa sẵn sàng",
                blur_score=sharpness,
                width=width,
                height=height,
                warnings=warnings,
                error=self.reason,
            )

        try:
            payload = self._call_model(image_bgr)
        except Exception as exc:
            return ImageResult(
                image_path=image_path,
                status="ERROR",
                reason="Gemini Vision lỗi khi phân tích ảnh",
                blur_score=sharpness,
                width=width,
                height=height,
                warnings=warnings,
                error=str(exc),
            )

        if payload.get("image_blurry"):
            warnings.append("Gemini đánh dấu ảnh mờ/khó đọc")
        if payload.get("needs_review"):
            warnings.append("Gemini yêu cầu đối chiếu lại kết quả")

        plates: list[PlateCandidate] = []
        seen: set[str] = set()
        for item in payload.get("plates", []):
            if not isinstance(item, dict):
                continue
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
            source = f"gemini_vision:{self.last_model_used}" if self.last_model_used else "gemini_vision"
            readable = (
                confidence >= GEMINI_AUTO_APPROVE_CONFIDENCE
                and visibility.lower() == "clear"
                and not payload.get("image_blurry")
                and not payload.get("needs_review")
            )

            plates.append(
                PlateCandidate(
                    bbox=(0, 0, width, height),
                    score=confidence,
                    source=source,
                    text=plate_text,
                    normalized_text=normalized,
                    confidence=confidence,
                    raw_text=json.dumps(item, ensure_ascii=False),
                    readable=readable,
                    reason=reason,
                )
            )

        notes = str(payload.get("notes", "") or "").strip()
        if plates:
            status = "OK"
            reason = "Gemini Vision đọc được biển số"
        elif sharpness < blur_threshold or payload.get("image_blurry"):
            status = "BLURRY"
            reason = notes or "Gemini Vision không đọc được vì ảnh mờ"
        else:
            status = "UNREADABLE"
            reason = notes or "Gemini Vision không thấy biển số đọc được"

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

    def _call_model(self, image_bgr) -> dict[str, Any]:
        image_parts = [_data_url_to_inline_data(_bgr_image_to_data_url(image_bgr))]
        image_parts.extend(_data_url_to_inline_data(data_url) for data_url in _candidate_crop_data_urls(image_bgr, max_crops=6))

        parts: list[dict[str, Any]] = [{"text": GEMINI_PLATE_PROMPT}]
        parts.extend(image_parts)

        last_error: Exception | None = None
        for model_name in self._model_retry_order():
            self.last_model_used = model_name
            for attempt in range(4):
                try:
                    text = self._generate_content(model_name, parts, use_schema=True)
                    return _parse_json_response(text)
                except Exception as exc:
                    last_error = exc
                    if _should_retry_without_schema(exc):
                        text = self._generate_content(model_name, parts, use_schema=False)
                        return _parse_json_response(text)
                    if _is_model_quota_error(exc):
                        break
                    if _is_model_access_error(exc):
                        break
                    if not _is_transient_error(exc) or attempt >= 3:
                        raise
                    time.sleep(_retry_delay_seconds(exc, attempt))

        if last_error:
            raise last_error
        raise RuntimeError("Gemini Vision không có model khả dụng.")

    def _generate_content(self, model_name: str, parts: list[dict[str, Any]], use_schema: bool) -> str:
        model_id = model_name.removeprefix("models/").strip()
        endpoint = GEMINI_API_URL.format(model=urllib.parse.quote(model_id, safe=""))
        generation_config: dict[str, Any] = {
            "temperature": 0,
            "maxOutputTokens": 1200,
            "responseMimeType": "application/json",
        }
        if use_schema:
            generation_config["responseJsonSchema"] = GEMINI_RESPONSE_SCHEMA
        thinking_config = _thinking_config_for_model(model_id)
        if thinking_config:
            generation_config["thinkingConfig"] = thinking_config

        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            _wait_for_gemini_slot()
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini API HTTP {exc.code}: {detail[:600]}") from exc

        return _extract_text(payload)

    def _model_retry_order(self) -> list[str]:
        candidates = [self.model, *GEMINI_MODEL_CHOICES]
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


GEMINI_PLATE_PROMPT = GPT_PLATE_PROMPT + """

Extra Gemini instruction:
- Vietnamese motorbike plates often have 2 lines. Combine both lines into one plate.
- In parking-lot photos, check every visible motorbike rear/front plate, not only the largest vehicle.
- Treat Image 1 as the full scene and later images as candidate crops. Use crops only to verify text from the same physical plate.
- A valid Vietnamese plate normally starts with 2 province digits, then 1-4 series letters/digits, then 4-6 serial digits.
- Reject text from stickers, shop signs, timestamps, camera overlays, road signs, or clothing even if it looks plate-like.
- Common OCR confusions: O/Q/D vs 0, I/L vs 1, S vs 5, B vs 8, G vs 6. Use the vehicle plate pattern to resolve them, but lower confidence when uncertain.
- Mark needs_review=true when any returned plate is blurry, partially blocked, very small, or has an uncertain character.
"""


def _data_url_to_inline_data(data_url: str) -> dict[str, Any]:
    header, encoded = data_url.split(",", 1)
    mime_type = header.removeprefix("data:").split(";", 1)[0] or "image/jpeg"
    return {"inline_data": {"mime_type": mime_type, "data": encoded}}


def _extract_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError(f"Gemini không trả candidate: {json.dumps(payload, ensure_ascii=False)[:600]}")

    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [str(part.get("text", "")) for part in parts if isinstance(part, dict) and part.get("text")]
    if not texts:
        finish_reason = candidates[0].get("finishReason", "")
        raise RuntimeError(f"Gemini không trả text. finishReason={finish_reason}")
    return "\n".join(texts)


def _is_model_access_error(exc: Exception) -> bool:
    message = str(exc).lower()
    model_words = ("not found", "not supported", "permission", "access", "invalid model", "403", "404")
    return any(word in message for word in model_words) and not _is_transient_error(exc)


def _is_model_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message and ("limit: 0" in message or "billing" in message)


def _is_transient_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(word in message for word in ("rate limit", "429", "timeout", "temporarily", "server error", "503", "502", "500"))


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    message = str(exc).lower()
    if "429" in message or "rate limit" in message or "quota exceeded" in message:
        return min(45.0, 8.0 * (2**attempt))
    return 1.5 * (attempt + 1)


def _wait_for_gemini_slot() -> None:
    global _GEMINI_LAST_REQUEST_AT
    with _GEMINI_REQUEST_LOCK:
        now = time.monotonic()
        wait_seconds = GEMINI_MIN_REQUEST_INTERVAL_SECONDS - (now - _GEMINI_LAST_REQUEST_AT)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        _GEMINI_LAST_REQUEST_AT = time.monotonic()


def _should_retry_without_schema(exc: Exception) -> bool:
    message = str(exc).lower()
    schema_words = ("responsejsonschema", "response_json_schema", "json schema", "schema", "additionalproperties", "enum")
    return any(word in message for word in schema_words)


def _thinking_config_for_model(model_id: str) -> dict[str, Any]:
    normalized = model_id.lower()
    if normalized.startswith("gemini-3"):
        return {"thinkingLevel": "high"}
    if normalized.startswith("gemini-2.5"):
        return {"thinkingBudget": -1}
    return {}
