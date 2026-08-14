# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import paddle
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata


block_cipher = None
project_root = Path(SPECPATH)
vendor_tesseract = project_root / "vendor" / "tesseract"
paddle_libs = Path(paddle.__file__).resolve().parent / "libs"
yunet_model_dir = project_root / "models" / "opencv_yunet"
paddleocr_model_names = (
    "PP-OCRv6_small_det",
    "PP-OCRv6_small_rec",
    "PP-OCRv6_tiny_det",
    "PP-OCRv6_tiny_rec",
    "PP-OCRv5_mobile_det",
    "en_PP-OCRv5_mobile_rec",
)
paddleocr_model_runtime_files = (
    "config.json",
    "inference.json",
    "inference.pdiparams",
    "inference.yml",
)
binaries = [(str(dll), "paddle/libs") for dll in paddle_libs.glob("*.dll")]


def copy_metadata_optional(package_name):
    try:
        return copy_metadata(package_name)
    except Exception:
        return []


def collect_dynamic_libs_optional(package_name):
    try:
        return collect_dynamic_libs(package_name)
    except Exception:
        return []


datas = collect_data_files("paddlex") + collect_data_files("paddleocr")
model_manifest = project_root / "models" / "manifest.json"
if model_manifest.is_file():
    datas.append((str(model_manifest), "models"))
runtime_versions = project_root / "build" / "runtime-versions.json"
if runtime_versions.is_file():
    datas.append((str(runtime_versions), "build"))
windows_version_info = project_root / "build" / "windows-version-info.txt"
icons_dir = project_root / "assets" / "icons"
if icons_dir.is_dir():
    datas.append((str(icons_dir), "assets/icons"))
tesseract_assets = project_root / "assets" / "tesseract"
if tesseract_assets.is_dir():
    datas.append((str(tesseract_assets), "assets/tesseract"))
for model_name in paddleocr_model_names:
    model_dir = project_root / "models" / "paddleocr" / model_name
    for runtime_file_name in paddleocr_model_runtime_files:
        runtime_file = model_dir / runtime_file_name
        if runtime_file.is_file():
            datas.append((str(runtime_file), f"models/paddleocr/{model_name}"))
if yunet_model_dir.is_dir():
    for detector_asset in yunet_model_dir.iterdir():
        if detector_asset.is_file():
            datas.append((str(detector_asset), "models/opencv_yunet"))
for package_name in (
    "paddlex",
    "paddleocr",
    "paddlepaddle",
    "imagesize",
    "opencv-contrib-python",
    "opencv-python-headless",
    "pyclipper",
    "pypdfium2",
    "python-bidi",
    "shapely",
):
    datas += copy_metadata_optional(package_name)
if vendor_tesseract.exists():
    tesseract_exe = vendor_tesseract / "tesseract.exe"
    if tesseract_exe.exists():
        datas.append((str(tesseract_exe), "tesseract"))
    for dll in vendor_tesseract.glob("*.dll"):
        datas.append((str(dll), "tesseract"))

    tessdata = vendor_tesseract / "tessdata"
    for data_file in [*tessdata.glob("eng.*"), tessdata / "osd.traineddata", tessdata / "pdf.ttf"]:
        if data_file.exists():
            datas.append((str(data_file), "tesseract/tessdata"))
    for config_dir in (tessdata / "configs", tessdata / "tessconfigs"):
        if config_dir.exists():
            datas.append((str(config_dir), f"tesseract/tessdata/{config_dir.name}"))


a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=["pillow_heif"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CheckVehicleOCR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "assets" / "icons" / "app-icon.ico"),
    version=str(windows_version_info) if windows_version_info.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CheckVehicleOCR",
)
