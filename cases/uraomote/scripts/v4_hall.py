"""v4 晾画大厅 (script_v4.md 1.1, 1.2): the look of the hall before anything moves. A long empty hall with a floor
of still black water, rows of two-sided prints of her hung on wires, a row of high windows with the sky behind.
Two lights: dawn (表: a cold sun through the high windows and haze, the prints lit from the front) and rose (裏:
a rose lamp behind every print, so the back of each sheet shows through the front). Cycles stills.

    blender -b --factory-startup -P cases/uraomote/scripts/v4_hall.py -- [out_dir] [shot ...]
    shots: aisle_dawn beams_dawn print_dawn | aisle_rose front_rose beams_rose   (dawn and rose in separate runs)
    RES=50 SAMPLES=48 for a quick look

The prints are scripts/paper.py's two-sided sheets (the hybrid ones scripts/hybrid.py's), hung here on wires in
rows. The KV's back is KV' (same composition); every other print carries round 2's pictures, a 表 one in front and
a 裏 one of another composition behind.
The hall is plaster over a steel frame: a column on each long wall at every pier with a cross beam over the pair,
purlins under the concrete ceiling, the high windows in steel frames with old glass, a sill under each; a damp band
darkens the plaster above the water. Textures and the lamps and pipes are Poly Haven (scripts/fetch_assets.py);
the walls take painted plaster, or worn plaster calmed down where the painted one is not downloaded. `LAMPS` lights
the ceiling lamps (1 is about right; 0, the default, leaves them off).
Dawn is one sun through the windows and the sky's own light through them, nothing else: the beams in the haze and
the prints they fall on carry the picture, the rest of the hall stays dark. In rose light a print whose front gets
no light of its own shows only the dark lines of its 表 over the 裏 glowing through, which reads as stripes; a cold
front light keeps the 表 there, and a cold moon through the windows is the night's only other light.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402
import assets as A  # noqa: E402
import cyc  # noqa: E402
import kit  # noqa: E402
import mvlib as m  # noqa: E402
import paper as P  # noqa: E402
import texlib as T  # noqa: E402

ART = P.ART = os.path.join(C.CASE, "art", "v4")      # the pictures; paper.py reads them from here
L, WD, H = 40.0, 14.0, 12.0                 # the hall: length along +X, width along Y, height
X0, X1 = -16.0, L + 10.0                    # the walls, floor and ceiling run from the open near end past the far wall
SHEET_W, SHEET_H = P.SHEET_W, P.SHEET_H     # a print, metres (paper.py's usual sheet)
MARGIN, TOP, WET = P.MARGIN, P.TOP, P.WET   # its bare border, its top edge above the water, how much light it lets through
ROWS = [2.0 + 4.0 * i for i in range(7)]    # x of each wire
WINDOWS = [3.0 + 4.0 * i for i in range(10)]            # window centres along x
WIN_W, WIN_Z0, WIN_Z1 = 2.6, 6.0, 10.5                  # a window: width, glass from .. to
BAYS = [1.0 + 4.0 * i for i in range(-4, 12)]           # x of the columns and cross beams: on the piers
LAMPS = float(os.environ.get("LAMPS", 0.0))
SAMPLES = int(os.environ.get("SAMPLES", 0))             # 0: each shot's own count
ROSE = "#F0285A"
STEEL = "#23272B"                           # the frame's paint, dark and gone matt

# fronts are 表 pictures, backs 裏 ones; the first print (row 0, in the middle) is the KV with KV' behind it
KV = ("v4_kv_211", "v4_kvu_211_n75")
FRONTS = ["v4_a1_211", "v4_a2_211", "v4_a3_211", "v4_a4_211", "v4_q1_211", "v4_a5_211"]
BACKS = ["v4_u1_211", "v4_u2_211", "v4_c1_211", "v4_w2_211", "v4_u4_211", "v4_c2_211", "v4_c4_211"]


def _damp(mat, z0=0.6, z1=2.0, color="#5F635C"):
    """A damp band up from the water: the plaster darker and greener to z0, gone by z1, its edge wandering."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    src = bsdf.inputs["Base Color"].links[0].from_socket
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.9
    nz.inputs["Detail"].default_value = 5.0
    nt.links.new(geo.outputs["Position"], nz.inputs["Vector"])
    ragged = nt.nodes.new("ShaderNodeMath")                          # the height read +-0.6 m off, by the noise
    ragged.operation = "MULTIPLY_ADD"
    nt.links.new(nz.outputs["Fac"], ragged.inputs[0])
    ragged.inputs[1].default_value = 1.2
    nt.links.new(sep.outputs["Z"], ragged.inputs[2])
    band = nt.nodes.new("ShaderNodeMapRange")
    band.inputs["From Min"].default_value = z0 + 0.6
    band.inputs["From Max"].default_value = z1 + 0.6
    band.inputs["To Min"].default_value = 1.0
    band.inputs["To Max"].default_value = 0.0
    nt.links.new(ragged.outputs[0], band.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    nt.links.new(band.outputs["Result"], kit.sock(mix.inputs, "Factor", "VALUE"))
    nt.links.new(src, kit.sock(mix.inputs, "A", "RGBA"))
    kit.sock(mix.inputs, "B", "RGBA").default_value = m.srgb(color)
    nt.links.new(kit.sock(mix.outputs, "Result", "RGBA"), bsdf.inputs["Base Color"])


def frame(steel):
    """The steel: a column on each long wall at every pier, a cross beam over the pair under the ceiling, and three
    purlins the length of the hall carrying the slab."""
    for x in BAYS:
        for side in (-1, 1):
            col = A.rounded_box(f"column_{x:.0f}_{side:+d}", (0.24, 0.24, H), 0.004, [steel])
            col.location = (x, side * (WD / 2 - 0.12), H / 2)
        A.rounded_box(f"beam_{x:.0f}", (0.2, WD, 0.5), 0.004, [steel]).location = (x, 0.0, H - 0.75)
    for y in (-4.7, 0.0, 4.7):
        A.rounded_box(f"purlin_{y:+.0f}", (X1 - X0, 0.14, 0.5), 0.004, [steel]).location = ((X0 + X1) / 2, y, H - 0.25)


def windows(steel, plaster):
    """Each high window: a steel frame with two mullions and five transoms, old glass that lets the light through
    unbent and unshadowed, and a plaster sill."""
    glass = A.clear_glass()
    y, zc, hh = WD / 2 + 0.08, (WIN_Z0 + WIN_Z1) / 2, WIN_Z1 - WIN_Z0
    for x in WINDOWS:
        for dx in (-WIN_W / 2, WIN_W / 2):
            A.rounded_box(f"jamb_{x:.0f}{dx:+.1f}", (0.08, 0.1, hh + 0.08), 0.003, [steel]).location = (x + dx, y, zc)
        for dx in (-WIN_W / 6, WIN_W / 6):
            A.rounded_box(f"mullion_{x:.0f}{dx:+.1f}", (0.05, 0.08, hh), 0.003, [steel]).location = (x + dx, y, zc)
        for k in range(6):
            A.rounded_box(f"transom_{x:.0f}_{k}", (WIN_W, 0.08, 0.05), 0.003, [steel]).location = \
                (x, y, WIN_Z0 + k * hh / 5)
        pane = A.rounded_box(f"glass_{x:.0f}", (WIN_W, 0.006, hh), 0.0, [glass])
        pane.location = (x, y, zc)
        pane.visible_shadow = False
        A.rounded_box(f"sill_{x:.0f}", (WIN_W + 0.3, 0.5, 0.08), 0.004, [plaster]).location = \
            (x, WD / 2 - 0.05, WIN_Z0 - 0.04)


def hall(dawn):
    """The walls, ceiling, water, frame, windows and sky. Returns the walls (the dark one first), the sky and its
    emission, the water's, the plaster's and the steel's materials."""
    body = "painted_plaster_wall" if T._find("painted_plaster_wall", "diffuse") else "worn_plaster_wall"
    calm = {} if body == "painted_plaster_wall" else {"flat": ("#9C9B95", 0.55)}   # the worn one is all blotches
    # coarser and calmer than life: at 1280 px the set's grain under a raking lamp read as static on the far wall
    plaster = T.pbr(body, scale=1.5, bump=0.5, tint="#B8BAB4" if dawn else "#7C7E84", name="plaster", **calm)
    _damp(plaster)
    slab = T.pbr("concrete_slab_wall", scale=1.0, tint="#9A9AA0" if dawn else "#5A5A62", name="ceiling")
    steel = A._principled("frame", **{"Base Color": m.srgb(STEEL), "Roughness": 0.55})[0]
    # 3 cm of black water over a concrete floor: dark enough to read as a mirror, the floor only where a beam falls
    xm, xl = (X0 + X1) / 2, X1 - X0
    bed = A.rounded_box("floor", (xl, WD, 0.1), 0.0, [T.pbr("hangar_concrete_floor", scale=1.0, tint="#38383C")])
    bed.location = (xm, 0, -0.08)
    water, b = A._principled("water", **{"Base Color": (0.03, 0.03, 0.035, 1.0), "Roughness": 0.015, "IOR": 1.33,
                                         "Transmission Weight": 1.0})
    A._bump(water, b, 0.35, 0.015, detail=2.0, distance=0.03)      # still water: a mirror, not a mosaic
    A.rounded_box("water", (xl, WD, 0.03), 0.0, [water]).location = (xm, 0, -0.015)
    t = 0.4
    A.rounded_box("ceiling", (xl, WD + 2 * t, t), 0.0, [slab]).location = (xm, 0, H + t / 2)
    walls = [((xm, -WD / 2 - t / 2, H / 2), (xl, t, H)),                 # the dark wall
             ((L + t / 2, 0, H / 2), (t, WD, H)),                       # far end
             ((xm, WD / 2 + t / 2, WIN_Z0 / 2), (xl, t, WIN_Z0)),                           # window wall below
             ((xm, WD / 2 + t / 2, (WIN_Z1 + H) / 2), (xl, t, H - WIN_Z1))]                 # and above the windows
    edges = [X0] + [e for x in WINDOWS for e in (x - WIN_W / 2, x + WIN_W / 2)] + [X1]
    walls += [(((a + b2) / 2, WD / 2 + t / 2, (WIN_Z0 + WIN_Z1) / 2), (b2 - a, t, WIN_Z1 - WIN_Z0))
              for a, b2 in zip(edges[::2], edges[1::2])]                # the piers
    obs = []
    for k, (loc, size) in enumerate(walls):
        obs.append(A.rounded_box(f"wall{k}", size, 0.0, [plaster]))
        obs[-1].location = loc
    frame(steel)
    windows(steel, plaster)
    # the sky behind the windows: painted later (S1, S2), a glowing backdrop for now
    sky, nt, out = P.nodes("sky")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = m.srgb("#D6E4F2" if dawn else "#0E1630")
    em.inputs["Strength"].default_value = 2.5 if dawn else 0.4
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    backdrop = A.rounded_box("sky", (xl + 20, 0.1, 30), 0.0, [sky])
    backdrop.location = (xm, WD / 2 + 4.0, 10)
    backdrop.visible_shadow = False                  # the sun and the moon are beyond it; a slab would shade the hall
    return dict(walls=obs, sky=backdrop, sky_emission=em, water=water, plaster=plaster, steel=steel)


def _piece(aid, pick=None):
    """The one mesh of a Poly Haven model (or of a modular pack, `pick`), at real size, and its local bounds."""
    root = T.model(aid, scale=1.0, pick=pick)
    ob = next(c for c in root.children if c.type == "MESH")
    ob.parent = None
    bpy.data.objects.remove(root)
    vs = [v.co for v in ob.data.vertices]
    return ob, Vector([min(v[i] for v in vs) for i in range(3)]), Vector([max(v[i] for v in vs) for i in range(3)])


def _copies(ob, locs):
    """`ob` at the first location and a copy sharing its mesh at each of the others."""
    for k, loc in enumerate(locs):
        c = ob if k == 0 else ob.copy()
        if k:
            m._link(c)
        c.location = loc


def lamps():
    """Industrial lamps hanging from the ceiling between the rows, two to a row; lit by LAMPS, else off.
    Returns the bulbs (a point light under each lamp, with its full energy) and the lamps' emission inputs."""
    ob, lo, hi = _piece("hanging_industrial_lamp")
    glow = []
    for slot in ob.material_slots:
        for n in slot.material.node_tree.nodes if slot.material and slot.material.node_tree else []:
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Emission Strength"].default_value = 6.0 * LAMPS
                glow.append(n.inputs["Emission Strength"])
    spots = [(x + 2.0, y) for x in ROWS for y in (-3.2, 3.2)]
    _copies(ob, [(x - (lo.x + hi.x) / 2, y - (lo.y + hi.y) / 2, H - hi.z) for x, y in spots])
    bulbs = [cyc.point_light(f"lamp{k}", (x, y, H - (hi.z - lo.z) - 0.15), 4200, 400 * LAMPS, radius=0.12)
             for k, (x, y) in enumerate(spots)]
    return [(b, 400.0) for b in bulbs], glow


def pipes():
    """Two runs of pipe under the ceiling along the dark wall: the pack's straight piece end to end along X."""
    ob, lo, hi = _piece("modular_industrial_pipes_01", pick="pipe02")
    ob.rotation_euler = (0.0, math.pi / 2, 0.0)                # its length, along local Z, now runs along X
    cx, cy, n = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2, int((L + 12) / (hi.z - lo.z)) + 1
    _copies(ob, [(-6 + i * (hi.z - lo.z) - lo.z, y - cy, z + cx)
                 for y, z in ((-WD / 2 + 0.35, 9.6), (-WD / 2 + 0.6, 10.15)) for i in range(n)])


def hang(make=None):
    """The wires and the prints on them. `make(name, x, y, front, back, seed)` builds a print in place of
    paper.sheet() with paper.print_mat() (hybrid.make_print for the hybrid prints)."""
    mats, k = {}, 0
    steel = A._principled("steel", **{"Base Color": m.srgb("#3A3A40"), "Metallic": 1.0, "Roughness": 0.3})[0]
    prints = []
    for r, x in enumerate(ROWS):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.004, depth=WD, location=(x, 0, TOP + 0.04),
                                            rotation=(math.pi / 2, 0, 0))
        bpy.context.active_object.data.materials.append(steel)
        ys = [0.0] if r == 0 else ([-4.8, -1.6, 1.6, 4.8] if r % 2 else [-3.2, 0.0, 3.2])
        for y in ys:
            front, back = KV if r == 0 else (FRONTS[k % len(FRONTS)], BACKS[k % len(BACKS)])
            if r:
                k += 1
            name, seed = f"print_{r}_{y:+.1f}", r * 10 + int(y * 3)
            if make is not None:
                prints.append(make(name, x, y, front, back, seed))
                continue
            key = (front, back)
            if key not in mats:
                mats[key] = P.print_mat(front, back)
            prints.append(P.sheet(name, x, y, mats[key], seed=seed))
    return prints


def dawn_light():
    """表: one cold sun through the high windows, low enough to cross the hall and land on the dark wall and the
    water in front of it, raking the prints' fronts; and the sun off the water onto the ceiling. The sky's own
    light through the windows is the only fill. Each light with its full energy."""
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 9.0
    sun.angle = math.radians(0.6)
    sun.color = A.kelvin(7600)
    ob = bpy.data.objects.new("sun", sun)
    m._link(ob)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector((0.35, -0.85, -0.42)).normalized().to_track_quat("-Z", "Y")
    bounce = cyc.area_light("bounce", (L / 2, 0, 0.6), (L / 2, 0, 5), 20, 7000, 150, size_y=8)   # off the water
    return [(ob, 9.0), (bounce, 150.0)]


def rose_light(prints):
    """裏: a rose lamp behind every print, narrowed so it lights the paper and not the hall; a cold moon through the
    windows; a little cold light from above and from the near end on the fronts, so her 表 still reads while the
    裏 glows through it. Returns {print name: (lamp, energy)} and the cold lights with theirs."""
    behind = {}
    for p in prints:
        x, y = p.location.x, p.location.y
        lamp = cyc.area_light(f"behind_{p.name}", (x + 0.9, y, TOP - SHEET_H / 2), (x, y, TOP - SHEET_H / 2),
                              2.0, 2000, 160, size_y=3.6, color=ROSE, spread_deg=70)
        lamp.visible_glossy = False
        behind[p.name] = (lamp, 160.0)
    moon = bpy.data.lights.new("moon", "SUN")
    moon.energy = 2.5                                # a moon that lays real shafts through the windows
    moon.angle = math.radians(1.0)
    moon.color = m.srgb("#8FA4FF")[:3]
    mob = bpy.data.objects.new("moon", moon)
    m._link(mob)
    mob.rotation_mode = "QUATERNION"
    mob.rotation_quaternion = Vector((0.2, -0.75, -0.62)).normalized().to_track_quat("-Z", "Y")
    fill = cyc.area_light("fill", (L / 2, 0, H - 0.5), (L / 2, 0, 0), 30, 9000, 140, size_y=10, color="#5A78FF")
    front = cyc.area_light("front", (-6.0, 0, 4.0), (L / 2, 0, 2.5), 14, 9000, 260, size_y=6, color="#7C94FF")
    return behind, [(mob, 2.5), (fill, 140.0), (front, 260.0)]


def haze(dawn):
    # a little past the hall on every side: with its faces on the water's surface and on the walls' and ceiling's
    # inner faces, a ray leaving the water met the box's face at the same depth, and the water, seen from above,
    # mirrored nothing at all (a bare test: a lit panel over water, its reflection gone with the box's face on the
    # surface, back with the box half a metre lower)
    size, at = (L - X0 + 4.4, WD + 0.4, H + 0.8), ((X0 + L) / 2 + 2, 0, H / 2 + 0.15)
    if dawn:
        return cyc.haze("haze", size, at, 0.012, color="#E4ECF4", anisotropy=0.3)
    return cyc.haze("haze", size, at, 0.004, color="#F2D8E0", anisotropy=0.45)


def main():
    out, shots = cyc.args(os.path.join(C.RENDERS, "v4_hall"), ["aisle_dawn", "beams_dawn", "print_dawn"])
    dawn = all(s.endswith("dawn") for s in shots)
    if not dawn and any(s.endswith("dawn") for s in shots):
        sys.exit("dawn and rose shots need separate runs (the lights differ)")
    m.reset()
    cyc.cycles(bounces=8)
    cyc.world((0.0004, 0.0004, 0.0008))
    hall(dawn)
    lamps()
    pipes()
    prints = hang()
    if dawn:
        dawn_light()
    else:
        rose_light(prints)
    haze(dawn)
    cyc.post(bloom=0.35 if dawn else 0.6, threshold=1.0 if dawn else 0.75)
    kv = (ROWS[0], 0.0, TOP - SHEET_H / 2)
    mid = (ROWS[2], 0.3, 4.0)                                         # the middle print of the third row
    clip = (ROWS[2], -3.2 + SHEET_W / 2 - 0.12, TOP)                  # a clip of the third row's left print
    aisle = ((-1.0, -3.8, 0.75), (20.0, 0.8, 3.0), 24, 4.0)           # low over the water, the rows receding
    beams = ((7.2, -6.0, 1.2), (13.0, WD / 2, 7.6), 28, 5.6)          # from the dark wall up at the windows
    cams = {"aisle_dawn": cyc.camera("aisle_dawn", *aisle), "aisle_rose": cyc.camera("aisle_rose", *aisle),
            "beams_dawn": cyc.camera("beams_dawn", *beams), "beams_rose": cyc.camera("beams_rose", *beams),
            "print_dawn": cyc.camera("print_dawn", (8.8, -1.3, 4.55), (ROWS[2], -2.3, 4.72), 50, 2.8),
            "front_rose": cyc.camera("front_rose", (-4.6, 0.0, 2.95), kv, 28, 5.6)}
    focus = {"aisle_dawn": kv, "aisle_rose": kv, "beams_dawn": mid, "beams_rose": mid, "print_dawn": clip,
             "front_rose": kv}
    cams = {k: v for k, v in cams.items() if k in shots}
    cyc.render_shots(cams, shots, out, "hall", focus={k: focus[k] for k in cams},
                     samples={k: SAMPLES or (128 if k.endswith("dawn") else 160) for k in cams},
                     exposure={"aisle_dawn": 1.2, "beams_dawn": 0.4, "print_dawn": 0.8},
                     blend="hall_dawn.blend" if dawn else "hall_rose.blend")


if __name__ == "__main__":
    main()
