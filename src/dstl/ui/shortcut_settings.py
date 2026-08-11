"""快捷键设置窗口。

点「更改」进入录制态,直接按下新组合键生效;Esc 取消录制。
校验:唤起键与复制触发键需含修饰键;三个快捷键不能重复。
复制触发键:默认 Ctrl+C 显示「双击触发」,自定义组合键显示「单击触发」。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..hotkeys import combo_from_qkeyevent, display_combo, is_modifier_key, normalize_combo
from .search_bar import _ToggleSwitch

_KEY_STYLE = (
    "border:1px solid #d5dae1; border-radius:6px; padding:4px 10px; "
    "background:#f6f8fb; font-family:Consolas,monospace;"
)
_RECORD_STYLE = (
    "border:1px solid #f2c94c; border-radius:6px; padding:4px 10px; "
    "background:#fff8e6; color:#b7791f; font-family:Consolas,monospace;"
)


class ShortcutSettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config
        self._original_summon = config.summon_hotkey
        self._original_copy = config.copy_hotkey
        self._summon = config.summon_hotkey
        self._copy = config.copy_hotkey
        self._close = config.close_key
        self._capture_enabled = config.capture_enabled
        self._recording: str | None = None  # "summon" | "copy" | "close" | None
        self._rows: dict[str, tuple[QLabel, QPushButton]] = {}
        self._badge: QLabel | None = None
        self.setWindowTitle("快捷键设置")
        self.setMinimumWidth(460)
        self._build_ui()

    def summon_changed(self) -> bool:
        return self._summon != self._original_summon

    def copy_changed(self) -> bool:
        return self._copy != self._original_copy

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(QLabel("点「更改」后,直接按下新的组合键;Esc 取消。"))

        # 捕获状态条(方案C):当前捕获状态 + 触发方式 + 开关,与托盘勾选联动
        self._cap_strip = QWidget()
        cap_lay = QHBoxLayout(self._cap_strip)
        cap_lay.setContentsMargins(10, 8, 10, 8)
        cap_lay.setSpacing(8)
        self._cap_dot = QLabel()
        self._cap_dot.setFixedSize(9, 9)
        self._cap_text = QLabel()
        self._cap_switch = _ToggleSwitch(self._capture_enabled)
        self._cap_switch.toggled.connect(self._on_capture_toggled)
        cap_lay.addWidget(self._cap_dot)
        cap_lay.addWidget(self._cap_text, 1)
        cap_lay.addWidget(self._cap_switch)
        root.addWidget(self._cap_strip)
        self._update_capture_strip()

        self._add_row("summon", "唤起搜索栏", self._summon)
        self._add_row("copy", "复制触发键", self._copy, badge=True)
        self._add_row("close", "关闭搜索栏", self._close)

        tip = QLabel(
            "规则:\n"
            "· 唤起键与复制触发键需含 Ctrl / Alt / Win / Shift 修饰键;\n"
            "· 关闭键可为单键(默认 Esc);\n"
            "· 三个快捷键不能相同;\n"
            "· 复制触发键默认 Ctrl+C 双击触发,改其他组合键后单击触发;\n"
            "· 关闭「启用捕获」后,复制与唤起键都不再自动弹窗(托盘手动打开仍可用)。"
        )
        tip.setStyleSheet("color:#4b5563; font-size:12px;")
        root.addWidget(tip)

        btns = QHBoxLayout()
        b_reset = QPushButton("恢复默认")
        b_reset.clicked.connect(self._on_reset)
        btns.addWidget(b_reset)
        btns.addStretch(1)
        b_cancel = QPushButton("取消")
        b_cancel.clicked.connect(self.reject)
        b_ok = QPushButton("完成")
        b_ok.setDefault(True)
        b_ok.clicked.connect(self._on_done)
        btns.addWidget(b_cancel)
        btns.addWidget(b_ok)
        root.addLayout(btns)

    def _add_row(self, rid: str, name: str, combo: str, badge: bool = False) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel(name))
        row.addStretch(1)
        key_lbl = QLabel(display_combo(combo))
        key_lbl.setStyleSheet(_KEY_STYLE)
        row.addWidget(key_lbl)
        if badge:
            self._badge = QLabel()
            row.addWidget(self._badge)
        btn = QPushButton("更改")
        btn.clicked.connect(lambda: self._start_record(rid))
        row.addWidget(btn)
        self._rows[rid] = (key_lbl, btn)
        self.layout().addLayout(row)
        if badge:
            self._update_badge()

    # --- 录制 ------------------------------------------------------------------

    def _start_record(self, rid: str) -> None:
        self._recording = rid
        lbl, _ = self._rows[rid]
        lbl.setText("按下新的组合键…")
        lbl.setStyleSheet(_RECORD_STYLE)

    def _cancel_record(self) -> None:
        if self._recording is None:
            return
        self._recording = None
        self._refresh_row()

    def _refresh_row(self) -> None:
        for rid, (lbl, _) in self._rows.items():
            lbl.setText(display_combo(self._value_for(rid)))
            lbl.setStyleSheet(_KEY_STYLE)
        self._update_badge()
        self._update_capture_strip()  # 复制键变了,状态条触发方式提示跟着变

    # --- 捕获状态条(方案C)---------------------------------------------------------

    def _capture_hint(self) -> str:
        if self._copy == "ctrl+c":
            return "双击 Ctrl+C 翻译"
        return f"单击 {display_combo(self._copy)} 翻译"

    def _update_capture_strip(self) -> None:
        on = self._capture_enabled
        if on:
            text, color, bg = f"捕获中 · {self._capture_hint()}", "#2f6fed", "#f0f6ff"
        else:
            text, color, bg = "捕获已暂停", "#8a919c", "#f6f8fb"
        self._cap_text.setText(text)
        self._cap_text.setStyleSheet(f"font-size:12.5px; color:{color};")
        self._cap_dot.setStyleSheet(f"background:{color}; border-radius:5px;")
        self._cap_strip.setStyleSheet(f"background:{bg}; border:1px solid #e6e9ee; border-radius:8px;")

    def _on_capture_toggled(self, on: bool) -> None:
        self._capture_enabled = bool(on)
        self._update_capture_strip()

    def _value_for(self, rid: str) -> str:
        return {"summon": self._summon, "copy": self._copy, "close": self._close}[rid]

    def _update_badge(self) -> None:
        if self._badge is None:
            return
        if self._copy == "ctrl+c":
            self._badge.setText("双击触发")
            self._badge.setStyleSheet(
                "color:#2f6fed; font-size:11px; font-weight:600; "
                "border:1px solid rgba(47,111,237,.4); border-radius:999px; padding:2px 8px;"
            )
        else:
            self._badge.setText("单击触发")
            self._badge.setStyleSheet(
                "color:#15803d; font-size:11px; font-weight:600; "
                "border:1px solid rgba(21,128,61,.4); border-radius:999px; padding:2px 8px;"
            )

    def keyPressEvent(self, event) -> None:
        if self._recording is None:
            return super().keyPressEvent(event)
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_record()
            return
        if is_modifier_key(event.key()):
            return  # 等待主键
        combo = normalize_combo(combo_from_qkeyevent(event))
        if not combo:
            return
        rid = self._recording
        if rid in ("summon", "copy"):
            has_mod = any(m in combo for m in ("ctrl", "alt", "shift", "win"))
            if not has_mod:
                QMessageBox.warning(self, "提示", "该快捷键需包含 Ctrl / Alt / Win / Shift 修饰键。")
                return
        others = {k: self._value_for(k) for k in ("summon", "copy", "close") if k != rid}
        if combo in others.values():
            QMessageBox.warning(self, "提示", "该快捷键已在其他功能使用。")
            return
        if rid == "summon":
            self._summon = combo
        elif rid == "copy":
            self._copy = combo
        else:
            self._close = combo
        self._recording = None
        self._refresh_row()

    def _on_reset(self) -> None:
        self._summon = "ctrl+alt+s"
        self._copy = "ctrl+c"
        self._close = "esc"
        self._capture_enabled = True
        self._recording = None
        self._cap_switch.setChecked(True)
        self._refresh_row()

    def _on_done(self) -> None:
        self._config.summon_hotkey = self._summon
        self._config.copy_hotkey = self._copy
        self._config.close_key = self._close
        self._config.capture_enabled = self._capture_enabled
        self._config.save()
        self.accept()
