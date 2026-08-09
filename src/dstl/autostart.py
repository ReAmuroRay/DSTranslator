"""开机自启(注册表 HKCU Run 键)。"""
from __future__ import annotations

import os
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "DSTranslator"


def _command() -> str:
    if getattr(sys, "frozen", False):
        # 打包后:开机自启直接指向 exe
        return f'"{sys.executable}"'
    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{sys.executable}" "{main_py}"'


def set_autostart(enabled: bool) -> None:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
    try:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)


def is_enabled() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE)
    except OSError:
        return False
    try:
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
    finally:
        winreg.CloseKey(key)
