# Gaussian Splat Tools

Convert videos to 3D Gaussian splats. Supports local Mac training (Brush) or remote Windows GPU training (4090).

## Quick Start

### Mac Only (Local Training)
```bash
cd mac
./setup.sh
python -u video_to_splat.py --video your_video.mp4 --output ./splat
```

### Mac + Windows GPU (Remote Training)
```bash
# On Windows: Run setup script (see below)
# On Mac:
python -u video_to_splat.py --video your_video.mp4 --output ./splat \
  --remote --remote-host 192.168.1.XXX --remote-user YourWindowsUsername
```

---

## Windows Setup (One-Time)

### Step 1: Clone This Repo on Windows

Open PowerShell:
```powershell
cd C:\
git clone https://github.com/YOUR_USERNAME/gaussian-splat-tools.git
cd gaussian-splat-tools\windows
```

Or download the ZIP and extract to `C:\gaussian-splat-tools\`

### Step 2: Run Setup Script

**Right-click PowerShell → Run as Administrator**, then:
```powershell
cd C:\gaussian-splat-tools\windows
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup_windows.ps1
```

This will:
- Enable OpenSSH server
- Install Miniconda (if needed)
- Create `splat` conda environment with PyTorch CUDA
- Download COLMAP with CUDA support
- Create working directories at `C:\splat\`

### Step 3: Note Your Windows IP

The script will show your IP at the end, like:
```
Your Windows IP: 192.168.1.100
```

You can also find it with:
```powershell
ipconfig
# Look for "IPv4 Address" under your network adapter
```

---

## SSH Setup (Mac → Windows)

### On Windows (Already done by setup script)

Verify SSH is running:
```powershell
Get-Service sshd
# Should show "Running"
```

### On Mac

#### 1. Test SSH Connection
```bash
ssh YourWindowsUsername@192.168.1.XXX
# Enter your Windows password when prompted
# Type 'exit' to disconnect
```

#### 2. Set Up SSH Key (No Password Prompts)
```bash
# Generate key if you don't have one
ls ~/.ssh/id_ed25519 || ssh-keygen -t ed25519

# Copy key to Windows
ssh-copy-id YourWindowsUsername@192.168.1.XXX
# Enter password one last time

# Test passwordless login
ssh YourWindowsUsername@192.168.1.XXX
# Should connect without password prompt
```

#### 3. Save Remote Config (Optional)
```bash
# First run with --save-remote-config to remember settings
python -u video_to_splat.py --video test.mp4 --output ./test \
  --remote --remote-host 192.168.1.XXX --remote-user YourWindowsUsername \
  --save-remote-config --skip-training

# Future runs just need --remote
python -u video_to_splat.py --video video.mp4 --output ./splat --remote
```

---

## Troubleshooting

### SSH Connection Refused
```powershell
# On Windows, check SSH service
Get-Service sshd
Start-Service sshd

# Check firewall
Get-NetFirewallRule -Name "*ssh*"
```

### SSH Asks for Password Every Time
```bash
# On Mac, ensure key was copied
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@host

# On Windows, check authorized_keys file exists
# It should be at: C:\Users\USERNAME\.ssh\authorized_keys
```

### CUDA Not Found on Windows
```powershell
# Activate conda env and check
conda activate splat
python -c "import torch; print(torch.cuda.is_available())"

# If False, reinstall PyTorch
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### rsync Not Found (Windows)
The script uses SSH for file transfer. If rsync is needed:
```powershell
# Install Git for Windows (includes rsync)
winget install Git.Git
```

---

## File Structure

```
gaussian-splat-tools/
├── README.md
├── mac/
│   ├── setup.sh              # Install Mac dependencies
│   └── video_to_splat.py     # Main pipeline script
└── windows/
    ├── setup_windows.ps1     # Windows setup script
    └── windows_train.py      # GPU training script
```

After Windows setup:
```
C:\splat\
├── colmap\           # COLMAP with CUDA
├── scripts\          # Training scripts
├── jobs\             # Working directory for jobs
└── train.bat         # Training wrapper
```

---

## Usage Examples

### Basic (Local Mac)
```bash
python -u video_to_splat.py --video video.mp4 --output ./my_splat
```

### Remote GPU Training
```bash
python -u video_to_splat.py --video video.mp4 --output ./my_splat --remote
```

### More Frames (Better Quality)
```bash
python -u video_to_splat.py --video video.mp4 --output ./my_splat --fps 3
```

### High Quality (More Steps)
```bash
python -u video_to_splat.py --video video.mp4 --output ./my_splat --steps 60000
```

### Headless (No Viewer)
```bash
python -u video_to_splat.py --video video.mp4 --output ./my_splat --no-viewer
```

---

## Performance Comparison

| | Mac M1 | Windows 4090 |
|--|--------|--------------|
| COLMAP | 5 min (CPU) | 30 sec (CUDA) |
| Training 30k | 45 min | 3 min |
| Training 100k | 2.5 hrs | 10 min |

---

## Credits

- [Brush](https://github.com/ArthurBrussee/brush) - Mac Gaussian splatting
- [COLMAP](https://colmap.github.io/) - Structure from Motion
- [3D Gaussian Splatting](https://github.com/graphdeco-inria/gaussian-splatting) - Original implementation
