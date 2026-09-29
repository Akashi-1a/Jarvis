"""Atajo de teclado global con RegisterHotKey.

Es la API oficial de Windows para esto: no usa hooks de teclado ni lee lo que
se escribe, lo que además evita alertas de antivirus típicas de los keyloggers.
"""
import ctypes
import logging
import threading
from ctypes import wintypes

MODIFICADORES = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012


def parsear_atajo(atajo):
    """'ctrl+alt+j' -> (modificadores, código de tecla virtual)."""
    mods, vk = 0, None
    for parte in atajo.lower().replace(" ", "").split("+"):
        if parte in MODIFICADORES:
            mods |= MODIFICADORES[parte]
        elif len(parte) == 1 and parte.isalnum():
            vk = ord(parte.upper())
        elif parte.startswith("f") and parte[1:].isdigit() and 1 <= int(parte[1:]) <= 12:
            vk = 0x70 + int(parte[1:]) - 1
        else:
            raise ValueError(f"Tecla no reconocida en el atajo: {parte!r}")
    if vk is None or mods == 0:
        raise ValueError("El atajo necesita al menos un modificador y una tecla (ej. ctrl+alt+j).")
    return mods, vk


class AtajoGlobal(threading.Thread):
    def __init__(self, atajo, callback, al_fallar=None):
        super().__init__(daemon=True)
        self.atajo, self.callback, self.al_fallar = atajo, callback, al_fallar
        self._tid = None

    def run(self):
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        try:
            mods, vk = parsear_atajo(self.atajo)
        except ValueError:
            logging.exception("Atajo inválido")
            if self.al_fallar:
                self.al_fallar()
            return
        self._tid = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, vk):
            logging.error("No se pudo registrar el atajo %s (¿lo usa otro programa?)", self.atajo)
            if self.al_fallar:
                self.al_fallar()
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                self.callback()
        user32.UnregisterHotKey(None, 1)

    def detener(self):
        if self._tid:
            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
