from __future__ import annotations

import sys
import tempfile
import os
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.app import CheckVehicleApp


def main() -> int:
    with tempfile.TemporaryDirectory() as appdata:
        previous_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = appdata
        app = CheckVehicleApp()
        try:
            app.update_idletasks()
            assert app.minsize()[0] <= 1024 and app.minsize()[1] <= 640
            assert set(app.shell.pages) == {"scan"}
            assert app.telegram_notifier is None and app.provider_refresh_button is None and app.update_check_button is None
            assert str(app.local_ocr_workers_spin.cget("state")) == "disabled"
            assert "một inference worker" in app.local_ocr_hint_var.get()
            app.engine_var.set("Local OCR")
            app.update_idletasks()
            assert str(app.local_ocr_workers_spin.cget("state")) == "normal"
            app.engine_var.set("PaddleOCR Local")
            for page in ("scan", "session", "review", "export", "providers", "telegram", "updates", "settings"):
                app.show_page(page)
                app.update_idletasks()
                assert app.shell.pages[page].winfo_exists()
            assert app.crop_preview_label.winfo_exists()
            original_theme = app.dark_mode_var.get()
            app.dark_mode_var.set(not original_theme)
            app._on_theme_toggle()
            app.update_idletasks()
            app.dark_mode_var.set(original_theme)
            app._on_theme_toggle()
            for scale in (1.25, 1.5):
                app.tk.call("tk", "scaling", scale)
                app.update_idletasks()
            app.tk.call("tk", "scaling", 1.0)
            assert str(app.start_button.cget("state")) == "disabled"
            with tempfile.TemporaryDirectory() as temporary:
                image_path = Path(temporary) / "input.jpg"
                Image.new("RGB", (80, 40), "white").save(image_path)
                app._add_paths([image_path])
                app.update_idletasks()
                assert str(app.start_button.cget("state")) == "normal"
                app._apply_progress_snapshot(
                    {
                        "status": "RUNNING",
                        "total": 4,
                        "completed": 2,
                        "percent": 50,
                        "elapsed_seconds": 10,
                        "images_per_minute": 12,
                        "eta_seconds": 10,
                        "active_workers": {"local_ocr": 1},
                        "configured_workers": {"image": 2, "local_ocr": 1, "api": 2},
                        "current_files": ["input.jpg"],
                        "succeeded": 1,
                        "needs_review": 1,
                        "failed": 0,
                    },
                    force=True,
                )
                assert "2/4" in app.progress_primary_var.get() and "ETA" in app.progress_timing_var.get()
                app.clear_all()
                assert str(app.start_button.cget("state")) == "disabled"
        finally:
            app.destroy()
            if previous_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = previous_appdata
    print("ui_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
