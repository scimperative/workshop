# Workshop 01 Summary: Whisper-tiny on Pi CPU vs Hailo-8L

- **Model**: Whisper-tiny
- **Hardware**: Raspberry Pi 5 + Hailo-8L (AI HAT+)
- **CPU RTF (avg)**: 0.030
- **HAT RTF (avg)**: 0.185
- **Prediction Met**: HAT RTF ≤ 50% of CPU RTF was not met in terms of absolute speedup due to overhead, but both run successfully under real-time factor (< 1.0).
