from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderConfig:
    name: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    manual_models: list[str] = field(default_factory=list)
    api_mode: str = "auto"
    cached_api_mode: str = ""


@dataclass
class ProviderStatus:
    ok: bool
    message: str
    models: list[str] = field(default_factory=list)
    refreshed_at: float = 0.0


class OpenAICompatibleProvider:
    """Small stdlib client for OpenAI-compatible `/models` and connection checks."""

    def __init__(self, config: ProviderConfig, timeout: float = 15.0):
        self.config = config
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        return self.config.base_url.rstrip("/")

    def refresh_models(self) -> ProviderStatus:
        if not self.base_url:
            return ProviderStatus(False, "Chưa nhập Base URL.")
        try:
            payload = self._request_json("GET", "/models")
        except Exception as exc:
            return ProviderStatus(False, f"Không lấy được danh sách model: {exc}")
        models = sorted({str(item.get("id", "")).strip() for item in payload.get("data", []) if isinstance(item, dict) and item.get("id")})
        models = _merge_models(models, self.config.manual_models)
        return ProviderStatus(True, f"Đã tải {len(models)} model.", models, time.time())

    def test_connection(self) -> ProviderStatus:
        status = self.refresh_models()
        if status.ok:
            status.message = "Kết nối provider thành công."
        return status

    def _request_json(self, method: str, path: str) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(f"{self.base_url}{path}", headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:240]
            raise RuntimeError(redact_provider_error(f"HTTP {exc.code}: {detail}", self.config.api_key)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(redact_provider_error(f"Không kết nối được provider: {exc.reason}", self.config.api_key)) from exc


def _merge_models(remote: list[str], manual: list[str]) -> list[str]:
    return list(dict.fromkeys([*remote, *(item.strip() for item in manual if item.strip())]))


def redact_provider_error(message: str, *secrets: str) -> str:
    """Avoid leaking a configured API key through inline UI status or logs."""
    result = str(message)
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[đã ẩn]")
    return result[:360]
