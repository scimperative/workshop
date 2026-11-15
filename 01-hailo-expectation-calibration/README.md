# Workshop 01: Calibrating Expectations for Raspberry Pi 5 + Hailo AI HAT+

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
