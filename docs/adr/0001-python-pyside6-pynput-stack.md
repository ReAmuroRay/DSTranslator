# Python + PySide6 + pynput 作为技术栈

为 DSTranslator 选择 Python + PySide6 + pynput,而非 Electron、Tauri 或 C#/WPF。

核心需求是监听剪贴板捕获用户复制的内容、一个全局唤起热键、以及无边框置顶的悬浮窗口。早期设计还包含全局热键抓取与左键+右键鼠标组合两种捕获,需要系统级鼠标钩子;后因与其他应用热键冲突,捕获收敛为仅剪贴板(见 [0003](0003-capture-clipboard-only.md)),钩子需求只余全局唤起热键。`pynput` 对全局热键开箱即用,`PySide6` 对无边框置顶窗口支持成熟,Python 迭代最快,适合单人开发。

目标平台限定 Windows,规避了 Python 跨平台打包的短板。分发用 PyInstaller 单文件,代价是体积较大且部分杀软会误报——接受该代价。

**Consequences**:打包体积与杀软误报是已知代价;全局热键的实现细节随 Windows 钩子机制走。
