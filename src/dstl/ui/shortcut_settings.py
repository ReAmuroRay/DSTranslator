"""快捷键设置窗口。

点「更改」进入录制态,直接按下新组合键生效;Esc 取消录制。
校验:唤起键需含修饰键;两个快捷键不能重复。
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
)

from ..config import Config
from ..hotkeys import combo_from_qkeyevent, display_combo, is_modifier_key, normalize_combo

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
        self._summon = config.summon_hotkey
        self._close = config.close_key
        self._recording: str | None = None  # "summon" | "close" | None
        self._rows: dict[str, tuple[QLabel, QPushButton]] = {}
        self.setWindowTitle("快捷键设置")
        self.setMinimumWidth(440)
        self._build_ui()

    def summon_changed(self) -> bool:
        return self._summon != self._original_summon

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(QLabel("点「更改」后,直接按下新的组合键;Esc 取消。"))

        self._add_row("summon", "唤起搜索栏", self._summon)
        self._add_row("close", "关闭搜索栏", self._close)

        tip = QLabel(
            "规则:\n"
            "· 唤起键需含 Ctrl / Alt / Win / Shift 修饰键;\n"
            "· 关闭键可为单键(默认 Esc);\n"
            "· 两个快捷键不能相同。"
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

    def _add_row(self, rid: str, name: str, combo: str) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel(name))
        row.addStretch(1)
        key_lbl = QLabel(display_combo(combo))
        key_lbl.setStyleSheet(_KEY_STYLE)
        row.addWidget(key_lbl)
        btn = QPushButton("更改")
        btn.clicked.connect(lambda: self._start_record(rid))
        row.addWidget(btn)
        self._rows[rid] = (key_lbl, btn)
        self.layout().addLayout(row)

    # --- 录制 ------------------------------------------------------------------

    def _start_record(self, rid: str) -> None:
        self._recording = rid
        lbl, _ = self._rows[rid]
        lbl.setText("按下新的组合键…")
        lbl.setStyleSheet(_RECORD_STYLE)

    def _cancel_record(self) -> None:
        if self._recording is None:
            return
        rid = self._recording
        self._recording = None
        self._refresh_row(rid)

    def _refresh_row(self, rid: str) -> None:
        val = self._summon if rid == "summon" else self._close
        lbl, _ = self._rows[rid]
        lbl.setText(display_combo(val))
        lbl.setStyleSheet(_KEY_STYLE)

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
        if rid == "summon":
            has_mod = any(m in combo for m in ("ctrl", "alt", "shift", "win"))
            if not has_mod:
                QMessageBox.warning(self, "提示", "唤起键需包含 Ctrl / Alt / Win / Shift 修饰键。")
                return
            other = self._close
        else:
            other = self._summon
        if combo == other:
            QMessageBox.warning(self, "提示", "该快捷键已在其他功能使用。")
            return
        if rid == "summon":
            self._summon = combo
        else:
            self._close = combo
        self._recording = None
        self._refresh_row(rid)

    def _on_reset(self) -> None:
        self._summon = "ctrl+alt+s"
        self._close = "esc"
        self._recording = None
        for rid in self._rows:
            self._refresh_row(rid)

    def _on_done(self) -> None:
        self._config.summon_hotkey = self._summon
        self._config.close_key = self._close
        self._config.save()
        self.accept()
