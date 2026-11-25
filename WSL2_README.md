# PulseBar on WSL2（簡易メモ）

詳細は `PulseBar.py` の docstring（WSL2 対応・メニュー方式の節）参照。

- 前提: Win11 + WSLg（既定の有効化済み WSL2）。古かったら `wsl --update` して `wsl --shutdown` から起動し直し。
- このフォルダを WSL の `~/` 等に置き、`./run.sh`（venv 自動作成。python は 3.12→3.11→3 の順で探す）。
- センサーは WSL 内から見えるものだけ。GPU=WSLg の NVML が使えれば GPU 項目可。
  CPU温度/SSD温度/CPU電力(powercap)は通常見えず、自動で選択不可（off）になる。
- 環境変数:
  - `PB_PLATFORM=wsl|native` … WSL 判定の手動上書き（既定は自動判定）。
  - `PB_MENU=auto|popup|inline` … メニュー方式（既定 auto = WSL では inline、native では従来 popup）。
- 自己診断: WSL2 上で `./.venv/bin/python wsl_selftest.py`（PASS/FAIL 一行ずつ。環境差异 FAIL は許容）。
- WSL ではドック（パネル帯埋め込み）はしない。常にガジェット（最前面無管理窓）として出る。config.json の mode は書き換わらない。
