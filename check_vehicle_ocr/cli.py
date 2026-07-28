from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .excel_export import export_results
from .image_io import collect_images
from .ocr import TesseractOcrEngine
from .processor import process_image


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch OCR bien so xe va xuat Excel.")
    parser.add_argument("inputs", nargs="+", type=Path, help="File anh hoac folder anh")
    parser.add_argument("-o", "--output", type=Path, default=None, help="File Excel output")
    parser.add_argument("--tesseract", type=Path, default=None, help="Duong dan tesseract.exe")
    parser.add_argument("--no-recursive", action="store_true", help="Khong quet folder con")
    parser.add_argument("--blur-threshold", type=float, default=80.0)
    parser.add_argument("--confidence-threshold", type=float, default=40.0)
    args = parser.parse_args()

    images = collect_images(args.inputs, recursive=not args.no_recursive)
    if not images:
        print("Khong tim thay anh dau vao.")
        return 2

    engine = TesseractOcrEngine(args.tesseract, confidence_threshold=args.confidence_threshold)
    if not engine.available:
        print(f"OCR chua san sang: {engine.reason}")
        return 3

    output = args.output or Path.cwd() / f"vehicle_plates_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    crop_dir = output.with_suffix("").parent / f"{output.stem}_crops"
    results = []
    for index, image in enumerate(images, start=1):
        print(f"[{index}/{len(images)}] {image}")
        results.append(process_image(image, crop_dir, engine, args.blur_threshold, args.confidence_threshold))

    export_results(results, output, args.blur_threshold)
    print(f"Da xuat: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
