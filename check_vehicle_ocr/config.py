from __future__ import annotations

import base64
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


APP_DIR_NAME = "CheckVehicleOCR"
SETTINGS_FILE = "settings.json"
SETTINGS_VERSION = 15

# These values were used only by early UI tests.  They must never behave as a
# release source in a real operator profile.  Keep this exact, small list: a
# legitimate ``file:///...`` manifest selected by an operator is supported.
_TEST_UPDATE_SENTINELS = frozenset({"file:///mock", "file:///mock-manifest.json"})


def is_test_update_sentinel(value: object) -> bool:
    """Return whether *value* is one of the old, test-only update URLs.

    This intentionally compares the complete value.  Operators are still free
    to use a real local ``file:///...`` manifest when that is their chosen
    update source.
    """
    return str(value or "").strip() in _TEST_UPDATE_SENTINELS


def settings_path() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_DIR_NAME / SETTINGS_FILE
    return Path.home() / ".check_vehicle_ocr" / SETTINGS_FILE


def load_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    original_data = deepcopy(data)
    data = migrate_settings(data)
    if data != original_data:
        # Persist only the raw, still-protected migration result.  This removes
        # old test sentinels before the Update Center can attempt to open them
        # and never serializes decrypted API keys.
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    protected_fields = {
        "api_key": "api_key_dpapi",
        "gemini_api_key": "gemini_api_key_dpapi",
        "plate_recognizer_token": "plate_recognizer_token_dpapi",
    }
    for plain_name, protected_name in protected_fields.items():
        encrypted_key = str(data.get(protected_name) or "")
        data[plain_name] = _unprotect_text(encrypted_key) if encrypted_key else ""
    _restore_nested_secrets(data)
    return data


def migrate_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Add safe defaults without discarding existing user settings."""
    migrated = dict(data)
    migrated["version"] = SETTINGS_VERSION
    migrated.setdefault("worker_mode", "AUTO")
    migrated.setdefault("image_workers", 0)
    migrated.setdefault("local_ocr_workers", 1)
    migrated.setdefault("api_workers", 2)
    migrated.setdefault("queue_capacity", 32)
    migrated.setdefault("provider_configs", {})
    if not isinstance(migrated["provider_configs"], dict):
        migrated["provider_configs"] = {}
    migrated.setdefault("telegram", {})
    if not isinstance(migrated["telegram"], dict):
        migrated["telegram"] = {}
    migrated.setdefault("updates", {"manifest_url": "", "channel": "stable", "auto_install": False})
    if not isinstance(migrated["updates"], dict):
        migrated["updates"] = {"manifest_url": "", "channel": "stable", "auto_install": False}
    updates = migrated["updates"]
    manifest_url = str(updates.get("manifest_url") or "").strip()
    removed_test_manifest = is_test_update_sentinel(manifest_url)
    if removed_test_manifest:
        updates["manifest_url"] = ""
    updates.setdefault("source_mode", "disabled")
    if updates["source_mode"] not in {"disabled", "github", "manifest"}:
        updates["source_mode"] = "manifest" if updates.get("manifest_url") else "disabled"
    # Previous screenshot tests could persist ``file:///mock`` while leaving
    # the mode set to ``manifest``.  Disable that exact stale configuration so
    # the operator sees a neutral setup prompt instead of a WinError.  Do not
    # change a legitimate local manifest URL.
    if removed_test_manifest and updates["source_mode"] == "manifest":
        updates["source_mode"] = "disabled"
    updates.setdefault("github_repository", "")
    updates.setdefault("github_token_dpapi", "")
    # A short-lived development build could have written this optional token
    # without protection.  Preserve it by migrating into DPAPI/plain64 rather
    # than leaving a secret in settings.json.
    legacy_github_token = str(updates.pop("github_token", "") or "").strip()
    if legacy_github_token and not str(updates.get("github_token_dpapi") or ""):
        updates["github_token_dpapi"] = _protect_text(legacy_github_token)
    updates.setdefault("paddle_release_source", "https://pypi.org/pypi/paddleocr/json")
    updates.setdefault("paddle_candidate_version", "")
    updates.setdefault("model_manifest_url", "")
    updates.setdefault("tesseract_manifest_url", "")
    engine = str(migrated.get("engine") or "PaddleOCR Local")
    recognition_mode = str(migrated.get("recognition_mode") or "").strip()
    if recognition_mode not in {"local", "local_ai_review", "online"}:
        if engine == "PaddleOCR + AI Review":
            recognition_mode = "local_ai_review"
        elif engine in {"OpenAI Compatible", "GPT Vision", "Gemini Vision", "Plate Recognizer"}:
            recognition_mode = "online"
        else:
            recognition_mode = "local"
    migrated["recognition_mode"] = recognition_mode
    migrated.setdefault("tesseract_fallback_enabled", engine == "Local OCR")
    migrated.setdefault("export_reviewed_only", False)
    migrated.setdefault("performance_preset", _performance_preset_from_legacy(migrated))
    if migrated.get("paddle_scan_mode") == "Cân bằng":
        migrated["paddle_scan_mode"] = "Cân bằng — Khuyên dùng"
    elif migrated.get("paddle_scan_mode") == "Quét kỹ":
        migrated["paddle_scan_mode"] = "Kỹ"
    return migrated


def _performance_preset_from_legacy(data: dict[str, Any]) -> str:
    try:
        image_workers = int(data.get("image_workers") or data.get("worker_count") or 0)
        api_workers = int(data.get("api_workers") or 0)
    except (TypeError, ValueError):
        return "AUTO"
    if image_workers <= 1 and api_workers <= 1:
        return "LOW_MEMORY"
    if image_workers >= 3 or api_workers >= 3:
        return "FAST"
    return "AUTO"


def save_settings(
    data: dict[str, Any],
    api_key: str = "",
    gemini_api_key: str = "",
    plate_recognizer_token: str = "",
    provider_api_keys: dict[str, str] | None = None,
    telegram_bot_token: str = "",
    github_token: str = "",
) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    plain_key_names = {"api_key", "gemini_api_key", "plate_recognizer_token"}
    payload = deepcopy({key: value for key, value in data.items() if key not in plain_key_names})
    protected_values = {
        "api_key_dpapi": api_key.strip(),
        "gemini_api_key_dpapi": gemini_api_key.strip(),
        "plate_recognizer_token_dpapi": plate_recognizer_token.strip(),
    }
    for protected_name, value in protected_values.items():
        if payload.get("remember_key") and value:
            payload[protected_name] = _protect_text(value)
        else:
            payload.pop(protected_name, None)

    _protect_nested_secrets(
        payload,
        provider_api_keys or {},
        telegram_bot_token,
        github_token,
        remember=bool(payload.get("remember_key")),
    )

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def clear_saved_api_key() -> None:
    data = load_settings()
    data["remember_key"] = False
    save_settings(data, api_key="", gemini_api_key="", plate_recognizer_token="", provider_api_keys={}, telegram_bot_token="", github_token="")


def _restore_nested_secrets(data: dict[str, Any]) -> None:
    providers = data.get("provider_configs")
    if isinstance(providers, dict):
        for value in providers.values():
            if not isinstance(value, dict):
                continue
            encrypted = str(value.get("api_key_dpapi") or "")
            value["api_key"] = _unprotect_text(encrypted) if encrypted else ""

    telegram = data.get("telegram")
    if isinstance(telegram, dict):
        encrypted = str(telegram.get("bot_token_dpapi") or "")
        telegram["bot_token"] = _unprotect_text(encrypted) if encrypted else ""

    updates = data.get("updates")
    if isinstance(updates, dict):
        encrypted = str(updates.get("github_token_dpapi") or "")
        updates["github_token"] = _unprotect_text(encrypted) if encrypted else ""


def _protect_nested_secrets(
    payload: dict[str, Any],
    provider_api_keys: dict[str, str],
    telegram_bot_token: str,
    github_token: str,
    *,
    remember: bool,
) -> None:
    providers = payload.get("provider_configs")
    if isinstance(providers, dict):
        for name, value in providers.items():
            if not isinstance(value, dict):
                continue
            value.pop("api_key", None)
            secret = str(provider_api_keys.get(str(name), "") or "").strip()
            if remember and secret:
                value["api_key_dpapi"] = _protect_text(secret)
            else:
                value.pop("api_key_dpapi", None)

    telegram = payload.get("telegram")
    if isinstance(telegram, dict):
        telegram.pop("bot_token", None)
        if remember and telegram_bot_token.strip():
            telegram["bot_token_dpapi"] = _protect_text(telegram_bot_token.strip())
        else:
            telegram.pop("bot_token_dpapi", None)

    updates = payload.get("updates")
    if isinstance(updates, dict):
        updates.pop("github_token", None)
        if remember and github_token.strip():
            updates["github_token_dpapi"] = _protect_text(github_token.strip())
        else:
            updates.pop("github_token_dpapi", None)


def _protect_text(value: str) -> str:
    raw = value.encode("utf-8")
    if sys.platform == "win32":
        try:
            return "dpapi:" + base64.b64encode(_crypt_protect(raw)).decode("ascii")
        except Exception:
            pass
    return "plain64:" + base64.b64encode(raw).decode("ascii")


def _unprotect_text(value: str) -> str:
    try:
        if value.startswith("dpapi:") and sys.platform == "win32":
            raw = base64.b64decode(value.removeprefix("dpapi:"))
            return _crypt_unprotect(raw).decode("utf-8")
        if value.startswith("plain64:"):
            return base64.b64decode(value.removeprefix("plain64:")).decode("utf-8")
    except Exception:
        return ""
    return ""


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32
    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p

    def _blob_from_bytes(data: bytes) -> tuple[_DataBlob, Any]:
        buffer = ctypes.create_string_buffer(data)
        return _DataBlob(len(data), ctypes.cast(buffer, ctypes.c_void_p)), buffer

    def _crypt_protect(data: bytes) -> bytes:
        input_blob, buffer = _blob_from_bytes(data)
        _ = buffer
        output_blob = _DataBlob()
        ok = _crypt32.CryptProtectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob))
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            _kernel32.LocalFree(output_blob.pbData)

    def _crypt_unprotect(data: bytes) -> bytes:
        input_blob, buffer = _blob_from_bytes(data)
        _ = buffer
        output_blob = _DataBlob()
        ok = _crypt32.CryptUnprotectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob))
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            _kernel32.LocalFree(output_blob.pbData)

else:

    def _crypt_protect(data: bytes) -> bytes:
        return data

    def _crypt_unprotect(data: bytes) -> bytes:
        return data
