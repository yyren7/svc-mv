"""Prompt pieces every v4 round shares (script_v4.md, section 2): who she is, the look, and the two lights.
Qwen-Image-2.1 runs at cfg 1, so a negative prompt does nothing; what must not appear is kept out by the wording."""

HER = ("an original anime girl of about seventeen: slender, pale skin, straight glossy black hair that falls just past "
       "her shoulders with blunt bangs; the hidden underlayer of her hair is dyed vivid rose red and shows only where "
       "the hair parts or moves. Calm dark grey-blue eyes with long lashes, a cool, composed, slightly melancholic face. "
       "She wears a white short-sleeved summer sailor school uniform with a black sailor collar edged by one thin white "
       "line, a long loose black ribbon tie, a black pleated knee-length skirt, white socks and black loafers. No "
       "accessories, no hair clips.")

LOOK = ("A breathtaking high-end anime key visual for a music video, refined and elegant rather than cute: delicate "
        "clean lineart, meticulous glossy hair with fine strands, luminous soft light with gentle bloom, cinematic "
        "composition, shallow depth of field, subtle paper grain. No text, no letters, no logo, no signature.")

# 表: the face she shows. 裏: the side she hides.
OMOTE = ("Cool high-key morning light: white, silver and pale sky-blue tones, airy and clean, soft blue-grey shadows; "
         "the only warm colour in the picture is the hidden rose red in her hair.")
URA = ("Low-key night: deep black and ink-blue darkness lit by vivid fluorescent rose-red light from behind and below, "
       "glowing rim light on her hair and skin, glossy wet highlights, dramatic and beautiful.")

WIDE, TALL = (1664, 928), (928, 1664)


def qwen(name, seed, size, *parts, **extra):
    w, h = size
    return dict(model="qwen", name=name, seed=seed, w=w, h=h, prompt=" ".join(parts), **extra)
