from __future__ import annotations

import queue
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.models import BatchSession, ExpectedPlateCount, ImageResult, PlateCandidate
from check_vehicle_ocr.plate_formatting import PlateType
from check_vehicle_ocr.services.ocr_process import OcrProcessCrashed, OcrProcessError, OcrProcessOutcome, OcrProcessStartupError
from check_vehicle_ocr.services.worker_manager import WorkerSettings


class _FakeProcessClient:
    def __init__(self) -> None:
        self.start_calls = 0
        self.resume_calls = 0
        self.cancel_calls = 0
        self.close_calls = 0
        self.tasks = []
        self.init_count = 1
        self.init_seconds = 0.01

    def start(self) -> None:
        self.start_calls += 1

    def resume(self) -> None:
        self.resume_calls += 1

    def process(self, task, *, timeout: float = 300.0) -> OcrProcessOutcome:
        del timeout
        self.tasks.append(task)
        plate = PlateCandidate(
            bbox=(10, 20, 200, 70),
            score=96.0,
            text="59X112345",
            raw_text="59X112345",
            confidence=96.0,
            readable=True,
        )
        result = ImageResult(task.image_path, "OK", "fake process", plates=[plate])
        return OcrProcessOutcome(
            request_id=task.request_id,
            result=result,
            timing_ms=1.0,
            ocr_text=plate.text,
            confidence=plate.confidence,
            bboxes=(plate.bbox,),
            candidates=(plate.text,),
        )

    def cancel_pending(self) -> None:
        self.cancel_calls += 1

    def close(self, *, timeout: float = 10.0) -> None:
        del timeout
        self.close_calls += 1


class _CrashOnceProcessClient(_FakeProcessClient):
    def __init__(self) -> None:
        super().__init__()
        self.process_calls = 0
        self.restart_calls = 0

    def process(self, task, *, timeout: float = 300.0) -> OcrProcessOutcome:
        self.process_calls += 1
        if self.process_calls == 1:
            raise OcrProcessCrashed("child stopped")
        return super().process(task, timeout=timeout)

    def restart_after_crash(self) -> None:
        self.restart_calls += 1


class _RestartFailsProcessClient(_CrashOnceProcessClient):
    def restart_after_crash(self) -> None:
        self.restart_calls += 1
        raise OcrProcessStartupError("cannot restart")


class _GenericFailureProcessClient(_FakeProcessClient):
    def process(self, task, *, timeout: float = 300.0) -> OcrProcessOutcome:
        del task, timeout
        raise OcrProcessError("internal queue timeout")


class _StatusVar:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


def _task_kwargs(root: Path) -> dict[str, object]:
    return {
        "request_id": "recovery",
        "image": root / "one.jpg",
        "crop_dir": root / "crops",
        "blur_threshold": 80.0,
        "confidence_threshold": 25.0,
        "paddle_scan_mode": "fast",
        "selected_plate_type": PlateType.MOTORCYCLE,
        "expected_plate_count": ExpectedPlateCount.ONE,
    }


def _assert_recovery_statuses(root: Path) -> None:
    app = object.__new__(CheckVehicleApp)
    app.event_queue = queue.Queue()
    app.stop_event = threading.Event()
    app.worker_manager = None
    client = _CrashOnceProcessClient()
    result = CheckVehicleApp._run_paddle_process_task(app, client, **_task_kwargs(root))
    assert result.primary_plate is not None
    assert client.process_calls == 2 and client.restart_calls == 1
    assert list(app.event_queue.queue) == [
        ("ocr_tool_status", "restarting"),
        ("ocr_tool_status", "ready"),
    ]

    stopped: list[bool] = []
    app.event_queue = queue.Queue()
    app.stop_event.clear()
    app.worker_manager = type("Manager", (), {"stop": lambda _self: stopped.append(True)})()
    broken = _RestartFailsProcessClient()
    try:
        CheckVehicleApp._run_paddle_process_task(app, broken, **_task_kwargs(root))
    except OcrProcessError as exc:
        assert "công cụ nhận diện" in str(exc).lower()
        assert "process" not in str(exc).lower()
    else:
        raise AssertionError("Restart thất bại phải dừng batch có kiểm soát.")
    assert app.stop_event.is_set() and stopped == [True]
    assert list(app.event_queue.queue) == [
        ("ocr_tool_status", "restarting"),
        ("ocr_tool_status", "failed"),
    ]

    app.event_queue = queue.Queue()
    app.stop_event.clear()
    stopped.clear()
    generic_failure = _GenericFailureProcessClient()
    try:
        CheckVehicleApp._run_paddle_process_task(app, generic_failure, **_task_kwargs(root))
    except OcrProcessError as exc:
        message = str(exc).lower()
        assert "công cụ nhận diện" in message
        assert all(term not in message for term in ("process", "pipe", "queue", "spawn", "request"))
    else:
        raise AssertionError("Lỗi điều phối OCR phải dừng batch bằng thông báo thân thiện.")
    assert app.stop_event.is_set() and stopped == [True]
    assert list(app.event_queue.queue) == [("ocr_tool_status", "failed")]

    expected = {
        "initializing": "Đang chuẩn bị công cụ nhận diện…",
        "ready": "Công cụ nhận diện đã sẵn sàng",
        "restarting": "Công cụ nhận diện gặp lỗi và đang khởi động lại…",
        "failed": "Không thể khởi động lại công cụ nhận diện. Đã dừng quét an toàn.",
    }
    for state, message in expected.items():
        ui = object.__new__(CheckVehicleApp)
        ui.event_queue = queue.Queue()
        ui.event_queue.put(("ocr_tool_status", state))
        ui.status_var = _StatusVar()
        ui._log = lambda _message: None
        ui.after = lambda _delay, _callback: "after-id"
        CheckVehicleApp._drain_events(ui)
        assert ui.status_var.value == message


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ocr_process_app_") as temporary:
        root = Path(temporary)
        paths = [root / "one.jpg", root / "two.jpg"]
        for path in paths:
            Image.new("RGB", (320, 180), "white").save(path)

        app = object.__new__(CheckVehicleApp)
        app.event_queue = queue.Queue()
        app.stop_event = threading.Event()
        app.worker_manager = None
        app.batch_progress = None
        app._ocr_process_client = _FakeProcessClient()
        session = BatchSession(
            batch_id="process-batch",
            selected_plate_type=PlateType.MOTORCYCLE,
            started_at="2026-08-06T00:00:00+07:00",
            total_images=len(paths),
            expected_plate_count=ExpectedPlateCount.ONE,
        )
        settings = WorkerSettings(
            mode="MANUAL",
            image_workers=2,
            local_ocr_workers=1,
            api_workers=1,
            queue_capacity=2,
        )

        with patch.object(CheckVehicleApp, "_make_engine", side_effect=AssertionError("UI process must not create PaddleOCR")), patch(
            "check_vehicle_ocr.app.load_image", side_effect=AssertionError("Paddle task must use an image path, not serialize a decoded 4K frame")
        ):
            CheckVehicleApp._worker_process(
                app,
                paths,
                root / "output.xlsx",
                "PaddleOCR Local",
                None,
                None,
                "",
                None,
                "",
                None,
                "",
                80.0,
                35.0,
                settings,
                "fast",
                False,
                None,
                False,
                session,
            )

        client = app._ocr_process_client
        assert client.start_calls == 1 and client.resume_calls == 1
        assert sorted(task.request_id for task in client.tasks) == ["0", "1"]
        assert {task.image_path for task in client.tasks} == set(paths)
        assert all(task.mode == "fast" for task in client.tasks)
        assert all(task.plate_type is PlateType.MOTORCYCLE for task in client.tasks)
        assert all(task.expected_plate_count is ExpectedPlateCount.ONE for task in client.tasks)
        assert all(task.confidence_threshold == 25.0 for task in client.tasks)
        events = list(app.event_queue.queue)
        done = [event for event in events if event[0] == "done_scan"]
        assert len(done) == 1 and len(done[0][1]) == 2
        assert [result.primary_plate.final_text for result in done[0][1]] == ["59X1-12345", "59X1-12345"]
        _assert_recovery_statuses(root)

    print("ocr_process_app_integration_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
