# DSTranslator

DeepSeek 驱动的 Windows 翻译 / 解释悬浮窗工具。浏览网页或读 PDF 时,选中文字复制一下,立即看到翻译或释义,不用切换应用。

🌐 **在线主页**:[https://reamuray.github.io/DSTranslator/](https://reamuray.github.io/DSTranslator/) —— 功能介绍、真实截图、使用说明。

## ✨ 绿色版(免安装 · 拷贝即用)

仓库自带打包好的绿色版 **`dist/DSTranslator/`**:

- 双击 `DSTranslator.exe` 即可使用,**目标机器无需安装 Python**;
- 数据(配置、**加密的** API key、历史记录)都保存在 exe 旁的 `data\` 文件夹,**拷走整个文件夹 = 换设备数据一起带走**;
- 首次使用需输入一次 DeepSeek API key(Windows DPAPI 加密保存,只本机当前用户可解)。

也可以直接从 **[GitHub Releases](https://github.com/ReAmuroRay/DSTranslator/releases)** 下载最新绿色版 zip(解压即用)。

> 面向最终用户的操作说明见 [`docs/使用说明.md`](docs/使用说明.md)。

## 功能

- **翻译**:任意应用中选中文字,**双击 `Ctrl+C`** 弹窗自动翻译;单击只复制、不触发(他语 → 中文,默认);
- **解释**:词典 + 百科式释义;「深度解释」「联网解释」两个开关可叠加;
- **捕获开关**:托盘勾选 / 快捷键设置顶部开关,关闭后复制与唤起都不弹窗(托盘图标变灰);
- **复制触发键**:默认 `Ctrl+C` 双击触发,可改成自定义组合键(单击触发);
- **唤起 / 关闭**:`Ctrl+Alt+S` 空召、托盘双击唤起;`Esc` 关闭(均可自定义);
- **弹窗**:固定驻留或自动消失(N 秒无操作自动收起,可配)、边缘/角落拖拽调大小、位置与尺寸记忆;
- **历史记录**:本地 SQLite,可搜索 / 删除 / 复制 / 导出。

## 开发者

- **源码**:位于 `src/`(`main.py` 为入口,`dstl/` 为应用包)。
- **环境与从源码运行**:

  ```bash
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
  .venv\Scripts\python src\main.py
  ```

- **重新打包绿色版**:见 [`docs/打包指南.md`](docs/打包指南.md)(命令 `pyinstaller DSTranslator.spec` + 拷贝使用说明)。
- **术语与架构决策**:[`docs/CONTEXT.md`](docs/CONTEXT.md)、[`docs/adr/`](docs/adr/)。
- **开发历程**:[`docs/CHANGELOG.md`](docs/CHANGELOG.md)。

## 目录结构

```
├── src/                    源码(main.py + dstl/)
├── dist/DSTranslator/      绿色版(免安装,拷走即用)
├── docs/                   文档(使用说明 / 打包指南 / CHANGELOG / CONTEXT / ADR)
├── tools/                  make_icon.py(图标生成)
├── DSTranslator.spec       打包脚本
├── dstl.ico                图标
└── requirements.txt / smoke_test.py / .gitignore
```
