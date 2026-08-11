"""应用装配:配置 → 首次配置 → DeepSeek 客户端 → 捕获 → 搜索栏 → 历史 → 托盘。"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import autostart, config as config_mod
from .capture import CaptureManager
from .config import Config
from .deepseek_client import DeepSeekClient
from .history import HistoryStore
from .ui.first_run import FirstRunDialog
from .ui.history_window import HistoryWindow
from .ui.search_bar import SearchBar


def _build_tray_icon(enabled: bool = True) -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#2f6fed") if enabled else QColor("#9aa4b0"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, 64, 64, 14, 14)
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setPixelSize(40)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "译")
    painter.end()
    return QIcon(pm)


class Application:
    def __init__(self, app: QApplication):
        self._app = app
        self._config = Config.load()
        self._client = self._make_client()
        self._history = HistoryStore(os.path.join(config_mod.app_dir(), "history.db"))
        self._history_window: HistoryWindow | None = None
        self._search_bar: SearchBar | None = None
        self._capture: CaptureManager | None = None

    def _make_client(self) -> DeepSeekClient | None:
        key = config_mod.load_api_key()
        if key:
            return DeepSeekClient(key, model=self._config.model)
        return None

    def run(self) -> None:
        print("[app] starting, api_key_present=%s" % (self._client is not None), flush=True)
        if self._client is None:
            FirstRunDialog().exec()
            self._client = self._make_client()

        # 开机自启状态与配置对齐
        autostart.set_autostart(self._config.autostart)

        self._search_bar = SearchBar(self._config, self._client)
        self._search_bar.result_done.connect(self._on_result_done)
        self._search_bar.history_requested.connect(self._show_history)
        self._search_bar.configure_key_requested.connect(self._configure_key)
        self._search_bar.shortcut_settings_requested.connect(self._open_shortcut_settings)
        self._search_bar.quit_requested.connect(self._quit)

        def get_clip() -> str:
            return QApplication.clipboard().text()

        self._capture = CaptureManager(
            summon_hotkey=self._config.summon_hotkey,
            copy_hotkey=self._config.copy_hotkey,
            get_clipboard=get_clip,
        )
        self._capture.set_enabled(self._config.capture_enabled)
        self._capture.text_captured.connect(self._search_bar.show_with_text)
        self._capture.summon_requested.connect(self._search_bar.show_empty)
        self._capture.start()
        print("[app] capture started", flush=True)

        self._build_tray()
        print("[app] tray built", flush=True)

    def _build_tray(self) -> None:
        menu = QMenu()
        self._cap_action = menu.addAction("启用捕获")
        self._cap_action.setCheckable(True)
        self._cap_action.setChecked(self._config.capture_enabled)
        self._cap_action.triggered.connect(self._on_capture_enabled)
        menu.addSeparator()
        menu.addAction("显示 / 隐藏搜索栏", self._toggle_bar)
        menu.addAction("历史记录…", self._show_history)
        menu.addAction("配置 API key…", self._configure_key)
        menu.addSeparator()
        menu.addAction("退出", self._quit)

        self._tray = QSystemTrayIcon(_build_tray_icon(self._config.capture_enabled))
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._update_tray_state()
        self._tray.show()

    def _on_capture_enabled(self, on: bool) -> None:
        """捕获开关:托盘勾选 / 搜索栏 ⚙ 开关共用,两处联动同步。"""
        self._config.capture_enabled = bool(on)
        self._config.save()
        if self._capture:
            self._capture.set_enabled(bool(on))
        self._update_tray_state()

    def _update_tray_state(self) -> None:
        on = self._config.capture_enabled
        # 同步托盘勾选(托盘菜单一次性构建,状态变化时需手动刷新)
        if getattr(self, "_cap_action", None) is not None:
            self._cap_action.setChecked(on)
        self._tray.setIcon(_build_tray_icon(on))
        self._tray.setToolTip("DSTranslator" if on else "DSTranslator · 捕获已暂停")

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_bar()

    def _toggle_bar(self) -> None:
        if self._search_bar is None:
            return
        if self._search_bar.isVisible():
            self._search_bar.hide()
        else:
            self._search_bar.show_empty()

    def _on_result_done(self, source: str, result: str, mode: str) -> None:
        try:
            self._history.add(source, result, mode)
            print(f"[history] saved mode={mode} len={len(result)}", flush=True)
        except Exception as exc:
            print(f"[history] 保存失败: {exc}", flush=True)

    def _show_history(self) -> None:
        if self._history_window is None:
            self._history_window = HistoryWindow(self._history)
        self._history_window.show()
        self._history_window.raise_()
        self._history_window.activateWindow()

    def _configure_key(self) -> None:
        dlg = FirstRunDialog()
        if dlg.exec():
            self._client = self._make_client()
            self._search_bar.set_client(self._client)

    def _open_shortcut_settings(self) -> None:
        from .ui.shortcut_settings import ShortcutSettingsDialog

        dlg = ShortcutSettingsDialog(self._config)
        if dlg.exec():
            if dlg.summon_changed():
                self._capture.update_summon_hotkey(self._config.summon_hotkey)
            if dlg.copy_changed():
                self._capture.update_copy_hotkey(self._config.copy_hotkey)
            # 对话框内改动的捕获开关(方案C状态条)同步到捕获与托盘
            self._on_capture_enabled(self._config.capture_enabled)

    def _quit(self) -> None:
        if self._capture:
            self._capture.stop()
        self._history.close()
        self._app.quit()
