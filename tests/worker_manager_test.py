from __future__ import annotations

import sys
import threading
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.services.worker_manager import WorkerManager, WorkerSettings


def _measure(engine_mode: str, image_workers: int, local_workers: int, api_workers: int, expected: int) -> int:
    manager = WorkerManager(
        WorkerSettings(
            mode="MANUAL",
            image_workers=image_workers,
            local_ocr_workers=local_workers,
            api_workers=api_workers,
            queue_capacity=16,
        ),
        engine_mode,
    )
    active = 0
    maximum = 0
    lock = threading.Lock()
    barrier = threading.Barrier(expected)

    def infer(value: int) -> int:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        try:
            if value < expected:
                barrier.wait(timeout=2)
            time.sleep(0.02)
            return value
        finally:
            with lock:
                active -= 1

    values = list(range(max(4, expected)))
    results = manager.run_pipeline(values, lambda value: value, infer)
    assert [result for result in results if result is not None] == values
    return maximum


def _measure_preparation(image_workers: int, expected: int) -> int:
    manager = WorkerManager(
        WorkerSettings(mode="MANUAL", image_workers=image_workers, local_ocr_workers=1, api_workers=1, queue_capacity=16),
        "PaddleOCR Local",
    )
    active = 0
    maximum = 0
    lock = threading.Lock()
    barrier = threading.Barrier(expected)

    def prepare(value: int) -> int:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        try:
            barrier.wait(timeout=2)
            return value
        finally:
            with lock:
                active -= 1

    assert manager.run_pipeline(list(range(expected)), prepare, lambda value: value) == list(range(expected))
    return maximum


def _assert_stop_keeps_inflight_result() -> None:
    stop_event = threading.Event()
    manager = WorkerManager(
        WorkerSettings(mode="MANUAL", image_workers=1, local_ocr_workers=1, api_workers=1, queue_capacity=2),
        "PaddleOCR Local",
        stop_event,
    )
    inference_started = threading.Event()
    allow_finish = threading.Event()
    holder: dict[str, list[int | None]] = {}
    finished: list[int] = []

    def infer(value: int) -> int:
        inference_started.set()
        assert allow_finish.wait(timeout=2.0)
        return value * 10

    thread = threading.Thread(
        target=lambda: holder.setdefault(
            "results",
            manager.run_pipeline(
                [1, 2],
                lambda value: value,
                infer,
                on_finished=lambda item, result, _pool: finished.append(item.index) if not isinstance(result, Exception) else None,
            ),
        )
    )
    thread.start()
    assert inference_started.wait(timeout=2.0)
    manager.stop()
    allow_finish.set()
    thread.join(timeout=3.0)
    assert not thread.is_alive()
    assert holder["results"] == [10, None]
    assert finished == [0]


def main() -> int:
    assert _measure_preparation(1, 1) == 1
    assert _measure_preparation(2, 2) == 2
    assert _measure_preparation(4, 4) == 4
    assert _measure("Local OCR", 1, 1, 1, 1) == 1
    assert _measure("Local OCR", 2, 2, 1, 2) == 2
    assert _measure("Local OCR", 4, 4, 1, 4) == 4

    # PaddleOCR remains guarded despite a manual request for four OCR workers.
    assert _measure("PaddleOCR Local", 4, 4, 4, 1) == 1
    assert _measure("PaddleOCR + AI Review", 4, 4, 4, 1) == 1
    assert _measure("OpenAI Compatible", 4, 1, 3, 3) == 3

    manager = WorkerManager(WorkerSettings(mode="MANUAL", image_workers=2, local_ocr_workers=2, api_workers=1, queue_capacity=4), "Local OCR")
    finished: list[tuple[int, bool, str]] = []
    results = manager.run_pipeline(
        [0, 1, 2],
        lambda value: value,
        lambda value: (_ for _ in ()).throw(ValueError("expected")) if value == 1 else value * 2,
        on_finished=lambda item, result, pool: finished.append((item.index, isinstance(result, Exception), pool)),
    )
    assert results == [0, None, 4]
    assert sorted(finished) == [(0, False, "local_ocr"), (1, True, "local_ocr"), (2, False, "local_ocr")]
    _assert_stop_keeps_inflight_result()
    print("worker_manager_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
