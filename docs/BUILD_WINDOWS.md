# Build Windows

Run from PowerShell at repository root:

```powershell
.\build_exe.ps1
.\build_installer.ps1 -SkipExeBuild
.\build_release_assets.ps1 -SkipBuild
```

The scripts use only `.venv\Scripts\python.exe` with `PYTHONNOUSERSITE=1`.
`build_exe.ps1` writes non-secret build metadata immediately before PyInstaller.
`release-assets\` contains the versioned portable ZIP, installer, manifest and
`SHA256SUMS.txt`. Do not package `.venv`, `.runtime`, settings, user output,
API keys, datasets or audit data.
