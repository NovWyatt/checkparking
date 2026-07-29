"""Measure the pinned PP-OCRv5/v6 profiles and optional Tesseract component.

It creates only synthetic plates and never calls an online API.  Each model
profile is instantiated in this process for an explicit warm measurement;
the report must be interpreted on the machine that generated it.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PROFILES = {
    "pp-ocrv5-mobile": ("PP-OCRv5_mobile_det", "en_PP-OCRv5_mobile_rec", ROOT / "models" / "paddleocr"),
    "pp-ocrv6-tiny": ("PP-OCRv6_tiny_det", "PP-OCRv6_tiny_rec", ROOT / "models" / "paddleocr"),
    "pp-ocrv6-small": ("PP-OCRv6_small_det", "PP-OCRv6_small_rec", ROOT / "models" / "paddleocr"),
    "pp-ocrv6-medium": ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec", ROOT / ".runtime" / "paddlex-v6-cache" / "official_models"),
}


def _working_set_mb() -> float:
    if os.name != "nt":
        return 0.0

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    get_process = ctypes.windll.kernel32.GetCurrentProcess
    get_process.restype = ctypes.c_void_p
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    get_memory.restype = ctypes.c_int
    if get_memory(get_process(), ctypes.byref(counters), counters.cb):
        return counters.WorkingSetSize / (1024 * 1024)
    return 0.0


def _synthetic_image() -> np.ndarray:
    image = Image.new("RGB", (900, 520), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((170, 185, 730, 345), fill="white", outline="black", width=6)
    try:
        font = ImageFont.truetype("arialbd.ttf", 86)
    except OSError:
        font = ImageFont.load_default()
    draw.text((265, 215), "59X112345", font=font, fill="black")
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def _model_size(root: Path, names: tuple[str, str]) -> int:
    return sum(path.stat().st_size for name in names for path in (root / name).rglob("*") if path.is_file())


def _measure_paddle(profile: str, batch_sizes: list[int]) -> dict[str, object]:
    from paddleocr import PaddleOCR

    detection, recognition, root = PROFILES[profile]
    if not (root / detection / "inference.yml").is_file() or not (root / recognition / "inference.yml").is_file():
        return {"status": "skipped", "reason": "model files unavailable"}
    before = _working_set_mb()
    started = time.perf_counter()
    engine = PaddleOCR(
        text_detection_model_name=detection,
        text_detection_model_dir=str(root / detection),
        text_recognition_model_name=recognition,
        text_recognition_model_dir=str(root / recognition),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_rec_score_thresh=0.1,
    )
    init_seconds = time.perf_counter() - started
    image = _synthetic_image()
    first_started = time.perf_counter()
    first = list(engine.predict(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))
    first_seconds = time.perf_counter() - first_started
    batches: dict[str, object] = {}
    for size in batch_sizes:
        started = time.perf_counter()
        results = [list(engine.predict(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))) for _ in range(size)]
        elapsed = time.perf_counter() - started
        batches[str(size)] = {
            "seconds": round(elapsed, 4),
            "images_per_minute": round(size / elapsed * 60.0, 2) if elapsed else 0.0,
            "result_count": sum(len(item) for item in results),
        }
    return {
        "status": "passed",
        "detection_model": detection,
        "recognition_model": recognition,
        "cold_init_seconds": round(init_seconds, 4),
        "first_inference_seconds": round(first_seconds, 4),
        "warm_batches": batches,
        "working_set_delta_mb": round(max(0.0, _working_set_mb() - before), 2),
        "package_model_bytes": _model_size(root, (detection, recognition)),
        "first_result_count": len(first),
    }


def _measure_tesseract(executable: Path, batch_sizes: list[int]) -> dict[str, object]:
    if not executable.is_file():
        return {"status": "skipped", "reason": "component executable unavailable"}
    from check_vehicle_ocr.ocr import TesseractOcrEngine

    engine = TesseractOcrEngine(executable, confidence_threshold=20)
    if not engine.available:
        return {"status": "failed", "reason": engine.reason}
    image = _synthetic_image()
    first_started = time.perf_counter()
    first = engine.read_plate(image)
    first_seconds = time.perf_counter() - first_started
    batches: dict[str, object] = {}
    for size in batch_sizes:
        started = time.perf_counter()
        attempts = [engine.read_plate(image) for _ in range(size)]
        elapsed = time.perf_counter() - started
        batches[str(size)] = {
            "seconds": round(elapsed, 4),
            "images_per_minute": round(size / elapsed * 60.0, 2) if elapsed else 0.0,
            "nonempty": sum(1 for item in attempts if item.normalized_text),
        }
    return {"status": "passed", "first_inference_seconds": round(first_seconds, 4), "first_text": first.normalized_text, "warm_batches": batches}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force-30", action="store_true")
    parser.add_argument("--tesseract-exe", type=Path)
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=tuple(PROFILES),
        help="Only benchmark the named Paddle profiles. Useful for bounded CI/manual runs.",
    )
    args = parser.parse_args()
    batch_sizes = [10, 30] if args.force_30 else [10]
    report: dict[str, object] = {"schema_version": 1, "synthetic_only": True, "profiles": {}}
    for profile in args.profiles or PROFILES:
        report["profiles"][profile] = _measure_paddle(profile, batch_sizes)
    # Tesseract's bounded multi-variant fallback is intentionally measured on
    # ten images.  Its production policy never sends every normal batch image
    # through all variants, so a 30-image all-fallback run is not representative.
    report["tesseract_5_5_3"] = _measure_tesseract(args.tesseract_exe, [10]) if args.tesseract_exe else {"status": "skipped", "reason": "no --tesseract-exe"}
    report["paddle_tesseract_fallback"] = {"status": "policy-only", "note": "Fallback runs only for an unreadable, low-confidence, ambiguous or unmatched PaddleOCR candidate; this synthetic batch did not force fallback."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
