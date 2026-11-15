#!/usr/bin/env bash
# One-time setup on the Raspberry Pi 5 (Raspberry Pi OS Bookworm, AI HAT+ fitted).
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v hailortcli >/dev/null 2>&1; then
  echo "HailoRT not installed. Run, then reboot and re-run this script:"
  echo "  sudo apt update && sudo apt full-upgrade -y && sudo apt install -y hailo-all"
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# --system-site-packages is REQUIRED: hailo_platform comes from the apt package python3-hailort.
if [ ! -d .venv ]; then
  uv venv --system-site-packages --python /usr/bin/python3 .venv
fi
uv sync --frozen --extra eval

.venv/bin/python - <<'PY'
import hailo_platform, numpy, cv2
print("hailo_platform OK, numpy", numpy.__version__, "cv2", cv2.__version__)
PY

echo; hailortcli fw-control identify || true
echo; echo "Next: source .venv/bin/activate && python scripts/fetch_assets.py hef && python scripts/fetch_assets.py coco"
