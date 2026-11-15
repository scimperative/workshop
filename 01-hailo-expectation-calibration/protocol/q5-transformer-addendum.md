# Q5 (transformer tier) addendum, written BEFORE any compile attempt
Logged 2026-11-15T17:12:15Z. This addendum does not change the frozen prediction (T0 in predictions.json, bd92298). It adds detail that file lacks. Values were chosen by the author on the day of writing; no transformer compile or run has been attempted.

- Model: DeiT-tiny, 224x224, batch 1 (exact source URL, commit and export command to be recorded at export).
- Stated probability for T0: 60%.
- T1: compile succeeds but more than 5% of ops run on the host CPU or the graph is split with host segments.
- T2: fully on the NPU, but utilisation below the T3 bar or INT8/FP32 top-1 agreement below 95%.
- T3: utilisation (measured ops/s divided by 13 TOPS) at least 0.0503 (70% of the YOLOv8n Mode A figure of 0.07185) AND INT8/FP32 top-1 agreement at least 95%.
- Accuracy is a proxy (INT8/FP32 agreement on the COCO-500 images), not ImageNet top-1. Labelled as such in results.
- Ops per inference is taken from the exported graph (MACs vs FLOPs stated explicitly).
- Scope: Hailo-8L, HailoRT 4.20.0, firmware 4.20.0, one model, one toolchain version. No generalisation.
