from __future__ import annotations

"""Capture real Tkinter UI states for internal visual review.

The script uses the active desktop only. It does not synthesize images, start
OCR, call network services, or overwrite screenshots when desktop capture is
unavailable.
"""

import sys
import tempfile
import time
import os
from pathlib import Path

from PIL import Image, ImageGrab


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.models import ImageResult, PlateCandidate


def capture(app: CheckVehicleApp, output: Path) -> None:
    app.deiconify()
    app.lift()
    app.focus_force()
    app.update_idletasks()
    app.update()
    time.sleep(0.25)
    if os.name == "nt":
        image = _capture_window_win32(app.winfo_id())
    else:
        x, y, width, height = app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()
        image = ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True)
    if image.width <= 1 or image.height <= 1:
        raise RuntimeError("Desktop capture returned an empty image.")
    image.save(output)


def _capture_window_win32(hwnd: int) -> Image.Image:
    """Capture this exact HWND; desktop grabs can capture another foreground app."""
    import ctypes
    from ctypes import wintypes

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", ctypes.c_long),
            ("biHeight", ctypes.c_long),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_byte * 4)]

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    rect = RECT()
    if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        raise RuntimeError("Không lấy được kích thước cửa sổ Tkinter.")
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 1 or height <= 1:
        raise RuntimeError("Cửa sổ Tkinter chưa hiển thị để chụp.")
    window_dc = user32.GetWindowDC(wintypes.HWND(hwnd))
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    old_bitmap = gdi32.SelectObject(memory_dc, bitmap)
    try:
        if not user32.PrintWindow(wintypes.HWND(hwnd), memory_dc, 2):
            raise RuntimeError("Windows không thể chụp cửa sổ Tkinter bằng PrintWindow.")
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        buffer = ctypes.create_string_buffer(width * height * 4)
        rows = gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(info), 0)
        if rows != height:
            raise RuntimeError("Windows trả về ảnh cửa sổ không đầy đủ.")
        return Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1).copy()
    finally:
        if old_bitmap:
            gdi32.SelectObject(memory_dc, old_bitmap)
        if bitmap:
            gdi32.DeleteObject(bitmap)
        if memory_dc:
            gdi32.DeleteDC(memory_dc)
        if window_dc:
            user32.ReleaseDC(wintypes.HWND(hwnd), window_dc)


def main() -> int:
    output_dir = PROJECT_ROOT / "docs" / "ui-review"
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_appdata = tempfile.TemporaryDirectory(prefix="check_vehicle_ui_capture_")
    previous_environment = {name: os.environ.get(name) for name in ("APPDATA", "TEMP", "TMP")}
    for name in previous_environment:
        os.environ[name] = temporary_appdata.name
    app = CheckVehicleApp()
    app.geometry("1366x768+20+20")
    try:
        app.show_page("scan")
        capture(app, output_dir / "light-scan.png")
        scan_page = app.shell.pages["scan"]
        capture(app, output_dir / "advanced-collapsed.png")
        scan_page._toggle_advanced()
        capture(app, output_dir / "advanced-expanded.png")
        scan_page._toggle_advanced()
        app.dark_mode_var.set(True)
        app._on_theme_toggle()
        capture(app, output_dir / "dark-scan.png")
        app.dark_mode_var.set(False)
        app._on_theme_toggle()
        app._apply_progress_snapshot(
            {
                "status": "RUNNING",
                "total": 12,
                "completed": 4,
                "percent": 33,
                "elapsed_seconds": 20,
                "images_per_minute": 12.0,
                "eta_seconds": 40.0,
                "active_workers": {"local_ocr": 1},
                "configured_workers": {"image": 3, "local_ocr": 1, "api": 2},
                "current_files": ["ảnh-mẫu-04.jpg"],
                "succeeded": 3,
                "needs_review": 1,
                "failed": 0,
            },
            force=True,
        )

        with tempfile.TemporaryDirectory() as temporary:
            image_path = Path(temporary) / "xe_mau.jpg"
            Image.new("RGB", (640, 360), "white").save(image_path)
            app._add_paths([image_path])
            result = ImageResult(
                image_path=image_path,
                status="UNREADABLE",
                reason="Kết quả cần đối chiếu thủ công",
                width=640,
                height=360,
                plates=[
                    PlateCandidate(
                        bbox=(120, 120, 300, 70),
                        score=80,
                        source="paddle_region",
                        text="30A12B45",
                        raw_text="30A12B45",
                        cleaned_text="30A12B45",
                        normalized_text="30A12B45",
                        suggested_texts=["30A12845"],
                        ambiguity_flags=["B/8"],
                        needs_review=True,
                        confidence=78,
                        readable=False,
                    )
                ],
            )
            app.results = [result]
            app._refresh_table()
            app._apply_progress_snapshot(
                {
                    "status": "COMPLETED_WITH_ERRORS",
                    "total": 1,
                    "completed": 1,
                    "percent": 100,
                    "elapsed_seconds": 8,
                    "images_per_minute": 7.5,
                    "eta_seconds": 0.0,
                    "active_workers": {},
                    "configured_workers": {"image": 2, "local_ocr": 1, "api": 2},
                    "current_files": [],
                    "succeeded": 0,
                    "needs_review": 1,
                    "failed": 0,
                },
                force=True,
            )
            app.show_page("scan")
            app.show_page("results")
            app._select_path(image_path)
            capture(app, output_dir / "light-results.png")
            app.dark_mode_var.set(True)
            app._on_theme_toggle()
            capture(app, output_dir / "dark-results.png")
            app.dark_mode_var.set(False)
            app._on_theme_toggle()

        app.show_settings_section("ai")
        capture(app, output_dir / "settings-ai.png")
        app.show_settings_section("updates")
        capture(app, output_dir / "settings-updates.png")
    finally:
        app.destroy()
        temporary_appdata.cleanup()
        for name, previous_value in previous_environment.items():
            if previous_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous_value
    # Keep the harness usable in Windows consoles that still use cp1252.
    # The generated screenshots and application text remain UTF-8.
    print(f"Screenshots created at {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
