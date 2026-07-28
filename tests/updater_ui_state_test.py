from __future__ import annotations

import sys
import time
import os
import tempfile
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.updater import UpdateManifest


def _pump(app: CheckVehicleApp, predicate) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        app.update()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for UI worker event")


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        previous_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = temporary
        app = CheckVehicleApp()
        try:
            app.show_page("updates")
            app.update_source_mode_var.set("Manifest tùy chỉnh")
            app.update_manifest_url_var.set("")
            app.check_for_updates()
            assert "Chưa cấu hình" in app.update_status_var.get()
            manifest = UpdateManifest("9.9.9", "Ghi chú release mock", "https://example.invalid/app", "a" * 64)
            app.update_manifest_url_var.set("https://example.invalid/mock-manifest.json")
            with patch("check_vehicle_ocr.app.fetch_manifest", return_value=manifest):
                app.check_for_updates()
                _pump(app, lambda: app.current_update_manifest is not None)
            assert app.current_update_manifest == manifest and "9.9.9" in app.update_status_var.get()
            assert app.update_check_button is not None and app.update_download_button is None
            assert str(app.update_check_button.cget("state")) == "normal"
            assert app.update_check_button.cget("text") == "Tải bản cập nhật"
            destination = Path(temporary) / "mock-update.download"
            with patch("check_vehicle_ocr.app.download_verified", return_value=destination):
                app.download_update()
                _pump(app, lambda: "Đã tải và xác minh" in app.update_status_var.get())
            assert "Đã tải và xác minh" in app.update_status_var.get() and app.update_check_button.cget("text") == "Cài khi đóng app"
        finally:
            app.destroy()
            if previous_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = previous_appdata
    print("updater_ui_state_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
