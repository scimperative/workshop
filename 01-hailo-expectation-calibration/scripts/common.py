"""Shared helpers for Workshop 01 scripts (stdlib + numpy; cv2 imported lazily)."""
from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import pathlib
import subprocess
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text())


def sh(cmd, timeout=10):
    """Run a command, return stripped stdout or None on any failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def sha256_file(path, chunk=1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def git_commit() -> str | None:
    return sh(["git", "-C", str(ROOT), "rev-parse", "HEAD"])


# --------------------------------------------------------------------------
# Pi telemetry
# --------------------------------------------------------------------------
def read_soc_temp() -> float:
    """SoC temperature in degC (vcgencmd first, sysfs fallback). NaN if unavailable."""
    out = sh(["vcgencmd", "measure_temp"], timeout=3)
    if out and "=" in out:
        try:
            return float(out.split("=")[1].replace("'C", "").strip())
        except ValueError:
            pass
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return float("nan")


def read_throttled() -> str:
    """Raw `vcgencmd get_throttled` hex string, e.g. '0x0'. '' if unavailable."""
    out = sh(["vcgencmd", "get_throttled"], timeout=3)
    if out and "=" in out:
        return out.split("=")[1].strip()
    return ""


def read_arm_clock_hz() -> float:
    out = sh(["vcgencmd", "measure_clock", "arm"], timeout=3)
    if out and "=" in out:
        try:
            return float(out.split("=")[1])
        except ValueError:
            pass
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") as f:
            return float(f.read().strip()) * 1000.0
    except Exception:
        return float("nan")


def read_cpu_times():
    """[(name, idle, total), ...] from /proc/stat ('cpu' first, then cpu0..N)."""
    out = []
    try:
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("cpu"):
                    p = line.split()
                    v = list(map(int, p[1:9]))
                    out.append((p[0], v[3] + v[4], sum(v)))
    except Exception:
        pass
    return out


def cpu_util(prev, cur):
    """(overall %, busiest-core %) between two read_cpu_times() snapshots."""
    if not prev or not cur or len(prev) != len(cur):
        return float("nan"), float("nan")
    utils = []
    for (_, i0, t0), (_, i1, t1) in zip(prev, cur):
        dt = t1 - t0
        utils.append(100.0 * (1.0 - (i1 - i0) / dt) if dt > 0 else float("nan"))
    overall = utils[0]
    cores = [u for u in utils[1:] if not math.isnan(u)]
    return overall, (max(cores) if cores else float("nan"))


def hailo_pcie_link() -> dict:
    """Negotiated PCIe link of the Hailo device (vendor 0x1e60) from sysfs."""
    for dev in glob.glob("/sys/bus/pci/devices/*"):
        try:
            with open(dev + "/vendor") as f:
                if f.read().strip() != "0x1e60":
                    continue
            info = {"device": os.path.basename(dev)}
            for k in ("current_link_speed", "current_link_width", "max_link_speed", "max_link_width"):
                try:
                    with open(f"{dev}/{k}") as f:
                        info[k] = f.read().strip()
                except Exception:
                    info[k] = None
            return info
        except Exception:
            continue
    return {}


# --------------------------------------------------------------------------
# Steady-state detection (shared by bench.py and analyse.py)
# --------------------------------------------------------------------------
def steady_state(t_rel, frames, temps, window_s=600, bin_s=30, temp_slope_max=0.5, fps_cv_max=0.02):
    """Pre-registered stop rule.

    t_rel  : per-second timestamps (seconds since loop start), ascending, 1 Hz
    frames : frames completed in each second
    temps  : SoC temp per second (NaN allowed)
    Returns (is_steady, temp_slope_C_per_window, fps_cv). Needs a full window.

    Interpretation (documented in protocol/protocol.md):
      * temp slope  = least-squares slope over the last `window_s` seconds, in degC per `window_s`
      * FPS variance = coefficient of variation of `bin_s`-second mean FPS across the window
    """
    t_rel = np.asarray(t_rel, float)
    frames = np.asarray(frames, float)
    temps = np.asarray(temps, float)
    if len(t_rel) < window_s or t_rel[-1] - t_rel[0] < window_s - 2:
        return False, float("nan"), float("nan")
    t = t_rel[-window_s:]
    f = frames[-window_s:]
    tp = temps[-window_s:]
    ok = ~np.isnan(tp)
    slope = float("nan")
    if ok.sum() > 10:
        slope = float(np.polyfit(t[ok], tp[ok], 1)[0] * window_s)
    nb = window_s // bin_s
    bins = f[: nb * bin_s].reshape(nb, bin_s).mean(axis=1)
    cv = float(bins.std() / bins.mean()) if bins.mean() > 0 else float("inf")
    steady = (not math.isnan(slope)) and abs(slope) < temp_slope_max and cv < fps_cv_max
    return steady, slope, cv


# --------------------------------------------------------------------------
# Dataset + preprocessing
# --------------------------------------------------------------------------
def dataset_dir() -> pathlib.Path:
    return ROOT / "data" / "coco" / "val2017_subset"


def list_dataset(images_dir=None):
    """Return list of (image_id|None, path). Uses the committed manifest unless images_dir is given."""
    if images_dir:
        files = sorted(glob.glob(os.path.join(images_dir, "*.jpg")))
        if not files:
            raise SystemExit(f"No .jpg files in {images_dir}")
        return [(None, p) for p in files]
    mf = ROOT / "data" / "coco" / "subset_manifest.json"
    if not mf.exists():
        raise SystemExit("data/coco/subset_manifest.json missing. Run: python scripts/fetch_assets.py coco")
    items = json.loads(mf.read_text())["images"]
    d = dataset_dir()
    out = []
    for it in items:
        p = d / it["file_name"]
        if not p.exists():
            raise SystemExit(f"Missing image {p}. Run: python scripts/fetch_assets.py coco")
        out.append((it["id"], str(p)))
    return out


def letterbox(img_bgr, size=640, pad=114):
    """BGR image -> (RGB uint8 size x size x 3, meta). meta = (scale, left, top, orig_w, orig_h)."""
    import cv2

    h, w = img_bgr.shape[:2]
    r = min(size / h, size / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas = np.full((size, size, 3), pad, np.uint8)
    canvas[top : top + nh, left : left + nw] = resized
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    return rgb, (r, left, top, w, h)


def load_and_letterbox(path, size=640):
    import cv2

    img = cv2.imread(path, cv2.IMREAD_COLOR)  # JPEG decode on host CPU
    if img is None:
        raise RuntimeError(f"Could not decode {path}")
    return letterbox(img, size)


def boxes_to_original(dets, meta, size=640):
    """dets: Nx6 [xmin,ymin,xmax,ymax,score,cls] normalised to the letterboxed input.
    Returns Nx6 in original-image pixel coords (clipped)."""
    if dets.shape[0] == 0:
        return dets
    r, left, top, w, h = meta
    d = dets.copy()
    d[:, [0, 2]] = (d[:, [0, 2]] * size - left) / r
    d[:, [1, 3]] = (d[:, [1, 3]] * size - top) / r
    d[:, [0, 2]] = np.clip(d[:, [0, 2]], 0, w)
    d[:, [1, 3]] = np.clip(d[:, [1, 3]], 0, h)
    return d


# --------------------------------------------------------------------------
# HailoRT NMS output parsing
# --------------------------------------------------------------------------
def _is_class_list(x) -> bool:
    try:
        if len(x) == 0:
            return False
        return all(isinstance(e, np.ndarray) and e.dtype != object for e in list(x)[:5])
    except TypeError:
        return False


def parse_nms_output(out, i=0, score_thr=0.0):
    """Parse a HailoRT NMS_BY_CLASS output for batch element i.

    Hailo returns, per frame, a list with one array per class; each row is
    [y_min, x_min, y_max, x_max, score] normalised to the network input.
    Returns Nx6 float32 [xmin, ymin, xmax, ymax, score, class_id].
    Handles both 'list-of-frames' and bare 'list-of-classes' layouts.
    """
    item = out if _is_class_list(out) else out[i]
    if not _is_class_list(item):
        raise ValueError(f"Unrecognised NMS output structure: {type(out)} / {type(item)}")
    rows = []
    for cls, arr in enumerate(item):
        a = np.asarray(arr, dtype=np.float32)
        if a.size == 0:
            continue
        a = a.reshape(-1, 5)
        a = a[a[:, 4] >= score_thr]
        if a.shape[0] == 0:
            continue
        cid = np.full((a.shape[0], 1), cls, np.float32)
        rows.append(np.hstack([a[:, [1, 0, 3, 2, 4]], cid]))
    return np.vstack(rows) if rows else np.zeros((0, 6), np.float32)
