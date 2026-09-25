# computer-control

**Give your AI agent eyes and hands on Windows.**

A zero-dependency desktop automation toolkit for AI agents. Screenshot the screen, move the mouse with human-like trajectories, click, type, read the clipboard, and find windows — all through a single Python script that talks straight to `user32.dll` via `ctypes`.

No `pyautogui`. No `pynput`. No AutoHotkey. No `pip install` beyond Pillow (and only for screenshots).

```
$ python cc.py shot --out screen.png --grid 300     # look at the screen
$ python cc.py click --win notepad --rx 400 --ry 60 # click inside a window
$ python cc.py type "hello world"                   # type into it
```

---

## Why

Browser automation is a solved problem. **Native desktop apps are not.** When the thing you need to operate has no API — a proprietary client, a legacy tool, a game launcher, an Electron app with a canvas UI — your only option is to drive the mouse and keyboard like a human does.

This toolkit was built for that case, and specifically for the failure modes that show up in practice:

- **DPI scaling breaks every coordinate.** Miss `SetProcessDpiAwareness` and `GetSystemMetrics` returns 1440×900 while your screenshot is 2880×1800. Every click lands at half the intended position.
- **Electron window titles change constantly.** Matching on title text works until the page navigates. Match on process name instead.
- **Absolute coordinates rot.** The moment the user drags the window, every hardcoded position is wrong. Use window-relative coordinates.
- **Robots move like robots.** Perfectly straight, constant-velocity motion is trivially detectable and looks wrong in recordings. Add entropy.

## Features

### Screen

| Command | Description |
|---|---|
| `screen` | Physical resolution and coordinate range |
| `monitors` | All monitors with their bounds |
| `shot` | Screenshot — full screen, a region, or a single window's client area |
| `pixel` | Read a pixel's colour (RGB + hex) |
| `stable` | Block until the screen stops changing — wait for a page to load |

`shot --grid 300` overlays a labelled coordinate grid so an agent can read off pixel positions directly from the image.

### Mouse

| Command | Description |
|---|---|
| `move` | Move to absolute or relative coordinates |
| `hover` | Move and hold, without clicking |
| `click` / `rclick` / `dclick` / `mclick` | Left, right, double, middle |
| `drag` | Press, move, release |
| `down` / `up` | Hold and release separately |
| `scroll` | Wheel |

Every click command accepts **window-relative coordinates**:

```bash
python cc.py click --win notepad --rx 400 --ry 60   # client-area origin + (400, 60)
python cc.py click --process chrome --center        # dead centre of the window
```

### Keyboard

```bash
python cc.py type "你好 world"        # Unicode, including CJK
python cc.py key enter
python cc.py hotkey ctrl shift s
```

Typing is batched into a single `SendInput` call — 36 mixed CJK/Latin characters land in **0.004 s**.

### Clipboard

```bash
python cc.py clip --set "text to paste"
python cc.py clip --get
```

### Windows

| Command | Description |
|---|---|
| `windows` | List visible windows (HWND, process, PID, title) |
| `info` | Window rect, client rect, class name, state |
| `focus` | Bring to foreground, with verification |
| `waitwin` | Block until a window appears |
| `winstate` | Minimize / maximize / restore / close |

Windows can be located three ways, and you should prefer the second:

```bash
--win      "some title fragment"     # brittle: Electron titles change
--process  chrome                    # robust
--class    Chrome_WidgetWin_1        # most precise
```

## Human entropy

Mouse movement is not a straight line. By default each move is:

- **curved** — a quadratic Bézier with a randomly offset control point
- **overshooting** — for distances over ~140 px, the cursor drifts past the target and corrects back
- **jittered** — Gaussian noise of roughly 1 px per step, mimicking hand tremor
- **irregularly paced** — ±20 % per-step timing variance, with occasional micro-pauses
- **exactly landed** — the final position is snapped to the true target

Measured over a 1442 px move:

| Mode | Max deviation from straight line | Landing error |
|---|---|---|
| `--no-human` | 0.6 px | 0.0 px |
| default | **8.9 px** | **0.0 px** |

The path looks human. The landing is exact. Pass `--no-human` when you need a true straight line, such as aligning to a drawn guide.

## Installation

Requires Python 3.8+ on Windows. Only `Pillow` is needed, and only for screenshots and `stable`.

```bash
git clone https://github.com/<you>/computer-control.git
cd computer-control
pip install pillow        # optional, for screenshots
python scripts/cc.py screen
```

## Usage as an agent skill

`SKILL.md` is written as a skill descriptor for agent harnesses that support them (WorkBuddy, Claude Code, and similar). It documents the commands, the coordinate system, the standard observe-act-verify workflow, and the safety rules an agent must follow.

If your harness supports skills, drop this directory into its skills folder. Otherwise, just call `scripts/cc.py` directly — it is a plain CLI.

## Workflow an agent should follow

```
1. shot --grid 300 --maxw 1400     → look, locate the target
2. focus --process <app>           → activate, verify the title is right
3. --dry-run click ...             → confirm the parameters
4. click ...
5. stable --timeout 8              → wait for the UI to settle
6. shot --out after.png            → verify it worked
```

**Never skip the verification steps.** An agent that clicks without looking is a liability.

## Safety

This tool genuinely controls the computer. It can destroy work.

- **Confirm the target window before typing.** `type` sends to whatever has focus. Always check the title `focus` reports.
- **Prefer `--process` over title matching.** Matching the generic word "Notepad" once sent test text into a user's open `server.log`.
- **Never close a window with `alt+f4`.** It raises a save dialog, and a subsequent keystroke can confirm "Save". Terminate processes you started instead.
- **`--dry-run` before anything destructive.**
- **Ask the user before deleting, sending, paying, or submitting.**

## How it works

| Technique | Why it matters |
|---|---|
| `SendInput` for all input | Reliable and atomic; `mouse_event` and `keybd_event` are deprecated |
| `INPUT` struct must be 40 bytes on x64 | Wrong size or field order fails silently — no exception, no input |
| `KEYEVENTF_UNICODE` for text | VK codes cannot express CJK or emoji |
| `SetProcessDpiAwareness(2)` | Without it every coordinate is off by the scale factor |
| `AttachThreadInput` before `SetForegroundWindow` | Plain `SetForegroundWindow` fails when the foreground lock is held |
| Batched `SendInput` arrays | One syscall for N keystrokes instead of N syscalls |
| `GetPixel` via GDI for colour reads | Cheaper than grabbing a screenshot for one pixel |

## Requirements

- Windows 10 / 11 (x64)
- Python 3.8+
- Pillow — only for `shot`, `stable`

## License

MIT — see [LICENSE](LICENSE).
