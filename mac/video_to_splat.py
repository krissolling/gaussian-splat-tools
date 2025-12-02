#!/usr/bin/env python3
"""
Video to Gaussian Splat Pipeline for macOS
==========================================

This script automates the full process of converting a video into a trained
Gaussian splat using COLMAP for camera pose estimation and Brush for training.

Based on the tutorial for Brush + COLMAP on Mac (M1/M2/M3).

Prerequisites:
1. Homebrew installed
2. COLMAP: brew install colmap
3. ImageMagick: brew install imagemagick
4. FFmpeg: brew install ffmpeg
5. Brush app downloaded from: https://github.com/ArthurBrussee/brush/releases

Usage:
    python -u video_to_splat.py --video /path/to/video.mp4 --output /path/to/output

    # With custom settings
    python -u video_to_splat.py --video video.mp4 --output ./my_splat --fps 2 --steps 30000
"""

import argparse
import os
import subprocess
import shutil
import sys
import glob
import json
import time
from pathlib import Path

# Remote training configuration file
REMOTE_CONFIG_PATH = os.path.expanduser("~/.claude/commands/gaussian-splat/remote_config.json")

# Default Brush locations to search
BRUSH_SEARCH_PATHS = [
    "/Applications/brush_app",
    "/Applications/Brush.app/Contents/MacOS/brush_app",
    os.path.expanduser("~/Applications/brush_app"),
    os.path.expanduser("~/brush-app-aarch64-apple-darwin/brush_app"),
    os.path.expanduser("~/Downloads/brush-app-aarch64-apple-darwin/brush_app"),
]


def find_brush():
    """Find Brush executable."""
    # Check if BRUSH_PATH env var is set
    if os.environ.get('BRUSH_PATH'):
        path = os.environ['BRUSH_PATH']
        if os.path.exists(path):
            return path

    # Search common locations
    for path in BRUSH_SEARCH_PATHS:
        if os.path.exists(path):
            return path

    # Try to find it with glob
    home = os.path.expanduser("~")
    patterns = [
        f"{home}/**/brush_app",
        f"{home}/**/brush-app*/brush_app",
    ]
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]

    return None


def check_dependencies(brush_path: str = None):
    """Check if required dependencies are installed."""
    dependencies = {
        'ffmpeg': 'brew install ffmpeg',
        'colmap': 'brew install colmap',
        'magick': 'brew install imagemagick'
    }

    missing = []
    for cmd, install_cmd in dependencies.items():
        if shutil.which(cmd) is None:
            missing.append((cmd, install_cmd))

    if missing:
        print("Missing dependencies:")
        for cmd, install_cmd in missing:
            print(f"  - {cmd}: Install with '{install_cmd}'")
        sys.exit(1)

    # Check Brush
    if brush_path and not os.path.exists(brush_path):
        print(f"Error: Brush not found at {brush_path}")
        print("Download from: https://github.com/ArthurBrussee/brush/releases")
        sys.exit(1)

    print("[OK] All dependencies found")


def extract_frames(video_path: str, output_dir: str, fps: float = 2.0):
    """
    Extract frames from video at specified FPS.

    Args:
        video_path: Path to input video
        output_dir: Directory to save extracted frames
        fps: Frames per second to extract (default: 2)

    Returns:
        Tuple of (images_dir, frame_count)
    """
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    print(f"\n[1/5] Extracting frames at {fps} FPS...")

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', f'fps={fps}',
        '-q:v', '2',  # High quality JPEG
        os.path.join(images_dir, 'frame_%04d.jpg')
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error extracting frames: {result.stderr}")
        sys.exit(1)

    frame_count = len(list(Path(images_dir).glob('*.jpg')))
    print(f"    Extracted {frame_count} frames")

    return images_dir, frame_count


def resize_images(images_dir: str, resolution: int = 1600):
    """
    Resize images to target resolution using ImageMagick.

    Args:
        images_dir: Directory containing images
        resolution: Target resolution (longest edge)
    """
    print(f"\n[2/5] Resizing images to {resolution}px...")

    originals_dir = os.path.join(os.path.dirname(images_dir), "images_original")
    os.makedirs(originals_dir, exist_ok=True)

    # Move originals
    for img in Path(images_dir).glob('*.jpg'):
        shutil.copy(img, originals_dir)

    # Resize in place
    for img in Path(images_dir).glob('*.jpg'):
        cmd = [
            'magick', str(img),
            '-resize', f'{resolution}x{resolution}>',
            str(img)
        ]
        subprocess.run(cmd, capture_output=True)

    print(f"    Originals saved to: {originals_dir}")
    print(f"    Resized images in: {images_dir}")


def run_colmap(workspace_dir: str, matcher_type: str = "exhaustive"):
    """
    Run COLMAP to estimate camera poses.

    Args:
        workspace_dir: Directory containing 'images' folder
        matcher_type: Type of feature matching ('exhaustive', 'sequential')
    """
    print(f"\n[3/5] Running COLMAP ({matcher_type} matching)...")

    database_path = os.path.join(workspace_dir, "database.db")
    images_dir = os.path.join(workspace_dir, "images")
    sparse_dir = os.path.join(workspace_dir, "sparse")
    os.makedirs(sparse_dir, exist_ok=True)

    # Step 1: Feature extraction
    print("    Extracting features...")
    cmd_extract = [
        'colmap', 'feature_extractor',
        '--database_path', database_path,
        '--image_path', images_dir,
        '--ImageReader.single_camera', '1'
    ]
    result = subprocess.run(cmd_extract, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Feature extraction failed: {result.stderr}")
        sys.exit(1)

    # Step 2: Feature matching
    print(f"    Matching features ({matcher_type})...")
    if matcher_type == "sequential":
        cmd_match = [
            'colmap', 'sequential_matcher',
            '--database_path', database_path
        ]
    else:
        cmd_match = [
            'colmap', 'exhaustive_matcher',
            '--database_path', database_path
        ]

    result = subprocess.run(cmd_match, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Feature matching failed: {result.stderr}")
        sys.exit(1)

    # Step 3: Sparse reconstruction (mapping)
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

    # Step 4: Convert to text format for Brush compatibility
    print("    Converting to text format...")
    for model_dir in Path(sparse_dir).iterdir():
        if model_dir.is_dir():
            cmd_convert = [
                'colmap', 'model_converter',
                '--input_path', str(model_dir),
                '--output_path', str(model_dir),
                '--output_type', 'TXT'
            ]
            subprocess.run(cmd_convert, capture_output=True)

    print("    COLMAP reconstruction complete!")
    return sparse_dir


def get_smart_defaults(frame_count: int):
    """
    Calculate smart training defaults based on frame count.

    Best practices:
    - 200-1000 images is optimal
    - refine_every should roughly equal image count
    - More frames = can use more training steps

    Args:
        frame_count: Number of extracted frames

    Returns:
        Dict with recommended settings
    """
    defaults = {
        'steps': 30000,
        'refine_every': min(frame_count, 200),  # Refine roughly every "scene coverage"
        'sh_degree': 3,
        'export_every': 5000,
    }

    # Adjust based on frame count
    if frame_count < 50:
        print(f"    Warning: Only {frame_count} frames - quality may be limited")
        print(f"    Tip: Try increasing --fps to get more frames")
        defaults['steps'] = 20000  # Less data = less training needed
    elif frame_count < 100:
        defaults['steps'] = 25000
    elif frame_count > 300:
        defaults['steps'] = 35000  # More data can benefit from more training

    return defaults


def run_brush_training(
    brush_path: str,
    workspace_dir: str,
    total_steps: int = 30000,
    refine_every: int = 200,
    sh_degree: int = 3,
    export_every: int = 5000,
    max_resolution: int = 1600,
    with_viewer: bool = True
):
    """
    Run Brush to train the Gaussian splat.

    Args:
        brush_path: Path to Brush executable
        workspace_dir: Directory with COLMAP output
        total_steps: Total training steps
        refine_every: How often to refine/densify gaussians
        sh_degree: Spherical harmonics degree (0-3)
        export_every: Export checkpoint every N steps
        max_resolution: Max image resolution for training
        with_viewer: Whether to show the viewer window
    """
    print(f"\n[4/5] Training Gaussian splat with Brush...")
    print(f"    Steps: {total_steps}")
    print(f"    Refine every: {refine_every}")
    print(f"    SH degree: {sh_degree}")
    print(f"    Export every: {export_every} steps")
    print(f"    Viewer: {'enabled' if with_viewer else 'disabled'}")

    workspace_abs = os.path.abspath(workspace_dir)

    cmd = [
        brush_path,
        workspace_abs,
        '--total-steps', str(total_steps),
        '--refine-every', str(refine_every),
        '--sh-degree', str(sh_degree),
        '--export-every', str(export_every),
        '--export-path', workspace_abs,
        '--max-resolution', str(max_resolution),
    ]

    if with_viewer:
        cmd.append('--with-viewer')

    print(f"\n    Running: {' '.join(cmd)}\n")

    # Run Brush (this will block until training completes or user closes)
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"\n    Brush exited with code {result.returncode}")
    else:
        print(f"\n    Training complete!")

    return result.returncode


def load_remote_config():
    """Load remote training configuration."""
    if os.path.exists(REMOTE_CONFIG_PATH):
        with open(REMOTE_CONFIG_PATH) as f:
            return json.load(f)
    return None


def save_remote_config(host: str, user: str, remote_path: str):
    """Save remote training configuration."""
    config = {
        "host": host,
        "user": user,
        "remote_path": remote_path
    }
    os.makedirs(os.path.dirname(REMOTE_CONFIG_PATH), exist_ok=True)
    with open(REMOTE_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"    Saved remote config to {REMOTE_CONFIG_PATH}")


def ssh_cmd(host: str, user: str, command: str, capture: bool = False):
    """Run a command on remote host via SSH."""
    ssh = ['ssh', f'{user}@{host}', command]
    if capture:
        result = subprocess.run(ssh, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    else:
        return subprocess.run(ssh).returncode, None, None


def rsync_to_remote(local_path: str, host: str, user: str, remote_path: str):
    """Sync local directory to remote host."""
    cmd = [
        'rsync', '-avz', '--progress',
        local_path.rstrip('/') + '/',
        f'{user}@{host}:{remote_path}/'
    ]
    return subprocess.run(cmd).returncode


def rsync_from_remote(host: str, user: str, remote_path: str, local_path: str, pattern: str = "*.ply"):
    """Sync files from remote host to local."""
    cmd = [
        'rsync', '-avz', '--progress',
        f'{user}@{host}:{remote_path}/{pattern}',
        local_path + '/'
    ]
    return subprocess.run(cmd).returncode


def run_remote_training(
    workspace_dir: str,
    host: str,
    user: str,
    remote_base_path: str = "/c/splat/jobs",
    total_steps: int = 30000,
):
    """
    Run training on remote Windows machine with CUDA GPU.

    Args:
        workspace_dir: Local directory with images/
        host: Remote host IP or hostname
        user: SSH username
        remote_base_path: Base path on remote for jobs
        total_steps: Training iterations
    """
    print(f"\n[4/5] Remote GPU Training")
    print(f"    Host: {user}@{host}")
    print(f"    Steps: {total_steps}")

    workspace_abs = os.path.abspath(workspace_dir)
    job_id = f"job_{int(time.time())}"
    remote_job_path = f"{remote_base_path}/{job_id}"

    # Step 1: Create remote directory
    print(f"\n    Creating remote directory: {remote_job_path}")
    ret, _, err = ssh_cmd(host, user, f'mkdir -p "{remote_job_path}"', capture=True)
    if ret != 0:
        print(f"    Error creating remote directory: {err}")
        return 1

    # Step 2: Sync images to remote
    print(f"\n    Syncing images to {host}...")
    local_images = os.path.join(workspace_abs, "images")
    ret = rsync_to_remote(local_images, host, user, f"{remote_job_path}/images")
    if ret != 0:
        print("    Error syncing images")
        return 1

    # Step 3: Run COLMAP + training on remote
    print(f"\n    Running COLMAP + training on remote GPU...")
    # Use the Windows training script we created
    train_cmd = f'cd "{remote_job_path}" && python C:/splat/windows_train.py --input "{remote_job_path}" --steps {total_steps}'

    print(f"    Command: {train_cmd}")
    ret, _, _ = ssh_cmd(host, user, train_cmd)
    if ret != 0:
        print(f"    Remote training may have failed (exit code {ret})")
        # Continue anyway to try to fetch results

    # Step 4: Sync results back
    print(f"\n    Syncing results back...")
    # Try to get PLY files from various locations
    for pattern in ["output/*.ply", "*.ply", "output/**/*.ply"]:
        rsync_from_remote(host, user, remote_job_path, workspace_abs, pattern)

    # Check if we got any PLY files
    ply_files = list(Path(workspace_abs).rglob("*.ply"))
    if ply_files:
        print(f"    Retrieved {len(ply_files)} PLY file(s)")
    else:
        print("    Warning: No PLY files retrieved")

    return 0


def print_summary(workspace_dir: str, frame_count: int):
    """Print final summary."""
    workspace_abs = os.path.abspath(workspace_dir)

    # Find exported PLY files
    ply_files = sorted(glob.glob(os.path.join(workspace_abs, "*.ply")))

    print(f"""
[5/5] Pipeline Complete!
========================

Output directory: {workspace_abs}
Frames processed: {frame_count}
""")

    if ply_files:
        print("Exported splats:")
        for ply in ply_files:
            size_mb = os.path.getsize(ply) / (1024 * 1024)
            print(f"  - {os.path.basename(ply)} ({size_mb:.1f} MB)")
    else:
        print("No .ply exports found yet (training may have been interrupted)")

    print(f"""
To view your splat:
  - Open in Brush: brush_app {workspace_abs}
  - Upload to: https://supersplat.io/
  - Or use any PLY viewer
""")


def main():
    parser = argparse.ArgumentParser(
        description='Convert video to trained Gaussian splat',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (auto-detects settings)
  python -u video_to_splat.py --video my_video.mp4 --output ./my_splat

  # Custom training settings
  python -u video_to_splat.py --video video.mov --output ./output --steps 60000

  # More frames for better quality
  python -u video_to_splat.py --video video.mp4 --output ./output --fps 3

  # Headless training (no viewer window)
  python -u video_to_splat.py --video video.mp4 --output ./output --no-viewer

  # Skip COLMAP (reuse existing data)
  python -u video_to_splat.py --video video.mp4 --output ./output --skip-colmap

Environment variables:
  BRUSH_PATH    Path to Brush executable (auto-detected if not set)
        """
    )

    # Input/Output
    parser.add_argument('--video', '-v', required=True,
                        help='Path to input video file')
    parser.add_argument('--output', '-o', required=True,
                        help='Output directory for processed data and splat')

    # Frame extraction
    parser.add_argument('--fps', '-f', type=float, default=2.0,
                        help='Frames per second to extract (default: 2)')
    parser.add_argument('--resolution', '-r', type=int, default=1600,
                        help='Target image resolution (default: 1600)')
    parser.add_argument('--matcher', '-m', choices=['exhaustive', 'sequential'],
                        default='sequential',
                        help='COLMAP matcher type (default: sequential)')

    # Training settings
    parser.add_argument('--steps', '-s', type=int, default=None,
                        help='Training steps (default: auto based on frame count)')
    parser.add_argument('--sh-degree', type=int, default=3, choices=[0, 1, 2, 3],
                        help='Spherical harmonics degree (default: 3)')
    parser.add_argument('--export-every', type=int, default=5000,
                        help='Export checkpoint every N steps (default: 5000)')

    # Brush settings
    parser.add_argument('--brush-path', type=str, default=None,
                        help='Path to Brush executable (auto-detected)')
    parser.add_argument('--no-viewer', action='store_true',
                        help='Run training without viewer window')

    # Skip steps
    parser.add_argument('--skip-extract', action='store_true',
                        help='Skip frame extraction (use existing images)')
    parser.add_argument('--skip-colmap', action='store_true',
                        help='Skip COLMAP (use existing camera poses)')
    parser.add_argument('--skip-training', action='store_true',
                        help='Skip Brush training (only prepare data)')

    # Remote training options
    parser.add_argument('--remote', action='store_true',
                        help='Use remote Windows GPU for training')
    parser.add_argument('--remote-host', type=str,
                        help='Remote host IP or hostname (e.g., 192.168.1.100)')
    parser.add_argument('--remote-user', type=str,
                        help='SSH username on remote host')
    parser.add_argument('--remote-path', type=str, default='/c/splat/jobs',
                        help='Base path on remote for jobs (default: /c/splat/jobs)')
    parser.add_argument('--save-remote-config', action='store_true',
                        help='Save remote settings for future use')

    args = parser.parse_args()

    # Handle remote training configuration
    remote_host = args.remote_host
    remote_user = args.remote_user
    remote_path = args.remote_path

    if args.remote:
        # Load saved config if host/user not provided
        if not remote_host or not remote_user:
            saved_config = load_remote_config()
            if saved_config:
                remote_host = remote_host or saved_config.get('host')
                remote_user = remote_user or saved_config.get('user')
                remote_path = remote_path or saved_config.get('remote_path', '/c/splat/jobs')
                print(f"Using saved remote config: {remote_user}@{remote_host}")

        if not remote_host or not remote_user:
            print("Error: Remote training requires --remote-host and --remote-user")
            print("Example: --remote --remote-host 192.168.1.100 --remote-user kris")
            sys.exit(1)

        # Save config if requested
        if args.save_remote_config:
            save_remote_config(remote_host, remote_user, remote_path)

    # Find Brush (only needed for local training)
    brush_path = None
    if not args.remote and not args.skip_training:
        brush_path = args.brush_path or find_brush()
        if not brush_path:
            print("Error: Could not find Brush executable")
            print("Please either:")
            print("  1. Set BRUSH_PATH environment variable")
            print("  2. Use --brush-path /path/to/brush_app")
            print("  3. Download from: https://github.com/ArthurBrussee/brush/releases")
            print("  4. Use --remote for GPU training on Windows")
            sys.exit(1)

    # Validate inputs
    if not args.skip_extract and not os.path.exists(args.video):
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output, exist_ok=True)

    print("=" * 50)
    print("Video to Gaussian Splat Pipeline")
    print("=" * 50)
    print(f"Video:      {args.video}")
    print(f"Output:     {os.path.abspath(args.output)}")
    print(f"FPS:        {args.fps}")
    print(f"Resolution: {args.resolution}")
    print(f"Matcher:    {args.matcher}")
    if args.remote:
        print(f"Training:   REMOTE ({remote_user}@{remote_host})")
    elif brush_path:
        print(f"Training:   LOCAL (Brush: {brush_path})")
    print("=" * 50)

    # Check dependencies
    check_dependencies(brush_path if not args.skip_training else None)

    # Step 1: Extract frames from video
    if not args.skip_extract:
        images_dir, frame_count = extract_frames(args.video, args.output, args.fps)
    else:
        images_dir = os.path.join(args.output, "images")
        if not os.path.exists(images_dir):
            print(f"Error: Images directory not found: {images_dir}")
            sys.exit(1)
        frame_count = len(list(Path(images_dir).glob('*.jpg')))
        print(f"\n[1/5] Using existing {frame_count} frames")

    # Step 2: Resize images
    if not args.skip_extract:
        resize_images(images_dir, args.resolution)
    else:
        print(f"\n[2/5] Skipping resize (using existing images)")

    # Step 3: Run COLMAP
    if not args.skip_colmap:
        run_colmap(args.output, args.matcher)
    else:
        print(f"\n[3/5] Skipping COLMAP (using existing camera poses)")

    # Get smart defaults based on frame count
    defaults = get_smart_defaults(frame_count)
    total_steps = args.steps or defaults['steps']
    refine_every = defaults['refine_every']

    print(f"\n    Smart defaults for {frame_count} frames:")
    print(f"    - Training steps: {total_steps}")
    print(f"    - Refine every: {refine_every}")

    # Step 4: Run training
    if not args.skip_training:
        if args.remote:
            # Remote GPU training on Windows
            run_remote_training(
                workspace_dir=args.output,
                host=remote_host,
                user=remote_user,
                remote_base_path=remote_path,
                total_steps=total_steps,
            )
        else:
            # Local training with Brush
            run_brush_training(
                brush_path=brush_path,
                workspace_dir=args.output,
                total_steps=total_steps,
                refine_every=refine_every,
                sh_degree=args.sh_degree,
                export_every=args.export_every,
                max_resolution=args.resolution,
                with_viewer=not args.no_viewer
            )

    # Step 5: Print summary
    print_summary(args.output, frame_count)


if __name__ == "__main__":
    main()
