from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.dataset_benchmark import evaluate_result, load_benchmark_items, summarise
from check_vehicle_ocr.paddle_ocr_engine import PaddleOcrEngine
from check_vehicle_ocr.processor import process_image


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark PaddleOCR bằng folder ảnh local và manifest tùy chọn.")
    parser.add_argument("--folder", type=Path, required=True, help="Folder ảnh local; không tải ảnh từ Internet.")
    parser.add_argument("--manifest", type=Path, help="Mảng JSON image/expected_plate, đường dẫn image tương đối manifest.")
    parser.add_argument("--mode", choices=("fast", "balanced", "thorough"), default="balanced")
    parser.add_argument("--output", type=Path, required=True, help="File JSON báo cáo mới.")
    parser.add_argument("--blur-threshold", type=float, default=80.0)
    parser.add_argument("--confidence-threshold", type=float, default=25.0)
    args = parser.parse_args()

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    items = load_benchmark_items(args.folder, args.manifest)
    if not items:
        raise SystemExit("Không có ảnh local nào để benchmark.")
    engine = PaddleOcrEngine(confidence_threshold=args.confidence_threshold)
    if not engine.available:
        raise SystemExit(engine.reason or "PaddleOCR chưa sẵn sàng.")
    crop_dir = args.output.with_suffix("").parent / f"{args.output.stem}_crops"
    started = time.perf_counter()
    rows = []
    for item in items:
        result = process_image(
            item.image_path,
            crop_dir,
            engine,
            blur_threshold=args.blur_threshold,
            confidence_threshold=args.confidence_threshold,
            paddle_scan_mode=args.mode,
        )
        rows.append(evaluate_result(result, item.expected_plate))
    report = summarise(rows, time.perf_counter() - started, args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
