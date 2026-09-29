"""Ícono en la bandeja del sistema con estado (gris = inactivo, verde = escuchando)."""
import logging
import os
import subprocess

from . import autostart
from .config import ruta_config
from .paths import datos_usuario

GRIS = (120, 120, 135, 255)
VERDE = (46, 204, 113, 255)


def _imagen(color):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=color)
    d.ellipse((22, 22, 42, 42), fill=(255, 255, 255, 235))
    return img


class Bandeja:
    def __init__(self, app):
        import pystray

        self.app = app
        self._gris, self._verde = _imagen(GRIS), _imagen(VERDE)
        item = pystray.MenuItem
        menu = pystray.Menu(
            item("Escuchar ahora", lambda i, m: app.pedir_escucha(), default=True),
            item("Iniciar con Windows", self._alternar_inicio, checked=lambda m: autostart.activado()),
            item("Editar configuración", lambda i, m: subprocess.Popen(["notepad.exe", str(ruta_config())])),
            item("Actualizar aplicaciones", lambda i, m: app.actualizar_apps()),
            item("Conectar Spotify", lambda i, m: app.conectar_spotify()),
            item("Ver registro", lambda i, m: subprocess.Popen(["notepad.exe", str(datos_usuario() / "jarvis.log")])),
            pystray.Menu.SEPARATOR,
            item("Salir", lambda i, m: app.salir()),
        )
        self.icon = pystray.Icon("Jarvis", self._gris, "Jarvis — inactivo", menu)

    def _alternar_inicio(self, icon, item):
        try:
            autostart.establecer(not autostart.activado())
        except Exception:
            logging.exception("No se pudo cambiar el inicio con Windows")

    def estado(self, escuchando):
        self.icon.icon = self._verde if escuchando else self._gris
        self.icon.title = "Jarvis — escuchando" if escuchando else "Jarvis — inactivo"

    def notificar(self, mensaje):
        try:
            self.icon.notify(mensaje, "Jarvis")
        except Exception:
            logging.info("Notificación: %s", mensaje)

    def run(self):
        self.icon.run()

    def detener(self):
        self.icon.stop()
