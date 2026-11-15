#!/usr/bin/env python3
"""Q5: classify a small vision transformer (MobileViT / DeiT-tiny) into pre-registered tiers T0-T3.

Compilation needs the Hailo Dataflow Compiler (x86 Linux, Hailo Developer Zone account) -- it
does NOT run on the Pi. Compile elsewhere, keep the compiler log, copy the HEF to the Pi:

  T0 compile failed          : python scripts/check_transformer.py --tier T0 --model deit_tiny --note "parser error: ..."
  HEF compiled, run on Pi    : python scripts/check_transformer.py --hef models/deit_tiny.hef --model deit_tiny
  T1 (host-CPU fallback for major layers) cannot be seen from the HEF; pass --tier T1 after reading
  the compile/profiler logs. Without --tier the script only suggests T2/T3 from measured FPS vs
  --t3-min-fps (pre-register that threshold!)."""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hef")
    ap.add_argument("--model", required=True)
    ap.add_argument("--tier", choices=["T0", "T1", "T2", "T3"])
    ap.add_argument("--note", default="")
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--t3-min-fps", type=float, default=100.0)
    a = ap.parse_args()
    res = {"model": a.model, "note": a.note, "hef": a.hef, "epoch": time.time()}
    if a.hef:
        from hailo_backend import HailoBackend

        res["hef_sha256"] = common.sha256_file(a.hef)
        res["parse_hef"] = subprocess.run(["hailortcli", "parse-hef", a.hef], capture_output=True, text=True).stdout
        be = HailoBackend(a.hef).open()
        x = np.random.randint(0, 255, (8, *be.input_shape), dtype=np.uint8)
        be.infer(x)
        n, t0, lat = 0, time.perf_counter(), []
        while time.perf_counter() - t0 < a.duration:
            s = time.perf_counter(); be.infer(x); lat.append((time.perf_counter() - s) * 1e3); n += 8
        res["fps"] = n / (time.perf_counter() - t0)
        res["call_latency_ms_p50"] = float(np.percentile(lat, 50))
        be.close()
        res["tier_suggested"] = "T3" if res["fps"] >= a.t3_min_fps else "T2"
        res["accuracy_note"] = "Throughput only; measure accuracy separately before claiming T3."
    elif not a.tier:
        sys.exit("Give --hef (compiled model) or --tier T0 (compile failure).")
    res["tier"] = a.tier or res.get("tier_suggested")
    res["tier_needs_human_confirmation"] = a.tier is None
    path = common.ROOT / "data" / "raw" / f"transformer_{a.model}.json"
    path.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "parse_hef"}, indent=2))
