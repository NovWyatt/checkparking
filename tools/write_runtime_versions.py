"""Write build-specific OCR runtime metadata for a distributable artifact."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _installed(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def _opencv_runtime_version() -> str:
    try:
        import cv2

        return str(cv2.__version__)
    except Exception:
        return "not-installed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "runtime-versions.json")
    parser.add_argument("--commit", default="")
    parser.add_argument("--build-date", default="")
    args = parser.parse_args()

    from check_vehicle_ocr.ocr_models import DEFAULT_MODEL_PROFILE
    from check_vehicle_ocr.version import VERSION

    manifest = json.loads((ROOT / "models" / "manifest.json").read_text(encoding="utf-8"))
    models = manifest.get("models") if isinstance(manifest, dict) else []
    index = {str(item.get("id")): item for item in models if isinstance(item, dict)}
    payload = {
        "schema_version": 1,
        "app_version": VERSION,
        "python_version": __import__("sys").version.split()[0],
        "paddleocr": _installed("paddleocr"),
        "paddlepaddle": _installed("paddlepaddle"),
        "paddlex": _installed("paddlex"),
        "opencv": _opencv_runtime_version(),
        "numpy": _installed("numpy"),
        "model_profile": DEFAULT_MODEL_PROFILE.profile_id,
        "detection_model": DEFAULT_MODEL_PROFILE.detection_model,
        "recognition_model": DEFAULT_MODEL_PROFILE.recognition_model,
        "model_source": "Bundled from official PaddleOCR model source selected by PaddleX 3.7.2",
        "model_sha256": {
            DEFAULT_MODEL_PROFILE.detection_model: index.get(DEFAULT_MODEL_PROFILE.detection_model, {}).get("sha256"),
            DEFAULT_MODEL_PROFILE.recognition_model: index.get(DEFAULT_MODEL_PROFILE.recognition_model, {}).get("sha256"),
        },
        "build_date": args.build_date.strip() or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "commit": args.commit.strip() or _git_commit(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
