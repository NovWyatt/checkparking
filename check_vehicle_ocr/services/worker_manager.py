from __future__ import annotations

import os
import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")
P = TypeVar("P")
R = TypeVar("R")


@dataclass(frozen=True)
class WorkerSettings:
    """Independent limits for file preparation, local OCR, and remote APIs."""

    mode: str = "AUTO"
    image_workers: int = 0
    local_ocr_workers: int = 1
    api_workers: int = 2
    queue_capacity: int = 32

    def resolved(self, engine_mode: str) -> "WorkerSettings":
        cpu = max(1, os.cpu_count() or 1)
        if self.mode.upper() == "AUTO":
            image_workers = min(4, cpu)
            api_workers = min(4, max(1, cpu // 2))
            local_ocr_workers = min(2, max(1, cpu // 2))
        else:
            image_workers = max(1, self.image_workers)
            api_workers = max(1, self.api_workers)
            local_ocr_workers = max(1, self.local_ocr_workers)

        # A PaddleOCR engine contains one shared predictor.  Its calls remain
        # serialized unless an independently benchmarked engine pool is added.
        if engine_mode in {"PaddleOCR Local", "PaddleOCR + AI Review"}:
            local_ocr_workers = 1

        return WorkerSettings(
            mode=self.mode.upper(),
            image_workers=image_workers,
            local_ocr_workers=local_ocr_workers,
            api_workers=api_workers,
            queue_capacity=max(1, self.queue_capacity),
        )


@dataclass(frozen=True)
class WorkItem(Generic[T]):
    index: int
    value: T


class WorkerManager:
    """A bounded two-stage worker pipeline.

    The preparation pool may decode/validate multiple images in parallel.  The
    inference pool is independent: one worker for shared PaddleOCR, a bounded
    local pool for other local engines, or the configured API pool for remote
    providers.  Callbacks never touch Tkinter; callers forward their events to
    the UI queue.
    """

    API_ENGINES = frozenset({"GPT Vision", "Gemini Vision", "Plate Recognizer", "OpenAI Compatible"})

    def __init__(self, settings: WorkerSettings, engine_mode: str, stop_event: threading.Event | None = None):
        self.settings = settings.resolved(engine_mode)
        self.engine_mode = engine_mode
        self.stop_event = stop_event or threading.Event()

    @property
    def pool_name(self) -> str:
        return "api" if self.engine_mode in self.API_ENGINES else "local_ocr"

    @property
    def inference_workers(self) -> int:
        return self.settings.api_workers if self.pool_name == "api" else self.settings.local_ocr_workers

    @property
    def configured_workers(self) -> dict[str, int]:
        return {
            "image": self.settings.image_workers,
            "local_ocr": self.settings.local_ocr_workers,
            "api": self.settings.api_workers,
        }

    def stop(self) -> None:
        self.stop_event.set()

    def run_pipeline(
        self,
        items: list[T],
        prepare: Callable[[T], P],
        infer: Callable[[P], R],
        *,
        on_started: Callable[[WorkItem[T], str], None] | None = None,
        on_finished: Callable[[WorkItem[T], R | Exception, str], None] | None = None,
    ) -> list[R | None]:
        """Run preparation and inference without serial ``future.result`` calls.

        Output indices always match the input.  Individual errors are supplied
        to ``on_finished`` and do not abort remaining images.  Only a bounded
        number of preparation/inference payloads are retained at one time.
        """

        results: list[R | None] = [None] * len(items)
        if not items:
            return results

        next_index = 0
        prepared: list[tuple[WorkItem[T], P]] = []
        preparing: dict[Future[P], WorkItem[T]] = {}
        inferring: dict[Future[R], WorkItem[T]] = {}
        capacity = self.settings.queue_capacity

        def submit_preparation(executor: ThreadPoolExecutor) -> None:
            nonlocal next_index
            while (
                not self.stop_event.is_set()
                and next_index < len(items)
                and len(preparing) < self.settings.image_workers
                and len(prepared) + len(inferring) < capacity
            ):
                item = WorkItem(next_index, items[next_index])
                next_index += 1
                preparing[executor.submit(prepare, item.value)] = item

        def submit_inference(executor: ThreadPoolExecutor) -> None:
            while not self.stop_event.is_set() and prepared and len(inferring) < self.inference_workers:
                item, payload = prepared.pop(0)
                if on_started:
                    on_started(item, self.pool_name)
                inferring[executor.submit(infer, payload)] = item

        with ThreadPoolExecutor(max_workers=self.settings.image_workers, thread_name_prefix="check_vehicle_image") as image_pool:
            with ThreadPoolExecutor(max_workers=self.inference_workers, thread_name_prefix=f"check_vehicle_{self.pool_name}") as infer_pool:
                submit_preparation(image_pool)
                while preparing or prepared or inferring:
                    if self.stop_event.is_set():
                        for future in [*preparing, *inferring]:
                            future.cancel()
                        break

                    submit_inference(infer_pool)
                    submit_preparation(image_pool)

                    futures = [*preparing, *inferring]
                    if not futures:
                        continue
                    done, _pending = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        item = preparing.pop(future, None)
                        if item is not None:
                            try:
                                prepared.append((item, future.result()))
                            except Exception as exc:
                                if on_started:
                                    on_started(item, "image")
                                if on_finished:
                                    on_finished(item, exc, "image")
                            continue

                        item = inferring.pop(future)
                        try:
                            result = future.result()
                        except Exception as exc:
                            if on_finished:
                                on_finished(item, exc, self.pool_name)
                        else:
                            results[item.index] = result
                            if on_finished:
                                on_finished(item, result, self.pool_name)

        return results
