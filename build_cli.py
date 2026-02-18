#!/usr/bin/env python3
"""Cross-platform CLI build for Touch and Go mod.

Runs the 6-step pipeline (default + reverse layout):
  1. Export KN5 (default CW)
  2. Setup mod folder structure (default + reverse)
  3. Generate AI line (default CW)
  4. Create reverse blend (flip empties)
  5. Export KN5 (reverse)
  6. Generate AI line (reverse CCW)

Usage:
    python build_cli.py
"""

import os
import shutil
import subprocess
import sys

# Ensure scripts/ is on the path for platform_utils
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))
import platform_utils


def main():
    blend_file = os.path.join(ROOT_DIR, "touch_and_go.blend")
    if not os.path.isfile(blend_file):
        print("Error: touch_and_go.blend not found.")
        print("Run the track generator first:")
        print("  blender --python scripts/create_track.py")
        sys.exit(1)

    blender = platform_utils.find_blender()
    venv_py = platform_utils.venv_python()

    # Verify venv exists
    if not os.path.isfile(venv_py):
        print(f"Error: venv Python not found at {venv_py}")
        print("Create it first:")
        if platform_utils.IS_WINDOWS:
            print("  python -m venv .venv")
            print("  .venv\\Scripts\\pip install -r requirements.txt")
        else:
            print("  python3 -m venv .venv")
            print("  .venv/bin/pip install -r requirements.txt")
        sys.exit(1)

    reverse_blend = os.path.join(ROOT_DIR, "touch_and_go_reverse.blend")
    reverse_env = dict(os.environ, TRACK_REVERSE="1")

    steps = [
        ("1/6 - Export KN5", [
            blender, "--background", blend_file,
            "--python", os.path.join(ROOT_DIR, "scripts", "export_kn5.py"),
        ], None),
        ("2/6 - Mod folder", [
            venv_py, os.path.join(ROOT_DIR, "scripts", "setup_mod_folder.py"),
        ], None),
        ("3/6 - AI line CW", [
            blender, "--background", blend_file,
            "--python", os.path.join(ROOT_DIR, "scripts", "generate_ai_line.py"),
        ], None),
        ("4/6 - Reverse blend", [
            blender, "--background", blend_file,
            "--python", os.path.join(ROOT_DIR, "scripts", "create_reverse_blend.py"),
        ], None),
        ("5/6 - Export KN5 reverse", [
            blender, "--background", reverse_blend,
            "--python", os.path.join(ROOT_DIR, "scripts", "export_kn5.py"),
        ], reverse_env),
        ("6/6 - AI line CCW", [
            blender, "--background", reverse_blend,
            "--python", os.path.join(ROOT_DIR, "scripts", "generate_ai_line.py"),
        ], reverse_env),
    ]

    print("=== Touch and Go - Build mod ===")
    print()

    for label, cmd, env in steps:
        print(f"[{label}] Running...")
        result = subprocess.run(cmd, cwd=ROOT_DIR, env=env)
        if result.returncode != 0:
            print(f"[{label}] FAILED (exit code {result.returncode})")
            sys.exit(1)
        print(f"[{label}] Done.")
        print()

    # Copy KN5 files to mod folder
    mod_dir = os.path.join(ROOT_DIR, "mod", "touch_and_go")
    os.makedirs(mod_dir, exist_ok=True)
    for kn5_name in ["touch_and_go.kn5", "touch_and_go_reverse.kn5"]:
        src = os.path.join(ROOT_DIR, kn5_name)
        dst = os.path.join(mod_dir, kn5_name)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print(f"  {kn5_name} copied to mod/")

    # Create distributable zip
    import zipfile
    builds_dir = os.path.join(ROOT_DIR, "builds")
    os.makedirs(builds_dir, exist_ok=True)
    zip_path = os.path.join(builds_dir, "touch_and_go.zip")
    if os.path.isdir(mod_dir):
        print("Creating distributable zip...")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for dirpath, dirnames, filenames in os.walk(mod_dir):
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    arcname = os.path.join("touch_and_go", os.path.relpath(full, mod_dir))
                    zf.write(full, arcname)
        size_kb = os.path.getsize(zip_path) / 1024
        print(f"  builds/touch_and_go.zip ({size_kb:.0f} KB)")

    print()
    print("=== Build completed! ===")
    print()
    print("Layouts: default (CW) + reverse (CCW)")
    print("To install: bash install.sh")
    print("To share:   send builds/touch_and_go.zip")


if __name__ == "__main__":
    main()
