"""首次启动 / 重新配置:输入 DeepSeek API key 的对话框。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..config import save_api_key

KEY_URL = "https://platform.deepseek.com/api_keys"


class FirstRunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DSTranslator - 配置 API key")
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                "翻译和解释由 DeepSeek API 驱动,需要你的 API key。\n"
                "Key 会用 Windows DPAPI 加密保存在本机,不会上传到其他服务。"
            )
        )
        self._key = QLineEdit()
        self._key.setEchoMode(QLineEdit.EchoMode.Password)
        self._key.setPlaceholderText("sk-…")
        self._key.returnPressed.connect(self._on_ok)
        root.addWidget(self._key)

        link = QLabel(f'<a href="{KEY_URL}">没有 key?去 DeepSeek 平台创建</a>')
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(link)

        btns = QHBoxLayout()
        b_ok = QPushButton("保存")
        b_ok.clicked.connect(self._on_ok)
        b_cancel = QPushButton("取消")
        b_cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(b_ok)
        btns.addWidget(b_cancel)
        root.addLayout(btns)

    def _on_ok(self) -> None:
        key = self._key.text().strip()
        if not key:
            QMessageBox.warning(self, "提示", "请输入 API key。")
            return
        save_api_key(key)
        self.accept()
