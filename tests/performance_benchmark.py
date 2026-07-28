from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _measure(callable_):
    started = time.perf_counter()
    result = callable_()
    return time.perf_counter() - started, result


def _make_synthetic_image(path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 520), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((290, 250, 610, 330), fill="white", outline="black", width=4)
    try:
        font = ImageFont.truetype("arial.ttf", 52)
    except Exception:
        font = ImageFont.load_default()
    draw.text((330, 263), "30A-123.45", fill="black", font=font)
    image.save(path)


def _ocr_counters(engine, image_shape: tuple[int, int]):
    counters = {"scene": 0, "roi": 0, "fallback": 0, "total": 0}
    original = engine.read_plate_regions_batch
    image_height, image_width = image_shape

    def wrapped(crops, *args, **kwargs):
        for crop in crops:
            counters["total"] += 1
            height, width = crop.shape[:2]
            if height >= image_height * 0.95 and width >= image_width * 0.95:
                counters["scene"] += 1
            else:
                counters["roi"] += 1
                counters["fallback"] += 1
        return original(crops, *args, **kwargs)

    engine.read_plate_regions_batch = wrapped
    return counters


def _single_run() -> dict[str, float | int]:
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("CHECK_VEHICLE_DISABLE_ONNX_DETECTOR", "1")

    import_started = time.perf_counter()
    from check_vehicle_ocr.app import CheckVehicleApp
    from check_vehicle_ocr.excel_export import export_results
    from check_vehicle_ocr.image_io import load_image
    from check_vehicle_ocr.paddle_ocr_engine import PaddleOcrEngine
    from check_vehicle_ocr.processor import process_image

    import_seconds = time.perf_counter() - import_started
    previous_appdata = os.environ.get("APPDATA")
    with tempfile.TemporaryDirectory(prefix="check_vehicle_benchmark_appdata_") as appdata:
        os.environ["APPDATA"] = appdata
        try:
            ui_seconds, app = _measure(CheckVehicleApp)
            app.destroy()
        finally:
            if previous_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = previous_appdata

    with tempfile.TemporaryDirectory(prefix="check_vehicle_benchmark_") as temporary:
        root = Path(temporary)
        image_paths = [root / f"sample_{index}.jpg" for index in range(3)]
        for image_path in image_paths:
            _make_synthetic_image(image_path)

        engine = PaddleOcrEngine(confidence_threshold=20)
        cold_init_seconds, available = _measure(lambda: engine.available)
        if not available:
            raise RuntimeError(engine.reason or "PaddleOCR is unavailable")

        image_bgr, (image_width, image_height) = load_image(image_paths[0])
        counters = _ocr_counters(engine, (image_height, image_width))
        first_seconds, first_result = _measure(
            lambda: process_image(image_paths[0], root / "crops", engine, blur_threshold=10, confidence_threshold=20)
        )
        warm_seconds, warm_result = _measure(
            lambda: process_image(image_paths[1], root / "crops", engine, blur_threshold=10, confidence_threshold=20)
        )
        batch_seconds, batch_results = _measure(
            lambda: [
                process_image(image_path, root / "batch_crops", engine, blur_threshold=10, confidence_threshold=20)
                for image_path in image_paths
            ]
        )

        compact_path = root / "compact.xlsx"
        compact_seconds, _ = _measure(
            lambda: export_results(batch_results, compact_path, blur_threshold=10, include_images=False)
        )
        full_path = root / "full.xlsx"
        full_seconds, _ = _measure(
            lambda: export_results(batch_results, full_path, blur_threshold=10, include_images=True)
        )
        return {
            "app_import_seconds": import_seconds,
            "ui_init_seconds": ui_seconds,
            "paddle_cold_init_seconds": cold_init_seconds,
            "first_image_seconds": first_seconds,
            "warm_image_seconds": warm_seconds,
            "batch_seconds": batch_seconds,
            "excel_compact_seconds": compact_seconds,
            "excel_full_seconds": full_seconds,
            "paddle_initializations": 1,
            "ocr_scene_calls": counters["scene"],
            "ocr_roi_calls": counters["roi"],
            "ocr_fallback_calls": counters["fallback"],
            "ocr_total_calls": counters["total"],
            "compact_bytes": compact_path.stat().st_size,
            "full_bytes": full_path.stat().st_size,
            "first_result_plates": len(first_result.plates),
            "warm_result_plates": len(warm_result.plates),
        }


def _run_three_times() -> int:
    results = []
    for _ in range(3):
        completed = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--single-run"],
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True",
                "CHECK_VEHICLE_DISABLE_ONNX_DETECTOR": "1",
            },
        )
        payload = completed.stdout.strip().splitlines()[-1]
        results.append(json.loads(payload))

    numeric_keys = sorted(results[0])
    median = {key: statistics.median(item[key] for item in results) for key in numeric_keys}
    print(json.dumps({"runs": results, "median": median}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-run", action="store_true")
    args = parser.parse_args()
    if args.single_run:
        print(json.dumps(_single_run(), ensure_ascii=False))
        return 0
    return _run_three_times()


if __name__ == "__main__":
    raise SystemExit(main())
