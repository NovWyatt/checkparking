from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.dataset_benchmark import evaluate_result, load_benchmark_items, summarise
from check_vehicle_ocr.models import ImageResult, PlateCandidate


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        image_path = root / "images" / "sample.jpg"
        image_path.parent.mkdir()
        Image.new("RGB", (40, 20), "white").save(image_path)
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps([{"image": "images/sample.jpg", "expected_plate": "51H-123.45"}]), encoding="utf-8")
        items = load_benchmark_items(root, manifest)
        assert len(items) == 1 and items[0].expected_plate == "51H-123.45"
        result = ImageResult(
            image_path=image_path,
            status="OK",
            reason="ok",
            plates=[PlateCandidate(bbox=(0, 0, 1, 1), score=90, text="51H-123.45", normalized_text="51H12345", confidence=90, readable=True)],
        )
        row = evaluate_result(result, items[0].expected_plate)
        assert row["exact_match"] and row["character_accuracy"] == 1.0 and not row["false_positive"]
        summary = summarise([row], 2.0, "balanced")
        assert summary["total_images"] == 1 and summary["exact_match_rate"] == 1.0 and summary["images_per_minute"] == 30.0
    print("dataset_benchmark_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
