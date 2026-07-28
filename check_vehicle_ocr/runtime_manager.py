"""Safe project-local PaddleOCR runtime staging and rollback helpers.

The running interpreter is never modified.  A candidate is installed into a
versioned directory under ``.runtime/staging`` and only becomes active after
all recorded acceptance commands pass.  The launcher in :mod:`main` falls
back to the base runtime when an activated candidate cannot start.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class RuntimeStagingPlan:
    version: str
    paddlepaddle_requirement: str
    stage_dir: Path
    python_path: Path
    commands: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class RuntimeStagingReport:
    version: str
    stage_dir: Path
    passed: bool
    summary: str
    commands_run: tuple[tuple[str, ...], ...]


class PaddleRuntimeManager:
    """Manage staged Python environments without touching the active one."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path(__file__).resolve().parents[1]).resolve()
        self.runtime_root = self.project_root / ".runtime"
        self.staging_root = self.runtime_root / "staging"
        self.registry_path = self.runtime_root / "active-runtime.json"

    def build_plan(self, version: str, paddlepaddle_version: str = "") -> RuntimeStagingPlan:
        candidate = _safe_version(version)
        stage_dir = self.staging_root / f"paddleocr-{candidate}"
        python_path = _venv_python(stage_dir / "venv")
        paddle_requirement = f"paddlepaddle=={paddlepaddle_version.strip()}" if paddlepaddle_version.strip() else "paddlepaddle"
        commands = (
            (sys.executable, "-m", "venv", str(stage_dir / "venv")),
            (str(python_path), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--upgrade", "pip"),
            (
                str(python_path),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                f"paddleocr=={candidate}",
                paddle_requirement,
                "numpy>=1.26",
                "opencv-python>=4.9",
                "openpyxl>=3.1",
                "pillow>=10.2",
                "pytesseract>=0.3.10",
                "openai>=2.0",
            ),
            (str(python_path), "-c", "import paddle, paddleocr; print(paddle.__version__, paddleocr.__version__)"),
            (str(python_path), str(self.project_root / "main.py"), "--self-test-paddle"),
            (str(python_path), str(self.project_root / "tools" / "validate_paddle_runtime.py"), "--compact"),
            (str(python_path), str(self.project_root / "tests" / "performance_benchmark.py"), "--single-run"),
        )
        return RuntimeStagingPlan(candidate, paddle_requirement, stage_dir, python_path, commands)

    def stage_and_test(
        self,
        version: str,
        paddlepaddle_version: str = "",
        *,
        runner: Callable[..., object] = subprocess.run,
        timeout: float = 900.0,
    ) -> RuntimeStagingReport:
        """Create and validate a candidate environment after an explicit UI action.

        Tests inject ``runner`` and never call this method with the real
        subprocess implementation.  A pre-existing stage is kept untouched so
        an interrupted or previously failed attempt is inspectable.
        """
        plan = self.build_plan(version, paddlepaddle_version)
        if plan.stage_dir.exists():
            return RuntimeStagingReport(plan.version, plan.stage_dir, False, "Thư mục thử nghiệm đã tồn tại; không ghi đè lần thử trước.", ())
        plan.stage_dir.parent.mkdir(parents=True, exist_ok=True)
        executed: list[tuple[str, ...]] = []
        env = {
            **os.environ,
            "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True",
            "CHECK_VEHICLE_DISABLE_ONNX_DETECTOR": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
        try:
            for command in plan.commands:
                result = runner(
                    list(command),
                    cwd=str(self.project_root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                executed.append(command)
                return_code = int(getattr(result, "returncode", 0))
                if return_code != 0:
                    detail = _short_process_output(result)
                    report = RuntimeStagingReport(plan.version, plan.stage_dir, False, f"Thử PaddleOCR {plan.version} không đạt: {detail}", tuple(executed))
                    self._write_acceptance(plan, report)
                    return report
            report = RuntimeStagingReport(
                plan.version,
                plan.stage_dir,
                True,
                f"PaddleOCR {plan.version} đã qua import, OCR synthetic, normalization và Excel smoke.",
                tuple(executed),
            )
            self._write_acceptance(plan, report)
            return report
        except Exception as exc:
            report = RuntimeStagingReport(plan.version, plan.stage_dir, False, "Không thể hoàn tất môi trường thử nghiệm; runtime hiện tại không thay đổi.", tuple(executed))
            self._write_acceptance(plan, report, technical_error=type(exc).__name__)
            return report

    def can_activate(self, version: str) -> bool:
        stage_dir = self.build_plan(version).stage_dir
        acceptance = _read_json(stage_dir / "acceptance.json")
        return bool(acceptance.get("passed")) and _venv_python(stage_dir / "venv").exists()

    def activate(self, version: str) -> bool:
        """Atomically choose an accepted candidate for the next application start."""
        plan = self.build_plan(version)
        if not self.can_activate(version):
            return False
        registry = self.read_registry()
        active = {
            "version": plan.version,
            "python": str(plan.python_path),
            "stage_dir": str(plan.stage_dir),
        }
        previous = registry.get("active") if isinstance(registry.get("active"), dict) else None
        self._write_registry({"active": active, "previous": previous})
        return True

    def rollback(self) -> bool:
        registry = self.read_registry()
        previous = registry.get("previous")
        if not isinstance(previous, dict) or not Path(str(previous.get("python") or "")).exists():
            return False
        self._write_registry({"active": previous, "previous": registry.get("active")})
        return True

    def read_registry(self) -> dict[str, object]:
        return _read_json(self.registry_path)

    def _write_acceptance(self, plan: RuntimeStagingPlan, report: RuntimeStagingReport, *, technical_error: str = "") -> None:
        plan.stage_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": report.version,
            "passed": report.passed,
            "summary": report.summary,
            "commands_run": [list(command) for command in report.commands_run],
            "technical_error": technical_error,
        }
        _atomic_json_write(plan.stage_dir / "acceptance.json", payload)

    def _write_registry(self, payload: Mapping[str, object]) -> None:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        _atomic_json_write(self.registry_path, dict(payload))


def active_runtime_python(project_root: Path | None = None) -> Path | None:
    manager = PaddleRuntimeManager(project_root)
    active = manager.read_registry().get("active")
    if not isinstance(active, dict):
        return None
    candidate = Path(str(active.get("python") or ""))
    return candidate if candidate.exists() else None


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _safe_version(value: str) -> str:
    candidate = str(value or "").strip().lstrip("vV")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if not candidate or any(character not in allowed for character in candidate):
        raise ValueError("Phiên bản PaddleOCR không hợp lệ.")
    return candidate


def _read_json(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _atomic_json_write(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False, mode="w", encoding="utf-8") as temporary:
            temporary_path = Path(temporary.name)
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def _short_process_output(result: object) -> str:
    value = str(getattr(result, "stderr", "") or getattr(result, "stdout", "") or "lệnh kiểm tra trả mã lỗi").strip()
    return " ".join(value.split())[:280]
