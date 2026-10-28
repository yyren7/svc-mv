"""Stills of the hybrid print (scripts/hybrid.py) in the hall of v4_hall.py: the KV at dawn and U1 (the row-1
print nearest the aisle) in rose light, each straight on and from the side, to judge the picture's planes as the
hall's surfaces (the sky behind her window moving against its frame, her water mirroring the lamps and taking a
ring, mirror glass) and her figure as a relief under the raking light, before the animatic hangs every print
this way.

    blender -b --factory-startup -P cases/uraomote/scripts/v4_hybrid.py -- [out_dir] [shot ...]
    shots: kv_dawn kv_side_dawn | u1_rose u1_side_rose      (dawn and rose in separate runs)
    RELIEF=0.14 how far the nearest part of a picture stands off the paper, metres

Needs art/v4/maps/<name>_{depth,flat,parts}.png from scripts/maps.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402
import cyc  # noqa: E402
import hybrid as H  # noqa: E402
import mvlib as m  # noqa: E402
import v4_hall as V  # noqa: E402

H.HERO = {V.KV[0]}                          # the KV at the full relief, the others a little flatter


def main():
    out, shots = cyc.args(os.path.join(C.RENDERS, "v4_hybrid"), ["kv_dawn", "kv_side_dawn"])
    dawn = all(s.endswith("dawn") for s in shots)
    if not dawn and any(s.endswith("dawn") for s in shots):
        sys.exit("dawn and rose shots need separate runs (the lights differ)")
    m.reset()
    cyc.cycles(bounces=8)
    cyc.world((0.0004, 0.0004, 0.0008))
    V.hall(dawn)
    if not dawn:
        V.LAMPS = 1.0                                   # lamps on at night: something for her water to mirror
    V.lamps()
    V.pipes()
    sky = "v4_s1_211" if dawn else "v4_s3_211"
    prints = V.hang(make=lambda name, x, y, front, back, seed: H.make_print(
        name, x, y, ("v4_u1_211" if name == "print_1_-1.6" else front), back, seed, sky))
    kv, u1 = next(p for p in prints if p.name == "print_0_+0.0"), next(p for p in prints if p.name == "print_1_-1.6")
    if dawn:
        V.dawn_light()
    else:
        V.rose_light(prints)
    V.haze(dawn)
    cyc.post(bloom=0.35 if dawn else 0.6, threshold=1.0 if dawn else 0.75)
    hair = H.anchor(u1, "v4_u1_211", 0)
    H.ring(u1.name, hair["point"].y - u1.location.y, -1.6, 0.5, 0.6)            # one ring below her hair
    kvc = (kv.location.x, 0.0, 3.4)
    u1c = (u1.location.x, u1.location.y, 3.2)
    cams = {"kv_dawn": cyc.camera("kv_dawn", (-4.2, -0.9, 3.3), kvc, 35, 4.0),
            "kv_side_dawn": cyc.camera("kv_side_dawn", (-1.6, -4.2, 3.4), (kvc[0], -0.3, 3.4), 40, 4.0),
            "u1_rose": cyc.camera("u1_rose", (1.2, -2.6, 3.0), u1c, 35, 4.0),
            "u1_side_rose": cyc.camera("u1_side_rose", (3.2, -5.2, 3.0), (u1c[0], u1c[1] - 0.3, 3.2), 40, 4.0)}
    focus = {"kv_dawn": kvc, "kv_side_dawn": kvc, "u1_rose": u1c, "u1_side_rose": u1c}
    cams = {k: v for k, v in cams.items() if k in shots}
    cyc.render_shots(cams, shots, out, "hybrid", focus={k: focus[k] for k in cams},
                     samples={k: V.SAMPLES or (128 if dawn else 160) for k in cams},
                     exposure={k: (1.0 if dawn else 0.3) for k in cams},
                     blend="hybrid_dawn.blend" if dawn else "hybrid_rose.blend")


if __name__ == "__main__":
    main()
