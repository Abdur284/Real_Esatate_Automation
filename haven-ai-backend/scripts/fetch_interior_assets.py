"""
Downloads the real-world assets used by the Interior Design object library.

Everything comes from Poly Haven (https://polyhaven.com), whose models and
textures are photoscanned / artist-made from real objects and released as
CC0 (public domain, free for commercial use, no attribution required).

  models   : every library item whose model is {"kind": "mesh", "source":
             "polyhaven", "asset": ...} (library_data/items/*.json), as glTF
             with PBR textures.
  textures : every material in library_data/pbr_materials.json (colour,
             OpenGL normal and roughness maps).

Quality levels:
  1k  standard asset -- interactive editing (always downloaded)
  2k  high-quality   -- final renders (python scripts/fetch_interior_assets.py --high)

Files go to INTERIOR_ASSET_DIR (default: assets/interior). Already
downloaded files are checked by MD5 and skipped.

    python scripts/fetch_interior_assets.py            # standard
    python scripts/fetch_interior_assets.py --high     # + high quality
"""
import argparse
import concurrent.futures as cf
import glob
import hashlib
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.core.config import settings  # noqa: E402

DATA = os.path.join(ROOT, "app", "services", "interior", "library_data")
API = "https://api.polyhaven.com"
UA = {"User-Agent": "HavenAI-FYP-interior/1.0"}
TEXTURE_MAPS = {"Diffuse": "diff", "nor_gl": "nor_gl", "Rough": "rough"}


def _get(url: str, tries: int = 4) -> bytes:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(url)


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch(url: str, dest: str, md5: str = "") -> bool:
    if os.path.isfile(dest) and (not md5 or _md5(dest) == md5):
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    data = _get(url)
    if md5 and hashlib.md5(data).hexdigest() != md5:
        raise RuntimeError(f"checksum mismatch for {url}")
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)
    return True


def mesh_assets() -> list:
    out = []
    for path in sorted(glob.glob(os.path.join(DATA, "items", "*.json"))):
        with open(path, encoding="utf-8") as f:
            for it in json.load(f):
                m = it.get("model") or {}
                if m.get("kind") == "mesh" and m.get("source") == "polyhaven":
                    out.append(m["asset"])
    return sorted(set(out))


def texture_assets() -> list:
    with open(os.path.join(DATA, "pbr_materials.json"), encoding="utf-8") as f:
        return sorted({v["asset"] for k, v in json.load(f).items() if not k.startswith("_") and v.get("source") == "polyhaven"})


def model_jobs(asset: str, res: str, base: str) -> list:
    files = json.loads(_get(f"{API}/files/{asset}"))
    g = files["gltf"][res]["gltf"]
    folder = os.path.join(base, "models", asset, res)
    jobs = [(g["url"], os.path.join(folder, f"{asset}.gltf"), g["md5"])]
    for rel, v in g["include"].items():
        jobs.append((v["url"], os.path.join(folder, rel), v["md5"]))
    info = json.loads(_get(f"{API}/info/{asset}"))
    meta = {"id": asset, "name": info["name"], "license": "CC0", "authors": list(info.get("authors", {})),
            "source": f"https://polyhaven.com/a/{asset}", "polycount": info.get("polycount"),
            "dimensions_mm": info.get("dimensions")}
    os.makedirs(os.path.join(base, "models", asset), exist_ok=True)
    with open(os.path.join(base, "models", asset, "info.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return jobs


def texture_jobs(asset: str, res: str, base: str) -> list:
    files = json.loads(_get(f"{API}/files/{asset}"))
    folder = os.path.join(base, "textures", asset, res)
    jobs = []
    for key, short in TEXTURE_MAPS.items():
        f = files[key][res]["jpg"]
        jobs.append((f["url"], os.path.join(folder, f"{short}.jpg"), f["md5"]))
    info = json.loads(_get(f"{API}/info/{asset}"))
    os.makedirs(os.path.join(base, "textures", asset), exist_ok=True)
    with open(os.path.join(base, "textures", asset, "info.json"), "w", encoding="utf-8") as f:
        json.dump({"id": asset, "name": info["name"], "license": "CC0",
                   "source": f"https://polyhaven.com/a/{asset}", "dimensions_mm": info.get("dimensions")}, f, indent=1)
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--high", action="store_true", help="also download the 2k high-quality assets")
    ap.add_argument("--dest", default=settings.INTERIOR_ASSET_DIR)
    args = ap.parse_args()
    base = os.path.abspath(args.dest)
    levels = ["1k", "2k"] if args.high else ["1k"]
    models, textures = mesh_assets(), texture_assets()
    print(f"{len(models)} models, {len(textures)} textures -> {base} ({', '.join(levels)})")

    jobs, failed = [], []
    with cf.ThreadPoolExecutor(6) as ex:
        plans = {ex.submit(model_jobs, a, r, base): a for a in models for r in levels}
        plans.update({ex.submit(texture_jobs, a, r, base): a for a in textures for r in levels})
        for fut in cf.as_completed(plans):
            try:
                jobs += fut.result()
            except Exception as e:           # keep going; report at the end
                failed.append(f"{plans[fut]}: {e}")
        done = 0
        for fut in cf.as_completed([ex.submit(_fetch, *j) for j in jobs]):
            try:
                done += bool(fut.result())
            except Exception as e:
                failed.append(str(e))
    print(f"{len(jobs)} files checked, {done} downloaded")
    if failed:
        print("FAILED:\n  " + "\n  ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
