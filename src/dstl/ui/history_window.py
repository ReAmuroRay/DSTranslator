"""历史记录管理窗口:列表 / 搜索 / 删除 / 复制 / 导出。"""
from __future__ import annotations

import datetime

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..history import HistoryStore


class HistoryWindow(QWidget):
    def __init__(self, store: HistoryStore, parent=None):
        super().__init__(parent)
        self._store = store
        self._ids: list[int] = []
        self.setWindowTitle("DSTranslator - 搜索记录")
        self.resize(760, 520)
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("搜索:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("按源文本或结果过滤…")
        self._search.textChanged.connect(lambda _t: self.reload())
        bar.addWidget(self._search, 1)
        bar.addWidget(QLabel("模式:"))
        self._mode = QComboBox()
        self._mode.addItem("全部", None)
        self._mode.addItem("翻译", "translate")
        self._mode.addItem("解释", "explain")
        self._mode.currentIndexChanged.connect(lambda _i: self.reload())
        bar.addWidget(self._mode)
        root.addLayout(bar)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["时间", "模式", "源文本", "结果"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self._table, 1)

        btns = QHBoxLayout()
        b_copy = QPushButton("复制结果")
        b_copy.clicked.connect(self._copy_selected)
        b_del = QPushButton("删除选中")
        b_del.clicked.connect(self._delete_selected)
        b_clear = QPushButton("清空")
        b_clear.clicked.connect(self._clear_all)
        b_export = QPushButton("导出 JSON…")
        b_export.clicked.connect(self._export)
        b_close = QPushButton("关闭")
        b_close.clicked.connect(self.close)
        for b in (b_copy, b_del, b_clear, b_export):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(b_close)
        root.addLayout(btns)

    def reload(self) -> None:
        query = self._search.text().strip()
        mode = self._mode.currentData()
        rows = self._store.search(query=query, mode=mode)
        self._ids = [row["id"] for row in rows]
        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            ts = datetime.datetime.fromtimestamp(row["ts"]).strftime("%Y-%m-%d %H:%M:%S")
            self._table.setItem(r, 0, QTableWidgetItem(ts))
            self._table.setItem(r, 1, QTableWidgetItem("翻译" if row["mode"] == "translate" else "解释"))
            self._table.setItem(r, 2, QTableWidgetItem(row["source"]))
            self._table.setItem(r, 3, QTableWidgetItem(row["result"]))

    def _selected_ids(self) -> list[int]:
        return [self._ids[idx.row()] for idx in self._table.selectionModel().selectedRows()]

    def _delete_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        self._store.delete(ids)
        self.reload()

    def _clear_all(self) -> None:
        if (
            QMessageBox.question(self, "清空", "确定删除所有记录?")
            == QMessageBox.StandardButton.Yes
        ):
            self._store.clear()
            self.reload()

    def _copy_selected(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        result = self._table.item(rows[0].row(), 3).text()
        QApplication.clipboard().setText(result)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出记录", "records.json", "JSON (*.json)")
        if path:
            self._store.export_json(path)
