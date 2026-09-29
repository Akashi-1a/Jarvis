"""Ventanas y procesos de Windows, usando solo APIs públicas (user32 / psutil).

Cerrar una ventana = enviarle WM_CLOSE, exactamente lo que hace la X.
"""
import ctypes
from ctypes import wintypes

WM_CLOSE = 0x0010
WM_APPCOMMAND = 0x0319
DWMWA_CLOAKED = 14

_listo = False


def _u():
    global _listo
    u = ctypes.windll.user32
    if not _listo:
        u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        u.PostMessageW.restype = wintypes.BOOL
        _listo = True
    return u


def _oculta_por_sistema(hwnd):
    """Ventanas 'cloaked' (apps de la Tienda suspendidas): parecen visibles pero no lo están."""
    try:
        valor = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(valor), ctypes.sizeof(valor))
        return valor.value != 0
    except Exception:
        return False


def ventanas(incluir_ocultas=False):
    """Lista de ventanas de nivel superior: hwnd, pid, exe, título, clase, visible."""
    import psutil

    u = _u()
    resultado = []
    tipo = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        visible = bool(u.IsWindowVisible(hwnd)) and not _oculta_por_sistema(hwnd)
        if not visible and not incluir_ocultas:
            return True
        n = u.GetWindowTextLengthW(hwnd)
        titulo = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, titulo, n + 1)
        clase = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(hwnd, clase, 256)
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            exe = psutil.Process(pid.value).name()
        except Exception:
            exe = ""
        resultado.append({"hwnd": hwnd, "pid": pid.value, "exe": exe,
                          "titulo": titulo.value, "clase": clase.value, "visible": visible})
        return True

    u.EnumWindows(tipo(cb), 0)
    return resultado


def cerrar_ventana(hwnd):
    """Equivale a apretar la X: la app puede preguntar si guardar cambios."""
    _u().PostMessageW(hwnd, WM_CLOSE, 0, 0)


def ventana_visible(hwnd):
    u = _u()
    return bool(u.IsWindow(hwnd)) and bool(u.IsWindowVisible(hwnd))


def ventana_existe(hwnd):
    return bool(_u().IsWindow(hwnd))


def ventana_colgada(hwnd):
    return bool(_u().IsHungAppWindow(hwnd))


def enviar_appcommand(hwnd, comando):
    """Envía un comando multimedia (play/pausa/siguiente...) a UNA ventana concreta."""
    _u().PostMessageW(hwnd, WM_APPCOMMAND, hwnd, comando << 16)


def procesos_vivos(pids):
    import psutil

    vivos = set()
    for pid in pids:
        try:
            if psutil.Process(pid).status() != psutil.STATUS_ZOMBIE:
                vivos.add(pid)
        except psutil.Error:
            pass
    return vivos


def terminar_arbol(pids, espera=3):
    """Cierre forzado (solo después de que el usuario lo confirme)."""
    import psutil

    objetivos = []
    for pid in pids:
        try:
            p = psutil.Process(pid)
            objetivos += p.children(recursive=True) + [p]
        except psutil.Error:
            pass
    for p in objetivos:
        try:
            p.terminate()
        except psutil.Error:
            pass
    _, vivos = psutil.wait_procs(objetivos, timeout=espera)
    for p in vivos:
        try:
            p.kill()
        except psutil.Error:
            pass
