param(
    [switch]$SkipInstall,
    [switch]$SkipModelWarmup
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$ReleaseRoot = Join-Path $Root "release"
$WorkPath = Join-Path $Root "build\pyinstaller"
$Spec = Join-Path $Root "CheckVehicleOCR.spec"

if (-not (Test-Path -LiteralPath $Python)) {
    & python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Không tạo được .venv." }
}

$env:PYTHONNOUSERSITE = "1"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
if (-not $SkipInstall) {
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Không nâng được pip trong .venv." }
    & $Python -m pip install -r (Join-Path $Root "requirements-build.txt")
    if ($LASTEXITCODE -ne 0) { throw "Không cài được dependency build vào .venv." }
}

$Version = (& $Python -c "from check_vehicle_ocr.version import VERSION; print(VERSION)").Trim()
$Commit = (& git -C $Root rev-parse HEAD).Trim()
$Remote = (& git -C $Root remote get-url origin).Trim()
$Repository = ""
if ($Remote -match "github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$") { $Repository = "$($Matches[1])/$($Matches[2])" }
& $Python (Join-Path $Root "tools\write_build_metadata.py") --commit $Commit --repository $Repository
if ($LASTEXITCODE -ne 0) { throw "Không tạo được build metadata." }

if (-not $SkipModelWarmup) {
    $env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"
    & $Python -c "from check_vehicle_ocr.paddle_ocr_engine import _get_ocr; _get_ocr(); print('PaddleOCR models ready')"
    if ($LASTEXITCODE -ne 0) { throw "PaddleOCR model warm-up failed." }
}

& $Python -m PyInstaller --noconfirm --clean --distpath $ReleaseRoot --workpath $WorkPath $Spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }

Write-Host "Build complete: $(Join-Path $ReleaseRoot 'CheckVehicleOCR\CheckVehicleOCR.exe')"
Write-Host "Version: $Version"
