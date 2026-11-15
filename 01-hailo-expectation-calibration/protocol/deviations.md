# Deviations log (append-only; never edit past entries)

| UTC timestamp | Session / step | What deviated | Why | Impact on validity |
|---|---|---|---|---|

## Pilot Runs & Harness Calibration (2026-11-15)

- **Pilot Measurements (Mode A):** Measured at ~108.8 FPS (32 frames-per-call, device batch 1), matching HailoRT CLI benchmark reference (~115.1 FPS).
- **GIL Starvation Bottleneck Identified:** Initial Mode B thread implementation capped at ~82 FPS because `hailo_platform.infer()` held the Python GIL, starving the OpenCV decode thread (`diag_hostpath.py` confirmed counter-thread ratio during infer was 0.06).
- **Harness Modification:** Mode B was rewritten to use a separate spawned process pool (`scripts/decode_proc.py`) writing to a shared-memory ring buffer.
- **Post-Fix Validation:** Mode B throughput increased to **99.8 FPS**, leaving a minor ~8.2% host copy/JPEG decode overhead gap vs Mode A.
- **Model Post-Processing Note:** Hailo HEF uses baked-in NMS score threshold of `0.20`. Baseline FP32 ONNX script parameter updated to match (`--conf 0.20`).

## Pre-registration timestamping gaps (logged 2026-11-15T17:06:09Z)

- **Freeze commit:** predictions.json was committed as bd92298 at 2026-11-15T13:54:20Z. Author and committer timestamps are client-set and unverified; the git identity was the placeholder you@example.com.
- **Measurement order:** the first scored benchmark run folder (20261115T141127Z_model-only_main_run1) began after that commit. Section 10 steps 3-4 (protected annotated tag, independent OSF/Zenodo deposit) were NOT completed before measuring, and the prereg markdown template (2026-11-xx-prereg.md) still has blank freeze time, commit and DOI fields. Step 6 was therefore not followed.
- **Pilot-informed predictions:** the numerical predictions were set after pilot runs on this same rig (see the 2026-11-15 pilot entry above; pilot Mode A about 108.8 FPS). The YOLOv8n scorecard (interval hit rate, log error) must be read as pilot-informed, not blind forecasts.
- **Retrospective tag:** annotated tag prereg-01 is being created after the YOLOv8n runs, pointing at bd92298. Its tag date is the tagging time, not the freeze time. The independent deposit is also retrospective and will be linked here once it has a DOI.
- **Q5 (transformer tier):** frozen as T0 with no stated probability, no model named, and no numeric T3 threshold. The default --t3-min-fps 100 in scripts/check_transformer.py was never pre-registered. As of this entry, no transformer compile or run has been attempted (data/raw/transformers and models/transformers are empty).

## Independent deposit deferred (logged 2026-11-15T17:11:56Z)

- The Zenodo/OSF deposit mentioned above has been deferred by the author. As of this entry the pre-registration has only git-based evidence (commit bd92298, tag prereg-01), which is client-set and unverified. Any claim that predictions pre-date measurement rests on that weaker evidence until an independent deposit or timestamp is added.
