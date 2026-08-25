from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_vehicle_ocr.version import DEFAULT_GITHUB_REPOSITORY, VERSION


def main() -> int:
    assert VERSION == "1.9.8"
    assert DEFAULT_GITHUB_REPOSITORY == "NovWyatt/checkparking"
    icon_root = ROOT / "assets" / "icons"
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        assert (icon_root / f"app-icon-{size}.png").is_file()
    icon = Image.open(icon_root / "app-icon.ico")
    assert len(icon.ico.sizes()) >= 6
    for name in ("scan", "folder", "images", "results", "review", "export", "settings", "update", "download", "telegram-notification", "ai", "local-ocr", "warning", "success", "error", "stop", "search", "edit", "delete", "refresh", "install"):
        assert (icon_root / f"{name}.svg").is_file() and (icon_root / f"{name}.png").is_file()
    spec = (ROOT / "CheckVehicleOCR.spec").read_text(encoding="utf-8")
    installer = (ROOT / "installer" / "CheckVehicleOCR.iss").read_text(encoding="utf-8")
    assert "app-icon.ico" in spec and "SetupIconFile" in installer
    print("release_v180_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
