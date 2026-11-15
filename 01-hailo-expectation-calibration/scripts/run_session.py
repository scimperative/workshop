#!/usr/bin/env python3
"""One full measured session: env capture -> idle baseline -> sustained run, with loggers.

Example (Mode B, run 1, Gen3):
  python scripts/run_session.py --mode end-to-end --run 1 --ambient-c 21.5 \
      --power-source shelly-gen1 --power-url http://192.168.1.50

Output: data/raw/<UTC>_<mode>_<tag>_run<N>/{session.json,env.txt,thermal.csv,power.csv,
        bench_summary.json,bench_seconds.csv,latencies.npz}
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

HERE = Path(__file__).resolve().parent


def stop_proc(p):
    if p and p.poll() is None:
        p.send_signal(signal.SIGINT)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()


def main():
    cfg = common.load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["model-only", "end-to-end"], required=True)
    ap.add_argument("--run", type=int, required=True, help="repetition number (>=3 per mode)")
    ap.add_argument("--tag", default="main", help="main | pcie-gen2 | latency-sync | ... (analyse groups by mode+tag)")
    ap.add_argument("--hef", default=str(common.ROOT / cfg["default_hef"]))
    ap.add_argument("--backend", choices=["hailo", "sim"], default="hailo")
    ap.add_argument("--idle-seconds", type=int, default=600)
    ap.add_argument("--duration", type=int, default=3600)
    ap.add_argument("--fixed-duration", action="store_true", help="run the full --duration instead of stopping at steady state")
    ap.add_argument("--min-run", type=int, default=900)
    ap.add_argument("--frames-per-call", type=int, default=32)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--device-batch", type=int, default=1)
    ap.add_argument("--images-dir", default=None)
    ap.add_argument("--ambient-c", type=float, default=None, help="room thermometer reading")
    ap.add_argument("--power-source", choices=["none", "shelly-gen1", "shelly-gen2", "tasmota", "http"], default="none")
    ap.add_argument("--power-url", default=None)
    ap.add_argument("--power-json-path", default=None)
    ap.add_argument("--out-root", default=str(common.ROOT / "data" / "raw"))
    a = ap.parse_args()

    sid = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_{a.mode}_{a.tag}_run{a.run}"
    d = Path(a.out_root) / sid
    d.mkdir(parents=True)
    print(f"[SESSION] {sid}")

    env = subprocess.run(["bash", str(HERE / "env_check.sh")], capture_output=True, text=True).stdout
    (d / "env.txt").write_text(env)
    if a.backend == "hailo" and "HAILO8L" not in env.upper().replace("-", "").replace("_", ""):
        print("[WARN] env.txt does not show a Hailo-8L. Check `hailortcli fw-control identify`.")
    t_start_temp = common.read_soc_temp()
    print(f"[INFO] SoC temp at session start: {t_start_temp} C (ambient {a.ambient_c})")

    procs = []
    meta = {"session_id": sid, "args": vars(a), "soc_temp_at_start_c": t_start_temp, "ambient_c": a.ambient_c,
            "git_commit": common.git_commit(), "simulated": a.backend == "sim"}
    try:
        procs.append(subprocess.Popen([sys.executable, str(HERE / "log_thermal.py"), str(d / "thermal.csv")]))
        if a.power_source != "none":
            if not a.power_url:
                raise SystemExit("--power-url required with --power-source")
            cmd = [sys.executable, str(HERE / "log_power.py"), str(d / "power.csv"), "--source", a.power_source, "--url", a.power_url]
            if a.power_json_path:
                cmd += ["--json-path", a.power_json_path]
            procs.append(subprocess.Popen(cmd))
        time.sleep(2)

        meta["idle_start"] = time.time()
        print(f"[PHASE] idle baseline {a.idle_seconds}s (do not touch the Pi)")
        t_end = time.time() + a.idle_seconds
        while time.time() < t_end:
            time.sleep(min(30, max(0.0, t_end - time.time())))
            print(f"  idle... {int(t_end - time.time())}s left")
        meta["idle_end"] = time.time()

        cmd = [sys.executable, str(HERE / "bench.py"), "--hef", a.hef, "--mode", a.mode, "--backend", a.backend,
               "--duration", str(a.duration), "--min-run", str(a.min_run), "--frames-per-call", str(a.frames_per_call),
               "--workers", str(a.workers), "--device-batch", str(a.device_batch), "--outdir", str(d), "--tag", a.tag]
        if not a.fixed_duration:
            cmd.append("--until-steady")
        if a.images_dir:
            cmd += ["--images-dir", a.images_dir]
        print("[PHASE] benchmark")
        meta["bench_start"] = time.time()
        rc = subprocess.call(cmd)
        meta["bench_end"] = time.time()
        meta["bench_returncode"] = rc
    finally:
        for p in procs:
            stop_proc(p)
        if a.backend == "hailo" and meta.get("bench_returncode") == 0:
            # Independent reference (no Python in the loop). Run AFTER loggers stop so it cannot contaminate them.
            ref = subprocess.run(["hailortcli", "benchmark", a.hef, "-t", "15", "--batch-size", str(a.device_batch)],
                                 capture_output=True, text=True).stdout
            (d / "hailortcli_benchmark.txt").write_text(ref)
        (d / "session.json").write_text(json.dumps(meta, indent=2))
    print(f"[DONE] {d}")
    sys.exit(meta.get("bench_returncode", 1))


if __name__ == "__main__":
    main()
