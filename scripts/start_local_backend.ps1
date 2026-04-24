$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$embeddedPython = Resolve-Path -Path (Join-Path $repoRoot "..\tools\python-3.11.9-embed-amd64\python.exe") -ErrorAction SilentlyContinue
if ($embeddedPython) {
    $python = $embeddedPython.Path
} else {
    $python = "python"
}

$env:DATABASE_URL = "sqlite+pysqlite:///./local_dev.db"
$env:UPLOADS_DIR = Join-Path $repoRoot "uploads"
$env:JWT_SECRET_KEY = "dev-secret-key"

Write-Host ""
Write-Host "Energy Bill AI Backend - local dev" -ForegroundColor Cyan
Write-Host "Repo: $repoRoot"
Write-Host "Python: $python"
Write-Host "Database: $env:DATABASE_URL"
Write-Host ""
Write-Host "Backend URLs:" -ForegroundColor Yellow
Write-Host "  Local: http://127.0.0.1:8000/health"
Write-Host "  LAN:   http://192.168.31.19:8000/health"
Write-Host ""
Write-Host "Keep this PowerShell window open while using the Android app." -ForegroundColor Yellow
Write-Host "Starting Uvicorn on 0.0.0.0:8000..."
Write-Host ""

& $python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
