from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.providers import OpenAICompatibleProvider, ProviderConfig
from check_vehicle_ocr.telegram_notify import TelegramNotifier, TelegramSettings, mask_plate
from check_vehicle_ocr.updater import download_verified, parse_manifest
from check_vehicle_ocr.config import load_settings, migrate_settings, save_settings, settings_path


class Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def main() -> int:
    phase = "settings migration"
    try:
        migrated = migrate_settings({"engine": "PaddleOCR Local"})
        assert migrated["engine"] == "PaddleOCR Local" and migrated["telegram"] == {} and migrated["updates"]["channel"] == "stable"
        phase = "protected settings"
        with tempfile.TemporaryDirectory() as temporary:
            import os

            old_appdata = os.environ.get("APPDATA")
            os.environ["APPDATA"] = temporary
            try:
                save_settings(
                    {
                        "remember_key": True,
                        "provider_configs": {"custom_openai": {"name": "Custom", "api_key": "secret-provider", "api_mode": "chat_completions", "cached_api_mode": "chat_completions"}},
                        "telegram": {"enabled": True, "bot_token": "secret-telegram"},
                    },
                    provider_api_keys={"custom_openai": "secret-provider"},
                    telegram_bot_token="secret-telegram",
                )
                raw = settings_path().read_text(encoding="utf-8")
                restored = load_settings()
                assert "secret-provider" not in raw and "secret-telegram" not in raw
                assert restored["provider_configs"]["custom_openai"]["api_key"] == "secret-provider"
                assert restored["provider_configs"]["custom_openai"]["api_mode"] == "chat_completions"
                assert restored["telegram"]["bot_token"] == "secret-telegram"
            finally:
                if old_appdata is None:
                    os.environ.pop("APPDATA", None)
                else:
                    os.environ["APPDATA"] = old_appdata
        phase = "provider model refresh"
        provider = OpenAICompatibleProvider(ProviderConfig("Mock", "key", "https://provider.example/v1", manual_models=["manual", "gpt-test"]))
        with patch("urllib.request.urlopen", return_value=Response(b'{"data":[{"id":"gpt-test"},{"id":"vision"}]}')):
            status = provider.refresh_models()
        assert status.ok and status.models == ["gpt-test", "vision", "manual"]

        phase = "telegram mock"
        notifier = TelegramNotifier(TelegramSettings(enabled=True, bot_token="token", chat_id="123", minimum_interval_seconds=3600))
        with patch("urllib.request.urlopen", return_value=Response(b'{"ok":true}')):
            assert notifier.send("test") and not notifier.send("suppressed")
        assert mask_plate("30A-123.45") == "30***45"

        phase = "verified updater download"
        content = b"verified update"
        manifest = parse_manifest(json.dumps({"version":"1.2.3", "release_notes":"test", "download_url":"https://update.example/file", "sha256":hashlib.sha256(content).hexdigest()}))
        with tempfile.TemporaryDirectory() as temporary:
            downloaded = download_verified(manifest, Path(temporary), opener=lambda *_args, **_kwargs: Response(content))
            assert downloaded.read_bytes() == content
    except Exception as exc:
        # GitHub Action annotations expose the phase without ever echoing a
        # provider key, Telegram token or raw settings payload.
        print(f"::error title=services_test failed::{phase}: {type(exc).__name__}")
        raise
    print("services_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
