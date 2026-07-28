from __future__ import annotations

import queue
import os
import sys
import threading
import time
import tempfile
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.telegram_notify import AsyncTelegramNotifier, TelegramSettings


class FakeNotifier:
    calls: list[tuple[str, bool]] = []

    def __init__(self, _settings, timeout=0):
        self.last_error = ""

    def send(self, text: str, *, force: bool = False) -> bool:
        FakeNotifier.calls.append((text, force))
        return True


class LifecycleNotifier:
    instances: list["LifecycleNotifier"] = []

    def __init__(self, _settings, **_kwargs):
        self.messages: list[tuple[str, bool]] = []
        LifecycleNotifier.instances.append(self)

    def send_later(self, text: str, *, force: bool = False) -> bool:
        self.messages.append((text, force))
        return True

    def close(self, *_args):
        return None


def main() -> int:
    delivered = threading.Event()
    FakeNotifier.calls.clear()
    notifier = AsyncTelegramNotifier(
        TelegramSettings(enabled=True, bot_token="secret", chat_id="123", minimum_interval_seconds=0),
        notifier_factory=FakeNotifier,
        on_delivery=lambda sent, error: delivered.set() if sent and not error else None,
    )
    assert notifier.send_later("test", force=True)
    assert delivered.wait(2), "Async Telegram worker did not deliver fake message"
    notifier.close()
    assert FakeNotifier.calls == [("test", True)]

    with tempfile.TemporaryDirectory() as temporary:
        previous_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = temporary
        app = CheckVehicleApp()
        try:
            app.telegram_enabled_var.set(True)
            app.telegram_bot_token_var.set("secret")
            app.telegram_chat_id_var.set("123")
            app.telegram_notify_start_var.set(True)
            app.telegram_notify_progress_var.set(True)
            app.telegram_notify_complete_var.set(True)
            LifecycleNotifier.instances.clear()
            with patch("check_vehicle_ocr.app.AsyncTelegramNotifier", LifecycleNotifier):
                app._start_telegram_lifecycle(20, "PaddleOCR Local")
                app._notify_telegram_progress({"percent": 10, "completed": 2, "total": 20})
                app._notify_telegram_progress({"percent": 10, "completed": 2, "total": 20})
                app._finish_telegram_lifecycle("completed")
            messages = LifecycleNotifier.instances[-1].messages
            assert len(messages) == 3
            assert "bắt đầu" in messages[0][0] and "10%" in messages[1][0] and "hoàn tất" in messages[2][0]
        finally:
            app.destroy()
            if previous_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = previous_appdata
    print("telegram_integration_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
