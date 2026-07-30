import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "TechGrowthConnector"


def launch_command() -> str:
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return f'"{executable}"'
    return f'"{executable}" -m techgrowth_connector'


def is_startup_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return value == launch_command()
    except FileNotFoundError:
        return False


def set_startup_enabled(enabled: bool) -> None:
    if sys.platform != "win32":
        raise RuntimeError("startup registration is only available on Windows")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass

