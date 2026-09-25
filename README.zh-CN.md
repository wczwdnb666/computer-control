# computer-control

**给我的 AI 助手装上眼睛和手。**

一个面向 AI Agent 的 Windows 桌面自动化工具包。截图看屏幕、鼠标带真人轨迹、点击、打字、读写剪贴板、定位窗口——全部由一个 Python 脚本搞定，通过 `ctypes` 直接调 `user32.dll`。

不需要 `pyautogui`，不需要 `pynput`，不需要 AutoHotkey。除了截图用的 Pillow，**零依赖**。

```
$ python cc.py shot --out screen.png --grid 300     # 先看
$ python cc.py click --win notepad --rx 400 --ry 60 # 点窗口里的相对位置
$ python cc.py type "你好 world"                     # 再打字
```

[English README](README.md)

---

## 为什么要做这个

浏览器自动化早就成熟了。**但原生桌面应用没有。**

当你需要操作的东西没有 API——闭源客户端、十年前的老工具、游戏启动器、用 canvas 画界面的 Electron 应用——你唯一的办法就是像人一样去动鼠标键盘。

这个工具就是为这个场景写的。而且在写的过程中，我踩了一堆坑，所以它专门解决这些：

**DPI 缩放会把所有坐标搞错一倍。** 忘了调 `SetProcessDpiAwareness`，`GetSystemMetrics` 会返回逻辑分辨率 1440×900，而截图是物理分辨率 2880×1800。于是每次点击都落在目标的一半位置——而且不报错，就是点不中。这个坑我踩了，现在填好了。

**Electron 应用的标题一直在变。** 按标题文字匹配窗口，页面一跳转就失效。得按进程名匹配才行。

**绝对坐标会过期。** 用户一拖窗口，写死的位置全废。所以所有点击都支持窗口相对坐标。

**机器人动起来真的像机器人。** 完美直线、匀速运动，既容易被检测出来，录屏里看着也假。

## 能干什么

### 看

`screen` 看分辨率，`monitors` 看所有显示器边界，`pixel` 读某个点的颜色。

`shot` 截图，支持全屏、指定区域、或者某个窗口的客户区。加 `--grid 300` 会在图上叠一层坐标网格，**网格边标的是真实像素值**，Agent 可以直接照着读数，不用自己换算。这个功能是踩坑之后加的——最早没有它，我对着截图目测坐标，点偏了三次。

`stable` 会阻塞到屏幕停止变化，用来等页面加载完。比 `sleep 3` 靠谱：快的时候 0.7 秒就返回，慢的时候它会一直等。

### 动鼠标

`move` `hover` `click` `rclick` `dclick` `mclick` `drag` `down` `up` `scroll`——左键、右键、双击、中键、拖拽、悬停、长按，都齐了。

所有点击命令都能用**窗口相对坐标**：

```bash
python cc.py click --win notepad --rx 400 --ry 60   # 客户区左上角 + (400, 60)
python cc.py click --process chrome --center        # 窗口正中心
```

这样窗口被拖动或调整大小之后，坐标依然有效。

### 打字

```bash
python cc.py type "你好 world"        # Unicode，中文没问题
python cc.py key enter
python cc.py hotkey ctrl shift s
```

中文能打是因为走 `KEYEVENTF_UNICODE` 而不是虚拟键码——虚拟键码根本表达不了汉字。

速度上，输入是攒成一批一次性提交的。实测 **36 个中英混合字符 0.004 秒**。

### 剪贴板

```bash
python cc.py clip --set "要粘贴的文本"
python cc.py clip --get
```

读回剪贴板是**验证输入是否成功**最可靠的方式——比看截图准，因为不用肉眼判断。示例脚本里就用它做二次校验。

### 找窗口

`windows` 列窗口，`info` 看位置尺寸，`focus` 激活，`waitwin` 等它出现，`winstate` 最小化/最大化/关闭。

三种定位方式，**推荐第二种**：

```bash
--win      "标题片段"          # 脆弱：Electron 标题会变
--process  chrome              # 稳
--class    Chrome_WidgetWin_1  # 最精确
```

## 真人熵

鼠标默认不是"从 A 匀速滑到 B"。它按真人的运动模型走：

**反应延迟**——决定移动之后，手不会立刻动，先停 45~160 毫秒。

**多段子运动**——这是最关键的一条。真人搬鼠标不是一次到位，而是**弹道冲刺 → 停一下 → 修正 → 停一下 → 微调**。每段覆盖剩余距离的固定比例（约 86%），所以后段距离越来越小、但时间占比不按比例缩，速度自然降下来。如果距离和时间一起缩，全程匀速，一眼就假。

**非对称速度曲线**——每段内部加速快、减速慢，不是对称缓动。

**低频手抖**——生理性手抖是 8~12Hz。如果每个采样点换个新随机值，抖动频率会到 200Hz，看起来像鼠标坏了不像人手。所以每 16~26 个采样点才取一个新随机值，中间插值。

实测（1664 像素的距离）：

| 模式 | 速度峰数 | 速度剖面 | 偏离直线 | 落点误差 |
|---|---|---|---|---|
| `--no-human` | **2 个** | 对称钟形（加速→匀速→减速）——机器人的指纹 | 0.8 px | 0.0 px |
| 默认 | **5 个** | 冲刺→回落→修正→回落→微调，尾部缓慢收尾 | 12 px | **0.0 px** |

实测路程 1672px vs 直线 1664px，**只多走 0.5%**——像人，但没在乱晃。

移动耗时按距离自动估算（`170 + 距离 × 0.42` 毫秒，钳制在 200~1150ms）。真人对不同距离的手感不一样，远距离不会一秒就到。

需要绝对直线时加 `--no-human`；需要瞬间到位加 `--duration 0`。

## 装上试试

Windows + Python 3.8+。只有截图和 `stable` 需要 Pillow。

```bash
git clone https://github.com/<you>/computer-control.git
cd computer-control
pip install pillow        # 可选，不截图就不需要
python scripts/cc.py screen
```

## 给 Agent 用

`SKILL.md` 是写给支持技能的 Agent 框架（WorkBuddy、Claude Code 之类）看的技能描述文件。里面除了命令说明，还写清了坐标系怎么算、标准流程是什么、以及必须遵守的安全红线。

如果你的框架不支持技能，直接调 `scripts/cc.py` 就行，它就是个普通命令行程序。

## Agent 应该照着做的流程

```
1. shot --grid 300 --maxw 1400     → 先看，找到目标在哪
2. focus --process <应用>           → 激活它，核对标题对不对
3. --dry-run click ...             → 干跑一遍确认参数
4. click ...
5. stable --timeout 8              → 等界面反应完
6. shot --out after.png            → 截图确认真的生效了
```

**第 2 步和第 6 步最容易被跳过，也最重要。点了不看结果的自动化是负债，不是资产。**

## 安全

这工具真的能操控电脑，用错会毁掉工作成果。这几条是真金白银换来的：

- **打字前必须确认目标窗口。** `type` 打到当前有焦点的窗口，`focus` 之后一定要核对它输出的标题。
- **优先用 `--process`，别用标题匹配。** 我曾经按通用词「Notepad」去匹配，结果把 27 个测试字符打进了用户正在编辑的 `server.log`——幸好保存提示上按的是"不保存"。
- **绝对不要用 `alt+f4` 关窗口。** 会弹保存确认框，后面排队的按键很容易误触"保存"。关自己启动的进程请直接 terminate。
- **破坏性操作前先 `--dry-run`。**
- **删除、发送、支付、提交表单之前，必须先问用户。**

## 实现上几个要命的点

| 技术 | 为什么重要 |
|---|---|
| 全部用 `SendInput` | 可靠且原子；`mouse_event` / `keybd_event` 已经废弃了 |
| `INPUT` 结构体 x64 下必须 40 字节 | 大小或字段顺序错会**静默失败**——不报错，也没有输入 |
| 文本走 `KEYEVENTF_UNICODE` | 虚拟键码表达不了中文和 emoji |
| 必须调 `SetProcessDpiAwareness(2)` | 不调的话所有坐标按缩放比例偏移 |
| `SetForegroundWindow` 前先 `AttachThreadInput` | 前台锁被占用时裸调用会失败 |
| 批量 `SendInput` 数组 | N 次按键只走一次系统调用 |
| 读颜色用 GDI `GetPixel` | 比为一个像素截整屏便宜得多 |

## 许可

**0BSD**（Zero-Clause BSD）—— 想怎么用就怎么用：改、卖、闭源分发都行。**没有任何条件，也不要求署名。** 见 [LICENSE](LICENSE)。
