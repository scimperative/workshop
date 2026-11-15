#!/usr/bin/env bash
# Environment capture for the pre-run checklist. Safe to run repeatedly; output goes to stdout.
set -u
sec() { echo; echo "== $1 =="; }
sec date;            date -u +%FT%TZ
sec uname;           uname -a
sec os-release;      grep -E '^(PRETTY_NAME|VERSION)=' /etc/os-release 2>/dev/null
sec pi-model;        tr -d '\0' < /proc/device-tree/model 2>/dev/null; echo
sec memory;          grep MemTotal /proc/meminfo
sec bootloader;      vcgencmd bootloader_version 2>&1 | head -3
sec config.txt;      grep -vE '^\s*(#|$)' /boot/firmware/config.txt 2>/dev/null
sec hailo-pci;       lspci -nn 2>/dev/null | grep -i -E 'hailo|1e60'
for d in /sys/bus/pci/devices/*; do
  if [ "$(cat $d/vendor 2>/dev/null)" = "0x1e60" ]; then
    echo "$d: speed=$(cat $d/current_link_speed) width=$(cat $d/current_link_width) (max $(cat $d/max_link_speed) x$(cat $d/max_link_width))"
  fi
done
sec hailortcli;      hailortcli --version 2>&1 | head -2
sec hailo-identify;  hailortcli fw-control identify 2>&1
sec hailo-packages;  dpkg -l 2>/dev/null | grep -i hailo | awk '{print $2, $3}'
sec governor;        cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | sort | uniq -c
sec throttled;       vcgencmd get_throttled 2>&1
sec soc-temp;        vcgencmd measure_temp 2>&1
sec fan;             for c in /sys/class/thermal/cooling_device*; do echo "$(cat $c/type 2>/dev/null) cur_state=$(cat $c/cur_state 2>/dev/null)"; done
sec running-services; systemctl list-units --type=service --state=running --no-legend 2>/dev/null | awk '{print $1}'
sec load;            uptime
sec python;          python3 --version; command -v uv >/dev/null && uv --version
sec git;             git -C "$(dirname "$0")/.." rev-parse HEAD 2>&1; git -C "$(dirname "$0")/.." status --porcelain 2>&1 | head -10
