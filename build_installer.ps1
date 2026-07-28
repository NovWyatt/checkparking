$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Exe = Join-Path $Root "release\CheckVehicleOCR\CheckVehicleOCR.exe"
if (-not (Test-Path $Exe)) {
    & (Join-Path $Root "build_exe.ps1")
}

$Iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $Iscc) {
    $Candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "E:\Inno Setup 6\ISCC.exe"
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path $Candidate) {
            $Iscc = $Candidate
            break
        }
    }
}

if (-not $Iscc) {
    $Shortcut = "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Inno Setup 6\Inno Setup Compiler.lnk"
    if (Test-Path $Shortcut) {
        $Shell = New-Object -ComObject WScript.Shell
        $Target = $Shell.CreateShortcut($Shortcut).TargetPath
        $Candidate = Join-Path (Split-Path -Parent $Target) "ISCC.exe"
        if (Test-Path $Candidate) {
            $Iscc = $Candidate
        }
    }
}

if (-not $Iscc) {
    throw "Khong tim thay Inno Setup ISCC.exe. Hay cai Inno Setup 6 roi chay lai."
}

& $Iscc (Join-Path $Root "installer\CheckVehicleOCR.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compile failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Installer:"
Write-Host (Join-Path $Root "installer\Output\CheckVehicleOCR_Setup.exe")
