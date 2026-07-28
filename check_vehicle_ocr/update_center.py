"""Safe, offline-testable helpers for the operator-facing Update Center.

Nothing in this module changes the running Python environment or active OCR
models.  Package/model staging is intentionally a separate, explicit step so
the UI can describe what will happen before an operator approves it.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable


PYPI_PADDLEOCR_URL = "https://pypi.org/pypi/paddleocr/json"


@dataclass(frozen=True)
class PaddleRuntimeInfo:
    paddleocr_version: str
    paddlepaddle_version: str
    compatibility: str


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


def installed_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "Chưa cài"


def paddle_runtime_info() -> PaddleRuntimeInfo:
    paddleocr_version = installed_version("paddleocr")
    paddlepaddle_version = installed_version("paddlepaddle")
    if paddleocr_version == "Chưa cài":
        compatibility = "PaddleOCR chưa được cài. Không thể kiểm tra tương thích."
    elif paddlepaddle_version == "Chưa cài":
        compatibility = "Chưa xác định PaddlePaddle. Cần thử nghiệm trong môi trường staging."
    else:
        compatibility = "Chưa suy đoán tương thích chỉ theo phiên bản; cần smoke test và benchmark staging."
    return PaddleRuntimeInfo(paddleocr_version, paddlepaddle_version, compatibility)


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
        ("Nhận diện chữ", "PP-OCRv5_mobile_det"),
        ("Đọc chữ", "en_PP-OCRv5_mobile_rec"),
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
                active=bool(model_path),
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
