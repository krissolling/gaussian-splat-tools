# Windows GPU Training Setup Script
# Run this in PowerShell as Administrator
#
# Usage: Right-click PowerShell -> Run as Administrator, then:
#   cd C:\path\to\gaussian-splat-tools\windows
#   .\setup_windows.ps1

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Gaussian Splat - Windows GPU Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Please run this script as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell -> Run as Administrator" -ForegroundColor Yellow
    exit 1
}

# ============================================
# Step 1: Enable OpenSSH Server
# ============================================
Write-Host "[1/6] Setting up OpenSSH Server..." -ForegroundColor Green

$sshCapability = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($sshCapability.State -ne 'Installed') {
    Write-Host "    Installing OpenSSH Server..."
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
} else {
    Write-Host "    OpenSSH Server already installed"
}

# Start and enable SSH service
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
Write-Host "    SSH service started and enabled"

# Firewall rule
$fwRule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
if (-not $fwRule) {
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
    Write-Host "    Firewall rule added"
}

# Get IP address
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -notlike "169.*" } | Select-Object -First 1).IPAddress
Write-Host "    Your IP address: $ip" -ForegroundColor Yellow

# ============================================
# Step 2: Install Miniconda if needed
# ============================================
Write-Host ""
Write-Host "[2/6] Checking Miniconda..." -ForegroundColor Green

$condaPath = "$env:USERPROFILE\miniconda3\Scripts\conda.exe"
$condaPathAlt = "C:\ProgramData\miniconda3\Scripts\conda.exe"

if (Test-Path $condaPath) {
    Write-Host "    Miniconda found at $condaPath"
    $conda = $condaPath
} elseif (Test-Path $condaPathAlt) {
    Write-Host "    Miniconda found at $condaPathAlt"
    $conda = $condaPathAlt
} elseif (Get-Command conda -ErrorAction SilentlyContinue) {
    Write-Host "    Conda found in PATH"
    $conda = "conda"
} else {
    Write-Host "    Downloading Miniconda..."
    $minicondaUrl = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
    $minicondaInstaller = "$env:TEMP\Miniconda3-latest-Windows-x86_64.exe"
    Invoke-WebRequest -Uri $minicondaUrl -OutFile $minicondaInstaller

    Write-Host "    Installing Miniconda (this may take a few minutes)..."
    Start-Process -FilePath $minicondaInstaller -ArgumentList "/S /D=$env:USERPROFILE\miniconda3" -Wait
    $conda = "$env:USERPROFILE\miniconda3\Scripts\conda.exe"

    # Add to PATH for this session
    $env:PATH = "$env:USERPROFILE\miniconda3\Scripts;$env:USERPROFILE\miniconda3;$env:PATH"
}

# ============================================
# Step 3: Create conda environment
# ============================================
Write-Host ""
Write-Host "[3/6] Creating conda environment 'splat'..." -ForegroundColor Green

# Initialize conda for PowerShell
& $conda init powershell 2>$null

# Check if environment exists
$envExists = & $conda env list | Select-String "^splat\s"
if ($envExists) {
    Write-Host "    Environment 'splat' already exists"
} else {
    Write-Host "    Creating new environment..."
    & $conda create -n splat python=3.10 -y
}

# ============================================
# Step 4: Install CUDA dependencies
# ============================================
Write-Host ""
Write-Host "[4/6] Installing CUDA dependencies..." -ForegroundColor Green

# Activate environment and install packages
$activateScript = @"
& '$conda' activate splat
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install plyfile tqdm pillow numpy
"@

# Run in the splat environment
& $conda run -n splat pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
& $conda run -n splat pip install plyfile tqdm pillow numpy opencv-python

Write-Host "    PyTorch with CUDA installed"

# ============================================
# Step 5: Install COLMAP
# ============================================
Write-Host ""
Write-Host "[5/6] Installing COLMAP..." -ForegroundColor Green

$colmapPath = "C:\splat\colmap"
$colmapExe = "$colmapPath\COLMAP.bat"

if (Test-Path $colmapExe) {
    Write-Host "    COLMAP already installed"
} else {
    Write-Host "    Downloading COLMAP..."
    $colmapUrl = "https://github.com/colmap/colmap/releases/download/3.9.1/COLMAP-3.9.1-windows-cuda.zip"
    $colmapZip = "$env:TEMP\colmap.zip"

    Invoke-WebRequest -Uri $colmapUrl -OutFile $colmapZip

    Write-Host "    Extracting COLMAP..."
    New-Item -ItemType Directory -Force -Path "C:\splat" | Out-Null
    Expand-Archive -Path $colmapZip -DestinationPath "C:\splat" -Force

    # Rename folder
    $extractedFolder = Get-ChildItem "C:\splat" -Directory | Where-Object { $_.Name -like "COLMAP*" } | Select-Object -First 1
    if ($extractedFolder -and $extractedFolder.Name -ne "colmap") {
        Rename-Item $extractedFolder.FullName "colmap"
    }

    Write-Host "    COLMAP installed to C:\splat\colmap"
}

# Add COLMAP to PATH
$colmapBin = "C:\splat\colmap"
if ($env:PATH -notlike "*$colmapBin*") {
    [Environment]::SetEnvironmentVariable("PATH", "$env:PATH;$colmapBin", [EnvironmentVariableTarget]::User)
    $env:PATH = "$env:PATH;$colmapBin"
}

# ============================================
# Step 6: Setup working directories and scripts
# ============================================
Write-Host ""
Write-Host "[6/6] Setting up directories and scripts..." -ForegroundColor Green

# Create directories
New-Item -ItemType Directory -Force -Path "C:\splat\jobs" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\splat\scripts" | Out-Null

# Copy training script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path "$scriptDir\windows_train.py") {
    Copy-Item "$scriptDir\windows_train.py" "C:\splat\scripts\" -Force
    Write-Host "    Training script copied to C:\splat\scripts\"
}

# Create a wrapper batch file for easy SSH execution
$wrapperContent = @"
@echo off
call %USERPROFILE%\miniconda3\Scripts\activate.bat splat
python C:\splat\scripts\windows_train.py %*
"@
Set-Content -Path "C:\splat\train.bat" -Value $wrapperContent

Write-Host "    Created C:\splat\train.bat wrapper"

# ============================================
# Verify installation
# ============================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verifying installation..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check CUDA
Write-Host ""
Write-Host "CUDA check:" -ForegroundColor Yellow
& $conda run -n splat python -c "import torch; print(f'  CUDA available: {torch.cuda.is_available()}'); print(f'  GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"

# Check COLMAP
Write-Host ""
Write-Host "COLMAP check:" -ForegroundColor Yellow
if (Test-Path "C:\splat\colmap\COLMAP.bat") {
    Write-Host "  COLMAP installed at C:\splat\colmap"
} else {
    Write-Host "  WARNING: COLMAP not found" -ForegroundColor Red
}

# ============================================
# Print summary
# ============================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Your Windows IP: $ip" -ForegroundColor Yellow
Write-Host ""
Write-Host "On your Mac, run:" -ForegroundColor Cyan
Write-Host "  python video_to_splat.py --video video.mp4 --output ./splat \" -ForegroundColor White
Write-Host "    --remote --remote-host $ip --remote-user $env:USERNAME --save-remote-config" -ForegroundColor White
Write-Host ""
Write-Host "Or test SSH connection:" -ForegroundColor Cyan
Write-Host "  ssh $env:USERNAME@$ip" -ForegroundColor White
Write-Host ""
Write-Host "Files installed:" -ForegroundColor Cyan
Write-Host "  C:\splat\colmap\      - COLMAP with CUDA"
Write-Host "  C:\splat\scripts\     - Training scripts"
Write-Host "  C:\splat\jobs\        - Job working directory"
Write-Host "  C:\splat\train.bat    - Training wrapper"
Write-Host ""
