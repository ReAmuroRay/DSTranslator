"""捕获触发的搜索栏:无边框、置顶、平时隐藏,捕获时出现在停放位并自动翻译。

- 「翻译」「解释」两个 tab;「解释」面板内放两个滑块开关:深度解释 / 联网解释,
  切换后自动重新解释当前内容。
- 顶栏 × 关闭按钮;⚙ 设置含「弹窗消失」(固定驻留 / 自动·流式结束后 N 秒)。
- 流式结果在工作线程生成,通过 Qt 信号跨线程更新 UI。
"""
from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from .. import autostart
from ..config import Config
from ..deepseek_client import DeepSeekClient
from ..hotkeys import combo_from_qkeyevent, normalize_combo
from ..text_utils import strip_markdown

_QSS = """
SearchBar {
    background-color: rgba(255, 255, 255, 0.98);
    border: 1px solid #aab3c0;
    border-radius: 12px;
}
QLineEdit#sourceInput {
    border: 1px solid #b6bfca;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 14px;
    background: #f2f4f7;
    selection-background-color: #b6d4fe;
}
QPushButton#modeBtn {
    border: 1px solid #b6bfca;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
    background: #f2f4f7;
}
QPushButton#modeBtn:checked {
    background: #2f6fed;
    color: white;
    border-color: #2f6fed;
}
QPushButton#toolBtn {
    border: none;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    background: transparent;
}
QPushButton#toolBtn:hover { background: #e6e9ee; }
QPushButton#closeBtn {
    border: 1px solid #aab3c0;
    border-radius: 13px;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    padding: 0;
    font-size: 15px;
    color: #4b5563;
    background: #ffffff;
}
QPushButton#closeBtn:hover { background: #e0483e; border-color: #e0483e; color: #ffffff; }
QWidget#explainPanel {
    background: #eaf1ff;
    border: 1px solid #bcd0fa;
    border-radius: 8px;
}
QTextEdit#resultArea {
    border: 1px solid #d5dae1;
    border-radius: 8px;
    background: #fbfcfd;
    font-size: 14px;
    padding: 8px;
}
QMenu { font-size: 13px; }
"""


class _WorkerSignals(QObject):
    token = Signal(str, int)   # (token, run_id)
    finished = Signal(int)     # run_id
    error = Signal(str, int)   # (message, run_id)


class _Grip(QWidget):
    """顶部拖动手柄:忽略鼠标事件,使其冒泡到 SearchBar 处理移动。"""

    def mousePressEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()


# 原生边缘缩放的窗口命中测试常量(Windows WM_NCHITTEST)
_HT_LEFT, _HT_RIGHT, _HT_TOP, _HT_TOPLEFT = 10, 11, 12, 13
_HT_TOPRIGHT, _HT_BOTTOM, _HT_BOTTOMLEFT, _HT_BOTTOMRIGHT = 14, 15, 16, 17
_HT_CLIENT = 1
_EDGE = 14       # 边缘热区厚度(px),加宽便于对准
_TOP_MOVE = 6    # 顶部条带高度,保留给移动(对应拖动手柄)


class _ToggleSwitch(QWidget):
    """iOS 式滑块开关。"""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = bool(checked)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, on: bool) -> None:
        on = bool(on)
        if on != self._checked:
            self._checked = on
            self.toggled.emit(on)
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            event.accept()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._checked:
            p.setBrush(QColor("#2f6fed"))
            knob_x = 36 - 16 - 2
        else:
            p.setBrush(QColor("#d0d7de"))
            knob_x = 2
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, 36, 20, 10, 10)
        p.setBrush(QColor("white"))
        p.drawEllipse(knob_x, 2, 16, 16)
        p.end()


class SearchBar(QWidget):
    result_done = Signal(str, str, str)  # (source, result, mode)
    history_requested = Signal()
    configure_key_requested = Signal()
    shortcut_settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, config: Config, client: Optional[DeepSeekClient] = None, parent=None):
        super().__init__(parent)
        self._config = config
        self._client = client
        self._stop_event = threading.Event()
        self._run_id = 0
        self._streaming = False
        self._result_buffer = ""
        self._drag_offset = None
        self._secs_val: Optional[QLabel] = None
        self._secs_btn: Optional[QPushButton] = None

        self._signals = _WorkerSignals()
        self._signals.token.connect(self._on_token)
        self._signals.finished.connect(self._on_finished)
        self._signals.error.connect(self._on_error)

        self.setObjectName("SearchBar")
        self.setMinimumSize(480, 220)
        self._resize_timer: Optional[QTimer] = None
        self._build_ui()

        self._autohide_timer = QTimer(self)
        self._autohide_timer.setSingleShot(True)
        self._autohide_timer.timeout.connect(self._on_autohide)

    # --- UI -------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addWidget(_Grip(self))

        row = QHBoxLayout()
        row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setObjectName("sourceInput")
        self._input.setPlaceholderText("粘贴或输入内容…(Enter 执行)")
        self._input.returnPressed.connect(self.run_current_mode)
        self._input.textChanged.connect(self._on_input_changed)
        row.addWidget(self._input, 1)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._btn_translate = self._make_mode_btn("翻译", 0)
        self._btn_explain = self._make_mode_btn("解释", 1)
        self._btn_translate.setChecked(self._config.default_mode != "explain")
        self._btn_explain.setChecked(self._config.default_mode == "explain")
        row.addWidget(self._btn_translate)
        row.addWidget(self._btn_explain)

        self._btn_stop = QPushButton("■ 停止")
        self._btn_stop.setObjectName("toolBtn")
        self._btn_stop.clicked.connect(self._on_stop_clicked)
        self._btn_stop.hide()
        row.addWidget(self._btn_stop)

        self._btn_menu = QPushButton("⚙")
        self._btn_menu.setObjectName("toolBtn")
        self._btn_menu.setToolTip("设置")
        self._btn_menu.clicked.connect(self._open_menu)
        row.addWidget(self._btn_menu)

        self._btn_close = QPushButton("×")
        self._btn_close.setObjectName("closeBtn")
        self._btn_close.setToolTip("关闭 (Esc)")
        self._btn_close.clicked.connect(self._on_close_clicked)
        row.addWidget(self._btn_close)

        root.addLayout(row)

        # 解释面板:两个滑块开关,仅在「解释」tab 显示
        self._explain_panel = QWidget()
        self._explain_panel.setObjectName("explainPanel")
        explain_row = QHBoxLayout(self._explain_panel)
        explain_row.setContentsMargins(10, 6, 10, 6)
        explain_row.setSpacing(14)
        lbl = QLabel("解释选项")
        lbl.setStyleSheet("color:#2f6fed; font-weight:600; font-size:13px;")
        explain_row.addWidget(lbl)
        self._switch_deep = _ToggleSwitch(self._config.thinking_enabled)
        self._switch_deep.toggled.connect(self._set_thinking)
        self._lbl_deep = QLabel("深度解释")
        self._lbl_deep.setStyleSheet("font-size:13px;")
        explain_row.addWidget(self._switch_deep)
        explain_row.addWidget(self._lbl_deep)
        self._switch_web = _ToggleSwitch(self._config.web_search_enabled)
        self._switch_web.toggled.connect(self._set_web_search)
        self._lbl_web = QLabel("联网解释")
        self._lbl_web.setStyleSheet("font-size:13px;")
        explain_row.addWidget(self._switch_web)
        explain_row.addWidget(self._lbl_web)
        explain_row.addStretch(1)
        self._explain_panel.hide()
        root.addWidget(self._explain_panel)

        self._result = QTextEdit()
        self._result.setObjectName("resultArea")
        self._result.setReadOnly(True)
        self._result.setAcceptRichText(False)
        self._result.setMinimumHeight(90)
        root.addWidget(self._result, 1)

    def _make_mode_btn(self, text: str, bid: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("modeBtn")
        btn.setCheckable(True)
        self._mode_group.addButton(btn, bid)
        btn.clicked.connect(self._on_mode_switch)
        return btn

    def _open_menu(self) -> None:
        menu = QMenu(self)

        dismiss_menu = menu.addMenu("弹窗消失")
        act_pin = dismiss_menu.addAction("固定驻留")
        act_pin.setCheckable(True)
        act_pin.setChecked(self._config.dismiss_mode != "auto")
        act_pin.triggered.connect(lambda: self._set_dismiss("pin"))
        act_auto = dismiss_menu.addAction("自动")
        act_auto.setCheckable(True)
        act_auto.setChecked(self._config.dismiss_mode == "auto")
        act_auto.triggered.connect(lambda: self._set_dismiss("auto"))
        # 秒数作为「自动」的缩进子行,固定驻留时置灰
        dismiss_menu.addAction(self._make_secs_row(dismiss_menu))

        menu.addAction("快捷键设置…", lambda: self.shortcut_settings_requested.emit())

        act_autostart = menu.addAction("开机自启")
        act_autostart.setCheckable(True)
        act_autostart.setChecked(self._config.autostart)
        act_autostart.toggled.connect(self._set_autostart)

        menu.addSeparator()
        menu.addAction("历史记录…", lambda: self.history_requested.emit())
        menu.addAction("配置 API key…", lambda: self.configure_key_requested.emit())
        menu.addSeparator()
        menu.addAction("退出", lambda: self.quit_requested.emit())

        menu.exec(self._btn_menu.mapToGlobal(self._btn_menu.rect().bottomLeft()))

    def _set_dismiss(self, mode: str) -> None:
        self._config.dismiss_mode = mode
        self._config.save()
        self._update_secs_row()
        self._arm_autohide()  # 切换后立即生效:自动->启动倒计时,固定->停止

    def _make_secs_row(self, menu: QMenu) -> QWidgetAction:
        """秒数编辑行:作为「自动」的缩进子行,固定驻留时置灰。"""
        action = QWidgetAction(menu)
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(30, 2, 12, 2)
        lay.setSpacing(8)
        lbl = QLabel("秒数")
        lbl.setStyleSheet("color:#4b5563; font-size:12.5px;")
        self._secs_val = QLabel()
        self._secs_btn = QPushButton("编辑…")
        self._secs_btn.clicked.connect(self._edit_auto_hide_seconds)
        lay.addWidget(lbl)
        lay.addWidget(self._secs_val)
        lay.addWidget(self._secs_btn)
        lay.addStretch(1)
        action.setDefaultWidget(w)
        self._update_secs_row()
        return action

    def _update_secs_row(self) -> None:
        if self._secs_val is None or self._secs_btn is None:
            return
        enabled = self._config.dismiss_mode == "auto"
        self._secs_val.setText(f"{self._config.auto_hide_seconds} 秒")
        self._secs_btn.setEnabled(enabled)
        if enabled:
            self._secs_val.setStyleSheet(
                "border:1px solid #d5dae1; border-radius:4px; padding:1px 8px; "
                "background:#f6f8fb; font-family:Consolas,monospace; font-size:12px;"
            )
        else:
            self._secs_val.setStyleSheet(
                "border:1px solid #e6e9ee; border-radius:4px; padding:1px 8px; "
                "background:#f6f8fb; color:#b6bfca; font-family:Consolas,monospace; font-size:12px;"
            )

    def _edit_auto_hide_seconds(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        val, ok = QInputDialog.getInt(
            self, "自动消失秒数", "流式输出结束后多少秒自动收起?",
            self._config.auto_hide_seconds, 1, 600,
        )
        if ok:
            self._config.auto_hide_seconds = val
            self._config.save()
            self._update_secs_row()
            self._arm_autohide()  # 秒数改动后按新值重新计时

    def _set_autostart(self, on: bool) -> None:
        self._config.autostart = bool(on)
        self._config.save()
        autostart.set_autostart(bool(on))

    def _set_thinking(self, on: bool) -> None:
        self._config.thinking_enabled = bool(on)
        self._config.save()
        if self.current_mode() == "explain" and self._input.text().strip():
            self.run_current_mode()

    def _set_web_search(self, on: bool) -> None:
        self._config.web_search_enabled = bool(on)
        self._config.save()
        if self.current_mode() == "explain" and self._input.text().strip():
            self.run_current_mode()

    # --- 对外 ------------------------------------------------------------------

    def set_client(self, client: Optional[DeepSeekClient]) -> None:
        self._client = client

    def show_with_text(self, text: str) -> None:
        print(f"[ui] show_with_text: {text[:60]!r}", flush=True)
        self._input.setText(text)
        self._show_at_parked()
        self.run_current_mode()

    def show_empty(self) -> None:
        print("[ui] show_empty", flush=True)
        self._input.clear()
        self._result.clear()
        self._result_buffer = ""
        self._show_at_parked()
        self._arm_autohide()  # 自动模式下,空唤无操作也会计时收起

    def current_mode(self) -> str:
        return "translate" if self._mode_group.checkedId() == 0 else "explain"

    def run_current_mode(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        if self._client is None:
            self._result.clear()
            self._result_buffer = ""
            self._result.setPlainText("未配置 API key。请点「⚙ 设置 → 配置 API key…」。")
            self._arm_autohide()
            return
        mode = self.current_mode()
        print(f"[ui] run_current_mode: mode={mode}", flush=True)
        thinking = mode == "explain" and self._config.thinking_enabled
        web_search = mode == "explain" and self._config.web_search_enabled

        self._stop_event.set()  # 停掉仍在跑的旧请求
        stop_event = threading.Event()  # 本次请求专用的停止事件(绑定给线程)
        self._stop_event = stop_event
        self._run_id += 1
        run_id = self._run_id
        self._result.clear()
        self._result_buffer = ""
        self._streaming = True
        self._btn_stop.show()
        self._autohide_timer.stop()

        worker = threading.Thread(
            target=self._run_worker,
            args=(text, mode, thinking, web_search, stop_event, run_id),
            daemon=True,
        )
        worker.start()

    # --- 工作线程 --------------------------------------------------------------

    def _run_worker(
        self,
        text: str,
        mode: str,
        thinking: bool,
        web_search: bool,
        stop_event: threading.Event,
        run_id: int,
    ) -> None:
        try:
            stop = lambda: stop_event.is_set()  # noqa: E731  绑定本次事件,切换模式时旧线程能真正停止
            on_token = lambda t: self._signals.token.emit(t, run_id)  # noqa: E731
            if mode == "translate":
                self._client.translate(text, thinking=thinking, on_token=on_token, stop=stop)
            else:
                self._client.explain(
                    text, thinking=thinking, web_search=web_search,
                    on_token=on_token, stop=stop,
                )
            self._signals.finished.emit(run_id)
        except Exception as exc:
            self._signals.error.emit(str(exc), run_id)

    # --- 主线程槽 ---------------------------------------------------------------

    def _on_token(self, token: str, run_id: int) -> None:
        if run_id != self._run_id:
            return  # 过期输出丢弃
        self._result_buffer += token
        self._result.moveCursor(QTextCursor.MoveOperation.End)
        self._result.insertPlainText(token)

    def _on_finished(self, run_id: int) -> None:
        if run_id != self._run_id:
            return  # 旧请求的结束信号丢弃
        print(f"[ui] finished buffer_len={len(self._result_buffer)}", flush=True)
        self._streaming = False
        self._btn_stop.hide()
        # 去除 Markdown 格式符号,只留文字
        self._result_buffer = strip_markdown(self._result_buffer)
        self._result.setPlainText(self._result_buffer)
        text = self._input.text().strip()
        if text and self._result_buffer.strip():
            self.result_done.emit(text, self._result_buffer, self.current_mode())
        self._arm_autohide()

    def _on_error(self, message: str, run_id: int) -> None:
        if run_id != self._run_id:
            return
        print(f"[ui] error: {message}", flush=True)
        self._streaming = False
        self._btn_stop.hide()
        self._result_buffer = ""
        self._result.append(f"\n[错误] {message}")
        self._arm_autohide()

    def _on_stop_clicked(self) -> None:
        self._stop_event.set()

    def _on_close_clicked(self) -> None:
        self._stop_event.set()
        self.hide()

    def _on_mode_switch(self) -> None:
        self._config.default_mode = self.current_mode()
        self._config.save()
        self._update_explain_panel()
        if self._input.text().strip():
            self.run_current_mode()

    def _update_explain_panel(self) -> None:
        show = self.current_mode() == "explain"
        self._explain_panel.setVisible(show)

    # --- 自动收起 ---------------------------------------------------------------

    def _arm_autohide(self) -> None:
        """自动模式下,流式输出结束后 N 秒收起;固定驻留模式不自动收起。"""
        self._autohide_timer.stop()
        if self._config.dismiss_mode == "auto" and self._config.auto_hide_seconds > 0:
            self._autohide_timer.start(self._config.auto_hide_seconds * 1000)

    def _on_autohide(self) -> None:
        if self._streaming or self.hasFocus() or self._is_interacting():
            self._arm_autohide()
        else:
            self.hide()

    def _is_interacting(self) -> bool:
        """设置菜单等弹出层打开,或鼠标悬停在弹窗上时,不自动收起。"""
        from PySide6.QtGui import QCursor

        if QApplication.activePopupWidget() is not None:
            return True  # 设置菜单 / 任何弹出层打开
        if self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            return True  # 鼠标悬停在弹窗上(正在阅读/操作)
        return False

    # --- 定位与拖动 -------------------------------------------------------------

    def _show_at_parked(self) -> None:
        if self._config.bar_width and self._config.bar_height:
            self.resize(self._config.bar_width, self._config.bar_height)
        else:
            self.adjustSize()  # 首次:自然紧凑尺寸
        if self._config.bar_x is not None and self._config.bar_y is not None:
            self.move(self._config.bar_x, self._config.bar_y)
        else:
            self._center_top()
        self.show()
        self.raise_()
        self._force_activate()
        print(f"[ui] shown -> isVisible={self.isVisible()} geo={self.geometry()}", flush=True)
        self._input.selectAll()
        self._input.setFocus()

    def _center_top(self) -> None:
        geo = QGuiApplication.primaryScreen().availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + 40
        self.move(x, y)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._resize_timer is None:
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._save_size)
        self._resize_timer.start(300)  # 拖动停止 300ms 后保存,避免拖动时频繁写盘

    def _save_size(self) -> None:
        self._config.bar_width = self.width()
        self._config.bar_height = self.height()
        self._config.save()

    # --- 原生边缘缩放(Windows WM_NCHITTEST) ------------------------------------

    def nativeEvent(self, event_type, message):
        """让无边框窗口像普通窗口那样,左右下边缘与底部两角可拖调大小。"""
        if event_type == b"windows_generic_MSG":
            try:
                addr = int(message)
            except (TypeError, ValueError):
                try:
                    addr = int(message.__int__())
                except Exception:
                    return super().nativeEvent(event_type, message)
            try:
                import ctypes

                msg = ctypes.wintypes.MSG.from_address(addr)
                if msg.message == 0x0084:  # WM_NCHITTEST
                    x = ctypes.c_short(msg.lParam & 0xFFFF).value
                    y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                    return True, self._hit_test(x, y)
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    def _hit_test(self, screen_x: int, screen_y: int) -> int:
        """根据屏幕坐标判断命中区域:边缘/角 -> 对应缩放,顶部条带 -> 移动,内部 -> 正常。"""
        dpr = self.devicePixelRatioF()
        g = self.frameGeometry()
        gx = int(g.x() * dpr)
        gy = int(g.y() * dpr)
        gw = int(g.width() * dpr)
        gh = int(g.height() * dpr)
        lx = screen_x - gx
        ly = screen_y - gy
        if ly < _TOP_MOVE:
            return _HT_CLIENT  # 顶部条带 = 移动区(拖动手柄)
        bottom = ly >= gh - _EDGE
        right = lx >= gw - _EDGE
        left = lx < _EDGE
        if bottom and right:
            return _HT_BOTTOMRIGHT
        if bottom and left:
            return _HT_BOTTOMLEFT
        if right:
            return _HT_RIGHT
        if bottom:
            return _HT_BOTTOM
        if left:
            return _HT_LEFT
        return _HT_CLIENT

    def _save_pos(self) -> None:
        self._config.bar_x = self.x()
        self._config.bar_y = self.y()
        self._config.save()

    def _force_activate(self) -> None:
        """Windows 下尽力让后台进程的窗口获得键盘焦点(Esc / 输入立即可用)。"""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.GetWindowThreadProcessId.argtypes = [
                wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
            ]
            user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.SetForegroundWindow.restype = wintypes.BOOL
            user32.AttachThreadInput.argtypes = [
                wintypes.DWORD, wintypes.DWORD, wintypes.BOOL,
            ]
            user32.AttachThreadInput.restype = wintypes.BOOL
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD

            hwnd = wintypes.HWND(int(self.winId()))
            fg = user32.GetForegroundWindow()
            cur = kernel32.GetCurrentThreadId()
            fg_thread = user32.GetWindowThreadProcessId(fg, None)
            attached = False
            if fg_thread and fg_thread != cur:
                attached = bool(user32.AttachThreadInput(cur, fg_thread, True))
            user32.SetForegroundWindow(hwnd)
            if attached:
                user32.AttachThreadInput(cur, fg_thread, False)
        except Exception:
            pass
        self.activateWindow()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self._save_pos()
            event.accept()

    def keyPressEvent(self, event) -> None:
        if combo_from_qkeyevent(event) == normalize_combo(self._config.close_key):
            self._stop_event.set()
            self.hide()
        else:
            super().keyPressEvent(event)

    def _on_input_changed(self) -> None:
        if not self._streaming:
            self._arm_autohide()  # 自动模式下,打字会重置倒计时
