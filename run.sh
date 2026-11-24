#!/bin/bash
# PulseBar 起動用（uv で作った ./.venv を使う）
cd "$(dirname "$0")"

# ./.venv が無ければ uv で作成（Mint 同梱の python3.12、依存3つ）
if [ ! -x .venv/bin/python ]; then
  uv venv .venv --python /usr/bin/python3.12 || { echo "uv venv 作成失敗"; exit 1; }
  uv pip install --python .venv/bin/python psutil nvidia-ml-py python-xlib \
    || { echo "依存インストール失敗"; exit 1; }
fi

# CPU電力(RAPL)の初回設定を必要時のみ自動実行:
# powercap が存在するのに energy_uj が読めない時だけ enable_cpu_power.sh を
# 起動する（pkexec=認証窓、無ければ sudo が端末でパスワードを聞く）。
# 設定済み（読める）なら何もせず素通りする。失敗しても bar の起動は続ける。
if [ -d /sys/class/powercap ]; then
  need=0
  for f in /sys/class/powercap/*/energy_uj; do
    [ -e "$f" ] || continue
    [ -r "$f" ] || need=1
  done
  if [ "$need" = 1 ]; then
    echo "CPU電力(RAPL)が読めないため enable_cpu_power.sh を実行します（初回のみ。パスワードを聞かれることがあります）"
    pkexec ./enable_cpu_power.sh || sudo ./enable_cpu_power.sh \
      || echo "設定できなかったため CPWR なしで起動します"
  fi
fi

exec .venv/bin/python PulseBar.py
