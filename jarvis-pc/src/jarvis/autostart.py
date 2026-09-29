"""Iniciar con Windows: clave estándar HKCU\\...\\Run (sin tareas programadas ni servicios)."""
import sys
from pathlib import Path

CLAVE = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE = "Jarvis"


def _comando():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    ejecutable = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{ejecutable}" -m jarvis'


def activado():
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE) as k:
            winreg.QueryValueEx(k, NOMBRE)
            return True
    except OSError:
        return False


def establecer(activar):
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE, 0, winreg.KEY_SET_VALUE) as k:
        if activar:
            winreg.SetValueEx(k, NOMBRE, 0, winreg.REG_SZ, _comando())
        else:
            try:
                winreg.DeleteValue(k, NOMBRE)
            except FileNotFoundError:
                pass
