# Scorecard

Generated from 6 session(s). Prediction file git commit should predate all runs.

**Read this first**

- Numeric: 4/4 intervals hit. Categorical: 0/1 hit (Q2 bottleneck is a miss; see Q2 evidence below). The numeric hit rate is not the whole result.
- 5 predictions have no measurement and are not scored: q3_energy_total_j_per_inf_mode_b, q3_energy_idle_sub_j_per_inf_mode_b, q5_transformer_tier, power_w_mode_b, latency_p95_ms_mode_a_sync.
- The numerical predictions were set after pilot runs on this same rig: this is a pilot-informed calibration, not a blind forecast. See protocol/deviations.md.
- The pre-registration tag (prereg-01) was created after the runs; the independent deposit is retrospective. See protocol/deviations.md.

| metric | predicted (80% interval) | measured | hit | log10 error |
|---|---|---|---|---|
| q1_fps_mode_a | 108 (102-114) | 107.4 | YES | -0.003 |
| q1_fps_mode_b | 99 (93-105) | 100.6 | YES | +0.007 |
| q2_bottleneck_mode_b | host_cpu | npu | NO | - |
| q3_energy_total_j_per_inf_mode_b | - | - | no measurement | - |
| q3_energy_idle_sub_j_per_inf_mode_b | - | - | no measurement | - |
| q4_fps_ratio_steady_over_cold_mode_b | 0.98 (0.92-1.02) | 0.9984 | YES | +0.008 |
| q5_transformer_tier | - | - | no measurement | - |
| q6_npu_utilization_mode_a | 0.072 (0.06-0.09) | 0.07185 | YES | -0.001 |
| power_w_mode_b | - | - | no measurement | - |
| latency_p95_ms_mode_a_sync | - | - | no measurement | - |

Numeric interval hit rate: 100% (4/4); target ~80%.
Mean absolute log10 error: 0.005  (0.1 = 26% off, 0.3 = 2x off)
Categorical hits: 0/1

Q2 evidence:
- Mode B/Mode A FPS = 0.94; Mode B CPU total 34%, busiest core 39%
- no pcie-gen2 model-only runs: PCIe sensitivity untested
- no thermal/CPU/PCIe signature found => device-side (NPU/compiler mapping)
