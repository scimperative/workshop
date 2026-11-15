#!/usr/bin/env python3
"""Parse raw sessions in data/raw/, compute Q1-Q6 measurements, make tables/figures, score predictions.

  python scripts/analyse.py                 # tables + figures (+ scorecard if predictions are frozen)
  python scripts/analyse.py --allow-simulated   # include sim-backend runs (pipeline testing only)
"""
import argparse
import csv
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

RAW = common.ROOT / "data" / "raw"
RES = common.ROOT / "results"
THERMAL_BITS = 0x2 | 0x4 | 0x8  # arm freq capped | currently throttled | soft temp limit active
UNDERVOLT_BIT = 0x1


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_sessions(allow_sim):
    out, skipped = [], []
    for sj in sorted(RAW.glob("*/session.json")):
        d = sj.parent
        if not (d / "bench_summary.json").exists():
            continue
        meta = json.loads(sj.read_text())
        summ = json.loads((d / "bench_summary.json").read_text())
        if summ.get("simulated") and not allow_sim:
            skipped.append(d.name)
            continue
        out.append({"dir": d, "meta": meta, "summ": summ, "sec": read_csv(d / "bench_seconds.csv"),
                    "power": read_csv(d / "power.csv")})
    return out, skipped


def mean_in(rows, key_t, key_v, lo, hi):
    v = [fnum(r[key_v]) for r in rows if lo <= fnum(r[key_t]) < hi]
    v = [x for x in v if not math.isnan(x)]
    return (sum(v) / len(v)) if v else float("nan")


def session_metrics(s):
    sec, summ, meta = s["sec"], s["summ"], s["meta"]
    if not sec:
        return None
    t = np.array([fnum(r["t_rel_s"]) for r in sec])
    f = np.array([fnum(r["frames"]) for r in sec])
    T = np.array([fnum(r["soc_temp_c"]) for r in sec])
    cpu_t = np.array([fnum(r["cpu_total_pct"]) for r in sec])
    cpu_m = np.array([fnum(r["cpu_max_core_pct"]) for r in sec])
    thr = [int(r["throttled"], 16) if r["throttled"].startswith("0x") else 0 for r in sec]
    warm, dur = summ["warmup_s"], t[-1]
    win_lo = max(warm, dur - 600)
    ss = t > win_lo
    cold = (t > warm) & (t <= warm + 60)
    m = {
        "session": s["dir"].name, "mode": summ["mode"], "tag": summ["tag"], "simulated": summ.get("simulated"),
        "duration_s": float(dur), "stop_reason": summ["stop_reason"],
        "fps_steady": float(f[ss].mean()) if ss.any() else float("nan"),
        "fps_cold": float(f[cold].mean()) if cold.any() else float("nan"),
        "lat_p50_ms": summ["latency_ms"]["p50"], "lat_p95_ms": summ["latency_ms"]["p95"], "lat_p99_ms": summ["latency_ms"]["p99"],
        "temp_start_c": float(np.nanmin(T[:10])) if len(T) and not np.all(np.isnan(T[:10])) else float("nan"),
        "temp_max_c": float(np.nanmax(T)) if len(T) and not np.all(np.isnan(T)) else float("nan"),
        "cpu_total_pct": float(np.nanmean(cpu_t[ss])) if ss.any() else float("nan"),
        "cpu_max_core_pct": float(np.nanmean(cpu_m[ss])) if ss.any() else float("nan"),
        "thermal_throttle_s": int(sum(1 for x in thr if x & THERMAL_BITS)),
        "undervolt_s": int(sum(1 for x in thr if x & UNDERVOLT_BIT)),
        "pcie_link": summ.get("pcie_link", {}).get("current_link_speed"),
        "postprocess_executed": summ.get("postprocess_executed"),
    }
    m["fps_ratio_steady_over_cold"] = m["fps_steady"] / m["fps_cold"] if m["fps_cold"] and not math.isnan(m["fps_cold"]) else float("nan")
    # power (mains). Idle excludes first 60 s while the plug/Pi settle.
    pw = s["power"]
    if pw and "idle_start" in meta:
        idle_w = mean_in(pw, "timestamp_utc", "watts", meta["idle_start"] + 60, meta["idle_end"])
        e0 = summ["epoch_start"]
        load_w = mean_in(pw, "timestamp_utc", "watts", e0 + win_lo, e0 + dur)
        m.update(idle_w=idle_w, load_w=load_w,
                 energy_total_j=load_w / m["fps_steady"], energy_idle_sub_j=(load_w - idle_w) / m["fps_steady"])
    else:
        m.update(idle_w=float("nan"), load_w=float("nan"), energy_total_j=float("nan"), energy_idle_sub_j=float("nan"))
    return m


def group_median(ms, key):
    v = [x[key] for x in ms if not math.isnan(fnum(x.get(key)))]
    return statistics.median(v) if v else float("nan")


def plot_session(s, m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sec = s["sec"]
    t = np.array([fnum(r["t_rel_s"]) for r in sec]) / 60
    f = np.array([fnum(r["frames"]) for r in sec])
    T = np.array([fnum(r["soc_temp_c"]) for r in sec])
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    k = max(1, min(30, len(f) // 4))
    ax[0].plot(t, np.convolve(f, np.ones(k) / k, mode="same")); ax[0].set_ylabel(f"FPS ({k}s mean)")
    ax[1].plot(t, T); ax[1].set_ylabel("SoC temp (C)")
    pw = s["power"]
    if pw:
        e0 = s["summ"]["epoch_start"]
        pt = np.array([(fnum(r["timestamp_utc"]) - e0) / 60 for r in pw]); pv = np.array([fnum(r["watts"]) for r in pw])
        ax[2].plot(pt, pv); ax[2].set_ylabel("Mains W")
    else:
        ax[2].text(0.5, 0.5, "no power log", ha="center", transform=ax[2].transAxes)
    ax[2].set_xlabel("minutes since benchmark start")
    fig.suptitle(m["session"] + ("  [SIMULATED]" if m["simulated"] else ""), fontsize=9)
    fig.tight_layout()
    (RES / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(RES / "figures" / f"{m['session']}.png", dpi=110)
    plt.close(fig)


def classify_bottleneck(groups):
    """Heuristic Q2 label + evidence. A human should confirm against the plots."""
    ev = []
    B = groups.get(("end-to-end", "main"), [])
    A = groups.get(("model-only", "main"), [])
    if not B:
        return None, ["no end-to-end runs"]
    ratio = group_median(B, "fps_ratio_steady_over_cold")
    thr_s = group_median(B, "thermal_throttle_s")
    if thr_s > 0 and ratio < 0.95:
        return "thermal", [f"throttle flags set {thr_s:.0f}s and steady/cold FPS = {ratio:.3f}"]
    if A:
        fa, fb = group_median(A, "fps_steady"), group_median(B, "fps_steady")
        cpu_m, cpu_t = group_median(B, "cpu_max_core_pct"), group_median(B, "cpu_total_pct")
        ev.append(f"Mode B/Mode A FPS = {fb/fa:.2f}; Mode B CPU total {cpu_t:.0f}%, busiest core {cpu_m:.0f}%")
        if fb < 0.85 * fa and (cpu_m >= 90 or cpu_t >= 85):
            return "host_cpu", ev
    g2 = groups.get(("model-only", "pcie-gen2"), [])
    if A and g2:
        drop = 1 - group_median(g2, "fps_steady") / group_median(A, "fps_steady")
        ev.append(f"Gen2 vs Gen3 Mode A FPS drop = {drop*100:.1f}%")
        if drop >= 0.10:
            return "pcie", ev
    else:
        ev.append("no pcie-gen2 model-only runs: PCIe sensitivity untested")
    return "npu", ev + ["no thermal/CPU/PCIe signature found => device-side (NPU/compiler mapping)"]


def measured_values(groups, cfg, transformer, acc):
    A = groups.get(("model-only", "main"), [])
    B = groups.get(("end-to-end", "main"), [])
    L = groups.get(("model-only", "latency-sync"), [])
    v = {}
    if A:
        v["q1_fps_mode_a"] = group_median(A, "fps_steady")
        v["q6_npu_utilization_mode_a"] = v["q1_fps_mode_a"] * cfg["model_flops_per_inference"] / (cfg["rated_tops"] * 1e12)
    if B:
        v["q1_fps_mode_b"] = group_median(B, "fps_steady")
        v["q3_energy_total_j_per_inf_mode_b"] = group_median(B, "energy_total_j")
        v["q3_energy_idle_sub_j_per_inf_mode_b"] = group_median(B, "energy_idle_sub_j")
        v["power_w_mode_b"] = group_median(B, "load_w")
        v["q4_fps_ratio_steady_over_cold_mode_b"] = group_median(B, "fps_ratio_steady_over_cold")
    if L:
        v["latency_p95_ms_mode_a_sync"] = group_median(L, "lat_p95_ms")
    label, ev = classify_bottleneck(groups)
    if label:
        v["q2_bottleneck_mode_b"] = label
    if transformer:
        v["q5_transformer_tier"] = transformer.get("tier")
    return {k: x for k, x in v.items() if not (isinstance(x, float) and math.isnan(x))}, ev


def score(preds, measured):
    rows = []
    for k, p in preds.items():
        if k not in measured:
            rows.append({"metric": k, "status": "no measurement"}); continue
        mv = measured[k]
        if "value" in p:
            rows.append({"metric": k, "pred": p["value"], "meas": mv, "hit": p["value"] == mv, "cat": True}); continue
        hit = p["low"] <= mv <= p["high"]
        rows.append({"metric": k, "pred": p["point"], "meas": mv, "low": p["low"], "high": p["high"], "hit": hit,
                     "log_err": float(np.log10(mv / p["point"])) if mv > 0 and p["point"] > 0 else float("nan"), "cat": False})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-simulated", action="store_true")
    ap.add_argument("--allow-unfrozen", action="store_true")
    a = ap.parse_args()
    cfg = common.load_config()
    sessions, skipped = load_sessions(a.allow_simulated)
    if skipped:
        print(f"[INFO] skipped {len(skipped)} simulated session(s) (use --allow-simulated for pipeline tests)")
    if not sessions:
        sys.exit("No sessions found in data/raw/.")
    (RES / "tables").mkdir(parents=True, exist_ok=True)

    metrics, groups = [], defaultdict(list)
    for s in sessions:
        m = session_metrics(s)
        if m:
            metrics.append(m)
            groups[(m["mode"], m["tag"])].append(m)
            plot_session(s, m)

    fmt = lambda x, p=2: "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else (f"{x:.{p}f}" if isinstance(x, float) else str(x))
    L = ["# Per-session results", "",
         "| session | mode | tag | dur (min) | stop | FPS steady | FPS cold | steady/cold | p50 ms | p95 ms | p99 ms | T max C | CPU % (tot/core) | throttle s | W idle | W load | J/inf total | J/inf idle-sub |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in metrics:
        L.append(f"| {m['session']} | {m['mode']} | {m['tag']} | {m['duration_s']/60:.1f} | {m['stop_reason']} | {fmt(m['fps_steady'],1)} | {fmt(m['fps_cold'],1)} | {fmt(m['fps_ratio_steady_over_cold'],3)} | {fmt(m['lat_p50_ms'])} | {fmt(m['lat_p95_ms'])} | {fmt(m['lat_p99_ms'])} | {fmt(m['temp_max_c'],1)} | {fmt(m['cpu_total_pct'],0)}/{fmt(m['cpu_max_core_pct'],0)} | {m['thermal_throttle_s']} | {fmt(m['idle_w'])} | {fmt(m['load_w'])} | {fmt(m['energy_total_j'],4)} | {fmt(m['energy_idle_sub_j'],4)} |")
    L += ["", "# Group medians (across repetitions)", "", "| mode | tag | runs | FPS steady (min-max) | J/inf total | steady/cold |", "|---|---|---|---|---|---|"]
    for (mode, tag), ms in sorted(groups.items()):
        fs = [x["fps_steady"] for x in ms]
        L.append(f"| {mode} | {tag} | {len(ms)} | {fmt(statistics.median(fs),1)} ({min(fs):.1f}-{max(fs):.1f}) | {fmt(group_median(ms,'energy_total_j'),4)} | {fmt(group_median(ms,'fps_ratio_steady_over_cold'),3)} |")
        if len(ms) < 3 and tag == "main":
            L[-1] += "  **<3 runs: protocol requires >=3**"
    (RES / "tables" / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))

    acc = {}
    for b in ("hailo", "onnx"):
        p = RAW / f"accuracy_{b}.json"
        if p.exists():
            acc[b] = json.loads(p.read_text())
    if "hailo" in acc and "onnx" in acc:
        d = acc["hailo"]["map50_95"] - acc["onnx"]["map50_95"]
        txt = f"mAP50-95 INT8(Hailo) {acc['hailo']['map50_95']:.4f} vs FP32(ONNX) {acc['onnx']['map50_95']:.4f}  delta {d:+.4f}"
        (RES / "tables" / "accuracy.md").write_text(txt + "\n\n" + json.dumps({k: v["note"] for k, v in acc.items()}, indent=1) + "\n")
        print("\n" + txt)
    tf = next(iter(sorted(RAW.glob("transformer_*.json"))), None)
    transformer = json.loads(tf.read_text()) if tf else None

    measured, ev = measured_values(groups, cfg, transformer, acc)
    print("\nQ2 evidence:", *ev, sep="\n  - ")
    print("\nMeasured values:", json.dumps({k: (round(x, 4) if isinstance(x, float) else x) for k, x in measured.items()}, indent=1))

    pp = common.ROOT / "pre-registration" / "predictions.json"
    if not pp.exists():
        print("\n[INFO] pre-registration/predictions.json not found -> scorecard skipped.")
        return
    P = json.loads(pp.read_text())
    if not P.get("frozen") and not a.allow_unfrozen:
        print("\n[WARN] predictions.json has frozen=false -> scorecard skipped (pre-registration must be frozen BEFORE benchmarking).")
        return
    preds = {k: v for k, v in P["predictions"].items() if not k.startswith("_")}
    if any(v is None or any(x is None for x in v.values()) for v in preds.values()):
        sys.exit("predictions.json still has null entries.")
    rows = score(preds, measured)
    num = [r for r in rows if r.get("cat") is False]
    cat = [r for r in rows if r.get("cat")]
    S = ["# Scorecard", "", f"Generated from {len(sessions)} session(s). Prediction file git commit should predate all runs.", "",
         "| metric | predicted (80% interval) | measured | hit | log10 error |", "|---|---|---|---|---|"]
    unscored = [r for r in rows if r.get("status")]
    S[4:4] = [
        "**Read this first**", "",
        f"- Numeric: {sum(r['hit'] for r in num)}/{len(num)} intervals hit. Categorical: {sum(r['hit'] for r in cat)}/{len(cat)} hit (Q2 bottleneck is a miss; see Q2 evidence below). The numeric hit rate is not the whole result.",
        f"- {len(unscored)} predictions have no measurement and are not scored: {', '.join(r['metric'] for r in unscored)}.",
        "- The numerical predictions were set after pilot runs on this same rig: this is a pilot-informed calibration, not a blind forecast. See protocol/deviations.md.",
        "- The pre-registration tag (prereg-01) was created after the runs; the independent deposit is retrospective. See protocol/deviations.md.",
        "",
    ]
    for r in rows:
        if r.get("status"):
            S.append(f"| {r['metric']} | - | - | {r['status']} | - |")
        elif r["cat"]:
            S.append(f"| {r['metric']} | {r['pred']} | {r['meas']} | {'YES' if r['hit'] else 'NO'} | - |")
        else:
            S.append(f"| {r['metric']} | {r['pred']:.4g} ({r['low']:.4g}-{r['high']:.4g}) | {r['meas']:.4g} | {'YES' if r['hit'] else 'NO'} | {r['log_err']:+.3f} |")
    if num:
        hr = 100 * sum(r["hit"] for r in num) / len(num)
        mae = float(np.nanmean([abs(r["log_err"]) for r in num]))
        S += ["", f"Numeric interval hit rate: {hr:.0f}% ({sum(r['hit'] for r in num)}/{len(num)}); target ~80%.",
              f"Mean absolute log10 error: {mae:.3f}  (0.1 = 26% off, 0.3 = 2x off)"]
    if cat:
        S.append(f"Categorical hits: {sum(r['hit'] for r in cat)}/{len(cat)}")
    S += ["", "Q2 evidence:"] + [f"- {e}" for e in ev]
    (RES / "scorecard.md").write_text("\n".join(S) + "\n")
    print("\n" + "\n".join(S))


if __name__ == "__main__":
    main()
