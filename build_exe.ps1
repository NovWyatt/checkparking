param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$ReleaseRoot = Join-Path $Root "release"
$WorkPath = Join-Path ([System.IO.Path]::GetTempPath()) "CheckVehicleOCR_pyinstaller"
$Spec = Join-Path $Root "CheckVehicleOCR.spec"

function Test-VenvPython {
    param([string]$PythonPath)
    if (-not (Test-Path $PythonPath)) {
        return $false
    }
    try {
        $PreviousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $PythonPath -c "import sys; print(sys.executable)" *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
}

function New-ProjectVenv {
    $PythonCommands = @(
        "python",
        "py",
        "D:\Python\python.exe"
    )
    foreach ($Command in $PythonCommands) {
        try {
            & $Command -m venv $Venv
            if ($LASTEXITCODE -eq 0 -and (Test-VenvPython $Python)) {
                return
            }
        }
        catch {
        }
    }
    throw "Khong tao duoc .venv. Hay cai Python 3.12 hoac sua PATH roi chay lai."
}

if (-not (Test-VenvPython $Python)) {
    if (Test-Path $Venv) {
        $ResolvedVenv = (Resolve-Path $Venv).Path
        if ($ResolvedVenv.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $ResolvedVenv -Recurse -Force
        }
    }
    New-ProjectVenv
}

if (-not $SkipInstall) {
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r (Join-Path $Root "requirements.txt")
}

$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"
$WarmupScript = "from check_vehicle_ocr.paddle_ocr_engine import _get_ocr; _get_ocr(); print('PaddleOCR models ready')"
& $Python -c $WarmupScript
if ($LASTEXITCODE -ne 0) {
    throw "PaddleOCR model warm-up failed with exit code $LASTEXITCODE."
}

Push-Location $Root
try {
    & $Python -m PyInstaller --noconfirm --clean --distpath $ReleaseRoot --workpath $WorkPath $Spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$OldOutputs = @("dist", "dist_release", "build_release", "build")
foreach ($Name in $OldOutputs) {
    $Path = Join-Path $Root $Name
    if (Test-Path $Path) {
        $Resolved = (Resolve-Path $Path).Path
        if ($Resolved.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
            try {
                Remove-Item -LiteralPath $Resolved -Recurse -Force -ErrorAction Stop
            }
            catch {
                Write-Warning "Khong xoa duoc output cu dang bi khoa: $Resolved. Dong file/app dang mo roi chay lai script neu muon don sach hoan toan."
            }
        }
    }
}

Write-Host ""
Write-Host "Build xong:"
Write-Host (Join-Path $Root "release\CheckVehicleOCR\CheckVehicleOCR.exe")
