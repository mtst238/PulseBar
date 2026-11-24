#!/usr/bin/env bash
# PulseBar first-time setup: make CPU package power
# (/sys/class/powercap/intel-rapl:0/energy_uj) readable by normal users.
# Run once with sudo:  sudo ./enable_cpu_power.sh
# It is a udev rule, so it survives reboots.
set -u
[ "$(id -u)" = 0 ] || { echo "run with sudo: sudo $0"; exit 1; }

# On AMD machines enabled=1 may fail without the amd_atl module
if ! lsmod | grep -q "^amd_atl"; then
  if modprobe amd_atl 2>/dev/null; then
    echo 'amd_atl' > /etc/modules-load.d/pulsebar.conf
    echo "loaded amd_atl and set it to load on boot."
  else
    echo "(amd_atl not present on this machine; skipped)"
  fi
fi

RULE=/etc/udev/rules.d/99-pulsebar-rapl.rules
cat > "$RULE" <<'EOF'
# PulseBar: enable CPU package power monitoring and make energy_uj world-readable
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*", ATTR{enabled}="1", \
  RUN+="/bin/sh -c 'chmod 0444 /sys%p/energy_uj 2>/dev/null || :'"
EOF

udevadm control --reload
udevadm trigger --subsystem-match=powercap
sleep 1

echo "--- check ---"
ok=0
for f in /sys/class/powercap/intel-rapl:0/energy_uj; do
  en=$(cat "${f%energy_uj}enabled" 2>/dev/null)
  if head -c 20 "$f" >/dev/null 2>&1; then
    echo "OK: $f readable (enabled=$en, value=$(cat "$f"))"
    [ "$en" = "1" ] && ok=1
  else
    echo "NG: $f not readable (enabled=$en)"
  fi
done
if [ "$ok" = "1" ]; then
  echo "Restart PulseBar to enable CPWR."
else
  cat <<'EOF'
NG: could not set enabled=1.
Some boards require enabling "RAPL" / "Package power reporting" /
"Power Supply Sense" in UEFI(BIOS). Enable it and re-run this script.
EOF
  exit 2
fi
