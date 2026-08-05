from __future__ import annotations

import sys
import tempfile
import traceback
import os
import subprocess
import multiprocessing as mp
from pathlib import Path


def _launch_active_runtime_if_needed() -> None:
    """Run an accepted staged runtime and fall back to this interpreter on failure.

    The parent intentionally waits for the child: a broken candidate exits and
    the known-good base runtime starts instead.  Self-tests are always run in
    the explicitly selected interpreter so staging validation cannot redirect
    to a previously active candidate.
    """
    if os.environ.get("CHECK_VEHICLE_RUNTIME_LAUNCHED") or "--self-test-paddle" in sys.argv:
        return
    try:
        from check_vehicle_ocr.runtime_manager import active_runtime_python

        runtime_python = active_runtime_python(Path(__file__).resolve().parent)
        if runtime_python is None or runtime_python.resolve() == Path(sys.executable).resolve():
            return
        completed = subprocess.run(
            [str(runtime_python), str(Path(__file__).resolve()), *sys.argv[1:]],
            env={**os.environ, "CHECK_VEHICLE_RUNTIME_LAUNCHED": "1"},
            check=False,
        )
        if completed.returncode == 0:
            raise SystemExit(0)
        print("Runtime thử nghiệm không khởi động được; đang quay lại runtime trước đó.", file=sys.stderr)
    except SystemExit:
        raise
    except Exception:
        # Starting from the bundled/base interpreter is the safe fallback.  Do
        # not show internal paths or exception details in the UI path.
        return


def _recover_interrupted_app_update() -> None:
    """Best-effort recovery of an interrupted installer helper before GUI use."""
    try:
        from check_vehicle_ocr.config import settings_path
        from check_vehicle_ocr.updater import recover_pending_installer_update

        recover_pending_installer_update(settings_path().parent / "updates" / "pending-installer-update.json")
    except Exception:
        # The updater helper owns detailed diagnostics.  Startup must retain a
        # working base runtime even when its prior state cannot be read.
        pass


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


def _run_runtime_health_check() -> int:
    """Non-GUI health check used by the updater after runtime activation."""
    try:
        from check_vehicle_ocr.paddle_ocr_engine import PaddleOcrEngine

        engine = PaddleOcrEngine(confidence_threshold=20)
        return 0 if engine.available else 2
    except Exception:
        return 10


def _write_self_test_log(message: str) -> None:
    log_path = Path(tempfile.gettempdir()) / "CheckVehicleOCR_paddle_self_test.log"
    try:
        log_path.write_text(message, encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    # Required by Windows spawn and frozen PyInstaller executables.  This must
    # run before importing the Tk application to avoid recursive GUI children.
    mp.freeze_support()
    _recover_interrupted_app_update()
    _launch_active_runtime_if_needed()
    if "--runtime-health-check" in sys.argv:
        raise SystemExit(_run_runtime_health_check())
    if "--self-test-paddle" in sys.argv:
        raise SystemExit(_run_paddle_self_test())

    from check_vehicle_ocr.app import main as app_main

    app_main()

if __name__ == "__main__":
    main()
