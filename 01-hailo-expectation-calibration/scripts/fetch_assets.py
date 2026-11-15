#!/usr/bin/env python3
"""Fetch / verify the fixed assets.

  python scripts/fetch_assets.py hef        # try config.json hef_candidates -> models/yolov8n_h8l.hef
  python scripts/fetch_assets.py coco       # deterministic 500-image COCO val2017 subset + manifest hash
  python scripts/fetch_assets.py verify     # re-hash images against data/coco/MANIFEST.sha256

Commit data/coco/subset_manifest.json, instances_val2017_subset500.json and MANIFEST.sha256
BEFORE running any benchmark (they are the pre-registered dataset identity). Images stay untracked.
"""
import argparse
import hashlib
import json
import os
import random
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

COCO = common.ROOT / "data" / "coco"


def download(url, dest, quiet=False):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "scimperative-w01"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            got += len(b)
            if total and not quiet:
                print(f"\r  {got/1e6:.0f}/{total/1e6:.0f} MB", end="", flush=True)
    if not quiet:
        print()
    tmp.rename(dest)


def cmd_hef(cfg):
    dest = common.ROOT / cfg["default_hef"]
    if dest.exists():
        print(f"already present: {dest}  sha256={common.sha256_file(dest)}")
        return
    for url in cfg["hef_candidates"]:
        try:
            print("trying", url)
            download(url, dest)
            print(f"saved {dest}\nsha256={common.sha256_file(dest)}")
            print("VERIFY it targets the 8L:  hailortcli parse-hef", dest)
            return
        except Exception as e:
            print("  failed:", e)
    sys.exit("No candidate URL worked. Get a Hailo-8L YOLOv8n HEF (Hailo Model Zoo, or compile with the\n"
             f"Dataflow Compiler on x86) and copy it to {dest}. Any HEF works with --hef.")


def cmd_coco(cfg):
    tmp = COCO / "_tmp"
    zpath = tmp / "annotations_trainval2017.zip"
    ann_full = tmp / "instances_val2017.json"
    if not ann_full.exists():
        if not zpath.exists():
            print("downloading COCO annotations (~250 MB, one-off)...")
            download(cfg["coco_annotations_zip"], zpath)
        with zipfile.ZipFile(zpath) as z:
            with z.open("annotations/instances_val2017.json") as src, open(ann_full, "wb") as dst:
                dst.write(src.read())
    ann = json.loads(ann_full.read_text())
    ids = sorted(im["id"] for im in ann["images"])
    rng = random.Random(cfg["dataset_seed"])
    pick = set(rng.sample(ids, cfg["dataset_size"]))
    images = sorted((im for im in ann["images"] if im["id"] in pick), key=lambda im: im["id"])
    sub = {
        "info": ann.get("info", {}), "licenses": ann.get("licenses", []),
        "images": images, "categories": ann["categories"],
        "annotations": [a for a in ann["annotations"] if a["image_id"] in pick],
    }
    (COCO / "instances_val2017_subset500.json").write_text(json.dumps(sub))
    d = common.dataset_dir()
    d.mkdir(parents=True, exist_ok=True)

    def get(im):
        p = d / im["file_name"]
        if not p.exists():
            for attempt in range(4):
                try:
                    download(cfg["coco_image_base"] + im["file_name"], p, quiet=True)
                    break
                except Exception:
                    if attempt == 3:
                        raise
        return im["file_name"], common.sha256_file(p)

    print(f"downloading {len(images)} images...")
    with ThreadPoolExecutor(8) as ex:
        hashes = dict(ex.map(get, images))
    manifest = {"seed": cfg["dataset_seed"], "source": cfg["dataset_source"],
                "images": [{"id": im["id"], "file_name": im["file_name"], "sha256": hashes[im["file_name"]]} for im in images]}
    (COCO / "subset_manifest.json").write_text(json.dumps(manifest, indent=1))
    h = hashlib.sha256("".join(f"{m['file_name']} {m['sha256']}\n" for m in manifest["images"]).encode()).hexdigest()
    (COCO / "MANIFEST.sha256").write_text(h + "\n")
    print(f"dataset sha256 = {h}\nCommit: data/coco/subset_manifest.json, instances_val2017_subset500.json, MANIFEST.sha256")


def cmd_verify(cfg):
    m = json.loads((COCO / "subset_manifest.json").read_text())
    bad = 0
    for it in m["images"]:
        p = common.dataset_dir() / it["file_name"]
        if not p.exists() or common.sha256_file(p) != it["sha256"]:
            print("MISMATCH", it["file_name"])
            bad += 1
    h = hashlib.sha256("".join(f"{i['file_name']} {i['sha256']}\n" for i in m["images"]).encode()).hexdigest()
    committed = (COCO / "MANIFEST.sha256").read_text().strip()
    print("images ok" if not bad else f"{bad} bad images", "| manifest hash", "OK" if h == committed else "DOES NOT MATCH committed hash")
    sys.exit(1 if bad or h != committed else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["hef", "coco", "verify"])
    a = ap.parse_args()
    {"hef": cmd_hef, "coco": cmd_coco, "verify": cmd_verify}[a.what](common.load_config())
