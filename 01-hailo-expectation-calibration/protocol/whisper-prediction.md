# Whisper-tiny prediction (frozen 2026-11-15T17:58Z)

Model: openai/whisper-tiny (multilingual)
Audio: fixed set of short English clips (to be recorded/saved under data/raw/whisper/clips/)
Metric: real-time factor (RTF) = wall-clock processing time / audio duration
Secondary: word error rate (WER) vs reference transcripts

**CPU baseline (Pi 5, 4 threads, no HAT):**
- RTF mean: 2.5 (80% interval 1.8 – 3.5)
- WER: < 15% on clean short clips

**HAT (Hailo-8L via official speech_recognition pipeline, variant=tiny):**
- RTF mean: 0.8 (80% interval 0.5 – 1.3)
- WER: within 2 absolute points of CPU (or better)

**Success criteria for "HAT helps":** HAT RTF ≤ 50% of CPU RTF on the same clips (at least 3 repeats each).

Prediction committed before any Whisper install or measurement.
