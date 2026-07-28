"""Versioned, atomic OCR model staging for the local PaddleOCR runtime.

The project does not publish a model package yet, so this module never
inventories a remote URL or enables automatic downloads by itself.  Once an
operator supplies a project-controlled manifest with SHA-256, a bundle is
staged below the user profile, validated in a separate process, then selected
for the next OCR engine initialization.  The previous selection is retained
for rollback.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


@dataclass(frozen=True)
class ModelValidationReport:
    version: str
    stage_dir: Path
    passed: bool
    summary: str


class ModelRuntimeManager:
    """Keep model selection out of the application install directory."""

    def __init__(self, root: Path | None = None, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path(__file__).resolve().parents[1]).resolve()
        self.root = (root or _default_model_root()).resolve()
        self.staging_root = self.root / "staging"
        self.registry_path = self.root / "active-model.json"

    def stage_dir(self, version: str) -> Path:
        return self.staging_root / f"paddleocr-{_safe_version(version)}"

    def validate_and_record(
        self,
        *,
        version: str,
        stage_dir: Path,
        detection_model: str,
        recognition_model: str,
        runner: Callable[..., object] = subprocess.run,
        timeout: float = 900.0,
    ) -> ModelValidationReport:
        """Run an isolated synthetic OCR smoke test before a model is eligible.

        The command receives explicit model paths and does not alter the
        running engine.  A failed check leaves the staged archive on disk for
        inspection, but it can never be activated.
        """
        candidate = _safe_version(version)
        root = Path(stage_dir).resolve()
        detection_dir = root / detection_model
        recognition_dir = root / recognition_model
        if not _valid_model_dir(detection_dir) or not _valid_model_dir(recognition_dir):
            report = ModelValidationReport(candidate, root, False, "Gói model đã xác minh nhưng thiếu tệp nhận diện hoặc đọc chữ hợp lệ.")
            self._write_acceptance(report, detection_model, recognition_model)
            return report
        command = (
            sys.executable,
            str(self.project_root / "tools" / "validate_model_bundle.py"),
            "--detection-dir",
            str(detection_dir),
            "--recognition-dir",
            str(recognition_dir),
        )
        try:
            result = runner(
                list(command),
                cwd=str(self.project_root),
                env={**os.environ, "PYTHONNOUSERSITE": "1", "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True"},
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if int(getattr(result, "returncode", 1)) != 0:
                detail = " ".join(str(getattr(result, "stderr", "") or getattr(result, "stdout", "") or "kiểm tra model trả mã lỗi").split())[:240]
                report = ModelValidationReport(candidate, root, False, f"Model {candidate} chưa đạt OCR smoke: {detail}")
            else:
                report = ModelValidationReport(candidate, root, True, f"Model {candidate} đã qua kiểm tra OCR synthetic. Có thể chọn dùng ở lần mở sau.")
        except Exception:
            report = ModelValidationReport(candidate, root, False, "Không thể hoàn tất kiểm tra model; model đang dùng không thay đổi.")
        self._write_acceptance(report, detection_model, recognition_model)
        return report

    def can_activate(self, version: str) -> bool:
        acceptance = _read_json(self.stage_dir(version) / "acceptance.json")
        if not acceptance.get("passed"):
            return False
        return _valid_model_dir(Path(str(acceptance.get("detection_dir") or ""))) and _valid_model_dir(Path(str(acceptance.get("recognition_dir") or "")))

    def activate(self, version: str) -> bool:
        candidate = _safe_version(version)
        if not self.can_activate(candidate):
            return False
        acceptance = _read_json(self.stage_dir(candidate) / "acceptance.json")
        active = {
            "version": candidate,
            "stage_dir": str(self.stage_dir(candidate)),
            "detection_dir": str(acceptance["detection_dir"]),
            "recognition_dir": str(acceptance["recognition_dir"]),
        }
        registry = self.read_registry()
        previous = registry.get("active") if isinstance(registry.get("active"), dict) else None
        self._write_registry({"active": active, "previous": previous})
        return True

    def rollback(self) -> bool:
        registry = self.read_registry()
        previous = registry.get("previous")
        if isinstance(previous, dict) and _registry_entry_valid(previous):
            self._write_registry({"active": previous, "previous": registry.get("active")})
            return True
        if isinstance(registry.get("active"), dict):
            # No earlier staged model means the engine falls back to bundled or
            # cache models.  This is still a valid rollback path.
            self._write_registry({})
            return True
        return False

    def active_model_dirs(self) -> dict[str, str]:
        active = self.read_registry().get("active")
        if not isinstance(active, dict) or not _registry_entry_valid(active):
            return {}
        return {
            "PP-OCRv5_mobile_det": str(active["detection_dir"]),
            "en_PP-OCRv5_mobile_rec": str(active["recognition_dir"]),
        }

    def read_registry(self) -> dict[str, object]:
        return _read_json(self.registry_path)

    def _write_acceptance(self, report: ModelValidationReport, detection_model: str, recognition_model: str) -> None:
        payload = {
            "version": report.version,
            "passed": report.passed,
            "summary": report.summary,
            "detection_dir": str(report.stage_dir / detection_model),
            "recognition_dir": str(report.stage_dir / recognition_model),
        }
        _atomic_json_write(report.stage_dir / "acceptance.json", payload)

    def _write_registry(self, payload: Mapping[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        _atomic_json_write(self.registry_path, dict(payload))


def active_model_dirs() -> dict[str, str]:
    """Return only a previously accepted, still-valid active model selection."""
    return ModelRuntimeManager().active_model_dirs()


def _default_model_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "CheckVehicleOCR" / "models"
    return Path.home() / ".check_vehicle_ocr" / "models"


def _safe_version(value: str) -> str:
    candidate = str(value or "").strip().lstrip("vV")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if not candidate or any(character not in allowed for character in candidate):
        raise ValueError("Phiên bản model không hợp lệ.")
    return candidate


def _valid_model_dir(path: Path) -> bool:
    return path.is_dir() and (path / "inference.yml").is_file() and (any(path.glob("*.pdmodel")) or any(path.glob("*.json")))


def _registry_entry_valid(entry: Mapping[str, object]) -> bool:
    return _valid_model_dir(Path(str(entry.get("detection_dir") or ""))) and _valid_model_dir(Path(str(entry.get("recognition_dir") or "")))


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_json_write(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False, mode="w", encoding="utf-8") as file:
            temporary = Path(file.name)
            json.dump(payload, file, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)
