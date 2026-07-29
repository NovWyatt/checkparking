from __future__ import annotations

"""Controlled PaddleOCR pool experiment; never changes the app default guard."""

import argparse
import ctypes
import json
import multiprocessing as mp
import os
import queue
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("CHECK_VEHICLE_DISABLE_ONNX_DETECTOR", "1")

from check_vehicle_ocr import paddle_ocr_engine as paddle_module
from check_vehicle_ocr.models import OcrAttempt
from check_vehicle_ocr.paddle_ocr_engine import PaddleOCR, PaddleOcrEngine
from check_vehicle_ocr.processor import process_image


class IndependentPaddleEngine:
    """Private benchmark wrapper around a distinct PaddleOCR predictor."""

    def __init__(self):
        if PaddleOCR is None:
            raise RuntimeError("PaddleOCR không khả dụng.")
        detection_model, recognition_model = paddle_module.current_model_selection()
        model_dirs = paddle_module._bundled_model_dirs(detection_model, recognition_model)
        self.ocr = PaddleOCR(
            text_detection_model_name=detection_model,
            text_detection_model_dir=model_dirs.get(detection_model),
            text_recognition_model_name=recognition_model,
            text_recognition_model_dir=model_dirs.get(recognition_model),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_det_limit_side_len=768,
            text_det_limit_type="min",
            text_rec_score_thresh=0.1,
        )

    def read_plate_regions_batch(self, crops_bgr: list[np.ndarray], **kwargs):
        valid = [(index, cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)) for index, crop in enumerate(crops_bgr) if crop.size]
        output = [[] for _crop in crops_bgr]
        if not valid:
            return output
        results = self.ocr.predict([image for _index, image in valid], **paddle_module._predict_kwargs(kwargs.get("detector_limit_side_len"), kwargs.get("detector_limit_type")))
        for (index, _image), result in zip(valid, results or [], strict=False):
            output[index] = paddle_module._region_attempts_from_result([result])
        return output

    def read_plate_regions(self, crop_bgr, **kwargs):
        return self.read_plate_regions_batch([crop_bgr], **kwargs)[0]


class PeakMonitor:
    def __init__(self):
        self.peak_mb = _working_set_mb()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_args):
        self._stop.set()
        self._thread.join(timeout=1)
        self.peak_mb = max(self.peak_mb, _working_set_mb())

    def _run(self):
        while not self._stop.wait(0.05):
            self.peak_mb = max(self.peak_mb, _working_set_mb())


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
    process = get_process()
    if get_memory(process, ctypes.byref(counters), counters.cb):
        return counters.WorkingSetSize / (1024 * 1024)
    return 0.0


def _available_memory_mb() -> float:
    if os.name != "nt":
        return 0.0

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    status_ex = ctypes.windll.kernel32.GlobalMemoryStatusEx
    status_ex.argtypes = [ctypes.c_void_p]
    status_ex.restype = ctypes.c_int
    if status_ex(ctypes.byref(status)):
        return status.ullAvailPhys / (1024 * 1024)
    return 0.0


def _make_images(root: Path, count: int) -> list[Path]:
    paths = []
    for index in range(count):
        path = root / f"sample_{index:02d}.jpg"
        image = Image.new("RGB", (900, 520), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((290, 250, 610, 330), fill="white", outline="black", width=4)
        try:
            font = ImageFont.truetype("arial.ttf", 52)
        except Exception:
            font = ImageFont.load_default()
        draw.text((330, 263), "30A-123.45", fill="black", font=font)
        image.save(path)
        paths.append(path)
    return paths


def _plates(result) -> list[str]:
    return sorted(plate.normalized_text for plate in result.plates if plate.readable and plate.normalized_text)


def _run_with_engines(paths: list[Path], engines: list[object], crop_root: Path) -> list[list[str]]:
    def task(index_path):
        index, path = index_path
        result = process_image(path, crop_root, engines[index % len(engines)], blur_threshold=10, confidence_threshold=20)
        return _plates(result)

    if len(engines) == 1:
        return [task(item) for item in enumerate(paths)]
    with ThreadPoolExecutor(max_workers=len(engines), thread_name_prefix="paddle_pool_benchmark") as executor:
        return list(executor.map(task, enumerate(paths)))


def _run_shared(paths: list[Path], root: Path) -> dict[str, object]:
    started = time.perf_counter()
    engine = PaddleOcrEngine(20)
    if not engine.available:
        raise RuntimeError(engine.reason)
    cold = time.perf_counter() - started
    with PeakMonitor() as memory:
        batch_started = time.perf_counter()
        plates = _run_with_engines(paths, [engine], root / "shared_crops")
        elapsed = time.perf_counter() - batch_started
    return _result(cold, elapsed, memory.peak_mb, 1, plates)


def _run_two_engines(paths: list[Path], root: Path) -> dict[str, object]:
    started = time.perf_counter()
    engines = [IndependentPaddleEngine(), IndependentPaddleEngine()]
    cold = time.perf_counter() - started
    with PeakMonitor() as memory:
        batch_started = time.perf_counter()
        plates = _run_with_engines(paths, engines, root / "two_engine_crops")
        elapsed = time.perf_counter() - batch_started
    return _result(cold, elapsed, memory.peak_mb, 2, plates)


def _scenario_worker(kind: str, paths: list[str], crop_root: str, result_queue) -> None:
    try:
        resolved_paths = [Path(path) for path in paths]
        if kind == "shared":
            result = _run_shared(resolved_paths, Path(crop_root))
        elif kind == "two_engines":
            result = _run_two_engines(resolved_paths, Path(crop_root))
        else:
            raise ValueError(f"Scenario không hợp lệ: {kind}")
        result_queue.put({"ok": True, "result": result})
    except Exception as exc:
        result_queue.put({"ok": False, "error": str(exc)})


def _run_isolated_scenario(kind: str, paths: list[Path], root: Path) -> dict[str, object]:
    context = mp.get_context("spawn")
    output = context.Queue()
    process = context.Process(target=_scenario_worker, args=(kind, [str(path) for path in paths], str(root), output))
    process.start()
    try:
        message = output.get(timeout=240)
    finally:
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
    if not message.get("ok"):
        raise RuntimeError(str(message.get("error")))
    return message["result"]


def _child_worker(group_index: int, paths: list[str], crop_root: str, result_queue) -> None:
    try:
        started = time.perf_counter()
        engine = IndependentPaddleEngine()
        cold = time.perf_counter() - started
        with PeakMonitor() as memory:
            batch_started = time.perf_counter()
            plates = _run_with_engines([Path(path) for path in paths], [engine], Path(crop_root))
            elapsed = time.perf_counter() - batch_started
        result_queue.put({"ok": True, "group_index": group_index, "cold": cold, "elapsed": elapsed, "peak_mb": memory.peak_mb, "plates": plates})
    except Exception as exc:
        result_queue.put({"ok": False, "group_index": group_index, "error": str(exc)})


def _run_two_processes(paths: list[Path], root: Path) -> dict[str, object]:
    context = mp.get_context("spawn")
    output = context.Queue()
    groups = [paths[::2], paths[1::2]]
    processes = [context.Process(target=_child_worker, args=(index, [str(path) for path in group], str(root / f"process_{index}_crops"), output)) for index, group in enumerate(groups)]
    started = time.perf_counter()
    for process in processes:
        process.start()
    messages = []
    try:
        for _ in processes:
            messages.append(output.get(timeout=240))
    finally:
        for process in processes:
            process.join(timeout=10)
            if process.is_alive():
                process.terminate()
    if not all(message.get("ok") for message in messages):
        raise RuntimeError("; ".join(str(message.get("error")) for message in messages if not message.get("ok")))
    elapsed = time.perf_counter() - started
    ordered = [None] * len(paths)
    for message in messages:
        group_index = int(message["group_index"])
        for local_index, plates in enumerate(message["plates"]):
            ordered[group_index + local_index * 2] = plates
    return _result(max(float(message["cold"]) for message in messages), elapsed, sum(float(message["peak_mb"]) for message in messages), 2, ordered)


def _result(cold: float, elapsed: float, peak_mb: float, engines: int, plates: list[list[str]]) -> dict[str, object]:
    return {
        "cold_init_seconds": cold,
        "batch_seconds": elapsed,
        "images_per_minute": len(plates) / elapsed * 60.0 if elapsed else 0.0,
        "peak_working_set_mb": peak_mb,
        "engine_count": engines,
        "errors": 0,
        "plates": plates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force-30", action="store_true", help="Chạy batch 30 dù RAM khả dụng thấp.")
    args = parser.parse_args()
    available_memory = _available_memory_mb()
    sizes = [10]
    if args.force_30 or available_memory == 0 or available_memory >= 6000:
        sizes.append(30)
    report: dict[str, object] = {"available_memory_mb_before": available_memory, "batches": {}, "notes": []}
    with tempfile.TemporaryDirectory(prefix="paddle_pool_benchmark_") as temporary:
        root = Path(temporary)
        paths = _make_images(root, max(sizes))
        for size in sizes:
            subset = paths[:size]
            # Each engine scenario starts in a new process so its cold-init
            # measurement is not warmed by a previous scenario in this run.
            baseline = _run_isolated_scenario("shared", subset, root / f"batch_{size}" / "shared")
            two_engines = _run_isolated_scenario("two_engines", subset, root / f"batch_{size}" / "two_engines")
            two_processes = _run_two_processes(subset, root / f"batch_{size}")
            baseline_plates = baseline["plates"]
            for result in (two_engines, two_processes):
                result["matches_baseline"] = result["plates"] == baseline_plates
                result.pop("plates", None)
            baseline.pop("plates", None)
            report["batches"][str(size)] = {"shared_one_worker": baseline, "two_independent_engines": two_engines, "two_processes": two_processes}
    if 30 not in sizes:
        report["notes"].append("Batch 30 bị bỏ qua vì RAM khả dụng dưới 6 GB.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # PowerShell hosts can still expose a legacy console code page.  The
    # persisted report remains UTF-8; ASCII console JSON keeps this benchmark
    # deterministic instead of failing after all scenarios have completed.
    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
