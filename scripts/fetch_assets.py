"""Fetch the CC0 assets the sets use from Poly Haven (textures, HDRIs, models with their textures) into
assets/polyhaven/. The manifest below is the only list; running the script again downloads only what is
missing, so a fresh clone gets the same files.

    .venv/Scripts/python scripts/fetch_assets.py [--res 2k] [--only textures|hdris|models] [ids ...]

Files are pulled in parallel range requests: a single connection to dl.polyhaven.org runs at ~100 kB/s
from here, eight of them at close to 1 MB/s. All Poly Haven assets are CC0 (https://polyhaven.com/license).
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "assets", "polyhaven")
API = "https://api.polyhaven.com"

MANIFEST = {
    # surface sets: diffuse / roughness / normal / displacement (+ ao where it exists), JPG
    "textures": [
        # S5 platform
        "concrete_floor_01", "brushed_concrete", "gravel_floor", "rusty_metal_02", "rusty_painted_metal",
        "rusty_corrugated_iron", "brown_planks_03", "metal_plate",
        # S4 alley
        "asphalt_02", "brick_wall_001", "dark_wooden_planks", "corrugated_iron_02", "peeling_painted_wall",
        # S1 / S3 / S6 rooms
        "painted_plaster_wall", "wood_floor_worn", "wood_floor", "brown_planks_05", "grey_plaster",
        # S2 lab bench
        "dirty_tiles",
        # fabric for the bedding and the bag
        "denim_fabric_03", "fabric_pattern_07", "cotton_jersey", "rough_linen", "crepe_satin", "leather_white",
        # rooms: wallpaper, floors, the desk
        "decrepit_wallpaper", "oak_veneer_01", "laminate_floor", "plywood", "painted_concrete", "dirty_carpet",
        "book_pattern",
    ],
    "hdris": [
        "belfast_sunset_puresky", "bloem_train_track_clear", "industrial_sunset",   # S5 omote
        "dresden_station_night",                                                   # S5 ura
        "cobblestone_street_night",                                                # S4
        "kloofendal_overcast_puresky",                                             # soft fill for the rooms
    ],
    "models": [
        "old_bed_frame", "alarm_clock_01", "korean_public_payphone_01", "painted_wooden_bench",
        "modular_chainlink_fence", "modular_electricity_poles", "street_lamp_01", "utility_box_01",
        "power_box_01", "binder_notebook", "postcard_set_01", "wooden_crate_01", "concrete_road_barrier",
        "modular_street_seating", "cardboard_box_01",
        # rooms
        "throw_pillows_01", "desk_lamp_arm_01", "hanging_picture_frame_01", "standing_picture_frame_01",
        "vintage_day_bed", "painted_wooden_chair_01", "small_wooden_table_01", "side_table_01", "wall_clock",
        # the alley
        "metal_trash_can", "trashbag", "street_lamp_02", "wooden_crate_02", "plastic_crate_01",
    ],
}

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # the Windows proxy here is dead
opener.addheaders = [("User-Agent", "svc-mv-fetch/1.0")]


def get_json(url, tries=4):
    for k in range(tries):
        try:
            with opener.open(url, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:   # noqa: BLE001
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))


def head_size(url):
    req = urllib.request.Request(url, method="HEAD")
    with opener.open(req, timeout=60) as r:
        return int(r.headers.get("Content-Length", "0")), r.headers.get("Accept-Ranges", "") == "bytes"


def fetch_range(url, start, end, tries=5):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
            with opener.open(req, timeout=120) as r:
                data = r.read()
            if len(data) == end - start + 1:
                return data
        except Exception:   # noqa: BLE001
            pass
        time.sleep(1.5 * (k + 1))
    raise RuntimeError(f"range {start}-{end} of {url} failed")


def download(url, path, size=None, parts=8):
    """Segmented download to path (skipped when the file is already complete)."""
    if size is None:
        size, ranged = head_size(url)
    else:
        ranged = True
    if os.path.exists(path) and os.path.getsize(path) == size and size > 0:
        return "kept"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    if size < 1_500_000 or not ranged:
        with opener.open(url, timeout=300) as r, open(tmp, "wb") as f:
            f.write(r.read())
    else:
        n = parts
        bounds = [(i * size // n, (i + 1) * size // n - 1) for i in range(n)]
        with cf.ThreadPoolExecutor(n) as ex:
            chunks = list(ex.map(lambda b: fetch_range(url, *b), bounds))
        with open(tmp, "wb") as f:
            for c in chunks:
                f.write(c)
    if os.path.getsize(tmp) != size:
        raise RuntimeError(f"{path}: got {os.path.getsize(tmp)} of {size} bytes")
    os.replace(tmp, path)
    return "fetched"


def plan_texture(aid, res):
    files = get_json(f"{API}/files/{aid}")
    out = []
    for key in ("Diffuse", "Rough", "nor_gl", "Displacement", "AO", "Metal", "Alpha"):
        entry = files.get(key, {}).get(res, {})
        f = entry.get("jpg") or entry.get("png")
        if f:
            ext = "jpg" if entry.get("jpg") else "png"
            out.append((f["url"], os.path.join(DEST, "textures", aid, f"{aid}_{key.lower()}_{res}.{ext}"), f["size"]))
    return out


def plan_hdri(aid, res):
    files = get_json(f"{API}/files/{aid}")
    f = files["hdri"][res]["hdr"]
    return [(f["url"], os.path.join(DEST, "hdris", f"{aid}_{res}.hdr"), f["size"])]


def plan_model(aid, res):
    files = get_json(f"{API}/files/{aid}")
    blend = files["blend"][res]["blend"]
    folder = os.path.join(DEST, "models", aid)
    out = [(blend["url"], os.path.join(folder, f"{aid}.blend"), blend["size"])]
    for rel, inc in blend.get("include", {}).items():
        out.append((inc["url"], os.path.join(folder, *rel.split("/")), inc["size"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="2k")
    ap.add_argument("--model-res", default="1k")
    ap.add_argument("--only", choices=("textures", "hdris", "models"))
    ap.add_argument("ids", nargs="*")
    a = ap.parse_args()
    jobs = []
    for kind, plan in (("textures", plan_texture), ("hdris", plan_hdri), ("models", plan_model)):
        if a.only and a.only != kind:
            continue
        for aid in MANIFEST[kind]:
            if a.ids and aid not in a.ids:
                continue
            res = a.model_res if kind == "models" else a.res
            try:
                items = plan(aid, res)
            except Exception as e:   # noqa: BLE001
                print(f"!! {kind}/{aid}: {e}", file=sys.stderr)
                continue
            jobs.extend(items)
    total = sum(s for _, _, s in jobs)
    print(f"{len(jobs)} files, {total / 1e6:.0f} MB")
    done = 0
    t0 = time.time()
    with cf.ThreadPoolExecutor(3) as ex:   # three files at a time, each in eight ranges
        futs = {ex.submit(download, url, path, size): (path, size) for url, path, size in jobs}
        for fut in cf.as_completed(futs):
            path, size = futs[fut]
            try:
                status = fut.result()
            except Exception as e:   # noqa: BLE001
                status = f"FAILED {e}"
            done += size
            print(f"[{done / 1e6:6.0f}/{total / 1e6:.0f} MB {time.time() - t0:5.0f}s] {status:8s} {os.path.relpath(path, DEST)}")
    print("done")


if __name__ == "__main__":
    main()
