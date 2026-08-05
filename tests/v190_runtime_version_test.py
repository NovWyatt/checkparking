from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_vehicle_ocr.ocr_models import DEFAULT_MODEL_PROFILE, PP_OCRV6_TINY
from check_vehicle_ocr.model_registry import ModelRuntimeManager
from check_vehicle_ocr.paddle_ocr_engine import _bundled_model_dirs, current_model_selection
from check_vehicle_ocr.version import VERSION


def main() -> int:
    assert VERSION == "1.9.3"
    with tempfile.TemporaryDirectory() as temporary:
        previous_appdata, previous_localappdata = os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA")
        os.environ["APPDATA"] = temporary
        os.environ["LOCALAPPDATA"] = temporary
        detection, recognition = current_model_selection()
        assert (detection, recognition) == (DEFAULT_MODEL_PROFILE.detection_model, DEFAULT_MODEL_PROFILE.recognition_model)
        bundled = _bundled_model_dirs(detection, recognition)
        assert Path(bundled[detection]).is_dir() and Path(bundled[recognition]).is_dir()
        assert PP_OCRV6_TINY.detection_model != detection
        output = Path(temporary) / "runtime-versions.json"
        subprocess.run([sys.executable, str(ROOT / "tools" / "write_runtime_versions.py"), "--output", str(output), "--commit", "a" * 40], check=True)
        metadata = json.loads(output.read_text(encoding="utf-8"))
        assert metadata["app_version"] == VERSION
        assert metadata["paddleocr"] == "3.7.0"
        assert metadata["paddlepaddle"] == "3.3.1"
        assert metadata["paddlex"] == "3.7.2"
        assert metadata["detection_model"] == detection and metadata["model_sha256"][detection]
        assert metadata["commit"] == "a" * 40
        if previous_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = previous_appdata
        if previous_localappdata is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = previous_localappdata

        staged = Path(temporary) / "staged"
        for name in ("PP-OCRv6_small_det", "PP-OCRv6_small_rec"):
            model = staged / name
            model.mkdir(parents=True)
            (model / "inference.yml").write_text("model: test", encoding="utf-8")
            (model / "model.json").write_text("{}", encoding="utf-8")
        captured: dict[str, object] = {}

        def runner(command, **kwargs):
            captured["command"] = command
            captured["env"] = kwargs["env"]
            return type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        report = ModelRuntimeManager(root=Path(temporary) / "registry", project_root=ROOT).validate_and_record(
            version="1.9.0-smoke",
            stage_dir=staged,
            detection_model="PP-OCRv6_small_det",
            recognition_model="PP-OCRv6_small_rec",
            runner=runner,
        )
        assert report.passed
        assert captured["env"]["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] == "0"
        assert "PP-OCRv6_small_det" in captured["command"]
    print("v190_runtime_version_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
