from __future__ import annotations

import json
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.gpt_vision import GptVisionEngine
from check_vehicle_ocr.providers import OpenAICompatibleProvider, ProviderConfig


class Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class FakeOpenAI:
    calls: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeOpenAI.calls.append(kwargs)


def main() -> int:
    captured = []

    def fake_urlopen(request, timeout=0):
        captured.append((request.full_url, request.headers, timeout))
        return Response(b'{"data":[{"id":"remote-model"}]}')

    config = ProviderConfig("Custom", "secret-token", "https://custom.example/v1/", "manual-model", ["manual-model"])
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        status = OpenAICompatibleProvider(config, timeout=7).refresh_models()
    assert status.ok and status.models == ["remote-model", "manual-model"]
    assert captured[0][0] == "https://custom.example/v1/models" and captured[0][2] == 7
    assert captured[0][1]["Authorization"] == "Bearer secret-token"

    error = HTTPError("https://custom.example/v1/models", 401, "Unauthorized", {}, Response(b"secret-token invalid"))
    with patch("urllib.request.urlopen", side_effect=error):
        failed = OpenAICompatibleProvider(config).refresh_models()
    assert not failed.ok and "HTTP 401" in failed.message and "secret-token" not in failed.message

    FakeOpenAI.calls.clear()
    with patch("check_vehicle_ocr.gpt_vision.OpenAI", FakeOpenAI):
        engine = GptVisionEngine("secret-token", "manual-model", timeout=17, base_url="https://custom.example/v1/")
    assert engine.available and FakeOpenAI.calls[-1]["base_url"] == "https://custom.example/v1"
    assert FakeOpenAI.calls[-1]["timeout"] == 17

    with tempfile.TemporaryDirectory() as temporary:
        image_path = Path(temporary) / "image.jpg"
        Image.new("RGB", (100, 60), "white").save(image_path)
        engine._call_model = lambda *_args: {"plates": [{"plate": "30A-123.45", "confidence": 93, "vehicle": "car", "visibility": "clear"}], "image_blurry": False, "notes": ""}
        result = engine.analyze_image(image_path)
    assert result.status == "OK" and result.plates[0].final_text == "30A-123.45"

    custom = {"enabled": True, "base_url": "https://custom.example/v1", "api_key": "secret-token", "model": "manual-model", "timeout": 17}
    with patch("check_vehicle_ocr.gpt_vision.OpenAI", FakeOpenAI):
        custom_engine = CheckVehicleApp._make_engine("OpenAI Compatible", None, None, "fallback", None, "", None, "", custom)
    assert custom_engine.base_url == "https://custom.example/v1" and custom_engine.model == "manual-model"
    unavailable = CheckVehicleApp._make_engine("OpenAI Compatible", None, None, "fallback", None, "", None, "", {"enabled": False})
    assert not unavailable.available and "chưa được bật" in unavailable.reason
    print("provider_integration_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
