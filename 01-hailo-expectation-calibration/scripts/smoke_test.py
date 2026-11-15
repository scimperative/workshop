#!/usr/bin/env python3
"""No-hardware pipeline test (SIMULATED backend + fake smart plug). Takes ~1 minute.
Verifies loggers, both modes, per-second CSV, analysis, figures. Output is NOT a measurement:
it goes to data/raw/_smoke*/ (git-ignored) and is deleted afterwards."""
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import common  # noqa: E402

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"meters": [{"power": 7.5 + np.random.rand()}]}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_port}"

img_dir = os.path.join(ROOT, "data", "smoke", "imgs")
os.makedirs(img_dir, exist_ok=True)
for i in range(8):
    cv2.imwrite(os.path.join(img_dir, f"{i}.jpg"), np.random.randint(0, 255, (480, 640, 3), np.uint8))

out_root = os.path.join(ROOT, "data", "raw", "_smoke")
shutil.rmtree(out_root, ignore_errors=True)
for mode in ("model-only", "end-to-end"):
    for run in (1, 2):
        subprocess.check_call([sys.executable, os.path.join(HERE, "run_session.py"), "--mode", mode, "--run", str(run),
                               "--backend", "sim", "--idle-seconds", "5", "--duration", "15", "--fixed-duration",
                               "--images-dir", img_dir, "--out-root", out_root, "--power-source", "shelly-gen1", "--power-url", url])
# analyse reads data/raw/*/session.json; point it at the smoke dir via a temporary symlink layout
tmp_raw = os.path.join(ROOT, "data", "raw")
for d in os.listdir(out_root):
    os.rename(os.path.join(out_root, d), os.path.join(tmp_raw, "_smoke_" + d))
os.rmdir(out_root)
try:
    subprocess.check_call([sys.executable, os.path.join(HERE, "analyse.py"), "--allow-simulated"])
    assert os.listdir(os.path.join(ROOT, "results", "figures")), "no figures"
    print("\nSMOKE TEST PASSED")
finally:
    for d in os.listdir(tmp_raw):
        if d.startswith("_smoke_"):
            shutil.rmtree(os.path.join(tmp_raw, d))
    for f in os.listdir(os.path.join(ROOT, "results", "figures")):
        if f.startswith("_smoke_"):
            os.remove(os.path.join(ROOT, "results", "figures", f))
    shutil.rmtree(os.path.join(ROOT, "data", "smoke"), ignore_errors=True)
    for p in ("summary.md",):
        try: os.remove(os.path.join(ROOT, "results", "tables", p))
        except OSError: pass
