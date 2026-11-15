# Physical run protocol

All commands run on the Pi inside the repo with the venv active: `source .venv/bin/activate`.

## 0. One-time
1. `scripts/setup_pi.sh`
2. `python scripts/fetch_assets.py hef`  then  `hailortcli parse-hef models/yolov8n_h8l.hef` (must target HAILO8L). If no download works, put any Hailo-8L YOLOv8n HEF there.
3. `python scripts/fetch_assets.py coco` -> commit `data/coco/{subset_manifest.json,instances_val2017_subset500.json,MANIFEST.sha256}` and push (dataset identity is fixed BEFORE benchmarks).
4. Tick `environment-checklist.md`.

## 1. Pre-register (before any benchmark)
`python scripts/ceiling.py` -> fill `pre-registration/2026-11-xx-prereg.md` and `predictions.json` (copy of `predictions.template.json`, `frozen: true`). Commit, push, deposit on OSF/Zenodo. **No benchmark may run before this commit.**

## 2. Sessions (each = env capture + 10 min idle + sustained run; stops at steady state or 60 min)
Cold start each: shut the Pi down >=30 min, boot, SSH in, do not run anything else.
Add `--ambient-c <reading>` and your plug flags (`--power-source shelly-gen1 --power-url http://<ip>`; see `scripts/log_power.py`).

```
# Primary, PCIe Gen3: >=3 runs per mode
python scripts/run_session.py --mode model-only  --run 1 --ambient-c 21
python scripts/run_session.py --mode end-to-end  --run 1 --ambient-c 21
# ... runs 2 and 3 for each

# Synchronous latency (p95 prediction): 1 frame per call
python scripts/run_session.py --mode model-only --run 1 --tag latency-sync --frames-per-call 1 --duration 300 --fixed-duration --idle-seconds 120

# Secondary PCIe Gen2: set dtparam=pciex1_gen=2 in /boot/firmware/config.txt, reboot, confirm link, then:
python scripts/run_session.py --mode model-only --run 1 --tag pcie-gen2   # >=1, ideally 3
# restore Gen3 afterwards
```
Time budget: a full session is ~70 min; 6 primary sessions ~7 h.

## 3. Accuracy (Q-accuracy, not timing)
```
python scripts/eval_accuracy.py --backend hailo --model models/yolov8n_h8l.hef
python scripts/eval_accuracy.py --backend onnx  --model models/yolov8n.onnx --conf 0.25   # FP32 baseline (ONNX exported elsewhere)
```
## 4. Transformer check (Q5)
Compile DeiT-tiny / MobileViT with the Hailo Dataflow Compiler on an x86 Linux machine (not the Pi), then see the header of `scripts/check_transformer.py`.

## 5. Analyse
`python scripts/analyse.py` -> `results/tables/`, `results/figures/`, `results/scorecard.md`; write `results/gap-analysis.md`. Commit `data/raw/` untouched.

## Definitions / interpretations (fixed here; deviations go in deviations.md)
- 10 s warm-up discarded; "cold FPS" = mean over the 60 s after warm-up; "steady FPS" = mean over the last 10 min.
- Steady state: |temp slope| < 0.5 C/10 min and CV of 30 s-mean FPS < 2% over a 10 min window; checked every 30 s after `--min-run` (900 s).
- Throttle bits counted as thermal: 0x2 (freq capped), 0x4 (throttled), 0x8 (soft temp limit). 0x1 = under-voltage is reported separately (PSU problem, invalidates the run).
- Throughput runs use 8 frames per `infer()` call with device batch 1.
