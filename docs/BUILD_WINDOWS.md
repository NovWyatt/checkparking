# Build Windows

Chạy từ PowerShell tại thư mục gốc repository:

```powershell
.\build_exe.ps1
.\build_installer.ps1 -SkipExeBuild
.\build_release_assets.ps1 -SkipBuild
```

Các script chỉ dùng `.venv\Scripts\python.exe` với `PYTHONNOUSERSITE=1`.
`build_exe.ps1` ghi build metadata và `build/runtime-versions.json` không chứa
secret ngay trước PyInstaller. Với v1.9.0, chạy component Tesseract trước:

```powershell
.\.venv\Scripts\python.exe -s -B tools\build_tesseract_component.py ...
.\.venv\Scripts\python.exe -s -B tools\validate_tesseract_component.py ...
.\build_exe.ps1 -SkipInstall
.\build_installer.ps1 -SkipExeBuild
.\build_release_assets.ps1 -SkipBuild
```

`release-assets\` phải có portable ZIP, installer, `update-manifest.json`,
`runtime-versions.json`, model manifest/component, Tesseract component/manifest,
inventory build và `SHA256SUMS.txt`. Không đóng gói `.venv`, `.runtime`,
settings, output người dùng, API key, dataset hoặc audit data.
