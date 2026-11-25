#!/usr/bin/env python3
"""PulseBar: CPU/GPU/メモリ/VRAM の使用率・電力・温度をコンパクトに監視するデスクトップガジェット。

仕様（正本はこの docstring）:
  - 監視項目（config.json の "items" で表示/非表示を選ぶ。既定の "order" は
      系統別グループ: CPU系(cpu load cfrg cpupower cputemp) /
      GPU系(gpu gclk power temp fan) / メモリ系(ram memtemp vram) /
      転送・ストレージ(net disk ssdtemp)）:
      cpu=CPU使用率, gpu=GPU使用率, ram=メモリ使用率, vram=VRAM使用率,
      power=GPU電力(W), temp=GPU温度(℃), cputemp=CPU温度(℃, k10temp/coretemp),
      cpupower=CPUパッケージ電力(W, RAPL=powercap energy_uj差分。有効化には
      enable_cpu_power.sh を sudo で1回実行。run.sh は energy_uj が読めない時
      だけ自動で pkexec/sudo 起動する)。
      fan=GPUファン回転(%, NVML FanSpeed の全デバイス max。既定 off)。
      cfrg=CPU周波数(内部MHz, psutil cpu_freq。表示は GHz に換算し '2.9G' 形式
      固定（disp_div。ラベル接尾 G）。既定 off)。
      net=ネットワークスループット(MB/s, sent+recv の1秒差分。既定 off)。
      disk=ディスクI/Oスループット(MB/s, read+write の1秒差分。既定 off)。
      ssdtemp=SSD温度(℃, nvme Composite 優先/無ければ hwmon nvme temp1_input。
      既定 off)。
      gclk=GPU SM周波数(内部MHz, NVML ClockInfo SM の全デバイス max。表示は
      GHz 換算 '2.9G'（disp_div。ラベル接尾 G）。既定 off)。
      load=CPUロードアベレージ(1分値, os.getloadavg。既定 off)。
      memtemp=メモリ(DIMM)温度(℃, hwmon spd5118 の temp1_input 全モジュール
      max。表示ラベル MTMP。既定 off)。
      NVIDIA GPU がない場合は cpu/ram/cputemp/cpupower/cfrg/net/disk/load/
      memtemp のみ選択可。センサーが無い項目は選択不可。
  - 1項目1セルで「上段=ラベル+現在値 / 下段=波形」を並べる。
    数値=今の値を正確に読むため、波形=過去からの推移を直感的に把握するため。
    波形線から波形帯下端までは水平帯分割+色ブレンドの縦グラデで塗り、
    線付近が濃く下端で背景色に溶ける（塗り色は波形線と同じ負荷色に追随）。
  - 更新間隔 1 秒、波形の表示範囲は約 60 秒（リングバッファ HISTORY 点）。
  - 波形の縦スケール: %系と温度は 0-100 固定。電力はバッファ内の最大値と
    POWER_FLOOR の大きい方で自動スケール。同じ自動スケール機構を CPU周波数
    (下限 CFRG_FLOOR=1000MHz) とネット/ディスクスループット
    (下限 IO_FLOOR=10MB/s) にも使う。
  - 高負荷の強調: 値が warn 超で数値・波形・セル枠が警告色(橙)、crit 超で危険色(赤)。
      cpu/gpu/ram: warn 80% crit 93% / vram: warn 90% crit 95% /
      temp: warn 75℃ crit 88℃ / power: GPU電力上限の warn 80% crit 95%。
  - 表示モード（config.json の "mode"）:
      gadget = 画面前面に浮かぶコンパクトバー。左ドラッグで移動、位置は
               config.json の geometry に保存。
               "orient": "h"=セル横1列 / "v"=セル縦1列。
               "topmost": true/false で積層の方針を選ぶ。
               true  = 最前面固定（override-redirect で全ウィンドウの上）。
               false = アクティブ順。他のアプリと同じ扱いで、後からアクティブに
                       した窓に覆われる。覆われたバーの露出端やバー本体をクリック
                       すると前面へ出る（実測: muffin は override-redirect を常に
                       最前面へ回すため、この挙動には WM管理+飾りなしが必要）。
               前面固定時、バーがパネル帯に重なる場合は「ポインタがバー矩形上に
               あり帯のオーバレイ窓(幽霊窓)が入力を握っている間だけ」帯の窓の直上へ
               積層を作り直し、クリックが取れるようにする（無条件の毎tick再主張は
               Cinnamon のホバー・ポップアップを打ち消すため廃止。代償として他窓に
               覆われた直後はマウスがバーに乗るまで1tick遅れで前面化される）。
      dock   = 下端パネル帯の中に同一高さで埋め込む（帯の上端にドッキングし、
               帯の高さ＝自動高さで帯の内側に収まる）。帯のアプリレットと
               重ならない位置は dock_offset_x で調整。帯のポインタ入力は
               コンポジタ(Cinnamon stage窓)が握るが、必要時の積層再主張
               （maybe_reassert_stack + 幽霊窓検出）で入力を取れる。常に横1列。
               X11 の DOCK タイプを設定（STRUT は予約しない＝作業領域を変えない）。
               dock_auto=true（既定）なら dock_offset_x を使わず、Cinnamon の
               D-BusEval で測る帯右側アプレット群の直前（余白6px）にバー幅で
               右寄せ自動配置（起動時と5秒ごとに再計算、失敗時は最後の位置維持）。
  - 操作: 右クリックでメニュー（項目名は英語）。
      左ドラッグ: ドック時は常に、ガジェット時は上段（ラベル/数値行）プレス時に、
      押下点真下の最前面の他ウィンドウ（WM管理フレーム。自分/override-redirect/
      パネル・デスクトップ系は除外）を探して窓と一緒にドラッグで動かす。対象が
      無ければ従来動作。ガジェットの波形帯領域プレス時はバー自身を動かす（従来どおり）。
      中クリック: バー下の窓を前面へ巡回（重なった窓の選択）。押下点と交差する
      WM管理窓を積層順に列挙し最背面を前面へ raise（_NET_ACTIVE_WINDOW→フレーム
      Above の順）。連続クリックで候補が巡回し、直後にその窓が左ドラッグ対象になる。
      Layout: いま出ていない方へ切替のみ（ガジェット中は "Dock"、
            パネル中は "Gadget"。現在の表示形式の選択肢は出さない）。
            以下はガジェット時のみ: "Always on top" と、配置の切り替え先のみ
            （横配置中は "Vertical"、縦配置中は "Horizontal"）。
      Show/Hide: 表示中なら "Hide <name>"、非表示なら "Show <name>"
             （最後の1項目は非表示にできない）。
      "Quit"。外部からも `kill -USR1 <pid>` で gadget/dock 切替。Esc で終了。
  - config.json キー: mode(gadget|dock), items(項目キー->true/false),
      order(表示順: 項目キーの並べ替えで表示位置を変える。右クリックメニューでは
      変更せずこのファイルを編集する), topmost, orient(h|v),
      dock_auto(dock で true=既定: 帯右側アプレット群の直前に自動右寄せ。
      false: dock_offset_x 固定),
      dock_offset_x(プライマリモニタ左端からのオフセット px),
      dock_height(0=パネル帯の高さに自動（PANEL_H が取れない環境のみセル高さ既定40）、
      下限34), geometry(gadget の [x,y])。
  - 対応OS: Linux (X11)。動作確認済みは Linux Mint 22.3 (Cinnamon/muffin) のみ。
    他ディストリビューションでは未検証。Windows は非対応（撤去）。Wayland 未対応。
  - GPU は NVML の全デバイスを1系統に集計して表示する
    （使用率=max, VRAM=合計使用/合計搭載, 電力=合計, 温度=max）。
    検証用フック: PULSEBAR_NO_GPU=1 / PULSEBAR_NO_SENSORS=1 で GPU無し・
    センサー無し構成を再現できる。
  - WSL2 (WSLg) 対応: /proc/version に microsoft または環境変数
    WSL_DISTRO_NAME があれば WSL 判定（環境変数 PB_PLATFORM=wsl|native で
    手動上書き可。結果は IS_WSL）。IS_WSL 時は mode 設定によらず常に
    ガジェット扱い（ドック計算・gdbus/cinnamon_panel_bounds は呼ばない。
    config.json の mode は書き換えない）。overrideredirect(True) +
    attributes('-topmost',True) の無管理窓を geometry でマップ前に配置し、
    以後の Xlib 積層操作（maybe_reassert_stack / raise_or_below /
    restack_above_stage / set_window_role / apply_motif_nodecor /
    request_skip_taskbar / clear_dock_role / 裏窓ドラッグの窓ピッキング）は
    入口で no-op。Cinnamon 専用の幽霊窓戦法は WSLg では誤作動するため。
    ドラッグ（B1-Motion）と Esc 終了は従来通り。センサーは WSL 側から
    見えるものだけ（GPU=WSLg の NVML。CPU温度/SSD温度/powercap は通常
    見えず、no_sensor 扱いで自動選択不可になる）。概要は WSL2_README.md、
    WSL 上の接続検証は wsl_selftest.py。
  - メニュー方式（環境変数 PB_MENU=auto|popup|inline、既定 auto）:
      popup = tk_popup で別ポップアップ窓（native 従来方式）。
      inline = バー窓自身を縦/横に拡張し同一 canvas 上に面板を描く
        （別窓を作らない。他アプリの grab 妨害に強く WSLg 推奨。バー中心が
        画面下半分/右半分なら上/左、逆なら下/右へ拡張。項目構成は popup 版と
        同一: Layout 切替・Always on top・縦横・Items Show/Hide・Quit）。
        展開中は別 Xlib 接続で root に pointer+keyboard grab を張り
        （grab 失敗時は focus_force + Tk バインディングにフォールバック）、
        面板外クリック/再右クリック/Esc で閉じる。Esc は展開中=閉じる、
        閉じている=終了。auto は native=popup / WSL=inline。native でも
        PB_MENU=inline で同経路を試せる。WSL でも PB_MENU=popup で従来
        ポップアップが使える。
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
from collections import deque

import tkinter as tk
import tkinter.font as tkfont
from tkinter import Menu

import psutil

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DEFAULT_CONFIG = {
    "mode": "gadget",
    "items": {"cpu": True, "gpu": True, "ram": True, "vram": True, "power": True,
              "cpupower": True, "temp": True, "cputemp": True,
              "fan": False, "cfrg": False, "net": False, "disk": False,
              "ssdtemp": False, "gclk": False, "load": False, "memtemp": False},
    "order": ["cpu", "load", "cfrg", "cpupower", "cputemp",
              "gpu", "gclk", "power", "temp", "fan",
              "ram", "memtemp", "vram",
              "net", "disk", "ssdtemp"],
    "topmost": True,
    "orient": "h",
    "dock_auto": True,
    "dock_offset_x": 0,
    "dock_height": 0,
    "geometry": None,
}

try:
    import pynvml
    pynvml.nvmlInit()
    # マルチGPU対応: 全デバイスを収集し、集計して1系統として表示する
    #   gpu使用率=max, vram=sum(used)/sum(total), 電力=sum, 温度=max
    GPUS = [pynvml.nvmlDeviceGetHandleByIndex(i)
            for i in range(pynvml.nvmlDeviceGetCount())]
except Exception:
    GPUS = []

# 検証フック: PULSEBAR_NO_GPU=1 で「GPUが無いPC」、
# PULSEBAR_NO_SENSORS=1 で「GPU/CPU温度/CPU電力センサー全て無し構成」を模す。
if os.environ.get("PULSEBAR_NO_GPU") or os.environ.get("PULSEBAR_NO_SENSORS"):
    GPUS = []


def find_cpu_temp_chip():
    """CPU ダイ温度の (チップ名, センサーlabel) を探す（AMD=k10temp/Tctl,
    Intel=coretemp/Tdie Package）。見つからなければ None。"""
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None
    for chip in ("k10temp", "coretemp", "zenpower"):
        entries = temps.get(chip)
        if not entries:
            continue
        for e in entries:
            lab = e.label or ""
            if lab in ("Tctl", "Tdie", "Package id 0", "Tdie Package", ""):
                return chip, lab
    return None


CPU_CHIP = find_cpu_temp_chip()  # ("k10temp","Tctl") 等 / 無ければ None
if os.environ.get("PULSEBAR_NO_SENSORS"):
    CPU_CHIP = None  # 検証フック: CPU温度センサー無し構成を模す


def find_cpu_power_source():
    """CPU パッケージ電力の読み出し経路を返す。
    1) hwmon の power1_input (amd_energy / k10temp 等, 単位 µW)
    2) powercap の energy_uj (RAPL 系, エネルギー積算から 1 秒差分を W に換算)
    見つからなければ None。"""
    import glob
    # 1) hwmon power1_input
    for d in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        try:
            name = open(d + "/name").read().strip()
            v = int(open(d + "/power1_input").read().strip())
            if v > 0:
                return ("hwmon", d, name)
        except (OSError, ValueError):
            continue
    # 2) powercap energy_uj（読み取れる場合のみ）
    for d in sorted(glob.glob("/sys/class/powercap/*")):
        if ":" not in os.path.basename(d) and "rapl" not in os.path.basename(d):
            continue
        try:
            open(d + "/energy_uj").read()
            return ("rapl", d, "package")
        except OSError:
            continue
    return None


CPU_POWER = find_cpu_power_source()
if os.environ.get("PULSEBAR_NO_SENSORS"):
    CPU_POWER = None  # 検証フック: CPU電力センサー無し構成を模す
CPU_POWER_LAST = [0, 0.0]  # [energy_uj 前値秒, 前値uJ] (rapl 用)


def find_ssd_temp_source():
    """SSD温度の読み出し経路を返す。
    1) psutil.sensors_temperatures()['nvme'] の Composite（label が Composite か
       label 空で "Composite" を含むもの）
    2) /sys/class/hwmon/*/name が nvme の temp1_input (m℃)
    見つからなければ None。"""
    import glob
    if not os.environ.get("PULSEBAR_NO_SENSORS"):
        try:
            entries = psutil.sensors_temperatures().get("nvme") or []
        except Exception:
            entries = []
        for e in entries:
            lab = e.label or ""
            if lab == "Composite" or "Composite" in lab or lab == "":
                return ("psutil", lab)  # tick毎に nvme から読み直す（label で照合）
    if not os.environ.get("PULSEBAR_NO_SENSORS"):
        for d in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
            try:
                if open(d + "/name").read().strip() != "nvme":
                    continue
                v = int(open(d + "/temp1_input").read().strip())
                if v > 0:
                    return ("hwmon", d)
            except (OSError, ValueError):
                continue
    return None


SSD_TEMP = find_ssd_temp_source()


def find_dimm_temp_sources():
    """メモリ(DIMM)温度の読み出し経路: /sys/class/hwmon/*/name が spd5118 の
    ディレクトリ一覧（temp1_input は m℃）。1つも無ければ []。"""
    import glob
    if os.environ.get("PULSEBAR_NO_SENSORS"):
        return []
    out = []
    for d in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        try:
            if open(d + "/name").read().strip() == "spd5118":
                int(open(d + "/temp1_input").read().strip())  # 読めることだけ確認
                out.append(d)
        except (OSError, ValueError):
            continue
    return out


DIMM_SENSORS = find_dimm_temp_sources()

INTERVAL_MS = 1000        # 更新間隔
_PB_DEBUG = bool(os.environ.get("PB_DEBUG"))   # 積層再主張のデバッグ出力
HISTORY = 60              # 波形点数（=約60秒分）
POWER_FLOOR = 100.0       # 電力スケールの下限 (W)
CFRG_FLOOR = 1000.0       # CPU周波数スケールの下限 (MHz)
GCLK_FLOOR = 500.0        # GPU SM周波数スケールの下限 (MHz)
IO_FLOOR = 10.0           # ネット/ディスクI/Oスケールの下限 (MB/s)
MB = 1024.0 * 1024.0      # 1MB

NET_LAST = [0.0, 0]       # [前値秒, 前値(sent+recv bytes)] (net_io_counters 差分用)
DISK_LAST = [0.0, 0]      # [前値秒, 前値(read+write bytes)] (disk_io_counters 差分用)

PAD = 6
CELL_W = 60               # 1セルの幅
_DRAG_DEBUG = bool(os.environ.get("PULSEBAR_DRAG_DEBUG"))
CELL_H = 40               # 1セルの高さ（gadget 用）

BG = "#15171c"
FG = "#d8dee9"
OK = "#8f97a7"       # 通常時の描画色（項目固有色ではなく負荷段階で色分けするため）
GRID = "#2a2e37"
WARN = "#ffb86c"   # warn 超
CRIT = "#ff4444"   # crit 超

PANEL_H = 0               # 起動時に測った下端パネルの高さ


def detect_wsl():
    """/proc/version に microsoft または WSL_DISTRO_NAME 環境変数 -> WSL。
    環境変数 PB_PLATFORM=wsl|native で手動上書き（native 機で WSL 経路を
    検証するためのフックも含む）。"""
    ov = os.environ.get("PB_PLATFORM", "").strip().lower()
    if ov in ("wsl", "native"):
        return ov == "wsl"
    try:
        with open("/proc/version") as f:
            if "microsoft" in f.read().lower():
                return True
    except OSError:
        pass
    return bool(os.environ.get("WSL_DISTRO_NAME"))


IS_WSL = detect_wsl()


def resolve_menu_mode():
    """PB_MENU=auto|popup|inline。auto: WSL=inline / native=popup（従来）。"""
    v = os.environ.get("PB_MENU", "auto").strip().lower()
    if v not in ("auto", "popup", "inline"):
        v = "auto"
    return ("inline" if IS_WSL else "popup") if v == "auto" else v


MENU_MODE = resolve_menu_mode()   # Bar 生成時に参照（環境変数は起動時固定）

# インラインメニュー（同一窓面板）の寸定数
MENU_ROW_H = 18           # 項目1行の高さ
MENU_HDR_H = 16           # グループ見出し1行の高さ
MENU_SEP_H = 7            # 区切り線の高さ
MENU_PAD = 5              # 面板の内側余白
MENU_W_MIN = 176          # 面板の最小幅


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    cfg["items"] = dict(DEFAULT_CONFIG["items"])
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        for k, v in data.items():
            if k == "items" and isinstance(v, dict):
                cfg["items"].update({ik: iv for ik, iv in v.items() if ik in cfg["items"]})
            elif k in cfg:
                cfg[k] = v
            else:
                # DEFAULT_CONFIG に無いキーでも保持する（過去に geometry 消失事件：
                # 未知キーを保存時に落とすとユーザー設定が消える）
                cfg[k] = v
    except Exception:
        pass
    if cfg.get("mode") == "float":
        cfg["mode"] = "gadget"  # 旧設定名
    # order: 未知キー除去 + 新項目は末尾に補う（未設定なら DEFAULT の順）
    keys = list(DEFAULT_CONFIG["items"])
    cur = cfg.get("order") or DEFAULT_CONFIG["order"]
    cfg["order"] = [k for k in cur if k in keys] + \
                   [k for k in keys if k not in cur]
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


class Metric:
    def __init__(self, key, label, unit, color, fmt="{:.0f}", gpu_only=False,
                 warn=None, crit=None):
        self.key = key
        self.label = label
        self.unit = unit
        self.color = color
        self.fmt = fmt
        self.gpu_only = gpu_only
        self.warn = warn          # これ超で警告色（None=無効）
        self.crit = crit          # これ超で危険色
        self.buf = deque([0.0] * HISTORY, maxlen=HISTORY)
        self.fixed_max = 100.0  # %系と温度は0-100固定、電力・周波数・S/I/OはNoneで自動スケール
        self.floor = POWER_FLOOR  # 自動スケール時のスケール下限（項目ごとに設定）
        self.compact_g = False    # MB/s系: 1000超で GB/s に繰り上げ '1.2G' 表示
        self.disp_div = 1.0       # 表示のみ除算（周波数を MHz->GHz で '2.9G' 表示等）
        self.no_sensor = False  # このPCにセンサーが無い（表示不可）

    def unavailable(self):
        return (self.gpu_only and not GPUS) or self.no_sensor

    def level(self):
        """現在値の負荷段階: 0=通常 1=警告 2=危険。"""
        v = self.buf[-1]
        if self.crit is not None and v >= self.crit:
            return 2
        if self.warn is not None and v >= self.warn:
            return 1
        return 0

    def ui_color(self):
        """描画色は負荷段階のみで決める（項目固有色は背景の淡色にのみ使う）。"""
        lv = self.level()
        return CRIT if lv == 2 else WARN if lv == 1 else OK

    def push(self, v):
        self.buf.append(v)

    def value_text(self):
        v = self.buf[-1]
        if v is None:
            return "--"
        if self.compact_g and v >= 1000.0:
            return "{:.1f}G".format(v / 1000.0)  # MB/s -> GB/s 繰り上げ
        return self.fmt.format(v / self.disp_div) + self.unit

    def polyline(self, gx0, gx1, top, bot):
        span = bot - top - 2
        vmax = self.fixed_max if self.fixed_max else max(max(self.buf), self.floor)
        pts = []
        for j, v in enumerate(self.buf):
            x = gx0 + (gx1 - gx0) * j / (HISTORY - 1)
            y = bot - 1 - span * min(max(v / vmax, 0.0), 1.0)
            pts += [x, y]
        return pts


def fill_bands(pts, top, bot, bands=8):
    """折れ線頂点 pts=[x0,y0,x1,y1,...] から下端 bot までの塗り帯を
    上端側から順に返す。各帯は水平帯 [ya,yb] に対し「線 y を [ya,yb] に
    クリップした上面境界 + 帯下端 yb」の多角形頂点リスト。折れ線が帯より
    上に出る/下に入る部分も矩形化されず正しく欠ける。"""
    xs, ys = pts[0::2], pts[1::2]
    step = (bot - top) / bands
    out = []
    for k in range(bands):
        ya = top + step * k
        yb = ya + step
        poly = []
        for x, y in zip(xs, ys):
            poly += [x, min(max(y, ya), yb)]
        for x in reversed(xs):
            poly += [x, yb]
        out.append(poly)
    return out


def blend(c1, c2, t):
    """#rrggbb 2色を t 割で混ぜた色を返す（背景の下色作り用）。"""
    a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(x * (1 - t) + y * t) for x, y in zip(a, b))


def power_limits():
    """GPU の電力上限合計 (W)。全デバイスから取得、取れなければ None。"""
    if not GPUS:
        return None
    total = None
    for gpu in GPUS:
        for fn in (pynvml.nvmlDeviceGetPowerManagementLimit,
                   pynvml.nvmlDeviceGetEnforcedPowerLimit):
            try:
                w = fn(gpu) / 1e3  # mW -> W
                if w > 0:
                    total = (total or 0.0) + w
                    break
            except Exception:
                continue
    return total


def build_metrics():
    plim = power_limits()
    mets = {
        "cpu": Metric("cpu", "CPU", "%", "#88c0d0", warn=80, crit=93),
        "gpu": Metric("gpu", "GPU", "%", "#ebcb8b", gpu_only=True, warn=80, crit=93),
        "ram": Metric("ram", "RAM", "%", "#a3be8c", warn=80, crit=93),
        "vram": Metric("vram", "VRAM", "%", "#b48ead", gpu_only=True, warn=90, crit=95),
        "power": Metric("power", "GPWR", "W", "#d08770", gpu_only=True,
                        warn=None if plim is None else plim * 0.80,
                        crit=None if plim is None else plim * 0.95),
        "temp": Metric("temp", "GTMP", "C", "#bf616a", gpu_only=True, warn=75, crit=88),
        "cputemp": Metric("cputemp", "CTMP", "C", "#5e81ac", warn=80, crit=95),
        "cpupower": Metric("cpupower", "CPWR", "W", "#e3738c",
                           warn=90, crit=140),
        "fan": Metric("fan", "FAN", "%", "#8fbcbb", gpu_only=True,
                      warn=70, crit=90),
        "cfrg": Metric("cfrg", "CFRG", "G", "#81a1c1", fmt="{:.1f}"),
        "net": Metric("net", "NET", "M", "#57c7a5"),
        "disk": Metric("disk", "DISK", "M", "#d8973c"),
        "ssdtemp": Metric("ssdtemp", "STMP", "C", "#e8e060", warn=65, crit=75),
        "gclk": Metric("gclk", "GCLK", "G", "#7ea9d6", gpu_only=True,
                       fmt="{:.1f}"),
        "load": Metric("load", "LOAD", "", "#c0ca89", fmt="{:.1f}",
                       warn=2.0 * (os.cpu_count() or 8),
                       crit=3.0 * (os.cpu_count() or 8)),
        "memtemp": Metric("memtemp", "MTMP", "C", "#a0c4b8", warn=75, crit=85),
    }
    if CPU_CHIP is None:
        mets["cputemp"].no_sensor = True  # CPU温度センサーが無い場合は選択不可扱い
    else:
        mets["cputemp"].chip, mets["cputemp"].tlabel = CPU_CHIP
    if CPU_POWER is None:
        mets["cpupower"].no_sensor = True  # CPU電力センサーが無い場合は選択不可扱い
    else:
        mets["cpupower"].fixed_max = None  # CPU電力も自動スケール
    if SSD_TEMP is None:
        mets["ssdtemp"].no_sensor = True  # SSD温度センサーが無い場合は選択不可扱い
    else:
        mets["ssdtemp"].kind, mets["ssdtemp"].spath = SSD_TEMP
    mets["power"].fixed_max = None  # 電力のみ自動スケール
    # 周波数とスループットは 0-100 固定に収まらないので電力と同じ自動スケール
    # （バッファ最大値と floor の大きい方でスケール）
    mets["cfrg"].fixed_max = None
    mets["cfrg"].floor = CFRG_FLOOR
    mets["cfrg"].disp_div = 1000.0  # 内部MHzのまま表示だけGHz '2.9G'
    for k in ("net", "disk"):
        mets[k].fixed_max = None
        mets[k].floor = IO_FLOOR
        mets[k].compact_g = True  # >=1000 MB/s は GB/s に繰り上げ '1.2G'
    mets["gclk"].fixed_max = None
    mets["gclk"].floor = GCLK_FLOOR
    mets["gclk"].disp_div = 1000.0  # 内部MHzのまま表示だけGHz '2.9G'
    if not DIMM_SENSORS:
        mets["memtemp"].no_sensor = True  # DIMM温度センサー(spd5118)が無い場合は選択不可
    return mets


def sample_gpu(mets):
    """複数GPUは1系統に集計して表示する:
    使用率=max(全GPU), VRAM=sum(used)/sum(total), 電力=sum, 温度=max。
    デバイス単位の取得失敗はスキップ（一部欠けても止めない）。"""
    if not GPUS:
        return
    utils, psum, temps, fans = [], 0.0, [], []
    used = tot = 0
    for gpu in GPUS:
        try:
            utils.append(float(pynvml.nvmlDeviceGetUtilizationRates(gpu).gpu))
        except Exception:
            pass
        try:
            fans.append(float(pynvml.nvmlDeviceGetFanSpeed(gpu)))
        except Exception:
            pass
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(gpu)
            used += mem.used
            tot += mem.total
        except Exception:
            pass
        try:
            psum += pynvml.nvmlDeviceGetPowerUsage(gpu) / 1e3  # mW -> W
        except Exception:
            pass
        try:
            temps.append(float(pynvml.nvmlDeviceGetTemperature(
                gpu, pynvml.NVML_TEMPERATURE_GPU)))
        except Exception:
            pass
    if utils:
        mets["gpu"].push(max(utils))
    if fans:
        mets["fan"].push(max(fans))  # ファン回転は fan の max（温度と同じ方針）
    g = mets.get("gclk")
    if g is not None:
        clks = []
        for gpu in GPUS:
            try:
                clks.append(float(pynvml.nvmlDeviceGetClockInfo(
                    gpu, pynvml.NVML_CLOCK_SM)))
            except Exception:
                pass
        if clks:
            g.push(max(clks))
    if tot > 0:
        mets["vram"].push(100.0 * used / tot)
    mets["power"].push(psum)
    if temps:
        mets["temp"].push(max(temps))


def sample_cpu(mets):
    mets["cpu"].push(psutil.cpu_percent(interval=None))
    mets["ram"].push(psutil.virtual_memory().percent)
    m = mets.get("load")
    if m is not None:
        try:
            m.push(os.getloadavg()[0])
        except OSError:
            pass
    m = mets.get("memtemp")
    if m is not None and DIMM_SENSORS:
        vals = []
        for d in DIMM_SENSORS:  # 全DIMMの max（温度項目と同じ方針）
            try:
                vals.append(int(open(d + "/temp1_input").read().strip()) / 1000.0)
            except (OSError, ValueError):
                continue
        if vals:
            m.push(max(vals))
    m = mets.get("cputemp")
    if m is not None and hasattr(m, "chip"):
        try:
            for e in psutil.sensors_temperatures().get(m.chip, []):
                if (e.label or "") == m.tlabel:
                    m.push(float(e.current))
                    break
        except Exception:
            pass
    m = mets.get("cpupower")
    if m is not None and CPU_POWER is not None:
        kind, path, _name = CPU_POWER
        try:
            if kind == "hwmon":  # µW
                w = int(open(path + "/power1_input").read().strip()) / 1e6
            else:  # rapl: energy_uj 差分 / 経過秒
                import time as _t
                now, e = _t.monotonic(), float(open(path + "/energy_uj").read().strip())
                dt, de = now - CPU_POWER_LAST[0], e - CPU_POWER_LAST[1]
                CPU_POWER_LAST[0], CPU_POWER_LAST[1] = now, e
                w = (de / 1e6 / dt) if dt > 0 and de >= 0 else 0.0  # µJ/s = µW
            m.push(w)
        except Exception:
            pass
    m = mets.get("cfrg")
    if m is not None:
        try:
            f = psutil.cpu_freq()
            if f is not None and f.current:
                m.push(float(f.current))
        except Exception:
            pass
    m = mets.get("net")
    if m is not None:
        try:
            import time as _t
            c = psutil.net_io_counters()
            now, tot = _t.monotonic(), c.bytes_sent + c.bytes_recv
            dt, de = now - NET_LAST[0], tot - NET_LAST[1]
            NET_LAST[0], NET_LAST[1] = now, tot
            m.push((de / MB / dt) if dt > 0 and de >= 0 else 0.0)  # MB/s
        except Exception:
            pass
    m = mets.get("disk")
    if m is not None:
        try:
            import time as _t
            c = psutil.disk_io_counters()
            if c is None:
                raise OSError("disk_io_counters unavailable")
            now, tot = _t.monotonic(), c.read_bytes + c.write_bytes
            dt, de = now - DISK_LAST[0], tot - DISK_LAST[1]
            DISK_LAST[0], DISK_LAST[1] = now, tot
            m.push((de / MB / dt) if dt > 0 and de >= 0 else 0.0)  # MB/s
        except Exception:
            pass
    m = mets.get("ssdtemp")
    if m is not None and SSD_TEMP is not None:
        kind, path = SSD_TEMP
        try:
            if kind == "psutil":
                for e in psutil.sensors_temperatures().get("nvme", []):
                    if (e.label or "") == path:
                        m.push(float(e.current))
                        break
            else:  # hwmon: m℃ -> ℃
                m.push(int(open(path + "/temp1_input").read().strip()) / 1000.0)
        except Exception:
            pass


def monitor_geom(primary=True):
    """xrandr からプライマリ（または最初の接続）モニタの (x, 幅, 高さ) を返す。"""
    try:
        out = subprocess.run(["xrandr"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if " connected" not in line:
            continue
        if primary != (" primary" in line):
            continue
        m = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", line)
        if m:
            w, h, x, _y = (int(v) for v in m.groups())
            return x, w, h
    return None


# --- dock_auto: Cinnamon パネル帯の未使用領域にバーを自動配置 ---------------
# D-BusEval で panelManager の _leftBox/_rightBox 子アプレットの矩形を取り、
# 帯右側アプレット列の先頭xと左側末端xを取得（この機の Cinnamon 6.6.9 で
# get_transformed_box は actor に存在せず get_allocation_box は親相対だった
# ため、panel actor の絶対x + box の子相対を足して絶対座標に直す）。
PANEL_BOUNDS_JS = (
    "var pm = imports.ui.main.panelManager;"
    "var panels = pm.panels.filter(function(p){ return !!p; });"
    "if (panels.length === 0) throw 'no panels';"
    "var bottom = panels[0], by = -1;"
    "for (var i = 0; i < panels.length; i++) {"
    "  var b = panels[i].actor.get_allocation_box();"
    "  if (b.y1 >= by) { by = b.y1; bottom = panels[i]; } }"
    "var pa = bottom.actor.get_allocation_box();"
    "var rb = bottom._rightBox.get_allocation_box();"
    "var lb = bottom._leftBox.get_allocation_box();"
    "var rightStart = null;"
    "var ch = bottom._rightBox.get_children();"
    "for (var j = 0; j < ch.length; j++) {"
    "  try { var a = ch[j].get_allocation_box();"
    "    if (a.x2 - a.x1 <= 0) continue;"
    "    var x = pa.x1 + rb.x1 + a.x1;"
    "    if (rightStart === null || x < rightStart) rightStart = x; } catch (e) {} }"
    "if (rightStart === null) rightStart = pa.x2;"
    "var leftEnd = null;"
    "ch = bottom._leftBox.get_children();"
    "for (var k = 0; k < ch.length; k++) {"
    "  try { var a2 = ch[k].get_allocation_box();"
    "    if (a2.x2 - a2.x1 <= 0) continue;"
    "    var x2 = pa.x1 + lb.x1 + a2.x2;"
    "    if (leftEnd === null || x2 > leftEnd) leftEnd = x2; } catch (e) {} }"
    "if (leftEnd === null) leftEnd = pa.x1;"
    "JSON.stringify([rightStart, leftEnd]);"
)


def cinnamon_panel_bounds():
    """帯右側アプレット列の先頭xと左側末端xを [rightStart, leftEnd] で返す。
    Cinnamon 以外・失敗時（gdbus timeout 2s）は None。"""
    try:
        out = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.Cinnamon",
             "--object-path", "/org/Cinnamon", "--method",
             "org.Cinnamon.Eval", PANEL_BOUNDS_JS],
            capture_output=True, text=True, timeout=2).stdout
        # 戻りは (true, '[..]') 形式。末尾の JSON 配列を拾う。
        m = re.search(r"\[\s*\d+\s*,\s*\d+\s*\]", out)
        if not m:
            return None
        v = json.loads(m.group(0))
        return [int(v[0]), int(v[1])]
    except Exception:
        return None


def measure_panel_height(root):
    """_NET_WORKAREA から下端パネルの高さを推定（取れなければ 0）。"""
    try:
        out = subprocess.run(["xprop", "-root", "_NET_WORKAREA"],
                             capture_output=True, text=True, timeout=5).stdout
        nums = [int(v) for v in re.findall(r"-?\d+", out.split(":")[-1])]
        sh = root.winfo_screenheight()
        for i in range(0, len(nums) - 3, 4):
            _x, y, _w, h = nums[i:i + 4]
            if sh - (y + h) > 0:
                return sh - (y + h)
    except Exception:
        pass
    return 0


def find_my_window():
    """Xlib で自分のトップレベルウィンドウ（wm_class に pulsebar）を返す。"""
    from Xlib import display
    d = display.Display()
    stack = [d.screen().root]
    while stack:
        w = stack.pop()
        try:
            kids = w.query_tree().children
        except Exception:
            continue
        for c in kids:
            try:
                cls = c.get_wm_class()
            except Exception:
                cls = None
            if cls and "pulsebar" in (cls[0] + cls[1]).lower():
                return d, c
            stack.append(c)
    return d, None


def _find_desktop_window(d):
    """壁紙を描くデスクトップウィンドウ（クラス名に desktop を含むもの）を探す。"""
    stack = [d.screen().root]
    while stack:
        w = stack.pop()
        for c in w.query_tree().children:
            try:
                cls = c.get_wm_class()
            except Exception:
                continue
            if cls and "desktop" in (cls[0] + cls[1]).lower():
                return c
            stack.append(c)
    return None


def apply_bounding_shape(win, w, h, dock):
    """常に通常長方形（張り出し機構は撤去済み。将来の形状変更用に残す）。"""
    try:
        from Xlib.ext import shape
        win.shape_rectangles(shape.ShapeBounding, shape.ShapeSet, 0, 0, 0,
                             [(0, 0, w, h)])
    except Exception:
        pass


def set_window_role(dock, w, h, x, y, above=True):
    """dock=True なら DOCK タイプ+下端 STRUT を設定、False ならそれらを削除。
    above=True なら最上位に積む。above=False は他ウィンドウのウラ面へ下げるが、
    壁紙ウィンドウの下に潜ると見えなくなるため、壁紙の直上（＝アプリ全員のウラ）に
    restack する。壁紙が見つからなければ単体で最背面。"""
    if IS_WSL:
        return False  # WSLg: DOCK タイプ/積層操作不要（幽霊窓戦法の誤作動防止）
    try:
        from Xlib import X as Xc
        d, win = find_my_window()
        if win is None:
            return False
        a_type = d.intern_atom("_NET_WM_WINDOW_TYPE")
        xa_atom = d.intern_atom("ATOM")  # 型アトム ATOM (id 4)。Xlib.X.ATOM は存在しない
        if dock:
            # DOCK タイプのみ。STRUT は予約しない——ドックはパネル帯の内側に
            # 重なるため、追加予約すると作業領域が二重に縮む（ウィンドウがずれる）。
            win.change_property(a_type, xa_atom, 32,
                                [d.intern_atom("_NET_WM_WINDOW_TYPE_DOCK")])
        else:
            win.delete_property(a_type)
            win.delete_property(d.intern_atom("_NET_WM_STRUT_PARTIAL"))
            win.delete_property(d.intern_atom("_NET_WM_STRUT"))
        apply_bounding_shape(win, w, h, dock)
        # override-redirect のウィンドウは WM のスタック管理外なので、
        # 自前でスタック操作しないとウラ面へ行けない。
        if above or dock:
            win.configure(stack_mode=Xc.Above)
        else:
            desk = _find_desktop_window(d)
            if desk is not None:
                win.configure(stack_mode=Xc.Above, sibling=desk)
            else:
                win.configure(stack_mode=Xc.Below)
        d.flush()
        return True
    except Exception:
        return False


def clear_dock_role():
    """_NET_WM_WINDOW_TYPE / STRUT を削除する（ドック→ガジェット戻し用）。"""
    if IS_WSL:
        return False
    try:
        d, win = find_my_window()
        if win is None:
            return False
        for name in ("_NET_WM_WINDOW_TYPE", "_NET_WM_STRUT_PARTIAL", "_NET_WM_STRUT"):
            try:
                win.delete_property(d.intern_atom(name))
            except Exception:
                pass
        d.flush()
        return True
    except Exception:
        return False


def _stage_windows(d, win):
    """コンポジタ(Cinnamon/muffin)の全画面オーバレイ窓候補（下端パネル帯の
    ポインタ入力を握る窓）を、積層の上位(末尾=前面)順に返す。
    条件: override-redirect で画面の下端～中央まで覆う大きさ。
    自分のウィンドウツリー（自窓・その親・兄弟）は除外する。"""
    out = []
    try:
        root = d.screen().root
        # python-xlib の Screen に height/width は無い（昔 scr.height を見ていて
        # AttributeError で常に空振りだった）。root の geometry から取る。
        rw, rh = root.get_geometry().width, root.get_geometry().height
        par = win.query_tree().parent
        mine = {win.id} | ({par.id} if par is not None else set())
        cands = list(root.query_tree().children)
        if par is not None and par.id != root.id:
            cands += [c for c in par.query_tree().children if c.id not in mine]
        for c in cands:
            if c.id in mine:
                continue
            try:
                a = c.get_attributes()
                if not a.override_redirect:
                    continue
                g = c.get_geometry()
            except Exception:
                continue
            if (g.x <= 0 and g.y <= rh // 2 and
                    g.x + g.width >= rw and
                    g.y + g.height >= rh - 5):
                out.append(c)
        return out
    except Exception:
        return []


# パネル帯領域でポインタ入力を握るコンポジタ窓は、ウィンドウツリーに現れない
# ことがある（実測: 0x1d8 は restack の sibling に名前を挙げるまで query_tree の
# どの子にも出ない）。query_pointer で帯上の入力の真のオーナーを測り、その ID を
# here にキャッシュして sibling に使う。
_hidden_thief = None


def force_above(win, other):
    """ Below→Above の二段 restack で、積層順に「変化」を作ってから other の直上に
    積む。muffin は同じ位置への no-op configure だと入力ルーティングを再同期せず、
    真に上下が入れ替わる操作のときだけ追従する（実測: query_pointer の owner が
    0x1d8 のまま積む操作は空振り、Below→Above で反転し以降tickで保持）。
    罠（右クリック不能事件 2026-11-25）: win.display は python-xlib の
    _BaseDisplay を返し sync() が無い（AttributeError）。握りつぶすと常に False
    になり再主張が全滅する。同じ接続内は要求順に処理されるので flush() で十分。"""
    try:
        if other is not None and getattr(other, "id", None) == win.id:
            return False  # sibling が自分自身だと BadMatch
        d = win.display
        Xc = __import__("Xlib").X
        win.configure(stack_mode=Xc.Below, sibling=other)
        d.flush()
        win.configure(stack_mode=Xc.Above, sibling=other)
        d.flush()
        return True
    except Exception as e:
        if _PB_DEBUG:
            import traceback; traceback.print_exc()
        return False


def _pointer_owner(d):
    """query_pointer でポインタ位置と、そこで入力を受けている窓の ID を返す
    (root_x, root_y, child_id|None)。失敗時 None。"""
    try:
        qp = d.screen().root.query_pointer()
        c = qp.child
        c = c if isinstance(c, int) else (c.id if c else 0)
        return qp.root_x, qp.root_y, (c or None)
    except Exception:
        return None


# --- バー下ドラッグ: 押下点真下の最前面の他窓と WM 管理フレームを探す ------
# query_pointer の root 点から root.query_tree()（積層の下端=背面順）を上へ辿り、
# 点を含み・bar_base の client に属さず・override-redirect でなく・
# パネル/デスクトップ/stage でない窓まで最深の子へ下りる。そこから WM_STATE /
# _NET_WM_PID のある最も外側の root 直下祖先（=muffin のフレーム）へ遡って
# 移動対象にする（子だけ configure すると内容が切れるため）。

def _type_excluded(d, w):
    """DOCK/DESKTOP/stage/パネル系の窓なら True（動かしてはいけない窓）。"""
    try:
        from Xlib import X as _X
        t = w.get_full_property(d.intern_atom("_NET_WM_WINDOW_TYPE"),
                                _X.AnyPropertyType)
        if t:
            names = {d.get_atom_name(v) for v in t.value}
            if names & {"_NET_WM_WINDOW_TYPE_DOCK", "_NET_WM_WINDOW_TYPE_DESKTOP",
                        "_NET_WM_WINDOW_TYPE_DOCK_MENU", "_NET_WM_WINDOW_TYPE_DROPDOWN_MENU",
                        "_NET_WM_WINDOW_TYPE_POPUP_MENU", "_NET_WM_WINDOW_TYPE_TOOLTIP",
                        "_NET_WM_WINDOW_TYPE_SPLASH"}:
                return True
    except Exception:
        pass
    try:
        cls = w.get_wm_class()
    except Exception:
        cls = None
    blob = " ".join(cls).lower() if cls else ""
    return any(s in blob for s in ("desktop", "panel", "stage", "cinnamon",
                                   "muffin", "plank", "dock"))


def climb_window(d, root, win):
    """押下点最深窓から移動・raise 対象を特定し (frame, managed) を返す。
    frame = 祖先鎖の最も外側（root 直下）の祖先（reparent 済みなら WM フレーム窓、
    CSD で直下なら自分）。configure 移動はこれを対象にしないと子だけ動いて
    内容がフレームに切り抜かれる。managed = 鎖の中で WM_STATE / _NET_WM_PID を
    持つ窓（=WM に管理されている証拠であり、_NET_ACTIVE_WINDOW の送信先）。
    managed が無い鎖（オーバレイ/パネルの子・管理外）は None。"""
    from Xlib import X as _X
    xa_pid = d.intern_atom("_NET_WM_PID")
    xa_wmstate = d.intern_atom("WM_STATE")

    def managed(w):
        try:
            # Window.get_property は 4 引数必須。get_full_property を使う
            return (w.get_full_property(xa_wmstate, _X.AnyPropertyType) is not None
                    or w.get_full_property(xa_pid, _X.AnyPropertyType) is not None)
        except Exception:
            return False

    if win is None:
        return None
    try:
        if win.get_attributes().override_redirect:
            return None
    except Exception:
        return None
    target = win if managed(win) else None
    top = win
    w = win
    for _ in range(32):
        try:
            par = w.query_tree().parent
            if par is None or par.id == root.id:
                break
            if par.get_attributes().override_redirect or _type_excluded(d, par):
                return None  # オーバレイ/パネルの子として埋まっている窓
        except Exception:
            break
        if managed(par):
            target = target or par
            top = par
        w = par
    if target is None:
        # 鎖のどこにも WM_STATE/_NET_WM_PID が無い = WM 管理外。移動対象にしない
        return None
    # frame は最も外側の root 直下祖先（フレーム）。managed は管理窓そのもの。
    return (top, target)


def outermost_ancestor(d, root, win):
    """管理窓から最も外側の root 直下祖先（WM フレーム）を返す（自らが直下なら自分）。
    raise のフォールバック（Above configure）はフレーム窓に当てる必要があるため。"""
    top = win
    w = win
    for _ in range(32):
        try:
            par = w.query_tree().parent
            if par is None or par.id == root.id:
                break
            top = par
            w = par
        except Exception:
            break
    return top


def raise_managed(d, managed_win, frame=None):
    """WM 管理窓を前面へ: まず _NET_ACTIVE_WINDOW（mutter/muffin はこれで
    フォーカス+raise する）。そのうえでフォールバックとして root 直下の
    フレーム窓に stack_mode=Above の configure を送る（フレーム無しの窓は自分）。"""
    from Xlib import X as Xc
    from Xlib.protocol import event
    try:
        nwa = d.intern_atom("_NET_ACTIVE_WINDOW")
        # EWMH 準拠: window フィールド=対象、送信先=root
        ev = event.ClientMessage(window=managed_win, client_type=nwa,
                                 data=(32, [2, 0, 0, 0, 0]))  # source=pager
        d.screen().root.send_event(ev, propagate=False,
                                   event_mask=Xc.SubstructureNotifyMask |
                                   Xc.SubstructureRedirectMask)
        d.flush()
    except Exception:
        pass
    try:
        if frame is None:
            frame = outermost_ancestor(d, d.screen().root, managed_win)
        frame.configure(stack_mode=Xc.Above)
        d.flush()
    except Exception:
        pass


def _windows_at_point(d, root, x, y, bar_base):
    """(x,y) を覆う WM 管理窓を積層順（前面->背面）に (frame, managed) で列挙。
    除外（自分/O-R/パネル・デスクトップ/管理外）は除去、重複は最初の位置だけ残す。"""
    out = []
    seen = set()
    for w in _deepest_at_point(d, root, x, y, bar_base):
        pair = climb_window(d, root, w)
        if pair is None:
            continue
        frame, managed = pair
        if frame.id not in seen:
            seen.add(frame.id)
            out.append((frame, managed))
    return out


def _net_moveresize(d, win, x, y):
    """_NET_MOVERESIZE_WINDOW を wmctrl と同じ形式で root に送る
    （window フィールド=対象、l[0]=flags(x,y present)+NW gravity、l[1..2]=x,y）。
    muffin は管理窓への素の X configure（クライアント/フレームどちらでも）を
    無視するため、WM への移動要求はこれで行う（wmctrl -e と同じ経路）。"""
    from Xlib import X as Xc
    from Xlib.protocol import event
    flags = 0x100 | 0x200 | 1  # x present | y present | gravity=NorthWest
    ev = event.ClientMessage(window=win,
                             client_type=d.intern_atom("_NET_MOVERESIZE_WINDOW"),
                             data=(32, [flags, x & 0xffffffff, y & 0xffffffff, 0, 0]))
    root = d.screen().root
    root.send_event(ev, propagate=False,
                    event_mask=Xc.SubstructureNotifyMask | Xc.SubstructureRedirectMask)
    d.flush()


def _deepest_at_point(d, root, x, y, bar_base):
    """(x,y) を覆う窓を積層 DFS で前面->背面順に返す（管理窓への写像は呼び出し側）。
    除外判断（O-R/パネル類）は climb_window 側で行うのでここでは全候補を返す。"""
    Xv = 2  # IsViewable

    def hits(win, lx, ly):
        try:
            kids = win.query_tree().children  # 積層の背面->前面順
        except Exception:
            return []
        out = []
        for c in reversed(kids):  # 前面順
            if (c.id >> 21) == bar_base:
                continue  # 自分自身（バー・Tk メニュー等の自前ポップアップ）
            try:
                g = c.get_geometry()
                if not (g.x <= lx < g.x + g.width and
                        g.y <= ly < g.y + g.height):
                    continue
                if c.get_attributes().map_state != Xv:
                    continue
            except Exception:
                continue
            subs = hits(c, lx - g.x, ly - g.y)
            if subs:
                out.extend(subs)  # 前面窓の内部が最前面
            else:
                out.append(c)
        return out

    return hits(root, x, y)


def _walk_to_point(d, root, x, y, bar_base):
    """(x,y) 押下点の最前面 WM 管理窓（移動対象）を返す。無ければ None。
    オーバレイ（幽霊/stage/O-R）は climb_window の除外で素通りされるので、
    オーバレイの下の本当の窓が見つかる。"""
    frames = _windows_at_point(d, root, x, y, bar_base)
    return frames[0] if frames else None


def restack_above_stage(win, thief=None, d=None):
    """帯上のポインタ入力を握るコンポジタ・オーバレイ窓の直上に自分を積む。
    query_pointer で実測した入力オーナー（ツリーに出ないことがある最強候補）を
    優先し、ダメならツリーに現れる全画面オーバレイ窓の直上へ積む。
    （実測: override-redirect のスタック操作は muffin に無視されないこと、
    真の thief 0x1d8 は sibling に挙げるまでツリーへ出ないこと。）
    d は本物の Xlib.display.Display を渡すこと（find_my_window の返し値）。
    win.display は接続オブジェクト(_BaseDisplay)で create_resource_object /
    screen を持たない（罠 2026-11-25: 幽霊窓の sibling が作れず再主張が全滅し
    右クリック不能になった）。省略時は find_my_window で取り直す。"""
    if IS_WSL:
        return False  # WSLg: Cinnamon 専用の幽霊窓 restack は行わない
    try:
        if d is None:
            d2, win2 = find_my_window()
            d = d2
        Xc = __import__("Xlib").X
        cands = []
        if thief is not None:
            cands.append((True, d.create_resource_object("window", thief)))
        for c in reversed(_stage_windows(d, win)):  # 積層の上位順
            if thief is not None and c.id == thief:
                continue
            cands.append((False, c))
        for is_thief, st in cands:
            if force_above(win, st):
                return True
            if _PB_DEBUG:
                print("  [restack] cand=%s FAILED" % (hex(getattr(st, 'id', 0)),), flush=True)
            global _hidden_thief
            if is_thief:
                _hidden_thief = None  # 死んだIDなら捨ててツリー候補で再試行
        if _PB_DEBUG:
            print("  [restack] cands=%s -> False" % (
                [hex(getattr(s, 'id', 0)) for _, s in cands],), flush=True)
        return False
    except Exception:
        if _PB_DEBUG:
            import traceback; traceback.print_exc()
    return False


def raise_or_below(above):
    """自分の積層を再主張する。WM管理時は WM のフレーム側を restack する。
    最前面指定時は、コンポジタの全画面オーバレイ窓（帯のクリックを握る）の
    直上にも積む（帯に重なる位置で右クリックが届くように）。"""
    if IS_WSL:
        return  # WSLg: tick 毎の Xlib 積層操作は全停止
    try:
        from Xlib import X as Xc
        d, win = find_my_window()
        if win is None:
            return
        target = win
        try:
            a = win.get_attributes()
            if not a.override_redirect:
                par = win.query_tree().parent
                if par is not None and par.id != d.screen().root.id:
                    target = par
        except Exception:
            pass
        target.configure(stack_mode=Xc.Above if above else Xc.Below)
        if above:
            restack_above_stage(target, d=d)
        d.flush()
    except Exception:
        pass


def apply_motif_nodecor():
    """_MOTIF_WM_HINTS でタイトルバー等の飾りを消す（マップ前に効かせる）。"""
    if IS_WSL:
        return False
    try:
        d, win = find_my_window()
        if win is None:
            return False
        motif = d.intern_atom("_MOTIF_WM_HINTS")
        win.change_property(motif, motif, 32, [2, 0, 0, 0, 0])  # decorations=0
        d.flush()
        return True
    except Exception:
        return False


def request_skip_taskbar():
    """WM へ _NET_WM_STATE の SKIP_TASKBAR / SKIP_PAGER を要求する（マップ後に送る）。
    積層はアクティブ順（通常の管理ウィンドウと同じ）に任せるため BELOW は要求しない。"""
    if IS_WSL:
        return False
    try:
        from Xlib import X as Xc
        from Xlib.protocol import event
        d, win = find_my_window()
        if win is None:
            return False
        nws = d.intern_atom("_NET_WM_STATE")
        for atom in ("_NET_WM_STATE_SKIP_TASKBAR", "_NET_WM_STATE_SKIP_PAGER"):
            ev = event.ClientMessage(
                window=win, client_type=nws, data=(32, [1, d.intern_atom(atom), 0, 0, 0]))
            win.send_event(ev, event_mask=Xc.SubstructureNotifyMask | Xc.SubstructureRedirectMask)
        d.flush()
        return True
    except Exception:
        return False


def menu_grab_loop(d, actions, alive):
    """インラインメニュー展開中に grab 接続で待機するイベントループ（grab 自体は
    Tk スレッド側の try_menu_grab() が同期で張る）。grab を張るのは Tk とは
    「別クライアント」の接続なので、grab 中はバー内外すべての press/motion が
    この接続にだけ届く。press（ボタン番号付き）と motion は root 座標ごと
    actions に積んで Tk へ転送し、面板ヒットテストは Tk 側（_poll_menu_grab）で
    行う（Tk の同名バインディングは grab 中は発火しない＝二重処理なし）。
    - keyboard grab は owner_events=False: OR 窓は click-to-focus で
      フォーカスを持たないので、これが Esc の唯一確実な経路。
    - press は押しっぱなし/drag を食わないよう release まで motion を抑止。
    - alive() が偽（メニューが Tk 側で閉じた）になり次第 finally で grab 解除+
      接続クローズ。50ms select で確認するので grab 寿命≈メニュー寿命。
    - python-xlib 罠: fd は d.fd ではなく d.display.fileno()。"""
    from Xlib import X
    import select
    done = False
    suppressing = False  # press→release まで motion 無視（ドラッグ誤反応防止）
    try:
        while not done and alive():
            try:
                select.select([d.display.fileno()], [], [], 0.05)
            except (InterruptedError, OSError):
                continue
            while d.pending_events():
                try:
                    ev = d.next_event()
                except Exception:
                    done = True
                    break
                et = getattr(ev, "type", None)
                if et == X.KeyPress:
                    # keysym 直比較でなく keycode から d.keycode_to_keysym で照合
                    for ks in d.keycode_to_keysym(ev.detail, 0):
                        if ks == 0xFF1B:  # XK_Escape
                            actions.append(("esc",))
                            done = True
                            break
                        if ks in (0xFF0D, 0xFF8D):  # Return / KP_Enter
                            actions.append(("enter",))
                            done = True
                            break
                elif et == X.ButtonPress:
                    if suppressing:
                        continue
                    # detail=ボタン番号（3=再右クリック: Tk 側で閉じるに翻訳）。
                    # grab 解除は alive() が偽（=メニューが閉じた）になったときだけ。
                    actions.append(("press", ev.root_x, ev.root_y, ev.detail))
                    suppressing = True
                elif et == X.ButtonRelease:
                    suppressing = False
                elif et == X.MotionNotify and not suppressing:
                    # 高頻度: 古い motion は新しいもので上書き（1個だけ保持）
                    while actions and actions[-1][0] == "motion":
                        actions.pop()
                    actions.append(("motion", ev.root_x, ev.root_y))
    finally:
        try:
            d.screen().root.ungrab_pointer(X.CurrentTime)
            d.screen().root.ungrab_keyboard(X.CurrentTime)
            d.flush()
        except Exception:
            pass
        try:
            d.close()
        except Exception:
            pass


def try_menu_grab(d, tk_win_id):
    """Tk スレッドから同期で grab を張る（結果を即座に知って Tk バインディングの
    フォールバック要否を決めるため）。失敗（他アプリが grab 中: GrabBusy/
    GrabImpossible）は False を返し、呼び出し側は focus_force/Esc/FocusOut/
    再右クリックに頼る。
    python-xlib 罠: grab_pointer の引数順は (owner_events, event_mask,
    pointer_mode, keyboard_mode, confine_to, cursor, time)（event_mask は2番目）。
    grab_* の戻り値は GrabNotify ではなく status が既に int（r.status と読むな）。"""
    from Xlib import X
    try:
        r_kb = d.screen().root.grab_keyboard(False, X.GrabModeAsync,
                                             X.GrabModeAsync, X.CurrentTime)
        r_pt = d.screen().root.grab_pointer(
            False,
            (X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask),
            X.GrabModeAsync, X.GrabModeAsync, 0, 0, X.CurrentTime)
        d.sync()
        ok = (r_kb == X.GrabSuccess and r_pt == X.GrabSuccess)
        if not ok:
            try:
                d.screen().root.ungrab_pointer(X.CurrentTime)
                d.screen().root.ungrab_keyboard(X.CurrentTime)
                d.flush()
            except Exception:
                pass
        if _PB_DEBUG:
            print("[grab] kb=%s pt=%s ok=%s" % (r_kb, r_pt, ok),
                  flush=True)
        return ok
    except Exception:
        if _PB_DEBUG:
            import traceback; traceback.print_exc()
        try:
            d.screen().root.ungrab_pointer(X.CurrentTime)
            d.screen().root.ungrab_keyboard(X.CurrentTime)
            d.flush()
        except Exception:
            pass
        return False


class Bar:
    REASSERT_GRACE_S = 1.5  # 最後の再主張後、この時間だけ restack を継続（ホバー離れの余韻）

    def __init__(self, root, mets, cfg):
        global PANEL_H
        self.all_mets = mets                      # key -> Metric（常に全項目サンプル）
        self.root = root
        self.cfg = cfg
        PANEL_H = measure_panel_height(root)
        self.geom = monitor_geom(True) or monitor_geom(False) \
            or (0, root.winfo_screenwidth(), root.winfo_screenheight())
        # インラインメニュー（PB_MENU=inline）用状態。popup mode では _menu は
        # tk Menu か None のまま（面板辞書になるのは inline 経路のみ）。
        self._inline_menu = MENU_MODE == "inline"
        self._menu = None
        self._grab_active = False
        self._grab_q = []
        self._body = None       # 意図したバー本体矩形 (x,y,w,h)。窓矩形ではない。
        self._win_w = self._win_h = 0
        self._mfont = tkfont.Font(family="DejaVu Sans", size=9)
        root.overrideredirect(True)
        # WSLg: WM の積層操作が使えないので常に無管理最前面窓。
        root.attributes("-topmost",
                        True if IS_WSL else bool(cfg.get("topmost", True)))
        try:
            root.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        # topmost off のガジェットだけ WM管理（飾りなし）にする。override-redirect の
        # ママでは WM(muffin) が常に最前面層へ回してウラ面へ行けない（実測）。
        # WSLg は常に OR 窓。
        self._or_mode = self.dock or IS_WSL or bool(cfg.get("topmost", True))
        if not self._or_mode:
            root.overrideredirect(False)
            apply_motif_nodecor()  # マップ前に飾りなしヒントを渡す
        self.w = self.h = 0
        # dock_auto: 帯右側アプレット列の先頭x・左側末端x [rightStart, leftEnd]。
        # 起動時と5秒ごとに gdbus で更新（失敗時は最後の位置を維持）。
        self._pbounds = None
        self._auto_tick = 0
        if self.dock and self.cfg.get("dock_auto", True):
            self._pbounds = cinnamon_panel_bounds()
        self.relayout(first=True)
        root.configure(bg=BG)
        self.cv = tk.Canvas(root, width=self._win_w, height=self._win_h, bg=BG,
                            highlightthickness=0)
        self.cv.pack()
        root.bind("<Button-1>", self._grab)
        root.bind("<B1-Motion>", self._drag)
        root.bind("<ButtonRelease-1>", self._release)
        root.bind("<Button-2>", self._cycle)
        root.bind("<Button-3>", self._open_menu)
        if self._inline_menu:
            # インライン面板: B1/Motion/Esc をメニュー判定ラッパー経由にする。
            root.bind("<Button-1>", self._click1)
            root.bind("<Motion>", self._motion)
            root.bind("<Escape>", self._key_esc)
            # 他窓へフォーカスが実移動した時だけ面板を閉じる（grab 由来 detail は
            # _focus_out 側で無視。OR 窓は通常フォーカスを持たないので実害なし）。
            root.bind("<FocusOut>", self._focus_out)
        else:
            root.bind("<Escape>", lambda e: root.destroy())

    # ---- 状態ヘルパ -------------------------------------------------------
    @property
    def dock(self):
        # WSLg: mode 設定によらず常にガジェット扱い（config.json は書き換えない）
        return self.cfg["mode"] == "dock" and not IS_WSL

    def visible_mets(self):
        return [self.all_mets[k] for k in self.cfg.get("order", self.all_mets)
                if k in self.all_mets
                and self.cfg["items"].get(k) and not self.all_mets[k].unavailable()]

    def _dock_h(self):
        # 自動高さはパネル帯の高さ基準（帯の中に同一高さで埋め込むため）。
        # ユーザー設定値(dock_height>0)を優先し、下限34。PANEL_H が取れない
        # 環境でのみ CELL_H にフォールバック。
        return max(self.cfg["dock_height"] or PANEL_H or CELL_H, 34)

    def _cell(self):
        """(セル横幅, セル縦幅) を layout から返す。dock は常に横。"""
        return (CELL_W, self._dock_h() if self.dock else CELL_H)

    # ---- サイズ・位置 -----------------------------------------------------
    def relayout(self, first=False, keep_pos=True):
        """mode/orient/items 変更後にウィンドウサイズと位置を作り直す。"""
        mets = self.visible_mets()
        n = max(len(mets), 1)
        cw, ch = self._cell()
        vertical = (not self.dock) and self.cfg.get("orient") == "v"
        if vertical:
            self.w, self.h = cw, ch * n
        elif self.dock:
            self.w, self.h = cw * n + PAD, ch
        else:
            self.w, self.h = cw * n + PAD, ch
        self.vertical = vertical
        self.top_off = 0
        # インラインメニュー展開中は窓原点≠本体原点なので本体矩形を位置基準にする
        if isinstance(self._menu, dict):
            old_x, old_y = self._body[0], self._body[1]
        else:
            old_x, old_y = self.root.winfo_x(), self.root.winfo_y()
        if self.dock:
            x, y = self._dock_pos()
        elif first and self.cfg.get("geometry"):
            x, y = self._clamp_float(*self.cfg["geometry"][:2])
        elif first:
            x, y = self.geom[0] + self.geom[1] - self.w - 12, 12  # プライマリ右上
        elif keep_pos:
            x, y = self._clamp_float(old_x, old_y)
        else:
            x, y = self._clamp_float(old_x, old_y)
        self._body = (x, y, self.w, self.h)
        self._apply_window_geom()
        self.root.update_idletasks()
        if not self._or_mode:
            apply_motif_nodecor()
            request_skip_taskbar()
        else:
            # 注意: 形状(bounding shape)は「窓の実寸」で切る（self.w/h は本体矩形。
            # メニュー展開中の relayout で面板がクリップされる罠）。
            set_window_role(self.dock, self._win_w, self._win_h, x, y,
                            above=self.dock or bool(self.cfg.get("topmost", True)))

    def _clamp_float(self, x, y):
        """ガジェットの位置をプライマリモニタ内に収める。
        パネル帯の上に置くこともできる（その場合、帯に重なる部分は右クリックが
        届かなくなるが、ユーザーが自分で配置する分には許容する運用）。"""
        mx, mw, mh = self.geom
        x = max(mx, min(x, mx + mw - self.w))
        y = max(0, min(y, mh - self.h))
        return x, y

    def _dock_pos(self):
        # ドックはパネル帯の中に埋め込む（帯の上端に窓の上端を合わせ、自動高さは
        # 帯の高さ＝窓が帯にぴったり収まる）。帯のポインタ入力を握る幽霊窓には
        # 必要時の積層再主張（maybe_reassert_stack）で勝つ。STRUT は予約しない
        # （作業領域を変えない）。
        mx, mw, mh = self.geom
        y = mh - (PANEL_H or 40)
        if self.cfg.get("dock_auto", True) and self._pbounds:
            # 自動配置: 帯右側アプレット群の直前（余白6px）にバー幅で右寄せ。
            # 左側アプレット群より左には出さない（重なり防止）。
            right_start, left_end = self._pbounds
            x = right_start - PAD - self.w
            x = max(mx + PAD, x, left_end + PAD)
            x = max(mx, min(x, mx + mw - self.w))
        else:
            x = mx + self.cfg["dock_offset_x"]
            x = max(mx, min(x, mx + mw - self.w))
        return x, y

    def refresh_dock_auto(self):
        """dock_auto 時に帯アプレットの縁を取り直し、位置が変わっていれば窓だけ
        動かす（geometry 更新は changed 時のみ。gdbus 失敗時は最後の位置を維持＝
        Cinnamon 以外では dock_offset_x フォールバック）。"""
        if not (self.dock and self.cfg.get("dock_auto", True)):
            return
        b = cinnamon_panel_bounds()
        if b is not None:
            self._pbounds = b
        x, y = self._dock_pos()
        if (self.root.winfo_x(), self.root.winfo_y()) != (x, y):
            self.root.geometry(f"+{x}+{y}")

    def after_show(self):
        # マップ後にスタック・装飾の設定を当てる（__init__ 時はマップ前で空振りする）。
        # MOTIF decorations=0 はマップ後に当てない限り muffin に無視される（実測）。
        if not self.dock and not self._or_mode:
            clear_dock_role()
            apply_motif_nodecor()
            request_skip_taskbar()
            return
        x, y = self.root.winfo_x(), self.root.winfo_y()
        set_window_role(self.dock, self._win_w, self._win_h, x, y,
                        above=self.dock or bool(self.cfg.get("topmost", True)))
        self.maybe_reassert_stack()

    def _apply_layer_mode(self):
        """override-redirect（前面固定/dock）と WM管理（ウラ面可）を切り替える。
        overrideredirect の変更はマップ込みで作り直す必要がある。"""
        want = self.dock or IS_WSL or bool(self.cfg.get("topmost", True))
        if want == self._or_mode:
            return
        root = self.root
        pos = (root.winfo_x(), root.winfo_y())
        root.withdraw()
        root.overrideredirect(want)
        self._or_mode = want
        if not want:
            apply_motif_nodecor()
        root.attributes("-topmost", want and bool(self.cfg.get("topmost", True)))
        root.deiconify()
        root.geometry(f"+{pos[0]}+{pos[1]}")
        root.update_idletasks()
        # overrideredirect 切替で X ウィンドウが作り直されうるので、マップ完了後に
        # 属性（DOCK タイプ/STRUT/装飾/スタック）を一度遅延再適用する
        root.after(800, self.after_show)

    # ---- 操作 -------------------------------------------------------------
    def _grab(self, e):
        self._ox, self._oy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()
        self._wd = None  # 裏窓ドラッグセッション
        # ドックは常時裏窓移動。ガジェットは上段（ラベル/数値行、セル先頭16px）
        # プレス時だけ裏窓移動し、波形帯領域プレス時は従来どおりバー自身を動かす。
        yy = e.y - getattr(self, "top_off", 0)
        if self.vertical:
            yy = yy % CELL_H
        want_window = self.dock or yy < 16
        if _DRAG_DEBUG:
            print(f"[grab] xy={e.x_root},{e.y_root} y={e.y} want_win={want_window}", flush=True)
        if want_window:
            self._wd = self._pick_under_window(e)
            if _DRAG_DEBUG:
                print(f"[grab] pick -> {self._wd and (hex(self._wd['frame'].id), hex(self._wd['managed'].id))}", flush=True)
            # Tk の暗黙 grab（Button-1 束縛）がポインタがバーから外れても
            # B1-Motion を Delivery し続けるので追加 grab はしない
            # （余計な grab は tk_popup の grab 罠を招く）。

    def _pick_under_window(self, e):
        """押下点真下の最前面の他窓を特定し、移動対象と Xlib 接続を返す。
        対象が無ければ None（＝従来動作フォールバック）。"""
        if IS_WSL:
            return None  # WSLg: ドラッグは必ずバー自身を動かす（他窓ピッキング停止）
        try:
            from Xlib import display as xld
            d = xld.Display()
            root = d.screen().root
            pair = _walk_to_point(d, root, e.x_root, e.y_root,
                                  self.root.winfo_id() >> 21)
            if pair is None:
                d.close()
                return None
            frame, managed = pair
            return {"d": d, "frame": frame, "managed": managed,
                    "px": e.x_root, "py": e.y_root}
        except Exception:
            return None

    def _cycle(self, e):
        """中クリック: 押下点と交差する WM 管理窓のうち最背面のものを前面へ raise。
        連続クリックで候補が巡回する（上げる→また最背面を上げる の繰り返しで
        積層が回転し、重なる窓を1つずつ選べる）。左ドラッグの対象は押下点の
        最前面窓なので、ここで前に出した窓がそのままドラッグ対象になる。"""
        try:
            from Xlib import display as xld
            d = xld.Display()
            root = d.screen().root
            frames = _windows_at_point(d, root, e.x_root, e.y_root,
                                       self.root.winfo_id() >> 21)
            if frames:
                frame, managed = frames[-1]  # 最背面を前面へ（巡回）
                if _DRAG_DEBUG:
                    print(f"[cycle] {len(frames)} candidates, raise "
                          f"0x{frame.id:08x}", flush=True)
                raise_managed(d, managed, frame)
            d.close()
        except Exception:
            pass

    def _release(self, e):
        wd = getattr(self, "_wd", None)
        self._wd = None
        if wd is not None:
            try:
                wd["d"].close()
            except Exception:
                pass

    def _drag(self, e):
        wd = getattr(self, "_wd", None)
        if wd is not None:
            try:
                self._move_under_window(wd, e)
            except Exception:
                if _DRAG_DEBUG:
                    import traceback
                    traceback.print_exc()
            return
        if self.dock:
            return  # パネルモードは自己移動しない（裏窓移動は上で処理済み）
        x, y = self._clamp_float(e.x_root - self._ox, e.y_root - self._oy)
        self.root.geometry(f"+{x}+{y}")
        self.cfg["geometry"] = [x, y]
        save_config(self.cfg)
        self.maybe_reassert_stack()

    def _move_under_window(self, wd, e):
        """毎モーション: 窓の現在位置（root 絶対）を再取得し、ポインタ移動差分を
        加算した地点へ _NET_MOVERESIZE_WINDOW で移動要求する（mutter/muffin は
        管理窓への素の configure を無視するため WM 経由。wmctrl -e と同じ経路）。
        WM は位置要求に frame extents 相当の固定オフセットを効かせるので、前回
        要求地点と今回の実位置の誤差を計測し、次要求から補正する（閉ループ。
        計測は次のモーション時＝WM が反映した後來なので stale に強い）。
        窓側が座標系を変えても（WM が動かしても）現在位置基準なので破綻しない。"""
        d = wd["d"]
        win = wd["managed"]
        ax, ay = self._win_abs_xy(d, win)
        pend = wd.get("pend")
        if pend is not None:
            wd["err"] = (ax - pend[0], ay - pend[1])
        ex, ey = wd.get("err", (0, 0))
        nx = ax + (e.x_root - wd["px"]) - ex
        ny = ay + (e.y_root - wd["py"]) - ey
        wd["px"], wd["py"] = e.x_root, e.y_root
        _net_moveresize(d, win, nx, ny)
        wd["pend"] = (nx, ny)

    @staticmethod
    def _win_abs_xy(d, win):
        """窓の root 絶対座標（親鎖の x,y 総和。境界幅 0 の WM フレーム前提で十分）。"""
        x = y = 0
        w = win
        root = d.screen().root
        for _ in range(32):
            try:
                g = w.get_geometry()
                x += g.x
                y += g.y
                par = w.query_tree().parent
                if par is None or par.id == root.id:
                    break
                w = par
            except Exception:
                break
        return x, y

    def maybe_reassert_stack(self):
        """前面固定モード（dock 含む）でバーが下端パネル帯に重なっているとき、帯の
        クリックを握るコンポジタ・オーバレイ窓の直上へ自分を作り直す。これをしないと
        帯上にドラッグ配置した後、帯内の右クリックが stage 窓に取られて
        バーを選択できない（実測: query_pointer の child が stage になる）。
        ただし「無条件に毎 tick restack」は Cinnamon のホバー・ポップアップ
        （ウィンドウ一覧のサムネイル等）を毎秒打ち消す（実測回归）。restack は
        「実需があるときだけ」:
          - ポインタがバー矩形（∩帯）の上にあり、なおかつ入力オーナーが自分
            以外（=帯の幽霊窓に取られている）ときだけ restack する。
          - オーナーが自クライアント（Tk メニュー等、id>>21 が同じ）なら restack しない。
          - 最後に restack してから REASSERT_GRACE_S(1.5s) は猶予して継続 restack
            （ポップアップ展開直後にポインタが一瞬バー縁に留まるケース対策）。
        代償: 他窓に覆われた直後は、マウスがバーに乗るまで 1 tick 遅れで前面化
        される（実操作ではマウスを寄せてからクリックするので許容）。
        オーバレイ窓はツリーに出ないことがあるため、ポインタがバー∩帯の上にある
        ときは query_pointer の入力オーナーで真の相手を見つけてキャッシュする。"""
        if IS_WSL:
            return  # WSLg: 幽霊窓戦法は誤作動。tick 毎の積層操作は全停止
        if not self._or_mode:
            return
        mh = self.geom[2]
        band_top = mh - (PANEL_H or 40)
        d = None
        dbg = _PB_DEBUG
        try:
            bx, by = self.root.winfo_x(), self.root.winfo_y()
            if by + self.h <= band_top:
                return
            d, win = find_my_window()
            if win is None:
                return
            global _hidden_thief
            probe = _pointer_owner(d)
            if probe is None:
                return
            px, py, owner = probe
            if owner is not None and (owner >> 21) == (win.id >> 21):
                return  # 自分自身（Tkメニュー等のポップアップ）には勝たせない
            on_bar = (bx <= px < bx + self.w and
                      max(by, band_top) <= py < by + self.h)
            if on_bar and owner is not None and owner != win.id:
                _hidden_thief = owner  # 帯の入力を握っている幽霊窓の ID
            now = time.monotonic()
            need = on_bar and owner is not None and owner != win.id
            prev = getattr(self, "_reassert_prev_a", False)
            if need and not prev:
                self._reassert_at = None  # ポインタがバー上へ入った立上り: 即再主張
            self._reassert_prev_a = need
            if not need:
                return  # 実需なし: ポップアップ（他窓）が上でも restack しない
            last = getattr(self, "_reassert_at", None)
            if last is not None and now - last >= self.REASSERT_GRACE_S:
                if dbg: print("[reassert] grace-expired", flush=True)
                return  # 連続要求が猶予(1.5s)を超過: restack を絞る
            ok = restack_above_stage(win, thief=_hidden_thief, d=d)
            if dbg:
                print("[reassert] bar=(%d,%d,%d,%d) ptr=(%d,%d) owner=%s ok=%s" % (
                    bx, by, self.w, self.h, px, py,
                    hex(owner) if owner else None, ok), flush=True)
            if ok:
                self._reassert_at = now
        except Exception:
            pass
        finally:
            try:
                if d is not None:
                    d.close()
            except Exception:
                pass

    def _drag(self, e):
        if isinstance(getattr(self, "_menu", None), dict):
            return  # インラインメニュー展開中はバードラッグ不可（押下は選択処理）
        if self.dock:
            return  # パネルモードは位置固定
        x, y = self._clamp_float(e.x_root - self._ox, e.y_root - self._oy)
        self.root.geometry(f"+{x}+{y}")
        self._body = (x, y, self.w, self.h)  # 本体矩形を窓と同期（面板展開基準）
        self.cfg["geometry"] = [x, y]
        save_config(self.cfg)
        self.maybe_reassert_stack()

    def toggle_mode(self):
        self.set_mode("gadget" if self.dock else "dock")

    def set_topmost(self, val):
        if IS_WSL:
            return  # WSLg: 窓は常に OR+topmost 固定。config も書き換えない
        self.cfg["topmost"] = bool(val)
        save_config(self.cfg)
        self._apply_layer_mode()
        if not self.dock and self._or_mode:
            self.root.attributes("-topmost", bool(val))
            raise_or_below(bool(val))

    def set_mode(self, mode):
        if IS_WSL:
            # WSLg: mode は常時ガジェット解釈。config も書き換えない（ゲート:
            # WSL 起動/操作で config.json の mode が変わってはならない）。
            return
        if mode == self.cfg["mode"]:
            return
        self.cfg["mode"] = mode
        save_config(self.cfg)
        self._apply_layer_mode()
        self.relayout()
        self.draw()

    def set_orient(self, val):
        if val == self.cfg.get("orient"):
            return
        self.cfg["orient"] = val
        save_config(self.cfg)
        self.relayout()
        self.draw()

    def toggle_item(self, key):
        items = self.cfg["items"]
        if items.get(key) and sum(1 for v in items.values() if v) <= 1:
            return  # 最後の1項目は消させない
        items[key] = not items.get(key)
        save_config(self.cfg)
        self.relayout()
        if self._inline_menu and isinstance(self._menu, dict):
            self._rebuild_menu()  # 面板を開いたままラベル/高さだけ作り直す
        else:
            self.draw()

    def move_item(self, key):
        """表示順を1つ右へ動かす（末尾なら先頭へ折返し）。非表示項目の位置は動かさない。"""
        order = self.cfg["order"]
        shown = [k for k in order
                 if self.cfg["items"].get(k) and not self.all_mets[k].unavailable()]
        if len(shown) <= 1 or key not in shown:
            return
        i = shown.index(key)
        shown.pop(i)
        shown.insert(0 if i == len(shown) else i + 1, key)  # 1つ右（末尾は先頭へ）
        it = iter(shown)
        self.cfg["order"] = [next(it) if k in shown else k for k in order]
        save_config(self.cfg)
        self.relayout()
        self.draw()

    # ---- メニュー ----------------------------------------------------------
    ITEM_NAMES = {"cpu": "CPU", "gpu": "GPU", "ram": "RAM",
                  "vram": "VRAM", "power": "GPU Power", "temp": "GPU Temp",
                  "cputemp": "CPU Temp", "cpupower": "CPU Power",
                  "fan": "GPU Fan", "cfrg": "CPU Freq", "net": "Network",
                  "disk": "Disk I/O", "ssdtemp": "SSD Temp",
                  "gclk": "GPU Clock", "load": "CPU Load", "memtemp": "DIMM Temp"}

    def _open_menu(self, e):
        if self._inline_menu:
            # 同一窓面板経路（pop-up 窓を作らない。WSL 既定。native でも手動可）
            if getattr(self, "_grab_active", False):
                return  # grab 中は事件が grab 転送側(_poll_menu_grab)へ届く
            if isinstance(self._menu, dict):
                self.close_menu()  # 再右クリック=閉じる
                return
            self.open_menu()
            return
        if self._menu is not None:
            try:
                self._menu.destroy()
            except tk.TclError:
                pass
        m = Menu(self.root, tearoff=0, bg="#1c2027", fg=FG, activebackground="#2e3440",
                 activeforeground=FG, bd=1, relief="solid", font=("DejaVu Sans", 9))
        g = Menu(m, tearoff=0)
        m.add_cascade(label="Layout", menu=g)
        # 現在の表示形式の選択肢は出さず、切り替え先のみを出す
        if self.dock:
            g.add_command(label="Gadget", command=lambda: self.set_mode("gadget"))
        else:
            g.add_command(label="Dock", command=lambda: self.set_mode("dock"))
        if not self.dock:  # 最前面・縦横はガジェット時のみ
            g.add_separator()
            tk_top = tk.BooleanVar(value=bool(self.cfg.get("topmost", True)))
            g.add_checkbutton(label="Always on top", variable=tk_top,
                              command=lambda: self.set_topmost(tk_top.get()))
            # 現在の配置の選択肢は出さず、切り替え先のみを出す
            g.add_command(label="Vertical" if self.cfg.get("orient", "h") == "h" else "Horizontal",
                          command=lambda: self.set_orient(
                              "v" if self.cfg.get("orient", "h") == "h" else "h"))
        it = Menu(m, tearoff=0)
        m.add_cascade(label="Show/Hide", menu=it)
        names = {"cpu": "CPU", "gpu": "GPU", "ram": "RAM",
                 "vram": "VRAM", "power": "GPU Power", "temp": "GPU Temp",
                 "cputemp": "CPU Temp", "cpupower": "CPU Power",
                 "fan": "GPU Fan", "cfrg": "CPU Freq", "net": "Network",
                 "disk": "Disk I/O", "ssdtemp": "SSD Temp",
                 "gclk": "GPU Clock", "load": "CPU Load", "memtemp": "DIMM Temp"}
        n_shown = sum(1 for k in names if self.cfg["items"].get(k)
                      and not self.all_mets[k].unavailable())
        for key in self.cfg.get("order", names):
            name = names[key]
            if self.all_mets[key].unavailable():
                it.add_command(label=f"{name} (n/a)", state="disabled")
                continue
            shown = bool(self.cfg["items"].get(key))
            label = f"Hide {name}" if shown else f"Show {name}"
            state = "disabled" if (shown and n_shown <= 1) else "normal"
            it.add_command(label=label, state=state,
                           command=lambda k=key: self.toggle_item(k))
        # 表示順の変更は右クリックメニューには出さない（config.json の "order" で編集）
        m.add_separator()
        m.add_command(label="Quit", command=self.root.destroy)
        self._menu = m
        m.tk_popup(e.x_root, e.y_root)
        # tk_popup 直後の一元経路だけで呼ぶ（再展開時も毎回ここを通る）。
        self.root.after(60, self._set_popup_opacity)

    def _set_popup_opacity(self):
        """tk_popup メニュー窓にコンポジタの窓透過（_NET_WM_WINDOW_OPACITY）を
        設定する。Tk 側の色は変えず、muffin/mutter に背後を薄く混ぜさせる。
        PB_MENU_ALPHA=0.0-1.0（既定 0.90）。>=0.995 ならプロパティ削除で完全不透明。
        窓が見つからない／例外時は何もしない（メニューは不透明のまま可）。
        インライン面板経路（PB_MENU=inline）はバー窓 alpha 0.92 が効くため未使用。"""
        try:
            a = float(os.environ.get("PB_MENU_ALPHA", "0.90"))
        except ValueError:
            a = 0.90
        a = min(max(a, 0.0), 1.0)
        try:
            from Xlib import display as xld
            d = xld.Display()
            stack = [d.screen().root]
            wins = []
            while stack:
                w = stack.pop()
                try:
                    kids = w.query_tree().children
                except Exception:
                    continue
                for c in kids:
                    try:
                        cls = c.get_wm_class()
                        if (cls and cls[1] == "Menu"
                                and re.fullmatch(r"!menu\d*",
                                                 cls[0], re.IGNORECASE)
                                and c.get_attributes().map_state == 2):
                            # override-redirect のマップ済みメニュー窓
                            # （Tk は WM_CLASS 実体を "!menu", "!menu2"... にする。
                            #  IsViewable=2。メニュー窓は描画用子窓を1つ持つので
                            #  子なし条件は付けられない）
                            wins.append(c)
                        else:
                            stack.append(c)
                    except Exception:
                        continue
            if not wins:
                return
            atom = d.intern_atom("_NET_WM_WINDOW_OPACITY")
            for win in wins:  # cascade 副メニュー窓が同時マップ済みなら全て
                if a >= 0.995:
                    win.delete_property(atom)
                else:
                    # 型アトムは d.intern_atom('CARDINAL')（Xlib.X.CARDINAL は存在しない）
                    win.change_property(atom, d.intern_atom("CARDINAL"), 32,
                                        [int(round(a * 0xFFFFFFFF))])
            d.flush()
        except Exception:
            if _PB_DEBUG:
                import traceback
                traceback.print_exc()

    # ---- インラインメニュー（同一窓面板。wm_managed/strut 連動なし）----------
    # 窓自身を拡大し同一 canvas 上に面板を描く。セル領域の画面座標は動かさない
    # （本体矩形 self._body を保持し、窓原点との差を top_off / left_off に）。
    def _menu_action(self, fn):
        """項目選択: メニューを閉じてから動作（モード/配置/topmost 変更は窓を
        作り直すため、面板を開いたままにできない）。"""
        self.close_menu()
        fn()

    def _build_menu_rows(self):
        """メニュー行を [(kind, label, cmd, checked|None, enabled)] で返す。
        項目構成は popup 版と同一: Layout 切替 / (ガジェット時のみ Always on top・
        縦横) / Items Show・Hide（n/a 無効、最後の1項目は消させない）/ Quit。"""
        rows = [("hdr", "Layout", None, None, False)]
        if self.dock:
            rows.append(("cmd", "Gadget",
                         lambda: self._menu_action(lambda: self.set_mode("gadget")),
                         None, True))
        else:
            rows.append(("cmd", "Dock",
                         lambda: self._menu_action(lambda: self.set_mode("dock")),
                         None, True))
            rows.append(("sep", "", None, None, False))
            rows.append(("check", "Always on top",
                         lambda: self._menu_action(
                             lambda: self.set_topmost(
                                 not bool(self.cfg.get("topmost", True)))),
                         bool(self.cfg.get("topmost", True)), True))
            horiz = self.cfg.get("orient", "h") == "h"
            rows.append(("cmd", "Vertical" if horiz else "Horizontal",
                         lambda: self._menu_action(
                             lambda: self.set_orient("v" if horiz else "h")),
                         None, True))
        rows.append(("hdr", "Show/Hide", None, None, False))
        names = self.ITEM_NAMES
        n_shown = sum(1 for k in names if self.cfg["items"].get(k)
                      and not self.all_mets[k].unavailable())
        for key in self.cfg.get("order", names):
            name = names[key]
            if self.all_mets[key].unavailable():
                rows.append(("cmd", f"{name} (n/a)", None, None, False))
                continue
            shown = bool(self.cfg["items"].get(key))
            label = f"Hide {name}" if shown else f"Show {name}"
            enabled = not (shown and n_shown <= 1)
            # Items 切替は面板を開いたままにできる（複数項目の切り替えが楽）
            rows.append(("cmd", label,
                         (lambda k=key: self.toggle_item(k)) if enabled else None,
                         None, enabled))
        rows.append(("sep", "", None, None, False))
        rows.append(("cmd", "Quit", self.quit, None, True))
        return rows

    def _menu_metrics(self, rows):
        """行リストから (面板幅, 面板高) と各行の (x, y, h) を計算する。"""
        x = MENU_PAD
        out = []
        total = MENU_PAD
        wmax = 0
        for kind, label, cmd, checked, enabled in rows:
            h = {"hdr": MENU_HDR_H, "sep": MENU_SEP_H,
                 "cmd": MENU_ROW_H, "check": MENU_ROW_H}[kind]
            out.append((x, total, h))
            total += h
            if kind in ("cmd", "check", "hdr"):
                prefix = "\u2713 " if kind == "check" and checked else "   "
                w = 2 * MENU_PAD + self._mfont.measure(prefix + label)
                wmax = max(wmax, w)
        return max(MENU_W_MIN, wmax), total + MENU_PAD, out

    def _apply_window_geom(self):
        """本体矩形 self._body とメニュー拡大分（self._menu が dict のとき）から
        実際の窓矩形を組み立てて geometry を適用する。メニュー閉時（popup  mode
        を含む）は窓=本体で従来動作と同一。拡大方向: 横バーは中心が画面下半分なら
        上、縦バーは中心が右半分なら左（逆方向に空間が無ければ反転）。"""
        bx, by, bw, bh = self._body
        mx, mw, mh = self.geom
        if isinstance(self._menu, dict):
            m = self._menu
            if not self.vertical:
                # 横バー: 縦へ拡大。バー中心が画面下半分なら上へ。
                side = "above" if (by + bh / 2.0) >= mh / 2.0 else "below"
                if side == "above" and by - m["h"] < 0:
                    side = "below"
                if side == "below" and by + bh + m["h"] > mh:
                    side = "above"
                ww = max(bw, m["w"])
                wx = bx - (ww - bw) // 2
                wx = max(mx, min(wx, mx + mw - ww))
                th = bh + m["h"]
                wy = by - m["h"] if side == "above" else by
                m["px0"] = (ww - m["w"]) // 2
                m["py0"] = 0 if side == "above" else bh
            else:
                # 縦バー: 横へ拡大。バー中心が右半分なら左へ出す。
                side = "left" if (bx + bw / 2.0) >= mx + mw / 2.0 else "right"
                if side == "left" and bx - m["w"] < mx:
                    side = "right"
                if side == "right" and bx + bw + m["w"] > mx + mw:
                    side = "left"
                ww = bw + m["w"]
                th = max(bh, m["h"])
                wx = bx - m["w"] if side == "left" else bx
                wy = by - (th - bh) // 2
                wy = max(0, min(wy, mh - th))
                m["px0"] = 0 if side == "left" else bw
                m["py0"] = (th - m["h"]) // 2
            m["side"] = side
            self.left_off = bx - wx
            self.top_off = by - wy
            if _PB_DEBUG:
                print("[menu] win=%dx%d+%d+%d body=%s panel px0=%s py0=%s %dx%d"
                      % (ww, th, wx, wy, self._body, m["px0"], m["py0"],
                         m["w"], m["h"]), flush=True)
        else:
            ww, th, wx, wy = bw, bh, bx, by
            self.left_off = 0
            self.top_off = 0
        size_changed = (ww, th) != getattr(self, "_last_win_size", None)
        self._last_win_size = (ww, th)
        self._win_w, self._win_h = ww, th
        self.root.geometry(f"{ww}x{th}+{wx}+{wy}")
        if hasattr(self, "cv"):
            self.cv.configure(width=ww, height=th)
        # OR 窓の bounding shape は「窓実寸」で張り直す（本体寸で ShapeSet した
        # 形状がメニュー拡大後の窓をクリップして面板が見えない罠）。WSLg は
        # 形状操作を使わないので触らない。
        if self._or_mode and size_changed and not IS_WSL:
            try:
                dd, win = find_my_window()
                if win is not None:
                    apply_bounding_shape(win, ww, th, self.dock)
                dd.close()
            except Exception:
                pass

    def open_menu(self):
        """バー窓を拡大してメニュー面板状態をつくり、再レイアウト＋描画。
        ついでに別接続で pointer+keyboard grab を張り、面板外クリック/Esc を
        拾う（grab 失敗時は focus_force + Tk バインディングにフォールバック。
        tk_popup の grab failed と違い、握らないだけで済む）。"""
        rows = self._build_menu_rows()
        mw, mh, offs = self._menu_metrics(rows)
        self._menu = {"rows": rows, "offs": offs, "w": mw, "h": mh,
                      "hover": -1}
        self._menu_open_at = time.monotonic()
        self._apply_window_geom()
        try:
            # Esc/キー受信のため窓にフォーカスを寄せる（XSetInputFocus 直発なので
            # OR 窓でも効く。grab が張れなかった時のフォールバック経路）。
            self.root.focus_force()
        except tk.TclError:
            pass
        self._start_menu_grab()
        self.draw()

    def close_menu(self):
        if not isinstance(self._menu, dict):
            return
        self._menu = None
        # grab スレッドは alive()=False を見て grab 解除＋接続クローズで終了する。
        self._grab_active = False
        self._apply_window_geom()
        self.draw()
        # grab 解除後は焦点が旧焦点窓へ戻るため、Esc→終了 経路を生かすよう
        # 自窓へ焦点を取り直す（OR 窓でも XSetInputFocus 直発なので効く）。
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    def quit(self):
        """終了: grab 転送フラグを下げてから窓を破棄（grab スレッドはメニュー
        閉状態を検知して自分で grab を解く）。"""
        self._grab_active = False
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _start_menu_grab(self):
        import threading
        self._grab_q = []  # 前回セッションの残り事象を捨ててから grab を張る
        try:
            from Xlib import display as xld
            d = xld.Display()
        except Exception:
            self._grab_active = False
            return
        if not try_menu_grab(d, self.root.winfo_id()):
            self._grab_active = False
            try:
                d.close()
            except Exception:
                pass
            return
        self._grab_active = True  # 診断用（Tk バインディング側の抑止にも使用）
        t = threading.Thread(
            target=menu_grab_loop,
            args=(d, self._grab_q, lambda: self._menu is not None),
            daemon=True)
        t.start()
        self.root.after(30, self._poll_menu_grab)

    def _poll_menu_grab(self):
        """grab 接続が積んだ事象を Tk ループ側で処理（30ms 間隔）。
        grab 中はバー内外の press/motion が全部 grab 接続へ転送される（Tk
        バインディングは発火しない＝二重処理なし）。面板ヒットテストはここ。"""
        if not isinstance(self._menu, dict):
            return
        q = getattr(self, "_grab_q", None)
        if q is None:
            return
        while q:
            act = q.pop(0)
            kind = act[0]
            if kind == "esc":
                self.close_menu()
                return
            if kind == "enter":
                self._activate_hovered()
                if not isinstance(self._menu, dict):
                    return
                continue
            wx = act[1] - self.root.winfo_x()
            wy = act[2] - self.root.winfo_y()
            btn = act[3] if len(act) > 3 else 1
            if kind == "press":
                if btn == 3:
                    # 再右クリック=閉じる（_open_menu と同じ判断）
                    self.close_menu()
                    return
                if btn != 1:
                    continue
                self._menu_pick(wx, wy)
                if not isinstance(self._menu, dict):
                    return
            elif kind == "motion":
                i = self._panel_row_at(wx, wy)
                if i != self._menu["hover"]:
                    self._menu["hover"] = i
                    self.draw()
        # メニューを開いている間（Items 切替で開いたままでも）ポーリング継続
        if isinstance(self._menu, dict):
            self.root.after(30, self._poll_menu_grab)

    def _menu_pick(self, wx, wy):
        """窓座標の面板行を実行（行外=メニュー外クリック=閉じる）。
        Tk バインディング（_click1）と grab 転送（_poll_menu_grab）の共通経路。"""
        i = self._panel_row_at(wx, wy)
        if i < 0:
            self.close_menu()  # 面板外＝バーのセル領域クリックも外クリック扱い
            return
        _k, _l, cmd, _c, en = self._menu["rows"][i]
        if en and cmd is not None:
            cmd()

    def _activate_hovered(self):
        """Return キー: ホバー中の項目を実行（無ホバーなら何もしない）。"""
        m = self._menu
        if not isinstance(m, dict):
            return
        i = m.get("hover", -1)
        if 0 <= i < len(m["rows"]):
            _k, _l, cmd, _c, en = m["rows"][i]
            if en and cmd is not None:
                cmd()

    def _rebuild_menu(self):
        """Items 切替後、ラベル（Show/Hide）と高さを作り直して開いたまま維持。"""
        if not isinstance(self._menu, dict):
            return
        rows = self._build_menu_rows()
        mw, mh, offs = self._menu_metrics(rows)
        self._menu.update({"rows": rows, "offs": offs, "w": mw, "h": mh,
                           "hover": -1})
        self._apply_window_geom()
        self.draw()

    def _panel_row_at(self, x, y):
        """窓座標 (x,y) が面板の何行目か返す（面板外/行外は -1）。"""
        m = self._menu
        if not isinstance(m, dict):
            return -1
        px, py = m["px0"], m["py0"]
        if not (px <= x < px + m["w"] and py <= y < py + m["h"]):
            return -1
        lx, ly = x - px, y - py
        for i, (_ox, oy, h) in enumerate(m["offs"]):
            if oy <= ly < oy + h:
                return i
        return -1

    def _focus_out(self, e):
        """FocusOut: 他窓へフォーカスが移った時のみ面板を閉じる。
        grab 由来（NotifyGrab/NotifyUngrab/NotifyWhileGrabbed）や自窗内移動
        （NotifyInferior/NotifyVirtual 等）、開直後の猶予は無視する（拾うと
        「開いた瞬間に閉じる」）。"""
        if not isinstance(self._menu, dict):
            return
        detail = getattr(e, "detail", "") or ""
        if detail in ("NotifyGrab", "NotifyUngrab", "NotifyWhileGrabbed",
                      "NotifyInferior", "NotifyVirtual", "NotifyPointer",
                      "NotifyPointerRoot"):
            return
        if time.monotonic() - getattr(self, "_menu_open_at", 0.0) < 0.8:
            return
        if getattr(self, "_grab_active", False):
            return  # grab 転送側が外クリックで閉じる（フォーカス移動と無関係）
        self.close_menu()

    def _key_esc(self, e):
        """Esc: メニュー展開中なら閉じるだけ、閉じていなければ終了。
        grab 成功中は grab 接続の esc 事象だけが処理する（二重発火防止）。"""
        if getattr(self, "_grab_active", False):
            return
        if isinstance(self._menu, dict):
            self.close_menu()
            return
        self.quit()

    def _click1(self, e):
        """左クリック: 面板内なら項目選択、面板外の窓内クリックは閉じる。
        閉店中は通常のドラッグ開始へ。grab 成功中は grab 転送側が処理する。"""
        if getattr(self, "_grab_active", False):
            return
        if isinstance(self._menu, dict):
            self._menu_pick(e.x, e.y)
            return
        self._grab(e)

    def _motion(self, e):
        """ホバー行のハイライト更新（選択状態は描画時に hover idx として使う）。"""
        if getattr(self, "_grab_active", False):
            return
        m = self._menu
        if not isinstance(m, dict):
            return
        i = self._panel_row_at(e.x, e.y)
        if i != m["hover"]:
            m["hover"] = i
            self.draw()

    # ---- 描画 --------------------------------------------------------------
    def draw(self):
        cv = self.cv
        cv.delete("all")
        lo = getattr(self, "left_off", 0)
        for i, met in enumerate(self.visible_mets()):
            if self.vertical:
                x0, y0 = lo, i * CELL_H + getattr(self, "top_off", 0)
            else:
                x0, y0 = PAD + i * CELL_W + lo, getattr(self, "top_off", 0)
            self._draw_cell(cv, met, x0, y0)
        self._draw_menu(cv)

    def _draw_menu(self, cv):
        """インラインメニュー面板を canvas に描く（別窓ではない。popup  mode は
        _menu が dict でないので常に何もしない）。"""
        m = self._menu
        if not isinstance(m, dict):
            return
        px, py = m["px0"], m["py0"]
        cv.create_rectangle(px, py, px + m["w"], py + m["h"],
                            fill="#1c2027", outline="#4c566a")
        for i, (kind, label, cmd, checked, enabled) in enumerate(m["rows"]):
            _ox, oy, rh = m["offs"][i]
            yy, yc = py + oy, py + oy + rh // 2
            if kind == "sep":
                cv.create_line(px + 6, yc, px + m["w"] - 6, yc, fill=GRID)
            elif kind == "hdr":
                cv.create_text(px + MENU_PAD + 2, yc, anchor="w", text=label,
                               fill=OK, font=("DejaVu Sans", 8, "bold"))
            else:
                hovered = enabled and i == m["hover"]
                if hovered:
                    cv.create_rectangle(px + 2, yy + 1, px + m["w"] - 2,
                                        yy + rh - 1, fill="#2e3440", outline="")
                prefix = "\u2713 " if (kind == "check" and checked) else ""
                col = FG if enabled else "#59606f"
                if prefix:
                    col = "#a3be8c"
                cv.create_text(px + MENU_PAD + 2, yc, anchor="w",
                               text=prefix + label, fill=col, font=self._mfont)

    def _draw_cell(self, cv, m, x0, y0):
        # セル高は本体矩形基準（self.h=本体高さ。メニューで窓が伸びてもセルは伸びない）
        ch = CELL_H if self.vertical else self.h
        gx0, gx1 = x0 + 4, x0 + CELL_W - 4
        label_y = y0 + 8
        top, bot = y0 + 16, y0 + ch - 2
        c = m.ui_color()
        lv = m.level()
        # 項目ごとの背景（固有色を薄く混ぜる）でセルの境界を分かりやすくする
        cv.create_rectangle(x0, y0, x0 + CELL_W, y0 + ch,
                            fill=blend(BG, m.color, 0.12), outline=blend(BG, m.color, 0.28))
        cv.create_rectangle(gx0, top, gx1, bot,
                            fill=blend(BG, m.color, 0.20), outline="")
        # 波形線〜帯下端の縦グラデ塗り（線付近が濃く bot で BG へ溶ける）。
        # 水平帯に分割した polygon 近似。グリッド線・波形線より先に置く。
        pts = m.polyline(gx0, gx1, top, bot)
        nbands = 8
        for k, poly in enumerate(fill_bands(pts, top, bot, nbands)):
            t = 0.85 * (nbands - k) / nbands  # 上端の帯が最も濃く、下へ行くほど BG へ
            cv.create_polygon(*poly, fill=blend(BG, c, t), outline="")
        if lv:  # 警告/危険はセル枠を描いて目立たせる
            cv.create_rectangle(x0 + 1, y0 + 1, x0 + CELL_W - 1, y0 + ch - 1,
                                outline=c, width=2 if lv == 2 else 1)
        cv.create_line(gx0, bot, gx1, bot, fill=blend(BG, m.color, 0.45))
        cv.create_text(gx0, label_y, anchor="w", text=m.label,
                       fill=c if lv else FG,
                       font=("DejaVu Sans Mono", 7, "bold" if lv else "normal"))
        cv.create_text(gx1, label_y, anchor="e", text=m.value_text(), fill=c,
                       font=("DejaVu Sans Mono", 8 if lv < 2 else 9, "bold"))
        cv.create_line(*pts, fill=c, width=2 if lv else 1)


def main():
    if "--selftest" in sys.argv:
        mets = build_metrics()
        for _ in range(3):
            sample_cpu(mets)
            sample_gpu(mets)
            print("  ".join(f"{m.label}={m.value_text()}" for m in mets.values()))
            if not GPUS:
                break
            import time
            time.sleep(1)
        return

    cfg = load_config()
    if "--mode" in sys.argv:
        cfg["mode"] = sys.argv[sys.argv.index("--mode") + 1]
    if "--offset" in sys.argv:
        cfg["dock_offset_x"] = int(sys.argv[sys.argv.index("--offset") + 1])
    save_config(cfg)

    mets = build_metrics()
    root = tk.Tk(className="PulseBar")
    root.title("PulseBar")
    bar = Bar(root, mets, cfg)
    psutil.cpu_percent(interval=None)  # 初回呼び出しの基準値リセット

    # kill -USR1 で gadget/dock 切替（Tk のイベントループ内で処理する）
    want_toggle = []
    signal.signal(signal.SIGUSR1, lambda s, f: want_toggle.append(True))

    root.after(400, bar.after_show)

    def tick():
        if want_toggle:
            want_toggle.clear()
            bar.toggle_mode()
        sample_cpu(mets)
        sample_gpu(mets)
        bar.draw()
        # dock_auto: 帯アプレットの縁を5秒ごとに取り直し（gdbus は重いので間引く）
        bar._auto_tick += 1
        if bar._auto_tick >= 5:
            bar._auto_tick = 0
            bar.refresh_dock_auto()
        # 帯に重なっている間は毎tick stage窓直上へ自分を作り直す（常時選択可能に）
        bar.maybe_reassert_stack()
        root.after(INTERVAL_MS, tick)

    bar.draw()
    root.after(200, tick)
    root.mainloop()


if __name__ == "__main__":
    main()
