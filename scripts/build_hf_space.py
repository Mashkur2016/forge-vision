"""
Assemble a deployable Hugging Face Space repo for FORGE-Vision.

HF Docker Spaces require a root ``Dockerfile`` and a root ``README.md`` with
front-matter. This script copies the app + Space artifacts from this repo into a
clean output directory laid out exactly as the Space repo expects, optionally
initialising git + Git LFS and committing.

Usage:
    python scripts/build_hf_space.py                       # assemble ./hf_space_build
    python scripts/build_hf_space.py --out ../forge-space  # custom dir
    python scripts/build_hf_space.py --git-init            # + git/LFS/commit
    python scripts/build_hf_space.py --git-init --remote https://huggingface.co/spaces/<user>/<name>

Then push:
    cd <out> && git push -u space main        # if --remote was given
    # or add the remote yourself and push.
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def _on_rm_error(func, path, _exc):
    """rmtree handler: clear read-only bit (Git/LFS objects on Windows) and retry."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass

REPO = Path(__file__).resolve().parent.parent

# Single files copied to the Space root (src -> dest name).
FILE_MAP = {
    "Dockerfile.hf": "Dockerfile",
    "space/README.md": "README.md",
    "space/.gitattributes": ".gitattributes",
    "requirements-web.txt": "requirements-web.txt",
    "alembic.ini": "alembic.ini",
}

# Directories copied verbatim (with caches stripped). data/sops holds the SOP
# definitions the app + seeder need (the large data/synthetic videos are NOT
# shipped).
DIR_COPY = ["src", ".streamlit", "config", "alembic", "space", "data/sops"]

# The trained checkpoint (shipped via Git LFS).
MODEL_REL = "models/action_recognizer_best.pth"

_IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".pytest_cache", ".mypy_cache", "*.log"
)


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def assemble(out: Path) -> None:
    if out.exists():
        print(f"Cleaning existing {out} ...")
        shutil.rmtree(out, onerror=_on_rm_error)
    out.mkdir(parents=True)

    for src_rel, dst_rel in FILE_MAP.items():
        src = REPO / src_rel
        if not src.exists():
            sys.exit(f"ERROR: missing required file: {src_rel}")
        shutil.copy2(src, out / dst_rel)
        print(f"  + {dst_rel}")

    for d in DIR_COPY:
        src = REPO / d
        if not src.exists():
            sys.exit(f"ERROR: missing required directory: {d}/")
        shutil.copytree(src, out / d, ignore=_IGNORE)
        print(f"  + {d}/")

    model = REPO / MODEL_REL
    if not model.exists():
        sys.exit(f"ERROR: model checkpoint not found: {MODEL_REL}")
    (out / "models").mkdir(exist_ok=True)
    shutil.copy2(model, out / MODEL_REL)
    size_mb = model.stat().st_size / 1e6
    print(f"  + {MODEL_REL}  ({size_mb:.1f} MB, ships via Git LFS)")


def git_init(out: Path, remote: str | None) -> None:
    print("Initialising git + Git LFS ...")
    _run(["git", "init", "-b", "main"], out)
    _run(["git", "lfs", "install", "--local"], out)
    _run(["git", "lfs", "track", "*.pth", "*.pt"], out)
    _run(["git", "add", "-A"], out)
    _run(["git", "commit", "-m", "Deploy FORGE-Vision to Hugging Face Space"], out)
    if remote:
        _run(["git", "remote", "add", "space", remote], out)
        print(f"\nRemote 'space' added. Push with:\n  cd {out} && git push -u space main")


def main() -> None:
    ap = argparse.ArgumentParser(description="Assemble the FORGE-Vision HF Space repo.")
    ap.add_argument("--out", default=str(REPO / "hf_space_build"),
                    help="Output directory (default: ./hf_space_build)")
    ap.add_argument("--git-init", action="store_true",
                    help="Initialise git + Git LFS and make the first commit")
    ap.add_argument("--remote", default=None,
                    help="HF Space git URL to add as remote 'space' (implies --git-init)")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    print(f"Assembling HF Space repo at: {out}\n")
    assemble(out)

    if args.git_init or args.remote:
        try:
            git_init(out, args.remote)
        except FileNotFoundError:
            sys.exit("ERROR: git (or git-lfs) not found on PATH.")
        except subprocess.CalledProcessError as e:
            sys.exit(f"ERROR: git step failed: {e}")

    print("\nDone. Next:")
    if not (args.git_init or args.remote):
        print(f"  cd {out}")
        print("  git init -b main && git lfs install && git lfs track '*.pth'")
        print("  git add -A && git commit -m 'Deploy FORGE-Vision'")
        print("  git remote add space https://huggingface.co/spaces/<user>/<name>")
    print("  git push -u space main")
    print("  Then set Space secrets (see DEPLOYMENT.md §3).")


if __name__ == "__main__":
    main()
