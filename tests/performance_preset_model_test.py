from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.config import save_settings
from check_vehicle_ocr.ocr_models import DEFAULT_MODEL_PROFILE, PP_OCRV6_TINY, current_model_selection


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="check_vehicle_preset_model_") as temporary:
        previous_appdata = os.environ.get("APPDATA")
        previous_localappdata = os.environ.get("LOCALAPPDATA")
        os.environ["APPDATA"] = temporary
        os.environ["LOCALAPPDATA"] = temporary
        try:
            assert current_model_selection() == (
                DEFAULT_MODEL_PROFILE.detection_model,
                DEFAULT_MODEL_PROFILE.recognition_model,
            )

            save_settings({"performance_preset": "FAST"})
            assert current_model_selection() == (
                PP_OCRV6_TINY.detection_model,
                PP_OCRV6_TINY.recognition_model,
            )
        finally:
            if previous_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = previous_appdata
            if previous_localappdata is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous_localappdata

    print("performance_preset_model_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
