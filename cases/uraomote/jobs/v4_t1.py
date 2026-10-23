"""v4 round 1: her new design and the look, before any picture is drawn from a reference. A design sheet, the
表 key visual, and one picture from each part of script v4 (dawn window, chorus, rain, the night on the water), plus
the two-sided print as a painting.
    python cases/uraomote/jobs/v4_t1.py      -> cases/uraomote/jobs/v4_t1.json"""
import json
import os

from v4_prompts import HER, LOOK, OMOTE, TALL, URA, WIDE, qwen

HERE = os.path.dirname(os.path.abspath(__file__))

SHOTS = {
    "sheet": (WIDE, (201, 203, 205), [
        "Character design reference sheet of one original anime girl on a plain white background: a full-body front "
        "view, a full-body back view and a full-body side view standing in a row, and three head close-ups with "
        "different expressions (calm and composed; startled with wide eyes; a fragile crying smile).",
        "The girl is " + HER,
        "Clean professional character sheet, the same design in every view, delicate lineart, soft cel shading, "
        "refined modern anime style. No text, no labels, no letters."]),
    "kv": (TALL, (201, 203, 205, 207), [
        "Vertical key visual. The girl is " + HER,
        "She stands in a tall, empty white room in soft morning light and turns her face over her shoulder toward "
        "the viewer with a calm, composed, faintly melancholic gaze; framed from the thighs up, three-quarter view, "
        "placed right of centre with open pale space on the left. A breath of air lifts a few strands of her black "
        "hair and a glimpse of the rose-red underlayer shows at the ends. Sheer white curtains glow behind her and "
        "dust motes drift in a pale beam of light.", LOOK, OMOTE]),
    "window": (WIDE, (201, 203), [
        "The girl is " + HER,
        "She stands by a tall window in a bare white room at dawn, fingertips resting on the cold glass, looking out "
        "at a pale sky, seen from behind and a little to the side so her profile shows. Sheer white curtains billow "
        "inward; cool light floods in and lays long soft shadows of the window frame across the floor. A glass of "
        "water stands on the windowsill.", LOOK, OMOTE]),
    "chorus": (WIDE, (201, 203, 205, 207), [
        "The girl is " + HER,
        "She is suspended in a dark, endless space as if sinking through deep water, seen slightly from below, one "
        "hand reaching up toward a far light. Her long black hair flares out around her and the vivid rose-red "
        "underlayer blazes in the light. Ribbons and clouds of luminous rose-red ink unfurl around her like smoke in "
        "water, with tiny glittering droplets. Her eyes are wide open, overwhelmed, feverish and beautiful.",
        LOOK, URA]),
    "water": (WIDE, (201, 203), [
        "The girl is " + HER,
        "Seen from directly above: she lies on her back on a sheet of perfectly still black water at night, her long "
        "black hair spread out around her head like spilled ink with the rose-red underlayer fanning through it. She "
        "stares straight up at the viewer with wide sleepless eyes and the faint start of a crooked smile. A ring of "
        "soft rose light glows on the water around her.", LOOK, URA]),
    "rain": (WIDE, (201, 203), [
        "The girl is " + HER,
        "Close-up of her face in the rain at night. Rain streams down her face and wet black hair clings to her "
        "cheeks; thin streaks of luminous rose-red watercolour ink run down from the corners of her eyes and blur "
        "into the raindrops, as if the picture of her were dissolving. She looks straight at the viewer, calm on "
        "the surface and breaking underneath. Soft rose bokeh in the dark behind her.", LOOK, URA]),
    "print": (WIDE, (201, 203), [
        "A tall sheet of thin translucent paper hangs from a wire in a dark, empty hall with a floor of still black "
        "water. Printed on the paper is an elegant anime portrait of " + HER,
        "A strong rose-red light behind the sheet makes the paper glow, and a second, mirrored drawing of the same "
        "girl printed on the back of the sheet shows through: the same pose, but her hair flies loose and her eyes "
        "are wide and feverish. The sheet and its glow are reflected in the black water. Haze, a cold beam from a "
        "high window.", LOOK]),
}

jobs = [qwen(f"v4_{shot}_{seed}", seed, size, *parts) for shot, (size, seeds, parts) in SHOTS.items() for seed in seeds]
with open(os.path.join(HERE, "v4_t1.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(jobs, f, ensure_ascii=False, indent=1)
print(f"v4_t1.json: {len(jobs)} jobs")
