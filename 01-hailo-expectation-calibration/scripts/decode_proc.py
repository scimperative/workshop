"""Mode B decode workers as separate PROCESSES (spawned), writing letterboxed frames into a
shared-memory ring. Needed because HailoRT's infer() holds the Python GIL, which starves decode
threads (measured: diag_hostpath.py, GIL ratio 0.06)."""
import os
import queue
import signal
import sys
import time
from multiprocessing import shared_memory

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def decode_worker(paths, size, shm_name, nslots, free_q, ready_q, stop_ev, wid, nworkers):
    import cv2

    import common

    signal.signal(signal.SIGINT, signal.SIG_IGN)  # parent controls shutdown
    cv2.setNumThreads(1)                          # one core per worker
    shm = shared_memory.SharedMemory(name=shm_name)
    buf = np.ndarray((nslots, size, size, 3), np.uint8, buffer=shm.buf)
    i = wid
    try:
        while not stop_ev.is_set():
            try:
                slot = free_q.get(timeout=0.2)
            except queue.Empty:
                continue
            t0 = time.perf_counter()
            rgb, meta = common.load_and_letterbox(paths[i % len(paths)], size)  # JPEG decode + letterbox
            i += nworkers
            buf[slot] = rgb                                                      # copy into shared ring
            ready_q.put((slot, meta, time.perf_counter() - t0))
    finally:
        del buf
        shm.close()
