# Characters

Each character has a folder here, separate from the cases (`cases/`). A case can draw on a character, but nothing
about a character belongs to a case.

The characters are unrelated to each other. Do not draw two of them together, and do not give them a shared
concept (one as 表 and another as 裏, for example).

| Folder | |
|---|---|
| [shunka/](shunka/) | 旬夏: Anima text-to-image works directly |
| [pheebie/](pheebie/) | Pheebie: Qwen-Image-2.1 from her reference sheets, then Anima redraws it |
| `kue/` | Only the downloaded album so far, in `ref/album/` |

A character's folder:

```
characters/<name>/
  README.md      her design, the prompt that draws her, the recipe, the picks
  jobs/          the ComfyUI jobs files, one per round (tN.json), and any script that wrote one
  ref/           official pictures; album/ is the downloaded image posts (not in git)
  art/           generated pictures, with _sheet_*.png contact sheets (not in git)
```

How to run a jobs file: [docs/comfyui.md](../docs/comfyui.md). The images in `art/` are named after their jobs,
so `art/s3_sing_71_00001_.png` comes from the job `s3_sing_71` in `jobs/t5.json`.
