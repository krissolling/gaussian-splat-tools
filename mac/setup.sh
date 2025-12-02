#!/bin/bash
#
# Setup Script for Video to Gaussian Splat Pipeline
# ==================================================
# This script installs all dependencies needed for the video-to-splat pipeline on macOS
#

set -e

echo "========================================"
echo "Gaussian Splat Pipeline - macOS Setup"
echo "========================================"
echo ""

# Check for Apple Silicon
if [[ $(uname -m) != "arm64" ]]; then
    echo "Warning: This setup is optimized for Apple Silicon (M1/M2/M3)."
    echo "Some features may not work on Intel Macs."
    echo ""
fi

# Install Homebrew if not present
if ! command -v brew &> /dev/null; then
    echo "[1/4] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add to PATH for Apple Silicon
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "[1/4] Homebrew already installed"
fi

# Install COLMAP
if ! command -v colmap &> /dev/null; then
    echo "[2/4] Installing COLMAP..."
    brew install colmap
else
    echo "[2/4] COLMAP already installed"
fi

# Install ImageMagick
if ! command -v magick &> /dev/null; then
    echo "[3/4] Installing ImageMagick..."
    brew install imagemagick
else
    echo "[3/4] ImageMagick already installed"
fi

# Install FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "[4/4] Installing FFmpeg..."
    brew install ffmpeg
else
    echo "[4/4] FFmpeg already installed"
fi

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "All dependencies installed. You can now run:"
echo ""
echo "  python -u video_to_splat.py --video your_video.mp4 --output ./output"
echo ""
echo "Don't forget to download Brush from:"
echo "  https://github.com/ArthurBrussee/brush/releases"
echo ""
echo "Get the Apple Silicon release:"
echo "  brush-aarch64-apple-darwin.zip"
echo ""
