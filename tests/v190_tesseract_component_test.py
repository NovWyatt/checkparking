from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import check_vehicle_ocr.update_center as update_center
from check_vehicle_ocr.update_center import (
    activate_tesseract_stage,
    discard_tesseract_stage,
    parse_tesseract_manifest,
    stage_local_tesseract_package,
    validate_tesseract_component,
)


def _component_package(*, corrupt_file: bool = False, zip_slip: bool = False) -> tuple[bytes, dict[str, object]]:
    files = {
        "bin/tesseract.exe": b"fake executable",
        "bin/runtime.dll": b"runtime dependency",
        "tessdata/eng.traineddata": b"eng data",
        "tessdata/osd.traineddata": b"osd data",
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for path, value in files.items():
            archive.writestr(f"tesseract/{path}", value + (b"!" if corrupt_file and path == "bin/runtime.dll" else b""))
        if zip_slip:
            archive.writestr("../escaped.txt", "no")
    package = stream.getvalue()
    records = [
        {"path": path, "sha256": hashlib.sha256(value).hexdigest(), "size_bytes": len(value)}
        for path, value in files.items()
    ]
    manifest = {
        "schema_version": 1,
        "component": "tesseract",
        "version": "5.5.3",
        "platform": "windows-x64",
        "source_tag": "5.5.3",
        "archive": "CheckVehicleOCR-Tesseract-5.5.3-win-x64.zip",
        "download_url": "https://github.com/NovWyatt/checkparking/releases/download/v1.9.0/CheckVehicleOCR-Tesseract-5.5.3-win-x64.zip",
        "sha256": hashlib.sha256(package).hexdigest(),
        "archive_type": "zip",
        "entrypoint": "bin/tesseract.exe",
        "tessdata_dir": "tessdata",
        "languages": ["eng", "osd"],
        "license": "Apache-2.0",
        "source": "Project-controlled GitHub Release asset",
        "files": records,
    }
    return package, manifest


def _fake_runner(command, **_kwargs):
    if "--version" in command:
        return type("Result", (), {"returncode": 0, "stdout": "tesseract 5.5.3\n", "stderr": ""})()
    if "--list-langs" in command:
        return type("Result", (), {"returncode": 0, "stdout": "List of available languages (2):\neng\nosd\n", "stderr": ""})()
    return type("Result", (), {"returncode": 0, "stdout": "59X112345\n", "stderr": ""})()


def test_manifest_and_atomic_install() -> None:
    package, payload = _component_package()
    manifest = parse_tesseract_manifest(json.dumps(payload))
    assert manifest.version == "5.5.3" and len(manifest.files) == 4
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "LocalAppData" / "CheckVehicleOCR" / "components" / "tesseract"
        archive = Path(temporary) / "component.zip"
        archive.write_bytes(package)
        staged = stage_local_tesseract_package(archive, manifest, root)
        assert staged.is_file() and ".tesseract-5.5.3-" in str(staged)
        fixture = Path(temporary) / "fixture.png"
        fixture.write_bytes(b"fixture")
        assert validate_tesseract_component(staged, runner=_fake_runner, expected_version="5.5.3", smoke_image=fixture) == "tesseract 5.5.3"
        active = activate_tesseract_stage(staged, manifest, root)
        assert active == root / "5.5.3" / "bin" / "tesseract.exe" and active.is_file()
        assert not any(path.name.startswith(".tesseract-") for path in root.iterdir())


def test_corruption_zip_slip_and_interruption_cleanup() -> None:
    for options in ({"corrupt_file": True}, {"zip_slip": True}):
        package, payload = _component_package(**options)
        manifest = parse_tesseract_manifest(json.dumps(payload))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "components"
            archive = Path(temporary) / "component.zip"
            archive.write_bytes(package)
            try:
                stage_local_tesseract_package(archive, manifest, root)
            except ValueError:
                pass
            else:
                raise AssertionError("Unsafe or corrupted Tesseract package was accepted")
            assert not list(root.glob(".tesseract-*"))

    package, payload = _component_package()
    manifest = parse_tesseract_manifest(json.dumps(payload))
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "components"
        archive = Path(temporary) / "component.zip"
        archive.write_bytes(package)
        staged = stage_local_tesseract_package(archive, manifest, root)
        discard_tesseract_stage(staged, root)
        assert not list(root.glob(".tesseract-*"))


def test_archive_limit_and_manifest_policy() -> None:
    package, payload = _component_package()
    payload["download_url"] = "https://example.invalid/component.zip"
    try:
        parse_tesseract_manifest(json.dumps(payload))
    except ValueError:
        pass
    else:
        raise AssertionError("Foreign component source was accepted")

    manifest = parse_tesseract_manifest(json.dumps(_component_package()[1]))
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "component.zip"
        archive.write_bytes(package)
        previous = update_center.MAX_TESSERACT_ARCHIVE_BYTES
        update_center.MAX_TESSERACT_ARCHIVE_BYTES = 4
        try:
            stage_local_tesseract_package(archive, manifest, Path(temporary) / "components")
        except ValueError:
            pass
        else:
            raise AssertionError("Archive size limit was not enforced")
        finally:
            update_center.MAX_TESSERACT_ARCHIVE_BYTES = previous


def main() -> int:
    test_manifest_and_atomic_install()
    test_corruption_zip_slip_and_interruption_cleanup()
    test_archive_limit_and_manifest_policy()
    print("v190_tesseract_component_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
