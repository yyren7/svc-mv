"""Prompt pieces every v4 round shares (script_v4.md, section 2): who she is, the look, and the two lights.
Qwen-Image-2.1 runs at cfg 1, so a negative prompt does nothing; what must not appear is kept out by the wording."""

HER = ("an original anime girl of about seventeen: slender, pale skin, straight glossy black hair that falls just past "
       "her shoulders with blunt bangs; the hidden underlayer of her hair is dyed vivid rose red and shows only where "
       "the hair parts or moves. Calm dark grey-blue eyes with long lashes, a cool, composed, slightly melancholic face. "
       "She wears a white short-sleeved summer sailor school uniform with a black sailor collar edged by one thin white "
       "line, a long loose black ribbon tie, a black pleated knee-length skirt, white socks and black loafers. No "
       "accessories, no hair clips.")

LOOK1 = ("A breathtaking high-end anime key visual for a music video, refined and elegant rather than cute: delicate "
         "clean lineart, meticulous glossy hair with fine strands, luminous soft light with gentle bloom, cinematic "
         "composition, shallow depth of field, subtle paper grain. No text, no letters, no logo, no signature.")
# from round 2: eyes, shading and grading named, since round 1's 裏 pictures came out as flat pink wallpaper
LOOK = ("A breathtaking high-end anime key visual for a music video, refined and elegant rather than cute: delicate "
        "clean lineart, finely detailed eyes with layered highlights, meticulous glossy hair with fine strands catching "
        "the light, painterly soft shading with subtle colour gradients, luminous light with gentle bloom, cinematic "
        "composition and colour grading, shallow depth of field, subtle paper grain. No text, no letters, no logo, "
        "no signature.")

# 表: the face she shows. 裏: the side she hides.
OMOTE = ("Cool high-key morning light: white, silver and pale sky-blue tones, airy and clean, soft blue-grey shadows; "
         "the only warm colour in the picture is the hidden rose red in her hair.")
URA1 = ("Low-key night: deep black and ink-blue darkness lit by vivid fluorescent rose-red light from behind and below, "
        "glowing rim light on her hair and skin, glossy wet highlights, dramatic and beautiful.")
URA = ("Low-key night lighting in two colours: a strong vivid rose-red light from behind sets her hair and edges "
       "glowing, and a faint cold blue light from above keeps her face readable; deep velvety blacks, glossy "
       "highlights, cinematic contrast.")
INK = ("The ink behaves like real ink dropped into water: billowing translucent veils and thin silky curling filaments, "
       "layered and catching the light, not smoke and not fire.")

# from round 2 on, Qwen draws her from her design sheet (round 1's pick)
SHEET = "v4_sheet_201_00001_.png"
REF = ["ref_urao_sheet.png"]   # the whole sheet; its close-ups are startled and crying, so no face crop

KEEP = ("The girl from the reference picture: keep her face, her straight glossy black hair with blunt bangs and its "
        "hidden rose-red underlayer, her white short-sleeved sailor uniform with the black collar edged by one thin "
        "white line, the black neckerchief tie and the black pleated skirt exactly as in the reference picture.")
HIDDEN = "Her hair hangs calm and straight and the rose-red underlayer is hidden; only a thin line of it shows at the ends."
LOOSE = "Her hair flies loose and the rose-red underlayer is fully revealed, glowing."
WET = "Her wet hair clings to her cheeks and neck, and the rose-red underlayer shows in dark wet strands."
SPLIT = ("Half of her is lit by cold white-blue light from the left and half by vivid rose-red light from the right, "
         "deep shadow between.")

WIDE, TALL = (1664, 928), (928, 1664)


def qwen(name, seed, size, *parts, **extra):
    w, h = size
    return dict(model="qwen", name=name, seed=seed, w=w, h=h, prompt=" ".join(parts), **extra)
