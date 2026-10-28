"""Prompt pieces for the v5 pictures (script_v5.md): she is painted INTO the world's own plates
(cases/uraomote/scripts/v5_plates.py renders them), so each prompt names the place, the light the plate shows,
and her pose; who she is and the look come from v4_prompts. The v4 pictures were painted for other places (a white
room, a corridor, a hall) with their own light, and stood in the sea like stickers."""
from v4_prompts import HIDDEN, LOOK, LOOSE, REF, SHEET, TALL, WET, WIDE, qwen  # noqa: F401

KEEP = ("The girl is the one in the first reference picture, her design sheet: keep her face, her straight glossy black "
        "hair with blunt bangs and its hidden rose-red underlayer, her white short-sleeved sailor uniform with the black "
        "collar edged by one thin white line, the black neckerchief tie, the black pleated knee-length skirt, white "
        "socks and black loafers exactly as there.")
PLACE = ("The place is the one the picture already shows: an endless still sea like a mirror under a painted sky, and "
         "one old plaster wall standing alone in the water with a tall steel-framed window; nothing else exists there.")
# where to paint her: with the plate itself as the second reference, the model sees the grey mannequin
INTO = ("Paint her into this picture in the empty space left for her, at the full height of that space, her feet on "
        "the water at its bottom, standing on the water's surface. Leave everything around her exactly as it is.")
INTO_SEEN = ("Paint her into this picture exactly where the grey mannequin stands in the second reference picture, "
             "replacing it at its size, her feet where its feet are, on the water's surface. Leave everything around "
             "her exactly as it is.")
# the light of each plate, as the plate shows it
DAWN = ("Dawn. The low sun is behind the wall, so she is lit from behind: a thin warm rim of sunlight runs along her "
        "hair, her shoulders and the edges of her uniform, and her front is in soft cool blue-grey shadow, filled only "
        "by the pale sky and the light bouncing up from the water. No light falls on her face from the front; the "
        "window behind her is bright with the dawn sky.")
DUSK = ("Nightfall. The sky has gone dark blue-grey; a soft cold blue light from in front of her and a little to the "
        "left reads her face and uniform, a faint rose glow from behind her right shoulder edges her hair; deep blacks.")
RAIN = ("A rainy night. The only light is the window's rose-red glow in front of her, so the side of her toward us is "
        "dark, nearly a silhouette, with a rim of rose along her outline and wet highlights in her hair; the sky and the "
        "sea are deep blue night. The rain itself is not drawn.")
NIGHT = ("Night, the world turned inside out: a vivid rose-red light from low behind her sets her hair and her edges "
         "glowing, a faint cold blue light from above keeps her face readable; deep velvety blacks, glossy highlights.")
TWIN = ("Half of her is lit by cold white-blue light from the left and half by vivid rose-red light from the right, "
        "deep shadow between; torn pieces of white paper whirl round her.")
# the second pass over a picture the camera will enter: one painting, not a render with a drawing on it
PAINT = ("Redraw this whole picture as one hand-painted anime key visual: the plaster wall, the steel window frame, the "
         "sea and the sky painted in the same refined illustration style as she is, with delicate clean lineart, "
         "painterly soft shading and luminous light; the composition, the horizon, the window, the wall and her pose "
         "stay exactly where they are. No text, no letters, no logo.")

# pose, light, hair, and the plate each picture is painted on
POSES = {
    "kv": ("Full body. She stands on the still water a few steps before the wall's tall window with her back to us, "
           "and turns her head over her shoulder to look back at the viewer with a calm, composed, faintly melancholic "
           "gaze, lips closed, arms relaxed at her sides, loafers on the water.", DAWN, HIDDEN),
    "q1s": ("Full body, facing the viewer squarely, standing still on the water with her arms at her sides, chin "
            "level, a calm, composed, unreadable face looking straight into the lens.", DUSK, HIDDEN),
    "w1": ("Full body seen straight from behind: she stands still on the water facing the glowing window, arms by her "
           "sides, her wet hair clinging to her neck and back, a crisp clean silhouette.", RAIN, WET),
    "r0": ("Full body: she runs straight toward the viewer over the water, mid-stride, one knee high, hair and "
           "neckerchief streaming behind her, skirt flaring, a splash of water at her loafers, wet determined eyes.",
           NIGHT, LOOSE),
    "f1": ("She leaps high in mid-air with her arms open wide and her head tilted back, eyes closed in release, hair "
           "and skirt flying.", TWIN, LOOSE),
    "a1": ("Medium shot. She stands at the window with her back three-quarters to us so her profile shows, her "
           "fingertips resting on the cold glass, looking out at the pale sky; the glass of water stands on the sill "
           "beside her hand.", DAWN, HIDDEN),
    "a2": ("From the waist up. She walks away from us along the wall over the water and glances back over her shoulder "
           "at the viewer with the smallest composed smile, her skirt and neckerchief swaying.", DAWN, HIDDEN),
    "a3": ("From the waist up, seen from behind her left shoulder. She ties her black neckerchief before the window, "
           "and her face shows faintly reflected in the old glass, composed, eyes lowered to the knot.", DAWN, HIDDEN),
    "a4": ("Close-up. Her fingertips touch the cold window pane, misted with dawn condensation, leaving clear marks; "
           "her face is just behind her hand at the side of the frame, softly out of focus, eyes looking far out "
           "through the glass.", DAWN, HIDDEN),
    "a5": ("Close-up of her face and shoulders. She leans back against the window facing us, eyes gently closed, long "
           "lashes, lips relaxed, the dawn sky in the glass behind her head.", DAWN, HIDDEN),
    "u1": ("Seen from straight above. She lies on her back on the black night water, her face turned up to the "
           "camera, wide sleepless eyes, the first hint of a crooked smile; her hair fans out around her head on the "
           "water like spilled ink, the rose-red underlayer spreading through it; faint rings in the water.",
           NIGHT, LOOSE),
}
FIGURES = ("kv", "q1s", "w1", "r0", "f1")          # cut out afterwards (scripts/figures.py)
ENTERED = ("a1", "a2", "a3", "a4", "a5", "u1", "f1")   # the camera enters them: a second, painted pass
