from __future__ import annotations

import os
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.models import ExpectedPlateCount, ImageResult, PlateCandidate
from check_vehicle_ocr.plate_formatting import PlateType
from check_vehicle_ocr.services.ocr_process import (
    OcrProcessCancelled,
    OcrProcessClient,
    OcrProcessCrashed,
    OcrProcessStartupError,
    OcrProcessTask,
)


def _fake_worker(request_queue, result_queue) -> None:
    result_queue.put({"kind": "ready", "init_count": 1, "init_seconds": 0.001})
    while True:
        message = request_queue.get()
        if message is None or message.get("kind") == "shutdown":
            result_queue.put({"kind": "stopped"})
            return
        task = message["task"]
        if task.mode == "crash":
            os._exit(17)
        if task.mode == "slow":
            time.sleep(0.3)
        plate = PlateCandidate(
            bbox=(1, 2, 30, 10),
            score=95.0,
            text=f"59X1-{int(task.request_id):05d}",
            confidence=95.0,
            readable=True,
        )
        result = ImageResult(
            image_path=task.image_path,
            status="OK",
            reason="fake",
            plates=[plate],
        )
        result_queue.put(
            {
                "kind": "result",
                "request_id": task.request_id,
                "result": result,
                "timing_ms": 1.0,
                "error": "",
                "ocr_text": plate.text,
                "confidence": plate.confidence,
                "bboxes": [plate.bbox],
                "candidates": [plate.text],
            }
        )


def _dead_on_start_worker(_request_queue, _result_queue) -> None:
    os._exit(23)


def _task(root: Path, request_id: int, *, mode: str = "fast") -> OcrProcessTask:
    return OcrProcessTask(
        request_id=str(request_id),
        image_path=root / f"{request_id}.jpg",
        crop_dir=root / "crops",
        mode=mode,
        plate_type=PlateType.MOTORCYCLE,
        expected_plate_count=ExpectedPlateCount.ONE,
        blur_threshold=80.0,
        confidence_threshold=25.0,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ocr_process_test_") as temporary:
        root = Path(temporary)
        client = OcrProcessClient(worker_target=_fake_worker, queue_capacity=2, startup_timeout=10.0)
        client.start()
        first_pid = client.process_pid
        assert first_pid > 0
        assert client.init_count == 1
        assert client.is_alive

        outcomes = [client.process(_task(root, index), timeout=5.0) for index in range(3)]
        assert [outcome.request_id for outcome in outcomes] == ["0", "1", "2"]
        assert [outcome.ocr_text for outcome in outcomes] == ["59X1-00000", "59X1-00001", "59X1-00002"]
        assert all(outcome.result is not None and outcome.result.status == "OK" for outcome in outcomes)
        assert client.init_count == 1

        client.cancel_pending()
        try:
            client.process(_task(root, 3), timeout=1.0)
        except OcrProcessCancelled:
            pass
        else:
            raise AssertionError("Task mới phải bị bỏ sau khi batch yêu cầu dừng.")
        client.resume()
        assert client.process(_task(root, 4), timeout=5.0).request_id == "4"

        try:
            restart_count = client.automatic_restart_count
        except BaseException:
            client.close(timeout=5.0)
            raise
        assert restart_count == 0
        client.restart_after_crash()
        assert client.automatic_restart_count == 1
        assert client.is_alive
        try:
            client.restart_after_crash()
        except OcrProcessStartupError as exc:
            assert "giới hạn" in str(exc).lower()
        else:
            raise AssertionError("Mỗi batch chỉ được tự khởi động lại công cụ nhận diện một lần.")
        client.resume()
        assert client.automatic_restart_count == 0

        try:
            client.process(_task(root, 5, mode="crash"), timeout=5.0)
        except OcrProcessCrashed:
            pass
        else:
            raise AssertionError("Process crash phải được báo về parent thay vì làm app treo.")
        assert not client.is_alive

        client.restart()
        assert client.is_alive
        assert client.process_pid != first_pid
        assert client.init_count == 1
        assert client.process(_task(root, 6), timeout=5.0).request_id == "6"

        final_pid = client.process_pid
        client.close(timeout=5.0)
        assert not client.is_alive
        assert not client.used_terminate_fallback
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                os.kill(final_pid, 0)
            except OSError:
                break
            time.sleep(0.02)
        else:
            raise AssertionError("OCR subprocess còn tồn tại sau app close.")

        broken = OcrProcessClient(worker_target=_dead_on_start_worker, startup_timeout=2.0)
        try:
            broken.start()
        except OcrProcessStartupError:
            pass
        else:
            raise AssertionError("Process chết trước ready phải tạo startup error.")
        assert not broken.is_alive
        assert broken.process_pid == 0

        closing = OcrProcessClient(worker_target=_fake_worker, startup_timeout=5.0)
        closing.start()
        close_results = []
        close_errors: list[BaseException] = []

        def process_while_closing() -> None:
            try:
                close_results.append(closing.process(_task(root, 7, mode="slow"), timeout=3.0))
            except BaseException as exc:
                close_errors.append(exc)

        inflight = threading.Thread(target=process_while_closing)
        inflight.start()
        time.sleep(0.1)
        closing.close(timeout=2.0)
        inflight.join(timeout=2.0)
        assert not inflight.is_alive()
        assert not close_errors, close_errors
        assert [outcome.request_id for outcome in close_results] == ["7"]
        assert not closing.is_alive and not closing.used_terminate_fallback

    print("ocr_process_worker_test OK")
    return 0


if __name__ == "__main__":
    import multiprocessing as mp

    mp.freeze_support()
    raise SystemExit(main())
