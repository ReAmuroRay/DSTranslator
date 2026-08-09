r"""配置与 API key 存储。

- `config.json` 存普通设置(明文)。
- `api_key.dat` 用 Windows DPAPI(CryptProtectData)加密,只有当前 Windows
  用户能解开;换用户或重装系统后需重新输入。
- 数据目录:打包(便携版)后优先用 exe 旁 `data/` 文件夹,拷走整个目录即带数据;
  位置不可写(如 Program Files)或源码运行时回退到 `%APPDATA%\DSTranslator\`。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Optional

import win32crypt

APP_DIR_NAME = "DSTranslator"


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        # 便携模式:数据放 exe 旁 data/;不可写则回退
        data_dir = os.path.join(os.path.dirname(sys.executable), "data")
        try:
            os.makedirs(data_dir, exist_ok=True)
            probe = os.path.join(data_dir, ".write_test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            return data_dir
        except Exception:
            pass
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def _config_path() -> str:
    return os.path.join(app_dir(), "config.json")


def _key_path() -> str:
    return os.path.join(app_dir(), "api_key.dat")


# --- DPAPI 密钥加解密 ---------------------------------------------------------


def save_api_key(plaintext: str) -> None:
    """用当前 Windows 用户身份加密 API key 并写入 api_key.dat。"""
    blob = win32crypt.CryptProtectData(
        plaintext.strip().encode("utf-16-le"), "DSTranslator API key", None, None, None, 0
    )
    with open(_key_path(), "wb") as f:
        f.write(bytes(blob))


def load_api_key() -> Optional[str]:
    """读取并解密 API key;不存在或解密失败返回 None。"""
    if not os.path.exists(_key_path()):
        return None
    try:
        with open(_key_path(), "rb") as f:
            blob = f.read()
        _, data = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        key = data.decode("utf-16-le").strip()
        return key or None
    except Exception:
        return None


# --- 配置 -----------------------------------------------------------------------


@dataclass
class Config:
    model: str = "deepseek-v4-flash"
    default_mode: str = "translate"        # translate | explain
    thinking_enabled: bool = False         # 深度解释(思维模式)
    web_search_enabled: bool = False       # 联网解释
    dismiss_mode: str = "pin"              # pin(固定驻留) | auto(自动消失)
    auto_hide_seconds: int = 10            # 自动模式下,流式输出结束后多少秒消失
    summon_hotkey: str = "ctrl+alt+s"      # 全局热键(空召搜索栏)
    close_key: str = "esc"                 # 关闭搜索栏的键(弹窗有焦点时生效)
    autostart: bool = False
    bar_x: Optional[int] = None
    bar_y: Optional[int] = None
    bar_width: Optional[int] = None
    bar_height: Optional[int] = None

    def save(self) -> None:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if os.path.exists(_config_path()):
            try:
                with open(_config_path(), "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
            except Exception:
                pass
        return cfg
