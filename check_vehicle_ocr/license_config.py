"""Public configuration for the Check Vehicle OCR license service.

Only the Cloudflare Worker URL and Ed25519 public key belong here.  The
private signing key, key HMAC pepper and administrator code always stay in
Cloudflare Worker Secrets and must never be placed in this repository.
"""

from __future__ import annotations

LICENSE_SERVICE_URL = "https://license.wyattos.cyou"
LICENSE_SIGNING_PUBLIC_KEY_B64 = "4l8mBnX-XYjJb0dI2fsjKBoAprgLo_01awc-tryXlIU"


def license_service_is_configured() -> bool:
    """Return whether this distributable is configured to require a license."""

    return bool(LICENSE_SERVICE_URL.strip() and LICENSE_SIGNING_PUBLIC_KEY_B64.strip())
