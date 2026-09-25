#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Example: the observe -> act -> verify loop, minimal version.

This is the skeleton every desktop automation should follow. It drives Notepad,
but the shape is identical for any app.

Run:  python examples/basic_walkthrough.py
"""
import os
import subprocess
import sys
import tempfile
import time

CC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "scripts", "cc.py")
PY = sys.executable


def cc(*args, check=True):
    r = subprocess.run([PY, CC] + [str(a) for a in args],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if check and r.returncode != 0:
        raise SystemExit("cc.py %s failed:\n%s" % (" ".join(map(str, args)), out))
    return r.returncode, out


def main():
    tmp = tempfile.gettempdir()

    # A unique filename makes the window title unique, so we can never
    # accidentally target somebody else's Notepad window.
    tag = "cc_demo_%d" % int(time.time())
    target = os.path.join(tmp, tag + ".txt")
    open(target, "w", encoding="utf-8").close()

    print("[1] launching Notepad on %s" % target)
    nb = subprocess.Popen(["notepad.exe", target])
    try:
        # OBSERVE ------------------------------------------------------------
        print("[2] waiting for the window to appear")
        _, out = cc("waitwin", "--win", tag, "--timeout", "15")
        print("    " + out)

        hwnd = out.split()[2] if len(out.split()) > 2 else "?"

        print("[3] where is it?")
        _, info = cc("info", "--win", tag)
        print("    " + info.replace("\n", "\n    "))

        # ACT ----------------------------------------------------------------
        # focus verifies the foreground window really changed before we type.
        print("[4] focusing")
        _, out = cc("focus", "--win", tag)
        print("    " + out.replace("\n", "\n    "))
        if "✗" in out:
            raise SystemExit("focus failed - refusing to type into an unknown window")

        print("[5] typing")
        text = "Written by computer-control.\n中文也能输入。\n"
        _, out = cc("type", text)
        print("    " + out)

        # VERIFY -------------------------------------------------------------
        print("[6] screenshot to confirm")
        shot = os.path.join(tmp, "cc_demo_result.png")
        cc("shot", "--win", tag, "--out", shot, "--maxw", "1200")
        print("    -> %s" % shot)

        # Read the text back through the clipboard - a second, independent check
        # that does not rely on looking at a screenshot.
        cc("hotkey", "ctrl", "a")
        cc("hotkey", "ctrl", "c")
        time.sleep(0.3)
        _, got = cc("clip", "--get")
        print("[7] clipboard readback: %r" % got[:60])
        print("    match: %s" % ("YES" if "computer-control" in got else "NO"))

        # Also demonstrate a right-click, which opens a context menu.
        print("[8] right-clicking inside the window (context menu)")
        cc("rclick", "--win", tag, "--rx", 300, "--ry", 200)
        time.sleep(0.6)
        cc("key", "esc")          # dismiss the menu
        time.sleep(0.3)

    finally:
        # Always clean up the process you started. Never alt+f4 a window with
        # unsaved changes - the save dialog can be answered by a stray keystroke.
        print("[9] terminating Notepad")
        nb.terminate()
        time.sleep(0.5)
        try:
            os.remove(target)
        except OSError:
            pass


if __name__ == "__main__":
    main()
