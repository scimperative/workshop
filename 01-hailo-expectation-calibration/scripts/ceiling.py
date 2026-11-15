#!/usr/bin/env python3
"""First-principles ceilings to pre-register against. Edit config.json to change inputs."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

c = common.load_config()
flops, tops, sz = c["model_flops_per_inference"], c["rated_tops"], c["imgsz"]
peak = tops * 1e12 / flops
print(f"Variant {c['variant']}  rated {tops} TOPS  model {c['model_name']}@{sz}  {flops/1e9:.2f} GFLOPs/inference")
print(f"Compute ceiling at 100% utilisation: {peak:,.0f} FPS")
for u in (0.5, 0.25, 0.10, 0.05):
    print(f"  at {u*100:>4.0f}% utilisation: {peak*u:,.0f} FPS")
inp = sz * sz * 3
print(f"\nInput tensor: {inp/1e6:.2f} MB/frame (uint8). PCIe x1 nominal one-way bandwidth (80% efficiency assumed):")
for gen, gbs in (("Gen2", 0.5), ("Gen3", 0.985)):
    print(f"  {gen}: {gbs*0.8*1e9/inp:,.0f} FPS input-bound")
print("\nVerify FLOPs vs MACs (8.7 GFLOPs = ~4.35 GMACs) before pre-registering; the 13 TOPS figure counts 2 ops/MAC.")
