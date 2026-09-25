#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Example: search on Bilibili's desktop client.

Demonstrates the pattern this toolkit was built for — driving an Electron app
that has no usable API from the outside:

  1. find the window by PROCESS, not title (Electron titles change constantly)
  2. activate it and verify the foreground window really changed
  3. screenshot the window's client area so we can see the search box
  4. click it using window-relative coordinates
  5. type the query
  6. press Enter
  7. wait for the UI to settle, then screenshot the result

Run:  python examples/search_bilibili.py "关键词"
"""
import os
import subprocess
import sys
import tempfile
import time

CC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "scripts", "cc.py")
PY = sys.executable

# Bilibili's desktop client runs as several processes; this fragment matches them.
PROCESS = "bilibili"


def run(*args, check=True):
    r = subprocess.run([PY, CC] + [str(a) for a in args],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if check and r.returncode != 0:
        raise SystemExit("cc.py %s failed (%d):\n%s"
                         % (" ".join(str(a) for a in args), r.returncode, out))
    return r.returncode, out


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "鹈鹕骑车"
    tmp = tempfile.gettempdir()

    # 1. Is the app even running? waitwin blocks until it appears.
    print("[1] waiting for a %r window ..." % PROCESS)
    rc, out = run("waitwin", "--process", PROCESS, "--timeout", "10", check=False)
    if rc != 0:
        raise SystemExit("Bilibili is not running. Start it first.")
    print("    " + out)

    # 2. Activate it. `focus` verifies the foreground window actually changed —
    #    SetForegroundWindow silently fails when the foreground lock is held.
    print("[2] focusing ...")
    _, out = run("focus", "--process", PROCESS)
    print("    " + out.replace("\n", "\n    "))

    # 3. Look at just this window's client area, with a coordinate grid.
    shot = os.path.join(tmp, "bili_before.png")
    print("[3] screenshot -> %s" % shot)
    run("shot", "--process", PROCESS, "--out", shot, "--grid", "200", "--maxw", "1600")
    print("    open it, find the search box, then set SEARCH_BOX below")

    # Fill these in from the screenshot. They are relative to the window's
    # CLIENT AREA, so they survive the user moving or resizing the window.
    SEARCH_BOX = (int(os.environ.get("SEARCH_X", 640)),
                  int(os.environ.get("SEARCH_Y", 46)))

    # 4. Click the search box.
    print("[4] clicking search box at %s (window-relative)" % (SEARCH_BOX,))
    run("--dry-run", "click", "--process", PROCESS,
        "--rx", SEARCH_BOX[0], "--ry", SEARCH_BOX[1])
    run("click", "--process", PROCESS,
        "--rx", SEARCH_BOX[0], "--ry", SEARCH_BOX[1])
    time.sleep(0.4)

    # 5. Clear whatever is there, then type.
    print("[5] typing %r" % query)
    run("hotkey", "ctrl", "a")
    run("type", query)

    # 6. Submit.
    print("[6] pressing Enter")
    run("key", "enter")

    # 7. Wait for the UI to stop changing, then capture the result.
    print("[7] waiting for the UI to settle ...")
    rc, out = run("stable", "--timeout", "10", check=False)
    print("    " + out)

    after = os.path.join(tmp, "bili_after.png")
    run("shot", "--process", PROCESS, "--out", after, "--maxw", "1600")
    print("[8] result screenshot -> %s" % after)
    print("done.")


if __name__ == "__main__":
    main()
