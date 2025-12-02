#!/usr/bin/env python3
"""
Windows GPU Training Script
===========================

This script runs on Windows with a CUDA GPU to process Gaussian splat training.
Called remotely via SSH from the Mac skill.

Usage:
    python windows_train.py --input C:\splat\jobs\job_001 --steps 30000
"""

import argparse
import os
import subprocess
import sys
import shutil
from pathlib import Path


def run_colmap_cuda(workspace_dir: str):
    """Run COLMAP with CUDA acceleration."""
    print(f"\n[1/2] Running COLMAP with CUDA...")

    database_path = os.path.join(workspace_dir, "database.db")
    images_dir = os.path.join(workspace_dir, "images")
    sparse_dir = os.path.join(workspace_dir, "sparse")
    os.makedirs(sparse_dir, exist_ok=True)

    # Feature extraction with CUDA
    print("    Extracting features (CUDA)...")
    cmd_extract = [
        'colmap', 'feature_extractor',
        '--database_path', database_path,
        '--image_path', images_dir,
        '--ImageReader.single_camera', '1',
        '--SiftExtraction.use_gpu', '1'
    ]
    result = subprocess.run(cmd_extract, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Feature extraction failed: {result.stderr}")
        sys.exit(1)

    # Feature matching with CUDA
    print("    Matching features (CUDA)...")
    cmd_match = [
        'colmap', 'exhaustive_matcher',
        '--database_path', database_path,
        '--SiftMatching.use_gpu', '1'
    ]
    result = subprocess.run(cmd_match, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Feature matching failed: {result.stderr}")
        sys.exit(1)

    # Sparse reconstruction
    print("    Running sparse reconstruction...")
    cmd_mapper = [
        'colmap', 'mapper',
        '--database_path', database_path,
        '--image_path', images_dir,
        '--output_path', sparse_dir
    ]
    result = subprocess.run(cmd_mapper, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Sparse reconstruction failed: {result.stderr}")
        sys.exit(1)

    print("    COLMAP complete!")
    return sparse_dir


def run_gaussian_splatting(workspace_dir: str, total_steps: int = 30000):
    """
    Run Gaussian splatting training with CUDA.

    Supports either:
    - Original 3DGS (graphdeco-inria)
    - gsplat library
    """
    print(f"\n[2/2] Training Gaussian splat ({total_steps} steps)...")

    output_dir = os.path.join(workspace_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    # Check which implementation is available
    gs_original = shutil.which("python") and os.path.exists(
        os.path.expanduser("~/gaussian-splatting/train.py")
    )

    if gs_original:
        # Use original 3DGS implementation
        train_script = os.path.expanduser("~/gaussian-splatting/train.py")
        cmd = [
            'python', train_script,
            '-s', workspace_dir,
            '-m', output_dir,
            '--iterations', str(total_steps),
        ]
    else:
        # Use gsplat or nerfstudio splatfacto
        # This is a simplified version - adjust based on your setup
        cmd = [
            'python', '-c', f'''
import torch
from gsplat import rasterization
# Training code here - this is a placeholder
# In practice, you'd use nerfstudio or a custom training script
print("gsplat training - implement based on your setup")
'''
        ]

    print(f"    Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"Training failed with code {result.returncode}")
        sys.exit(1)

    # Find the output PLY file
    ply_files = list(Path(output_dir).rglob("*.ply"))
    if ply_files:
        print(f"    Training complete! Output: {ply_files[-1]}")
        return str(ply_files[-1])
    else:
        print("    Warning: No PLY file found in output")
        return None


def main():
    parser = argparse.ArgumentParser(description='GPU training for Gaussian splats')
    parser.add_argument('--input', '-i', required=True,
                        help='Input directory with images/')
    parser.add_argument('--steps', '-s', type=int, default=30000,
                        help='Training steps (default: 30000)')
    parser.add_argument('--skip-colmap', action='store_true',
                        help='Skip COLMAP (use existing sparse/)')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input directory not found: {args.input}")
        sys.exit(1)

    print("=" * 50)
    print("Windows GPU Training")
    print("=" * 50)
    print(f"Input:  {args.input}")
    print(f"Steps:  {args.steps}")

    # Check CUDA
    try:
        import torch
        if torch.cuda.is_available():
            print(f"GPU:    {torch.cuda.get_device_name(0)}")
        else:
            print("Warning: CUDA not available, will be slow!")
    except ImportError:
        print("Warning: PyTorch not found")

    print("=" * 50)

    # Run COLMAP
    if not args.skip_colmap:
        run_colmap_cuda(args.input)
    else:
        print("\n[1/2] Skipping COLMAP (using existing data)")

    # Run training
    ply_path = run_gaussian_splatting(args.input, args.steps)

    print(f"\n{'=' * 50}")
    print("Done!")
    if ply_path:
        print(f"Output: {ply_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
