"""Assert essential Tk controls from a real PyInstaller executable."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, default=ROOT / "release" / "CheckVehicleOCR" / "CheckVehicleOCR.exe")
    parser.add_argument("--version", default="1.9.9")
    args = parser.parse_args()
    executable = args.executable.resolve()
    if not executable.is_file():
        raise SystemExit(f"Không tìm thấy EXE để smoke: {executable}")
    with tempfile.TemporaryDirectory(prefix="check_vehicle_packaged_assert_") as temporary:
        root = Path(temporary)
        assertion = root / "ui.json"
        env = {
            **os.environ,
            "APPDATA": str(root),
            "LOCALAPPDATA": str(root),
            "TEMP": str(root),
            "TMP": str(root),
            "CHECK_VEHICLE_UI_ASSERT_PATH": str(assertion),
            "CHECK_VEHICLE_UI_REVIEW_PAGE": "updates",
        }
        process = subprocess.Popen([str(executable)], cwd=str(executable.parent), env=env)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not assertion.exists():
                time.sleep(0.1)
            if not assertion.exists():
                raise RuntimeError("EXE không tạo xác nhận giao diện trong thời gian chờ.")
            payload = json.loads(assertion.read_text(encoding="utf-8"))
            assert payload["version"] == args.version
            assert payload["plate_type_label"] == "Loại biển số"
            assert payload["plate_type_values"] == ["Xe máy", "Ô tô", "Không tự định dạng"]
            assert payload["expected_plate_count_label"] == "Số biển số dự kiến trong mỗi ảnh"
            assert payload["expected_plate_count_values"] == ["Một biển số — Khuyên dùng", "Có thể có nhiều biển số"]
            assert payload["update_source_mode"] == "github"
            assert payload["github_repository"] == "NovWyatt/checkparking"
            assert payload["update_primary_action"] == "Kiểm tra"
            assert payload["reconciliation_navigation"] is True
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
    print("packaged_ui_assert OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
