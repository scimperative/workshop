# Workshop 01 Pre-registration (FREEZE BEFORE ANY BENCHMARK RUN)

Date/time (UTC) frozen: ____    Git commit of this file: ____    OSF/Zenodo DOI: ____

## Hardware under test (fill from `scripts/env_check.sh`)
- Pi 5 RAM: ___   Active Cooler: yes   PSU: official 27W/5A   Pi OS / kernel: ___
- Accelerator: Raspberry Pi AI HAT+ **Hailo-8L, 13 TOPS** (confirm: `hailortcli fw-control identify`)
- HailoRT / firmware versions: ___   PCIe: Gen3 (primary), Gen2 (secondary)
- Power meter (make/model/rate): ___   Ambient thermometer: ___
- HEF file + sha256: ___   Dataset manifest sha256 (`data/coco/MANIFEST.sha256`): ___

## First-principles derivation (paste output of `python scripts/ceiling.py` and your reasoning)
- GFLOPs/inference and MAC-vs-FLOP check: ___
- Compute ceiling at 100% utilisation: ___ FPS
- Expected haircuts (memory bandwidth, layer mapping, host CPU, PCIe): ___

## Definitions fixed in advance
- FPS = frames completed per second, mean over the final 10 minutes of the run (steady) / first 60 s after the 10 s warm-up (cold).
- Steady state = last 10 min: |SoC temp slope| < 0.5 C per 10 min AND coefficient of variation of 30 s-mean FPS < 2%; 60-min hard cap.
- Mode A = pre-processed tensors in RAM, 8 frames per infer() call, device batch 1. Mode B = JPEG decode + letterbox on 2 host threads, same call size, NMS-output parsing on host.
- Latency = per-call (Mode A) / decode-start-to-parse-done per frame (Mode B). p95 prediction refers to the `latency-sync` tag (1 frame per call, Mode A).
- Energy per inference = mean mains W over the steady window / steady FPS; idle-subtracted uses the mean of the 10 min idle baseline (first 60 s excluded).
- Q2 bottleneck rule: `thermal` if throttle flags set and steady/cold < 0.95; else `host_cpu` if Mode B < 0.85 x Mode A and CPU saturated (core >=90% or total >=85%); else `pcie` if Gen2 Mode A FPS is >=10% below Gen3; else `npu`.
- Q5 tier rule + FPS threshold for T3 (`--t3-min-fps`): ___

## Predictions
Enter numbers in `predictions.json` (point + 80% interval). Mirror them here:

| ID | Metric | Point | 80% low | 80% high |
|---|---|---|---|---|
| Q1a | Mode A sustained FPS | | | |
| Q1b | Mode B sustained FPS | | | |
| Q2 | Binding constraint (Mode B) | | - | - |
| Q3a | J/inference, total mains (Mode B) | | | |
| Q3b | J/inference, idle-subtracted (Mode B) | | | |
| Q4 | steady/cold FPS ratio (Mode B) | | | |
| Q5 | Transformer tier (T0-T3) | | - | - |
| Q6 | NPU utilisation, Mode A (ops/s / rated peak) | | | |
| -  | Sustained mains W (Mode B) | | | |
| -  | p95 latency ms (Mode A, sync) | | | |

## Stopping / reporting commitments
All runs are reported, including failures. Deviations go in `protocol/deviations.md` (append-only).
