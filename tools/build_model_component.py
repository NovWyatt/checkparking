"""Create a verified, versioned PP-OCR model update asset from bundled files."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", default="")
    parser.add_argument("--repository", default="NovWyatt/checkparking")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--detection-model", default="PP-OCRv6_small_det")
    parser.add_argument("--recognition-model", default="PP-OCRv6_small_rec")
    args = parser.parse_args()

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    tag = args.tag.strip() or f"v{args.version}"
    name = f"CheckVehicleOCR-PP-OCRv6-small-model-{args.version}.zip"
    archive_path = output / name
    root = ROOT / "models" / "paddleocr"
    source_dirs = [root / args.detection_model, root / args.recognition_model]
    if not all((source / "inference.yml").is_file() for source in source_dirs):
        raise SystemExit("Bundled PP-OCRv6 Small model files are missing.")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in source_dirs:
            for path in sorted(source.rglob("*")):
                if path.is_file() and ".cache" not in path.parts:
                    archive.write(path, path.relative_to(root))
    checksum = _sha256(archive_path)
    payload = {
        "schema_version": 1,
        "version": f"pp-ocrv6-small-{args.version}",
        "detection_model": args.detection_model,
        "recognition_model": args.recognition_model,
        "download_url": f"https://github.com/{args.repository}/releases/download/{tag}/{name}",
        "sha256": checksum,
        "platform": "windows-x64",
        "source": "Project-controlled GitHub Release asset built from bundled verified PP-OCRv6 Small models",
    }
    manifest = output / "model-manifest.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"archive": name, "sha256": checksum, "manifest": manifest.name}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
