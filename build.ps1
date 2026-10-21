param(
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

Write-Host 'TrainerForge build' -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python is not on PATH. Install 64-bit Python 3.10+ and try again.'
}

if (-not $SkipTests) {
    Write-Host 'Running tests...' -ForegroundColor Cyan
    python -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed with exit code $LASTEXITCODE."
    }
}

Write-Host 'Building one-file windowed executable...' -ForegroundColor Cyan
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name TrainerForge `
    --icon 'trainerforge\assets\icon.ico' `
    --add-data 'trainerforge\assets;trainerforge\assets' `
    --version-file 'trainerforge\assets\version_info.txt' `
    'run.py'

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$exe = Join-Path $PSScriptRoot 'dist\TrainerForge.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Build completed without producing $exe."
}

$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
$sidecar = "$exe.sha256"
"$hash  TrainerForge.exe" | Set-Content -LiteralPath $sidecar -Encoding ASCII

Write-Host ''
Write-Host 'Build complete:' -ForegroundColor Green
Write-Host "  $exe"
Write-Host "  $sidecar"
Write-Host "  SHA-256: $hash"
Write-Host ''
Write-Host 'The executable is unsigned. SmartScreen may warn; publish the hash with any release.'
