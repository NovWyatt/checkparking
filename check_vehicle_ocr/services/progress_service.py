from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class BatchStatus(StrEnum):
    IDLE = "IDLE"
    PREPARING_MODEL = "PREPARING_MODEL"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class BatchProgress:
    total: int
    configured_workers: dict[str, int]
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: BatchStatus = BatchStatus.IDLE
    queued: int = 0
    active: int = 0
    completed: int = 0
    succeeded: int = 0
    needs_review: int = 0
    failed: int = 0
    cancelled: int = 0
    current_files: list[str] = field(default_factory=list)
    active_workers: dict[str, int] = field(default_factory=dict)
    started_at: float | None = None
    finished_at: float | None = None

    def preparing_model(self) -> None:
        self.status = BatchStatus.PREPARING_MODEL
        self.queued = self.total

    def start(self) -> None:
        self.status = BatchStatus.RUNNING
        self.queued = max(0, self.total - self.completed - self.active)
        self.started_at = time.monotonic()

    def request_stop(self) -> None:
        if self.status in {BatchStatus.PREPARING_MODEL, BatchStatus.RUNNING, BatchStatus.PAUSED}:
            self.status = BatchStatus.STOPPING

    @property
    def elapsed_seconds(self) -> float:
        if not self.started_at:
            return 0.0
        return max(0.0, (self.finished_at or time.monotonic()) - self.started_at)

    @property
    def images_per_minute(self) -> float:
        return self.completed / self.elapsed_seconds * 60.0 if self.elapsed_seconds >= 1.0 else 0.0

    @property
    def eta_seconds(self) -> float | None:
        if self.completed <= 0 or self.elapsed_seconds < 1.0:
            return None
        return max(0.0, (self.total - self.completed) * self.elapsed_seconds / self.completed)

    @property
    def percent(self) -> int:
        return int(min(100, max(0, round(self.completed * 100 / self.total)))) if self.total else 0

    def mark_started(self, filename: str, pool: str) -> None:
        self.queued = max(0, self.queued - 1)
        self.active += 1
        if filename not in self.current_files:
            self.current_files.append(filename)
        self.active_workers[pool] = self.active_workers.get(pool, 0) + 1

    def mark_finished(self, filename: str, pool: str, outcome: str) -> None:
        self.active = max(0, self.active - 1)
        self.completed = min(self.total, self.completed + 1)
        self.current_files = [value for value in self.current_files if value != filename]
        self.active_workers[pool] = max(0, self.active_workers.get(pool, 0) - 1)
        if outcome == "success":
            self.succeeded += 1
        elif outcome == "review":
            self.needs_review += 1
        elif outcome == "cancelled":
            self.cancelled += 1
        else:
            self.failed += 1

    def finish(self, cancelled: bool = False, fatal: bool = False) -> None:
        self.finished_at = time.monotonic()
        self.active = 0
        self.current_files.clear()
        if fatal:
            self.status = BatchStatus.FAILED
        elif cancelled:
            self.status = BatchStatus.CANCELLED
        elif self.failed:
            self.status = BatchStatus.COMPLETED_WITH_ERRORS
        else:
            self.status = BatchStatus.COMPLETED

    def snapshot(self) -> dict[str, object]:
        """Return UI-safe data without recursive ``asdict``/``deepcopy`` work."""
        elapsed = self.elapsed_seconds
        rate = self.completed / elapsed * 60.0 if elapsed >= 1.0 else 0.0
        eta = max(0.0, (self.total - self.completed) * elapsed / self.completed) if self.completed and elapsed >= 1.0 else None
        return {
            "batch_id": self.batch_id,
            "status": self.status.value,
            "total": self.total,
            "queued": self.queued,
            "active": self.active,
            "completed": self.completed,
            "succeeded": self.succeeded,
            "needs_review": self.needs_review,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "current_files": list(self.current_files),
            "active_workers": dict(self.active_workers),
            "configured_workers": dict(self.configured_workers),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": elapsed,
            "images_per_minute": rate,
            "eta_seconds": eta,
            "percent": self.percent,
        }
