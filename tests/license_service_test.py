from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_vehicle_ocr.license_service import (
    LicenseConfiguration,
    LicenseService,
    LicenseState,
    canonical_certificate,
    device_hash,
)
from check_vehicle_ocr.config import migrate_settings, save_settings, settings_path


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _signed_state(private_key, device_id: str, *, check_after: datetime, expires_at: datetime | None = None) -> dict[str, object]:
    certificate = {
        "check_after": check_after.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "device_hash": device_hash(device_id),
        "expires_at": expires_at.isoformat(timespec="milliseconds").replace("+00:00", "Z") if expires_at else None,
        "issued_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "license_id": "11111111-1111-4111-8111-111111111111",
        "license_type": "time" if expires_at else "perpetual",
        "status": "active",
        "v": 1,
    }
    return {"certificate": certificate, "signature": _base64url(private_key.sign(canonical_certificate(certificate)))}


def main() -> int:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    service = LicenseService(LicenseConfiguration("https://license.example.test", _base64url(public_key)))
    device_id = "installation-id-for-license-test"
    now = datetime.now(UTC)

    active = service.evaluate(_signed_state(private_key, device_id, check_after=now + timedelta(days=7)), device_id)
    assert active.state is LicenseState.ACTIVE_OFFLINE and active.usable

    requires_revalidation = service.evaluate(_signed_state(private_key, device_id, check_after=now - timedelta(seconds=1)), device_id)
    assert requires_revalidation.state is LicenseState.REQUIRES_REVALIDATION and not requires_revalidation.usable

    expired = service.evaluate(
        _signed_state(private_key, device_id, check_after=now + timedelta(days=7), expires_at=now - timedelta(seconds=1)),
        device_id,
    )
    assert expired.state is LicenseState.EXPIRED

    mismatched_device = service.evaluate(_signed_state(private_key, device_id, check_after=now + timedelta(days=7)), "other-installation-id-for-test")
    assert mismatched_device.state is LicenseState.INVALID

    invalid_signature = _signed_state(private_key, device_id, check_after=now + timedelta(days=7))
    invalid_signature["signature"] = "A" * 86
    assert service.evaluate(invalid_signature, device_id).state is LicenseState.INVALID

    not_configured = LicenseService(LicenseConfiguration("", "")).evaluate({}, "")
    assert not_configured.state is LicenseState.NOT_CONFIGURED and not_configured.usable

    raw_key = "CVOCR-ABCD-EFGH-JKLM-NPQR-STUV"
    migrated = migrate_settings(
        {
            "license": {
                "device_id": device_id,
                "certificate": active.certificate,
                "signature": active.signature,
                "key": raw_key,
            }
        }
    )
    assert set(migrated["license"]) == {"device_id", "certificate", "signature"}
    with tempfile.TemporaryDirectory() as appdata:
        original_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = appdata
        try:
            save_settings(migrated)
            assert raw_key not in settings_path().read_text(encoding="utf-8")
        finally:
            if original_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = original_appdata

    canonical = json.loads(canonical_certificate(_signed_state(private_key, device_id, check_after=now + timedelta(days=7))["certificate"]).decode("utf-8"))
    assert list(canonical) == ["check_after", "device_hash", "expires_at", "issued_at", "license_id", "license_type", "status", "v"]
    print("license_service_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
