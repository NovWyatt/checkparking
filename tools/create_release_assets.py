from __future__ import annotations

"""Create portable Windows artifacts, checksums and an updater manifest."""

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def installed_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def archive_directory(source_dir: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in source_dir.rglob("*"):
            if item.is_file():
                archive.write(item, Path(source_dir.name) / item.relative_to(source_dir))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repository", required=True, help="owner/repository")
    parser.add_argument("--tag", default="")
    parser.add_argument("--installer", type=Path)
    parser.add_argument("--release-notes", default="")
    parser.add_argument("--extra-asset", type=Path, action="append", default=[])
    args = parser.parse_args()

    source_dir = args.input_dir.resolve()
    if not source_dir.is_dir():
        raise SystemExit(f"Portable input directory does not exist: {source_dir}")
    tag = args.tag.strip() or f"v{args.version}"
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    portable_name = f"CheckVehicleOCR-Portable-{args.version}.zip"
    portable = output / portable_name
    archive_directory(source_dir, portable)

    assets: list[dict[str, object]] = []
    if args.installer:
        installer = args.installer.resolve()
        if not installer.is_file():
            raise SystemExit(f"Installer does not exist: {installer}")
        installer_name = f"CheckVehicleOCR-Setup-{args.version}.exe"
        installer_asset = output / installer_name
        shutil.copy2(installer, installer_asset)
        assets.append({"name": installer_name, "platform": "windows-x64", "kind": "installer", "sha256": sha256(installer_asset), "size": installer_asset.stat().st_size})
    assets.append({"name": portable_name, "platform": "windows-x64", "kind": "portable", "sha256": sha256(portable), "size": portable.stat().st_size})

    for extra in args.extra_asset:
        source = extra.resolve()
        if not source.is_file():
            raise SystemExit(f"Extra release asset does not exist: {source}")
        target = output / source.name
        if source != target:
            shutil.copy2(source, target)
        name = target.name
        kind = "component" if "tesseract" in name.lower() or "model" in name.lower() else "metadata"
        assets.append({"name": name, "platform": "windows-x64", "kind": kind, "sha256": sha256(target), "size": target.stat().st_size})

    urls = {asset["name"]: f"https://github.com/{args.repository}/releases/download/{tag}/{asset['name']}" for asset in assets}
    preferred = next((asset for asset in assets if asset["kind"] == "installer"), assets[0])
    manifest = {
        "schema_version": 1,
        "version": args.version,
        "tag": tag,
        "release_notes": args.release_notes,
        "download_url": urls[preferred["name"]],
        "sha256": preferred["sha256"],
        "ocr_runtime": {
            "paddleocr": installed_version("paddleocr"),
            "paddlepaddle": installed_version("paddlepaddle"),
            "paddlex": installed_version("paddlex"),
            "models": ["PP-OCRv6_small_det", "PP-OCRv6_small_rec"],
        },
        "assets": [{**asset, "download_url": urls[asset["name"]]} for asset in assets],
    }
    manifest_path = output / "update-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    versioned_manifest_path = output / f"CheckVehicleOCR-{args.version}-manifest.json"
    shutil.copy2(manifest_path, versioned_manifest_path)

    sums = output / "SHA256SUMS.txt"
    lines = [f"{asset['sha256']}  {asset['name']}" for asset in assets]
    lines.append(f"{sha256(manifest_path)}  {manifest_path.name}")
    lines.append(f"{sha256(versioned_manifest_path)}  {versioned_manifest_path.name}")
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"assets": [asset["name"] for asset in assets], "manifest": manifest_path.name, "checksums": sums.name}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
