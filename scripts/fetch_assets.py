"""Fetch the CC0 assets the sets use from Poly Haven (textures, HDRIs, models with their textures) into
assets/polyhaven/. The manifest below is the only list; running the script again downloads only what is
missing, so a fresh clone gets the same files.

    .venv/Scripts/python scripts/fetch_assets.py [--res 2k] [--only textures|hdris|models|objaverse|thirdparty] [ids ...]

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

# CC BY models from Sketchfab, fetched from the Objaverse copy on Hugging Face (no Sketchfab login needed).
# Each keeps its creator's licence: attribution is in docs/CREDITS.md, and recolours count as changes.
OBJAVERSE = {
    "kiha32": dict(uid="95c5d6515ff04092987d698ab2c8442a", title="国鉄キハ32形気動車 KIHA 32 Diesel", author="own.guest"),
    "nazo_no_eki": dict(uid="6cbd6ce6354f44a4b6517e8176d8741b", title="Nazo no eki (Mystery Station)", author="Thomas Nguyen"),
    "jp_payphone86": dict(uid="50f9b9982885403396f46d5f46c7b4be", title="Japanese Payphone 86'", author="Yevhen Avramenko"),
    "old_green_payphone": dict(uid="ad06f3ec91a24943ad4a38dd70413cda", title="Old Green Payphone", author="Yevhen Avramenko"),
    "umbrella": dict(uid="ae0abff9bb9d4bb3b2ef634b8bc539d5", title="Umbrella", author="Tatiana Sumarokova"),
    "parasol_clear": dict(uid="c97432ffbe97469694f2ee4364aabf30", title="Parasol Clear", author="Sungebob"),
    "jp_vending": dict(uid="4768555100004c75b5167d1aa02c683b", title="Japanese Vending Machine", author="filadog"),
    "red_vending": dict(uid="a8a6874f62da478f8572554959d3c62e", title="Red Japanese Vending Machine", author="Watanuki_San"),
    "chochin": dict(uid="20bcc5d20f2847f88aef3a267275d16c", title="Chinese / Japanese paper lantern chochin", author="DeepDown"),
    "umbrella_alsyd": dict(uid="ef0d9c9ce02345479b934720fe54ba2d", title="Umbrella", author="al_syd"),
    "umbrella_lizzy": dict(uid="67bc029c98454971a213c526bc1fbec0", title="Umbrella", author="Lizzy Koopa"),
}
# other files with their own licences
THIRDPARTY = {
    "khronos_shoe": dict(url="https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/"
                             "MaterialsVariantsShoe/glTF-Binary/MaterialsVariantsShoe.glb",
                         path="khronos_shoe/MaterialsVariantsShoe.glb",
                         title="MaterialsVariantsShoe (glTF sample)", author="Shopify", license="CC BY 4.0"),
}
HF = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
THIRD = os.path.join(ROOT, "assets", "thirdparty")

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # the Windows proxy here is dead
opener.addheaders = [("User-Agent", "svc-mv-fetch/1.0")]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_no_redirect = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def resolve(url, hops=8):
    """Follow redirects by hand (this Python's urllib gives up on 308, which the HF mirror sends) and
    return (final url, size, accepts ranges)."""
    import urllib.error
    import urllib.parse
    for _ in range(hops):
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "svc-mv-fetch/1.0"})
        try:
            with _no_redirect.open(req, timeout=60) as r:
                return url, int(r.headers.get("Content-Length", "0")), r.headers.get("Accept-Ranges", "") == "bytes"
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location")
            if e.code in (301, 302, 303, 307, 308) and loc:
                url = urllib.parse.urljoin(url, loc)
                continue
            raise
    raise RuntimeError(f"too many redirects for {url}")


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


def plan_objaverse(ids):
    """GLBs by Sketchfab uid from the Objaverse index (cached next to the files)."""
    import gzip
    index = os.path.join(THIRD, "objaverse", "object-paths.json.gz")
    if not os.path.exists(index):
        final, size, _ = resolve(f"{HF}/datasets/allenai/objaverse/resolve/main/object-paths.json.gz")
        download(final, index, size)
    paths = json.load(gzip.open(index, "rt", encoding="utf-8"))
    out = []
    for key, info in OBJAVERSE.items():
        if ids and key not in ids:
            continue
        rel = paths.get(info["uid"])
        if rel is None:
            print(f"!! objaverse/{key}: {info['uid']} is not in Objaverse 1.0", file=sys.stderr)
            continue
        out.append((f"{HF}/datasets/allenai/objaverse/resolve/main/{rel}", os.path.join(THIRD, "objaverse", f"{key}.glb"), None))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="2k")
    ap.add_argument("--model-res", default="1k")
    ap.add_argument("--only", choices=("textures", "hdris", "models", "objaverse", "thirdparty"))
    ap.add_argument("ids", nargs="*")
    a = ap.parse_args()
    jobs = []
    if not a.only or a.only == "objaverse":
        jobs.extend(plan_objaverse(a.ids))
    if not a.only or a.only == "thirdparty":
        for key, info in THIRDPARTY.items():
            if not a.ids or key in a.ids:
                jobs.append((info["url"], os.path.join(THIRD, info["path"]), None))
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
    sized = []
    for url, path, size in jobs:
        if size is None:
            try:
                url, size, _ = resolve(url)
            except Exception as e:   # noqa: BLE001
                print(f"!! HEAD {url}: {e}", file=sys.stderr)
                continue
        sized.append((url, path, size))
    jobs = sized
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
