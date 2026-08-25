"""Generate the Ed25519 key pair used by the Cloudflare license Worker.

Run this locally only when configuring a new Worker.  The private value is a
Cloudflare Secret and must never be written to a repository, release archive,
settings file, or issue.  The public value is safe to copy into
``check_vehicle_ocr/license_config.py`` before building a release.
"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def main() -> int:
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    print("Cloudflare Secret LICENSE_SIGNING_PRIVATE_KEY_B64:")
    print(_base64url(private_bytes))
    print()
    print("Public value for check_vehicle_ocr/license_config.py:")
    print(_base64url(public_bytes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
