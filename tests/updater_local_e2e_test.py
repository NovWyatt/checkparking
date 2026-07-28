from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.updater import compare_versions, download_verified, fetch_manifest


class _Handler(BaseHTTPRequestHandler):
    payload = b"verified update payload"
    manifest: bytes = b""

    def do_GET(self):
        if self.path == "/manifest.json":
            self._send(200, self.manifest)
        elif self.path == "/package.bin":
            self._send(200, self.payload)
        elif self.path == "/bad-checksum.bin":
            self._send(200, self.payload)
        elif self.path == "/interrupted.bin":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(self.payload) + 100))
            self.end_headers()
            self.wfile.write(self.payload[:5])
            self.wfile.flush()
            self.connection.close()
        else:
            self.send_error(404)

    def _send(self, status: int, payload: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json" if self.path.endswith("json") else "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        pass


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        _Handler.manifest = json.dumps(
            {
                "version": "9.9.9",
                "release_notes": "manifest local",
                "download_url": f"{base}/package.bin",
                "sha256": hashlib.sha256(_Handler.payload).hexdigest(),
            }
        ).encode("utf-8")
        manifest = fetch_manifest(f"{base}/manifest.json", timeout=2)
        assert manifest.version == "9.9.9" and compare_versions(manifest.version, "1.6.12") > 0
        assert compare_versions("1.6.12", "1.6.12") == 0 and compare_versions("1.6.11", "1.6.12") < 0

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            first = download_verified(manifest, destination, timeout=2)
            assert first.read_bytes() == _Handler.payload

            # Existing different package is preserved; verified update receives
            # a checksum suffix instead of replacing an old file.
            first.write_bytes(b"old package")
            second = download_verified(manifest, destination, timeout=2)
            assert second != first and first.read_bytes() == b"old package" and second.read_bytes() == _Handler.payload

            bad = type(manifest)(manifest.version, manifest.release_notes, f"{base}/bad-checksum.bin", "0" * 64)
            try:
                download_verified(bad, destination, timeout=2)
            except ValueError:
                pass
            else:
                raise AssertionError("Checksum mismatch did not fail")
            assert not list(destination.glob(".check_vehicle_update_*.tmp"))

            interrupted = type(manifest)(manifest.version, manifest.release_notes, f"{base}/interrupted.bin", hashlib.sha256(_Handler.payload).hexdigest())
            try:
                download_verified(interrupted, destination, timeout=2)
            except Exception:
                pass
            else:
                raise AssertionError("Interrupted download did not fail")
            assert not list(destination.glob(".check_vehicle_update_*.tmp"))
    finally:
        server.shutdown()
        server.server_close()
    print("updater_local_e2e_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
