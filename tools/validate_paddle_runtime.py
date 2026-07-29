from __future__ import annotations

"""Small offline acceptance check run inside a staged PaddleOCR runtime.

The Paddle synthetic OCR check is intentionally performed by
``main.py --self-test-paddle``.  This companion check verifies that the
candidate runtime can still normalize a plate and produce a compact Excel file
without reading images or using the network.
"""

import argparse
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compact", action="store_true")
    _args = parser.parse_args()

    from openpyxl import load_workbook

    from check_vehicle_ocr.excel_export import export_results
    from check_vehicle_ocr.models import ImageResult, PlateCandidate
    from check_vehicle_ocr.ocr import normalize_plate_text

    if normalize_plate_text("30A-123.45") != "30A12345":
        raise SystemExit("Normalization smoke failed")
    with tempfile.TemporaryDirectory(prefix="check_vehicle_runtime_excel_") as temporary:
        root = Path(temporary)
        result = ImageResult(
            image_path=root / "synthetic.jpg",
            status="OK",
            reason="runtime validation",
            plates=[PlateCandidate(bbox=(0, 0, 1, 1), score=99, text="30A-123.45", normalized_text="30A12345", readable=True)],
        )
        output = export_results([result], root / "validation.xlsx", blur_threshold=80, include_images=False)
        workbook = load_workbook(output, read_only=True)
        workbook.close()
    print("Paddle runtime normalization and Excel smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
