"""The animatic engine: a film cut on a song's downbeats, every frame built from the set at rest, rendered in
Cycles at a chosen size and sample count, so the pacing, the cameras and the effects can be judged from contact
sheets before a real render.

A case gives it a list of shots `(start bar, section, title, fn)`; `fn(u, t, b)` poses the set for the frame at
time t (seconds) and bar b, u running 0..1 over the shot. Every frame starts from the set at rest (the case's
`reset(scene, t, b)`), and the shot sets what it needs, so any frame can be rendered alone: frames are numbered
on the song's clock and frames already in the folder are skipped, so bar ranges run side by side into one folder.
Every frame is labelled with its section, shot, bar and time (stamp()).

    blender -b --factory-startup -P <case shots>.py -- <frames_dir> [first_bar last_bar]
    env: FPS=12 SAMPLES=16 WIDTH=640, LIMIT=1 (the first frame of every shot), AT=0.25,0.5 (those points of every
         shot), ONLY=P4,P5 (those sections), DEVICE=CPU (render on the CPU), DRY=1 (pose every frame, render nothing,
         save the .blend)

Then scripts/cut.py joins the frames with the song (and puts the film's finish on), scripts/sheet.py lays them
out as a contact sheet, scripts/grab.py saves full frames to look at, and scripts/exp.sh renders the same film
with a change, side by side. The per-frame setters that must write only on change are cyc.put and cyc.energy.
"""
import bisect
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

import cyc
import kit
import mvlib as m

FPS = int(os.environ.get("FPS", 12))
SAMPLES = int(os.environ.get("SAMPLES", 16))
WIDTH = int(os.environ.get("WIDTH", 640))
LIMIT = int(os.environ.get("LIMIT", 0))
AT = [float(a) for a in os.environ.get("AT", "").split(",") if a]
ONLY = [s for s in os.environ.get("ONLY", "").split(",") if s]
DRY = os.environ.get("DRY") == "1"
put, energy = cyc.put, cyc.energy


def args(default_frames):
    """`-- <frames_dir> [first_bar last_bar]` -> (frames dir, first bar or None, last bar or None)."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    frames = os.path.abspath(argv[0]) if argv else default_frames
    first, last = (float(argv[1]), float(argv[2])) if len(argv) > 2 else (None, None)
    return frames, first, last


# ---------------------------------------------------------------- the song's clock

class Clock:
    """The song's downbeats and beats (scripts/analyze.py's timing json): bars to seconds and back."""

    def __init__(self, timing_path):
        timing = json.load(open(timing_path, encoding="utf-8"))
        self.down, self.beats, self.duration = timing["downbeats"], timing["beats"], timing["duration"]
        self.last_beat_t = self.duration - (self.beats[-1] - self.beats[-2])   # the beats found may stop early; the song rings on

    def at(self, bar):
        """Seconds at a bar (a downbeat index; fractions fall between downbeats, bars below 0 in the pickup)."""
        d = self.down
        i = max(0, min(math.floor(bar), len(d) - 2))
        return max(0.0, d[i] + (bar - i) * (d[i + 1] - d[i]))

    def bar_at(self, t):
        d = self.down
        i = max(0, min(bisect.bisect_right(d, t) - 1, len(d) - 2))
        return i + (t - d[i]) / (d[i + 1] - d[i])

    def punch(self, t, amount, decay=0.12):
        """The impact push: `amount` on the beat, decaying over `decay` seconds."""
        i = bisect.bisect_right(self.beats, t) - 1
        return amount * math.exp(-(t - self.beats[i]) / decay) if i >= 0 else 0.0

    def last_beat(self, t):
        return self.beats[max(0, bisect.bisect_right(self.beats, t) - 1)]


def ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def clamp(u):
    return min(1.0, max(0.0, u))


# ---------------------------------------------------------------- the scene, the finish, the label

def scene(width=None, samples=None, bounces=6):
    """A fresh Cycles scene for the animatic: no caustics (fireflies at these samples), the GPU unless DEVICE=CPU,
    16:9 at `width`, persistent data (the set is rebuilt only where a frame changes it)."""
    width, samples = width or WIDTH, samples or SAMPLES
    m.reset()
    sc = cyc.cycles(samples=samples, bounces=bounces)
    sc.cycles.caustics_refractive = sc.cycles.caustics_reflective = False
    if os.environ.get("DEVICE") == "CPU":
        sc.cycles.device = "CPU"
        sc.cycles.denoising_use_gpu = False
    sc.render.resolution_x, sc.render.resolution_y = width, width * 9 // 16
    sc.render.resolution_percentage = 100
    sc.render.use_persistent_data = True
    return sc


def compositor(paper="#CFC8BA", threshold=0.8, strength=0.4, size=0.6, dispersion=0.004):
    """Bloom and a touch of dispersion (as cyc.post), and D4: the frame as its own print on paper for a beat, the
    negative multiplied by the paper's colour, mixed in by the returned lineart socket (0..1). Returns (lineart,
    glare strength socket). (Edges from the normal, depth or mist passes were tried for a line drawing: all three
    are noise at animatic samples.)"""
    sc = bpy.context.scene
    tree = bpy.data.node_groups.new("anim_post", "CompositorNodeTree")
    sc.compositing_node_group = tree
    kit._iface(tree, "Image", "OUTPUT", "NodeSocketColor")
    g = kit.G(tree)
    rl = g.node("CompositorNodeRLayers")
    glare = g.node("CompositorNodeGlare")
    for name, val in (("Type", "Bloom"), ("Threshold", threshold), ("Strength", strength), ("Size", size)):
        try:
            kit.sock(glare.inputs, name).default_value = val
        except (KeyError, TypeError, ValueError) as e:
            print("glare", name, e)
    g.link(rl.outputs["Image"], kit.sock(glare.inputs, "Image"))
    lens = g.node("CompositorNodeLensdist")
    g.link(glare.outputs[0], kit.sock(lens.inputs, "Image"))
    kit.sock(lens.inputs, "Dispersion").default_value = dispersion

    gam = g.node("ShaderNodeGamma")                                            # the darks lifted first, so the
    kit.sock(gam.inputs, "Gamma").default_value = 0.4                           # negative of a dark room has tones
    g.link(lens.outputs[0], kit.sock(gam.inputs, "Color", "RGBA"))
    inv = g.node("CompositorNodeInvert")
    g.link(gam.outputs[0], kit.sock(inv.inputs, "Color", "RGBA"))
    art = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    kit.sock(art.inputs, "Factor", "VALUE").default_value = 1.0
    g.link(inv.outputs[0], kit.sock(art.inputs, "A", "RGBA"))
    kit.sock(art.inputs, "B", "RGBA").default_value = m.srgb(paper)         # paper in shadow: a flash, not a strobe
    mix = g.node("ShaderNodeMix", data_type="RGBA")
    lineart = kit.sock(mix.inputs, "Factor", "VALUE")
    g.link(lens.outputs[0], kit.sock(mix.inputs, "A", "RGBA"))
    g.link(kit.sock(art.outputs, "Result", "RGBA"), kit.sock(mix.inputs, "B", "RGBA"))
    g.link(kit.sock(mix.outputs, "Result", "RGBA"), g.node("NodeGroupOutput").inputs[0])
    sc.render.use_compositing = True
    return lineart, kit.sock(glare.inputs, "Strength")


def stamp(size=11):
    """Only the note on the frame (section, shot, bar, time), in a small font."""
    r = bpy.context.scene.render
    r.use_stamp = True
    for attr in dir(r):
        if attr.startswith("use_stamp_") and attr not in ("use_stamp_note", "use_stamp_labels"):
            try:
                setattr(r, attr, False)
            except (AttributeError, TypeError):
                pass
    r.use_stamp_note = True
    r.stamp_font_size = size


def aim(cam, eye, target, lens=35.0, fstop=8.0, roll=0.0, focus=None, up=(0, 0, 1), ortho=None):
    """Put the camera at `eye` looking at `target`, rolled by `roll` degrees, `up` the world direction that is up
    in the frame (for a shot straight down), `ortho` an orthographic frame width; `focus` is a distance or a point
    (default: the target). Returns (eye, forward)."""
    eye, target = Vector(eye), Vector(target)
    f = (target - eye).normalized()
    upv = Vector(up)
    if abs(f.dot(upv)) > 0.999:
        upv = Vector((1.0, 0.0, 0.0))
    r = f.cross(upv).normalized()
    rot = Matrix((r, r.cross(f), -f)).transposed()
    if roll:
        rot = rot @ Matrix.Rotation(math.radians(roll), 3, "Z")
    cam.matrix_world = Matrix.Translation(eye) @ rot.to_4x4()
    data = cam.data
    data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        data.ortho_scale = ortho
    data.lens = lens
    data.dof.aperture_fstop = fstop
    data.dof.focus_object = None
    data.dof.focus_distance = focus if isinstance(focus, (int, float)) else \
        ((Vector(focus) if focus is not None else target) - eye).length
    return eye, f


# ---------------------------------------------------------------- frames

def label(sec, title, b, t):
    return f"{sec} {title}  |  bar {math.floor(b)}.{int(b % 1 * 4) + 1}  |  {int(t // 60)}:{t % 60:04.1f}"


def run(frames, shots, clock, setup, reset, after=None, first=None, last=None, name="animatic"):
    """Render the frames the environment asks for into `frames`: `setup()` builds the set once and returns the
    scene; for each frame `reset(scene, t, b)` puts it at rest, the shot's fn(u, t, b) poses it, `after(t)` (the
    strands' sway, say) runs last. `first`/`last` are bars. With DRY the shots run, nothing renders, and the .blend
    is saved beside the frames folder."""
    os.makedirs(frames, exist_ok=True)
    starts = [clock.at(s[0]) for s in shots] + [clock.duration]
    lo = round(clock.at(first) * FPS) if first is not None else 0
    hi = round(clock.at(last) * FPS) if last is not None else round(clock.duration * FPS)
    path = lambda f: os.path.join(frames, f"f_{f:05d}.png")   # noqa: E731
    todo = []
    for k, (bar, sec, title, fn) in enumerate(shots):
        if ONLY and sec not in ONLY:
            continue
        fr = list(range(round(starts[k] * FPS), round(starts[k + 1] * FPS)))
        if AT:
            fr = sorted({fr[round(a * (len(fr) - 1))] for a in AT}) if fr else []
        elif LIMIT:
            fr = fr[:LIMIT]
        todo += [(f, k) for f in fr if lo <= f < hi and not os.path.exists(path(f))]
    if not todo:
        print(f"{name}: nothing to do")
        return
    sc = setup()
    for done, (f, k) in enumerate(todo):
        bar, sec, title, fn = shots[k]
        t = f / FPS
        b = max(clock.bar_at(t), bar)              # rounding can put a shot's first frame just before it
        reset(sc, t, b)
        fn((t - starts[k]) / (starts[k + 1] - starts[k]), t, b)
        if after is not None:
            after(t)
        sc.render.stamp_note_text = label(sec, title, b, t)
        sc.render.filepath = path(f)
        if not DRY:
            bpy.ops.render.render(write_still=True)
        if done % 24 == 0:
            print(f"{name}: {done + 1}/{len(todo)} frames, now {sec} {title} at {t:.2f} s", flush=True)
    if DRY:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(frames), f"{name.replace(' ', '_')}_dry.blend"))
    print(f"{name}: {len(todo)} frames done")
