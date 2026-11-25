#!/bin/bash
# PulseBar launcher (uses ./.venv created by uv)
cd "$(dirname "$0")"

# Find a usable system python (WSL images often lack 3.12; prefer newest).
find_python() {
  for p in python3.12 python3.11 python3; do
    if command -v "$p" >/dev/null 2>&1; then echo "$p"; return 0; fi
  done
  return 1
}

# Create ./.venv with uv if missing (found system python + 3 deps)
if [ ! -x .venv/bin/python ]; then
  PY="$(find_python)" || { echo "no python3 found"; exit 1; }
  uv venv .venv --python "$PY" || { echo "uv venv failed"; exit 1; }
  uv pip install --python .venv/bin/python psutil nvidia-ml-py python-xlib \
    || { echo "dependency install failed"; exit 1; }
fi

# WSL: CPU power (RAPL/powercap) is not exposed to the guest; skip setup.
if grep -qi microsoft /proc/version 2>/dev/null; then
  echo "WSL detected; skipping RAPL/powercap setup (CPWR not available)"
elif [ -d /sys/class/powercap ]; then
  # Run first-time CPU power (RAPL) setup only when needed:
  # powercap exists but energy_uj is unreadable (pkexec = auth dialog, else sudo).
  # No-op when already readable. The bar starts even if this fails.
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
