"""v4 round 2: the illustrations of script_v4.md section 3.4, drawn by Qwen from her design sheet (v4_sheet_201,
round 1's pick) so that every picture is the same girl. Two seeds each, and the three skies; KV' and Q2 follow in
the next round from the picks here (same composition, the 裏 version).
Round 1 taught: the 表 pictures already work; the 裏 ones came out flat (one pink light, blank faces, pink smoke for
ink, a waving pose), the ink tears read as blood, and the bird's-eye view was ignored. So the 裏 light has a cold
fill, every face names its expression, the ink is described as ink in water, and the framing is closer.
    python cases/uraomote/jobs/v4_t2.py                       -> cases/uraomote/jobs/v4_t2.json
    python cases/uraomote/jobs/v4_t2.py <art dir> <input dir>  also copies the reference picture (needs PIL)
On the server: <art dir> is ComfyUI/output, <input dir> is ComfyUI/input."""
import json
import os
import sys

from v4_prompts import HIDDEN, INK, KEEP, LOOK, LOOSE, OMOTE, REF, SHEET, SPLIT, TALL, URA, WET, WIDE, qwen

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = {
    # 表
    "kv": (TALL, OMOTE, HIDDEN,
           "Vertical key visual, medium shot from the waist up. She stands by a tall window in an empty white room; "
           "the morning sun lays the soft shadow of the window frame across her shoulder and the wall behind her. She "
           "turns her face over her shoulder toward the viewer with a calm, composed, faintly melancholic gaze, lips "
           "closed. Placed right of centre with open pale space on the left. Dust motes drift in the beam."),
    "a1": (WIDE, OMOTE, HIDDEN,
           "She stands by a tall window in a bare white room at dawn, fingertips resting on the cold glass, looking out "
           "at a pale sky, seen from behind and a little to the side so her profile shows. Sheer white curtains billow "
           "inward; cool light lays long soft shadows of the window frame across the floor. A glass of water stands "
           "on the windowsill."),
    "a2": (WIDE, OMOTE, HIDDEN,
           "In a long white corridor full of morning light she glances back over her shoulder at the viewer while "
           "walking away, the smallest composed smile; her skirt and neckerchief tie sway. Framed from the waist up, "
           "placed on the left third, tall windows on the right throwing bars of light."),
    "a3": (WIDE, OMOTE, HIDDEN,
           "She ties her black neckerchief in front of a tall mirror in a white room at dawn. We see her face in the "
           "mirror, composed, eyes lowered to the knot; her real shoulder and hair are soft and out of focus in the "
           "foreground."),
    "a4": (WIDE, OMOTE, HIDDEN,
           "Close-up: her fingertips touch a cold window pane misted with morning condensation, leaving clear marks. "
           "Her face is just behind the glass, softly out of focus, eyes looking through it at something far away."),
    "a5": (WIDE, OMOTE, HIDDEN,
           "Close-up from above of her face lying on a white pillow in soft dawn light, eyes gently closed, long "
           "lashes, lips relaxed, strands of black hair spread across the white linen."),
    "q1": (WIDE, OMOTE, HIDDEN,
           "Tight close-up of her face in three-quarter view, turned toward the right of the frame, calm and composed, "
           "looking just past the viewer. Placed on the left third with empty pale space on the right."),
    # 裏
    "c1": (WIDE, URA, LOOSE,
           "Medium close-up from the waist up, seen from slightly below: she sinks backwards through deep dark water, "
           "head tilted back, lips parted as if her breath has caught, eyes wide and glistening. Her hair streams "
           "upward in slow motion. Veils and filaments of luminous rose-red ink unfurl around her and in front of the "
           "lens; tiny bubbles rise; one faint shaft of cold light falls from far above. " + INK),
    "c2": (WIDE, URA, LOOSE,
           "Extreme close-up of her eyes and the bridge of her nose: eyes wide open and trembling, tears welling on "
           "the lower lids, brows drawn together, rose-red light reflected in her dark irises, strands of black and "
           "rose-red hair crossing her face."),
    "c3": (WIDE, URA, LOOSE,
           "Her open hand reaches toward the viewer out of the darkness, sharp in the foreground; threads of luminous "
           "rose-red ink trail from her fingertips. Behind it her face, slightly out of focus, stares at her own hand "
           "with parted lips, frightened and fascinated. " + INK),
    "c4": (WIDE, URA, LOOSE,
           "She spins around in the darkness, seen from a low angle: her hair, neckerchief tie and pleated skirt flare "
           "out with the turn, and spirals of luminous rose-red ink follow the motion. Her face, turned toward the "
           "viewer mid-spin, wears a dazed, almost euphoric half-smile. " + INK),
    "w1": (TALL, URA, WET,
           "Full-body back view: she stands still in heavy rain at night, seen straight from behind, arms by her "
           "sides, against a plain dark background; a crisp clean silhouette with a rim of rose light, rain streaks "
           "falling in front of her."),
    "w2": (WIDE, URA, WET,
           "Close-up of her face seen through falling rain at night: raindrops on her lashes and lips, water running "
           "down her cheeks, rose-red light from the side turning the raindrops into glowing sparks. She looks "
           "straight at the viewer, lips slightly parted, eyes glistening, calm on the surface and breaking underneath."),
    "u1": (WIDE, URA, LOOSE,
           "Close bird's-eye view looking straight down: she lies on her back on the surface of still black water at "
           "night, seen from the waist up, her face turned up to the camera, her hair fanned out around her head on "
           "the water like spilled ink with the rose-red underlayer spreading through it, faint ripples. Wide "
           "sleepless eyes, the first hint of a crooked smile."),
    "u2": (WIDE, URA, LOOSE,
           "She sits on the floor of a dark room hugging her knees, outlined by rose-red rim light from behind, her "
           "chin on her knees; she looks at the viewer with a crooked, unsettling, beautiful smile and glassy eyes."),
    "u4": (WIDE, URA, LOOSE,
           "Extreme close-up: she bites her thumbnail, her eyes sliding sideways to the viewer, intense and feverish, "
           "rose-red light on one side of her face, the other side in cold blue shadow."),
    "r0": (WIDE, URA, LOOSE,
           "She runs straight toward the viewer through a dark hall flooded with shallow black water, hair streaming "
           "back, neckerchief tie flying, water splashing up around her loafers, rows of tall hanging paper sheets "
           "glowing rose-red behind her; low angle, determined wet eyes, motion blur at the edges."),
    # 表 + 裏
    "f1": (WIDE, SPLIT, LOOSE,
           "She leaps high in mid-air with her arms open and her head tilted back, eyes closed in release, torn pieces "
           "of white paper whirling around her against a vast painted sky breaking open with light."),
    "f2": (WIDE, SPLIT, LOOSE,
           "Extreme close-up of her face looking straight at the viewer, one eye calm and clear, the other wet with a "
           "single tear, a serene, quiet expression; strands of black and rose-red hair drift across her face."),
}

# skies for D2, no people
SKIES = {
    "s1": "A lavish painted anime sky at dawn: pale blue and silver clouds, the first cold light, a thin moon fading. "
          "No people, no buildings, no text.",
    "s2": "A lavish painted anime night sky full of heavy rain clouds, deep ink-blue, a faint rose glow low down, "
          "slanting streaks of rain. No people, no buildings, no text.",
    "s3": "A vast lavish painted anime sky breaking open after rain: towering white clouds, blinding white light "
          "pouring through, a few rose-tinted edges. No people, no buildings, no text.",
}


def refs(art, inp):
    from PIL import Image
    Image.open(os.path.join(art, SHEET)).convert("RGB").save(os.path.join(inp, REF[0]))
    print(*REF)


jobs = [qwen(f"v4_{shot}_{seed}", seed, size, KEEP, hair, scene, LOOK, light, ref=REF)
        for shot, (size, light, hair, scene) in SHOTS.items() for seed in (211, 213)]
SKY_LOOK = ("Lavish, luminous hand-painted anime background art for a film, painterly clouds with soft light and subtle "
            "colour gradients, a wide cinematic composition.")
jobs += [qwen(f"v4_{shot}_211", 211, WIDE, sky, SKY_LOOK) for shot, sky in SKIES.items()]
with open(os.path.join(HERE, "v4_t2.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(jobs, f, ensure_ascii=False, indent=1)
print(f"v4_t2.json: {len(jobs)} jobs")

if len(sys.argv) == 3:
    refs(sys.argv[1], sys.argv[2])
