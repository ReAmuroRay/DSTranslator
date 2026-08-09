"""捕获与唤起。

- 捕获:唯一为剪贴板复制。监听 QClipboard 的 dataChanged,用户在任意应用中
  Ctrl+C 后读取剪贴板内容。不采用全局热键/鼠标组合抓取,避免与其他应用冲突。
- 唤起:一个全局热键(默认 Ctrl+Alt+S)空召搜索栏。
监听在后台线程,通过 Qt 信号跨线程回主线程;日志 flush 便于实时排查。
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from pynput import keyboard
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

DEDUP_SECONDS = 2.0


def normalize_hotkey(hotkey: str) -> str:
    """把用户友好的格式转成 pynput 可解析格式。

    pynput 的 GlobalHotKeys 要求修饰键/特殊键带尖括号:`<ctrl>+<alt>+t`。
    单个字符(字母/数字)保持原样;已带尖括号的保持不变。
    """
    if not hotkey:
        return hotkey
    parts = []
    for p in hotkey.split("+"):
        p = p.strip()
        if not p:
            continue
        if p.startswith("<") and p.endswith(">"):
            parts.append(p)
        elif len(p) == 1:
            parts.append(p)
        else:
            parts.append(f"<{p}>")
    return "+".join(parts)


class CaptureManager(QObject):
    text_captured = Signal(str)   # 剪贴板捕获到文本
    summon_requested = Signal()   # 唤起键按下

    def __init__(
        self,
        summon_hotkey: str = "ctrl+alt+s",
        get_clipboard: Optional[Callable[[], str]] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._summon_hotkey = summon_hotkey
        self._get_clipboard = get_clipboard
        self._last_text = ""
        self._last_ts = 0.0
        self._hotkey_listener = None

    # --- 对外 -----------------------------------------------------------------

    def start(self) -> None:
        # 以当前剪贴板内容为基线,避免启动时旧内容自动触发
        if self._get_clipboard:
            self._last_text = (self._get_clipboard() or "").strip()
        print(f"[capture] start: summon_hotkey={self._summon_hotkey!r}", flush=True)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.dataChanged.connect(self._on_clipboard_changed)
        if self._summon_hotkey:
            threading.Thread(target=self._run_hotkey_listener, daemon=True).start()

    def stop(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            try:
                clipboard.dataChanged.disconnect(self._on_clipboard_changed)
            except (TypeError, RuntimeError):
                pass

    # --- 剪贴板监听(dataChanged)-------------------------------------------------

    def _on_clipboard_changed(self) -> None:
        # dataChanged 在数据就绪前发出,延迟一点再读
        QTimer.singleShot(30, self._read_clipboard)

    def _read_clipboard(self) -> None:
        if not self._get_clipboard:
            return
        text = self._get_clipboard()
        if text:
            self._emit_if_new(text)

    # --- 唤起热键 -----------------------------------------------------------------

    def update_summon_hotkey(self, hotkey: str) -> None:
        """唤起键变更后热更新全局监听。"""
        self._summon_hotkey = hotkey
        if self._hotkey_listener is not None:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None
        if hotkey:
            threading.Thread(target=self._run_hotkey_listener, daemon=True).start()

    def _run_hotkey_listener(self) -> None:
        if not self._summon_hotkey:
            return
        bindings = {normalize_hotkey(self._summon_hotkey): lambda: self.summon_requested.emit()}
        print(f"[capture] hotkey listener bindings: {bindings}", flush=True)
        try:
            listener = keyboard.GlobalHotKeys(bindings)
            self._hotkey_listener = listener
            with listener:
                print("[capture] hotkey listener started", flush=True)
                listener.join()
        except Exception as exc:
            print(f"[capture] 热键监听失败: {exc}", flush=True)

    # --- 去重/空值过滤 ------------------------------------------------------------

    def _emit_if_new(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        now = time.time()
        if text == self._last_text and now - self._last_ts < DEDUP_SECONDS:
            return
        self._last_text = text
        self._last_ts = now
        print(f"[capture] EMIT(clipboard): {text[:60]!r}", flush=True)
        self.text_captured.emit(text)
