"""Capture real UI states from a packaged Windows executable.

This is deliberately separate from the source UI harness: it launches the
PyInstaller executable with an isolated operator profile and captures actual
desktop pixels.  It never starts OCR, downloads models, sends Telegram or
contacts an update service.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _find_window(process_id: int) -> int:
    user32 = ctypes.windll.user32
    found: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def visit(hwnd, _lparam):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == process_id and user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title, len(title))
            if title.value.startswith("Check Vehicle OCR"):
                found.append(int(hwnd))
                return False
        return True

    user32.EnumWindows(visit, 0)
    return found[0] if found else 0


def _wait_window(process_id: int, timeout: float = 25.0) -> int:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        window = _find_window(process_id)
        if window:
            return window
        time.sleep(0.2)
    raise RuntimeError("The packaged application did not create a visible window.")


def _capture(hwnd: int, destination: Path) -> None:
    # PrintWindow captures the executable's HWND directly, so the review image
    # cannot accidentally contain Codex, a terminal, or another foreground
    # window.  It still captures the actual packaged Tk UI pixels.
    from capture_ui_review import _capture_window_win32

    image = _capture_window_win32(hwnd)
    if image.width < 100 or image.height < 100:
        raise RuntimeError("Packaged application capture was unexpectedly empty.")
    image.save(destination)


def _write_profile(directory: Path, *, dark: bool) -> None:
    settings = directory / "CheckVehicleOCR" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"version": 15, "dark_mode": dark, "updates": {"source_mode": "disabled"}}, ensure_ascii=False), encoding="utf-8")


def _run_capture(executable: Path, output: Path, *, dark: bool, prefix: str, review_page: str = "scan") -> None:
    with tempfile.TemporaryDirectory(prefix="check_vehicle_packaged_review_") as profile:
        profile_root = Path(profile)
        _write_profile(profile_root, dark=dark)
        env = {
            **os.environ,
            "APPDATA": str(profile_root),
            "LOCALAPPDATA": str(profile_root),
            "TEMP": str(profile_root),
            "TMP": str(profile_root),
            "CHECK_VEHICLE_UI_REVIEW_PAGE": review_page,
        }
        process = subprocess.Popen([str(executable)], cwd=str(executable.parent), env=env)
        try:
            window = _wait_window(process.pid)
            _capture(window, output / f"{prefix}-{review_page}.png")
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> int:
    if os.name != "nt":
        raise SystemExit("Packaged Windows screenshot capture requires Windows.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, default=ROOT / "release" / "CheckVehicleOCR" / "CheckVehicleOCR.exe")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "ui-review" / "release")
    args = parser.parse_args()
    executable = args.executable.resolve()
    if not executable.is_file():
        raise SystemExit(f"Packaged executable does not exist: {executable}")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    _run_capture(executable, output, dark=False, prefix="packaged-light")
    _run_capture(executable, output, dark=False, prefix="packaged-light", review_page="updates")
    _run_capture(executable, output, dark=True, prefix="packaged-dark")
    _run_capture(executable, output, dark=True, prefix="packaged-dark", review_page="updates")
    print(f"Packaged screenshots created at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
