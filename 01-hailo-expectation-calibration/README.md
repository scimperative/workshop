# Workshop 01: Calibrating Expectations for Raspberry Pi 5 + Hailo AI HAT+

## Status (2026-11-15): complete for the scope below

**Question:** is the Raspberry Pi AI HAT+ (Hailo-8L, 13 TOPS) good for AI? One device (Raspberry Pi 5 + HAT), several workloads, no other hardware.

| Workload | Runs on HAT? | Result |
|---|---|---|
| YOLOv8n 640x640, model-only | Yes | 107.4 FPS |
| YOLOv8n end-to-end (decode + NMS) | Yes | 100.6 FPS |
| NPU utilisation (YOLOv8n) | Yes | 7.2% of rated 13 TOPS |
| Llama-3.2-1B Q4_K_M (llama.cpp) | No, CPU only | 14.3 tok/s generation, 88.1 tok/s prompt processing |
| DeiT-tiny vision transformer | Not tested | Hailo compiler needs an x86 machine; none used in this run |

**Verdict (provisional):** good at CNN vision, and there is no evidence here that the HAT helps with LLMs. The LLM test ran on the CPU alone, and transformer support on the Hailo-8L was not tested.

**Read before citing:**
- The YOLOv8n predictions were set after pilot runs on the same rig, so the 4/4 interval hit rate is pilot-informed, not a blind forecast. The bottleneck call (predicted host CPU, measured NPU-side) was a miss.
- Energy, power and p95 latency were not measured. The PCIe Gen 2 vs Gen 3 test was not run.
- The pre-registration was tagged (`prereg-01`) after the YOLOv8n runs and has no independent deposit. See `protocol/deviations.md`.
- Scope: one Pi 5, one Hailo-8L, HailoRT/firmware 4.20.0. Do not generalise to other Hailo products.

Full write-up: `results/summary.md`. Scorecard: `results/scorecard.md`. Raw data: `data/raw/`.

Pre-registered measurement of YOLOv8n (640x640, INT8) on a Raspberry Pi 5 with the **AI HAT+ (Hailo-8L, 13 TOPS)**.
See `protocol/protocol.md` for the run procedure and `pre-registration/` for the frozen predictions.

> Note: 13 TOPS = **Hailo-8L**. The 26 TOPS AI HAT+ is Hailo-8. HEFs are chip-specific: use `hailo8l` HEFs here.

## Workflow
Laptop: `git init && git add . && git commit -m "Workshop 01 scaffold" && git remote add origin <url> && git push -u origin main`
Pi: `git clone <url> && cd <repo> && scripts/setup_pi.sh && source .venv/bin/activate`, then follow `protocol/protocol.md`.
Results: commit `data/raw/` + `results/` on the Pi, push, pull on the laptop.

## Test without hardware
`python scripts/smoke_test.py` (simulated backend + fake smart plug, ~1 min). Simulated runs are flagged and ignored by `analyse.py` unless `--allow-simulated`.

## Layout
- `config.json` model/chip constants (verify FLOPs!) | `scripts/ceiling.py` first-principles ceilings
- `scripts/bench.py` harness (Mode A/B) | `run_session.py` orchestrates env capture, idle baseline, loggers, run
- `log_thermal.py`, `log_power.py` (Shelly/Tasmota/generic HTTP), `env_check.sh`
- `fetch_assets.py` HEF + deterministic COCO-500 subset + hash | `eval_accuracy.py` | `check_transformer.py` | `analyse.py`

## Known limits
- Written against the HailoRT `InferVStreams` Python API (HailoRT 4.x). If `hailo_platform` imports fail or the API changed, only `scripts/hailo_backend.py` needs adapting.
- Mode B assumes a HEF with NMS output (model-zoo YOLO HEFs). Raw-output HEFs are flagged and post-processing is not timed.
- Power is mains-side from a smart plug; resolution and averaging are the plug's.
- The Hailo Dataflow Compiler (needed for Q5) runs on x86 Linux, not on the Pi.
