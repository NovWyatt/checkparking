from __future__ import annotations

import multiprocessing as mp
import statistics
import sys
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.models import ExpectedPlateCount
from check_vehicle_ocr.plate_formatting import PlateType
from check_vehicle_ocr.services.ocr_process import OcrProcessClient, OcrProcessTask


def _slow_worker(request_queue, result_queue) -> None:
    result_queue.put({"kind": "ready", "init_count": 1, "init_seconds": 0.001})
    while True:
        message = request_queue.get()
        if message is None or message.get("kind") == "shutdown":
            result_queue.put({"kind": "stopped"})
            return
        task = message["task"]
        time.sleep(0.4)
        result_queue.put(
            {
                "kind": "result",
                "request_id": task.request_id,
                "result": None,
                "timing_ms": 400.0,
                "error": "",
                "ocr_text": "",
                "confidence": 0.0,
                "bboxes": [],
                "candidates": [],
            }
        )


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def main() -> int:
    client = OcrProcessClient(worker_target=_slow_worker, queue_capacity=1, startup_timeout=10.0)
    client.start()
    root = tk.Tk()
    root.withdraw()
    done = threading.Event()
    errors: list[BaseException] = []
    delays_ms: list[float] = []
    interval_seconds = 0.02
    previous = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="ocr_heartbeat_") as temporary:
        path = Path(temporary)
        task = OcrProcessTask(
            request_id="heartbeat",
            image_path=path / "image.jpg",
            crop_dir=path / "crops",
            mode="fast",
            plate_type=PlateType.NONE,
            expected_plate_count=ExpectedPlateCount.ONE,
            blur_threshold=80.0,
            confidence_threshold=25.0,
        )

        def run_task() -> None:
            try:
                outcome = client.process(task, timeout=5.0)
                assert outcome.request_id == "heartbeat"
            except BaseException as exc:
                errors.append(exc)
            finally:
                done.set()

        def heartbeat() -> None:
            nonlocal previous
            now = time.perf_counter()
            delays_ms.append(max(0.0, (now - previous - interval_seconds) * 1000.0))
            previous = now
            if not done.is_set():
                root.after(round(interval_seconds * 1000), heartbeat)

        def poll() -> None:
            if done.is_set():
                root.quit()
            else:
                root.after(10, poll)

        worker = threading.Thread(target=run_task, daemon=True)
        worker.start()
        root.after(round(interval_seconds * 1000), heartbeat)
        root.after(10, poll)
        root.mainloop()
        worker.join(timeout=2.0)

    root.destroy()
    client.close(timeout=5.0)
    assert not errors, errors
    assert len(delays_ms) >= 10
    assert statistics.median(delays_ms) < 50.0
    assert _percentile(delays_ms, 0.95) < 100.0
    assert max(delays_ms) < 250.0
    assert not client.is_alive and not client.used_terminate_fallback
    print("ocr_process_heartbeat_test OK")
    return 0


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
