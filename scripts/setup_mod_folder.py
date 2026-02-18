#!/usr/bin/env python3
"""
Create the complete Assetto Corsa mod folder structure and config files
for Touch and Go karting track, Martina Franca.

Uses the AC multi-layout convention (like ks_brands_hatch):
  - models_<layout>.ini in track root
  - <layout>/ai/, <layout>/data/, <layout>/map.png
  - ui/<layout>/ui_track.json, preview.png, outline.png
"""

import os
import json
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
MOD_DIR = os.path.join(ROOT_DIR, "mod", "touch_and_go")

# Load track config (if available)
CONFIG_PATH = os.path.join(ROOT_DIR, "track_config.json")
_config = {}
if os.path.isfile(CONFIG_PATH):
    with open(CONFIG_PATH) as _f:
        _config = json.load(_f)
_surfaces = _config.get("surfaces", {})
_info = _config.get("info", {})


def create_directories():
    """Create the mod folder structure (both layouts as explicit sub-layouts)."""
    dirs = [
        os.path.join(MOD_DIR, "default", "ai"),
        os.path.join(MOD_DIR, "default", "data"),
        os.path.join(MOD_DIR, "reverse", "ai"),
        os.path.join(MOD_DIR, "reverse", "data"),
        os.path.join(MOD_DIR, "ui", "default"),
        os.path.join(MOD_DIR, "ui", "reverse"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    print("  Created directory structure (default + reverse sub-layouts)")


def _write_data_file(layout, filename, content):
    """Write a data file to <layout>/data/<filename>."""
    path = os.path.join(MOD_DIR, layout, "data", filename)
    with open(path, 'w') as f:
        f.write(content)
    return path


def write_surfaces_ini():
    """Write surfaces.ini — surface physics definitions (both layouts)."""
    road_friction = _surfaces.get("road_friction", 0.97)
    kerb_friction = _surfaces.get("kerb_friction", 0.93)
    grass_friction = _surfaces.get("grass_friction", 0.60)

    content = f"""\
[SURFACE_0]
KEY=ROAD
FRICTION={road_friction}
DAMPING=0.0
WAV=
WAV_PITCH=0
FF_EFFECT=NULL
DIRT_ADDITIVE=0.0
IS_VALID_TRACK=1
IS_PITLANE=0
BLACK_FLAG_TIME=0.0
SIN_HEIGHT=0
SIN_LENGTH=0
VIBRATION_GAIN=0
VIBRATION_LENGTH=0

[SURFACE_1]
KEY=KERB
FRICTION={kerb_friction}
DAMPING=0.0
WAV=kerb
WAV_PITCH=1
FF_EFFECT=KERB
DIRT_ADDITIVE=0.0
IS_VALID_TRACK=1
IS_PITLANE=0
BLACK_FLAG_TIME=0.0
SIN_HEIGHT=0.005
SIN_LENGTH=0.15
VIBRATION_GAIN=0.5
VIBRATION_LENGTH=0.15

[SURFACE_2]
KEY=GRASS
FRICTION={grass_friction}
DAMPING=0.1
WAV=grass
WAV_PITCH=0
FF_EFFECT=GRASS
DIRT_ADDITIVE=0.5
IS_VALID_TRACK=0
IS_PITLANE=0
BLACK_FLAG_TIME=3.0
SIN_HEIGHT=0
SIN_LENGTH=0
VIBRATION_GAIN=0.2
VIBRATION_LENGTH=0.5

[SURFACE_3]
KEY=WALL
FRICTION=0.365
DAMPING=0.0
WAV=
WAV_PITCH=0
FF_EFFECT=NULL
DIRT_ADDITIVE=0.0
IS_VALID_TRACK=0
IS_PITLANE=0
BLACK_FLAG_TIME=0.0
SIN_HEIGHT=0
SIN_LENGTH=0
VIBRATION_GAIN=0.05
VIBRATION_LENGTH=0.05

[SURFACE_4]
KEY=PIT
FRICTION=0.97
DAMPING=0.0
WAV=
WAV_PITCH=0
FF_EFFECT=NULL
DIRT_ADDITIVE=0.0
IS_VALID_TRACK=1
IS_PITLANE=1
BLACK_FLAG_TIME=0.0
SIN_HEIGHT=0
SIN_LENGTH=0
VIBRATION_GAIN=0
VIBRATION_LENGTH=0

[SURFACE_5]
KEY=GROUND
FRICTION={grass_friction}
DAMPING=0.15
WAV=grass
WAV_PITCH=0
FF_EFFECT=GRASS
DIRT_ADDITIVE=0.5
IS_VALID_TRACK=0
IS_PITLANE=0
BLACK_FLAG_TIME=3.0
SIN_HEIGHT=0
SIN_LENGTH=0
VIBRATION_GAIN=0.3
VIBRATION_LENGTH=0.5
"""
    for layout in ("default", "reverse"):
        p = _write_data_file(layout, "surfaces.ini", content)
        print(f"  Written {p}")


def write_cameras_ini():
    """Write cameras.ini — 6 replay cameras around the circuit."""
    content = """\
[HEADER]
VERSION=2
CAMERA_COUNT=6
SET_NAME=replay


[CAMERA_0]
NAME=Start/Finish
POSITION=5.0, 3.0, 0.0
FORWARD=0.0, -0.3, 1.0
FOV=56.0
NEAR=0.1
FAR=800.0
MIN_DISTANCE=3.0
MAX_DISTANCE=120.0

[CAMERA_1]
NAME=Curva 1
POSITION=-30.0, 4.0, 50.0
FORWARD=0.5, -0.3, -0.5
FOV=50.0
NEAR=0.1
FAR=800.0
MIN_DISTANCE=3.0
MAX_DISTANCE=100.0

[CAMERA_2]
NAME=Tornante Nord
POSITION=-50.0, 5.0, 100.0
FORWARD=0.7, -0.3, -0.3
FOV=48.0
NEAR=0.1
FAR=800.0
MIN_DISTANCE=3.0
MAX_DISTANCE=100.0

[CAMERA_3]
NAME=Chicane
POSITION=20.0, 3.5, 80.0
FORWARD=-0.5, -0.2, -0.5
FOV=52.0
NEAR=0.1
FAR=800.0
MIN_DISTANCE=3.0
MAX_DISTANCE=100.0

[CAMERA_4]
NAME=Curva Sud
POSITION=40.0, 4.0, -20.0
FORWARD=-0.6, -0.3, 0.4
FOV=50.0
NEAR=0.1
FAR=800.0
MIN_DISTANCE=3.0
MAX_DISTANCE=100.0

[CAMERA_5]
NAME=Panoramica
POSITION=0.0, 25.0, 50.0
FORWARD=0.0, -0.8, -0.2
FOV=70.0
NEAR=0.1
FAR=1200.0
MIN_DISTANCE=5.0
MAX_DISTANCE=200.0
"""
    for layout in ("default", "reverse"):
        p = _write_data_file(layout, "cameras.ini", content)
        print(f"  Written {p}")


def write_map_ini():
    """Write map.ini — minimap configuration."""
    content = """\
[PARAMETERS]
WIDTH=250
HEIGHT=250
MARGIN=20
SCALE_FACTOR=1.0
X_OFFSET=0.0
Z_OFFSET=0.0
DRAWING_SIZE=10
"""
    for layout in ("default", "reverse"):
        p = _write_data_file(layout, "map.ini", content)
        print(f"  Written {p}")


def write_lighting_ini():
    """Write lighting.ini — sun position."""
    content = """\
[LIGHTING]
SUN_PITCH_ANGLE=45
SUN_HEADING_ANGLE=45
"""
    for layout in ("default", "reverse"):
        p = _write_data_file(layout, "lighting.ini", content)
        print(f"  Written {p}")


def write_groove_ini():
    """Write groove.ini — rubber groove config."""
    content = """\
[HEADER]
GROOVES_NUMBER=0
"""
    for layout in ("default", "reverse"):
        p = _write_data_file(layout, "groove.ini", content)
        print(f"  Written {p}")


def write_models_ini():
    """Write models_default.ini and models_reverse.ini in track root.

    The KN5 references are swapped: the Blender→AC coordinate transform
    (x,y,z)→(x,z,-y) flips the apparent rotation direction viewed from above.
    The master .blend empties (CW in Blender) become CCW in AC, and the
    reverse .blend empties (CCW in Blender) become CW in AC.
    So: default (CW in AC) → reverse KN5, reverse (CCW in AC) → default KN5.
    """
    # Default layout (CW in AC) → uses reverse KN5 (empties flipped = CW in AC)
    path_def = os.path.join(MOD_DIR, "models_default.ini")
    with open(path_def, 'w') as f:
        f.write("[MODEL_0]\nFILE=touch_and_go_reverse.kn5\nPOSITION=0,0,0\nROTATION=0,0,0\n")
    print(f"  Written {path_def}")

    # Reverse layout (CCW in AC) → uses default KN5 (master empties = CCW in AC)
    path_rev = os.path.join(MOD_DIR, "models_reverse.ini")
    with open(path_rev, 'w') as f:
        f.write("[MODEL_0]\nFILE=touch_and_go.kn5\nPOSITION=0,0,0\nROTATION=0,0,0\n")
    print(f"  Written {path_rev}")


def write_ui_track_json():
    """Write ui_track.json for both layouts."""
    name = _info.get("name", "Touch and Go")
    city = _info.get("city", "Martina Franca")
    province = _info.get("province", "TA")
    region = _info.get("region", "Puglia")
    country = _info.get("country", "Italy")
    length = str(_info.get("length", "900"))
    pitboxes = str(_info.get("pitboxes", "5"))
    direction = _info.get("direction", "clockwise")
    geotags = _info.get("geotags", ["40.7010", "17.3352"])
    _geo = _config.get("geometry", {})
    road_w = _geo.get("road_width", 8.0)

    # Default layout
    path_def = os.path.join(MOD_DIR, "ui", "default", "ui_track.json")
    data_def = {
        "name": name,
        "description": f"Kartodromo {name} - Via Porcile, 57 - 74015 {city} ({province}), "
                       f"{region} - {country}. Tracciato tecnico su {length} metri.",
        "tags": ["circuit", "kart", "italy", "short"],
        "geotags": geotags,
        "country": country,
        "city": city,
        "length": length,
        "width": f"{road_w:.0f}-{road_w + 1:.0f}",
        "pitboxes": pitboxes,
        "run": direction,
        "author": "Bros on Trucks Team",
        "version": "1.0.0"
    }
    with open(path_def, 'w') as f:
        json.dump(data_def, f, indent=2, ensure_ascii=False)
    print(f"  Written {path_def}")

    # Reverse layout
    path_rev = os.path.join(MOD_DIR, "ui", "reverse", "ui_track.json")
    data_rev = {
        "name": f"{name} [reverse]",
        "description": f"Kartodromo {name} - Via Porcile, 57 - 74015 {city} ({province}), "
                       f"{region} - {country}. Tracciato tecnico su {length} metri. Senso antiorario.",
        "tags": ["circuit", "kart", "italy", "short", "reverse"],
        "geotags": geotags,
        "country": country,
        "city": city,
        "length": length,
        "width": f"{road_w:.0f}-{road_w + 1:.0f}",
        "pitboxes": pitboxes,
        "run": "counter-clockwise",
        "author": "Bros on Trucks Team",
        "version": "1.0.0"
    }
    with open(path_rev, 'w') as f:
        json.dump(data_rev, f, indent=2, ensure_ascii=False)
    print(f"  Written {path_rev}")


def copy_images():
    """Copy layout.png and cover.png to both layouts."""
    # Map.png to both layout folders
    src = os.path.join(ROOT_DIR, "layout.png")
    if os.path.exists(src):
        for layout in ("default", "reverse"):
            dst = os.path.join(MOD_DIR, layout, "map.png")
            shutil.copy2(src, dst)
        print(f"  Copied layout.png -> default/map.png + reverse/map.png")

    # Cover.png as preview/outline for both layouts
    cover = os.path.join(ROOT_DIR, "cover.png")
    img_src = cover if os.path.exists(cover) else src
    if os.path.exists(img_src):
        label = "cover.png" if os.path.exists(cover) else "layout.png"
        for layout in ("default", "reverse"):
            for img_name in ["outline.png", "preview.png"]:
                dst = os.path.join(MOD_DIR, "ui", layout, img_name)
                shutil.copy2(img_src, dst)
        print(f"  Copied {label} -> ui/default/ + ui/reverse/ (preview + outline)")


def main():
    print("Setting up Assetto Corsa mod folder...")

    create_directories()
    write_surfaces_ini()
    write_cameras_ini()
    write_map_ini()
    write_lighting_ini()
    write_groove_ini()
    write_models_ini()
    write_ui_track_json()
    copy_images()

    print(f"\nMod structure created at: {MOD_DIR}")
    print(f"  Layouts: default (CW) + reverse (CCW)")


if __name__ == "__main__":
    main()
