# Image models: quality and licences

Checked 2026-10-23: the two models in [comfyui.md](comfyui.md) against Krea 2, the strongest open-weights
rival, and the licences of the other models a picture passes through. Krea 2 has not been run here; its quality notes come from the leaderboard and other people's tests.
Licences change, so read the licence file again before relying on this, and get a written grant before anything
commercial. This is not legal advice.

## Quality

| | Qwen-Image-2.1 | Krea 2 | Anima |
|---|---|---|---|
| Artificial Analysis T2I, 2026-10-13 | 1038 Elo (1029–1047), first among open weights | Large 1027, Medium Turbo 1022, Medium 1014 | not on the board, which has no anime category |
| Open weights | the model on the board, 7B | only Raw (the base, for training) and Turbo (8 steps), 12B; Large and Medium are a paid API, and the open two have no row of their own | 2B |
| Good at | reference pictures, masks, img2img, transparency; flat, symbolic content | looks; the structure of 3D objects and photos; following a long sentence | anime flat colour and line, cute characters, fingers, steady composition |
| Takes | text, reference pictures, `init`, `mask` | text only (the open release has no editing) | Danbooru tags and a sentence, `init` |

- The gap between Qwen and Krea 2 Large is inside the intervals; don't read it as a ranking. In one Japanese test
  of 28 prompts with one seed each, Krea 2 won 10, Qwen 7, and 9 were even.
- The best Krea 2 pictures people show mostly come from Large, which is not open.
- Anime, from one blogger's test of Krea 2 Turbo (fp8, no LoRA) against Anima: Krea 2 kept closest to the prompt
  and looked cinematic; Anima had more anime flair and kept fingers and composition right more often. With a
  character LoRA, Krea 2 drew more detail in the eyes and hair.

For this repo: open Krea 2 can't take reference sheets or a mask, so it can't do Qwen's jobs (an outfit that has
to match an official design, `retouch.py`, the fills in `layers.py`). In Anima's place it would trade flat colour
for a cinematic look, which may suit the riso separation less. Untested; the fp8 Turbo fits the 4090D, so draw a
side-by-side from the same jobs before switching anything.

## Licences

| | Qwen-Image-2.1 | Anima | Krea 2 (Raw, Turbo) |
|---|---|---|---|
| Licence | Qwen Research License (released 2026-09-20) | CircleStone Labs Non-Commercial License v1.2 | Krea 2 Community License (2026-06-22) |
| The model | research and evaluation only: "You shall not use the Materials for any commercial purpose" | non-commercial only; revenue-generating activity is excluded | commercial use while the company's revenue stays under $1M a year (trailing twelve months, affiliates included) |
| The pictures | no clause on outputs, so drawing pictures for a commercial release is commercial use of the model | "You may use Outputs for any purpose (including for commercial purposes)" (2(e)) | "You own all Outputs you generate"; commercial use under the same $1M limit |
| Other terms | "Built with Qwen" when its outputs train a model you share; Chinese law, Hangzhou courts | a derivative of Cosmos-Predict2-2B, whose NVIDIA Open Model License allows commercial use | a content filter is required when self-hosting; derived models' names start with "Krea"; Delaware law |
| Commercial licence | email model-business@notice.qwencloud.com; no public price | ask CircleStone Labs (see the model card); people report slow replies | above $1M, an enterprise licence from opensource@krea.ai |

- From strictest to loosest: Qwen, Anima, Krea 2.
- Qwen's "non-commercial" is narrower than the word: research or evaluation only (1(i)). Read strictly, even an
  unpaid public video is neither, and the licence allows no other use.
- Anima's licence is built like FLUX.1 [dev]'s. The outputs clause allows commercial use, but the definition of
  non-commercial excludes revenue-generating activity, so running Anima for a paid job is unclear. Get a grant from
  CircleStone Labs to be sure.
- Early reports of a 50-seat limit on Krea 2 are not in the licence text; the only limit is the revenue.

The other models a picture passes through, by their model cards:

| Model | What it does here | Licence |
|---|---|---|
| Depth Anything V2 Large | depth for the layers (`onepic_prep.py`, `layers.py`) | CC BY-NC 4.0; the Small model is Apache 2.0 |
| 4x-AnimeSharp, 2x-AnimeSharpV4 RCAN (Kim2091) | enlarging pictures and layers | CC BY-NC-SA 4.0 |
| anime-seg (skytnt, ISNet) | cutting the character out | Apache 2.0 |
| big-lama | filling in behind the character (`onepic_prep.py`) | Apache 2.0 (the LaMa repo) |

## Before a commercial release

- Pictures that went Qwen → Anima (`init: "@<qwen job>"`), and anything retouched or layered with Qwen
  (`retouch.py`, `layers.py`), start from Qwen outputs, so Qwen's licence covers them: draw them again another way,
  or get a Qwen licence.
- Pictures Anima drew from text alone fall under its outputs clause, with the doubt above.
- Krea 2 is the clean way while revenue stays under $1M, but it can't use the reference sheets.
- No model licence covers the characters themselves: a character drawn to an official design also needs its owner's
  permission.
- Depth Anything V2 Large and the AnimeSharp upscalers are non-commercial too: use Depth Anything V2 Small and an
  upscaler whose licence allows it.

## Sources

- Licence files: [Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE),
  [Anima](https://huggingface.co/circlestone-labs/Anima/blob/main/LICENSE.md),
  [Krea 2 Turbo model card](https://huggingface.co/krea/Krea-2-Turbo) (the licence PDF is behind an agreement);
  a [clause-by-clause guide to the Krea 2 licence](https://krea2ai.com/blog/krea-2-license-commercial-use)
- Leaderboard: [Artificial Analysis T2I](https://artificialanalysis.ai/image/leaderboard/text-to-image),
  [Qwen-Image 2.1 vs Krea 2 (OrcaRouter)](https://www.orcarouter.ai/blog/qwen-image-2-1-vs-krea-2)
- Anime test: [Krea2 vs Anima vs SDXL (かみもと, note)](https://note.com/sepiablue/n/nffea54ceef6b)
- Commercial contact for Anima: [Hugging Face discussion #215](https://huggingface.co/circlestone-labs/Anima/discussions/215)
