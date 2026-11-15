#!/usr/bin/env python3
"""1 Hz SoC temperature / throttle flags / ARM clock logger (Raspberry Pi 5).
Usage: python scripts/log_thermal.py out.csv     (Ctrl+C or SIGTERM to stop)
No simulated fallback: unavailable sensors are logged as NaN/empty so bad data is visible."""
import csv
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

stop = False


def _sig(*_):
    global stop
    stop = True


if __name__ == "__main__":
    out_csv = sys.argv[1] if len(sys.argv) > 1 else "thermal_log.csv"
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    print(f"[INFO] thermal logging -> {out_csv}")
    warned = False
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "soc_temp_c", "throttle_hex", "arm_clock_hz"])
        nxt = time.time()
        while not stop:
            ts = time.time()
            temp = common.read_soc_temp()
            if temp != temp and not warned:
                print("[WARN] SoC temperature unavailable (not a Pi?)", file=sys.stderr)
                warned = True
            w.writerow([f"{ts:.3f}", temp, common.read_throttled(), common.read_arm_clock_hz()])
            f.flush()
            nxt += 1.0
            time.sleep(max(0.0, nxt - time.time()))
    print("[INFO] thermal logging stopped")
