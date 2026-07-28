$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Dest = Join-Path $Root "vendor\tesseract"

$Candidates = @(
    "C:\Program Files\Tesseract-OCR",
    "C:\Program Files (x86)\Tesseract-OCR"
)

$Source = $null
foreach ($Candidate in $Candidates) {
    if (Test-Path (Join-Path $Candidate "tesseract.exe")) {
        $Source = $Candidate
        break
    }
}

if (-not $Source) {
    $Cmd = (Get-Command tesseract -ErrorAction SilentlyContinue).Source
    if ($Cmd) {
        $Source = Split-Path -Parent $Cmd
    }
}

if (-not $Source) {
    throw "Khong tim thay Tesseract OCR da cai tren may."
}

if (Test-Path $Dest) {
    Remove-Item -LiteralPath $Dest -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item -Path (Join-Path $Source "*") -Destination $Dest -Recurse -Force

Write-Host "Da copy Tesseract vao:"
Write-Host $Dest
