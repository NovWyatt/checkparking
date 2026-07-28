from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from io import BytesIO

import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.gpt_vision import GptVisionEngine, _provider_error_reason
from check_vehicle_ocr.providers import OpenAICompatibleProvider, ProviderConfig


PAYLOAD = json.dumps({"plates": [{"plate": "30A-123.45", "confidence": 92, "vehicle": "car", "visibility": "clear", "note": ""}], "image_blurry": False, "needs_review": False, "notes": ""})


class _Response:
    def __init__(self, text: str):
        self.output_text = text


class _Message:
    def __init__(self, text: str):
        self.content = text


class _Choice:
    def __init__(self, text: str):
        self.message = _Message(text)


class _ChatResponse:
    def __init__(self, text: str):
        self.choices = [_Choice(text)]


class _HttpResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class _Endpoint:
    def __init__(self, mode: str, calls: list[tuple[str, dict]]):
        self.mode = mode
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append((self.mode, kwargs))
        if self.mode == "responses" and self.server.responses_error:
            raise RuntimeError(self.server.responses_error)
        if self.mode == "chat_completions" and self.server.chat_error:
            raise RuntimeError(self.server.chat_error)
        return _Response(PAYLOAD) if self.mode == "responses" else _ChatResponse(PAYLOAD)


class _Server:
    def __init__(self, responses_error: str = "", chat_error: str = ""):
        self.responses_error = responses_error
        self.chat_error = chat_error
        self.calls: list[tuple[str, dict]] = []
        responses = _Endpoint("responses", self.calls)
        responses.server = self
        chat = _Endpoint("chat_completions", self.calls)
        chat.server = self
        self.responses = responses
        self.chat = type("Chat", (), {"completions": chat})()


def _engine(server: _Server, *, api_mode: str = "auto", cached: str = "") -> GptVisionEngine:
    with patch("check_vehicle_ocr.gpt_vision.OpenAI", return_value=server):
        return GptVisionEngine("secret-token", "manual-model", base_url="https://custom.example/v1", api_mode=api_mode, cached_api_mode=cached)


def _call(engine: GptVisionEngine):
    with patch("check_vehicle_ocr.gpt_vision._candidate_crop_data_urls", return_value=[]):
        return engine._call_model(Path("fake.jpg"), np.zeros((20, 30, 3), dtype=np.uint8))


def main() -> int:
    responses_only = _Server()
    engine = _engine(responses_only)
    assert _call(engine)["plates"][0]["plate"] == "30A-123.45"
    assert [mode for mode, _kwargs in responses_only.calls] == ["responses"]
    assert engine.last_api_mode == "responses" and responses_only.calls[0][1]["model"] == "manual-model"

    chat_only = _Server(responses_error="HTTP 404: /v1/responses endpoint not found")
    engine = _engine(chat_only)
    assert _call(engine)["plates"]
    assert [mode for mode, _kwargs in chat_only.calls] == ["responses", "chat_completions"]
    assert engine.last_api_mode == "chat_completions"
    chat_content = chat_only.calls[-1][1]["messages"][0]["content"]
    assert chat_content[1]["type"] == "image_url" and chat_content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")

    both = _Server()
    engine = _engine(both, cached="chat_completions")
    assert _call(engine)["plates"]
    assert [mode for mode, _kwargs in both.calls] == ["chat_completions"]

    unsupported = _Server(
        responses_error="HTTP 404: /v1/responses endpoint not found",
        chat_error="HTTP 405: /v1/chat/completions method not allowed",
    )
    try:
        _call(_engine(unsupported))
    except RuntimeError as exc:
        assert "405" in str(exc)
    else:
        raise AssertionError("Unsupported inference endpoints did not fail")
    with patch("urllib.request.urlopen", return_value=_HttpResponse(b'{"data":[{"id":"manual-model"}]}')):
        models_status = OpenAICompatibleProvider(ProviderConfig("Mock", "secret-token", "https://custom.example/v1", "manual-model")).refresh_models()
    assert models_status.ok and models_status.models == ["manual-model"]

    unauthorized = _Server(responses_error="HTTP 401: secret-token unauthorized")
    try:
        _call(_engine(unauthorized))
    except RuntimeError as exc:
        assert "401" in str(exc)
    else:
        raise AssertionError("401 did not fail")
    assert [mode for mode, _kwargs in unauthorized.calls] == ["responses"]
    with tempfile.TemporaryDirectory() as temporary:
        image_path = Path(temporary) / "image.jpg"
        Image.new("RGB", (30, 20), "white").save(image_path)
        engine = _engine(_Server(responses_error="HTTP 401: secret-token unauthorized"))
        with patch("check_vehicle_ocr.gpt_vision._candidate_crop_data_urls", return_value=[]):
            result = engine.analyze_image(image_path)
        assert result.status == "ERROR" and "secret-token" not in result.error
    assert "xác thực" in _provider_error_reason(RuntimeError("HTTP 401"))
    assert "không hỗ trợ" in _provider_error_reason(RuntimeError("HTTP 404: /v1/responses endpoint not found"))
    assert "429" in _provider_error_reason(RuntimeError("HTTP 429 rate limit"))
    assert "thời gian" in _provider_error_reason(RuntimeError("timeout"))
    print("provider_api_mode_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
