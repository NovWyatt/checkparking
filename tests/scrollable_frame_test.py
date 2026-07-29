from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tkinter import ttk

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.ui.components.scrollable import ScrollableFrame


def main() -> int:
    previous_appdata = os.environ.get("APPDATA")
    with tempfile.TemporaryDirectory() as temporary:
        os.environ["APPDATA"] = temporary
        app = CheckVehicleApp()
        try:
            frame = ScrollableFrame(app, padding=4)
            frame.place(x=20, y=20, width=260, height=150)
            for row in range(40):
                ttk.Label(frame.content, text=f"Dòng kiểm thử {row}").grid(row=row, column=0, sticky="w", pady=2)
            app.update_idletasks()
            before = frame.canvas.yview()
            event = SimpleNamespace(x_root=frame.canvas.winfo_rootx() + 20, y_root=frame.canvas.winfo_rooty() + 20, delta=-120, widget=frame.canvas)
            assert frame._on_wheel(event) == "break"
            app.update_idletasks()
            assert frame.canvas.yview()[0] > before[0]
            frame._on_key_scroll(SimpleNamespace(keysym="End"))
            assert frame.canvas.yview()[1] >= 0.99
            frame._on_key_scroll(SimpleNamespace(keysym="Home"))
            assert frame.canvas.yview()[0] == 0.0

            app.show_page("scan")
            scan = app.shell.pages["scan"]
            assert isinstance(scan.scroll, ScrollableFrame)
            app.show_settings_section("updates")
            settings = app.shell.pages["settings"]
            assert settings.scrolls and all(isinstance(value, ScrollableFrame) for value in settings.scrolls.values())
        finally:
            app.destroy()
    if previous_appdata is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = previous_appdata
    print("scrollable_frame_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
