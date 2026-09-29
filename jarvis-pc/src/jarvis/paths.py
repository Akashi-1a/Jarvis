"""Rutas de la aplicación (funcionan en desarrollo y dentro del .exe)."""
import os
import sys
from pathlib import Path

APP_NAME = "Jarvis"


def congelado():
    return getattr(sys, "frozen", False)


def base_recursos():
    """Carpeta con los datos empaquetados (o la raíz del proyecto en desarrollo)."""
    if congelado():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def recurso(*partes):
    return base_recursos().joinpath(*partes)


def datos_usuario():
    """%APPDATA%\\Jarvis: configuración, registro, caché y plugins del usuario."""
    base = os.environ.get("APPDATA") or str(Path.home())
    ruta = Path(base) / APP_NAME
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta
