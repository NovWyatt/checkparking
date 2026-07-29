param(
    [switch]$SkipBuild,
    [switch]$PortableOnly,
    [string]$TesseractComponent = "",
    [string]$TesseractManifest = ""
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
$ReleaseAssetDir = Join-Path $Root "release-assets"
if (-not $TesseractComponent) { $TesseractComponent = Join-Path $ReleaseAssetDir "CheckVehicleOCR-Tesseract-5.5.3-win-x64.zip" }
if (-not $TesseractManifest) { $TesseractManifest = Join-Path $ReleaseAssetDir "tesseract-component-manifest.json" }
if (-not (Test-Path -LiteralPath $TesseractComponent) -or -not (Test-Path -LiteralPath $TesseractManifest)) {
    throw "Verified Tesseract component and manifest are required before creating a v1.9 release."
}
& $Python (Join-Path $Root "tools\build_model_component.py") --version $Version --tag "v$Version" --repository "NovWyatt/checkparking" --output-dir $ReleaseAssetDir
if ($LASTEXITCODE -ne 0) { throw "Unable to create the verified OCR model component." }
$ModelComponent = Join-Path $ReleaseAssetDir "CheckVehicleOCR-PP-OCRv6-small-model-$Version.zip"
$ModelManifest = Join-Path $ReleaseAssetDir "model-manifest.json"
$RuntimeVersions = Join-Path $Root "build\runtime-versions.json"
$TesseractBuildInventory = Join-Path $Root "tools\tesseract-build-lock.json"
if (-not (Test-Path -LiteralPath $RuntimeVersions)) { throw "Runtime version metadata is missing; build the executable first." }
$Remote = (& git -C $Root remote get-url origin).Trim()
if ($Remote -notmatch "github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$") { throw "Remote origin không phải GitHub repository hợp lệ." }
$Repository = "$($Matches[1])/$($Matches[2])"
$Arguments = @(
    (Join-Path $Root "tools\create_release_assets.py"),
    "--version", $Version,
    "--input-dir", (Join-Path $Root "release\CheckVehicleOCR"),
    "--output-dir", $ReleaseAssetDir,
    "--repository", $Repository
)
$Arguments += @(
    "--extra-asset", $TesseractComponent,
    "--extra-asset", $TesseractManifest,
    "--extra-asset", $ModelComponent,
    "--extra-asset", $ModelManifest,
    "--extra-asset", $RuntimeVersions,
    "--extra-asset", $TesseractBuildInventory
)
$ReleaseNotesPath = Join-Path $Root ("docs\release-notes-v" + $Version + ".md")
if (Test-Path -LiteralPath $ReleaseNotesPath) {
    $Arguments += @("--release-notes", (Get-Content -LiteralPath $ReleaseNotesPath -Raw -Encoding UTF8))
}
if (-not $PortableOnly) { $Arguments += @("--installer", (Join-Path $Root "installer\Output\CheckVehicleOCR-$Version-windows-x64-setup.exe")) }
& $Python @Arguments
if ($LASTEXITCODE -ne 0) { throw "Không tạo được release assets." }
