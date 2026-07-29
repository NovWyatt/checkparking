param(
    [switch]$SkipBuild,
    [switch]$PortableOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not $SkipBuild) {
    if ($PortableOnly) { & (Join-Path $Root "build_exe.ps1") } else { & (Join-Path $Root "build_installer.ps1") }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if (-not (Test-Path -LiteralPath $Python)) { throw "Không tìm thấy .venv." }
$Version = (& $Python -c "from check_vehicle_ocr.version import VERSION; print(VERSION)").Trim()
$Remote = (& git -C $Root remote get-url origin).Trim()
if ($Remote -notmatch "github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$") { throw "Remote origin không phải GitHub repository hợp lệ." }
$Repository = "$($Matches[1])/$($Matches[2])"
$Arguments = @(
    (Join-Path $Root "tools\create_release_assets.py"),
    "--version", $Version,
    "--input-dir", (Join-Path $Root "release\CheckVehicleOCR"),
    "--output-dir", (Join-Path $Root "release-assets"),
    "--repository", $Repository
)
$ReleaseNotesPath = Join-Path $Root ("docs\release-notes-v" + $Version + ".md")
if (Test-Path -LiteralPath $ReleaseNotesPath) {
    $Arguments += @("--release-notes", (Get-Content -LiteralPath $ReleaseNotesPath -Raw -Encoding UTF8))
}
if (-not $PortableOnly) { $Arguments += @("--installer", (Join-Path $Root "installer\Output\CheckVehicleOCR-$Version-windows-x64-setup.exe")) }
& $Python @Arguments
if ($LASTEXITCODE -ne 0) { throw "Không tạo được release assets." }
