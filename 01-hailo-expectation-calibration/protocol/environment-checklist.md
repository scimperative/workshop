# Environment checklist (tick before every session; `scripts/env_check.sh` captures the evidence into each session's env.txt)

- [ ] Pi 5 with official Active Cooler; AI HAT+ seated; official 5V/5A PSU
- [ ] `hailortcli fw-control identify` shows **HAILO8L** (13 TOPS) and the expected firmware
- [ ] `/boot/firmware/config.txt`: `dtparam=pciex1` and `dtparam=pciex1_gen=3` (Gen3 runs) / `=2` (Gen2 runs); rebooted after change
- [ ] Hailo PCIe link confirmed: `cat /sys/bus/pci/devices/*/current_link_speed` (device with vendor 0x1e60) shows 8.0 GT/s (Gen3) or 5.0 GT/s (Gen2)
- [ ] Headless over SSH; no desktop session; nothing else running (`systemctl list-units --state=running`)
- [ ] Same surface/orientation/airflow as previous runs; ambient temperature read and noted
- [ ] `git status` clean and commit hash recorded; `uv.lock` unmodified; kernel/hailort versions unchanged since pre-registration
- [ ] Pre-registration frozen, pushed and deposited BEFORE the first benchmark
- [ ] `python scripts/fetch_assets.py verify` passes (dataset identity)
- [ ] Smart plug logging verified (`curl` the plug URL; value changes with load)
- [ ] Cold start: Pi shut down >=30 min, powered on, SoC temp within a few C of ambient (script records it)
