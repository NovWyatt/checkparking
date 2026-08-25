"""Signed-license validation for the Windows desktop application.

The app never contains a Cloudflare secret.  It accepts a license response
only after Ed25519 verification with the public key compiled into the release.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .license_config import LICENSE_SERVICE_URL, LICENSE_SIGNING_PUBLIC_KEY_B64, license_service_is_configured
from .version import VERSION


class LicenseState(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NEEDS_ACTIVATION = "NEEDS_ACTIVATION"
    ACTIVE_OFFLINE = "ACTIVE_OFFLINE"
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    INVALID = "INVALID"
    NETWORK_ERROR = "NETWORK_ERROR"


@dataclass(frozen=True)
class LicenseDecision:
    state: LicenseState
    message: str
    certificate: dict[str, Any] | None = None
    signature: str = ""

    @property
    def usable(self) -> bool:
        return self.state in {LicenseState.NOT_CONFIGURED, LicenseState.ACTIVE_OFFLINE}


@dataclass(frozen=True)
class LicenseConfiguration:
    service_url: str
    signing_public_key_b64: str

    @property
    def enforced(self) -> bool:
        return bool(self.service_url.strip() and self.signing_public_key_b64.strip())


def bundled_license_configuration() -> LicenseConfiguration:
    """Return only public release configuration, never environment overrides."""

    return LicenseConfiguration(LICENSE_SERVICE_URL.strip(), LICENSE_SIGNING_PUBLIC_KEY_B64.strip())


def new_device_id() -> str:
    """Return a random local installation identifier without hardware data."""

    return secrets.token_urlsafe(24)


def canonical_certificate(certificate: dict[str, Any]) -> bytes:
    """Match the stable field order signed by the Cloudflare Worker."""

    payload = {
        "check_after": certificate.get("check_after"),
        "device_hash": certificate.get("device_hash"),
        "expires_at": certificate.get("expires_at"),
        "issued_at": certificate.get("issued_at"),
        "license_id": certificate.get("license_id"),
        "license_type": certificate.get("license_type"),
        "status": certificate.get("status"),
        "v": certificate.get("v"),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def device_hash(device_id: str) -> str:
    return _base64url(hashlib.sha256(device_id.encode("utf-8")).digest())


class LicenseService:
    """Validate local certificates and call the first-party Worker on demand."""

    def __init__(self, configuration: LicenseConfiguration | None = None, timeout: float = 12.0) -> None:
        self.configuration = configuration or bundled_license_configuration()
        self.timeout = timeout

    @property
    def enforced(self) -> bool:
        return self.configuration.enforced

    def evaluate(self, license_state: object, device_id: str) -> LicenseDecision:
        if not self.enforced:
            return LicenseDecision(LicenseState.NOT_CONFIGURED, "Bản thử nghiệm chưa bật kiểm tra bản quyền.")
        if not isinstance(license_state, dict) or not device_id:
            return LicenseDecision(LicenseState.NEEDS_ACTIVATION, "Nhập key bản quyền để kích hoạt ứng dụng.")
        certificate = license_state.get("certificate")
        signature = str(license_state.get("signature") or "")
        if not isinstance(certificate, dict) or not signature:
            return LicenseDecision(LicenseState.NEEDS_ACTIVATION, "Nhập key bản quyền để kích hoạt ứng dụng.")
        try:
            self._verify_signature(certificate, signature)
        except (ValueError, InvalidSignature):
            return LicenseDecision(LicenseState.INVALID, "Dữ liệu bản quyền trên máy không hợp lệ. Hãy kích hoạt lại key.")
        if certificate.get("v") != 1 or certificate.get("status") != "active":
            return LicenseDecision(LicenseState.INVALID, "Chứng nhận bản quyền không hợp lệ. Hãy kích hoạt lại key.")
        if certificate.get("device_hash") != device_hash(device_id):
            return LicenseDecision(LicenseState.INVALID, "Key này được kích hoạt trên thiết bị khác. Hãy kích hoạt lại key.")
        now = datetime.now(UTC)
        expires_at = _parse_time(certificate.get("expires_at"))
        if expires_at is not None and expires_at <= now:
            return LicenseDecision(LicenseState.EXPIRED, "Key bản quyền đã hết hạn.", certificate, signature)
        check_after = _parse_time(certificate.get("check_after"))
        if check_after is None:
            return LicenseDecision(LicenseState.INVALID, "Chứng nhận bản quyền thiếu thời điểm kiểm tra.")
        if check_after <= now:
            return LicenseDecision(LicenseState.REQUIRES_REVALIDATION, "Cần kết nối Internet để xác thực lại key bản quyền.", certificate, signature)
        return LicenseDecision(LicenseState.ACTIVE_OFFLINE, _active_message(certificate), certificate, signature)

    def activate(self, key: str, device_id: str, device_label: str) -> LicenseDecision:
        payload = self._post("/api/activate", {"key": key.strip(), "deviceId": device_id, "deviceLabel": device_label, "appVersion": VERSION})
        return self._decision_from_response(payload, device_id)

    def revalidate(self, license_id: str, device_id: str) -> LicenseDecision:
        payload = self._post("/api/validate", {"licenseId": license_id, "deviceId": device_id, "appVersion": VERSION})
        return self._decision_from_response(payload, device_id)

    def _decision_from_response(self, payload: dict[str, Any], device_id: str) -> LicenseDecision:
        if payload.get("error"):
            return LicenseDecision(_state_from_server_error(str(payload["error"])), str(payload["error"]))
        certificate = payload.get("certificate")
        signature = str(payload.get("signature") or "")
        if not isinstance(certificate, dict) or not signature:
            return LicenseDecision(LicenseState.INVALID, "Máy chủ trả về dữ liệu bản quyền không hợp lệ.")
        evaluated = self.evaluate({"certificate": certificate, "signature": signature}, device_id)
        return LicenseDecision(evaluated.state, evaluated.message, certificate, signature)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enforced:
            return {"error": "Ứng dụng chưa được cấu hình máy chủ bản quyền."}
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            f"{self.configuration.service_url.rstrip('/')}{path}",
            data=body,
            headers={"Accept": "application/json", "Content-Type": "application/json", "User-Agent": f"CheckVehicleOCR/{VERSION}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            return {"error": "Không thể kết nối máy chủ bản quyền. Kiểm tra Internet rồi thử lại.", "network_error": True}
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"error": "Máy chủ bản quyền trả về dữ liệu không hợp lệ."}
        return decoded if isinstance(decoded, dict) else {"error": "Máy chủ bản quyền trả về dữ liệu không hợp lệ."}

    def _verify_signature(self, certificate: dict[str, Any], signature: str) -> None:
        key = Ed25519PublicKey.from_public_bytes(_base64url_decode(self.configuration.signing_public_key_b64))
        key.verify(_base64url_decode(signature), canonical_certificate(certificate))


def _active_message(certificate: dict[str, Any]) -> str:
    expires_at = _parse_time(certificate.get("expires_at"))
    if expires_at is None:
        return "Key vĩnh viễn đang hoạt động."
    return f"Key đang hoạt động đến {expires_at.astimezone().strftime('%d/%m/%Y')}."


def _state_from_server_error(message: str) -> LicenseState:
    lowered = message.lower()
    if "thu hồi" in lowered:
        return LicenseState.REVOKED
    if "hết hạn" in lowered:
        return LicenseState.EXPIRED
    if "kết nối" in lowered:
        return LicenseState.NETWORK_ERROR
    if "thiết bị" in lowered:
        return LicenseState.INVALID
    return LicenseState.NEEDS_ACTIVATION


def _parse_time(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    normalized = value.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(normalized + "=" * (-len(normalized) % 4), validate=True)


__all__ = [
    "LicenseConfiguration",
    "LicenseDecision",
    "LicenseService",
    "LicenseState",
    "bundled_license_configuration",
    "canonical_certificate",
    "device_hash",
    "license_service_is_configured",
    "new_device_id",
]
