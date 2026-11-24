#!/bin/bash
# PulseBar launcher (uses ./.venv created by uv)
cd "$(dirname "$0")"

# Create ./.venv with uv if missing (system python3.12 + 3 deps)
if [ ! -x .venv/bin/python ]; then
  uv venv .venv --python /usr/bin/python3.12 || { echo "uv venv failed"; exit 1; }
  uv pip install --python .venv/bin/python psutil nvidia-ml-py python-xlib \
    || { echo "dependency install failed"; exit 1; }
fi

# Run first-time CPU power (RAPL) setup only when needed:
# powercap exists but energy_uj is unreadable (pkexec = auth dialog, else sudo).
# No-op when already readable. The bar starts even if this fails.
if [ -d /sys/class/powercap ]; then
  need=0
  for f in /sys/class/powercap/*/energy_uj; do
    [ -e "$f" ] || continue
    [ -r "$f" ] || need=1
  done
  if [ "$need" = 1 ]; then
    echo "RAPL energy_uj unreadable; running enable_cpu_power.sh (first time only; may ask for password)"
    pkexec ./enable_cpu_power.sh || sudo ./enable_cpu_power.sh \
      || echo "setup failed; starting without CPWR"
  fi
fi

exec .venv/bin/python PulseBar.py
