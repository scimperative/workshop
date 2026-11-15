#!/usr/bin/env python3
"""Why is Mode B slower than Mode A? Two measurements, ~40 s total.

 1. Host cost per frame: JPEG decode + letterbox on one core.
 2. Does infer() let other Python threads run? A counter thread runs while infer() is called in a
    loop; compared with the counter's rate while the main thread just sleeps. Ratio ~1.0 means the
    GIL is released during infer (decode threads CAN overlap); ratio ~0 means it is held (they can't).
Also prints the FPS you'd expect if decode were perfectly serial with inference."""
import argparse
import os
import sys
import threading
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from hailo_backend import make_backend  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--backend", choices=["hailo", "sim"], default="hailo")
ap.add_argument("--hef", default=str(common.ROOT / common.load_config()["default_hef"]))
ap.add_argument("--images-dir", default=None)
ap.add_argument("--fpc", type=int, default=8)
a = ap.parse_args()

items = common.list_dataset(a.images_dir)[:100]
t0 = time.perf_counter()
for _, p in items:
    common.load_and_letterbox(p, 640)
dec_ms = (time.perf_counter() - t0) / len(items) * 1000
print(f"1. decode+letterbox: {dec_ms:.2f} ms/frame (single thread) -> max {1000/dec_ms:.0f} FPS per core")

be = make_backend(a.backend, a.hef, 1).open()
name = be.output_name()
batch = np.stack([common.load_and_letterbox(items[0][1], 640)[0]] * a.fpc)
be.infer(batch)

count = [0]; stop = threading.Event()
def spin():
    while not stop.is_set():
        count[0] += 1
th = threading.Thread(target=spin, daemon=True); th.start()
T = 8.0
count[0] = 0; t = time.perf_counter()
while time.perf_counter() - t < T:
    time.sleep(0.01)
base = count[0] / T
count[0] = 0; t = time.perf_counter(); n = 0
while time.perf_counter() - t < T:
    be.infer(batch); n += a.fpc
busy = count[0] / T
fps = n / T
stop.set(); be.close()
print(f"2. counter thread rate: idle {base:,.0f}/s, during infer() {busy:,.0f}/s -> ratio {busy/base:.2f}")
print(f"   model-only throughput here: {fps:.1f} FPS")
print(f"   predicted Mode B if decode were fully serial with infer: {1/(1/fps + dec_ms/1000):.1f} FPS")
