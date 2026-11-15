# Deviations log (append-only; never edit past entries)

| UTC timestamp | Session / step | What deviated | Why | Impact on validity |
|---|---|---|---|---|

## Pilot Runs & Harness Calibration (2026-11-15)

- **Pilot Measurements (Mode A):** Measured at ~108.8 FPS (32 frames-per-call, device batch 1), matching HailoRT CLI benchmark reference (~115.1 FPS).
- **GIL Starvation Bottleneck Identified:** Initial Mode B thread implementation capped at ~82 FPS because `hailo_platform.infer()` held the Python GIL, starving the OpenCV decode thread (`diag_hostpath.py` confirmed counter-thread ratio during infer was 0.06).
- **Harness Modification:** Mode B was rewritten to use a separate spawned process pool (`scripts/decode_proc.py`) writing to a shared-memory ring buffer.
- **Post-Fix Validation:** Mode B throughput increased to **99.8 FPS**, leaving a minor ~8.2% host copy/JPEG decode overhead gap vs Mode A.
- **Model Post-Processing Note:** Hailo HEF uses baked-in NMS score threshold of `0.20`. Baseline FP32 ONNX script parameter updated to match (`--conf 0.20`).
