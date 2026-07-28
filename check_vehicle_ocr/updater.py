from __future__ import annotations

import hashlib
import json
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


GITHUB_API_ROOT = "https://api.github.com"


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    release_notes: str
    download_url: str
    sha256: str


@dataclass(frozen=True)
class GitHubReleaseAsset:
    name: str
    download_url: str
    sha256: str
    size: int = 0


@dataclass(frozen=True)
class GitHubRelease:
    version: str
    release_notes: str
    html_url: str
    assets: tuple[GitHubReleaseAsset, ...]


def parse_manifest(payload: str | bytes) -> UpdateManifest:
    data = json.loads(payload)
    required = ("version", "release_notes", "download_url", "sha256")
    if not isinstance(data, dict) or any(not isinstance(data.get(key), str) or not data[key].strip() for key in required):
        raise ValueError("Manifest cập nhật thiếu version, release_notes, download_url hoặc sha256.")
    checksum = data["sha256"].lower()
    if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
        raise ValueError("SHA-256 trong manifest không hợp lệ.")
    return UpdateManifest(data["version"].strip(), data["release_notes"].strip(), data["download_url"].strip(), checksum)


def fetch_manifest(
    manifest_url: str,
    timeout: float = 15.0,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> UpdateManifest:
    if not manifest_url.strip():
        raise ValueError("Chưa cấu hình manifest URL cập nhật.")
    with opener(manifest_url, timeout=timeout) as response:
        return parse_manifest(response.read())


def download_verified(
    manifest: UpdateManifest,
    destination_dir: Path,
    timeout: float = 60.0,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        digest = hashlib.sha256()
        with opener(manifest.download_url, timeout=timeout) as response:
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


def normalize_github_repository(value: str) -> str:
    """Return ``owner/repository`` from a supported GitHub repository input.

    This deliberately accepts only GitHub repository addresses.  A release
    source is configuration, not a generic URL redirector, so accepting extra
    path segments would make the update target ambiguous.
    """
    raw = str(value or "").strip().rstrip("/")
    if raw.endswith(".git"):
        raw = raw[:-4]
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix) :]
            break
    parts = [part for part in raw.split("/") if part]
    if len(parts) != 2 or any(part in {".", ".."} for part in parts):
        raise ValueError("Nhập repository theo dạng owner/repository hoặc URL GitHub của repository.")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if any(any(character not in allowed for character in part) for part in parts):
        raise ValueError("Tên owner/repository GitHub không hợp lệ.")
    return "/".join(parts)


def github_latest_release_api(value: str) -> str:
    repository = normalize_github_repository(value)
    return f"{GITHUB_API_ROOT}/repos/{repository}/releases/latest"


def fetch_github_latest_release(
    repository: str,
    timeout: float = 15.0,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> GitHubRelease:
    api_url = github_latest_release_api(repository)
    request = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json", "User-Agent": "CheckVehicleOCR-Updater"})
    with opener(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise ValueError("GitHub Releases trả về dữ liệu không hợp lệ.")
    version = str(payload.get("tag_name") or payload.get("name") or "").strip()
    if not version:
        raise ValueError("Release GitHub không có phiên bản/tag hợp lệ.")
    assets: list[GitHubReleaseAsset] = []
    raw_assets = payload.get("assets")
    if isinstance(raw_assets, list):
        for raw_asset in raw_assets:
            if not isinstance(raw_asset, dict):
                continue
            name = str(raw_asset.get("name") or "").strip()
            download_url = str(raw_asset.get("browser_download_url") or "").strip()
            checksum = _github_sha256(str(raw_asset.get("digest") or ""))
            if name and download_url and checksum:
                assets.append(
                    GitHubReleaseAsset(
                        name=name,
                        download_url=download_url,
                        sha256=checksum,
                        size=_safe_asset_size(raw_asset.get("size")),
                    )
                )
    return GitHubRelease(
        version=version,
        release_notes=str(payload.get("body") or "").strip(),
        html_url=str(payload.get("html_url") or "").strip(),
        assets=tuple(assets),
    )


def select_windows_release_asset(release: GitHubRelease) -> UpdateManifest:
    """Choose a verified Windows release *asset*, never GitHub source archives."""
    candidates = [asset for asset in release.assets if _is_windows_installer_asset(asset)]
    if not candidates:
        raise ValueError("Release chưa có gói Windows với SHA-256 do nhà phát hành cung cấp.")
    # Prefer the installer naming convention used by this project, then use a
    # deterministic lexical order instead of guessing from source archives.
    candidates.sort(key=lambda asset: ("setup" not in asset.name.lower() and "installer" not in asset.name.lower(), asset.name.lower()))
    asset = candidates[0]
    return UpdateManifest(release.version, release.release_notes, asset.download_url, asset.sha256)


def sanitize_update_error(error: BaseException | str) -> str:
    """Map transport details to an operator-safe message.

    Full exception paths (including ``WinError 2`` local paths) are not useful
    in the main UI and can reveal configuration details.  Callers may log the
    exception type only in a debug log.
    """
    message = str(error).lower()
    if "401" in message or "403" in message:
        return "Nguồn cập nhật từ chối truy cập. Kiểm tra quyền truy cập hoặc repository."
    if "404" in message:
        return "Không tìm thấy nguồn cập nhật. Kiểm tra lại repository hoặc manifest."
    if "checksum" in message or "sha-256" in message:
        return "Không thể xác minh tính toàn vẹn của gói cập nhật. File chưa được lưu."
    if "chưa cấu hình" in message:
        return "Chưa cấu hình nguồn cập nhật ứng dụng."
    return "Không thể kiểm tra hoặc tải cập nhật. Kiểm tra nguồn và thử lại."


def _github_sha256(value: str) -> str:
    prefix, separator, checksum = value.strip().lower().partition(":")
    if prefix != "sha256" or not separator or len(checksum) != 64:
        return ""
    return checksum if all(character in "0123456789abcdef" for character in checksum) else ""


def _is_windows_installer_asset(asset: GitHubReleaseAsset) -> bool:
    name = asset.name.lower()
    if not name.endswith((".exe", ".msi", ".zip")):
        return False
    if name in {"source code.zip", "source code.tar.gz"} or "source" in name and "checkvehicle" not in name:
        return False
    # ZIP is accepted only when it is a explicitly named Windows project asset,
    # never a GitHub-generated source archive.
    if name.endswith(".zip") and not any(marker in name for marker in ("win", "windows", "setup", "installer")):
        return False
    return any(marker in name for marker in ("checkvehicle", "check_vehicle", "setup", "installer", "win", "windows"))


def _safe_asset_size(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
