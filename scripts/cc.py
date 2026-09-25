#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""cc.py — Windows 通用桌面操控：截图、鼠标、键盘、窗口。

纯 ctypes 调 user32，无第三方依赖（截图需 Pillow）。

核心改进（v2）：
  · 窗口可同时按 标题 / 进程名 / 类名 匹配，适配 Electron 类应用（B站、Discord 等标题会变）
  · 支持「窗口相对坐标」——窗口移动后不用重新找坐标
  · 鼠标操作补全：左/右/中键、单击/双击/多击、悬停、按下保持、抬起、相对移动
  · 可直接对某个窗口的客户区截图，放大看细节

用法示例：
  cc.py screen                        屏幕信息
  cc.py shot --out a.png --grid 300   全屏截图带网格
  cc.py shot --win bilibili --out b.png   只截 B 站窗口
  cc.py windows --process chrome      按进程名找窗口
  cc.py info --win bilibili           窗口位置/尺寸/类名
  cc.py focus --process bilibili      激活窗口
  cc.py click --win bilibili --rx 400 --ry 60     窗口内相对坐标点击
  cc.py rclick --x 800 --y 400        右键单击
  cc.py dclick --x 800 --y 400        左键双击
  cc.py hover --x 800 --y 400         悬停不点击
  cc.py down / up                     按住 / 松开（配合 move 做拖拽）
  cc.py move --rel 100 -50            相对当前位置移动
  cc.py type "搜索内容"                输入文本
  cc.py hotkey ctrl a                 组合键

所有动作命令支持 --dry-run。
"""
import argparse
import ctypes
import math
import os
import random
import sys
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")

u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        u32.SetProcessDPIAware()
    except Exception:
        pass

# ---------------- SendInput ----------------
ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


u32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
u32.SendInput.restype = wintypes.UINT


def _send(*items):
    arr = (INPUT * len(items))(*items)
    sent = u32.SendInput(len(items), arr, ctypes.sizeof(INPUT))
    if sent != len(items):
        raise ctypes.WinError(ctypes.get_last_error())


def _mouse(flags, dx=0, dy=0, data=0):
    return INPUT(type=INPUT_MOUSE, u=_U(mi=MOUSEINPUT(dx, dy, data, flags, 0, None)))


def _key(vk=0, scan=0, flags=0):
    return INPUT(type=INPUT_KEYBOARD, u=_U(ki=KEYBDINPUT(vk, scan, flags, 0, None)))


BTN = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

VK = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
    "shift": 0x10, "ctrl": 0x11, "control": 0x11, "alt": 0x12,
    "pause": 0x13, "capslock": 0x14, "esc": 0x1B, "escape": 0x1B,
    "space": 0x20, "pageup": 0x21, "pgup": 0x21, "pagedown": 0x22, "pgdn": 0x22,
    "end": 0x23, "home": 0x24, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "insert": 0x2D, "delete": 0x2E, "del": 0x2E,
    "win": 0x5B, "lwin": 0x5B, "rwin": 0x5C,
    "numlock": 0x90, "scrolllock": 0x91, "printscreen": 0x2C,
    ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF,
    "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
}
for _i in range(1, 25):
    VK["f%d" % _i] = 0x6F + _i
for _c in "abcdefghijklmnopqrstuvwxyz":
    VK[_c] = ord(_c.upper())
for _d in "0123456789":
    VK[_d] = ord(_d)


def vk_of(name):
    k = name.strip().lower()
    if k in VK:
        return VK[k]
    if len(k) == 1:
        return ord(k.upper())
    raise SystemExit("未知按键: %s" % name)


# ---------------- 屏幕 / 鼠标 ----------------
def screen_info():
    return dict(width=u32.GetSystemMetrics(0), height=u32.GetSystemMetrics(1),
                vw=u32.GetSystemMetrics(78), vh=u32.GetSystemMetrics(79),
                monitors=u32.GetSystemMetrics(80))


def cursor_pos():
    p = POINT()
    u32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


_RNG = random.Random()


def _ease(t):
    """对称缓动，只在 --no-human 模式下用。"""
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2.0


def _tremor_series(n, rng, amp=1.0, knot_span=20):
    """生成低频相关噪声，模拟生理性手抖。

    关键：真人生理性手抖是 8~12Hz，不是逐步白噪声。
    如果每个采样点都换一个新随机值，抖动频率会到 200Hz——
    看起来像鼠标坏了，不像人手。
    所以这里每 knot_span 个采样点才取一个新随机值，中间线性插值。
    """
    knots = [rng.gauss(0, amp)]
    need = n // knot_span + 3
    while len(knots) < need:
        knots.append(knots[-1] * 0.58 + rng.gauss(0, amp * 0.85))
    out = []
    for i in range(n):
        t = i / float(knot_span)
        k = int(t)
        f = t - k
        if k + 1 >= len(knots):
            out.append(knots[-1])
        else:
            out.append(knots[k] * (1.0 - f) + knots[k + 1] * f)
    return out


def _asym_ease(t):
    """非对称速度曲线：加速快、减速慢，接近真人肢体运动。"""
    if t < 0.5:
        return pow(t * 2.0, 0.62) / 2.0
    return 1.0 - pow((1.0 - t) * 2.0, 1.55) / 2.0


def _submove(x0, y0, x1, y1, rng, bow_scale=0.06, bow_max=22.0):
    """一段子运动的采样点：二次贝塞尔 + 非对称速度曲线。"""
    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy)
    if dist < 0.6:
        return [(x1, y1)]
    ang = math.atan2(dy, dx)
    perp = ang + math.pi / 2.0
    bow = rng.gauss(0, min(dist * bow_scale, bow_max))
    cx = (x0 + x1) / 2.0 + math.cos(perp) * bow
    cy = (y0 + y1) / 2.0 + math.sin(perp) * bow
    n = max(3, min(56, int(dist / 7.0) + 3))
    pts = []
    for i in range(1, n + 1):
        e = _asym_ease(i / float(n))
        u = 1.0 - e
        pts.append((u * u * x0 + 2 * u * e * cx + e * e * x1,
                    u * u * y0 + 2 * u * e * cy + e * e * y1))
    return pts


def auto_duration(dist):
    """按距离估算真人移动耗时。真人搬鼠标不是匀速的。"""
    ms = 170.0 + dist * 0.42
    return max(200.0, min(1150.0, ms))


def move_to(x, y, duration_ms=-1, human=True):
    """移动鼠标。

    human=True 时按真人运动模型走，包含四个特征：
      1. 反应延迟  —— 决定移动之后，手不会立刻动
      2. 多段子运动 —— 粗定位 → 修正 → 微调，每段幅度递减
      3. 非对称速度 —— 加速快、减速慢，不是对称缓动
      4. 相关手抖   —— 平滑随机游走，不是白噪声
    最后落点会精确修正到目标，保证点击不偏。
    """
    x, y = int(x), int(y)
    if duration_ms == 0:
        u32.SetCursorPos(x, y)
        return

    x0, y0 = cursor_pos()
    dist = math.hypot(x - x0, y - y0)
    if dist < 2:
        u32.SetCursorPos(x, y)
        return

    if duration_ms is None or duration_ms < 0:
        duration_ms = auto_duration(dist)

    if not human:
        steps = max(10, min(80, int(dist / 8) + 10))
        for i in range(1, steps + 1):
            t = _ease(i / float(steps))
            u32.SetCursorPos(int(x0 + (x - x0) * t), int(y0 + (y - y0) * t))
            time.sleep(duration_ms / 1000.0 / steps)
        u32.SetCursorPos(x, y)
        return

    rng = _RNG
    total_s = duration_ms / 1000.0

    # 1) 反应延迟：决定移动之后手不会立刻动
    time.sleep(rng.uniform(0.045, 0.16))

    # 2) 子运动计划：每段覆盖"剩余距离"的固定比例。
    #    关键是后段距离越来越小、但时间占比不按比例缩，
    #    速度就自然降下来了——这才是真人"减速逼近"的手感。
    #    如果距离和时间一起缩，全程匀速，一眼假。
    if dist > 620:
        plan = [0.86, 0.86, 0.86, 1.0]
        shares = [0.50, 0.27, 0.15, 0.08]
    elif dist > 210:
        plan = [0.87, 0.87, 1.0]
        shares = [0.60, 0.26, 0.14]
    else:
        plan = [0.88, 1.0]
        shares = [0.72, 0.28]
    # 每个比例加随机扰动，避免每次轨迹长得一模一样
    plan = [1.0 if p >= 1.0 else min(0.97, max(0.60, p * rng.uniform(0.94, 1.06)))
            for p in plan]

    tremor = _tremor_series(700, rng, amp=0.55 + min(dist / 1400.0, 1.0),
                            knot_span=rng.randint(16, 26))
    ti = 0
    cur = (float(x0), float(y0))

    for k, frac in enumerate(plan):
        tx = cur[0] + (x - cur[0]) * frac
        ty = cur[1] + (y - cur[1]) * frac
        pts = _submove(cur[0], cur[1], tx, ty, rng,
                       bow_scale=0.075 if k == 0 else 0.05,
                       bow_max=26.0 if k == 0 else 12.0)
        seg_s = total_s * shares[k]
        per = seg_s / len(pts)
        for (px, py) in pts:
            t = tremor[ti % len(tremor)]
            ti += 1
            u32.SetCursorPos(int(round(px + t)), int(round(py + t * 0.62)))
            time.sleep(max(0.0006, per * (1.0 + rng.gauss(0, 0.13))))
        cur = (tx, ty)
        # 段与段之间短暂停顿：真人修正前会"看一下"
        if k < len(plan) - 1:
            time.sleep(rng.uniform(0.022, 0.070))

    # 3) 落点微调：最后 1~3 次极小幅修正，而不是"啪"地吸附
    for i in range(rng.randint(1, 3)):
        jx = _RNG.gauss(0, 0.9)
        jy = _RNG.gauss(0, 0.9)
        u32.SetCursorPos(int(round(x + jx)), int(round(y + jy)))
        time.sleep(rng.uniform(0.012, 0.034))
    u32.SetCursorPos(x, y)


def move_rel(dx, dy, duration_ms=-1, human=True):
    x, y = cursor_pos()
    move_to(x + dx, y + dy, duration_ms, human)


def mouse_down(button="left"):
    _send(_mouse(BTN[button][0]))


def mouse_up(button="left"):
    _send(_mouse(BTN[button][1]))


def click(button="left", x=None, y=None, count=1, interval_ms=110, move_ms=420,
          human=True):
    if x is not None and y is not None:
        move_to(x, y, move_ms, human)
        time.sleep(0.16 + _RNG.uniform(0, 0.09))
    down, up = BTN[button]
    for i in range(count):
        _send(_mouse(down))
        time.sleep(0.028 + _RNG.uniform(0, 0.022))   # 按下时长也带抖动
        _send(_mouse(up))
        if i < count - 1:
            time.sleep(interval_ms / 1000.0 * (1 + _RNG.gauss(0, 0.12)))


def drag(x1, y1, x2, y2, button="left", duration_ms=650, move_ms=420, human=True):
    move_to(x1, y1, move_ms, human)
    time.sleep(0.20 + _RNG.uniform(0, 0.08))
    mouse_down(button)
    time.sleep(0.12 + _RNG.uniform(0, 0.06))
    move_to(x2, y2, duration_ms, human)
    time.sleep(0.15 + _RNG.uniform(0, 0.07))
    mouse_up(button)


def scroll(amount, x=None, y=None, move_ms=420, human=True):
    if x is not None and y is not None:
        move_to(x, y, move_ms, human)
        time.sleep(0.10)
    _send(_mouse(MOUSEEVENTF_WHEEL, data=(int(amount) * 120) & 0xFFFFFFFF))


def type_via_clipboard(text, restore=True, settle=0.22):
    """走剪贴板粘贴，而不是逐字符模拟按键。

    为什么需要这个：SendInput 批量提交对浏览器/Electron 应用太快，
    会**静默丢字符**（实测 132 字符丢了 2 个）。剪贴板是原子的，
    无论多长都不会丢。

    代价：会覆盖用户当前剪贴板，所以默认用完恢复。
    """
    saved = None
    if restore:
        try:
            saved = clip_get()
        except Exception:
            saved = None
    clip_set(text)
    time.sleep(0.12)
    hotkey(["ctrl", "v"])
    time.sleep(settle)
    if restore and saved is not None:
        try:
            clip_set(saved)
        except Exception:
            pass


def type_text(text, interval_ms=1, chunk=30):
    events = []
    for ch in text:
        c = ord(ch)
        if c > 0xFFFF:
            c -= 0x10000
            for s in (0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF)):
                events.append(_key(scan=s, flags=KEYEVENTF_UNICODE))
                events.append(_key(scan=s, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        else:
            events.append(_key(scan=c, flags=KEYEVENTF_UNICODE))
            events.append(_key(scan=c, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    per = chunk * 2
    for i in range(0, len(events), per):
        batch = events[i:i + per]
        arr = (INPUT * len(batch))(*batch)
        sent = u32.SendInput(len(batch), arr, ctypes.sizeof(INPUT))
        if sent != len(batch):
            raise ctypes.WinError(ctypes.get_last_error())
        if interval_ms > 0:
            time.sleep(interval_ms / 1000.0)


def press_key(name, times=1):
    v = vk_of(name)
    for _ in range(times):
        _send(_key(vk=v), _key(vk=v, flags=KEYEVENTF_KEYUP))
        time.sleep(0.05)


def hotkey(keys):
    vs = [vk_of(k) for k in keys]
    for v in vs:
        _send(_key(vk=v))
        time.sleep(0.02)
    for v in reversed(vs):
        _send(_key(vk=v, flags=KEYEVENTF_KEYUP))
        time.sleep(0.02)


# ---------------- 窗口 ----------------
def proc_name(pid):
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(600)
        size = ctypes.c_ulong(600)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
    finally:
        k32.CloseHandle(h)
    return ""


def win_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def win_title(hwnd):
    n = u32.GetWindowTextLengthW(hwnd)
    if n == 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def list_windows(title_f=None, proc_f=None, class_f=None, include_hidden=False):
    out = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if not include_hidden and not u32.IsWindowVisible(hwnd):
            return True
        t = win_title(hwnd)
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pn = proc_name(pid.value)
        cn = win_class(hwnd)
        if not t and not pn:
            return True
        if title_f and title_f.lower() not in t.lower():
            return True
        if proc_f and proc_f.lower() not in pn.lower():
            return True
        if class_f and class_f.lower() not in cn.lower():
            return True
        out.append(dict(hwnd=int(hwnd), title=t, pid=pid.value, proc=pn, cls=cn))
        return True

    u32.EnumWindows(EnumProc(cb), 0)
    return out


def force_foreground(hwnd):
    """比裸 SetForegroundWindow 可靠：绕过前台窗口锁定。"""
    fg = u32.GetForegroundWindow()
    tid_fg = u32.GetWindowThreadProcessId(fg, None) if fg else 0
    tid_me = k32.GetCurrentThreadId()
    attached = False
    if tid_fg and tid_fg != tid_me:
        attached = bool(u32.AttachThreadInput(tid_me, tid_fg, True))
    try:
        if u32.IsIconic(hwnd):
            u32.ShowWindow(hwnd, 9)      # SW_RESTORE
        u32.BringWindowToTop(hwnd)
        u32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            u32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.35)


def find_window(title=None, proc=None, cls=None):
    ws = list_windows(title, proc, cls)
    return ws[0] if ws else None


def window_rect(hwnd):
    r = RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def client_rect(hwnd):
    """返回客户区在屏幕坐标系下的 (x, y, w, h)。"""
    r = RECT()
    u32.GetClientRect(hwnd, ctypes.byref(r))
    pt = POINT(0, 0)
    u32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, r.right - r.left, r.bottom - r.top


# ---------------- 剪贴板 ----------------
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

k32.GlobalAlloc.restype = wintypes.HGLOBAL
k32.GlobalLock.restype = ctypes.c_void_p
k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
u32.GetClipboardData.restype = wintypes.HANDLE
u32.GetClipboardData.argtypes = [wintypes.UINT]
u32.SetClipboardData.restype = wintypes.HANDLE
u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]


def clip_get():
    for _ in range(12):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.08)
    else:
        raise SystemExit("打开剪贴板失败（可能被其他程序占用）")
    try:
        h = u32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = k32.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.wstring_at(p)
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()


def clip_set(text):
    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)
    h = k32.GlobalAlloc(GMEM_MOVEABLE, size)
    if not h:
        raise SystemExit("分配剪贴板内存失败")
    p = k32.GlobalLock(h)
    if not p:
        raise SystemExit("锁定剪贴板内存失败")
    ctypes.memmove(p, data, size)
    k32.GlobalUnlock(h)
    for _ in range(12):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.08)
    else:
        raise SystemExit("打开剪贴板失败")
    try:
        u32.EmptyClipboard()
        if not u32.SetClipboardData(CF_UNICODETEXT, h):
            raise SystemExit("写入剪贴板失败")
        return len(text)
    finally:
        u32.CloseClipboard()


# ---------------- 等待 / 像素 / 显示器 ----------------
def wait_window(title=None, proc=None, cls=None, timeout=15.0, interval=0.4):
    t0 = time.time()
    while time.time() - t0 < timeout:
        w = find_window(title, proc, cls)
        if w:
            return w, time.time() - t0
        time.sleep(interval)
    return None, time.time() - t0


def wait_stable(region=None, timeout=15.0, interval=0.35, tolerance=1.6):
    """等屏幕某区域不再变化。用于等页面/界面加载完。"""
    try:
        from PIL import ImageChops, ImageGrab
    except ImportError:
        raise SystemExit("需要 Pillow：pip install pillow")
    prev = None
    t0 = time.time()
    while time.time() - t0 < timeout:
        cur = ImageGrab.grab(bbox=region, all_screens=True).convert("L")
        if prev is not None and prev.size == cur.size:
            diff = ImageChops.difference(prev, cur)
            hist = diff.histogram()          # 不依赖 getdata，避免 Pillow 弃用告警
            total = float(sum(hist))
            avg = (sum(i * c for i, c in enumerate(hist)) / total) if total else 0.0
            if avg <= tolerance:
                return True, time.time() - t0
        prev = cur
        time.sleep(interval)
    return False, time.time() - t0


def pixel_at(x, y):
    hdc = u32.GetDC(0)
    if not hdc:
        return None
    try:
        v = ctypes.windll.gdi32.GetPixel(hdc, int(x), int(y))
        if v == 0xFFFFFFFF:
            return None
        return (v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF)
    finally:
        u32.ReleaseDC(0, hdc)


def list_monitors():
    out = []
    Proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                              ctypes.POINTER(RECT), wintypes.LPARAM)

    def cb(hmon, hdc, lprc, _):
        r = lprc.contents
        out.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    u32.EnumDisplayMonitors(0, None, Proc(cb), 0)
    return out


SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE = 6, 3, 9
WM_CLOSE = 0x0010


def set_window_state(hwnd, action):
    if action == "min":
        u32.ShowWindow(hwnd, SW_MINIMIZE)
    elif action == "max":
        u32.ShowWindow(hwnd, SW_MAXIMIZE)
    elif action == "restore":
        u32.ShowWindow(hwnd, SW_RESTORE)
    elif action == "close":
        u32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    elif action == "top":
        force_foreground(hwnd)
    else:
        raise SystemExit("未知动作: %s" % action)


# ---------------- 截图 ----------------
def screenshot(path, region=None, grid=0, maxw=0, scale=1.0):
    try:
        from PIL import Image, ImageDraw, ImageGrab
    except ImportError:
        raise SystemExit("需要 Pillow 才能截图：pip install pillow")
    img = ImageGrab.grab(bbox=region, all_screens=True)
    if grid and grid > 0:
        d = ImageDraw.Draw(img)
        w, h = img.size
        for x in range(0, w, grid):
            d.line([(x, 0), (x, h)], fill=(255, 70, 70), width=2)
            d.text((x + 5, 8), str(x), fill=(255, 90, 90))
            d.text((x + 5, h - 26), str(x), fill=(255, 90, 90))
        for y in range(0, h, grid):
            d.line([(0, y), (w, y)], fill=(255, 70, 70), width=2)
            d.text((8, y + 5), str(y), fill=(255, 90, 90))
            d.text((w - 78, y + 5), str(y), fill=(255, 90, 90))
    if maxw and img.size[0] > maxw:
        r = maxw / float(img.size[0])
        img = img.resize((int(img.size[0] * r), int(img.size[1] * r)), Image.LANCZOS)
    elif scale and scale != 1.0:
        img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), Image.LANCZOS)
    dd = os.path.dirname(os.path.abspath(path))
    if dd:
        os.makedirs(dd, exist_ok=True)
    img.save(path)
    return img.size


# ---------------- CLI ----------------
def add_win_args(p, required=False):
    g = p.add_argument_group("窗口定位（三选一，也可组合）")
    g.add_argument("--win", help="窗口标题片段")
    g.add_argument("--process", help="进程名片段，如 chrome / bilibili")
    g.add_argument("--class", dest="cls", help="窗口类名片段")


def main():
    ap = argparse.ArgumentParser(description="Windows 通用桌面操控")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-human", action="store_true",
                    help="关闭真人熵：鼠标走直线、不加抖动与过冲")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("screen")
    sub.add_parser("cursor")
    sub.add_parser("active")

    p = sub.add_parser("windows", help="列出窗口")
    add_win_args(p)
    p.add_argument("--all", action="store_true", help="包含隐藏窗口")

    p = sub.add_parser("info", help="窗口位置尺寸")
    add_win_args(p)

    p = sub.add_parser("shot", help="截图")
    p.add_argument("--out", default=os.path.join(os.environ.get("TEMP", "."), "cc_shot.png"))
    p.add_argument("--region", help="x,y,w,h")
    add_win_args(p)
    p.add_argument("--grid", type=int, default=0)
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--maxw", type=int, default=0)

    p = sub.add_parser("focus", help="激活窗口")
    add_win_args(p)

    p = sub.add_parser("move", help="移动鼠标")
    p.add_argument("x", type=int, nargs="?")
    p.add_argument("y", type=int, nargs="?")
    p.add_argument("--rel", nargs=2, type=int, metavar=("DX", "DY"))
    p.add_argument("--duration", type=int, default=-1, help="移动耗时ms，-1=按距离自动，0=瞬移")

    p = sub.add_parser("hover", help="移到目标悬停，不点击")
    p.add_argument("--x", type=int, required=True)
    p.add_argument("--y", type=int, required=True)
    p.add_argument("--duration", type=int, default=-1, help="移动耗时ms，-1=按距离自动，0=瞬移")
    p.add_argument("--hold", type=float, default=0.3, help="悬停保持秒数")

    for name in ("click", "rclick", "dclick", "mclick"):
        p = sub.add_parser(name, help={"click": "单击(默认左键)", "rclick": "右键单击",
                                       "dclick": "左键双击", "mclick": "中键单击"}[name])
        p.add_argument("--x", type=int)
        p.add_argument("--y", type=int)
        p.add_argument("--count", type=int)
        p.add_argument("--move", type=int, default=-1, help="移向目标耗时ms，-1=自动")
        add_win_args(p)
        p.add_argument("--rx", type=int, help="窗口内相对 X（相对客户区左上角）")
        p.add_argument("--ry", type=int, help="窗口内相对 Y")
        p.add_argument("--center", action="store_true", help="点击窗口客户区中心")

    p = sub.add_parser("drag", help="拖拽")
    p.add_argument("x1", type=int)
    p.add_argument("y1", type=int)
    p.add_argument("x2", type=int)
    p.add_argument("y2", type=int)
    p.add_argument("--button", default="left", choices=list(BTN))
    p.add_argument("--duration", type=int, default=-1, help="拖动耗时ms，-1=自动")
    p.add_argument("--move", type=int, default=-1, help="移向目标耗时ms，-1=自动")

    p = sub.add_parser("down", help="按住鼠标键不放")
    p.add_argument("--button", default="left", choices=list(BTN))
    p = sub.add_parser("up", help="松开鼠标键")
    p.add_argument("--button", default="left", choices=list(BTN))

    p = sub.add_parser("scroll", help="滚轮")
    p.add_argument("amount", type=int)
    p.add_argument("--x", type=int)
    p.add_argument("--y", type=int)
    p.add_argument("--move", type=int, default=-1, help="移向目标耗时ms，-1=自动")

    p = sub.add_parser("type", help="输入文本")
    p.add_argument("text")
    p.add_argument("--interval", type=int, default=1)
    p.add_argument("--chunk", type=int, default=30)
    p.add_argument("--paste", action="store_true",
                   help="走剪贴板粘贴。文本较长或目标应用会丢字符时用这个")
    p.add_argument("--no-restore", action="store_true",
                   help="配合 --paste：不恢复原剪贴板内容")
    p.add_argument("--require", metavar="PROCESS",
                   help="硬闸：前台进程名必须匹配才允许输入，否则拒绝执行。"
                        "强烈建议始终加上，防止文字打进错误的窗口")

    p = sub.add_parser("key", help="按单键")
    p.add_argument("name")
    p.add_argument("--times", type=int, default=1)

    p = sub.add_parser("hotkey", help="组合键")
    p.add_argument("keys", nargs="+")

    p = sub.add_parser("clip", help="读/写剪贴板")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--get", action="store_true", help="读取剪贴板文本")
    g.add_argument("--set", metavar="TEXT", help="写入剪贴板文本")

    p = sub.add_parser("waitwin", help="等待窗口出现")
    add_win_args(p)
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--interval", type=float, default=0.4)

    p = sub.add_parser("stable", help="等屏幕停止变化（等加载完成）")
    p.add_argument("--region", help="x,y,w,h，默认全屏")
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--interval", type=float, default=0.35)
    p.add_argument("--tolerance", type=float, default=1.6)

    p = sub.add_parser("pixel", help="读取某点像素颜色")
    p.add_argument("--x", type=int, required=True)
    p.add_argument("--y", type=int, required=True)

    sub.add_parser("monitors", help="列出所有显示器")

    p = sub.add_parser("winstate", help="窗口最小化/最大化/还原/关闭")
    add_win_args(p)
    p.add_argument("--action", required=True,
                   choices=["min", "max", "restore", "close", "top"])

    a = ap.parse_args()
    dry = a.dry_run
    hm = not a.no_human

    def resolve_win():
        if not (getattr(a, "win", None) or getattr(a, "process", None)
                or getattr(a, "cls", None)):
            return None
        w = find_window(getattr(a, "win", None), getattr(a, "process", None),
                        getattr(a, "cls", None))
        if not w:
            raise SystemExit("未找到匹配窗口：win=%s process=%s class=%s"
                             % (getattr(a, "win", None), getattr(a, "process", None),
                                getattr(a, "cls", None)))
        return w

    if a.cmd == "screen":
        s = screen_info()
        print("分辨率 %dx%d | 虚拟桌面 %dx%d | 显示器 %d 个"
              % (s["width"], s["height"], s["vw"], s["vh"], s["monitors"]))
        print("坐标范围: x 0~%d, y 0~%d" % (s["width"] - 1, s["height"] - 1))

    elif a.cmd == "cursor":
        print("%d %d" % cursor_pos())

    elif a.cmd == "active":
        h = u32.GetForegroundWindow()
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        print("HWND %s | %s | %s" % (h, proc_name(pid.value), win_title(h) or "(无标题)"))

    elif a.cmd == "windows":
        ws = list_windows(a.win, a.process, a.cls, a.all)
        if not ws:
            print("(无匹配窗口)")
        for w in ws:
            print("%-9d %-22s pid=%-6d %s"
                  % (w["hwnd"], w["proc"][:22], w["pid"], w["title"][:70]))

    elif a.cmd == "info":
        w = resolve_win()
        if not w:
            raise SystemExit("info 需要 --win / --process / --class")
        x, y, ww, hh = window_rect(w["hwnd"])
        cx, cy, cw, ch = client_rect(w["hwnd"])
        print("标题   : %s" % (w["title"] or "(无)"))
        print("进程   : %s (pid %d)" % (w["proc"], w["pid"]))
        print("类名   : %s" % w["cls"])
        print("窗口框 : x=%d y=%d w=%d h=%d" % (x, y, ww, hh))
        print("客户区 : x=%d y=%d w=%d h=%d" % (cx, cy, cw, ch))
        print("最小化 : %s | 可见: %s" % (bool(u32.IsIconic(w["hwnd"])),
                                          bool(u32.IsWindowVisible(w["hwnd"]))))

    elif a.cmd == "shot":
        if dry:
            print("[dry-run] 截图 →", a.out)
            return
        region = None
        if a.region:
            # --region 收的是 x,y,w,h；PIL 的 bbox 要的是 left,top,right,bottom
            rx, ry, rw, rh = (int(v) for v in a.region.split(","))
            region = (rx, ry, rx + rw, ry + rh)
        else:
            w = resolve_win()
            if w:
                cx, cy, cw, ch = client_rect(w["hwnd"])
                region = (cx, cy, cx + cw, cy + ch)
                print("截取窗口客户区: %s" % (w["title"] or w["proc"]))
        sz = screenshot(a.out, region, a.grid, a.maxw, a.scale)
        print("已保存 %s (%dx%d)" % (a.out, sz[0], sz[1]))

    elif a.cmd == "focus":
        w = resolve_win()
        if not w:
            raise SystemExit("focus 需要 --win / --process / --class")
        if dry:
            print("[dry-run] 激活 HWND %d | %s" % (w["hwnd"], w["title"]))
            return
        force_foreground(w["hwnd"])
        now = u32.GetForegroundWindow()
        ok = (now == w["hwnd"])
        print("已激活 HWND %d | %s" % (w["hwnd"], w["title"] or "(无标题)"))
        print("前台校验: %s" % ("✓ 就是它" if ok else "✗ 前台是别的窗口 HWND %d" % now))

    elif a.cmd == "move":
        if a.rel:
            dx, dy = a.rel
            if dry:
                print("[dry-run] 相对移动 %d,%d" % (dx, dy))
                return
            move_rel(dx, dy, a.duration, hm)
        else:
            if a.x is None or a.y is None:
                raise SystemExit("move 需要 X Y 或 --rel DX DY")
            if dry:
                print("[dry-run] 移动到 %d,%d" % (a.x, a.y))
                return
            move_to(a.x, a.y, a.duration, hm)
        print("鼠标位置", cursor_pos())

    elif a.cmd == "hover":
        if dry:
            print("[dry-run] 悬停 %d,%d" % (a.x, a.y))
            return
        move_to(a.x, a.y, a.duration, hm)
        time.sleep(a.hold)
        print("已悬停于", cursor_pos())

    elif a.cmd in ("click", "rclick", "dclick", "mclick"):
        button = {"click": "left", "rclick": "right",
                  "dclick": "left", "mclick": "middle"}[a.cmd]
        count = a.count if a.count else (2 if a.cmd == "dclick" else 1)

        tx, ty = a.x, a.y
        if (a.rx is not None or a.ry is not None or a.center):
            w = resolve_win()
            if not w:
                raise SystemExit("用 --rx/--ry/--center 时必须给 --win / --process / --class")
            cx, cy, cw, ch = client_rect(w["hwnd"])
            if a.center:
                tx, ty = cx + cw // 2, cy + ch // 2
            else:
                tx, ty = cx + (a.rx or 0), cy + (a.ry or 0)
            print("窗口「%s」客户区原点 (%d,%d) → 目标 (%d,%d)"
                  % (w["title"] or w["proc"], cx, cy, tx, ty))

        if tx is None or ty is None:
            raise SystemExit("需要 --x/--y，或用 --win + --rx/--ry/--center")
        if dry:
            print("[dry-run] %s 键点击 %d 次 @ (%d,%d)" % (button, count, tx, ty))
            return
        click(button, tx, ty, count, move_ms=a.move, human=hm)
        print("已%s @ (%d,%d)" % ({"click": "单击", "rclick": "右键单击",
                                    "dclick": "双击", "mclick": "中键单击"}[a.cmd], tx, ty))

    elif a.cmd == "drag":
        if dry:
            print("[dry-run] 拖拽 (%d,%d)→(%d,%d)" % (a.x1, a.y1, a.x2, a.y2))
            return
        drag(a.x1, a.y1, a.x2, a.y2, a.button, a.duration, a.move, hm)
        print("已拖拽 (%d,%d)→(%d,%d)" % (a.x1, a.y1, a.x2, a.y2))

    elif a.cmd == "down":
        if dry:
            print("[dry-run] 按住", a.button)
            return
        mouse_down(a.button)
        print("已按住", a.button)

    elif a.cmd == "up":
        if dry:
            print("[dry-run] 松开", a.button)
            return
        mouse_up(a.button)
        print("已松开", a.button)

    elif a.cmd == "scroll":
        if dry:
            print("[dry-run] 滚轮", a.amount)
            return
        scroll(a.amount, a.x, a.y, a.move, hm)
        print("已滚动", a.amount)

    elif a.cmd == "type":
        if dry:
            print("[dry-run] 输入 %d 字符: %s" % (len(a.text), a.text[:60]))
            return
        h = u32.GetForegroundWindow()
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        pname = proc_name(pid.value)
        wtitle = win_title(h)
        if a.require:
            if a.require.lower() not in pname.lower():
                print("✗ 前台进程是「%s」，与 --require「%s」不符，拒绝输入。"
                      % (pname, a.require))
                print("  当前窗口标题: %s" % (wtitle or "(无标题)"))
                sys.exit(5)
            print("前台校验通过: %s ✓" % pname)
        print("目标窗口: %s | %s" % (pname, wtitle or "(无标题)"))
        t0 = time.time()
        if a.paste:
            type_via_clipboard(a.text, restore=not a.no_restore)
            print("已粘贴 %d 字符（走剪贴板），耗时 %.3fs" % (len(a.text), time.time() - t0))
        else:
            type_text(a.text, a.interval, a.chunk)
            print("已输入 %d 字符，耗时 %.3fs" % (len(a.text), time.time() - t0))

    elif a.cmd == "key":
        if dry:
            print("[dry-run] 按键 %s x%d" % (a.name, a.times))
            return
        press_key(a.name, a.times)
        print("已按键 %s x%d" % (a.name, a.times))

    elif a.cmd == "hotkey":
        if dry:
            print("[dry-run] 组合键 %s" % "+".join(a.keys))
            return
        hotkey(a.keys)
        print("已按 %s" % "+".join(a.keys))

    elif a.cmd == "clip":
        if a.get:
            t = clip_get()
            print(t)
        else:
            if dry:
                print("[dry-run] 写入剪贴板 %d 字符" % len(a.set))
                return
            n = clip_set(a.set)
            print("已写入剪贴板 %d 字符" % n)

    elif a.cmd == "waitwin":
        if not (a.win or a.process or a.cls):
            raise SystemExit("waitwin 需要 --win / --process / --class")
        if dry:
            print("[dry-run] 等待窗口出现")
            return
        w, el = wait_window(a.win, a.process, a.cls, a.timeout, a.interval)
        if w:
            print("已出现（%.1fs）HWND %d | %s | %s"
                  % (el, w["hwnd"], w["proc"], w["title"] or "(无标题)"))
        else:
            print("超时 %.1fs，窗口未出现" % a.timeout)
            sys.exit(3)

    elif a.cmd == "stable":
        if dry:
            print("[dry-run] 等待屏幕稳定")
            return
        region = tuple(int(v) for v in a.region.split(",")) if a.region else None
        ok, el = wait_stable(region, a.timeout, a.interval, a.tolerance)
        print("%s（耗时 %.1fs）" % ("屏幕已稳定" if ok else "超时仍未稳定", el))
        if not ok:
            sys.exit(3)

    elif a.cmd == "pixel":
        c = pixel_at(a.x, a.y)
        if c is None:
            print("读取失败")
            sys.exit(4)
        print("(%d,%d) → RGB(%d,%d,%d) #%02X%02X%02X" % (a.x, a.y, c[0], c[1], c[2], c[0], c[1], c[2]))

    elif a.cmd == "monitors":
        ms = list_monitors()
        print("共 %d 个显示器" % len(ms))
        for i, (x, y, w, h) in enumerate(ms):
            print("  #%d  x=%d y=%d w=%d h=%d" % (i + 1, x, y, w, h))

    elif a.cmd == "winstate":
        w = resolve_win()
        if not w:
            raise SystemExit("winstate 需要 --win / --process / --class")
        if dry:
            print("[dry-run] 对 HWND %d 执行 %s" % (w["hwnd"], a.action))
            return
        set_window_state(w["hwnd"], a.action)
        time.sleep(0.4)
        print("已对「%s」执行 %s" % (w["title"] or w["proc"], a.action))


if __name__ == "__main__":
    main()
