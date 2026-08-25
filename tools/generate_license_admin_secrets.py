"""Create non-persistent Cloudflare secret values for the license Worker.

The administrator code is entered twice without echoing it.  This helper never
writes a file and never prints the administrator code itself.  Treat every
printed value as a secret and enter it only into the matching Wrangler prompt.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from getpass import getpass


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def main() -> int:
    code = getpass("Nhập mã quản trị mới: ")
    confirmation = getpass("Nhập lại mã quản trị: ")
    if not code or code != confirmation:
        print("Mã quản trị trống hoặc không khớp. Không tạo giá trị nào.")
        return 1
    print("ADMIN_CODE_SHA256")
    print(_base64url(hashlib.sha256(code.encode("utf-8")).digest()))
    print()
    print("ADMIN_SESSION_SECRET")
    print(secrets.token_urlsafe(48))
    print()
    print("LICENSE_KEY_PEPPER")
    print(secrets.token_urlsafe(48))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
