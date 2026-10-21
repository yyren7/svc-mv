"""Batch t8: Pheebie in the hand the user picked (p7_i2i_face_50/65): Qwen draws her outfit right from her debut
sheet, Anima redraws it at 0.5 and 0.65. Eight close-ups are new; the earlier Qwen pictures get the same redraw.
    python characters/pheebie/jobs/t8.py      -> characters/pheebie/jobs/t8.json"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REFS = ["ref_pheebie_up_clean.png", "ref_pheebie_full.png"]
KEEP = "Keep her face, hairstyle, hair colours, accessories and outfit exactly as in the reference pictures."
QNEG = "text, letters, name tag, label, watermark, signature, logo"

TAGS = ("masterpiece, best quality, safe, newest, 1girl, solo, pheebie, cute, petite, pale skin, blush, short hair, "
        "bob cut, ash blonde hair, streaked hair, black hair, two-tone hair, cat ears, animal ears, siamese cat, "
        "brown ear tips, glasses, round eyewear, blue eyes, ear piercing, black choker, black bowtie, white bolero, "
        "cropped jacket, short puffy sleeves, black cuffs, frilled collar, black shirt, cross-laced clothes, "
        "black corset, underbust, brooch, key, pocket watch")
PASTEL, NIGHT = "soft shading, pastel colors, delicate lineart", "soft shading, delicate lineart"
WHO = ("Pheebie, a cute and petite Siamese-cat girl with pale skin who works in a cafe tea room: a short ash-blonde bob "
       "with a black streak through her bangs, Siamese cat ears that are cream with dark brown tips, round thin-rimmed "
       "glasses over blue eyes and a gentle smile. She wears a white cropped bolero with short puffy sleeves and black "
       "cuffs over a black shirt laced crosswise at the chest, a black bowtie and choker, a black underbust corset, a "
       "blue shield badge with a golden key and a pocket watch pinned on the bolero.")
SOFT = "Soft, delicate and cute, in the gentle pastel style of her official art."
ANEG = ("worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration, watermark, text, "
        "signature, dark-skinned female, tan, mature female, lipstick, makeup, thick lips, large breasts")

# name: (Qwen picture to start from, shot tags, style, the scene in a sentence); the Qwen prompt for the new ones
OLD = {
    "cup": ("p7_q_cup_00001_.png", "upper body, holding cup, coffee cup, latte art, cafe, indoors, warm lighting, "
            "blurry background, smile, looking at viewer", PASTEL,
            "Here she sits in a warm cafe holding a cup of latte in both hands."),
    "glasses": ("p7_q_glasses_00001_.png", "upper body, adjusting eyewear, finger on eyewear, smile, looking at viewer, "
                "simple background, white background", PASTEL, "Here she pushes up her glasses with one finger."),
    "paw": ("p7_q_paw_00001_.png", "upper body, paw pose, paw gloves, open mouth, fang, :d, looking at viewer, "
            "simple background, white background", PASTEL, "Here she makes cat paws with fluffy paw gloves and laughs."),
    "lookback": ("p7_q_lookback_clean.png", "upper body, from behind, looking back, looking at viewer, smile, "
                 "simple background, yellow background", PASTEL, "Here she looks back over her shoulder at the viewer."),
    "bedroom": ("p6_bedroom_00001_.png", "sitting, on bed, holding clock, alarm clock, bedroom, indoors, window, "
                "morning, sunlight, smile, looking at viewer", PASTEL,
                "Here she sits on her bed in soft morning light holding an old red alarm clock."),
    "booth": ("p6_booth_00001_.png", "cowboy shot, phone booth, holding phone, telephone, night, rain, neon lights, "
              "smile, looking at viewer", NIGHT,
              "Here she stands in a rainy phone booth at night holding the green payphone receiver to her ear."),
    "platform": ("p6_platform_00001_.png", "full body, standing, train station, railway platform, train, sunset, "
                 "backlighting, power lines, looking at viewer", PASTEL,
                 "Here she stands on a small rural train platform at sunset, a cream and vermilion train behind her."),
    "ura": ("p6_ura_00001_.png", "upper body, holding heart, glowing heart, neon lights, pink light, cyan light, "
            "rim lighting, black background, floating hair", NIGHT,
            "Here she holds a glowing pink heart in the dark, lit by pink and cyan neon."),
}
NEW = {
    "tilt": ("a close-up of her face and shoulders seen from slightly above: she tilts her head to one side and smiles "
             "softly at the viewer, touching the rim of her round glasses with one finger, warm soft afternoon light, "
             "pale cream background",
             "portrait, close-up, from above, head tilt, finger on eyewear, smile, looking at viewer, simple background",
             PASTEL, "Here she tilts her head and touches the rim of her glasses."),
    "watch": ("a close-up of her face and shoulders: she holds her open pocket watch up beside her cheek toward the "
              "viewer and smiles, soft light, pale cream background",
              "portrait, close-up, holding pocket watch, smile, looking at viewer, simple background", PASTEL,
              "Here she holds her open pocket watch up beside her cheek."),
    "cup": ("a close-up of her face: she peeks over the rim of a white coffee cup held in both hands so only her eyes "
            "and glasses show above it, her eyes smiling, a wisp of steam, warm cafe light",
            "portrait, close-up, holding cup, covered mouth, peeking, steam, cafe, warm lighting, looking at viewer",
            PASTEL, "Here she peeks over the rim of a coffee cup held in both hands."),
    "sing": ("a close-up of her face and shoulders: eyes closed, singing softly into an old silver microphone, a soft "
             "warm spotlight from above, a dark warm background with floating specks of dust",
             "portrait, close-up, closed eyes, singing, open mouth, holding microphone, spotlight, dark background, "
             "dust particles", NIGHT, "Here she sings with her eyes closed into an old microphone under a warm spotlight."),
    "shh": ("a close-up of her face: she winks and holds one finger to her lips, playful, soft light, pale cream "
            "background",
            "portrait, close-up, one eye closed, finger to mouth, shushing, smile, looking at viewer, simple background",
            PASTEL, "Here she winks and holds a finger to her lips."),
    "table": ("a close-up: she rests her cheek on her folded arms on a wooden cafe table and looks up at the viewer "
              "with a sleepy smile, soft morning light through a window",
              "close-up, head on arms, head rest, table, cafe, looking up, looking at viewer, sleepy, smile, morning, "
              "sunlight", PASTEL,
              "Here she rests her cheek on her folded arms on a cafe table and looks up with a sleepy smile."),
    "rain": ("a close-up of her face and shoulders under a clear plastic umbrella in the rain, raindrops on the "
             "umbrella, she looks up at the viewer with a small smile, soft grey light",
             "portrait, close-up, umbrella, transparent umbrella, rain, water drop, looking up, looking at viewer, smile",
             PASTEL, "Here she stands under a clear umbrella in the rain."),
    "ura": ("a close-up of her face at night, lit from one side by pink neon light and from the other by cyan, the "
            "neon reflected in her round glasses, a small mysterious smile, dark background",
            "portrait, close-up, night, neon lights, pink light, cyan light, rim lighting, reflection, dark background, "
            "smile, looking at viewer", NIGHT, "Here she is lit by pink and cyan neon at night, the light in her glasses."),
}


def redraw(name, init, shot, style, scene):
    """Anima over a Qwen picture at the two strengths the user liked."""
    soft = SOFT if style == PASTEL else "Soft and delicate, in the gentle style of her official art."
    return [dict(model="anima", name=f"{name}_{int(d * 100)}", init=init, denoise=d, seed=81, w=1024, h=1024,
                 prompt=f"{TAGS}, {shot}, {style}. {WHO} {scene} {soft}", negative=ANEG) for d in (0.5, 0.65)]


jobs = [dict(model="qwen", name=f"p8_q_{k}", ref=REFS, w=1152, h=896, seed=91, negative=QNEG,
             prompt=f"Draw the character from the reference pictures in {q}, delicate anime illustration. {KEEP}")
        for k, (q, _, _, _) in NEW.items()]
for k, (init, shot, style, scene) in OLD.items():
    jobs += redraw(f"p8_i2i_{k}", init, shot, style, scene)
for k, (_, shot, style, scene) in NEW.items():
    jobs += redraw(f"p8_new_{k}", f"@p8_q_{k}", shot, style, scene)
json.dump(jobs, open(os.path.join(HERE, "t8.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(jobs), "jobs")
