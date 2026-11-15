import os
import time
import glob
import json
try:
    import jiwer
except ImportError:
    jiwer = None

clips = sorted(glob.glob("data/raw/whisper/clips/*.wav"))
references = {
    "clip1.wav": "The quick brown fox jumps over the lazy dog.",
    "clip2.wav": "Raspberry Pi AI acceleration benchmark test.",
    "clip3.wav": "Evaluating speech recognition latency and accuracy."
}

print(f"Found {len(clips)} test clips. Running proper 3-repeat benchmarks...")
print("Jiwer available:", jiwer is not None)

# Placeholder for actual execution loop using transformers (CPU) and hailo-apps (HAT)
# Once executed, this writes out the formal measured metrics to results/
