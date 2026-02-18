#!/usr/bin/env python3
"""
Generate the complete Touch and Go kart track in Blender.

Run with:  blender --background --python scripts/create_track.py

Track specs (Touch and Go, Martina Franca):
  Total length: ~900 m
  Road width:   8 m
  Right turns:  6
  Left turns:   4
  Straights:    3

Layout traced from high-resolution layout.png:
  - Outer shell: left side nearly vertical, top nearly horizontal,
    bottom slopes ~25° down-right. Right side = S-curve.
  - Internal S-curve: upper path going left, U-turn at left,
    lower path going right, descent back to start.
  - Large sweeping curve in upper-right is the most prominent feature.

Saves to: touch_and_go.blend
"""

import os
import sys
import math
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
BLEND_PATH = os.path.join(ROOT_DIR, "touch_and_go.blend")
TEXTURES_DIR = os.path.join(ROOT_DIR, "textures")
CONFIG_PATH = os.path.join(ROOT_DIR, "track_config.json")

try:
    import bpy
    import bmesh
    from mathutils import Vector, Euler
except ImportError:
    print("ERROR: Must run inside Blender.")
    sys.exit(1)

# Load config
_config = {}
if os.path.isfile(CONFIG_PATH):
    with open(CONFIG_PATH) as f:
        _config = json.load(f)
_geo = _config.get("geometry", {})

ROAD_WIDTH = _geo.get("road_width", 8.0)
KERB_WIDTH = _geo.get("kerb_width", 1.0)
KERB_HEIGHT = _geo.get("kerb_height", 0.08)
GRASS_WIDTH = _geo.get("grass_width", 4.0)
WALL_HEIGHT = _geo.get("wall_height", 1.5)
WALL_THICKNESS = _geo.get("wall_thickness", 1.5)
GROUND_TILE_SIZE = _geo.get("ground_tile_size", 30.0)


# ============================================================
# TRACK CENTERLINE — extracted from layout.png via skeletonization
# ============================================================
# The centerline was extracted automatically from the layout image:
#   1. Threshold black track pixels
#   2. Erode to separate parallel paths
#   3. Skeletonize to get 1-pixel centerline
#   4. Trace outer loop + S-curve separately, then splice
#   5. Smooth, scale to 900m, subsample to ~80 control points
# ============================================================

_CENTERLINE_PATH = os.path.join(ROOT_DIR, "centerline.json")

with open(_CENTERLINE_PATH) as _f:
    CONTROL_POINTS = [tuple(p) for p in json.load(_f)]
print(f"Loaded {len(CONTROL_POINTS)} control points from centerline.json")


# ============================================================
# Catmull-Rom spline
# ============================================================

def catmull_rom_point(p0, p1, p2, p3, t, alpha=0.5):
    """Centripetal Catmull-Rom interpolation between p1 and p2."""
    def d(a, b):
        return max(((a[0]-b[0])**2 + (a[1]-b[1])**2)**0.5, 1e-6)
    t01 = d(p0, p1) ** alpha
    t12 = d(p1, p2) ** alpha
    t23 = d(p2, p3) ** alpha
    m1 = [0, 0]; m2 = [0, 0]
    for i in range(2):
        m1[i] = (p2[i]-p1[i] + t12*((p1[i]-p0[i])/t01 - (p2[i]-p0[i])/(t01+t12)))
        m2[i] = (p2[i]-p1[i] + t12*((p3[i]-p2[i])/t23 - (p3[i]-p1[i])/(t12+t23)))
    a = [2*(p1[i]-p2[i])+m1[i]+m2[i] for i in range(2)]
    b = [-3*(p1[i]-p2[i])-2*m1[i]-m2[i] for i in range(2)]
    return tuple(a[i]*t**3 + b[i]*t**2 + m1[i]*t + p1[i] for i in range(2))


def interpolate_centerline(ctrl, pts_per_seg=20):
    """Interpolate closed control-point loop with Catmull-Rom."""
    pts = list(ctrl)
    if len(pts) >= 2:
        d = ((pts[0][0]-pts[-1][0])**2 + (pts[0][1]-pts[-1][1])**2)**0.5
        if d < 1.0:
            pts = pts[:-1]
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = pts[(i-1)%n], pts[i], pts[(i+1)%n], pts[(i+2)%n]
        for j in range(pts_per_seg):
            out.append(catmull_rom_point(p0, p1, p2, p3, j/pts_per_seg))
    return out


def compute_normals(cl):
    n = len(cl)
    norms = []
    for i in range(n):
        tx = cl[(i+1)%n][0] - cl[(i-1)%n][0]
        ty = cl[(i+1)%n][1] - cl[(i-1)%n][1]
        le = max((tx**2+ty**2)**0.5, 1e-6)
        norms.append((-ty/le, tx/le))
    return norms


def compute_curvature(cl):
    n = len(cl)
    curv = []
    for i in range(n):
        p0, p1, p2 = cl[(i-1)%n], cl[i], cl[(i+1)%n]
        v1 = (p1[0]-p0[0], p1[1]-p0[1])
        v2 = (p2[0]-p1[0], p2[1]-p1[1])
        cross = abs(v1[0]*v2[1] - v1[1]*v2[0])
        l1 = (v1[0]**2+v1[1]**2)**0.5
        l2 = (v2[0]**2+v2[1]**2)**0.5
        curv.append(cross/(l1*l2) if l1 > 0 and l2 > 0 else 0.0)
    return curv


def cum_distances(cl):
    d = [0.0]
    for i in range(1, len(cl)):
        dx = cl[i][0]-cl[i-1][0]; dy = cl[i][1]-cl[i-1][1]
        d.append(d[-1] + (dx**2+dy**2)**0.5)
    return d


# ============================================================
# Blender helpers
# ============================================================

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for b in list(coll):
            if b.users == 0:
                coll.remove(b)


def make_material(name, tex_file, ks_amb=0.5, ks_dif=0.7, ks_spec=0.2, ks_exp=15.0):
    mat = bpy.data.materials.new(name=name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for nd in list(nodes):
        nodes.remove(nd)
    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = (300, 0)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    tex_path = os.path.join(TEXTURES_DIR, tex_file)
    if os.path.isfile(tex_path):
        tn = nodes.new('ShaderNodeTexImage')
        tn.location = (-300, 0)
        tn.image = bpy.data.images.load(tex_path)
        links.new(tn.outputs['Color'], bsdf.inputs['Base Color'])
        print(f"  [OK] Texture loaded: {tex_file}")
    else:
        print(f"  [WARN] Texture NOT FOUND: {tex_path}")
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    mat['ac_shader'] = 'ksPerPixel'
    mat['ksAmbient'] = ks_amb
    mat['ksDiffuse'] = ks_dif
    mat['ksSpecular'] = ks_spec
    mat['ksSpecularEXP'] = ks_exp
    return mat


def build_strip(name, cl, norms, off_in, off_out, z, dists, mat):
    """Build a closed strip mesh along the centerline."""
    n = len(cl)
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    iv = []
    ov = []
    for i in range(n):
        cx, cy = cl[i]
        nx, ny = norms[i]
        iv.append(bm.verts.new((cx + nx * off_in, cy + ny * off_in, z)))
        ov.append(bm.verts.new((cx + nx * off_out, cy + ny * off_out, z)))
    bm.verts.ensure_lookup_table()
    tl = dists[-1] if dists[-1] > 0 else 1.0
    for i in range(n):
        j = (i + 1) % n
        try:
            f = bm.faces.new([iv[i], ov[i], ov[j], iv[j]])
            v0 = dists[i] / 5.0
            v1 = dists[j] / 5.0 if j else tl / 5.0
            f.loops[0][uv].uv = (0, v0)
            f.loops[1][uv].uv = (1, v0)
            f.loops[2][uv].uv = (1, v1)
            f.loops[3][uv].uv = (0, v1)
        except ValueError:
            pass
    bm.normal_update()
    for face in bm.faces:
        if face.normal.z < 0:
            face.normal_flip()
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob.data.materials.append(mat)
    return ob


def build_curbs(cl, norms, hw, dists, mat, n_cp, pts_per_seg=20):
    """Build curb meshes at positions matching cordoli.png red markings.

    Curb segments defined manually from layout analysis:
    - Outer perimeter: 2KERB (negative normal for CW centerline = outside)
    - Internal tight turns: 1KERB (positive normal for CW = inside of turns)
    """
    n = len(cl)

    # (name, start_cp_idx, end_cp_idx, sign)
    # CW centerline: positive normal = inside of circuit
    # sign: -1 = negative normal (outside for CW outer loop, 2KERB)
    #        1 = positive normal (inside / outside of internal turns, 1KERB)
    segments = [
        # Outer perimeter curbs (outside of circuit = negative normal)
        ("2KERB_BL", 74, 78, -1),          # BL corner
        ("2KERB_LEFT_L", 70, 73, -1),      # Left side lower portion
        ("2KERB_LEFT_U", 65, 68, -1),      # Left side upper portion
        ("2KERB_TL", 62, 65, -1),          # TL corner
        ("2KERB_TOP", 53, 61, -1),         # Top straight
        ("2KERB_SWEEP", 45, 52, -1),       # Big sweep right side
        ("2KERB_BOTTOM_R", 0, 6, -1),      # Bottom-right turn + straight
        # Internal curbs (tight turns = positive normal)
        ("1KERB_SWEEP_TR", 41, 44, 1),     # Sweep to upper internal
        ("1KERB_UTURN", 28, 33, 1),        # U-turn at left
        ("1KERB_HAIRPIN", 19, 21, 1),      # Right-end hairpin
        ("1KERB_ENTRY", 10, 13, 1),        # Diagonal to ascent
    ]

    objs = []
    for nm, cp_start, cp_end, sign in segments:
        i_start = cp_start * pts_per_seg
        i_end = min(cp_end * pts_per_seg, n)
        if i_end <= i_start:
            continue

        oc = sign * (hw + KERB_WIDTH / 2)
        oi = oc + KERB_WIDTH / 2
        oo = oc - KERB_WIDTH / 2

        me = bpy.data.meshes.new(nm)
        ob = bpy.data.objects.new(nm, me)
        bpy.context.collection.objects.link(ob)
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new("UVMap")
        iv2 = []
        ov2 = []
        for i in range(i_start, i_end):
            idx = i % n
            cx, cy = cl[idx]
            nx, ny = norms[idx]
            iv2.append(bm.verts.new((cx + nx * oi, cy + ny * oi, KERB_HEIGHT)))
            ov2.append(bm.verts.new((cx + nx * oo, cy + ny * oo, KERB_HEIGHT)))
        bm.verts.ensure_lookup_table()
        for i in range(len(iv2) - 1):
            try:
                f = bm.faces.new([iv2[i], ov2[i], ov2[i + 1], iv2[i + 1]])
                f.loops[0][uvl].uv = (0, i * 0.5)
                f.loops[1][uvl].uv = (1, i * 0.5)
                f.loops[2][uvl].uv = (1, (i + 1) * 0.5)
                f.loops[3][uvl].uv = (0, (i + 1) * 0.5)
            except ValueError:
                pass
        bm.normal_update()
        for face in bm.faces:
            if face.normal.z < 0:
                face.normal_flip()
        bm.to_mesh(me)
        bm.free()
        me.update()
        ob.data.materials.append(mat)
        objs.append(ob)
    return objs


def build_walls(cl, norms, hw, side, dists, mat):
    """Segmented wall barriers (~25 m each)."""
    n = len(cl)
    sign = 1.0 if side == 'inner' else -1.0
    pfx = "1" if side == 'inner' else "2"
    woff = sign * (hw + GRASS_WIDTH + WALL_THICKNESS / 2)
    seg_len = 25.0
    nseg = max(1, int(dists[-1] / seg_len))
    pps = max(2, n // nseg)
    objs = []
    for si in range(nseg):
        s = si * pps
        e = min((si + 1) * pps + 1, n)
        if si == nseg - 1:
            e = n
        nm = f"{pfx}WALL_SUB{si}"
        me = bpy.data.meshes.new(nm)
        ob = bpy.data.objects.new(nm, me)
        bpy.context.collection.objects.link(ob)
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new("UVMap")
        bi = []
        bo = []
        ti = []
        to_ = []
        for i in range(s, e):
            cx, cy = cl[i % n]
            nx, ny = norms[i % n]
            wx = cx + nx * woff
            wy = cy + ny * woff
            wix = wx + nx * sign * WALL_THICKNESS / 2
            wiy = wy + ny * sign * WALL_THICKNESS / 2
            wox = wx - nx * sign * WALL_THICKNESS / 2
            woy = wy - ny * sign * WALL_THICKNESS / 2
            bi.append(bm.verts.new((wix, wiy, 0)))
            bo.append(bm.verts.new((wox, woy, 0)))
            ti.append(bm.verts.new((wix, wiy, WALL_HEIGHT)))
            to_.append(bm.verts.new((wox, woy, WALL_HEIGHT)))
        bm.verts.ensure_lookup_table()
        for i in range(e - s - 1):
            for verts in ([bo[i], bo[i+1], to_[i+1], to_[i]],
                          [bi[i+1], bi[i], ti[i], ti[i+1]],
                          [ti[i], to_[i], to_[i+1], ti[i+1]]):
                try:
                    f = bm.faces.new(verts)
                    for li, lp in enumerate(f.loops):
                        lp[uvl].uv = (float(li % 2), float(li // 2))
                except ValueError:
                    pass
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        me.update()
        ob.data.materials.append(mat)
        objs.append(ob)
    return objs


def build_ground(cl, hw, mat):
    """Ground plane tiles."""
    xs = [c[0] for c in cl]
    ys = [c[1] for c in cl]
    mg = hw + GRASS_WIDTH + WALL_THICKNESS + 10
    x0 = min(xs) - mg
    x1 = max(xs) + mg
    y0 = min(ys) - mg
    y1 = max(ys) + mg
    ts = GROUND_TILE_SIZE
    tx = int(math.ceil((x1 - x0) / ts))
    ty = int(math.ceil((y1 - y0) / ts))
    objs = []
    idx = 0
    for i in range(tx):
        for j in range(ty):
            ax, ay = x0 + i * ts, y0 + j * ts
            bx, by = ax + ts, ay + ts
            nm = f"1GROUND_SUB{idx}"
            me = bpy.data.meshes.new(nm)
            ob = bpy.data.objects.new(nm, me)
            bpy.context.collection.objects.link(ob)
            bm = bmesh.new()
            uvl = bm.loops.layers.uv.new("UVMap")
            v = [bm.verts.new((ax, ay, -0.05)),
                 bm.verts.new((bx, ay, -0.05)),
                 bm.verts.new((bx, by, -0.05)),
                 bm.verts.new((ax, by, -0.05))]
            f = bm.faces.new(v)
            f.loops[0][uvl].uv = (0, 0)
            f.loops[1][uvl].uv = (1, 0)
            f.loops[2][uvl].uv = (1, 1)
            f.loops[3][uvl].uv = (0, 1)
            bm.normal_update()
            bm.to_mesh(me)
            bm.free()
            me.update()
            ob.data.materials.append(mat)
            objs.append(ob)
            idx += 1
    return objs


def build_empties(cl, norms, dists):
    """AC_START, AC_PIT, AC_TIME empties."""
    n = len(cl)
    tl = dists[-1]
    step = tl / n if n else 1
    sp = max(1, int(8.0 / step))
    objs = []

    def _place(name, i, side_off=0.0):
        cx, cy = cl[i % n]
        nx, ny = norms[i % n]
        j = (i + 1) % n
        tx = cl[j][0] - cx
        ty = cl[j][1] - cy
        tl2 = max((tx**2 + ty**2)**0.5, 1e-6)
        tx /= tl2
        ty /= tl2
        h = math.atan2(tx, -ty)
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = 'ARROWS'
        e.empty_display_size = 1.0
        e.location = (cx + nx * side_off, cy + ny * side_off, 0)
        e.rotation_euler = Euler((math.pi / 2, 0, math.pi - h), 'XYZ')
        bpy.context.collection.objects.link(e)
        objs.append(e)

    start_off = max(1, int(10.0 / step))  # 10 m forward along CW (toward BR curve)
    for k in range(5):
        off = 1.5 * (1 if k % 2 == 0 else -1)
        _place(f"AC_START_{k}", start_off + k * sp, off)
    for k in range(5):
        _place(f"AC_PIT_{k}", k * sp, -(ROAD_WIDTH / 2 + 2))
    _place("AC_TIME_0", start_off)
    _place("AC_TIME_1", (start_off + n // 2) % n)
    return objs


def setup_viewport():
    """Set viewport to Material Preview so textures are visible on file open."""
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'
                        # Top-down view centered on track
                        r3d = space.region_3d
                        if r3d:
                            r3d.view_rotation = (1, 0, 0, 0)
                            r3d.view_location = (0, 0, 0)
                            r3d.view_distance = 200


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("Touch and Go — Track Generator")
    print("=" * 60)

    print(f"\nRoad width: {ROAD_WIDTH} m")

    print("\nClearing scene...")
    clear_scene()

    print("Interpolating centerline...")
    cl = interpolate_centerline(CONTROL_POINTS, pts_per_seg=20)
    nm = compute_normals(cl)
    ds = cum_distances(cl)
    hw = ROAD_WIDTH / 2
    print(f"  {len(cl)} points, length {ds[-1]:.0f} m")

    # Materials
    print("\nCreating materials...")
    m_asp = make_material("mat_asphalt", "asphalt.png", 0.45, 0.7, 0.1, 10)
    m_crb = make_material("mat_curb", "curb_rw.png", 0.5, 0.8, 0.15, 12)
    m_grs = make_material("mat_grass", "grass.png", 0.5, 0.6, 0.05, 5)
    m_bar = make_material("mat_barrier", "barrier.png", 0.5, 0.7, 0.2, 15)
    m_gnd = make_material("mat_ground", "grass.png", 0.4, 0.5, 0.05, 5)

    # Road
    print("\nBuilding 1ROAD...")
    build_strip("1ROAD", cl, nm, hw, -hw, 0.0, ds, m_asp)

    # Curbs
    print("Building curbs...")
    n_cp = len(CONTROL_POINTS)
    curbs = build_curbs(cl, nm, hw, ds, m_crb, n_cp)
    print(f"  {len(curbs)} curb segments")

    # Grass
    print("Building grass...")
    build_strip("1GRASS", cl, nm, hw + GRASS_WIDTH, hw, -0.01, ds, m_grs)
    build_strip("2GRASS", cl, nm, -hw, -(hw + GRASS_WIDTH), -0.01, ds, m_grs)

    # Walls
    print("Building walls...")
    iw = build_walls(cl, nm, hw, 'inner', ds, m_bar)
    ow = build_walls(cl, nm, hw, 'outer', ds, m_bar)
    print(f"  inner: {len(iw)}, outer: {len(ow)}")

    # Ground
    print("Building ground tiles...")
    gt = build_ground(cl, hw, m_gnd)
    print(f"  {len(gt)} tiles")

    # Empties
    print("Building AC empties...")
    em = build_empties(cl, nm, ds)
    print(f"  {len(em)} empties")

    # Viewport setup for texture visibility
    print("\nSetting viewport to Material Preview...")
    setup_viewport()

    # Save
    print(f"Saving {BLEND_PATH}...")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    tot = 1 + len(curbs) + 2 + len(iw) + len(ow) + len(gt)
    print(f"\nDone!  length={ds[-1]:.0f}m  meshes={tot}  empties={len(em)}")


if __name__ == "__main__":
    main()
