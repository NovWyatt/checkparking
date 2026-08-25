from __future__ import annotations

import base64
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

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.license_service import LicenseConfiguration, LicenseService, canonical_certificate, device_hash


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _signed_state(private_key: Ed25519PrivateKey, device_id: str, *, check_after: datetime) -> dict[str, object]:
    certificate = {
        "check_after": check_after.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "device_hash": device_hash(device_id),
        "expires_at": None,
        "issued_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "license_id": "11111111-1111-4111-8111-111111111111",
        "license_type": "perpetual",
        "status": "active",
        "v": 1,
    }
    return {"certificate": certificate, "signature": _base64url(private_key.sign(canonical_certificate(certificate)))}


def main() -> int:
    with tempfile.TemporaryDirectory() as appdata:
        original_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = appdata
        app = CheckVehicleApp()
        try:
            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            app.license_service = LicenseService(LicenseConfiguration("https://license.example.test", _base64url(public_key)))
            app.license_device_id = "installation-id-for-app-license-test"
            app.license_state = _signed_state(private_key, app.license_device_id, check_after=datetime.now(UTC) + timedelta(days=7))
            assert app._license_operation_allowed()
            assert app.license_status_var.get() == "Bản quyền đang hoạt động"

            app.license_state = _signed_state(private_key, app.license_device_id, check_after=datetime.now(UTC) - timedelta(seconds=1))
            assert not app._license_operation_allowed()
            assert app.license_dialog is not None and app.license_dialog.winfo_exists()
            app.license_dialog.destroy()
            app.license_dialog = None

            app._license_operation_allowed = lambda: False
            app._start_processing([Path("not-used.jpg")])
            assert app.worker is None
            app.results = [object()]
            app._export_results(reviewed=False)
            assert app.export_worker is None
            app.start_reconciliation()
            assert app.reconciliation_worker is None
        finally:
            app.destroy()
            if original_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = original_appdata
    print("license_app_integration_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
