"""Queue text-to-image jobs on the local ComfyUI (AutoDL) and wait for them.
    python comfy_gen.py <jobs.json>      jobs: [{model, name, prompt, negative?, w, h, seed, steps?, cfg?}, ...]
Images land in ComfyUI/output/<name>_*.png. A job whose init is "@<name>" starts from the picture the job <name>
of the same file makes (Qwen keeps a character's design from reference pictures, Anima redraws it in its own hand).
A job with `upscale` enlarges its init picture with an upscale model first; model "upscale" only enlarges it.
How to run it: docs/comfyui.md."""
import json
import os
import shutil
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8188"
COMFY = "/root/autodl-tmp/ComfyUI"


def post(path, data):
    req = urllib.request.Request(URL + path, json.dumps(data).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())


def get(path):
    return json.loads(urllib.request.urlopen(URL + path).read())


def anima(j):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": j.get("unet", "anima-aesthetic-v1.1.safetensors"), "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_06b_base.safetensors", "type": "stable_diffusion", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": j["prompt"]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": j.get("negative", "")}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": j["w"], "height": j["h"], "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0],
                                                   "seed": j["seed"], "steps": j.get("steps", 30), "cfg": j.get("cfg", 4.0),
                                                   "sampler_name": j.get("sampler", "er_sde"), "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": j["name"]}},
    }


def qwen(j):
    g = qwen_t2i(j)
    refs = j.get("ref") or []
    if isinstance(refs, str):
        refs = [refs]
    for k, ref in enumerate(refs):   # reference pictures (in ComfyUI/input) the encoder looks at: same character, new picture
        g[str(10 + k)] = {"class_type": "LoadImage", "inputs": {"image": ref}}
        g["5"]["inputs"][f"images.image_{k + 1}"] = [str(10 + k), 0]
    if refs:
        g["5"]["inputs"]["vae"] = ["4", 0]
    return g


def qwen_t2i(j):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "QwenImage21Cache", "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_8b_w4a8.safetensors", "type": "qwen_image", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
        "5": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["3", 0], "prompt": j["prompt"], "negative_prompt": j.get("negative", ""),
                                                                "resolution": 1024}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": j["w"], "height": j["h"], "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "positive": ["5", 0], "negative": ["5", 1], "latent_image": ["6", 0],
                                                   "seed": j["seed"], "steps": j.get("steps", 25), "cfg": j.get("cfg", 1.0),
                                                   "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": j["name"]}},
    }


def enlarge(g, j, pixels):
    """The picture through the upscale model `upscale` (in models/upscale_models), then Lanczos to w x h. With
    crop "center" the picture keeps its aspect and loses a sliver at the sides."""
    g["22"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": j["upscale"]}}
    g["23"] = {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["22", 0], "image": pixels}}
    g["24"] = {"class_type": "ImageScale", "inputs": {"image": ["23", 0], "upscale_method": "lanczos", "width": j["w"], "height": j["h"],
                                                      "crop": j.get("crop", "disabled")}}
    return ["24", 0]


def upscale(j):
    """The init picture enlarged to w x h, nothing redrawn."""
    g = {"20": {"class_type": "LoadImage", "inputs": {"image": j["init"]}}}
    g["9"] = {"class_type": "SaveImage", "inputs": {"images": enlarge(g, j, ["20", 0]), "filename_prefix": j["name"]}}
    return g


def img2img(g, j, vae):
    """Start from a picture (in ComfyUI/input) instead of noise: the sampler keeps its layout and colours and
    redraws `denoise` of it. With `upscale`, the picture is enlarged to w x h first, so the redraw draws the detail
    of the bigger picture instead of stretching it. With `mask` (a picture in ComfyUI/input, white where to draw),
    only the white part is redrawn: what a layer hides, filled in."""
    g["20"] = {"class_type": "LoadImage", "inputs": {"image": j["init"]}}
    pixels = enlarge(g, j, ["20", 0]) if j.get("upscale") else ["20", 0]
    g["21"] = {"class_type": "VAEEncode", "inputs": {"pixels": pixels, "vae": vae}}
    g["7"]["inputs"]["latent_image"] = ["21", 0]
    if j.get("mask"):
        g["25"] = {"class_type": "LoadImageMask", "inputs": {"image": j["mask"], "channel": "red"}}
        g["26"] = {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["21", 0], "mask": ["25", 0]}}
        g["7"]["inputs"]["latent_image"] = ["26", 0]
    g["7"]["inputs"]["denoise"] = j.get("denoise", 0.55)
    g.pop("6", None)
    return g


def wait(pid):
    """The output files of a queued prompt, once it has run (none if it failed)."""
    while True:
        h = get(f"/history/{pid}")
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                for m in st.get("messages", []):
                    if m[0] == "execution_error":
                        print("  ", m[1].get("exception_message", "")[:600])
            return st.get("status_str"), [im["filename"] for o in h[pid].get("outputs", {}).values() for im in o.get("images", [])]
        time.sleep(2)


def main():
    jobs = json.load(open(sys.argv[1], encoding="utf-8"))
    queued, done = {}, {}

    def finish(name):
        if name not in done:
            done[name] = wait(queued[name])
            print(name, *done[name], flush=True)
        return done[name][1]

    for j in jobs:
        if str(j.get("init", "")).startswith("@"):   # an earlier job's picture: wait for it and hand it to input/
            outs = finish(j["init"][1:])
            if not outs:
                print("skip", j["name"], "no picture from", j["init"])
                continue
            shutil.copy(os.path.join(COMFY, "output", outs[0]), os.path.join(COMFY, "input", outs[0]))
            j["init"] = outs[0]
        graph = {"anima": anima, "qwen": qwen, "upscale": upscale}[j["model"]](j)
        if j.get("init") and j["model"] != "upscale":
            graph = img2img(graph, j, ["3", 0] if j["model"] == "anima" else ["4", 0])
        r = post("/prompt", {"prompt": graph})
        if r.get("node_errors"):
            print("node errors", j["name"], json.dumps(r["node_errors"])[:800])
        queued[j["name"]] = r["prompt_id"]
        print("queued", j["name"], r["prompt_id"], flush=True)
    for name in queued:
        finish(name)


if __name__ == "__main__":
    main()
