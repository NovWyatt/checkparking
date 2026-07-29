"""Safe, offline-testable helpers for the operator-facing Update Center.

Nothing in this module changes the running Python environment or active OCR
models.  Package/model staging is intentionally a separate, explicit step so
the UI can describe what will happen before an operator approves it.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .ocr_models import DEFAULT_MODEL_PROFILE, PP_OCRV5_MOBILE, PP_OCRV6_TINY


PYPI_PADDLEOCR_URL = "https://pypi.org/pypi/paddleocr/json"
PROJECT_GITHUB_REPOSITORY = "NovWyatt/checkparking"
DEFAULT_TESSERACT_MANIFEST_URL = (
    f"https://github.com/{PROJECT_GITHUB_REPOSITORY}/releases/latest/download/"
    "tesseract-component-manifest.json"
)
DEFAULT_MODEL_MANIFEST_URL = (
    f"https://github.com/{PROJECT_GITHUB_REPOSITORY}/releases/latest/download/"
    "model-manifest.json"
)
MAX_TESSERACT_ARCHIVE_BYTES = 250 * 1024 * 1024
MAX_TESSERACT_EXTRACTED_BYTES = 500 * 1024 * 1024
MAX_TESSERACT_ARCHIVE_FILES = 256


@dataclass(frozen=True)
class PaddleRuntimeInfo:
    paddleocr_version: str
    paddlepaddle_version: str
    compatibility: str
    paddlex_version: str = ""


@dataclass(frozen=True)
class PaddleRelease:
    version: str
    source_url: str
    release_notes_url: str


@dataclass(frozen=True)
class ModelInfo:
    role: str
    name: str
    path: Path | None
    source: str
    checksum: str | None
    active: bool
    version: str | None
    downloaded_at: str | None


@dataclass(frozen=True)
class PaddleStagingPlan:
    version: str
    paddlepaddle_version: str
    stage_dir: Path
    steps: tuple[str, ...]


@dataclass(frozen=True)
class ModelUpdateManifest:
    version: str
    detection_model: str
    recognition_model: str
    download_url: str
    sha256: str


@dataclass(frozen=True)
class ModelStageResult:
    version: str
    stage_dir: Path
    verified: bool
    message: str


@dataclass(frozen=True)
class TesseractPackageManifest:
    version: str
    platform: str
    download_url: str
    sha256: str
    archive_type: str
    license: str
    source: str
    schema_version: int = 0
    component: str = "tesseract"
    archive: str = ""
    entrypoint: str = ""
    tessdata_dir: str = ""
    languages: tuple[str, ...] = ()
    files: tuple["TesseractComponentFile", ...] = ()


@dataclass(frozen=True)
class TesseractComponentFile:
    """A content-addressed file within a portable component root."""

    path: str
    sha256: str
    size_bytes: int


def installed_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        module_name = {"paddlepaddle": "paddle", "paddleocr": "paddleocr", "paddlex": "paddlex"}.get(distribution, distribution)
        try:
            module = importlib.import_module(module_name)
            version = str(getattr(module, "__version__", "")).strip()
            return version or "Chưa cài"
        except Exception:
            return "Chưa cài"


def paddle_runtime_info() -> PaddleRuntimeInfo:
    paddleocr_version = installed_version("paddleocr")
    paddlepaddle_version = installed_version("paddlepaddle")
    paddlex_version = installed_version("paddlex")
    if paddleocr_version == "Chưa cài":
        compatibility = "PaddleOCR chưa được cài. Không thể kiểm tra tương thích."
    elif paddlepaddle_version == "Chưa cài":
        compatibility = "Chưa xác định PaddlePaddle. Cần thử nghiệm trong môi trường staging."
    else:
        compatibility = "Chưa suy đoán tương thích chỉ theo phiên bản; cần smoke test và benchmark staging."
    return PaddleRuntimeInfo(paddleocr_version, paddlepaddle_version, compatibility, paddlex_version)


def fetch_paddle_release(
    source_url: str = PYPI_PADDLEOCR_URL,
    timeout: float = 15.0,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> PaddleRelease:
    if not source_url.strip():
        raise ValueError("Chưa cấu hình nguồn kiểm tra PaddleOCR.")
    with opener(source_url, timeout=timeout) as response:
        payload = json.loads(response.read())
    info = payload.get("info") if isinstance(payload, dict) else None
    if not isinstance(info, dict) or not isinstance(info.get("version"), str) or not info["version"].strip():
        raise ValueError("Nguồn PaddleOCR không trả về phiên bản hợp lệ.")
    project_urls = info.get("project_urls") if isinstance(info.get("project_urls"), dict) else {}
    notes_url = str(project_urls.get("Release notes") or project_urls.get("Homepage") or source_url)
    return PaddleRelease(version=info["version"].strip(), source_url=source_url.strip(), release_notes_url=notes_url)


def paddle_model_inventory() -> tuple[ModelInfo, ...]:
    """Report local Paddle text models without downloading or hashing all weights.

    The available checksum is deliberately ``None``: a full checksum needs a
    verified upstream manifest and must not be invented from a partial file.
    """
    roots = (Path(__file__).resolve().parents[1], Path.home() / ".paddlex")
    entries = (
        ("Nhận diện chữ", DEFAULT_MODEL_PROFILE.detection_model),
        ("Đọc chữ", DEFAULT_MODEL_PROFILE.recognition_model),
        ("Tiết kiệm tài nguyên", PP_OCRV6_TINY.recognition_model),
        ("Model dự phòng", PP_OCRV5_MOBILE.recognition_model),
    )
    result: list[ModelInfo] = []
    for role, name in entries:
        model_path = _find_model_path(roots, name)
        result.append(
            ModelInfo(
                role=role,
                name=name,
                path=model_path,
                source="Cache cục bộ" if model_path else "Chưa tìm thấy trong cache cục bộ",
                checksum=None,
                active=bool(model_path and name in {DEFAULT_MODEL_PROFILE.detection_model, DEFAULT_MODEL_PROFILE.recognition_model}),
                version="Không có manifest version" if model_path else None,
                downloaded_at=_model_date(model_path),
            )
        )
    return tuple(result)


def build_paddle_staging_plan(version: str, paddlepaddle_version: str = "") -> PaddleStagingPlan:
    candidate = str(version).strip()
    if not candidate:
        raise ValueError("Cần một phiên bản PaddleOCR cụ thể để chuẩn bị kiểm thử.")
    paddle_candidate = str(paddlepaddle_version).strip()
    suffix = f" và PaddlePaddle {paddle_candidate}" if paddle_candidate else " cùng PaddlePaddle tương thích"
    stage_dir = Path("update-staging") / f"paddleocr-{candidate}"
    return PaddleStagingPlan(
        version=candidate,
        paddlepaddle_version=paddle_candidate,
        stage_dir=stage_dir,
        steps=(
            f"Tạo môi trường thử nghiệm riêng tại {stage_dir / 'venv'}.",
            f"Cài PaddleOCR {candidate}{suffix}; không thay môi trường đang chạy.",
            "Chạy smoke test và benchmark synthetic trong môi trường thử nghiệm.",
            "Nếu có dataset thật, so sánh tốc độ và kết quả OCR trước khi cho phép chuyển phiên bản.",
            "Giữ phiên bản/model cũ để rollback; không chuyển phiên bản khi bất kỳ kiểm tra nào thất bại.",
        ),
    )


def parse_model_manifest(payload: str | bytes) -> ModelUpdateManifest:
    data = json.loads(payload)
    required = ("version", "detection_model", "recognition_model", "download_url", "sha256")
    if not isinstance(data, dict) or any(not isinstance(data.get(key), str) or not data[key].strip() for key in required):
        raise ValueError("Manifest model thiếu thông tin phiên bản, model, URL hoặc SHA-256.")
    checksum = data["sha256"].strip().lower()
    if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
        raise ValueError("SHA-256 của manifest model không hợp lệ.")
    return ModelUpdateManifest(
        version=data["version"].strip(),
        detection_model=data["detection_model"].strip(),
        recognition_model=data["recognition_model"].strip(),
        download_url=data["download_url"].strip(),
        sha256=checksum,
    )


def fetch_model_manifest(
    manifest_url: str,
    timeout: float = 15.0,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> ModelUpdateManifest:
    if not manifest_url.strip():
        raise ValueError("Chưa cấu hình nguồn model đã xác minh.")
    if not _is_project_manifest_url(manifest_url):
        raise ValueError("Model manifest source is not this project's GitHub Release.")
    with opener(manifest_url, timeout=timeout) as response:
        resolved = getattr(response, "geturl", lambda: manifest_url)()
        if resolved and not _is_project_manifest_redirect(str(resolved)):
            raise ValueError("Model manifest redirect is not permitted.")
        return parse_model_manifest(response.read())


def stage_model_archive(
    manifest: ModelUpdateManifest,
    destination_root: Path,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
    timeout: float = 60.0,
) -> ModelStageResult:
    """Download a model archive to a versioned staging folder, never active paths.

    The caller must run model smoke/benchmark validation before activation.
    ``opener`` is injectable so tests never need a network connection.
    """
    destination_root.mkdir(parents=True, exist_ok=True)
    stage_dir = destination_root / f"paddleocr-{manifest.version}"
    if stage_dir.exists():
        raise FileExistsError("Thư mục staging model đã tồn tại; không ghi đè model cũ.")
    temporary_path: Path | None = None
    try:
        digest = hashlib.sha256()
        with opener(manifest.download_url, timeout=timeout) as response:
            with tempfile.NamedTemporaryFile(dir=destination_root, prefix=".model_stage_", suffix=".tmp", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                while chunk := response.read(1024 * 1024):
                    temporary.write(chunk)
                    digest.update(chunk)
        if digest.hexdigest() != manifest.sha256:
            raise ValueError("Checksum model không khớp; không lưu model staging.")
        stage_dir.mkdir(parents=True)
        with zipfile.ZipFile(temporary_path) as archive:
            _safe_extract(archive, stage_dir)
        return ModelStageResult(manifest.version, stage_dir, True, "Đã stage model mới. Chưa kích hoạt model này.")
    except Exception:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        raise
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def _find_model_path(roots: tuple[Path, ...], name: str) -> Path | None:
    for root in roots:
        for parent in (root / "models" / "paddleocr", root / "official_models"):
            candidate = parent / name
            if candidate.is_dir() and (candidate / "inference.yml").exists():
                return candidate
    return None


def _model_date(model_path: Path | None) -> str | None:
    if model_path is None:
        return None
    try:
        return datetime.fromtimestamp((model_path / "inference.yml").stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        return None


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if target != root and root not in target.parents:
            raise ValueError("Archive model chứa đường dẫn không an toàn.")
    archive.extractall(destination)


def _safe_extract_tesseract(archive: zipfile.ZipFile, destination: Path) -> None:
    """Extract a component archive only after bounded, zip-slip-safe checks."""

    root = destination.resolve()
    members = archive.infolist()
    if len(members) > MAX_TESSERACT_ARCHIVE_FILES:
        raise ValueError("Tesseract archive contains too many files.")
    total = 0
    for member in members:
        total += max(0, int(member.file_size))
        if total > MAX_TESSERACT_EXTRACTED_BYTES:
            raise ValueError("Tesseract archive expands beyond the allowed size limit.")
        target = (destination / member.filename).resolve()
        mode = member.external_attr >> 16
        if target != root and root not in target.parents:
            raise ValueError("Tesseract archive contains an unsafe path.")
        if mode and (mode & 0o170000) == 0o120000:
            raise ValueError("Tesseract archive may not contain symbolic links.")
    archive.extractall(destination)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_tesseract_manifest(payload: str | bytes) -> TesseractPackageManifest:
    """Validate a project-controlled portable Tesseract package manifest.

    There is intentionally no default upstream binary URL.  The operator can
    always select an existing executable; downloading happens only when the
    project owner has configured a specific package and SHA-256.
    """
    data = json.loads(payload)
    required = ("version", "platform", "download_url", "sha256", "archive_type", "license", "source")
    if not isinstance(data, dict) or any(not isinstance(data.get(key), str) or not data[key].strip() for key in required):
        raise ValueError("Manifest Tesseract thiếu phiên bản, nguồn hoặc SHA-256.")
    checksum = data["sha256"].strip().lower()
    if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
        raise ValueError("SHA-256 của gói Tesseract không hợp lệ.")
    archive_type = data["archive_type"].strip().lower()
    schema_version = int(data.get("schema_version") or 0)
    component = str(data.get("component") or "tesseract").strip().lower()
    archive = str(data.get("archive") or "").strip()
    entrypoint = _component_relative_path(str(data.get("entrypoint") or ""))
    tessdata_dir = _component_relative_path(str(data.get("tessdata_dir") or ""))
    languages_value = data.get("languages") or ()
    languages = tuple(str(language).strip().lower() for language in languages_value if str(language).strip()) if isinstance(languages_value, list) else ()
    files = _parse_component_files(data.get("files"))
    if archive_type != "zip":
        raise ValueError("Chỉ hỗ trợ gói Tesseract portable dạng ZIP đã xác minh.")
    if schema_version >= 1:
        if component != "tesseract" or not archive or not entrypoint or not tessdata_dir:
            raise ValueError("Tesseract component manifest is missing required package fields.")
        if not files or "eng" not in languages or "osd" not in languages:
            raise ValueError("Tesseract component manifest is missing hashes or eng/osd language data.")
        if not _is_project_release_url(data["download_url"].strip()):
            raise ValueError("Tesseract component source is not this project's GitHub Release.")
    return TesseractPackageManifest(
        version=data["version"].strip(),
        platform=data["platform"].strip().lower(),
        download_url=data["download_url"].strip(),
        sha256=checksum,
        archive_type=archive_type,
        license=data["license"].strip(),
        source=data["source"].strip(),
        schema_version=schema_version,
        component=component,
        archive=archive,
        entrypoint=entrypoint,
        tessdata_dir=tessdata_dir,
        languages=languages,
        files=files,
    )


def fetch_tesseract_manifest(
    manifest_url: str,
    timeout: float = 15.0,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> TesseractPackageManifest:
    if not manifest_url.strip():
        raise ValueError("Chưa cấu hình nguồn gói Tesseract đã xác minh.")
    if not _is_project_manifest_url(manifest_url):
        raise ValueError("Tesseract manifest source is not this project's GitHub Release.")
    with opener(manifest_url, timeout=timeout) as response:
        resolved = getattr(response, "geturl", lambda: manifest_url)()
        if resolved and not _is_project_manifest_redirect(str(resolved)):
            raise ValueError("Tesseract manifest redirect is not permitted.")
        return parse_tesseract_manifest(response.read())


def _parse_component_files(value: object) -> tuple[TesseractComponentFile, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("Tesseract component file list is invalid.")
    parsed: list[TesseractComponentFile] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Tesseract component file list is invalid.")
        path = _component_relative_path(str(item.get("path") or ""))
        checksum = str(item.get("sha256") or "").strip().lower()
        size = item.get("size_bytes")
        if not path or not _is_sha256(checksum) or not isinstance(size, int) or size < 0 or path in seen:
            raise ValueError("Tesseract component file hash or size is invalid.")
        seen.add(path)
        parsed.append(TesseractComponentFile(path, checksum, size))
    return tuple(parsed)


def _component_relative_path(value: str) -> str:
    candidate = value.replace("\\", "/").strip().lstrip("/")
    if not candidate or candidate.startswith("../") or "/../" in candidate or ":" in candidate:
        return ""
    return candidate


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _is_project_release_url(value: str) -> bool:
    parsed = urlparse(value)
    prefix = f"/{PROJECT_GITHUB_REPOSITORY}/releases/download/"
    return parsed.scheme == "https" and parsed.netloc.lower() == "github.com" and parsed.path.startswith(prefix)


def _is_project_manifest_url(value: str) -> bool:
    parsed = urlparse(value)
    prefix = f"/{PROJECT_GITHUB_REPOSITORY}/releases/"
    return parsed.scheme == "https" and parsed.netloc.lower() == "github.com" and parsed.path.startswith(prefix)


def _is_project_manifest_redirect(value: str) -> bool:
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    if parsed.scheme != "https":
        return False
    if host == "github.com":
        return parsed.path.startswith(f"/{PROJECT_GITHUB_REPOSITORY}/releases/")
    return host in {"objects.githubusercontent.com", "release-assets.githubusercontent.com", "github-releases.githubusercontent.com"}


def select_tesseract_executable(path: str | Path) -> Path | None:
    """Resolve an operator-selected executable or portable directory safely."""
    candidate = Path(path).expanduser()
    if candidate.is_dir():
        # A verified portable archive commonly has a single top-level folder
        # such as ``portable`` or ``bin``.  Support those predictable layouts
        # without recursively walking an arbitrary user-selected drive.
        for executable in (candidate / "tesseract.exe", candidate / "bin" / "tesseract.exe", candidate / "portable" / "tesseract.exe"):
            if executable.is_file():
                return executable.resolve()
        return None
    if candidate.name.lower() != "tesseract.exe" or not candidate.is_file():
        return None
    return candidate.resolve()


def stage_tesseract_archive(
    manifest: TesseractPackageManifest,
    destination_root: Path,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
    timeout: float = 60.0,
) -> Path:
    if manifest.platform not in {"windows-x64", "win-x64", "windows"}:
        raise ValueError("Gói Tesseract không dành cho Windows x64.")
    destination_root.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix=f".tesseract-{manifest.version}-", dir=destination_root))
    if False and stage_dir.exists():
        raise FileExistsError("Thư mục Tesseract đã tồn tại; không ghi đè bản dự phòng cũ.")
    temporary_path: Path | None = None
    try:
        digest = hashlib.sha256()
        archive_size = 0
        with opener(manifest.download_url, timeout=timeout) as response:
            resolved = getattr(response, "geturl", lambda: manifest.download_url)()
            if manifest.schema_version >= 1 and resolved and not _is_project_manifest_redirect(str(resolved)):
                raise ValueError("Tesseract component redirect is not permitted.")
            with tempfile.NamedTemporaryFile(dir=destination_root, prefix=".tesseract_stage_", suffix=".tmp", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                while chunk := response.read(1024 * 1024):
                    archive_size += len(chunk)
                    if archive_size > MAX_TESSERACT_ARCHIVE_BYTES:
                        raise ValueError("Tesseract archive exceeds the allowed size limit.")
                    temporary.write(chunk)
                    digest.update(chunk)
        if digest.hexdigest() != manifest.sha256:
            raise ValueError("Checksum gói Tesseract không khớp; không lưu bản staging.")
        stage_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(temporary_path) as archive:
            _safe_extract_tesseract(archive, stage_dir)
        component_root = stage_dir / "tesseract" if manifest.schema_version >= 1 else stage_dir
        executable = _component_executable(component_root, manifest)
        if executable is None:
            nested = next((item for item in stage_dir.rglob("tesseract.exe") if item.is_file()), None) if manifest.schema_version < 1 else None
            executable = nested.resolve() if nested else None
        if executable is None:
            raise ValueError("Gói Tesseract đã xác minh nhưng không chứa tesseract.exe.")
        if manifest.schema_version >= 1:
            _verify_tesseract_component_files(component_root, manifest)
        return executable
    except Exception:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        raise
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def stage_local_tesseract_package(package_path: Path, manifest: TesseractPackageManifest, destination_root: Path) -> Path:
    """Stage a user-selected local ZIP only after matching its configured hash."""
    package = Path(package_path)
    if not package.is_file():
        raise FileNotFoundError("Không tìm thấy gói Tesseract đã chọn.")
    digest = _sha256_file(package)
    if digest != manifest.sha256:
        raise ValueError("Gói Tesseract đã chọn không khớp SHA-256 trong manifest.")
    return stage_tesseract_archive(manifest, destination_root, opener=lambda *_args, **_kwargs: package.open("rb"))


def activate_tesseract_stage(executable: str | Path, manifest: TesseractPackageManifest, destination_root: Path) -> Path:
    """Atomically publish an already validated staged component version."""

    staged_executable = Path(executable).resolve()
    component_root = _component_root_for_executable(staged_executable, manifest)
    if component_root is None:
        raise ValueError("Tesseract staging directory is invalid.")
    destination_root.mkdir(parents=True, exist_ok=True)
    final_root = destination_root / manifest.version
    if final_root.exists():
        existing = _component_executable(final_root, manifest)
        if existing is None:
            raise FileExistsError("Existing Tesseract component directory is invalid.")
        return existing
    os.replace(component_root, final_root)
    _discard_empty_stage_parent(staged_executable, destination_root)
    final = _component_executable(final_root, manifest)
    if final is None:
        raise RuntimeError("Activated Tesseract component entry point is missing.")
    return final


def discard_tesseract_stage(executable: str | Path, destination_root: Path) -> None:
    """Discard only a private temporary stage when validation fails."""

    path = Path(executable).resolve()
    root = destination_root.resolve()
    for parent in path.parents:
        if parent.parent == root and parent.name.startswith(".tesseract-"):
            shutil.rmtree(parent, ignore_errors=True)
            return


def _component_executable(component_root: Path, manifest: TesseractPackageManifest) -> Path | None:
    if manifest.schema_version >= 1:
        candidate = (component_root / manifest.entrypoint).resolve()
        root = component_root.resolve()
        return candidate if candidate.is_file() and root in candidate.parents else None
    return select_tesseract_executable(component_root)


def _component_root_for_executable(executable: Path, manifest: TesseractPackageManifest) -> Path | None:
    if manifest.schema_version < 1:
        return executable.parent
    root = executable
    for _part in Path(manifest.entrypoint).parts:
        root = root.parent
    return root if root.is_dir() and _component_executable(root, manifest) == executable else None


def _verify_tesseract_component_files(component_root: Path, manifest: TesseractPackageManifest) -> None:
    expected = {item.path: item for item in manifest.files}
    for relative, item in expected.items():
        path = component_root / relative
        if not path.is_file() or path.stat().st_size != item.size_bytes or _sha256_file(path) != item.sha256:
            raise ValueError("Tesseract component file verification failed.")
    required = {manifest.entrypoint, f"{manifest.tessdata_dir}/eng.traineddata", f"{manifest.tessdata_dir}/osd.traineddata"}
    if not required <= set(expected):
        raise ValueError("Tesseract component manifest does not hash required runtime files.")


def _discard_empty_stage_parent(executable: Path, destination_root: Path) -> None:
    root = destination_root.resolve()
    for parent in executable.parents:
        if parent.parent == root and parent.name.startswith(".tesseract-"):
            shutil.rmtree(parent, ignore_errors=True)
            return


def validate_tesseract_component(
    executable: str | Path,
    *,
    runner: Callable[..., object] = subprocess.run,
    expected_version: str = "",
    smoke_image: str | Path | None = None,
    smoke_expected: str = "59X112345",
) -> str:
    """Validate a staged portable component before it becomes the active path."""

    path = Path(executable)
    if path.name.lower() != "tesseract.exe" or not path.is_file():
        raise ValueError("Gói Tesseract không chứa tesseract.exe hợp lệ.")
    tessdata = next((candidate for candidate in (path.parent / "tessdata", path.parent.parent / "tessdata") if (candidate / "eng.traineddata").is_file()), None)
    if tessdata is None:
        raise ValueError("Gói Tesseract thiếu tessdata/eng.traineddata.")
    if not (tessdata / "osd.traineddata").is_file():
        raise ValueError("Tesseract component is missing tessdata/osd.traineddata.")
    completed = runner([str(path), "--version"], capture_output=True, text=True, timeout=8, check=False)
    if int(getattr(completed, "returncode", 1)) != 0:
        raise ValueError("Không thể khởi động Tesseract đã tải.")
    languages = runner([str(path), "--tessdata-dir", str(tessdata), "--list-langs"], capture_output=True, text=True, timeout=8, check=False)
    output = f"{getattr(languages, 'stdout', '')}\n{getattr(languages, 'stderr', '')}".lower()
    if int(getattr(languages, "returncode", 1)) != 0 or "eng" not in output:
        raise ValueError("Tesseract đã tải không đọc được dữ liệu ngôn ngữ eng.")
    version_line = (str(getattr(completed, "stdout", "")) or str(getattr(completed, "stderr", ""))).splitlines()
    version = version_line[0].strip() if version_line else "Tesseract đã sẵn sàng"
    if expected_version and expected_version not in version:
        raise ValueError("Tesseract component version does not match its manifest.")
    if smoke_image is not None:
        image = Path(smoke_image)
        if not image.is_file():
            raise ValueError("Tesseract smoke fixture is missing.")
        smoke = runner(
            [str(path), "--tessdata-dir", str(tessdata), str(image), "stdout", "--psm", "7", "-c", "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        output = "".join(character for character in str(getattr(smoke, "stdout", "")).upper() if character.isalnum())
        if int(getattr(smoke, "returncode", 1)) != 0 or not output or (smoke_expected and smoke_expected.upper() not in output):
            raise ValueError("Tesseract OCR smoke check failed.")
    return version
