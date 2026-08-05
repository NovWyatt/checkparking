from __future__ import annotations

import hashlib
import io
import json
import subprocess
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_vehicle_ocr.updater import (
    GitHubRelease,
    GitHubReleaseAsset,
    UpdateManifest,
    launch_pending_installer_update,
    read_pending_installer_update,
    recover_pending_installer_update,
    select_windows_release_asset,
    write_pending_installer_update,
)
from check_vehicle_ocr.version import VERSION
from check_vehicle_ocr.model_registry import ModelRuntimeManager
from tools.write_build_metadata import windows_version_info
from tools.build_model_component import _runtime_files


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_version_and_model_manifest() -> None:
    assert VERSION.count(".") == 2 and all(part.isdigit() for part in VERSION.split("."))
    manifest = json.loads((ROOT / "models" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "bundled-verified" and manifest["active_profile"] == "pp-ocrv6-small"
    assert {"PP-OCRv6_small_det", "PP-OCRv6_small_rec", "PP-OCRv5_mobile_det", "en_PP-OCRv5_mobile_rec"} <= {item["id"] for item in manifest["models"]}
    assert all(item["sha256"] and len(item["sha256"]) == 64 for item in manifest["models"])


def test_checksum_fallback_and_pending_helper() -> None:
    checksum = "a" * 64
    release = GitHubRelease(
        "v9.9.9",
        "notes",
        "https://github.com/acme/repo/releases/tag/v9.9.9",
        (
            GitHubReleaseAsset("CheckVehicleOCR-9.9.9-windows-x64-setup.exe", "https://example.invalid/setup.exe"),
            GitHubReleaseAsset("SHA256SUMS.txt", "https://example.invalid/SHA256SUMS.txt"),
        ),
    )
    selected = select_windows_release_asset(
        release,
        opener=lambda request, **_kwargs: Response(f"{checksum}  CheckVehicleOCR-9.9.9-windows-x64-setup.exe\n".encode()),
    )
    assert selected.sha256 == checksum and selected.asset_name.endswith("setup.exe")

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        package = root / "setup.exe"
        package.write_bytes(b"verified installer")
        real_manifest = UpdateManifest("9.9.9", "notes", "https://example.invalid/setup.exe", hashlib.sha256(package.read_bytes()).hexdigest(), package.name)
        executable = root / "install" / "CheckVehicleOCR.exe"
        executable.parent.mkdir()
        executable.write_bytes(b"old executable")
        pending_path = write_pending_installer_update(package, real_manifest, install_dir=executable.parent, executable_path=executable, state_dir=root / "state", parent_pid=123)
        assert read_pending_installer_update(pending_path) is not None
        calls: list[tuple[tuple, dict]] = []
        helper = launch_pending_installer_update(pending_path, launcher=lambda *args, **kwargs: calls.append((args, kwargs)))
        assert helper.exists() and calls and "powershell.exe" in calls[0][0][0][0]
        script = helper.read_text(encoding="utf-8")
        assert "update-backup" in script and "VERYSILENT" in script and "--runtime-health-check" in script

        backup = executable.parent.with_name(f"{executable.parent.name}.update-backup")
        shutil.move(str(executable.parent), str(backup))
        assert recover_pending_installer_update(pending_path) == "restored"
        assert executable.is_file()


def test_model_registry_activation_and_rollback() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        manager = ModelRuntimeManager(root=root, project_root=ROOT)
        stage = manager.stage_dir("2026.07")
        for name in ("PP-OCRv5_mobile_det", "en_PP-OCRv5_mobile_rec"):
            directory = stage / name
            directory.mkdir(parents=True)
            (directory / "inference.yml").write_text("model: test", encoding="utf-8")
            (directory / "model.json").write_text("{}", encoding="utf-8")
        passed = manager.validate_and_record(
            version="2026.07",
            stage_dir=stage,
            detection_model="PP-OCRv5_mobile_det",
            recognition_model="en_PP-OCRv5_mobile_rec",
            runner=lambda *_args, **_kwargs: type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})(),
        )
        assert passed.passed and manager.can_activate("2026.07")
        assert manager.activate("2026.07")
        assert manager.active_model_dirs()["PP-OCRv5_mobile_det"].endswith("PP-OCRv5_mobile_det")
        assert manager.rollback() and manager.read_registry() == {}


def test_release_asset_tool() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        app = root / "CheckVehicleOCR"
        app.mkdir()
        (app / "CheckVehicleOCR.exe").write_bytes(b"portable")
        output = root / "assets"
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "create_release_assets.py"), "--version", "9.9.9", "--input-dir", str(app), "--output-dir", str(output), "--repository", "acme/repo"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "manifest" in completed.stdout
        manifest = json.loads((output / "update-manifest.json").read_text(encoding="utf-8"))
        assert manifest["download_url"].endswith(".zip") and manifest["assets"][0]["sha256"]
        assert {"paddleocr", "paddlepaddle", "paddlex", "models"} <= set(manifest["ocr_runtime"])
        assert (output / "SHA256SUMS.txt").is_file()


def test_release_workflow_publishes_the_model_component() -> None:
    """A model manifest must never point to an asset omitted from a release."""
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    required = '"release-assets\\CheckVehicleOCR-PP-OCRv6-small-model-$version.zip"'
    upload = "release-assets/CheckVehicleOCR-PP-OCRv6-small-model-*.zip"
    assert required in workflow
    assert upload in workflow
    assert "overwrite_files: true" in workflow
    assert "replacesArtifacts" not in workflow


def test_pyinstaller_model_bundle_excludes_local_cache() -> None:
    spec = (ROOT / "CheckVehicleOCR.spec").read_text(encoding="utf-8")
    assert "paddleocr_model_runtime_files" in spec
    assert "datas.append((str(model_dir)" not in spec
    assert '"inference.pdiparams"' in spec


def test_windows_executable_version_resource() -> None:
    resource = windows_version_info(VERSION)
    numeric = tuple(int(part) for part in VERSION.split(".")) + (0,)
    assert f"filevers={numeric}" in resource
    assert f"prodvers={numeric}" in resource
    assert f"StringStruct('ProductVersion', '{VERSION}.0')" in resource
    spec = (ROOT / "CheckVehicleOCR.spec").read_text(encoding="utf-8")
    assert "windows-version-info.txt" in spec and "version=str(windows_version_info)" in spec


def test_model_component_excludes_local_metadata() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        model = Path(temporary)
        for name in ("inference.json", "inference.pdiparams", "inference.yml", ".gitattributes", "README.md"):
            (model / name).write_text("fixture", encoding="utf-8")
        assert [path.name for path in _runtime_files(model)] == [
            "inference.json",
            "inference.pdiparams",
            "inference.yml",
        ]


def main() -> int:
    test_version_and_model_manifest()
    test_checksum_fallback_and_pending_helper()
    test_model_registry_activation_and_rollback()
    test_release_asset_tool()
    test_release_workflow_publishes_the_model_component()
    test_pyinstaller_model_bundle_excludes_local_cache()
    test_windows_executable_version_resource()
    test_model_component_excludes_local_metadata()
    print("release_system_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
