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

print("\nALL SMOKE TESTS PASSED")
