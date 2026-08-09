# DSTranslator

DeepSeek 驱动的 Windows 翻译 / 解释悬浮工具。浏览网页或读 PDF 时,选中内容即可翻译或查义,不离开当前应用。

设计决策见 [`adr/`](adr/),术语见 [`CONTEXT.md`](CONTEXT.md),开发历程见 [`CHANGELOG.md`](CHANGELOG.md),打包见 [`打包指南.md`](打包指南.md)。

## 环境

- Python 3.12(本机使用 Anaconda 的 `markitdown` 环境创建 venv)
- Windows 10 / 11

## 安装与运行

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python src\main.py
```

首次启动会要求输入 DeepSeek API key(Windows DPAPI 加密;源码运行存于 `%APPDATA%\DSTranslator\api_key.dat`,打包便携版存于 exe 旁 `data\api_key.dat`)。

## 使用

- **捕获**:在任意应用中选中文字后 `Ctrl+C`,搜索栏即在停放位置出现并自动执行当前模式(翻译/解释)。
- **唤起键**:`Ctrl+Alt+S` 空召一个空的搜索栏手动粘贴;托盘图标双击也可唤起。
- **关闭**:`Esc`(可在快捷键设置里改)或顶栏 ×。「弹窗消失」见 ⚙ 设置:固定驻留(默认)或自动(N 秒无操作自动收起,默认 10 秒,可配)。
- **解释面板**:「解释」tab 下有「深度解释」「联网解释」两个滑块开关,可叠加(联网+深度),切换后自动重新解释当前内容。
- **⚙ 设置**:弹窗消失、快捷键设置(唤起/关闭键)、开机自启、历史记录、配置 API key、退出。
