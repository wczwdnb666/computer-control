---
name: "computer-control"
description: "操控 Windows 桌面：截图看屏幕、移动鼠标（带真人轨迹抖动）、左/右/中键点击、双击、拖拽、悬停、输入中英文、组合键、剪贴板读写、窗口枚举与激活、等待界面加载。纯 ctypes 调 user32，无需安装任何依赖。适合操作没有 API 的图形界面程序——填表单、点按钮、在应用间搬运数据、自动化重复的桌面操作。"
version: "2.0.0"
triggers:
  - "鼠标"
  - "键盘"
  - "点击"
  - "右键"
  - "截图看屏幕"
  - "操控桌面"
  - "GUI 自动化"
  - "computer use"
  - "computer-control"
---

# Computer Control — Windows 桌面操控

让 AI 能看见屏幕、并像人一样操作鼠标键盘。

## 运行方式

```
$PY = C:\Users\到达胜利之前 无法回头\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe
$CC = C:\Users\到达胜利之前 无法回头\.workbuddy-ai\skills\computer-control\scripts\cc.py

$PY $CC <命令> [参数]
```

**不要用裸 `python`**，环境里的 `python` 不一定指向托管解释器。

## 命令总览（26 个）

### 观察
| 命令 | 说明 |
|---|---|
| `screen` | 屏幕分辨率与坐标范围 |
| `monitors` | 列出所有显示器及其边界 |
| `cursor` | 当前鼠标坐标 |
| `active` | 当前前台窗口（进程名 + 标题） |
| `windows [--win X] [--process X] [--class X] [--all]` | 列出窗口 |
| `info --win/--process/--class X` | 窗口位置、客户区、类名、状态 |
| `shot --out P [--win X] [--region x,y,w,h] [--grid N] [--maxw N]` | 截图 |
| `pixel --x X --y Y` | 读某点颜色（RGB + HEX） |

### 鼠标
| 命令 | 说明 |
|---|---|
| `move X Y` / `move --rel DX DY` | 移动（默认带真人轨迹） |
| `hover --x X --y Y [--hold S]` | 移到目标悬停不点击 |
| `click --x X --y Y` | 左键单击 |
| `rclick --x X --y Y` | **右键单击** |
| `dclick --x X --y Y` | **左键双击** |
| `mclick --x X --y Y` | 中键单击 |
| `drag X1 Y1 X2 Y2` | 拖拽 |
| `down` / `up` | 按住 / 松开（配合 move 做长按拖动） |
| `scroll N [--x X --y Y]` | 滚轮，正数向上 |

**所有点击类命令都支持窗口相对坐标**（窗口移动后不用重新找）：

```
click --win bilibili --rx 400 --ry 60      # 窗口客户区左上角 + (400,60)
click --process chrome --center            # 点窗口客户区正中心
```

### 键盘
| 命令 | 说明 |
|---|---|
| `type "文本"` | 输入文本，支持中文（走 KEYEVENTF_UNICODE） |
| `key enter [--times N]` | 按单键 |
| `hotkey ctrl shift s` | 组合键 |

### 剪贴板与等待
| 命令 | 说明 |
|---|---|
| `clip --get` / `clip --set "文本"` | 读/写剪贴板 |
| `waitwin --process X --timeout 15` | 等窗口出现，超时退出码 3 |
| `stable [--region x,y,w,h] [--timeout 15]` | 等屏幕停止变化（等加载完成），超时退出码 3 |
| `winstate --win X --action min\|max\|restore\|close\|top` | 窗口状态控制 |

全局参数：`--dry-run` 只打印不执行；`--no-human` 关闭真人熵。

## 窗口定位：三种方式

```
--win     按标题片段（Electron 应用标题会变，慎用）
--process 按进程名片段，如 chrome / bilibili / notepad   ← 最稳
--class   按窗口类名片段，如 Chrome_WidgetWin_1
```

**Electron 应用（B站、Discord、VS Code）标题随内容变化，必须用 `--process`。**

## 真人熵（human entropy）

默认开启。鼠标轨迹不是直线，而是：

- **二次贝塞尔弯曲** —— 垂直方向随机偏移控制点
- **过冲回正** —— 距离 >140px 时略微越过目标再修正
- **高斯微抖** —— 每一步叠加约 1px 的手部震颤
- **步间耗时抖动** —— ±20%，并偶发微停顿
- **精确落点** —— 最后强制落到目标坐标，保证点击不偏

实测（1442px 距离）：

| 模式 | 偏离直线最大 | 落点误差 |
|---|---|---|
| `--no-human` | 0.6 px | 0.0 px |
| 默认（human） | **8.9 px** | **0.0 px** |

**路径像人，落点像机器。** 需要绝对直线（如绘图对齐）时加 `--no-human`。

## 标准工作流

**永远按这个顺序，不要跳步：**

```
1. $PY $CC shot --out C:\tmp\s.png --grid 300 --maxw 1400
   → 用 Read 工具看图，定位目标坐标

2. $PY $CC focus --process bilibili
   → 激活窗口，核对输出的标题是不是你要的

3. $PY $CC --dry-run click --win bilibili --rx 400 --ry 60
   → 干跑确认参数

4. $PY $CC click --win bilibili --rx 400 --ry 60

5. $PY $CC stable --timeout 8
   → 等界面响应完

6. $PY $CC shot --out C:\tmp\s2.png --maxw 1400
   → 截图确认生效
```

**每步之后都要验证，不要假设成功。**

## 坐标系统

- `screen` 返回**物理分辨率**（已设 PER_MONITOR_AWARE），本机 **2880×1800**。
- 截图默认同尺寸，**与鼠标坐标系一一对应**。
- 用 `--maxw 1400` 缩放后，Read 看到的图是缩小的：
  `真实坐标 = 图中坐标 × (2880 / 图中宽度)`
- **推荐 `--grid 300`**：网格上标了真实像素值，照着读数最不容易错。
- 多显示器时用 `monitors` 拿各屏边界，虚拟桌面坐标可能是负的。

## ⚠️ 安全红线

**这套工具能真实操作电脑，用错会改坏东西。**

1. **输入前必须确认目标窗口。** `type` 打到当前前台窗口。`focus` 之后**一定要核对输出标题**。

2. **窗口匹配优先用 `--process`，别用通用标题词。**
   曾因按「Notepad」匹配，把测试文本打进了用户正在编辑的 `server.log`。
   测试自己启动的程序时，用带唯一标记的标题或按 PID 定位。

3. **不要用 `hotkey alt f4` 关窗口。** 会弹保存确认框，后续按键可能误触「保存」。
   关自己启动的程序直接结束进程。

4. **破坏性操作前先 `--dry-run`。**

5. **删除、发送、支付、提交表单类动作，必须先向用户说明并等他确认。**

6. **自己启动的测试程序要自己关掉。**

## 实现要点（改脚本时注意）

- `INPUT` 结构体 x64 下必须 **40 字节**，字段顺序类型不能错，否则 SendInput 静默失败。
- 中文必须用 `KEYEVENTF_UNICODE`，不能用 VK 码。
- 必须调 `SetProcessDpiAwareness(2)`，否则 `GetSystemMetrics` 返回逻辑分辨率（1440×900），
  与截图的物理分辨率（2880×1800）不一致，**所有坐标错位一倍**。
- 批量提交按键比逐字符快一个数量级：攒成一个 INPUT 数组一次 SendInput，
  实测 36 个中英混合字符 **0.004 秒**。
- `SetForegroundWindow` 会因前台锁定失败，需用 `AttachThreadInput` 绕过（见 `force_foreground`）。

## 环境依赖

- 截图与 `stable` 需要 **Pillow**（本机托管 Python 已具备）。缺失时 `pip install pillow`。
- 无需 pyautogui / pynput / AutoHotkey，纯 ctypes。
