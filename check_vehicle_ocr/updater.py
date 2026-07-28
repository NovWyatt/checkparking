from __future__ import annotations

import hashlib
import json
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    release_notes: str
    download_url: str
    sha256: str


def parse_manifest(payload: str | bytes) -> UpdateManifest:
    data = json.loads(payload)
    required = ("version", "release_notes", "download_url", "sha256")
    if not isinstance(data, dict) or any(not isinstance(data.get(key), str) or not data[key].strip() for key in required):
        raise ValueError("Manifest cập nhật thiếu version, release_notes, download_url hoặc sha256.")
    checksum = data["sha256"].lower()
    if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
        raise ValueError("SHA-256 trong manifest không hợp lệ.")
    return UpdateManifest(data["version"].strip(), data["release_notes"].strip(), data["download_url"].strip(), checksum)


def fetch_manifest(manifest_url: str, timeout: float = 15.0) -> UpdateManifest:
    if not manifest_url.strip():
        raise ValueError("Chưa cấu hình manifest URL cập nhật.")
    with urllib.request.urlopen(manifest_url, timeout=timeout) as response:
        return parse_manifest(response.read())


def download_verified(manifest: UpdateManifest, destination_dir: Path, timeout: float = 60.0) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        digest = hashlib.sha256()
        with urllib.request.urlopen(manifest.download_url, timeout=timeout) as response:
            with tempfile.NamedTemporaryFile(dir=destination_dir, prefix=".check_vehicle_update_", suffix=".tmp", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                while chunk := response.read(1024 * 1024):
                    temporary.write(chunk)
                    digest.update(chunk)
        if digest.hexdigest() != manifest.sha256:
            raise ValueError("Checksum cập nhật không khớp; không lưu file tải về.")

        primary = destination_dir / f"CheckVehicleOCR-{manifest.version}.download"
        destination = _safe_destination(primary, manifest.sha256)
        if destination.exists():
            if _sha256_file(destination) == manifest.sha256:
                return destination
            raise RuntimeError("Không thể chọn tên file cập nhật an toàn mà không ghi đè package cũ.")
        temporary_path.replace(destination)
        temporary_path = None
        return destination
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def compare_versions(candidate: str, current: str) -> int:
    """Compare release-like versions without introducing a packaging dependency."""
    candidate_parts = _version_parts(candidate)
    current_parts = _version_parts(current)
    width = max(len(candidate_parts), len(current_parts))
    return (candidate_parts + (0,) * (width - len(candidate_parts)) > current_parts + (0,) * (width - len(current_parts))) - (
        candidate_parts + (0,) * (width - len(candidate_parts)) < current_parts + (0,) * (width - len(current_parts))
    )


def _version_parts(value: str) -> tuple[int, ...]:
    pieces = []
    for part in str(value).strip().lstrip("vV").split("."):
        digits = "".join(character for character in part if character.isdigit())
        if not digits:
            break
        pieces.append(int(digits))
    if not pieces:
        raise ValueError(f"Version không hợp lệ: {value}")
    return tuple(pieces)


def _safe_destination(primary: Path, checksum: str) -> Path:
    if not primary.exists():
        return primary
    if _sha256_file(primary) == checksum:
        return primary
    return primary.with_name(f"{primary.stem}-{checksum[:12]}{primary.suffix}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
