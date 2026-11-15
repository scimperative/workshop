# Workshop 01 summary: is the Raspberry Pi AI HAT (Hailo-8L) good for AI?

Rig: Raspberry Pi 5 + Hailo-8L (HailoRT 4.20.0, firmware 4.20.0). Single device; no other hardware compared.

## Results

| Workload | Runs on HAT? | Result |
|---|---|---|
| YOLOv8n, 640x640, Mode A (model-only) | Yes | 107.4 FPS (3 cold-start runs) |
| YOLOv8n, Mode B (decode + inference + NMS) | Yes | 100.6 FPS; Mode B / Mode A = 0.94 |
| NPU utilisation (YOLOv8n, Mode A) | Yes | 7.2% of the rated 13 TOPS |
| Steady / cold FPS (Mode B) | Yes | 0.998 (no thermal throttling signature) |
| Llama-3.2-1B Q4_K_M via llama.cpp (4 CPU threads) | No (CPU only) | 14.3 tok/s generation, 88.1 tok/s prompt processing |
| DeiT-tiny (vision transformer) on the HAT | - | NOT TESTED (Hailo compiler needs an x86 machine; none available in this run) |

## Predictions scored

- YOLOv8n numeric: 4/4 intervals hit (pilot-informed, not blind; see protocol/deviations.md).
- Bottleneck call: predicted host CPU, measured NPU-side. Miss. PCIe Gen 2 vs Gen 3 sensitivity was not tested.
- LLM CPU baseline: 2/2 intervals hit (frozen before the run).
- Not measured, so not scored: energy per inference (both forms), power, p95 latency, transformer tier.

## Verdict (provisional)

- Good for what it is built for: CNN vision. About 100 FPS end-to-end for YOLOv8n is a strong result for a low-power add-on, and the pipeline did not throttle.
- Not a route to LLMs on this evidence: the LLM test ran on the Pi 5 CPU alone, because the HAT was not used for it. Hailo's LLM support is marketed for newer parts; this run did not test or verify that.
- Transformer support on the Hailo-8L is untested here, so the original claim that it is weak on transformers is neither supported nor refuted by this run.
- Only 7.2% of peak TOPS is used on the CNN workload. Headline TOPS is not a throughput number.

## Scope

One Pi 5, one Hailo-8L, HailoRT/firmware 4.20.0, one CNN model, one 1B LLM on CPU, one day (2026-11-15). Do not generalise to other Hailo products or toolchain versions.

## Whisper-tiny on the HAT vs the Pi CPU (PRELIMINARY; invalid for accuracy)

Prediction frozen before the run (`protocol/whisper-prediction.md`, commit 1188df7): CPU RTF 2.5 (1.8-3.5), HAT RTF 0.8 (0.5-1.3); "HAT helps" = HAT RTF at most 50% of CPU RTF over at least 3 repeats.

| Config | RTF per clip | Mean RTF | Prediction | Result |
|---|---|---|---|---|
| Pi CPU (`openai/whisper-tiny`, transformers) | 0.303, 0.301, 0.300 | 0.30 | 2.5 (1.8-3.5) | MISS (about 8x lower than predicted) |
| Pi + HAT (hailo-apps prebuilt Whisper-tiny HEFs, HailoRT 4.20.0) | 0.08, 0.40, 0.08 | 0.19 | 0.8 (0.5-1.3) | MISS (about 4x lower than predicted) |

- HAT RTF / CPU RTF = 0.62, so the "HAT helps" criterion (at most 0.50) was **not met**, although the HAT was about 1.6x faster on average.
- **Whisper-tiny runs on the Hailo-8L**, so the HAT is not CNN-only. Source: Hailo's prebuilt encoder/decoder HEFs.
- **Not valid yet:** the three clips are non-speech (tone-like, identical RMS), transcripts are hallucinations, clip 2's HAT time reflects a looping decoder, only one pass per clip was run (3 repeats required), and **no word error rate was measured**. Earlier text giving CPU RTF as 0.030 was a transcription error; the raw file says about 0.30.
- To fix: re-run with real speech clips with known transcripts, at least 3 repeats per clip, and compute WER for both configurations.
