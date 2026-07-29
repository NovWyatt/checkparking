"""Offline release-gate validation for a completed Tesseract component ZIP."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_vehicle_ocr.update_center import (
    activate_tesseract_stage,
    parse_tesseract_manifest,
    stage_local_tesseract_package,
    validate_tesseract_component,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=ROOT / "assets" / "tesseract" / "smoke-plate.png")
    args = parser.parse_args()
    manifest = parse_tesseract_manifest(args.manifest.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="check_vehicle_tesseract_validate_") as temporary:
        root = Path(temporary) / "LocalAppData" / "CheckVehicleOCR" / "components" / "tesseract"
        staged = stage_local_tesseract_package(args.archive, manifest, root)
        version = validate_tesseract_component(staged, expected_version=manifest.version, smoke_image=args.fixture)
        active = activate_tesseract_stage(staged, manifest, root)
        if not active.is_file():
            raise RuntimeError("Activated Tesseract executable is missing.")
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
