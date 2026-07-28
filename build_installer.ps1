param([switch]$SkipExeBuild)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { throw "Không tìm thấy .venv. Chạy build_exe.ps1 trước." }
if (-not $SkipExeBuild) { & (Join-Path $Root "build_exe.ps1"); if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }

$Iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $Iscc) {
    foreach ($Candidate in @("C:\Program Files (x86)\Inno Setup 6\ISCC.exe", "C:\Program Files\Inno Setup 6\ISCC.exe", (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"))) {
        if (Test-Path -LiteralPath $Candidate) { $Iscc = $Candidate; break }
    }
}
if (-not $Iscc) { throw "Không tìm thấy Inno Setup 6 (ISCC.exe)." }

$Version = (& $Python -c "from check_vehicle_ocr.version import VERSION; print(VERSION)").Trim()
$SourceDir = Join-Path $Root "release\CheckVehicleOCR"
& $Iscc "/DMyAppVersion=$Version" "/DSourceDir=$SourceDir" (Join-Path $Root "installer\CheckVehicleOCR.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE." }
Write-Host "Installer: $(Join-Path $Root "installer\Output\CheckVehicleOCR-$Version-windows-x64-setup.exe")"
