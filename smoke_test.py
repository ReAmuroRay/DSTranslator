"""无 GUI 冒烟测试:DPAPI 加解密、配置读写、历史库、客户端实例化、UI 构造。

用法:`.venv\\Scripts\\python smoke_test.py`
注意:会把 APPDATA 重定向到临时目录,不会动真实用户数据。
"""
import os
import sys
import tempfile

# 使 src/ 下的 dstl 可导入
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

tmp = tempfile.mkdtemp(prefix="dstl_smoke_")
os.environ["APPDATA"] = tmp

# --- config:DPAPI 加解密往返 ---
import dstl.config as cfg

KEY = "sk-abcdef1234567890"
cfg.save_api_key(KEY)
assert cfg.load_api_key() == KEY, "DPAPI round-trip failed"
print("[ok] config: DPAPI round-trip")

# --- config:读写 ---
c = cfg.Config()
c.thinking_enabled = True
c.web_search_enabled = True
c.save()
c2 = cfg.Config.load()
assert c2.thinking_enabled is True
assert c2.web_search_enabled is True
assert c2.model == "deepseek-v4-flash"
assert c2.capture_enabled is True
assert c2.copy_hotkey == "ctrl+c"
print("[ok] config: save/load")

# --- history:增查删导出清空 ---
from dstl.history import HistoryStore

db = os.path.join(tmp, "history.db")
h = HistoryStore(db)
h.add("Hello", "你好", "translate")
h.add("epistemic", "关于认识的;认识论的", "explain")
assert len(h.search()) == 2
assert len(h.search(query="epistemic")) == 1
r = h.search(mode="explain")
assert len(r) == 1 and r[0]["mode"] == "explain"
h.delete([r[0]["id"]])
assert len(h.search()) == 1
h.export_json(os.path.join(tmp, "out.json"))
assert os.path.exists(os.path.join(tmp, "out.json"))
h.clear()
assert len(h.search()) == 0
h.close()
print("[ok] history: add/search/delete/export/clear")

# --- deepseek_client:实例化(不发请求) ---
from dstl.deepseek_client import DeepSeekClient

cli = DeepSeekClient("sk-x", model="deepseek-v4-flash")
assert cli.model == "deepseek-v4-flash"
print("[ok] deepseek_client: import/instantiate")

# --- autostart:只读检查注册表 ---
import dstl.autostart as auto

auto.is_enabled()
print("[ok] autostart: is_enabled() read")

# --- UI:PySide6 导入 + SearchBar 构造(不显示) ---
from PySide6.QtWidgets import QApplication

from dstl.ui.search_bar import SearchBar

_qapp = QApplication.instance() or QApplication(sys.argv)
bar = SearchBar(cfg.Config())
assert bar is not None
print("[ok] pyside6: SearchBar constructs")

# --- UI:快捷键设置窗构造 + 复制键徽标逻辑 ---
from dstl.ui.shortcut_settings import ShortcutSettingsDialog

_sc = cfg.Config()
_dlg = ShortcutSettingsDialog(_sc)
assert not _dlg.copy_changed()
assert _dlg._badge is not None and _dlg._badge.text() == "双击触发"
assert _dlg._capture_enabled is True
assert _dlg._cap_switch.isChecked() is True
assert "捕获中" in _dlg._cap_text.text()
_dlg._copy = "ctrl+shift+c"
_dlg._refresh_row()  # 模拟录制新复制键后统一刷新(徽标 + 状态条)
assert _dlg._badge.text() == "单击触发"
assert _dlg.copy_changed()
assert "单击" in _dlg._cap_text.text(), "capture hint should reflect custom copy key"
_dlg._on_capture_toggled(False)
assert _dlg._capture_enabled is False
assert _dlg._cap_text.text() == "捕获已暂停"
_dlg._on_done()
assert _sc.capture_enabled is False, "done should persist capture switch"
_dlg._on_reset()
assert _dlg._copy == "ctrl+c" and _dlg._badge.text() == "双击触发"
assert _dlg._capture_enabled is True
print("[ok] pyside6: ShortcutSettingsDialog constructs + copy badge + capture strip")

# --- capture:复制触发键 双击/单击 逻辑(不启真实键盘钩子,直接调回调) ---
from PySide6.QtTest import QTest

from dstl.capture import CaptureManager

_captured: list[str] = []
_cm = CaptureManager(get_clipboard=lambda: "  hello world  ")
_cm.text_captured.connect(_captured.append)


def _reset_cm() -> None:
    _cm._last_copy_press = 0.0
    _cm._clipboard_refreshed = False
    _captured.clear()


# 单击 Ctrl+C 不触发
_reset_cm()
_cm._on_copy_press()
QTest.qWait(60)
assert _captured == [], "single ctrl+c should not trigger"

# 双击 + 剪贴板刷新 → 触发
_reset_cm()
_cm._on_copy_press()              # 第一击
_cm._clipboard_refreshed = True   # 模拟第一击把文字复制进剪贴板
_cm._on_copy_press()              # 第二击(窗口内)
QTest.qWait(60)
assert _captured == ["hello world"], f"double-tap should trigger, got {_captured}"

# 双击但剪贴板没刷新(没选中文字就双击)→ 不触发
_reset_cm()
_cm._on_copy_press()
_cm._on_copy_press()
QTest.qWait(60)
assert _captured == [], "double-tap without clipboard refresh should not trigger"

# 捕获开关关闭 → 不触发
_reset_cm()
_cm.set_enabled(False)
_cm._on_copy_press()
_cm._clipboard_refreshed = True
_cm._on_copy_press()
QTest.qWait(60)
assert _captured == [], "disabled capture should not trigger"
_cm.set_enabled(True)

# 自定义复制键:单击即触发
_reset_cm()
_cm._copy_hotkey = "ctrl+shift+c"
_cm._on_copy_press()
QTest.qWait(60)
assert _captured == ["hello world"], f"custom hotkey single press should trigger, got {_captured}"

# 切回默认:单击不触发
_reset_cm()
_cm._copy_hotkey = "ctrl+c"
_cm._on_copy_press()
QTest.qWait(60)
assert _captured == [], "single ctrl+c should not trigger after switch back"

print("[ok] capture: double-tap / custom-single / refresh-gate / switch")

print("\nALL SMOKE TESTS PASSED")
