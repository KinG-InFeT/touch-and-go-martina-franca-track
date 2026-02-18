"""Cross-platform utilities for Touch and Go Track pipeline."""

import os
import platform
import shutil
import sys
import tempfile
import urllib.request
import zipfile

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


def find_blender():
    """Find the Blender executable for the current platform."""
    if IS_LINUX:
        snap = "/snap/bin/blender"
        if os.path.isfile(snap):
            return snap
    elif IS_WINDOWS:
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        for base in (pf, pf86):
            blender_dir = os.path.join(base, "Blender Foundation")
            if os.path.isdir(blender_dir):
                versions = sorted(os.listdir(blender_dir), reverse=True)
                for v in versions:
                    exe = os.path.join(blender_dir, v, "blender.exe")
                    if os.path.isfile(exe):
                        return exe
    found = shutil.which("blender")
    return found or "blender"


def venv_python():
    """Return path to the venv Python interpreter."""
    root = _root_dir()
    if IS_WINDOWS:
        return os.path.join(root, ".venv", "Scripts", "python.exe")
    return os.path.join(root, ".venv", "bin", "python3")


def venv_bin_dir():
    """Return the venv bin/Scripts directory."""
    root = _root_dir()
    if IS_WINDOWS:
        return os.path.join(root, ".venv", "Scripts")
    return os.path.join(root, ".venv", "bin")


def path_separator():
    """Return the PATH environment variable separator for the current OS."""
    return ";" if IS_WINDOWS else ":"


def ac_search_paths():
    """Return a list of common Assetto Corsa installation directories."""
    paths = []
    if IS_LINUX:
        home = os.path.expanduser("~")
        paths = [
            os.path.join(home, ".steam", "steam", "steamapps", "common", "assettocorsa"),
            os.path.join(home, ".local", "share", "Steam", "steamapps", "common", "assettocorsa"),
            os.path.join(home, ".steam", "debian-installation", "steamapps", "common", "assettocorsa"),
        ]
    elif IS_WINDOWS:
        drives = ["C:", "D:", "E:", "F:"]
        for drv in drives:
            paths.append(os.path.join(drv, os.sep, "Program Files (x86)",
                                      "Steam", "steamapps", "common", "assettocorsa"))
            paths.append(os.path.join(drv, os.sep, "Program Files",
                                      "Steam", "steamapps", "common", "assettocorsa"))
            paths.append(os.path.join(drv, os.sep, "SteamLibrary",
                                      "steamapps", "common", "assettocorsa"))
    return paths


def cm_cache_dir():
    """Return Content Manager cache directory (or None if not found)."""
    if IS_LINUX:
        home = os.path.expanduser("~")
        return os.path.join(
            home, ".steam", "steam", "steamapps", "compatdata", "244210",
            "pfx", "drive_c", "users", "steamuser", "AppData", "Local",
            "AcTools Content Manager",
        )
    elif IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            return os.path.join(local, "AcTools Content Manager")
    return None


def download_dir_candidates():
    """Return list of common download directories for addon zip lookup."""
    home = os.path.expanduser("~")
    candidates = [os.path.join(home, "Downloads")]
    if IS_LINUX:
        candidates.append(os.path.join(home, "Scaricati"))
    return candidates


def download_file(url, dest_path):
    """Download a file from url to dest_path using urllib. Returns True on success."""
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        urllib.request.urlretrieve(url, dest_path)
        return True
    except Exception:
        return False


def extract_zip(zip_path, dest_dir):
    """Extract a zip archive to dest_dir. Returns True on success."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
        return True
    except Exception:
        return False


def _root_dir():
    """Return the project root directory (parent of scripts/)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
