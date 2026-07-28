from __future__ import annotations

"""Capture actual Tk widget states for contrast review.

The harness uses an isolated APPDATA directory and never writes mock update
sources or settings to the operator profile.  It captures a posted native
Combobox list rather than drawing a synthetic substitute.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

from PIL import ImageGrab


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.ui.components.forms import labelled_combo


def _capture(widget, destination: Path, *, dropdown: bool = False) -> None:
    if not dropdown:
        widget.deiconify()
        widget.lift()
        widget.focus_force()
    widget.update_idletasks()
    widget.update()
    if os.name == "nt" and not dropdown:
        import ctypes

        ctypes.windll.user32.SetForegroundWindow(widget.winfo_id())
        widget.update()
    time.sleep(0.2)
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    width, height = widget.winfo_width(), widget.winfo_height()
    if width <= 1 or height <= 1:
        raise RuntimeError("Cửa sổ kiểm tra control chưa hiển thị.")
    image = ImageGrab.grab(bbox=(x, y, x + width, y + height + (220 if dropdown else 0)), all_screens=True)
    image.save(destination)


def _post(combo) -> None:
    combo.focus_set()
    combo.tk.call("ttk::combobox::Post", str(combo))


def _unpost(combo) -> None:
    try:
        combo.tk.call("ttk::combobox::Unpost", str(combo))
    except Exception:
        pass


def _capture_control_states(app: CheckVehicleApp, output: Path, dark: bool) -> None:
    app.dark_mode_var.set(dark)
    app._on_theme_toggle()
    # Create a real child window without adding an application page.
    import tkinter as tk
    from tkinter import ttk

    window = tk.Toplevel(app)
    window.title("Trạng thái control")
    window.geometry("640x360+80+80")
    window.attributes("-topmost", True)
    frame = ttk.Frame(window, style="App.TFrame", padding=18)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)
    ttk.Label(frame, text="Kiểm tra trạng thái điều khiển", style="PageTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
    normal_var = tk.StringVar(value="Tự động")
    readonly_var = tk.StringVar(value="Tự động")
    disabled_var = tk.StringVar(value="Không khả dụng")
    window._state_variables = (normal_var, readonly_var, disabled_var)
    normal = labelled_combo(frame, 1, "Bình thường", normal_var, ("Tự động", "Tiết kiệm RAM", "Ưu tiên tốc độ"))
    readonly = labelled_combo(frame, 2, "Chỉ chọn", readonly_var, ("Tự động", "Tiết kiệm RAM", "Ưu tiên tốc độ"), readonly=True)
    disabled = labelled_combo(frame, 3, "Tắt", disabled_var, ("Không khả dụng",))
    disabled.state(["disabled"])
    ttk.Entry(frame, state="disabled").grid(row=4, column=1, sticky="ew", pady=4)
    normal.focus_set()
    window.deiconify()
    window.lift()
    window.focus_force()
    window.update_idletasks()
    _post(readonly)
    _capture(window, output, dropdown=True)
    _unpost(readonly)
    window.attributes("-topmost", False)
    window.destroy()


def _capture_scan_combo(app: CheckVehicleApp, output: Path, dark: bool) -> None:
    app.dark_mode_var.set(dark)
    app._on_theme_toggle()
    app.show_page("scan")
    app.geometry("1100x720+20+20")
    app.deiconify()
    app.lift()
    app.focus_force()
    app.update()
    if os.name == "nt":
        import ctypes

        ctypes.windll.user32.SetForegroundWindow(app.winfo_id())
    combo = app.shell.pages["scan"].performance_combo
    _post(combo)
    _capture(app, output, dropdown=True)
    _unpost(combo)


def main() -> int:
    output_dir = PROJECT_ROOT / "docs" / "ui-review"
    output_dir.mkdir(parents=True, exist_ok=True)
    old_environment = {name: os.environ.get(name) for name in ("APPDATA", "TEMP", "TMP")}
    with tempfile.TemporaryDirectory(prefix="check_vehicle_control_capture_") as isolated_appdata:
        for name in old_environment:
            os.environ[name] = isolated_appdata
        app = CheckVehicleApp()
        try:
            _capture_control_states(app, output_dir / "control-states-light.png", dark=False)
            _capture_control_states(app, output_dir / "control-states-dark.png", dark=True)
            _capture_scan_combo(app, output_dir / "scan-combobox-light.png", dark=False)
            _capture_scan_combo(app, output_dir / "scan-combobox-dark.png", dark=True)
        finally:
            app.destroy()
    for name, previous_value in old_environment.items():
        if previous_value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous_value
    print(f"Control-state screenshots created at {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
