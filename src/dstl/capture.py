"""捕获与唤起。

- 捕获:由「复制触发键」触发——默认 Ctrl+C 需 500ms 内连按两次(双击),自定义组合键
  单击即触发。触发后读剪贴板内容。内容来源始终是剪贴板;触发通过按键识别。
- 唤起:一个全局热键(默认 Ctrl+Alt+S)空召搜索栏。
- 捕获开关:enabled=False 时,复制触发与唤起都不响应(不弹窗);手动托盘调出不受此管。
- 剪贴板 dataChanged 不再直接触发,只作为双击的"剪贴板确实刷新过"门控标记。

实现说明:用**单个常驻 pynput Listener** 做全局按键监听,用 pynput `HotKey` 做组合匹配
(纯 Python,不触碰 Win32 布局)。启动时在主线程同步构造监听器(此时 Qt 事件循环未跑),
避免事件循环运行期间构造 `KeyTranslator`/`MapVirtualKeyEx` 死锁;改热键只换 HotKey 对象,
不重建监听器。

监听回调在 pynput 后台线程,通过 Qt 信号跨线程回主线程;日志 flush 便于实时排查。
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from pynput import keyboard
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

DOUBLE_TAP_WINDOW = 0.5  # 秒:默认 Ctrl+C 两次按下的间隔上限


def normalize_hotkey(hotkey: str) -> str:
    """把用户友好的格式转成 pynput 可解析格式。

    pynput 的 HotKey/GlobalHotKeys 要求修饰键/特殊键带尖括号:`<ctrl>+<alt>+t`。
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
    text_captured = Signal(str)   # 捕获触发后,剪贴板读到的文本
    summon_requested = Signal()   # 唤起键按下
    copy_triggered = Signal()     # 复制触发键判定通过(双击/自定义单击)

    def __init__(
        self,
        summon_hotkey: str = "ctrl+alt+s",
        copy_hotkey: str = "ctrl+c",
        enabled: bool = True,
        get_clipboard: Optional[Callable[[], str]] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._summon_hotkey = summon_hotkey
        self._copy_hotkey = copy_hotkey
        self._enabled = bool(enabled)
        self._get_clipboard = get_clipboard
        self._listener: Optional[keyboard.Listener] = None
        self._hk_summon: Optional[keyboard.HotKey] = None
        self._hk_copy: Optional[keyboard.HotKey] = None
        # 双击状态(pynput 回调线程内访问;跨线程 bool/float 读写由 GIL 保证原子)
        self._last_copy_press = 0.0
        self._clipboard_refreshed = False

        self.copy_triggered.connect(self._on_copy_triggered)

    # --- 对外 -----------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, on: bool) -> None:
        on = bool(on)
        if on == self._enabled:
            return
        self._enabled = on
        print(f"[capture] enabled={on}", flush=True)
        if on:
            # 重新启用:清掉双击计时与刷新标记,避免旧剪贴板内容误触发
            self._last_copy_press = 0.0
            self._clipboard_refreshed = False

    def start(self) -> None:
        """启动单一全局键盘监听。必须在 Qt 事件循环启动前调用(主线程构造安全)。"""
        print(
            f"[capture] start: summon_hotkey={self._summon_hotkey!r} "
            f"copy_hotkey={self._copy_hotkey!r} enabled={self._enabled}",
            flush=True,
        )
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.dataChanged.connect(self._on_clipboard_changed)
        self._rebuild_hotkeys()
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        print("[capture] listener started", flush=True)

    def stop(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            try:
                clipboard.dataChanged.disconnect(self._on_clipboard_changed)
            except (TypeError, RuntimeError):
                pass
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def update_summon_hotkey(self, hotkey: str) -> None:
        """唤起键变更:只换 HotKey 对象,不重建全局监听。"""
        self._summon_hotkey = hotkey
        self._rebuild_hotkeys()

    def update_copy_hotkey(self, hotkey: str) -> None:
        """复制触发键变更:只换 HotKey 对象,并清掉双击状态。"""
        self._copy_hotkey = hotkey
        self._last_copy_press = 0.0
        self._clipboard_refreshed = False
        self._rebuild_hotkeys()

    # --- 组合匹配(单一监听 + 纯 Python HotKey)----------------------------------

    def _rebuild_hotkeys(self) -> None:
        self._hk_summon = self._make_hotkey(self._summon_hotkey, self._on_summon_press)
        self._hk_copy = self._make_hotkey(self._copy_hotkey, self._on_copy_press)

    @staticmethod
    def _make_hotkey(hotkey: str, callback: Callable[[], None]) -> Optional[keyboard.HotKey]:
        if not hotkey:
            return None
        try:
            keys = keyboard.HotKey.parse(normalize_hotkey(hotkey))
        except Exception as exc:
            print(f"[capture] 热键解析失败 {hotkey!r}: {exc}", flush=True)
            return None
        return keyboard.HotKey(keys, callback)

    def _on_press(self, key) -> None:
        canonical = self._listener.canonical(key) if self._listener is not None else key
        if self._hk_summon is not None:
            self._hk_summon.press(canonical)
        if self._hk_copy is not None:
            self._hk_copy.press(canonical)

    def _on_release(self, key) -> None:
        canonical = self._listener.canonical(key) if self._listener is not None else key
        if self._hk_summon is not None:
            self._hk_summon.release(canonical)
        if self._hk_copy is not None:
            self._hk_copy.release(canonical)

    # --- 剪贴板监听(dataChanged):仅作双击门控,不直接触发 -----------------------

    def _on_clipboard_changed(self) -> None:
        # dataChanged 在数据就绪前发出,但这里只置标记,不读内容
        self._clipboard_refreshed = True

    # --- 唤起 / 复制触发键回调(pynput 线程)---------------------------------------

    def _on_summon_press(self) -> None:
        if not self._enabled:
            return
        self.summon_requested.emit()

    def _on_copy_press(self) -> None:
        """复制触发键按下。

        默认 Ctrl+C:需 500ms 内连按两次,且期间剪贴板确实刷新过才触发。
        自定义组合键:单击即触发。
        """
        if not self._enabled:
            return
        if self._copy_hotkey == "ctrl+c":
            now = time.time()
            if now - self._last_copy_press <= DOUBLE_TAP_WINDOW:
                # 双击达成
                self._last_copy_press = 0.0
                if self._clipboard_refreshed:
                    self._clipboard_refreshed = False
                    print("[capture] DOUBLE-TAP trigger", flush=True)
                    self.copy_triggered.emit()
                else:
                    print("[capture] DOUBLE-TAP ignored: clipboard not refreshed", flush=True)
            else:
                # 第一击:记时,等待第二击
                self._last_copy_press = now
                self._clipboard_refreshed = False
        else:
            # 自定义组合键:单击即触发
            print(f"[capture] COPY-HOTKEY single trigger: {self._copy_hotkey}", flush=True)
            self.copy_triggered.emit()

    # --- 触发后读剪贴板(主线程) ---------------------------------------------------

    def _on_copy_triggered(self) -> None:
        # 按键事件先于复制完成,延迟一点再读
        QTimer.singleShot(30, self._read_clipboard_for_trigger)

    def _read_clipboard_for_trigger(self) -> None:
        if not self._enabled or not self._get_clipboard:
            return
        text = self._get_clipboard()
        text = (text or "").strip()
        if text:
            print(f"[capture] EMIT(clipboard): {text[:60]!r}", flush=True)
            # 双击/单击是显式"翻译这段"手势,绕开去重,连续复制相同文本也触发
            self.text_captured.emit(text)
