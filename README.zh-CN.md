# computer-control

**给你的 AI 助手装上眼睛和手。**

面向 AI Agent 的 Windows 桌面自动化工具包。截图看屏幕、鼠标带真人轨迹移动、点击、输入、读写剪贴板、定位窗口——全部由一个 Python 脚本完成，通过 `ctypes` 直接调 `user32.dll`。

不需要 `pyautogui`、`pynput`、AutoHotkey。除了截图用的 Pillow，**零依赖**。

```
$ python cc.py shot --out screen.png --grid 300     # 看屏幕
$ python cc.py click --win notepad --rx 400 --ry 60 # 点窗口里的相对位置
$ python cc.py type "你好 world"                     # 输入
```

[English README](README.md)

---

## 为什么做这个

浏览器自动化已经很成熟，**但原生桌面应用不是**。当你需要操作的东西没有 API——闭源客户端、老旧工具、游戏启动器、用 canvas 画的 Electron 界面——唯一的路就是像人一样操作鼠标键盘。

这个工具就是为这个场景写的，并且专门解决实际会踩的坑：

- **DPI 缩放会让所有坐标失效。** 不调 `SetProcessDpiAwareness`，`GetSystemMetrics` 返回 1440×900，而截图是 2880×1800——每次点击都落在目标的一半位置。
- **Electron 窗口标题一直在变。** 按标题匹配，页面一跳转就失效。应该按进程名匹配。
- **绝对坐标会过期。** 用户一拖窗口，写死的位置全废。应该用窗口相对坐标。
- **机器人动起来像机器人。** 完美直线、匀速运动，既容易被检测，录出来也假。

## 功能

### 观察

| 命令 | 说明 |
|---|---|
| `screen` | 物理分辨率与坐标范围 |
| `monitors` | 所有显示器及其边界 |
| `shot` | 截图——全屏 / 指定区域 / 某个窗口的客户区 |
| `pixel` | 读某点颜色（RGB + HEX） |
| `stable` | 阻塞到屏幕停止变化——等页面加载完 |

`shot --grid 300` 会叠加带真实像素值的坐标网格，Agent 可以直接从图里读坐标。

### 鼠标

`move` `hover` `click` `rclick` `dclick` `mclick` `drag` `down` `up` `scroll`

**所有点击命令都支持窗口相对坐标：**

```bash
python cc.py click --win notepad --rx 400 --ry 60   # 客户区左上角 + (400,60)
python cc.py click --process chrome --center        # 窗口正中心
```

### 键盘

```bash
python cc.py type "你好 world"        # Unicode，支持中文
python cc.py key enter
python cc.py hotkey ctrl shift s
```

输入是批量提交的——36 个中英混合字符 **0.004 秒**落地。

### 剪贴板

```bash
python cc.py clip --set "要粘贴的文本"
python cc.py clip --get
```

### 窗口

`windows` `info` `focus` `waitwin` `winstate`

三种定位方式，**推荐第二种**：

```bash
--win      "标题片段"          # 脆弱：Electron 标题会变
--process  chrome              # 稳
--class    Chrome_WidgetWin_1  # 最精确
```

## 真人熵

鼠标默认不走直线。每次移动：

- **弯曲** —— 二次贝塞尔，控制点随机偏移
- **过冲** —— 超过约 140px 时略微越过目标再回正
- **抖动** —— 每步约 1px 的高斯噪声，模拟手部震颤
- **节奏不均** —— 步间耗时 ±20% 抖动，偶发微停顿
- **精确落点** —— 最后强制落到真实目标坐标

实测（1442px 距离）：

| 模式 | 偏离直线最大 | 落点误差 |
|---|---|---|
| `--no-human` | 0.6 px | 0.0 px |
| 默认 | **8.9 px** | **0.0 px** |

**路径像人，落点像机器。** 需要绝对直线时（比如对齐绘图参考线）加 `--no-human`。

## 安装

Windows + Python 3.8+。只有截图和 `stable` 需要 Pillow。

```bash
git clone https://github.com/<you>/computer-control.git
cd computer-control
pip install pillow        # 可选
python scripts/cc.py screen
```

## 作为 Agent 技能使用

`SKILL.md` 是给支持技能的 Agent 框架（WorkBuddy、Claude Code 等）用的技能描述文件，写明了命令、坐标系、观察-操作-验证的标准流程，以及必须遵守的安全红线。

不支持技能的话，直接调 `scripts/cc.py` 即可，它就是个普通 CLI。

## Agent 应该遵循的流程

```
1. shot --grid 300 --maxw 1400     → 先看，定位目标
2. focus --process <应用>           → 激活，核对标题对不对
3. --dry-run click ...             → 干跑确认参数
4. click ...
5. stable --timeout 8              → 等界面稳定
6. shot --out after.png            → 截图确认生效
```

**验证步骤一步都不能省。** 点了不看结果的 Agent 是负债。

## 安全

这工具真的能操控电脑，用错会毁掉工作成果。

- **输入前必须确认目标窗口。** `type` 打到当前焦点窗口，`focus` 之后一定要核对标题。
- **优先用 `--process` 而不是标题匹配。** 曾经因为匹配通用词「Notepad」，把测试文本打进了用户正在编辑的 `server.log`。
- **不要用 `alt+f4` 关窗口。** 会弹保存确认框，后续按键可能误触「保存」。关自己启动的进程请直接 terminate。
- **破坏性操作前先 `--dry-run`。**
- **删除、发送、支付、提交表单前必须问用户。**

## 实现要点

| 技术 | 为什么重要 |
|---|---|
| 全部用 `SendInput` | 可靠且原子；`mouse_event` / `keybd_event` 已废弃 |
| `INPUT` 结构体 x64 下必须 40 字节 | 大小或字段顺序错会**静默失败**——不报错，也没输入 |
| 文本用 `KEYEVENTF_UNICODE` | VK 码表达不了中文和 emoji |
| 必须调 `SetProcessDpiAwareness(2)` | 不调则所有坐标按缩放比例偏移 |
| `SetForegroundWindow` 前先 `AttachThreadInput` | 前台锁被持有时裸调用会失败 |
| 批量 `SendInput` 数组 | N 次按键一次系统调用 |
| 读颜色用 GDI `GetPixel` | 比为一个像素截整屏便宜得多 |

## 许可

MIT，见 [LICENSE](LICENSE)。
