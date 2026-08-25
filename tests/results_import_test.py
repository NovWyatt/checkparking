from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_vehicle_ocr.excel_export import export_results
from check_vehicle_ocr.models import ImageResult, PlateCandidate
from check_vehicle_ocr.results_import import ResultsImportError, load_exported_results


def _plate(value: str) -> PlateCandidate:
    return PlateCandidate(bbox=(0, 0, 0, 0), score=80, text=value, raw_text=value, readable=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "vehicle_plates.xlsx"
        crop = root / "xe_01_crop.jpg"
        Image.new("RGB", (120, 40), "#facc15").save(crop)
        original = [
            ImageResult(
                image_path=root / "xe_01.jpg",
                status="OK",
                reason="Đủ rõ",
                blur_score=12.5,
                width=1920,
                height=1080,
                plates=[PlateCandidate(bbox=(12, 15, 100, 30), score=80, crop_path=crop, text="30A-123.45", raw_text="30A-123.45", readable=True)],
            ),
            ImageResult(image_path=root / "xe_02.jpg", status="UNREADABLE", reason="Cần xem lại", blur_score=5.0, width=1280, height=720, plates=[_plate("59X1-999.99"), _plate("51F-123.45")]),
        ]
        export_results(original, source, blur_threshold=10.0, include_images=False)
        imported = load_exported_results(source)
        assert len(imported) == 2
        assert imported[0].image_path.name == "xe_01.jpg"
        assert imported[0].status == "OK" and imported[0].blur_score == 12.5
        assert (imported[0].width, imported[0].height) == (1920, 1080)
        assert imported[0].plates[0].crop_path == crop
        assert [plate.final_text for plate in imported[1].plates] == ["59X1-999.99", "51F-123.45"]
        crop.unlink()
        imported_without_crop = load_exported_results(source)
        assert imported_without_crop[0].plates[0].crop_path is None
        try:
            load_exported_results(root / "missing.xlsx")
        except ResultsImportError:
            pass
        else:
            raise AssertionError("Phải báo lỗi khi file không tồn tại")
    print("results_import_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
