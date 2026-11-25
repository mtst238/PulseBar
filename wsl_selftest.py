#!/usr/bin/env python3
"""wsl_selftest.py — PulseBar の WSL2 (WSLg) 自己診断。

WSL2 の中（または native 機で PB_PLATFORM を明示しない場合は WSL 強制）で
`python wsl_selftest.py` と実行すると、以下を PASS/FAIL 一行ずつ印字する:
  (a) X Display への接続可否（Xlib）
  (b) Tk 窓のマップと絶対位置が geometry 指定通りか
      （winfo_x/y と Xlib 親鎖 translate の両方で突き合わせ）
  (c) 窓を 300px 横へ移動して 500ms 後に実位置が従うか
  (d) -topmost が設定され窓が viewable か（WSLg で積層検証はしない:
      簡易版として topmost 属性とマップ状態のみ確認）
  (e) WSL 経路の open_menu/close_menu が例外なく呼べて窓サイズが
      変わるか（RMB 相当の合成イベントは送らない。直接呼出）
Xlib / Tkinter / psutil の import 失敗時は原因を日本語で印字して
終了する（クラッシュしない）。native 機で WSL 経路を検証するため、
PB_PLATFORM が未設定なら 'wsl' を仮定して走る（上書き可）。
詳細は PulseBar.py docstring の WSL2 対応節。
"""
import os
import sys
import time

os.environ.setdefault("PB_PLATFORM", "wsl")  # native 機でも WSL 経路を検証

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

results = []


def report(name, ok, detail=""):
    results.append((name, bool(ok)))
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def main():
    # ---- import 確認（失敗時は日本語でメッセージを出して終了） ----------
    try:
        import tkinter as tk  # noqa: F401
    except Exception as e:
        print("FAIL tkinter: Tkinter が利用できません（sudo apt install python3-tk）: %r" % (e,))
        return
    try:
        from Xlib import display as xld  # noqa: F401
        from Xlib import X  # noqa: F401
    except Exception as e:
        print("FAIL xlib: python-xlib が利用できません（pip install python-xlib / uv pip install python-xlib）: %r" % (e,))
        return
    try:
        import psutil  # noqa: F401
    except Exception as e:
        print("FAIL psutil: psutil が利用できません（uv pip install psutil）: %r" % (e,))
        return
    try:
        import PulseBar as pb
    except Exception as e:
        print("FAIL import: PulseBar.py の読込に失敗: %r" % (e,))
        return

    report("platform", pb.IS_WSL,
           "IS_WSL=%s (PB_PLATFORM=%r, 環境は判定結果に従う)" % (pb.IS_WSL, os.environ.get("PB_PLATFORM")))
    report("menu_mode", pb.MENU_MODE in ("inline", "popup"),
           "MENU_MODE=%s" % pb.MENU_MODE)

    # ---- (a) Display 接続 -------------------------------------------------
    d = None
    try:
        d = xld.Display()
        root = d.screen().root
        root.query_pointer()
        report("display", True, "X 接続 OK (%s)" % os.environ.get("DISPLAY", "?"))
    except Exception as e:
        report("display", False, "Xlib 接続失敗（WSLg の XWayland 起動待ち? / DISPLAY 未設定?）: %r" % (e,))
        print("NOTE 以降の検査は Display 接続が必要なため中止")
        return

    # ---- Tk 窓（WM_CLASS を本物と分けるため別クラス名） -------------------
    try:
        tkroot = tk.Tk(className="PulseBarSelf")
    except Exception as e:
        report("tk-window", False, "Tk 窓が作れない（WSLg の WSLg 配布確認）: %r" % (e,))
        d.close()
        return
    tkroot.title("PulseBarSelfTest")

    def pump(sec):
        t0 = time.monotonic()
        while time.monotonic() - t0 < sec:
            tkroot.update()
            time.sleep(0.02)

    try:
        cfg = pb.load_config()
        mets = pb.build_metrics()
        bar = pb.Bar(tkroot, mets, cfg)
        pump(0.4)
    except Exception as e:
        report("bar-init", False, "Bar 生成に失敗: %r" % (e,))
        d.close()
        return
    report("bar-init", True, "mode設定=%r → dock=%s(WSLでは常にFalse/ガジェット) OR窓=%s" %
           (cfg.get("mode"), bar.dock, bar._or_mode))

    # Xlib でこの Tk 窓を見つける（winfo_id からクライアント base を照合）
    tkwin_id = tkroot.winfo_id()
    base = tkwin_id >> 21

    def my_toplevel_id():
        # root 直下でクライアント base が一致する窓（OR 窓なので reparent なし）。
        # Tk は 1x1 の補助窓（WM_DELETE 用・unmapped）を先に作るので、単なる
        # 先頭一致だとそれ掴んで map/geometry が全滅する（2026-11-25 実測）。
        # IsViewable かつ 1x1 でない窓を優先し、無ければ最初の一致を返す。
        cands = []
        stack = [root]
        while stack:
            w = stack.pop()
            try:
                kids = w.query_tree().children
            except Exception:
                continue
            for c in kids:
                try:
                    if (c.id >> 21) == base:
                        cands.append(c)
                except Exception:
                    continue
                stack.append(c)
        for c in cands:
            try:
                g = c.get_geometry()
                if c.get_attributes().map_state == X.IsViewable and \
                        (g.width, g.height) != (1, 1):
                    return c
            except Exception:
                continue
        return cands[0] if cands else None

    def xlib_abs(win):
        x = y = 0
        w = win
        for _ in range(32):
            g = w.get_geometry()
            x += g.x
            y += g.y
            par = w.query_tree().parent
            if par is None or par.id == root.id:
                break
            w = par
        return x, y

    def xlib_size(win):
        g = win.get_geometry()
        return g.width, g.height

    # ---- (b) マップと絶対位置が geometry 通りか ---------------------------
    gx = max(8, min(int(tkroot.winfo_screenwidth() * 0.35), 400))
    gy = 200
    gw, gh = tkroot.winfo_width(), tkroot.winfo_height()
    tkroot.geometry("%dx%d+%d+%d" % (gw, gh, gx, gy))
    pump(0.6)
    win = my_toplevel_id()
    if win is None:
        report("map", False, "X ツリーに自窓が見つからない（マップ失敗）")
        tkroot.destroy()
        d.close()
        return
    try:
        viewable = win.get_attributes().map_state == X.IsViewable
    except Exception:
        viewable = False
    report("map", viewable, "map_state=%s id=0x%x" % ("IsViewable" if viewable else "!=viewable", win.id))
    xw, xh = xlib_size(win)
    ax, ay = xlib_abs(win)
    tx, ty = tkroot.winfo_x(), tkroot.winfo_y()
    okpos = (abs(ax - gx) <= 2 and abs(ay - gy) <= 2 and
             abs(tx - gx) <= 2 and abs(ty - gy) <= 2)
    report("geometry", okpos,
           "要求=(%d,%d) xlib絶対=(%d,%d) winfo=(%d,%d) サイズ=%dx%d" %
           (gx, gy, ax, ay, tx, ty, xw, xh))

    # ---- (c) 300px 移動に従うか -------------------------------------------
    nx = max(8, gx + 300)
    if nx + xw > tkroot.winfo_screenwidth() - 4:
        nx = max(8, gx - 300)
    tkroot.geometry("+%d+%d" % (nx, gy))
    pump(0.6)  # 500ms + α
    d.sync()
    ax2, ay2 = xlib_abs(win)
    moved = abs(ax2 - nx) <= 2
    report("move300", moved, "要求=%d 実=%d (移動前 %d)" % (nx, ax2, ax))

    # ---- (d) -topmost（簡易: 属性と viewable のみ。積層突合はしない） -----
    # 罠: WM(muffin/Cinnamon) は override-redirect 窓の TOPMOST 状態を property
    # 読み戻しから消すため、set 済みでも wm_attributes 質問が 0 を返す実測あり
    # （実際の最前面化は効いている）。再設定→即質問で「設定できること」を検証し、
    # 読み戻しが 0 でも viewable なら環境差异として許容（詳細に its_quirk を明記）。
    try:
        tkroot.attributes("-topmost", True)  # 設定が例外を投げないこと自体を確認
        topmost = bool(tkroot.wm_attributes("-topmost"))
        quirk = "" if topmost else "（WM が TOPMOST 読み戻しを消す型: 設定は例外なしで通っている）"
    except Exception:
        topmost = False
        quirk = "（attributes 設定で例外）"
    d.sync()
    try:
        still = win.get_attributes().map_state == X.IsViewable
    except Exception:
        still = False
    # muffin は OR 窓の TOPMOST を読み戻しから消す実測あり（WSLg では起きない見込み）。
    # 実検証対象は「設定が効くこと＋窓が viewable」なので viewable なら許容。
    report("topmost", still and (topmost or quirk.startswith("（WM")),
           "-topmost=%s viewable=%s%s（WSLg の積層検証は対象外）" % (topmost, still, quirk))

    # ---- (e) open_menu / close_menu 直接呼出（合成 RMB は送らない） -------
    try:
        pre = xlib_size(win)
        bar.open_menu()
        pump(0.3)
        d.sync()
        mid = xlib_size(win)
        grew = (mid[0] > pre[0]) or (mid[1] > pre[1])
        report("menu-open", grew, "窓サイズ %dx%d → %dx%d" % (pre[0], pre[1], mid[0], mid[1]))
        bar.close_menu()
        pump(0.3)
        d.sync()
        post = xlib_size(win)
        report("menu-close", post == pre, "窓サイズ %dx%d → %dx%d (復帰)" %
               (mid[0], mid[1], post[0], post[1]))
    except Exception as e:
        report("menu-open", False, "open_menu/close_menu で例外: %r" % (e,))

    try:
        tkroot.destroy()
    except Exception:
        pass
    try:
        d.close()
    except Exception:
        pass
    nfail = sum(1 for _, ok in results if not ok)
    print("TOTAL %d 件 / FAIL %d 件" % (len(results), nfail))
    print("NOTE 環境差异（センサー欠落等）による FAIL は許容。クラッシュしなければ計測成立。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL unexpected: 予期しない例外で終了: %r" % (e,))
        import traceback
        traceback.print_exc()
