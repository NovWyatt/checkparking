"""Build a content-addressed portable Tesseract release component.

This script never downloads or compiles anything.  CI or an operator must
provide a Tesseract executable built from the pinned source tag and the exact
official tessdata_fast checkout.  Keeping packaging separate makes the
archive, file inventory and release manifest independently auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


# MSYS2 package updates can legitimately increment a DLL SONAME even though
# Tesseract's pinned source tag is unchanged.  Resolve only these known
# dependency families (never arbitrary DLLs), then hash their exact filenames
# in the resulting manifest.  This keeps the component self-contained while
# allowing the release gate to detect a real missing DLL on a fresh runner.
RUNTIME_DLL_PATTERNS = (
    "libtesseract*.dll",
    "libgcc_s_*.dll",
    "libstdc++-*.dll",
    "libwinpthread-*.dll",
    "libleptonica-*.dll",
    "libtiff-*.dll",
    "libjbig-*.dll",
    "libdeflate.dll",
    "libjpeg-*.dll",
    "libLerc.dll",
    "liblzma-*.dll",
    "libwebp-*.dll",
    "zlib1.dll",
    "libzstd.dll",
    "libgif-*.dll",
    "libwebpmux-*.dll",
    "libopenjp2-*.dll",
    "libpng*.dll",
    "libsharpyuv-*.dll",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_required(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_runtime_dependencies(install_dir: Path, runtime_dll_dir: Path, destination: Path) -> list[str]:
    """Copy the exact DLL closure reported by the pinned UCRT64 objdump."""

    source_bin = install_dir / "bin"
    objdump = runtime_dll_dir / "objdump.exe"
    executable = source_bin / "tesseract.exe"
    available = {path.name.lower(): path for root in (source_bin, runtime_dll_dir) for path in root.glob("*.dll") if path.is_file()}
    if objdump.is_file() and executable.is_file():
        closure = _resolve_pe_dll_closure(executable, objdump, available)
        if closure:
            for source in closure:
                _copy_required(source, destination / source.name)
            return sorted(path.name for path in closure)

    # A bounded fallback remains for local environments without objdump.  The
    # following GitHub release gate still starts the executable and will reject
    # the package if a dependency is absent.
    copied: set[str] = set()
    for pattern in RUNTIME_DLL_PATTERNS:
        matches = sorted(source_bin.glob(pattern)) + sorted(runtime_dll_dir.glob(pattern))
        selected = next((path for path in matches if path.is_file() and path.name not in copied), None)
        if selected is None:
            raise FileNotFoundError(f"Missing required Windows runtime DLL matching {pattern}")
        _copy_required(selected, destination / selected.name)
        copied.add(selected.name)
    return sorted(copied)


def _resolve_pe_dll_closure(executable: Path, objdump: Path, available: dict[str, Path]) -> list[Path]:
    pending = [executable]
    copied: dict[str, Path] = {}
    while pending:
        current = pending.pop()
        try:
            output = subprocess.run([str(objdump), "-p", str(current)], capture_output=True, text=True, timeout=15, check=False).stdout
        except OSError:
            return []
        if not output:
            return []
        for name in re.findall(r"DLL Name:\s*([^\r\n]+)", output, flags=re.IGNORECASE):
            normalized = name.strip().lower()
            if normalized.startswith(("api-ms-win-", "kernel", "user32", "gdi32", "advapi32", "shell32", "ole", "comdlg", "ucrtbase")):
                continue
            dependency = available.get(normalized)
            if dependency is None or normalized in copied:
                continue
            copied[normalized] = dependency
            pending.append(dependency)
    return [copied[name] for name in sorted(copied)]


def _file_records(component_root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(component_root.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS.txt":
            continue
        relative = path.relative_to(component_root).as_posix()
        records.append({"path": relative, "sha256": sha256(path), "size_bytes": path.stat().st_size})
    return records


def _write_notices(component_root: Path, source_dir: Path, tessdata_dir: Path, version: str, source_commit: str, tessdata_commit: str) -> None:
    licenses = component_root / "LICENSES"
    _copy_required(source_dir / "LICENSE", licenses / "Tesseract-Apache-2.0.txt")
    _copy_required(tessdata_dir / "LICENSE", licenses / "tessdata-license.txt")
    (licenses / "third-party-notices.txt").write_text(
        "Check Vehicle OCR portable Tesseract component\n\n"
        f"Tesseract {version}, source commit {source_commit}, is licensed under Apache-2.0.\n"
        f"tessdata_fast commit {tessdata_commit} is distributed under its included Apache-2.0 license.\n"
        "Runtime DLLs are built or supplied by the pinned MSYS2 UCRT64 dependency set. "
        "Their package identities and licenses are recorded in SBOM.json and project third-party notices.\n",
        encoding="utf-8",
    )


def _write_sbom(component_root: Path, version: str, source_commit: str, tessdata_commit: str, dependencies: list[str]) -> None:
    components = [
        {"type": "application", "name": "tesseract", "version": version, "licenses": [{"license": {"id": "Apache-2.0"}}], "purl": f"pkg:github/tesseract-ocr/tesseract@{source_commit}"},
        {"type": "data", "name": "tessdata_fast", "version": tessdata_commit, "licenses": [{"license": {"id": "Apache-2.0"}}], "purl": f"pkg:github/tesseract-ocr/tessdata_fast@{tessdata_commit}"},
    ]
    components.extend({"type": "library", "name": item} for item in dependencies)
    payload = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:tesseract-{version}-{source_commit[:12]}",
        "version": 1,
        "metadata": {"timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "component": components[0]},
        "components": components,
    }
    (component_root / "SBOM.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_component_manifest(component_root: Path, version: str, source_tag: str, source_commit: str, tessdata_commit: str, archive_name: str) -> None:
    # The release manifest beside the ZIP owns the archive checksum.  Embedding
    # an archive hash inside the same ZIP would be self-referential; this
    # embedded manifest instead protects every material file in the component.
    payload = {
        "schema_version": 1,
        "component": "tesseract",
        "version": version,
        "platform": "windows-x64",
        "source_tag": source_tag,
        "source_commit": source_commit,
        "tessdata_fast_commit": tessdata_commit,
        "archive": archive_name,
        "entrypoint": "bin/tesseract.exe",
        "tessdata_dir": "tessdata",
        "languages": ["eng", "osd"],
        "license": "Apache-2.0",
    }
    (component_root / "component-manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _archive(component_root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(component_root.rglob("*")):
            if path.is_file():
                archive.write(path, Path("tesseract") / path.relative_to(component_root))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-dir", type=Path, required=True, help="CMake install prefix containing bin/tesseract.exe")
    parser.add_argument("--runtime-dll-dir", type=Path, required=True, help="Pinned MSYS2 UCRT64 bin directory")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--tessdata-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-tag", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--tessdata-commit", required=True)
    parser.add_argument("--repository", default="NovWyatt/checkparking")
    parser.add_argument("--tag", default="")
    args = parser.parse_args()

    version = args.version.strip()
    tag = args.tag.strip() or f"v{version}"
    archive_name = f"CheckVehicleOCR-Tesseract-{version}-win-x64.zip"
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / archive_name

    with tempfile.TemporaryDirectory(prefix="check_vehicle_tesseract_component_") as temporary:
        component_root = Path(temporary) / "tesseract"
        bin_dir = component_root / "bin"
        _copy_required(args.install_dir / "bin" / "tesseract.exe", bin_dir / "tesseract.exe")
        runtime_dlls = _copy_runtime_dependencies(args.install_dir, args.runtime_dll_dir, bin_dir)
        _copy_required(args.tessdata_dir / "eng.traineddata", component_root / "tessdata" / "eng.traineddata")
        _copy_required(args.tessdata_dir / "osd.traineddata", component_root / "tessdata" / "osd.traineddata")
        _write_notices(component_root, args.source_dir, args.tessdata_dir, version, args.source_commit, args.tessdata_commit)
        _write_sbom(component_root, version, args.source_commit, args.tessdata_commit, runtime_dlls)
        _write_component_manifest(component_root, version, args.source_tag, args.source_commit, args.tessdata_commit, archive_name)
        records = _file_records(component_root)
        (component_root / "SHA256SUMS.txt").write_text(
            "\n".join(f"{record['sha256']}  {record['path']}" for record in records) + "\n",
            encoding="utf-8",
        )
        _archive(component_root, archive_path)

    archive_hash = sha256(archive_path)
    external_manifest = {
        "schema_version": 1,
        "component": "tesseract",
        "version": version,
        "platform": "windows-x64",
        "source_tag": args.source_tag,
        "source_commit": args.source_commit,
        "archive": archive_name,
        "download_url": f"https://github.com/{args.repository}/releases/download/{tag}/{archive_name}",
        "sha256": archive_hash,
        "archive_sha256": archive_hash,
        "archive_type": "zip",
        "entrypoint": "bin/tesseract.exe",
        "tessdata_dir": "tessdata",
        "languages": ["eng", "osd"],
        "license": "Apache-2.0",
        "source": "Project-controlled GitHub Release asset built from tesseract-ocr source",
        "files": records,
    }
    manifest_path = output / "tesseract-component-manifest.json"
    manifest_path.write_text(json.dumps(external_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"archive": archive_path.name, "sha256": archive_hash, "manifest": manifest_path.name, "files": len(records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
