#!/usr/bin/env python3
"""
Generate fast_lane.ai for Assetto Corsa from Blender road mesh.

Run with: blender --background touch_and_go.blend --python scripts/generate_ai_line.py

Extracts the centerline from the 1ROAD mesh boundary edges (inner/outer road
edges), computes midpoints for the centerline, then generates the AI binary file
with curvature-based speed profile.

The .ai file format (little-endian):
  Header (4 x int32): [version=7, numPoints=N, 0, 0]
  Per point (N times): [x,y,z (float32), cumDist (float32), id (int32)]
  Then 4 sections (speed/gas/brake/lateral): [count (int32), N x float32]
"""

import os
import sys
import struct
import json
import math
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
_REVERSE = os.environ.get("TRACK_REVERSE", "0") == "1"
OUTPUT_PATH = os.path.join(
    ROOT_DIR, "mod", "touch_and_go",
    "reverse" if _REVERSE else "default",
    "ai", "fast_lane.ai",
)
CONFIG_PATH = os.path.join(ROOT_DIR, "track_config.json")
ROAD_OBJECT = "1ROAD"

try:
    import bpy
    import bmesh
except ImportError:
    print("ERROR: Must run inside Blender.")
    sys.exit(1)

# Load track config
_config = {}
if os.path.isfile(CONFIG_PATH):
    with open(CONFIG_PATH) as _f:
        _config = json.load(_f)

_ai = _config.get("ai_line", {})
DEFAULT_SPEED = _ai.get("default_speed", 75.0)
MIN_CORNER_SPEED = _ai.get("min_corner_speed", 35.0)


# --- Centerline extraction from road mesh ---

def _chain_boundary_loops(bm, world_mat):
    """Chain boundary edges into closed loops, returning world-space coords."""
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    print(f"  Found {len(boundary_edges)} boundary edges")
    if not boundary_edges:
        print("ERROR: No boundary edges found on road mesh")
        sys.exit(1)

    edge_set = set(boundary_edges)
    loops = []
    visited = set()

    for start_edge in boundary_edges:
        if start_edge in visited:
            continue
        loop_verts = []
        current = start_edge
        v = current.verts[0]
        while current not in visited:
            visited.add(current)
            co = world_mat @ v.co
            loop_verts.append((co.x, co.y, co.z))
            other = current.other_vert(v)
            next_edge = None
            for e in other.link_edges:
                if e in edge_set and e not in visited:
                    next_edge = e
                    break
            if next_edge is None:
                break
            v = other
            current = next_edge
        if len(loop_verts) > 2:
            loops.append(np.array(loop_verts))

    return loops


def extract_centerline():
    """Extract centerline from 1ROAD mesh boundary edges."""
    obj = bpy.data.objects.get(ROAD_OBJECT)
    if obj is None:
        print(f"ERROR: Object '{ROAD_OBJECT}' not found in scene")
        sys.exit(1)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()

    loops = _chain_boundary_loops(bm, obj.matrix_world)
    bm.free()

    print(f"  Found {len(loops)} boundary loops: {[len(l) for l in loops]}")
    if len(loops) != 2:
        print(f"ERROR: Expected 2 boundary loops (inner/outer road edge), got {len(loops)}")
        sys.exit(1)

    loop_a, loop_b = loops[0], loops[1]

    if len(loop_a) != len(loop_b):
        print(f"WARNING: Loop sizes differ: {len(loop_a)} vs {len(loop_b)}")
        min_len = min(len(loop_a), len(loop_b))
        loop_a = loop_a[:min_len]
        loop_b = loop_b[:min_len]

    # Align loop_b start to nearest point to loop_a[0]
    dists = np.sum((loop_b - loop_a[0]) ** 2, axis=1)
    offset = int(np.argmin(dists))
    if offset > 0:
        loop_b = np.roll(loop_b, -offset, axis=0)

    # Ensure both loops go in the same direction
    d_fwd = np.sum((loop_a[1] - loop_b[1]) ** 2)
    d_bwd = np.sum((loop_a[1] - loop_b[-1]) ** 2)
    if d_bwd < d_fwd:
        loop_b = loop_b[::-1]
        dists = np.sum((loop_b - loop_a[0]) ** 2, axis=1)
        offset = int(np.argmin(dists))
        if offset > 0:
            loop_b = np.roll(loop_b, -offset, axis=0)

    # Centerline = midpoint of corresponding boundary points
    centerline = (loop_a + loop_b) / 2.0

    # Determine direction: check if centerline goes clockwise (viewed from +Z)
    pts = centerline[:, :2]
    signed_area = np.sum(pts[:-1, 0] * pts[1:, 1] - pts[1:, 0] * pts[:-1, 1])
    direction = "CCW" if signed_area > 0 else "CW"
    print(f"  Centerline: {len(centerline)} points, direction: {direction}")

    # The AI line direction is determined by point ORDER, which is preserved
    # through the Blender→AC coordinate transform.  Only empty rotations
    # (matrices) are affected by the Y-axis flip — point sequences are not.
    # Default: clockwise (CW). Reverse layout: counter-clockwise (CCW).
    if _REVERSE:
        if signed_area < 0:
            centerline = centerline[::-1]
            print(f"  Reversed to CCW (reverse layout)")
    else:
        if signed_area > 0:
            centerline = centerline[::-1]
            print(f"  Reversed to CW")

    return centerline


# --- Curvature and speed computation ---

def compute_curvature(pts_2d):
    """Compute curvature at each point of the 2D path."""
    n = len(pts_2d)
    curvature = np.zeros(n)
    for i in range(n):
        p0 = pts_2d[(i - 1) % n]
        p1 = pts_2d[i]
        p2 = pts_2d[(i + 1) % n]
        v1 = p1 - p0
        v2 = p2 - p1
        cross = abs(v1[0] * v2[1] - v1[1] * v2[0])
        l1 = np.linalg.norm(v1)
        l2 = np.linalg.norm(v2)
        if l1 > 0 and l2 > 0:
            curvature[i] = cross / (l1 * l2)
    return curvature


def compute_speeds(curvature):
    """Compute target speed at each point based on curvature."""
    max_curv = np.percentile(curvature, 95) if np.max(curvature) > 0 else 1.0
    norm_curv = np.clip(curvature / max_curv, 0, 1)
    speeds = DEFAULT_SPEED - norm_curv * (DEFAULT_SPEED - MIN_CORNER_SPEED)
    kernel_size = 15
    kernel = np.ones(kernel_size) / kernel_size
    speeds = np.convolve(speeds, kernel, mode='same')
    return speeds


# --- Start index and AI file writing ---

def find_start_index(pts_blender):
    """Find centerline index closest to AC_START_0 position in Blender."""
    start_obj = bpy.data.objects.get("AC_START_0")
    if start_obj is None:
        print("  WARNING: AC_START_0 not found, using index 0")
        return 0
    pos = start_obj.matrix_world.translation
    dists = (pts_blender[:, 0] - pos.x) ** 2 + (pts_blender[:, 1] - pos.y) ** 2
    idx = int(np.argmin(dists))
    print(f"  Start/finish at AC_START_0: Blender({pos.x:.1f}, {pos.y:.1f}), index {idx}")
    return idx


def write_ai_file(centerline_blender, output_path):
    """Write fast_lane.ai binary file from Blender-coords centerline."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Reindex to start from start/finish line
    start_idx = find_start_index(centerline_blender)
    if start_idx > 0:
        centerline_blender = np.roll(centerline_blender, -start_idx, axis=0)
        print(f"  Reindexed AI line to start from index {start_idx}")

    n = len(centerline_blender)

    # Convert Blender (x,y,z) -> AC (x, z, -y)
    ac_pts = np.zeros((n, 3), dtype=np.float32)
    ac_pts[:, 0] = centerline_blender[:, 0]
    ac_pts[:, 1] = centerline_blender[:, 2]
    ac_pts[:, 2] = -centerline_blender[:, 1]

    # Cumulative distances
    diffs = np.diff(ac_pts, axis=0)
    seg_lengths = np.linalg.norm(diffs, axis=1)
    cum_dist = np.zeros(n, dtype=np.float32)
    cum_dist[1:] = np.cumsum(seg_lengths)

    # Curvature and speeds (Blender XY plane)
    curvature = compute_curvature(centerline_blender[:, :2])
    speeds = compute_speeds(curvature)

    # Gas/brake
    max_speed = np.max(speeds)
    gas = (speeds / max_speed).astype(np.float32)
    brake = np.clip(1.0 - gas, 0, 1).astype(np.float32) * 0.3
    lateral = np.zeros(n, dtype=np.float32)

    with open(output_path, 'wb') as f:
        # Header
        f.write(struct.pack('<4i', 7, n, 0, 0))

        # Point data
        for i in range(n):
            f.write(struct.pack('<3f', ac_pts[i, 0], ac_pts[i, 1], ac_pts[i, 2]))
            f.write(struct.pack('<f', cum_dist[i]))
            f.write(struct.pack('<i', i))

        # Speed section (km/h -> m/s)
        f.write(struct.pack('<i', n))
        for i in range(n):
            f.write(struct.pack('<f', speeds[i] / 3.6))

        # Gas section
        f.write(struct.pack('<i', n))
        for i in range(n):
            f.write(struct.pack('<f', gas[i]))

        # Brake section
        f.write(struct.pack('<i', n))
        for i in range(n):
            f.write(struct.pack('<f', brake[i]))

        # Lateral offset section
        f.write(struct.pack('<i', n))
        for i in range(n):
            f.write(struct.pack('<f', lateral[i]))

    total_length = cum_dist[-1]
    print(f"  Written {n} AI points to {output_path}")
    print(f"  Total AI line length: {total_length:.1f} m")
    print(f"  Speed range: {speeds.min():.1f} - {speeds.max():.1f} km/h")


def main():
    print("Generating AI driving line from road mesh...")
    centerline = extract_centerline()
    print("Writing AI file...")
    write_ai_file(centerline, OUTPUT_PATH)
    print("\nDone!")


if __name__ == "__main__":
    main()
