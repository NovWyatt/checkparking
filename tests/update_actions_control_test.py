from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace
from tkinter import ttk


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.config import APP_DIR_NAME, SETTINGS_FILE, load_settings, migrate_settings, save_settings
from check_vehicle_ocr.runtime_manager import PaddleRuntimeManager
from check_vehicle_ocr.ui.theme import TOKENS
from check_vehicle_ocr.update_center import parse_tesseract_manifest, select_tesseract_executable, stage_tesseract_archive
from check_vehicle_ocr.updater import (
    GitHubRelease,
    GitHubReleaseAsset,
    UpdateManifest,
    fetch_github_latest_release,
    github_latest_release_api,
    normalize_github_repository,
    select_windows_release_asset,
)


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def _production_settings_path() -> Path:
    base = os.environ.get("APPDATA")
    return (Path(base) / APP_DIR_NAME / SETTINGS_FILE) if base else (Path.home() / ".check_vehicle_ocr" / SETTINGS_FILE)


def _fake_runner(*_args, **_kwargs):
    return SimpleNamespace(returncode=0, stdout="ok", stderr="")


def _failing_runner(*_args, **_kwargs):
    return SimpleNamespace(returncode=1, stdout="", stderr="dependency conflict")


def _test_config_and_isolation() -> None:
    migrated = migrate_settings({"updates": {"manifest_url": "file:///mock"}})
    assert migrated["updates"]["manifest_url"] == ""
    assert migrated["updates"]["source_mode"] == "disabled"
    known_test = migrate_settings({"updates": {"manifest_url": "file:///mock-manifest.json"}})
    assert known_test["updates"]["manifest_url"] == ""
    real_file = migrate_settings({"updates": {"manifest_url": "file:///D:/operator/release.json"}})
    assert real_file["updates"]["manifest_url"] == "file:///D:/operator/release.json"
    legacy_token = migrate_settings({"remember_key": True, "updates": {"github_token": "private-token"}})
    assert "github_token" not in legacy_token["updates"]
    assert "private-token" not in json.dumps(legacy_token)

    production_path = _production_settings_path()
    before = production_path.read_bytes() if production_path.exists() else None
    old_appdata = os.environ.get("APPDATA")
    with tempfile.TemporaryDirectory() as isolated:
        os.environ["APPDATA"] = isolated
        app = CheckVehicleApp()
        try:
            app.update_source_mode_var.set("Manifest tùy chỉnh")
            app.update_manifest_url_var.set("https://example.invalid/test-only.json")
            app._save_settings()
            app.update_manifest_url_var.set("file:///mock")
            app._save_settings()
            payload = json.loads((Path(isolated) / APP_DIR_NAME / SETTINGS_FILE).read_text(encoding="utf-8"))
            assert payload["updates"]["manifest_url"] == ""
            assert payload["updates"]["source_mode"] == "disabled"
            save_settings(
                {"remember_key": True, "updates": {"source_mode": "github", "github_repository": "owner/private"}},
                github_token="private-token",
            )
            raw = (Path(isolated) / APP_DIR_NAME / SETTINGS_FILE).read_text(encoding="utf-8")
            assert "private-token" not in raw
            assert load_settings()["updates"]["github_token"] == "private-token"
        finally:
            app.destroy()
    if old_appdata is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = old_appdata
    after = production_path.read_bytes() if production_path.exists() else None
    assert before == after, "UI test must not write production settings"


def _pump(app: CheckVehicleApp, predicate) -> None:
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        app.update()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for UI event")


def _test_github_release() -> None:
    assert normalize_github_repository("https://github.com/acme/checkvhc.git") == "acme/checkvhc"
    assert github_latest_release_api("acme/checkvhc").endswith("/repos/acme/checkvhc/releases/latest")
    payload = {
        "tag_name": "v9.9.9",
        "body": "Release notes",
        "html_url": "https://github.com/acme/checkvhc/releases/tag/v9.9.9",
        "assets": [
            {"name": "Source code.zip", "browser_download_url": "https://github.com/archive.zip", "digest": "sha256:" + "b" * 64},
            {"name": "CheckVehicleOCR_Setup_win64.exe", "browser_download_url": "https://example.invalid/setup.exe", "digest": "sha256:" + "a" * 64, "size": 42},
        ],
    }
    release = fetch_github_latest_release("acme/checkvhc", opener=lambda *_args, **_kwargs: _Response(json.dumps(payload).encode()))
    manifest = select_windows_release_asset(release)
    assert manifest.version == "v9.9.9" and manifest.download_url.endswith("setup.exe") and manifest.sha256 == "a" * 64
    try:
        select_windows_release_asset(GitHubRelease("v1", "", "", (GitHubReleaseAsset("Source code.zip", "https://example.invalid/source.zip", "a" * 64),)))
    except ValueError:
        pass
    else:
        raise AssertionError("GitHub source ZIP must never be treated as an installer")


def _test_runtime_activation() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        manager = PaddleRuntimeManager(Path(temporary))
        plan = manager.build_plan("9.9.9", "3.3.1")
        assert any("paddleocr==9.9.9" in command for command in plan.commands)
        report = manager.stage_and_test("9.9.9", "3.3.1", runner=_fake_runner)
        assert report.passed and (report.stage_dir / "acceptance.json").exists()
        plan.python_path.parent.mkdir(parents=True, exist_ok=True)
        plan.python_path.write_text("placeholder", encoding="utf-8")
        assert manager.activate("9.9.9")
        assert manager.read_registry()["active"]["version"] == "9.9.9"

        other = manager.build_plan("9.9.10")
        other.python_path.parent.mkdir(parents=True, exist_ok=True)
        other.python_path.write_text("placeholder", encoding="utf-8")
        other.stage_dir.mkdir(parents=True, exist_ok=True)
        (other.stage_dir / "acceptance.json").write_text(json.dumps({"passed": True}), encoding="utf-8")
        assert manager.activate("9.9.10")
        assert manager.rollback()
        assert manager.read_registry()["active"]["version"] == "9.9.9"

    with tempfile.TemporaryDirectory() as temporary:
        manager = PaddleRuntimeManager(Path(temporary))
        failed = manager.stage_and_test("9.9.9", runner=_failing_runner)
        assert not failed.passed and not manager.can_activate("9.9.9")


def _test_tesseract_verified_package() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("portable/tesseract.exe", "binary")
        archive.writestr("portable/tessdata/eng.traineddata", "data")
    package = stream.getvalue()
    manifest = parse_tesseract_manifest(
        json.dumps(
            {
                "version": "5.5.0",
                "platform": "windows-x64",
                "download_url": "https://example.invalid/tesseract.zip",
                "sha256": hashlib.sha256(package).hexdigest(),
                "archive_type": "zip",
                "license": "Apache-2.0",
                "source": "project release",
            }
        )
    )
    with tempfile.TemporaryDirectory() as temporary:
        executable = stage_tesseract_archive(manifest, Path(temporary), opener=lambda *_args, **_kwargs: _Response(package))
        assert executable.name.lower() == "tesseract.exe" and executable.exists()
        assert select_tesseract_executable(executable.parent.parent) == executable


def _test_update_center_primary_actions() -> None:
    old_appdata = os.environ.get("APPDATA")
    with tempfile.TemporaryDirectory() as temporary:
        os.environ["APPDATA"] = temporary
        app = CheckVehicleApp()
        try:
            app.show_settings_section("updates")
            assert app.update_check_button is not None and app.update_download_button is None
            assert app.update_check_button.cget("text") == "Thiết lập nguồn"
            assert "Chưa cấu hình nguồn cập nhật ứng dụng." == app.update_status_var.get()

            app.update_source_mode_var.set("Manifest tùy chỉnh")
            app.update_manifest_url_var.set("file:///mock")
            app.check_for_updates()
            assert app.update_status_var.get() == "Chưa cấu hình nguồn cập nhật ứng dụng."
            assert app.update_check_button.cget("text") == "Thiết lập nguồn"
            app.stage_tesseract_from_manifest()
            assert "Chưa cấu hình nguồn gói xác minh" in app.tesseract_status_var.get()

            app.update_manifest_url_var.set("https://example.invalid/release.json")
            manifest = UpdateManifest("9.9.9", "Ghi chú", "https://example.invalid/setup.exe", "a" * 64)
            app.event_queue.put(("update_checked", manifest))
            _pump(app, lambda: app.current_update_manifest is not None)
            assert app.update_check_button.cget("text") == "Tải bản cập nhật"

            app.event_queue.put(("update_downloaded", Path(temporary) / "CheckVehicleOCR-9.9.9.download"))
            _pump(app, lambda: app.update_check_button.cget("text") == "Cài khi đóng app")
        finally:
            app.destroy()
    if old_appdata is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = old_appdata


def _test_packaged_github_default() -> None:
    import check_vehicle_ocr.app as app_module

    old_appdata = os.environ.get("APPDATA")
    original_repository = app_module.GITHUB_REPOSITORY
    had_frozen = hasattr(app_module.sys, "frozen")
    original_frozen = getattr(app_module.sys, "frozen", None)
    with tempfile.TemporaryDirectory() as temporary:
        os.environ["APPDATA"] = temporary
        app_module.GITHUB_REPOSITORY = "NovWyatt/checkparking"
        app_module.sys.frozen = True
        app = app_module.CheckVehicleApp()
        try:
            assert app._update_source_mode_key() == "github"
            assert app.github_repository_var.get() == "NovWyatt/checkparking"
        finally:
            app.destroy()
            app_module.GITHUB_REPOSITORY = original_repository
            if had_frozen:
                app_module.sys.frozen = original_frozen
            else:
                delattr(app_module.sys, "frozen")
    if old_appdata is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = old_appdata


def _test_combobox_states() -> None:
    old_appdata = os.environ.get("APPDATA")
    with tempfile.TemporaryDirectory() as temporary:
        os.environ["APPDATA"] = temporary
        app = CheckVehicleApp()
        try:
            app.show_page("scan")
            combo = app.shell.pages["scan"].performance_combo
            assert "readonly" in combo.state() and "disabled" not in combo.state()
            assert combo.cget("style") == "Operator.TCombobox"
            style = app.tk.call("ttk::style", "map", "Operator.TCombobox", "-fieldbackground")
            assert TOKENS["light"]["disabled_surface"] in str(style)
            assert TOKENS["light"]["surface"] in str(style)
            foreground_map = dict(ttk.Style(app).map("Operator.TCombobox", "foreground"))
            assert foreground_map["readonly"] == TOKENS["light"]["text_primary"]
            assert foreground_map["disabled"] == TOKENS["light"]["disabled_text"]
            app.dark_mode_var.set(True)
            app._on_theme_toggle()
            app.update_idletasks()
            app.update()
            dark_map = app.tk.call("ttk::style", "map", "Operator.TCombobox", "-fieldbackground")
            assert TOKENS["dark"]["disabled_surface"] in str(dark_map)
        finally:
            app.destroy()
    if old_appdata is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = old_appdata


def main() -> int:
    _test_config_and_isolation()
    _test_github_release()
    _test_runtime_activation()
    _test_tesseract_verified_package()
    _test_update_center_primary_actions()
    _test_packaged_github_default()
    _test_combobox_states()
    print("update_actions_control_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
