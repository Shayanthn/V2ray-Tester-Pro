# V2Ray Tester Pro - Setup Script for Windows
# Run this script in PowerShell

Write-Host "V2Ray Tester Pro - Setup Script" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

# Check Python version
Write-Host "`nChecking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = (python --version 2>&1) -replace 'Python ', ''
    Write-Host "Python $pythonVersion detected" -ForegroundColor Green
} catch {
    Write-Host "Python not found. Please install Python 3.11+" -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host "`nInstalling Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Download Xray core
Write-Host "`nDownloading Xray Core..." -ForegroundColor Yellow
try {
    $latestRelease = Invoke-RestMethod -Uri "https://api.github.com/repos/XTLS/Xray-core/releases/latest"
    $version = $latestRelease.tag_name
    Write-Host "Latest version: $version" -ForegroundColor Green
    
    $downloadUrl = "https://github.com/XTLS/Xray-core/releases/download/$version/Xray-windows-64.zip"
    $zipFile = "Xray-windows-64.zip"
    
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipFile
    Expand-Archive -Path $zipFile -DestinationPath . -Force
    Remove-Item $zipFile
    
    Write-Host "Xray Core installed" -ForegroundColor Green
} catch {
    Write-Host "Failed to download Xray Core: $_" -ForegroundColor Red
    Write-Host "Please download manually from: https://github.com/XTLS/Xray-core/releases" -ForegroundColor Yellow
}

# Create .env file
Write-Host "`nCreating .env file..." -ForegroundColor Yellow
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host ".env file created. Please edit it with your settings." -ForegroundColor Green
} else {
    Write-Host ".env file already exists" -ForegroundColor Blue
}

# Create directories
Write-Host "`nCreating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path subscriptions | Out-Null
New-Item -ItemType Directory -Force -Path logs | Out-Null
Write-Host "Directories created" -ForegroundColor Green

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "`nTo run the application:" -ForegroundColor Cyan
Write-Host "  GUI mode: python 'v2raytesterpro source.py'" -ForegroundColor White
Write-Host "  CLI mode: python 'v2raytesterpro source.py' --cli" -ForegroundColor White
