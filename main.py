from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path


def _run_paddle_self_test() -> int:
    from PIL import Image, ImageDraw, ImageFont

    from check_vehicle_ocr import paddle_ocr_engine
    from check_vehicle_ocr.paddle_ocr_engine import PaddleOcrEngine
    from check_vehicle_ocr.processor import process_image

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "paddle_self_test.jpg"
            image = Image.new("RGB", (900, 520), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((290, 250, 610, 330), fill="white", outline="black", width=4)
            try:
                font = ImageFont.truetype("arial.ttf", 52)
            except Exception:
                font = ImageFont.load_default()
            draw.text((330, 263), "30A-123.45", fill="black", font=font)
            image.save(image_path)

            try:
                paddle_ocr_engine._get_ocr()
            except Exception:
                _write_self_test_log(traceback.format_exc())
                return 2

            engine = PaddleOcrEngine(confidence_threshold=20)
            if not engine.available:
                _write_self_test_log(f"PaddleOCR unavailable: {engine.reason}")
                return 2
            result = process_image(image_path, root / "crops", engine, blur_threshold=10, confidence_threshold=20)
            normalized = [plate.normalized_text for plate in result.plates]
            if any(text == "30A12345" for text in normalized):
                _write_self_test_log("PaddleOCR self-test OK")
                return 0
            _write_self_test_log(f"PaddleOCR did not read expected plate. Got: {normalized}")
            return 3
    except Exception:
        _write_self_test_log(traceback.format_exc())
        return 10


def _write_self_test_log(message: str) -> None:
    log_path = Path(tempfile.gettempdir()) / "CheckVehicleOCR_paddle_self_test.log"
    try:
        log_path.write_text(message, encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    if "--self-test-paddle" in sys.argv:
        raise SystemExit(_run_paddle_self_test())

    from check_vehicle_ocr.app import main as app_main

    app_main()

if __name__ == "__main__":
    main()
