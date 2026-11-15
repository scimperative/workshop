# Per-session results

| session | mode | tag | dur (min) | stop | FPS steady | FPS cold | steady/cold | p50 ms | p95 ms | p99 ms | T max C | CPU % (tot/core) | throttle s | W idle | W load | J/inf total | J/inf idle-sub |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20261115T141127Z_model-only_main_run1 | model-only | main | 16.8 | completed | 107.4 | 107.7 | 0.997 | 28.50 | 32.10 | 35.00 | 52.1 | 14/23 | 0 | n/a | n/a | n/a | n/a |
| 20261115T143821Z_end-to-end_main_run1 | end-to-end | main | 14.6 | completed | 100.5 | 100.8 | 0.997 | 65.00 | 75.00 | 82.00 | 59.8 | 34/40 | 0 | n/a | n/a | n/a | n/a |
| 20261115T150900Z_model-only_main_run2 | model-only | main | 17.0 | steady_state | 107.1 | 107.7 | 0.995 | 284.01 | 284.34 | 284.45 | 51.6 | 15/24 | 0 | n/a | n/a | n/a | n/a |
| 20261115T153649Z_model-only_main_run3 | model-only | main | 15.5 | steady_state | 107.4 | 107.7 | 0.997 | 283.90 | 284.24 | 284.35 | 51.6 | 15/24 | 0 | n/a | n/a | n/a | n/a |
| 20261115T160308Z_end-to-end_main_run2 | end-to-end | main | 18.0 | steady_state | 100.7 | 100.8 | 0.999 | 336.37 | 641.24 | 684.78 | 60.4 | 34/39 | 0 | n/a | n/a | n/a | n/a |
| 20261115T163157Z_end-to-end_main_run3 | end-to-end | main | 16.0 | steady_state | 100.6 | 100.8 | 0.998 | 338.92 | 650.91 | 692.82 | 59.8 | 34/39 | 0 | n/a | n/a | n/a | n/a |

# Group medians (across repetitions)

| mode | tag | runs | FPS steady (min-max) | J/inf total | steady/cold |
|---|---|---|---|---|---|
| end-to-end | main | 3 | 100.6 (100.5-100.7) | n/a | 0.998 |
| model-only | main | 3 | 107.4 (107.1-107.4) | n/a | 0.997 |
