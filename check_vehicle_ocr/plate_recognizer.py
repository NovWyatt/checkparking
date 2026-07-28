from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .image_io import load_image
from .models import ImageResult, PlateCandidate
from .ocr import clean_display_text, format_vietnam_plate, is_timestamp_like, normalize_plate_text
from .processor import blur_score


PLATE_RECOGNIZER_API_URL = "https://api.platerecognizer.com/v1/plate-reader/"
DEFAULT_PLATE_RECOGNIZER_REGION = "vn"


class PlateRecognizerEngine:
    def __init__(self, api_token: str | None = None, regions: str | None = None, timeout: float = 60.0):
        self.api_token = (api_token or os.environ.get("PLATE_RECOGNIZER_TOKEN") or "").strip()
        self.regions = (regions or DEFAULT_PLATE_RECOGNIZER_REGION).strip()
        self.timeout = timeout
        self.reason = ""
        if not self.api_token:
            self.reason = "Chưa có PLATE_RECOGNIZER_TOKEN."

    @property
    def available(self) -> bool:
        return bool(self.api_token)

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
                reason="Plate Recognizer chưa sẵn sàng",
                blur_score=sharpness,
                width=width,
                height=height,
                warnings=warnings,
                error=self.reason,
            )

        try:
            payload = self._call_api(image_path)
        except Exception as exc:
            return ImageResult(
                image_path=image_path,
                status="ERROR",
                reason="Plate Recognizer lỗi khi phân tích ảnh",
                blur_score=sharpness,
                width=width,
                height=height,
                warnings=warnings,
                error=str(exc),
            )

        plates: list[PlateCandidate] = []
        seen: set[str] = set()
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            plate_text = self._plate_text_from_result(item)
            if not plate_text or is_timestamp_like(plate_text):
                continue
            normalized = normalize_plate_text(plate_text)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)

            confidence = self._confidence_from_result(item)
            bbox = self._bbox_from_result(item, width, height)
            region = ""
            if isinstance(item.get("region"), dict):
                region = str(item["region"].get("code", "") or "").strip()
            reason = f"region={region}" if region else "plate detector"
            plates.append(
                PlateCandidate(
                    bbox=bbox,
                    score=confidence,
                    source="plate_recognizer",
                    text=plate_text,
                    normalized_text=normalized,
                    confidence=confidence,
                    raw_text=json.dumps(item, ensure_ascii=False),
                    readable=bool(plate_text),
                    reason=reason,
                )
            )

        if plates:
            status = "OK"
            reason = "Plate Recognizer đọc được biển số"
        elif sharpness < blur_threshold:
            status = "BLURRY"
            reason = "Plate Recognizer không đọc được vì ảnh mờ"
        else:
            status = "UNREADABLE"
            reason = "Plate Recognizer không thấy biển số đọc được"

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

    def _call_api(self, image_path: Path) -> dict[str, Any]:
        image_bytes, filename, mime_type = _image_to_jpeg_bytes(image_path)
        fields: dict[str, str] = {}
        regions = [region.strip() for region in self.regions.replace(";", ",").split(",") if region.strip()]
        if regions:
            fields["regions"] = ",".join(regions)

        body, content_type = _encode_multipart(fields, "upload", filename, image_bytes, mime_type)
        request = urllib.request.Request(
            PLATE_RECOGNIZER_API_URL,
            data=body,
            headers={
                "Authorization": f"Token {self.api_token}",
                "Content-Type": content_type,
            },
            method="POST",
        )

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                error = RuntimeError(f"Plate Recognizer API HTTP {exc.code}: {detail[:600]}")
                if exc.code not in {429, 500, 502, 503}:
                    raise error from exc
                last_error = error
            except Exception as exc:
                last_error = exc

            if attempt < 2:
                time.sleep(1.2 * (attempt + 1))

        if last_error:
            raise last_error
        raise RuntimeError("Plate Recognizer không trả kết quả.")

    @staticmethod
    def _plate_text_from_result(item: dict[str, Any]) -> str:
        raw_value = str(item.get("plate", "") or "").strip()
        display = clean_display_text(raw_value)
        if not display:
            return ""
        formatted = format_vietnam_plate(display)
        return formatted or display

    @staticmethod
    def _confidence_from_result(item: dict[str, Any]) -> float:
        try:
            value = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            return 0.0
        if value <= 1.0:
            value *= 100.0
        return max(0.0, min(100.0, value))

    @staticmethod
    def _bbox_from_result(item: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int]:
        box = item.get("box")
        if not isinstance(box, dict):
            return (0, 0, width, height)
        try:
            xmin = int(box.get("xmin", 0))
            ymin = int(box.get("ymin", 0))
            xmax = int(box.get("xmax", width))
            ymax = int(box.get("ymax", height))
        except (TypeError, ValueError):
            return (0, 0, width, height)
        x = max(0, min(xmin, width))
        y = max(0, min(ymin, height))
        w = max(0, min(xmax, width) - x)
        h = max(0, min(ymax, height) - y)
        return (x, y, w, h)


def _image_to_jpeg_bytes(image_path: Path, max_side: int = 2200, quality: int = 92) -> tuple[bytes, str, str]:
    try:
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
            return buffer.getvalue(), f"{image_path.stem}.jpg", "image/jpeg"
    except Exception:
        data = image_path.read_bytes()
        mime_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
        return data, image_path.name, mime_type


def _encode_multipart(
    fields: dict[str, str],
    file_field: str,
    filename: str,
    file_bytes: bytes,
    mime_type: str,
) -> tuple[bytes, str]:
    boundary = f"----CheckVehicleOCR{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8"),
            f"Content-Type: {mime_type}\r\n\r\n".encode("ascii"),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"
