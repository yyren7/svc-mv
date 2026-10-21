"""小铃久绘's key visual for a one-picture song video, in three rounds.
    python characters/kue/jobs/kv.py      writes t1.json, t2.json, t3.json next to this file
Qwen-Image-2.1 looks at two pictures: picture 1 is her bust-up (her face, hair, ears and hair ornaments), picture 2
is Shunka's s3_sing_71 (the singing pose and the feel of the outfit). The picks are drawn again at 2496x1392 and
enlarged to 3840x2160."""
import json
import os

REF = ["ref_kue_face.png", "ref_shunka_sing.png"]
HER = ("The cat girl from picture 1: keep her face, her big blue eyes, her very long wine-red hair that turns pink "
       "towards the ends, her blunt bangs and ahoge, the small braided buns on both sides of her head, her pink cat ears "
       "with white fluff inside, the big light-blue ribbon bow on top of her head and the small white flower hairclip "
       "exactly as in picture 1. A long wine-red cat tail curls behind her.")
POSE = {
    1: ("She sings with her eyes closed and her mouth open into a microphone she holds in both hands below her chin, "
        "upper body, just like the girl in picture 2."),
    # round 1 gave half of them open eyes and a microphone stand
    2: ("She sings with her eyes gently closed and her mouth open into a cordless handheld microphone she holds in both "
        "hands just below her chin, upper body, just like the girl in picture 2. There is no microphone stand."),
}
WEAR = ("She wears the outfit of picture 2: an off-shoulder sheer white jacket with wide frilled see-through sleeves "
        "over a white dress with thin straps, a black lace choker with a white ribbon, and a light-blue ribbon bow with "
        "small white flowers tied into her hair.")
LOOK = ("Lavish, luminous, highly detailed anime key visual for a song video, delicate clean lineart, soft glow, rich "
        "colours, a wide 16:9 composition with the girl slightly right of centre and open space on the left.")
BG = {
    "stage": "She stands on a dreamy night concert stage: light-blue and soft pink spotlights beam down through haze, "
             "a sea of glowing light sticks far below, sparkles and white petals float in the air, translucent ribbons "
             "drift across the frame, shining bokeh everywhere.",
    "sweets": "She stands in a fantastical pastel dessert-shop wonderland at dusk: towering layered cakes, macarons and "
              "glass candy jars glowing like lanterns, cream-coloured shelves and lace curtains, strings of fairy lights, "
              "sparkles and petals floating in warm golden light.",
    "stars": "She stands on a hill of white flowers under a vast starry night sky with a huge pale moon: light-blue "
             "petals swirl around her in the wind, ribbons of starlight trail across the sky, glittering particles and "
             "soft blue-and-pink glow.",
}
NEG = {
    1: ("text, letters, title, logo, watermark, signature, name tag, label, two girls, extra person, extra fingers, "
        "deformed hands, extra arms, cropped head, blurry, low quality"),
}
NEG[2] = NEG[1] + ", microphone stand, pole, open eyes"

# Anima, tried as a redraw in round 2 (softer, and it loses the hair ornaments; not used)
TAGS = ("masterpiece, best quality, safe, newest, 1girl, solo, cat girl, cat ears, animal ear fluff, cat tail, very long "
        "hair, red hair, pink hair, gradient hair, blunt bangs, ahoge, braided bun, hair bow, light blue bow, white bow, "
        "hair flower, hairclip, black choker, lace choker, neck ribbon, off-shoulder, see-through sleeves, white jacket, "
        "wide sleeves, frilled sleeves, white dress, upper body, singing, holding microphone, closed eyes, open mouth, ")
STAGE_TAGS = "stage, stage lights, spotlight, concert, glowstick, audience, light rays, ribbon, night, "
ANIMA = (TAGS + STAGE_TAGS + "light particles, sparkle, petals, bokeh, detailed background, soft lighting, delicate "
         "lineart. A cat girl with very long wine-red hair fading to pink, pink cat ears with white fluff and a big "
         "light-blue bow on her head sings with her eyes closed in a sheer white off-shoulder frilled dress.")
ANIMA_NEG = "worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration, watermark, text, signature"

PICKS = {"stage": 103, "stars": 103, "sweets": 107}
UPSCALER = "4x-AnimeSharp.pth"


def prompt(bg, r):
    return " ".join([HER, POSE[r], WEAR, BG[bg], LOOK])


def draft(bg, seed, r):
    return dict(model="qwen", name=f"kue_q_{bg}_{seed}", ref=REF, w=1664, h=928, seed=seed, negative=NEG[r],
                prompt=prompt(bg, r))


def hires(bg, seed, init=None):
    """The draft enlarged to 2496x1392 and redrawn by Qwen at 0.3: sharper lines, same design."""
    return dict(model="qwen", name=f"kue_h_{bg}_{seed}_q30", init=init or f"kue_q_{bg}_{seed}_00001_.png",
                upscale=UPSCALER, w=2496, h=1392, denoise=0.3, seed=81, ref=REF, negative=NEG[2], prompt=prompt(bg, 2))


t1 = [draft(bg, seed, 1) for bg in BG for seed in (101, 103)]
t2 = [draft(bg, seed, 2) for bg in BG for seed in (107, 109)]
t2 += [dict(model="anima", name=f"kue_a_stage_103_{d}", init="kue_q_stage_103_00001_.png", denoise=d / 100, seed=81,
            w=1664, h=928, negative=ANIMA_NEG, prompt=ANIMA) for d in (35, 45)]
t2 += [hires("stage", 103),
       dict(model="anima", name="kue_h_stage_103_a35", init="kue_q_stage_103_00001_.png", upscale=UPSCALER,
            w=2496, h=1392, denoise=0.35, seed=81, negative=ANIMA_NEG, prompt=ANIMA)]
t3 = [hires(bg, seed) for bg, seed in PICKS.items() if bg != "stage"]          # stage_103 was drawn in t2
t3 += [dict(model="upscale", name=f"kue_pv_{bg}_{seed}_4k",
            init="kue_h_stage_103_q30_00001_.png" if bg == "stage" else f"@kue_h_{bg}_{seed}_q30",
            upscale=UPSCALER, w=3840, h=2160, crop="center") for bg, seed in PICKS.items()]

here = os.path.dirname(os.path.abspath(__file__))
for name, jobs in (("t1", t1), ("t2", t2), ("t3", t3)):
    json.dump(jobs, open(os.path.join(here, f"{name}.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print(name, len(jobs), "jobs")
