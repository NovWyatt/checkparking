from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.app import CheckVehicleApp, PERFORMANCE_PRESET_LABELS
from check_vehicle_ocr.config import migrate_settings
from check_vehicle_ocr.runtime_manager import RuntimeStagingReport
from check_vehicle_ocr.update_center import PaddleRelease


def _widget_texts(widget) -> list[str]:
    texts: list[str] = []
    try:
        value = widget.cget("text")
    except Exception:
        value = ""
    if isinstance(value, str) and value:
        texts.append(value)
    for child in widget.winfo_children():
        texts.extend(_widget_texts(child))
    return texts


def _pump(app: CheckVehicleApp, predicate) -> None:
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        app.update()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for UI event")


def main() -> int:
    migrated = migrate_settings({"engine": "PaddleOCR Local", "worker_count": 1, "api_workers": 1})
    assert migrated["recognition_mode"] == "local" and migrated["performance_preset"] == "LOW_MEMORY"
    migrated_online = migrate_settings({"engine": "OpenAI Compatible", "image_workers": 4, "api_workers": 4})
    assert migrated_online["recognition_mode"] == "online" and migrated_online["performance_preset"] == "FAST"
    migrated_tesseract = migrate_settings({"engine": "Local OCR"})
    assert migrated_tesseract["recognition_mode"] == "local" and migrated_tesseract["tesseract_fallback_enabled"] is True

    with tempfile.TemporaryDirectory() as appdata:
        previous_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = appdata
        app = CheckVehicleApp()
        try:
            scan = app.shell.pages["scan"]
            assert list(app.shell.nav_buttons) == ["scan", "results", "settings"]
            texts = "\n".join(_widget_texts(scan))
            assert "Engine" not in texts and "AI Providers" not in texts and "Worker ảnh" not in texts
            assert "Cục bộ — Khuyên dùng" in texts and "cách nhận diện" in texts

            app.performance_preset_var.set(PERFORMANCE_PRESET_LABELS["LOW_MEMORY"])
            assert app.worker_mode_var.get() == "MANUAL"
            assert (app.image_workers_var.get(), app.local_ocr_workers_var.get(), app.api_workers_var.get()) == (1, 1, 1)
            app.performance_preset_var.set(PERFORMANCE_PRESET_LABELS["FAST"])
            assert app.local_ocr_workers_var.get() == 1 and app.image_workers_var.get() >= 1 and app.api_workers_var.get() >= 1
            app.performance_preset_var.set(PERFORMANCE_PRESET_LABELS["AUTO"])
            assert app.worker_mode_var.get() == "AUTO" and app.local_ocr_workers_var.get() == 1

            app.recognition_mode_var.set("online")
            assert "Cần cấu hình" in app.ai_config_warning_var.get()
            app.start_processing()
            assert app.worker is None
            app.recognition_mode_var.set("local")
            assert app.engine_var.get() == "PaddleOCR Local" and not app.ai_config_warning_var.get()
            app.recognition_mode_var.set("local_ai_review")
            assert app.engine_var.get() == "PaddleOCR + AI Review"
            app.recognition_mode_var.set("local")

            app.show_page("results")
            assert "results" in app.shell.pages and hasattr(app, "image_tree") and hasattr(app, "plates_frame")
            app.show_settings_section("ai")
            assert app.ui_state.current_page == "settings" and app.settings_notebook is not None
            app.show_settings_section("updates")
            assert app.update_check_button is not None and app.paddle_stage_button is not None
            assert app.tesseract_fallback_enabled_var.get() is False
            with patch("check_vehicle_ocr.app.fetch_paddle_release", return_value=PaddleRelease("9.9.9", "mock://pypi", "mock://notes")):
                app.check_paddle_updates()
                _pump(app, lambda: app.current_paddle_release is not None)
            assert "9.9.9" in app.paddle_update_status_var.get()
            assert "mock://notes" in app.paddle_release_notes_var.get()
            assert str(app.paddle_stage_button.cget("state")) == "normal"
            staged = RuntimeStagingReport("9.9.9", Path(appdata) / "stage", True, "PaddleOCR 9.9.9 đã qua import, OCR synthetic, normalization và Excel smoke.", ())
            with patch.object(app.paddle_runtime_manager, "stage_and_test", return_value=staged):
                app.prepare_paddle_staging()
                _pump(app, lambda: "đã qua import" in app.paddle_update_status_var.get())

            app.event_generate("<Control-comma>")
            app.update_idletasks()
            assert app.ui_state.current_page == "settings"
        finally:
            app.destroy()
            if previous_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = previous_appdata
    print("ui_simplification_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
