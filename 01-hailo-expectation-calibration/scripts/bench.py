#!/usr/bin/env python3
"""Core inference harness for Workshop 01.

Mode A  (model-only)  : pre-processed tensors held in RAM, fed straight to HailoRT.
Mode B  (end-to-end)  : JPEG decode + letterbox on host worker threads, inference, result parsing.

Frames-per-call (--frames-per-call) is how many frames are handed to one InferVStreams.infer()
call. The *device* batch size stays 1; >1 only keeps the PCIe/NPU pipeline full so you measure
throughput instead of round-trip latency. Use --frames-per-call 1 for synchronous latency runs.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import queue
import signal
import sys
import threading
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from hailo_backend import make_backend  # noqa: E402

STOP = threading.Event()


def _sig(*_):
    STOP.set()


def prepare_cache(items, n, size):
    """Mode A: pre-processed tensors (not timed)."""
    tensors = []
    for _, p in items[:n]:
        rgb, _meta = common.load_and_letterbox(p, size)
        tensors.append(rgb)
    return tensors


def decode_worker(items, size, q, worker_id, n_workers):
    i = worker_id
    while not STOP.is_set():
        _, path = items[i % len(items)]
        t0 = time.perf_counter()
        try:
            rgb, meta = common.load_and_letterbox(path, size)
        except Exception as e:  # keep running, but make it loud
            print(f"[WARN] decode failed {path}: {e}", file=sys.stderr)
            i += n_workers
            continue
        i += n_workers
        while not STOP.is_set():
            try:
                q.put((rgb, meta, t0), timeout=0.2)
                break
            except queue.Full:
                pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cfg = common.load_config()
    ap.add_argument("--hef", default=str(common.ROOT / cfg["default_hef"]))
    ap.add_argument("--mode", choices=["model-only", "end-to-end"], required=True)
    ap.add_argument("--backend", choices=["hailo", "sim"], default="hailo")
    ap.add_argument("--duration", type=int, default=3600, help="hard cap, seconds (spec: 60 min)")
    ap.add_argument("--until-steady", action="store_true", help="stop early once thermal+FPS steady state is reached")
    ap.add_argument("--min-run", type=int, default=900, help="earliest steady-state check, seconds")
    ap.add_argument("--warmup", type=int, default=10, help="seconds discarded from summary stats")
    ap.add_argument("--frames-per-call", type=int, default=8)
    ap.add_argument("--workers", type=int, default=2, help="Mode B decode threads")
    ap.add_argument("--cache-images", type=int, default=64, help="Mode A: distinct pre-processed tensors")
    ap.add_argument("--images-dir", default=None, help="override dataset (smoke tests)")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--tag", default="main")
    a = ap.parse_args()

    outdir = Path(a.outdir or common.ROOT / "data" / "raw" / f"adhoc_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}")
    outdir.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    if a.backend == "hailo" and not os.path.exists(a.hef):
        raise SystemExit(f"HEF not found: {a.hef}  (python scripts/fetch_assets.py hef)")

    be = make_backend(a.backend, a.hef).open()
    size = be.input_shape[0]
    items = common.list_dataset(a.images_dir)
    fpc = max(1, a.frames_per_call)
    e2e = a.mode == "end-to-end"
    out_name = be.output_name()
    thr = cfg["score_threshold"]

    print(f"[INFO] backend={a.backend} mode={a.mode} fpc={fpc} hef={a.hef} input={be.input_shape} nms_output={be.has_nms}")
    if a.backend == "sim":
        print("[WARN] SIMULATED backend: results are NOT hardware measurements.")
    if not be.has_nms:
        print("[WARN] HEF has raw (non-NMS) outputs: Mode B will time decode+inference but NOT post-processing.")

    cache = None
    q = None
    threads = []
    if e2e:
        q = queue.Queue(maxsize=max(16, fpc * 4))
        for w in range(a.workers):
            t = threading.Thread(target=decode_worker, args=(items, size, q, w, a.workers), daemon=True)
            t.start()
            threads.append(t)
    else:
        cache = prepare_cache(items, a.cache_images, size)
        print(f"[INFO] Mode A: {len(cache)} tensors pre-loaded")

    # first-call diagnostic so a changed HailoRT output layout is visible immediately
    probe = np.stack([cache[0] if cache else common.load_and_letterbox(items[0][1], size)[0]] * 1)
    probe_out = be.infer(probe)[out_name]
    if be.has_nms:
        d = common.parse_nms_output(probe_out, 0, 0.0)
        print(f"[INFO] probe inference OK; NMS parse -> {d.shape[0]} candidate boxes")

    seconds_path = outdir / "bench_seconds.csv"
    sec_f = open(seconds_path, "w", newline="")
    sec_w = csv.writer(sec_f)
    hdr = ["t_epoch", "t_rel_s", "frames", "lat_mean_ms", "lat_p50_ms", "lat_p95_ms", "lat_p99_ms",
           "cpu_total_pct", "cpu_max_core_pct", "soc_temp_c", "throttled", "hailo_ts0_c", "hailo_ts1_c", "dets"]
    sec_w.writerow(hdr)

    # state
    all_lat, all_lat_t = [], []
    rows_t, rows_f, rows_T = [], [], []
    bucket_lat, bucket_frames, bucket_dets = [], 0, 0
    total_frames = total_dets = 0
    soc_temp, thr_flags, chip = float("nan"), "", {}
    last_slow = -1e9
    cpu_prev = common.read_cpu_times()
    loop_start = time.perf_counter()
    epoch0 = time.time()
    next_boundary = 1.0
    stop_reason = "hard_cap"
    err = None

    def flush_second(t_rel_end):
        nonlocal bucket_lat, bucket_frames, bucket_dets, cpu_prev, soc_temp, thr_flags, chip, last_slow
        if t_rel_end - last_slow >= 5.0:  # slow sensors every 5 s
            soc_temp = common.read_soc_temp()
            thr_flags = common.read_throttled()
            chip = be.chip_temps()
            last_slow = t_rel_end
        cpu_now = common.read_cpu_times()
        cpu_t, cpu_m = common.cpu_util(cpu_prev, cpu_now)
        cpu_prev = cpu_now
        if bucket_lat:
            l = np.asarray(bucket_lat)
            ls = [l.mean(), *np.percentile(l, [50, 95, 99])]
        else:
            ls = [float("nan")] * 4
        sec_w.writerow([round(epoch0 + t_rel_end, 3), round(t_rel_end, 3), bucket_frames,
                        *[round(float(x), 3) for x in ls], round(cpu_t, 1), round(cpu_m, 1),
                        soc_temp, thr_flags, chip.get("hailo_ts0_c", ""), chip.get("hailo_ts1_c", ""), bucket_dets])
        sec_f.flush()
        rows_t.append(t_rel_end)
        rows_f.append(bucket_frames)
        rows_T.append(soc_temp)
        bucket_lat, bucket_frames, bucket_dets = [], 0, 0

    try:
        while not STOP.is_set():
            now = time.perf_counter() - loop_start
            if now >= a.duration:
                break
            # ---- build batch -------------------------------------------------
            if e2e:
                batch, metas, starts = [], [], []
                while len(batch) < fpc and not STOP.is_set():
                    try:
                        rgb, meta, t0 = q.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    batch.append(rgb); metas.append(meta); starts.append(t0)
                if len(batch) < fpc:
                    break
                batch = np.stack(batch)
                t_call = time.perf_counter()
            else:
                idx = total_frames % len(cache)
                batch = np.stack([cache[(idx + k) % len(cache)] for k in range(fpc)])
                starts = None
                t_call = time.perf_counter()

            out = be.infer(batch)[out_name]

            ndet = 0
            if e2e and be.has_nms:  # host post-processing: parse NMS output + map to image coords
                for k in range(fpc):
                    d = common.parse_nms_output(out, k, thr)
                    d = common.boxes_to_original(d, metas[k], size)
                    ndet += d.shape[0]
            t_done = time.perf_counter()

            if e2e:
                lats = [(t_done - s) * 1000.0 for s in starts]   # decode start -> post done (incl. queue wait)
            else:
                lats = [(t_done - t_call) * 1000.0] * fpc        # per-call latency, shared by its frames

            t_rel = t_done - loop_start
            total_frames += fpc
            total_dets += ndet
            bucket_lat.extend(lats)
            bucket_frames += fpc
            bucket_dets += ndet
            if t_rel >= a.warmup:
                all_lat.extend(lats)
                all_lat_t.append(t_rel)

            while t_rel >= next_boundary:
                flush_second(next_boundary)
                next_boundary += 1.0
                # periodic steady-state check
                if a.until_steady and next_boundary > a.min_run and int(next_boundary) % 30 == 0:
                    ok, slope, cv = common.steady_state(rows_t, rows_f, rows_T)
                    if ok:
                        print(f"[INFO] steady state reached at t={next_boundary:.0f}s (temp slope {slope:.2f} C/10min, fps CV {cv*100:.2f}%)")
                        stop_reason = "steady_state"
                        STOP.set()
                        break
        if STOP.is_set() and stop_reason == "hard_cap":
            stop_reason = "interrupted"
    except Exception as e:
        err = repr(e)
        stop_reason = "error"
        raise
    finally:
        STOP.set()
        sec_f.close()
        end_t = time.perf_counter() - loop_start
        be.close()
        lat = np.asarray(all_lat) if all_lat else np.zeros(1)
        measured_frames = int(sum(f for t, f in zip(rows_t, rows_f) if t > a.warmup))
        measured_dur = max(1e-9, (rows_t[-1] if rows_t else end_t) - a.warmup)
        summary = {
            "mode": a.mode, "tag": a.tag, "simulated": bool(be.simulated), "backend": a.backend,
            "hef": a.hef, "hef_sha256": common.sha256_file(a.hef) if os.path.exists(a.hef) else None,
            "frames_per_call": fpc, "workers": a.workers if e2e else 0,
            "duration_s": end_t, "warmup_s": a.warmup, "stop_reason": stop_reason, "error": err,
            "total_frames": total_frames, "measured_frames": measured_frames,
            "fps_overall_post_warmup": measured_frames / measured_dur,
            "latency_ms": {"p50": float(np.percentile(lat, 50)), "p95": float(np.percentile(lat, 95)),
                           "p99": float(np.percentile(lat, 99)), "mean": float(lat.mean())},
            "latency_definition": ("decode-start to post-process-done per frame (incl. queue wait)" if e2e
                                   else "per infer() call, shared by all frames in the call"),
            "mean_dets_per_frame": (total_dets / total_frames) if (e2e and total_frames) else None,
            "postprocess_executed": bool(e2e and be.has_nms),
            "pcie_link": common.hailo_pcie_link(),
            "hailort_python": be.version(), "kernel": platform.release(), "python": platform.python_version(),
            "git_commit": common.git_commit(), "argv": sys.argv, "epoch_start": epoch0,
        }
        (outdir / "bench_summary.json").write_text(json.dumps(summary, indent=2))
        np.savez_compressed(outdir / "latencies.npz", lat_ms=np.asarray(all_lat, np.float32),
                            t_rel_s=np.asarray(all_lat_t, np.float32))
        print("\n--- RESULTS (post-warmup) ---")
        print(f"fps={summary['fps_overall_post_warmup']:.2f}  frames={measured_frames}  stop={stop_reason}")
        print("latency ms  p50={p50:.2f} p95={p95:.2f} p99={p99:.2f}".format(**summary["latency_ms"]))
        print(f"[INFO] wrote {outdir}")


if __name__ == "__main__":
    main()
