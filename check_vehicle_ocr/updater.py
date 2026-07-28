from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from urllib.parse import urlparse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


GITHUB_API_ROOT = "https://api.github.com"


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    release_notes: str
    download_url: str
    sha256: str
    asset_name: str = ""


@dataclass(frozen=True)
class GitHubReleaseAsset:
    name: str
    download_url: str
    sha256: str = ""
    size: int = 0


@dataclass(frozen=True)
class GitHubRelease:
    version: str
    release_notes: str
    html_url: str
    assets: tuple[GitHubReleaseAsset, ...]


@dataclass(frozen=True)
class PendingInstallerUpdate:
    package_path: str
    package_sha256: str
    install_dir: str
    executable_path: str
    parent_pid: int
    created_at: str


def parse_manifest(payload: str | bytes) -> UpdateManifest:
    data = json.loads(payload)
    required = ("version", "release_notes", "download_url", "sha256")
    if not isinstance(data, dict) or any(not isinstance(data.get(key), str) or not data[key].strip() for key in required):
        raise ValueError("Manifest cập nhật thiếu version, release_notes, download_url hoặc sha256.")
    checksum = data["sha256"].lower()
    if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
        raise ValueError("SHA-256 trong manifest không hợp lệ.")
    return UpdateManifest(
        data["version"].strip(),
        data["release_notes"].strip(),
        data["download_url"].strip(),
        checksum,
        str(data.get("asset_name") or "").strip(),
    )


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

        primary = destination_dir / _download_filename(manifest)
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


def _download_filename(manifest: UpdateManifest) -> str:
    candidate = manifest.asset_name.strip() or Path(urlparse(manifest.download_url).path).name
    candidate = candidate.replace("\\", "_").replace("/", "_")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    candidate = "".join(character if character in allowed else "_" for character in candidate)
    return candidate or f"CheckVehicleOCR-{manifest.version}.download"


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
    token: str = "",
) -> GitHubRelease:
    api_url = github_latest_release_api(repository)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "CheckVehicleOCR-Updater"}
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    request = urllib.request.Request(api_url, headers=headers)
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
            if name and download_url:
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


def select_windows_release_asset(
    release: GitHubRelease,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
    timeout: float = 15.0,
    token: str = "",
) -> UpdateManifest:
    """Choose a verified Windows release *asset*, never GitHub source archives."""
    candidates = [asset for asset in release.assets if _is_windows_installer_asset(asset)]
    if not candidates:
        raise ValueError("Release chưa có gói Windows với SHA-256 do nhà phát hành cung cấp.")
    # Prefer the installer naming convention used by this project, then use a
    # deterministic lexical order instead of guessing from source archives.
    candidates.sort(key=lambda asset: ("setup" not in asset.name.lower() and "installer" not in asset.name.lower(), asset.name.lower()))
    asset = candidates[0]
    checksum = asset.sha256 or _checksum_from_release_asset(release, asset.name, opener=opener, timeout=timeout, token=token)
    if not checksum:
        raise ValueError("Release chưa có SHA-256 cho gói Windows. Không tải gói chưa xác minh.")
    return UpdateManifest(release.version, release.release_notes, asset.download_url, checksum, asset.name)


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


def _checksum_from_release_asset(
    release: GitHubRelease,
    expected_name: str,
    *,
    opener: Callable[..., object],
    timeout: float,
    token: str,
) -> str:
    """Read a release-provided SHA256SUMS file when GitHub omits ``digest``."""
    sums = next((item for item in release.assets if item.name.lower() in {"sha256sums.txt", "sha256sums"}), None)
    if sums is None:
        return ""
    headers = {"User-Agent": "CheckVehicleOCR-Updater"}
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    request = urllib.request.Request(sums.download_url, headers=headers)
    try:
        with opener(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    for line in payload.splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) != 2:
            continue
        checksum, filename = fields[0].lower(), fields[1].lstrip(" *")
        if filename == expected_name and len(checksum) == 64 and all(character in "0123456789abcdef" for character in checksum):
            return checksum
    return ""


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


def write_pending_installer_update(
    package: Path,
    manifest: UpdateManifest,
    *,
    install_dir: Path,
    executable_path: Path,
    state_dir: Path,
    parent_pid: int | None = None,
) -> Path:
    """Atomically record a verified, user-approved installer update."""
    if package.suffix.lower() not in {".exe", ".msi"}:
        raise ValueError("Chỉ có thể tự cài gói installer Windows đã xác minh.")
    if not package.is_file() or _sha256_file(package) != manifest.sha256:
        raise ValueError("Gói cập nhật không còn khớp SHA-256; không tạo yêu cầu cài đặt.")
    from datetime import datetime, timezone

    pending = PendingInstallerUpdate(
        package_path=str(package.resolve()),
        package_sha256=manifest.sha256,
        install_dir=str(install_dir.resolve()),
        executable_path=str(executable_path.resolve()),
        parent_pid=int(parent_pid or os.getpid()),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    path = state_dir / "pending-installer-update.json"
    _atomic_json_write(path, asdict(pending))
    return path


def read_pending_installer_update(path: Path) -> PendingInstallerUpdate | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return None
        return PendingInstallerUpdate(**{key: value[key] for key in PendingInstallerUpdate.__dataclass_fields__})
    except (OSError, ValueError, KeyError, TypeError):
        return None


def recover_pending_installer_update(path: Path) -> str:
    """Restore a backup only when an interrupted helper left no install dir.

    It never overwrites an existing new install.  This makes recovery safe to
    call on startup after a power interruption without second-guessing an
    update that already passed the helper health check.
    """
    pending = read_pending_installer_update(path)
    if pending is None:
        return "none"
    install_dir = Path(pending.install_dir)
    backup = install_dir.with_name(f"{install_dir.name}.update-backup")
    if not backup.is_dir() or install_dir.exists():
        return "none"
    try:
        shutil.move(str(backup), str(install_dir))
        return "restored"
    except OSError:
        return "failed"


def launch_pending_installer_update(
    pending_path: Path,
    *,
    launcher: Callable[..., object] = subprocess.Popen,
) -> Path:
    """Start a separate PowerShell helper after the user chooses install.

    It waits for the GUI process, keeps an installation-directory backup, runs
    the verified Inno/MSI installer, then starts the new executable.  The
    helper is external so Windows can replace the application executable.
    """
    pending = read_pending_installer_update(pending_path)
    if pending is None:
        raise ValueError("Không đọc được yêu cầu cập nhật đang chờ.")
    helper = pending_path.with_name("apply-pending-update.ps1")
    log = pending_path.with_name("update-helper.log")
    helper.write_text(_powershell_update_helper(pending, pending_path, log), encoding="utf-8")
    launcher(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(helper)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=False,
    )
    return helper


def _atomic_json_write(path: Path, payload: dict[str, object]) -> None:
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False, mode="w", encoding="utf-8") as file:
            temporary = Path(file.name)
            json.dump(payload, file, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)


def _ps(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _powershell_update_helper(pending: PendingInstallerUpdate, pending_path: Path, log_path: Path) -> str:
    return f"""$ErrorActionPreference = 'Stop'
$package = {_ps(pending.package_path)}
$installDir = {_ps(pending.install_dir)}
$exe = {_ps(pending.executable_path)}
$pending = {_ps(str(pending_path))}
$log = {_ps(str(log_path))}
$backup = "$installDir.update-backup"
try {{
  while (Get-Process -Id {pending.parent_pid} -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 300 }}
  if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $installDir)) {{ Move-Item -LiteralPath $backup -Destination $installDir -Force }}
  if (Test-Path -LiteralPath $backup) {{ Remove-Item -LiteralPath $backup -Recurse -Force }}
  if (Test-Path -LiteralPath $installDir) {{ Copy-Item -LiteralPath $installDir -Destination $backup -Recurse -Force }}
  $result = Start-Process -FilePath $package -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru
  if ($result.ExitCode -ne 0) {{ throw "Installer exit code $($result.ExitCode)" }}
  if (-not (Test-Path -LiteralPath $exe)) {{ throw 'Updated executable was not found.' }}
  $health = Start-Process -FilePath $exe -ArgumentList '--runtime-health-check' -Wait -PassThru
  if ($health.ExitCode -ne 0) {{ throw "Updated application health check failed with code $($health.ExitCode)" }}
  Start-Process -FilePath $exe | Out-Null
  if (Test-Path -LiteralPath $backup) {{ Remove-Item -LiteralPath $backup -Recurse -Force }}
  Remove-Item -LiteralPath $pending -Force -ErrorAction SilentlyContinue
  'Update installed' | Out-File -LiteralPath $log -Append -Encoding utf8
}} catch {{
  if (Test-Path -LiteralPath $installDir) {{ Remove-Item -LiteralPath $installDir -Recurse -Force }}
  if (Test-Path -LiteralPath $backup) {{ Move-Item -LiteralPath $backup -Destination $installDir -Force }}
  if (Test-Path -LiteralPath $exe) {{ Start-Process -FilePath $exe | Out-Null }}
  $_ | Out-File -LiteralPath $log -Append -Encoding utf8
}}
"""
