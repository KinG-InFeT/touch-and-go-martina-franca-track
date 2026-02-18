#!/usr/bin/env python3
"""
Create reverse variant of touch_and_go.blend.

Opens the CW blend, flips all AC_ empties to face CCW direction,
and saves as touch_and_go_reverse.blend. The 3D mesh is unchanged.

Run with:
  blender --background touch_and_go.blend --python scripts/create_reverse_blend.py
"""

import os
import sys
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
REVERSE_BLEND = os.path.join(ROOT_DIR, "touch_and_go_reverse.blend")

try:
    import bpy
    from mathutils import Euler
except ImportError:
    print("ERROR: Must run inside Blender.")
    sys.exit(1)


def main():
    print("=" * 60)
    print("Touch and Go — Reverse Empties Generator")
    print("=" * 60)

    count = 0
    for obj in bpy.data.objects:
        if obj.type == 'EMPTY' and obj.name.startswith('AC_'):
            rot = obj.rotation_euler.copy()
            rot.z += math.pi  # flip yaw by 180 degrees
            obj.rotation_euler = rot
            count += 1
            print(f"  Flipped: {obj.name}")

    print(f"\n  {count} empties flipped to CCW")
    print(f"Saving {REVERSE_BLEND}...")
    bpy.ops.wm.save_as_mainfile(filepath=REVERSE_BLEND)
    print("Done!")


if __name__ == "__main__":
    main()
