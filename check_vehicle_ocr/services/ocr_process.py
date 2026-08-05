from __future__ import annotations

import multiprocessing as mp
import os
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import ExpectedPlateCount, ImageResult
from ..plate_formatting import PlateType


@dataclass(frozen=True)
class OcrProcessTask:
    """A small, path-backed OCR request safe for Windows ``spawn``."""

    request_id: str
    image_path: Path
    crop_dir: Path
    mode: str
    plate_type: PlateType
    expected_plate_count: ExpectedPlateCount
    blur_threshold: float
    confidence_threshold: float


@dataclass(frozen=True)
class OcrProcessOutcome:
    request_id: str
    result: ImageResult | None
    timing_ms: float
    error: str = ""
    ocr_text: str = ""
    confidence: float = 0.0
    bboxes: tuple[tuple[int, int, int, int], ...] = ()
    candidates: tuple[str, ...] = ()


class OcrProcessError(RuntimeError):
    pass


class OcrProcessStartupError(OcrProcessError):
    pass


class OcrProcessCrashed(OcrProcessError):
    pass


class OcrProcessCancelled(OcrProcessError):
    pass


def _ocr_process_main(request_queue: Any, result_queue: Any) -> None:
    """Own PaddleOCR and all native inference state inside one child process."""

    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    started = time.perf_counter()
    try:
        from ..paddle_ocr_engine import PaddleOcrEngine
        from ..processor import process_image

        engine = PaddleOcrEngine(confidence_threshold=25.0)
        if not engine.available:
            raise RuntimeError(engine.reason or "PaddleOCR chưa sẵn sàng.")
        result_queue.put(
            {
                "kind": "ready",
                "init_count": 1,
                "init_seconds": time.perf_counter() - started,
            }
        )
    except BaseException as exc:
        result_queue.put({"kind": "fatal", "error": f"{type(exc).__name__}: {exc}"})
        return

    while True:
        message = request_queue.get()
        if message is None or message.get("kind") == "shutdown":
            result_queue.put({"kind": "stopped"})
            return
        task: OcrProcessTask = message["task"]
        task_started = time.perf_counter()
        try:
            result = process_image(
                task.image_path,
                task.crop_dir,
                engine,
                task.blur_threshold,
                task.confidence_threshold,
                paddle_scan_mode=task.mode,
                selected_plate_type=task.plate_type,
                expected_plate_count=task.expected_plate_count,
            )
            readable = [plate for plate in result.plates if plate.readable and plate.final_text]
            primary = readable[0] if readable else None
            result_queue.put(
                {
                    "kind": "result",
                    "request_id": task.request_id,
                    "result": result,
                    "timing_ms": (time.perf_counter() - task_started) * 1000.0,
                    "error": "",
                    "ocr_text": primary.final_text if primary else "",
                    "confidence": float(primary.confidence or 0.0) if primary else 0.0,
                    "bboxes": [plate.bbox for plate in readable],
                    "candidates": [plate.final_text for plate in readable],
                }
            )
        except BaseException as exc:
            result_queue.put(
                {
                    "kind": "result",
                    "request_id": task.request_id,
                    "result": None,
                    "timing_ms": (time.perf_counter() - task_started) * 1000.0,
                    "error": f"{type(exc).__name__}: {exc}",
                    "ocr_text": "",
                    "confidence": 0.0,
                    "bboxes": [],
                    "candidates": [],
                }
            )


class OcrProcessClient:
    """Synchronous client for one persistent, bounded OCR subprocess."""

    def __init__(
        self,
        *,
        worker_target: Callable[[Any, Any], None] = _ocr_process_main,
        queue_capacity: int = 4,
        startup_timeout: float = 120.0,
        restart_limit: int = 1,
    ) -> None:
        self._context = mp.get_context("spawn")
        self._worker_target = worker_target
        self._queue_capacity = max(1, int(queue_capacity))
        self._startup_timeout = max(0.1, float(startup_timeout))
        self._restart_limit = max(0, int(restart_limit))
        self._request_queue: Any | None = None
        self._result_queue: Any | None = None
        self._process: Any | None = None
        self._request_lock = threading.Lock()
        self._cancelled = threading.Event()
        self.init_count = 0
        self.init_seconds = 0.0
        self._automatic_restart_count = 0
        self.used_terminate_fallback = False

    @property
    def is_alive(self) -> bool:
        return bool(self._process is not None and self._process.is_alive())

    @property
    def process_pid(self) -> int:
        return int(self._process.pid or 0) if self._process is not None else 0

    @property
    def automatic_restart_count(self) -> int:
        return self._automatic_restart_count

    def start(self) -> None:
        if self.is_alive:
            return
        if self._process is not None:
            self._process.join(timeout=0.1)
            self._process = None
        self._dispose_queues()
        self.used_terminate_fallback = False
        self._cancelled.clear()
        self._request_queue = self._context.Queue(maxsize=self._queue_capacity)
        self._result_queue = self._context.Queue(maxsize=self._queue_capacity)
        self._process = self._context.Process(
            target=self._worker_target,
            args=(self._request_queue, self._result_queue),
            name="check_vehicle_ocr_process",
        )
        self._process.start()
        deadline = time.monotonic() + self._startup_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.close(timeout=1.0)
                raise OcrProcessStartupError("Quá thời gian khởi tạo tiến trình PaddleOCR.")
            try:
                message = self._result_queue.get(timeout=min(0.1, remaining))
            except queue.Empty:
                if not self.is_alive:
                    error = self._exit_message("Tiến trình PaddleOCR dừng khi đang khởi tạo")
                    self.close(timeout=0.0)
                    raise OcrProcessStartupError(error)
                continue
            if message.get("kind") == "fatal":
                error = str(message.get("error") or "Không rõ lỗi")
                self.close(timeout=1.0)
                raise OcrProcessStartupError(f"Không thể khởi tạo PaddleOCR: {error}")
            if message.get("kind") != "ready":
                self.close(timeout=1.0)
                raise OcrProcessStartupError("Tiến trình PaddleOCR trả giao thức khởi tạo không hợp lệ.")
            self.init_count = int(message.get("init_count") or 0)
            self.init_seconds = float(message.get("init_seconds") or 0.0)
            return

    def process(self, task: OcrProcessTask, *, timeout: float = 300.0) -> OcrProcessOutcome:
        if self._cancelled.is_set():
            raise OcrProcessCancelled("Batch đã yêu cầu dừng; task OCR chưa chạy đã được bỏ.")
        self.start()
        deadline = time.monotonic() + max(0.1, float(timeout))
        with self._request_lock:
            self._put_task(task, deadline)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise OcrProcessError(f"OCR quá thời gian cho request {task.request_id}.")
                try:
                    message = self._result_queue.get(timeout=min(0.1, remaining))
                except queue.Empty:
                    if not self.is_alive:
                        raise OcrProcessCrashed(self._exit_message("Tiến trình PaddleOCR dừng bất ngờ"))
                    continue
                if message.get("kind") != "result":
                    if message.get("kind") == "fatal":
                        raise OcrProcessCrashed(str(message.get("error") or "Tiến trình PaddleOCR gặp lỗi."))
                    continue
                request_id = str(message.get("request_id") or "")
                if request_id != task.request_id:
                    raise OcrProcessError(
                        f"Sai thứ tự kết quả OCR: chờ {task.request_id}, nhận {request_id or 'trống'}."
                    )
                return OcrProcessOutcome(
                    request_id=request_id,
                    result=message.get("result"),
                    timing_ms=float(message.get("timing_ms") or 0.0),
                    error=str(message.get("error") or ""),
                    ocr_text=str(message.get("ocr_text") or ""),
                    confidence=float(message.get("confidence") or 0.0),
                    bboxes=tuple(tuple(value) for value in message.get("bboxes") or ()),
                    candidates=tuple(str(value) for value in message.get("candidates") or ()),
                )

    def _put_task(self, task: OcrProcessTask, deadline: float) -> None:
        while True:
            if self._cancelled.is_set():
                raise OcrProcessCancelled("Batch đã yêu cầu dừng; task OCR chưa chạy đã được bỏ.")
            if not self.is_alive:
                raise OcrProcessCrashed(self._exit_message("Tiến trình PaddleOCR chưa hoạt động"))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OcrProcessError(f"Không thể xếp request {task.request_id} vào queue OCR.")
            try:
                self._request_queue.put({"kind": "task", "task": task}, timeout=min(0.1, remaining))
                return
            except queue.Full:
                continue

    def cancel_pending(self) -> None:
        self._cancelled.set()

    def resume(self) -> None:
        self._cancelled.clear()
        self._automatic_restart_count = 0

    def restart(self) -> None:
        self.close(timeout=2.0)
        self.start()

    def restart_after_crash(self) -> None:
        if self._automatic_restart_count >= self._restart_limit:
            raise OcrProcessStartupError("Đã đạt giới hạn tự khởi động lại công cụ nhận diện trong batch này.")
        self._automatic_restart_count += 1
        self.restart()

    def close(self, *, timeout: float = 10.0) -> None:
        process = self._process
        if process is None:
            self._dispose_queues()
            return
        if process.is_alive() and self._request_queue is not None:
            try:
                self._request_queue.put({"kind": "shutdown"}, timeout=min(1.0, max(0.1, timeout)))
            except (queue.Full, ValueError, OSError):
                pass
        process.join(timeout=max(0.0, timeout))
        if process.is_alive():
            self.used_terminate_fallback = True
            process.terminate()
            process.join(timeout=2.0)
        self._process = None
        self._dispose_queues()

    def _dispose_queues(self) -> None:
        for value in (self._request_queue, self._result_queue):
            if value is None:
                continue
            try:
                value.close()
                value.join_thread()
            except (ValueError, OSError):
                pass
        self._request_queue = None
        self._result_queue = None

    def _exit_message(self, prefix: str) -> str:
        code = self._process.exitcode if self._process is not None else None
        return f"{prefix} (exit code {code})."


__all__ = [
    "OcrProcessCancelled",
    "OcrProcessClient",
    "OcrProcessCrashed",
    "OcrProcessError",
    "OcrProcessOutcome",
    "OcrProcessStartupError",
    "OcrProcessTask",
]
