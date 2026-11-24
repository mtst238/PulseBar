#!/usr/bin/env bash
# PulseBar 初回設定: CPUパッケージ電力(RAPL: /sys/class/powercap/intel-rapl:0/energy_uj)を
# 一般ユーザーから読めるようにする。 sudo で1回だけ実行してください。
#   sudo ./enable_cpu_power.sh
# udevルールなので再起動後も有効です。
set -u
[ "$(id -u)" = 0 ] || { echo "sudo で実行してください: sudo $0"; exit 1; }

# AMD マシンでは amd_atl モジュールがないと enabled=1 にできないことがある
if ! lsmod | grep -q "^amd_atl"; then
  if modprobe amd_atl 2>/dev/null; then
    echo 'amd_atl' > /etc/modules-load.d/pulsebar.conf
    echo "amd_atl をロードし、次回起動からも読込むように設定しました。"
  else
    echo "（amd_atl はこのマシンに存在しないためスキップ）"
  fi
fi

RULE=/etc/udev/rules.d/99-pulsebar-rapl.rules
cat > "$RULE" <<'EOF'
# PulseBar: CPUパッケージ電力。計測を有効化し energy_uj を一般読み取り可に
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*", ATTR{enabled}="1", \
  RUN+="/bin/sh -c 'chmod 0444 /sys%p/energy_uj 2>/dev/null || :'"
EOF

udevadm control --reload
udevadm trigger --subsystem-match=powercap
sleep 1

echo "--- 確認 ---"
ok=0
for f in /sys/class/powercap/intel-rapl:0/energy_uj; do
  en=$(cat "${f%energy_uj}enabled" 2>/dev/null)
  if head -c 20 "$f" >/dev/null 2>&1; then
    echo "OK: $f 読み取り可 (enabled=$en, 現在値=$(cat "$f"))"
    [ "$en" = "1" ] && ok=1
  else
    echo "NG: $f が読めません (enabled=$en)"
  fi
done
if [ "$ok" = "1" ]; then
  echo "PulseBar を再起動すると CPWR が有効になります。"
else
  cat <<'EOF'
NG: enabled=1 にできませんでした。
UEFI(BIOS)設定に "RAPL" / "Package power reporting" / "Power Supply Sense"
等の項目があるマザーでは、そこで有効化が必要な場合があります。
有効化後にこのスクリプトを再実行してください。
EOF
  exit 2
fi
