# computer-control

**Eyes and hands for your AI agent, on Windows.**

A desktop automation toolkit built for agents. Screenshot the screen, move the mouse along human-looking paths, click, type, read the clipboard, find windows — all from one Python script that talks straight to `user32.dll` through `ctypes`.

No `pyautogui`. No `pynput`. No AutoHotkey. Nothing to install beyond Pillow, and only if you want screenshots.

```
$ python cc.py shot --out screen.png --grid 300     # look
$ python cc.py click --win notepad --rx 400 --ry 60 # click inside a window
$ python cc.py type "hello world"                   # type
```

---

## Why this exists

Browser automation is a solved problem. **Native desktop apps are not.**

When the thing you need to operate has no API — a closed-source client, a ten-year-old internal tool, a game launcher, an Electron app that draws its whole UI on a canvas — your only option is to drive the mouse and keyboard the way a person would.

I built this for that case, and I built it around the specific ways it goes wrong:

**DPI scaling silently breaks every coordinate.** Forget `SetProcessDpiAwareness` and `GetSystemMetrics` reports 1440×900 while your screenshot is 2880×1800. Every click lands at half the intended distance. There is no error. It just misses. I lost an afternoon to this one.

**Electron window titles change constantly.** Match on title text and your automation dies the moment the page navigates. Match on process name instead.

**Absolute coordinates rot.** The user drags the window once and every hardcoded position is wrong. So every click command accepts window-relative coordinates.

**Robots move like robots.** Perfectly straight, constant-velocity motion looks wrong in a recording and is trivial to detect. So the default path is deliberately imperfect.

## What it does

### Looking

`screen` for resolution, `monitors` for every display's bounds, `pixel` to read one pixel's colour.

`shot` captures the full screen, a region, or a single window's client area. Add `--grid 300` and it overlays a labelled coordinate grid — **the labels are real pixel values**, so an agent can read positions straight off the image instead of estimating. I added that feature after estimating coordinates from screenshots and missing three times in a row.

`stable` blocks until the screen stops changing — the right way to wait for a page to load. It beats `sleep 3` in both directions: it returns in 0.7 s when things are fast, and it keeps waiting when they are not.

### Mouse

`move` `hover` `click` `rclick` `dclick` `mclick` `drag` `down` `up` `scroll`. Left, right, double, middle, drag, hover, press-and-hold — all of it.

Every click command takes **window-relative coordinates**:

```bash
python cc.py click --win notepad --rx 400 --ry 60   # client-area origin + (400, 60)
python cc.py click --process chrome --center        # dead centre of the window
```

So the automation survives the user moving or resizing the window.

### Typing

```bash
python cc.py type "你好 world"        # Unicode, CJK included
python cc.py key enter
python cc.py hotkey ctrl shift s
```

CJK works because text goes through `KEYEVENTF_UNICODE` rather than virtual key codes — VK codes simply cannot express those characters.

Keystrokes are batched into a single `SendInput` call. **36 mixed CJK/Latin characters land in 0.004 s.** Calling `SendInput` per character is an order of magnitude slower for no benefit.

### Clipboard

```bash
python cc.py clip --set "text to paste"
python cc.py clip --get
```

Don't skip this one. Reading the clipboard back is the most reliable way to **verify that typing worked** — it beats a screenshot because nothing has to be judged by eye. The example scripts use it as a second, independent check.

### Windows

`windows` lists them, `info` reports geometry, `focus` activates, `waitwin` blocks until one appears, `winstate` minimizes or closes.

Three ways to locate a window. **Prefer the second:**

```bash
--win      "title fragment"          # brittle — Electron titles change
--process  chrome                    # robust
--class    Chrome_WidgetWin_1        # most precise
```

## Human entropy

The mouse does not travel from A to B at constant speed. It follows a model of human motor control with four parts:

**Reaction delay.** After deciding to move, the hand does not move immediately — there is a 45–160 ms pause first.

**Multi-phase sub-movements.** This is the important one. People do not move a cursor once; they move, check, correct, check, adjust:

```
ballistic sprint  →  pause  →  correction  →  pause  →  fine adjust
(most of the way)              (small hop)              (last few px)
```

Each phase covers a fixed proportion (~86 %) of the *remaining* distance, so later phases cover far less ground — but their time share does not shrink proportionally. Speed therefore decays on its own. Shrink distance and time together and you get constant velocity, which reads as fake immediately.

**Asymmetric velocity.** Within each phase, acceleration is fast and deceleration is slow — not a symmetric ease.

**Low-frequency tremor.** Physiological hand tremor sits at 8–12 Hz. Regenerate a random value every sample and you get 200 Hz jitter, which looks like a broken mouse rather than a hand. So a new random value is drawn only every 16–26 samples, interpolated in between.

Measured over a 1664 px move:

| Mode | Velocity peaks | Speed profile | Deviation from straight line | Landing error |
|---|---|---|---|---|
| `--no-human` | **2** | symmetric bell — accelerate, cruise, decelerate. The robot signature. | 0.8 px | 0.0 px |
| default | **5** | sprint, dip, correction, dip, fine adjust, long slow settle | 12 px | **0.0 px** |

Total distance travelled was 1672 px against a 1664 px straight line — **0.5 % overhead**. Human-looking, not wandering.

Duration is estimated from distance (`170 + distance × 0.42` ms, clamped to 200–1150 ms). People do not cross a 1400 px screen in one second.

Pass `--no-human` for a true straight line, or `--duration 0` to teleport.

## Getting started

Windows and Python 3.8+. Pillow is needed only for `shot` and `stable`.

```bash
git clone https://github.com/<you>/computer-control.git
cd computer-control
pip install pillow        # optional
python scripts/cc.py screen
```

## Using it as an agent skill

`SKILL.md` is written as a skill descriptor for agent harnesses that support them — WorkBuddy, Claude Code, and similar. Beyond the command reference it documents the coordinate system, the standard workflow, and the safety rules an agent has to follow.

If your harness has no skill system, just call `scripts/cc.py` directly. It is a plain CLI.

## The loop an agent should run

```
1. shot --grid 300 --maxw 1400     -> look, find the target
2. focus --process <app>           -> activate, confirm the title is right
3. --dry-run click ...             -> check the parameters
4. click ...
5. stable --timeout 8              -> wait for the UI to settle
6. shot --out after.png            -> confirm it actually worked
```

**Steps 2 and 6 are the ones people skip, and they are the ones that matter. An agent that clicks without looking is a liability, not an asset.**

## Safety

This thing really does control the computer. Used carelessly it will destroy work. Every rule below was paid for:

- **Confirm the target window before typing.** `type` goes to whatever has focus. After `focus`, always check the title it reports.
- **Prefer `--process` over title matching.** Matching the generic word "Notepad" once sent 27 characters of test text into a user's open `server.log`. Only the fact that the save prompt was answered with "Don't save" prevented damage.
- **Never close a window with `alt+f4`.** It raises a save dialog, and a keystroke still queued behind it can confirm "Save". Terminate processes you started instead.
- **`--dry-run` before anything destructive.**
- **Ask the user before deleting, sending, paying, or submitting a form.**

## Implementation notes

Things that fail *silently* if you get them wrong:

| Technique | Why it matters |
|---|---|
| `SendInput` for everything | Reliable and atomic; `mouse_event` and `keybd_event` are deprecated |
| `INPUT` must be exactly 40 bytes on x64 | Wrong size or field order fails silently — no exception, no input |
| `KEYEVENTF_UNICODE` for text | Virtual key codes cannot express CJK or emoji |
| `SetProcessDpiAwareness(2)` | Without it every coordinate is scaled wrong |
| `AttachThreadInput` before `SetForegroundWindow` | A plain call fails while the foreground lock is held |
| Batched `SendInput` arrays | N keystrokes in one syscall instead of N |
| GDI `GetPixel` for colour reads | Cheaper than grabbing a screenshot for a single pixel |

## License

**0BSD** — the Zero-Clause BSD license. Do whatever you want with this: use it, modify it, sell it, ship it closed-source. There is no attribution requirement and no conditions of any kind. See [LICENSE](LICENSE).
