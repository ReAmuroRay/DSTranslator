# DSTranslator 开发历程

DeepSeek 驱动的 Windows 翻译 / 解释悬浮工具。本文档按阶段记录从设计到当前版本的功能演进、关键 Bug 与根因,便于回看与交接。

术语与架构决策另见 [`CONTEXT.md`](CONTEXT.md) 与 [`adr/`](adr/)。

---

## 阶段零 · 设计(grilling 会话)

通过「grilling + domain-modeling」会话敲定需求与术语,产出:

- **界面形态**:捕获触发的搜索栏(平时隐藏、捕获即出现在停放位并自动翻译、Esc 收起)。`ADR-0002`
- **两个功能**:翻译(他语→中文,默认)/ 解释(词典+百科式释义),均由用户提供的 DeepSeek API key 驱动,默认不联网。
- **技术栈**:Python + PySide6 + pynput(无边框置顶窗口 + 全局钩子)。`ADR-0001`
- **API key**:首次启动输入,Windows DPAPI 加密存 `%APPDATA%\DSTranslator\api_key.dat`。
- **模型**:`deepseek-v4-flash`,OpenAI 兼容端点,全流式输出。核实了 `deepseek-chat`/`deepseek-reasoner` 已于 2026-07-24 停用,并确认 Responses API 的 `web_search` 工具可用。

## v0.1.0 · 初始骨架(首个可运行版本)

功能:

- 三种捕获方式:剪贴板监听、全局热键(`Ctrl+Alt+T` 抓选中文本)、左键+右键鼠标组合。
- 搜索栏:无边框置顶、翻译/解释两个 tab、自动翻译、流式输出 + 停止按钮、Esc 收起、自动消失(8s)。
- 历史记录(SQLite):列表/搜索/删除/复制/导出。
- 系统托盘 + 可选开机自启(注册表 HKCU Run)。
- 冒烟测试 `smoke_test.py`(无 GUI 逻辑测试)。

### 关键 Bug 与根因

| Bug | 根因 | 修复 |
|---|---|---|
| **捕获事件"到了但弹窗不出现"** | `main.py` 中 `Application(app).run()` 的 Application 是**临时对象**,`run()` 返回后即被 GC;`_search_bar` 随之失引用,PySide6 对绑定方法的信号连接随接收对象被回收而失效(lambda 连接因无接收对象而幸存)。从第一次运行就存在。 | 持有 Application 引用(`application = Application(app); application.run()`) |
| 热键 `Ctrl+Alt+T` 无效 | pynput `GlobalHotKeys` 要求修饰键带尖括号(`<ctrl>+<alt>+t`),`ctrl+alt+t` 解析失败被静默吞掉 | `normalize_hotkey()` 归一化 |
| 剪贴板轮询每 2s 重复触发相同内容 | 用 `QTimer` 轮询 + 2s 去重,内容不变也反复触发 | 改用 `QClipboard.dataChanged` 信号,仅在真正变化时触发 |
| API key 加密后解不开 | `CryptUnprotectData` 在 pywin32 返回 `(description, data)`,取反了 | 修正取第二个元素 |

## v0.2.0 · 按用户反馈收敛交互

用户实测后提出的一系列调整:

- **捕获固定为仅 `Ctrl+C`**(读剪贴板):删除全局热键抓取与鼠标组合,避免与其他应用冲突。`ADR-0003`
- **弹窗消失**:默认「固定驻留」(顶栏 × / Esc 关闭);可选「自动」,从流式输出结束起 N 秒收起(默认 10s,可配)。
- **唤起键**:`Ctrl+Alt+S` 空召;托盘双击也可唤起。
- **解释面板**:「深度解释」「联网解释」两个开关移入解释 tab,滑块样式(IOS 式),可叠加。
- **切换开关自动重跑**当前解释(修复"切开关不刷新")。

### 关键 Bug

| Bug | 根因 | 修复 |
|---|---|---|
| 翻译/解释流式输出时切换模式,旧输出串入新模式 | 旧线程 `stop` 回调 `lambda: self._stop_event.is_set()` **动态读取** `self._stop_event`,切换时被换成新 Event,旧线程停不下来 | ① stop 事件按实例**绑定**给工作线程;② 新增 `run_id` 令牌,过期输出的 token/finished/error 全部丢弃 |
| 解释输出带 `**`、`*`、`` ` `` 等 Markdown 符号 | 直接渲染 LLM 原始输出 | 新增 `strip_markdown`,输出完成后转纯文本(加粗/斜体/代码/链接/列表/标题等) |
| 弹窗自动收起打断设置操作 | `_on_autohide` 只查 `hasFocus()`,设置菜单打开时焦点在弹出层上,弹窗被判为"空闲" | 自动模式下,弹出层打开或鼠标悬停弹窗时**不收起** |
| 空唤(无流式输出)不自动收起 | 倒计时只在"流式结束后"启动 | 自动模式 = 出现后 N 秒无操作自动收起(空唤也计时,打字/操作重置) |

## v0.3.0 · 快捷键与设置 UI 完善

- **快捷键设置页**:⚙ → 快捷键设置,唤起键 / 关闭键可录制式修改(按下新组合键即生效),校验(唤起键需修饰键、不可重复),唤起键变更热更新 pynput 监听。`config` 新增 `close_key`(默认 `esc`)。
- **弹窗消失菜单重设计**:自动秒数从"与固定/自动并列"改为**「自动」的缩进子行**(固定驻留时置灰,自动时点「编辑…」改秒数,1–600s)。
- **弹出即聚焦**:Windows 下用 `AttachThreadInput + SetForegroundWindow` 抢焦点,Esc / 输入立即可用。
- **对比度增强**:× 圆形带边框按钮,边框/文字加深。
- **深度 + 联网叠加**:联网解释走 Responses API 时透传 `thinking`(此前联网时忽略深度)。

## v0.4.0 · 窗口手动调大小

- 右下角可拖拽调大小;尺寸记入 `config.json` 下次沿用;最小 480×220,结果区可自由变高。

### 关键 Bug / 迭代

| 问题 | 根因 | 解决 |
|---|---|---|
| "看不到手柄" | 手柄 3 条 1px 浅灰细线,浅色背景上几乎不可见(裸 widget 对照实验证实与样式表无关) | 换成浅灰圆角方块 + 深色粗斜线 |
| "手柄太丑,要悬停变光标" | 可见手柄不是想要的交互 | 改为透明热区:右下角悬停变对角缩放光标 |
| "右下角很难选中,要整个边缘可拖" | 独立热区只有 26×26,太窄;且原热区与结果区在 DPI 缩放下对齐不易 | 用 Windows 原生 `WM_NCHITTEST`:右/下/左边缘 + 底部两角整条可拖,顶部条带保留为移动区,系统自动切换缩放光标 |
| 边缘按了只移动不缩放 | 8px 边缘热区太窄,鼠标按在边缘内侧几像素处被判定为内部 → 落入移动逻辑(日志证实:命中返回 HT_CLIENT) | 边缘热区加宽到 **14px**,日志确认缩放命中码(ht=11/15)正常返回 |

## v0.5.0 · 绿色版打包(免安装、拷贝即用)

- **PyInstaller one-folder 打包**,产物 `../dist/DSTranslator/`(约 137MB,含整个 PySide6 运行时),目标机器**无需安装 Python**。
- **便携数据目录**:打包后数据(config / 加密的 API key / 历史)存 exe 旁 `data\` 文件夹,拷走整个目录即带数据;位置不可写(如 Program Files)或源码运行时回退 `%APPDATA%`。
- `data\` 被删后下次运行自动重建;key 随之丢失需重输。
- 打包脚本 `../DSTranslator.spec`(重建命令:在项目根目录 `pyinstaller DSTranslator.spec`),图标由 `../tools/make_icon.py` 生成多尺寸 .ico。

### 关键 Bug / 经验

| 问题 | 根因 | 解决 |
|---|---|---|
| 打包 exe 启动即 `ImportError`(pynput 后端) | PyInstaller 未收集 pynput 的平台后端子模块 | spec 里 `collect_all('pynput')` |
| `DLL load failed while importing _ctypes / _sqlite3 / ...` | **conda 环境的 Python 其标准库扩展模块链接 conda 的 DLL**(`ffi.dll`、`sqlite3.dll`、`libcrypto`、`liblzma` 等),而 PyInstaller 的依赖扫描漏掉 `Library\bin` | spec 里把 `Library\bin\*.dll` 全部打进 `_internal` |
| 经验 | conda Python 打包必须显式带上 `Library\bin` 的运行库,否则逐类报 DLL 加载失败 | 已固化在 spec 中 |

### 实测通过(打包 exe 本体)

启动无报错、`data\` 自动生成、剪贴板捕获→翻译→历史入库、pynput 热键监听、DPAPI 解密 key、托盘。

---

## 当前能力速览

- 捕获:任意应用 `Ctrl+C` → 自动翻译 / 解释。
- 唤起:`Ctrl+Alt+S`(可在快捷键设置改)、托盘双击。
- 关闭:`Esc`(可改)、顶栏 ×、固定驻留 / 自动(N 秒无操作,可配)。
- 解释面板:深度解释 / 联网解释 滑块开关,可叠加,切换自动重跑;输出过滤 Markdown。
- 窗口:边缘 / 底部两角拖拽调大小,尺寸记忆;顶部拖动移动,位置记忆。
- 历史记录:SQLite,列表/搜索/删除/复制/导出。
- 托盘:显示/隐藏、历史、配置 key、退出;可选开机自启。

## 待办 / 已知边界

- PDF 等无法选中文字的控件:需手动 `Ctrl+C` 复制。
- 弹出即聚焦会从当前阅读应用抢走焦点(连续查词需点回阅读应用),如需可加"不抢焦点"开关。
- 打包后体积约 137MB;首次运行可能被 SmartScreen/杀软提示"未知发布者"(未签名),需加白名单或点"仍要运行";彻底解决需代码签名证书。
