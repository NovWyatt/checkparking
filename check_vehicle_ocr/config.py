from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any


APP_DIR_NAME = "CheckVehicleOCR"
SETTINGS_FILE = "settings.json"


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

    protected_fields = {
        "api_key": "api_key_dpapi",
        "gemini_api_key": "gemini_api_key_dpapi",
        "plate_recognizer_token": "plate_recognizer_token_dpapi",
    }
    for plain_name, protected_name in protected_fields.items():
        encrypted_key = str(data.get(protected_name) or "")
        data[plain_name] = _unprotect_text(encrypted_key) if encrypted_key else ""
    return data


def save_settings(
    data: dict[str, Any],
    api_key: str = "",
    gemini_api_key: str = "",
    plate_recognizer_token: str = "",
) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    plain_key_names = {"api_key", "gemini_api_key", "plate_recognizer_token"}
    payload = {key: value for key, value in data.items() if key not in plain_key_names}
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

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def clear_saved_api_key() -> None:
    data = load_settings()
    data["remember_key"] = False
    save_settings(data, api_key="", gemini_api_key="", plate_recognizer_token="")


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
