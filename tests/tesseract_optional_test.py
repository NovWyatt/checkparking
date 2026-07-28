from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.models import ImageResult


class _GeminiError:
    def analyze_image(self, image: Path, _blur_threshold: float) -> ImageResult:
        return ImageResult(image_path=image, status="ERROR", reason="Không đọc được")


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        image_path = Path(temporary) / "image.jpg"
        Image.new("RGB", (32, 16), "white").save(image_path)
        engine_factory = Mock()
        with patch("check_vehicle_ocr.app.TesseractOcrEngine", engine_factory):
            result = CheckVehicleApp._process_one(0, image_path, Path(temporary), "Gemini Vision", _GeminiError(), None, 10, 40, tesseract_fallback_enabled=False)
        assert result.status == "ERROR" and not engine_factory.called

        local_engine = Mock()
        local_engine.available = True
        local_result = ImageResult(image_path=image_path, status="OK", reason="Tesseract đọc được")
        with patch("check_vehicle_ocr.app.TesseractOcrEngine", return_value=local_engine) as engine_factory, patch(
            "check_vehicle_ocr.app.process_image", return_value=local_result
        ):
            result = CheckVehicleApp._process_one(0, image_path, Path(temporary), "Gemini Vision", _GeminiError(), None, 10, 40, tesseract_fallback_enabled=True)
        assert engine_factory.called and result.reason.startswith("Gemini và Local OCR")
    print("tesseract_optional_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
