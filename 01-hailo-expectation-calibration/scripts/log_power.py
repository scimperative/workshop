#!/usr/bin/env python3
"""Mains-side power logger for a smart plug with a local HTTP API (>=1 Hz).

  python scripts/log_power.py out.csv --source shelly-gen1 --url http://192.168.1.50
  python scripts/log_power.py out.csv --source shelly-gen2 --url http://192.168.1.50
  python scripts/log_power.py out.csv --source tasmota     --url http://192.168.1.50
  python scripts/log_power.py out.csv --source http --url http://host/status --json-path meters.0.power

Any other meter: export/log "timestamp_utc(epoch seconds),watts" to <session>/power.csv yourself.
Rows are written with the request midpoint timestamp; failures are logged as NaN."""
import argparse
import csv
import json
import signal
import time
import urllib.request

stop = False


def _sig(*_):
    global stop
    stop = True


def dig(obj, path):
    for part in path.split("."):
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


PRESETS = {
    "shelly-gen1": ("/status", "meters.0.power"),
    "shelly-gen2": ("/rpc/Switch.GetStatus?id=0", "apower"),
    "tasmota": ("/cm?cmnd=Status%208", "StatusSNS.ENERGY.Power"),
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--source", choices=[*PRESETS, "http"], required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--json-path", default=None)
    ap.add_argument("--interval", type=float, default=1.0)
    a = ap.parse_args()
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    if a.source == "http":
        url, path = a.url, a.json_path
        if not path:
            raise SystemExit("--json-path required for --source http")
    else:
        suffix, path = PRESETS[a.source]
        url = a.url.rstrip("/") + suffix
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "watts"])
        nxt = time.time()
        while not stop:
            t0 = time.time()
            try:
                with urllib.request.urlopen(url, timeout=2.0) as r:
                    watts = float(dig(json.loads(r.read()), path))
            except Exception:
                watts = float("nan")
            t1 = time.time()
            w.writerow([f"{(t0 + t1) / 2:.3f}", watts])
            f.flush()
            nxt += a.interval
            time.sleep(max(0.0, nxt - time.time()))
