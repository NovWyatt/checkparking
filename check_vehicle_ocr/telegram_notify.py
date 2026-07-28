from __future__ import annotations

import json
import queue
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class TelegramSettings:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    notify_start: bool = True
    notify_progress: bool = True
    notify_complete: bool = True
    notify_error: bool = True
    progress_percent_step: int = 10
    minimum_interval_seconds: int = 60
    mask_plate_number: bool = False


class TelegramNotifier:
    def __init__(self, settings: TelegramSettings, timeout: float = 12.0):
        self.settings = settings
        self.timeout = timeout
        # ``time.monotonic()`` can be lower than a configured interval on a
        # freshly booted machine or CI runner.  ``None`` distinguishes “never
        # sent” from an actual delivery timestamp so the first operator/test
        # notification is never rate-limited by mistake.
        self.last_sent_at: float | None = None
        self.last_error = ""

    def send(self, text: str, *, force: bool = False) -> bool:
        if not self.settings.enabled or not self.settings.bot_token or not self.settings.chat_id:
            return False
        if not force and self.last_sent_at is not None and time.monotonic() - self.last_sent_at < self.settings.minimum_interval_seconds:
            return False
        body = json.dumps({"chat_id": self.settings.chat_id, "text": text}).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.settings.bot_token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("ok"):
                raise RuntimeError(str(payload.get("description") or "Telegram từ chối gửi tin"))
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
            self.last_error = str(exc)
            return False
        self.last_error = ""
        self.last_sent_at = time.monotonic()
        return True


class AsyncTelegramNotifier:
    """Best-effort Telegram delivery isolated from OCR and the Tk thread."""

    def __init__(
        self,
        settings: TelegramSettings,
        *,
        timeout: float = 8.0,
        retries: int = 1,
        on_delivery=None,
        notifier_factory=TelegramNotifier,
    ):
        self.settings = settings
        self.retries = max(0, retries)
        self.on_delivery = on_delivery
        self.notifier = notifier_factory(settings, timeout=timeout)
        self._queue: queue.Queue[tuple[str, bool] | None] = queue.Queue(maxsize=24)
        self._closed = threading.Event()
        self._worker = threading.Thread(target=self._run, name="check_vehicle_telegram", daemon=True)
        self._worker.start()

    def send_later(self, text: str, *, force: bool = False) -> bool:
        if self._closed.is_set() or not self.settings.enabled:
            return False
        try:
            self._queue.put_nowait((text, force))
        except queue.Full:
            return False
        return True

    def close(self, timeout: float = 1.5) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        self._worker.join(timeout=max(0.0, timeout))

    def _run(self) -> None:
        while not self._closed.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is None:
                return
            text, force = item
            sent = False
            for attempt in range(self.retries + 1):
                sent = self.notifier.send(text, force=force or attempt > 0)
                if sent or not self.notifier.last_error:
                    break
            if self.on_delivery:
                try:
                    self.on_delivery(sent, self.notifier.last_error)
                except Exception:
                    # Notification observers are non-critical by design.
                    pass


def mask_plate(text: str) -> str:
    value = text.strip()
    return value if len(value) <= 4 else f"{value[:2]}***{value[-2:]}"
