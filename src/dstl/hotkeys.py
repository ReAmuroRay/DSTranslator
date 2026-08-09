"""快捷键字符串的规范化、显示与 Qt 事件转换。

内部统一用小写形式存储:如 `ctrl+alt+s`、`esc`、`f1`。
"""
from __future__ import annotations


def normalize_combo(combo: str) -> str:
    """'Ctrl+Alt+S' / 'ctrl + alt + s' -> 'ctrl+alt+s'"""
    if not combo:
        return ""
    parts = []
    for p in combo.lower().split("+"):
        p = p.strip()
        if p:
            parts.append(p)
    return "+".join(parts)


def display_combo(combo: str) -> str:
    """'ctrl+alt+s' -> 'Ctrl+Alt+S'; 'esc' -> 'Esc'"""
    if not combo:
        return ""
    return "+".join(p.capitalize() for p in combo.split("+"))


def combo_from_qkeyevent(event) -> str:
    """从 QKeyEvent 提取规范化快捷键字符串(小写)。"""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence

    mods = []
    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
        mods.append("ctrl")
    if event.modifiers() & Qt.KeyboardModifier.AltModifier:
        mods.append("alt")
    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
        mods.append("shift")
    if event.modifiers() & Qt.KeyboardModifier.MetaModifier:
        mods.append("win")
    key = QKeySequence(event.key()).toString().lower()
    return "+".join(mods + [key]) if key else ""


def is_modifier_key(qkey) -> bool:
    from PySide6.QtCore import Qt

    return qkey in (
        Qt.Key.Key_Control,
        Qt.Key.Key_Alt,
        Qt.Key.Key_Shift,
        Qt.Key.Key_Meta,
    )
