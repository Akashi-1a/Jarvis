"""Aplicación principal: une bandeja, atajo global, voz y plugins."""
import ctypes
import logging
import logging.handlers
import sys
import threading

from .comun import Respuesta, normalizar
from .config import cargar_config
from .paths import datos_usuario
from .router import Contexto, Motor
from .speech import Oido, Voz

_mutex = None


def _instancia_unica():
    """Evita abrir dos Jarvis a la vez."""
    global _mutex
    if sys.platform != "win32":
        return True
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\JarvisAsistenteVoz")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def _configurar_log():
    manejador = logging.handlers.RotatingFileHandler(
        datos_usuario() / "jarvis.log", maxBytes=500_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[manejador],
                        format="%(asctime)s %(levelname)s %(message)s")


class App:
    def __init__(self):
        self.config = cargar_config()
        self.voz = Voz(self.config["hablar_respuestas"])
        self.oido = Oido(self.config)
        self.motor = Motor(Contexto(self.config, self))
        self.bandeja = None
        self.atajo = None
        self._pedido = threading.Event()
        self._salir = threading.Event()

    # --- acciones que también usa el menú de la bandeja ---
    def pedir_escucha(self):
        self._pedido.set()

    def notificar(self, mensaje):
        if self.bandeja:
            self.bandeja.notificar(mensaje)

    def actualizar_apps(self):
        apps = self.motor.plugin("apps")
        if apps:
            threading.Thread(target=apps.indice.actualizar, daemon=True).start()
            self.notificar("Actualizando la lista de aplicaciones…")

    def conectar_spotify(self):
        sp = self.motor.plugin("spotify")
        if sp:
            threading.Thread(target=sp.conectar, daemon=True).start()

    def salir(self):
        self._salir.set()
        self._pedido.set()
        if self.atajo:
            self.atajo.detener()
        if self.bandeja:
            self.bandeja.detener()

    # --- ciclo de escucha ---
    def decir(self, texto):
        logging.info("Jarvis: %s", texto)
        self.voz.decir(texto)

    def _turno(self):
        self.bandeja.estado(True)
        try:
            texto = self.oido.escuchar(self.config["segundos_max_escucha"])
            if not texto:
                return
            logging.info("Usted: %s", texto)
            respuesta = self.motor.procesar(texto)
            for _ in range(3):  # hasta 3 preguntas de seguimiento ("¿cuál?", "¿confirma?")
                self.bandeja.estado(False)
                self.decir(respuesta.texto)
                if not respuesta.seguimiento:
                    break
                self.bandeja.estado(True)
                otra = self.oido.escuchar(6)
                if not otra:
                    self.decir("No recibí respuesta. Cancelado.")
                    break
                try:
                    respuesta = respuesta.seguimiento(normalizar(otra)) or Respuesta("Entendido.")
                except Exception:
                    logging.exception("Error en el seguimiento")
                    respuesta = Respuesta("Ocurrió un error.")
        except Exception:
            logging.exception("Error durante la escucha")
            self.decir("Tuve un problema con el micrófono o el reconocimiento de voz.")
        finally:
            self.bandeja.estado(False)

    def _bucle(self):
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass
        try:
            self.motor.cargar_plugins()
            self.oido.precargar()
        except Exception:
            logging.exception("Fallo al iniciar")
            self.notificar("No se pudo cargar el modelo de voz. Vea el registro.")
        if self.config.get("saludo_inicial"):
            atajo = self.config["atajo"].replace("+", " más ")
            self.decir(f"Jarvis listo. Presione {atajo} para hablarme.")
        while not self._salir.is_set():
            if self._pedido.wait(0.5):
                self._pedido.clear()
                if not self._salir.is_set():
                    self._turno()

    def ejecutar(self):
        from .hotkey import AtajoGlobal
        from .tray import Bandeja

        self.bandeja = Bandeja(self)
        self.atajo = AtajoGlobal(
            self.config["atajo"], self.pedir_escucha,
            al_fallar=lambda: self.notificar("No se pudo registrar el atajo de teclado. Vea el registro."))
        self.atajo.start()
        threading.Thread(target=self._bucle, daemon=True).start()
        self.bandeja.run()  # bloquea hasta "Salir"


def main():
    if not _instancia_unica():
        return
    _configurar_log()
    logging.info("Jarvis iniciado")
    try:
        App().ejecutar()
    except Exception:
        logging.exception("Jarvis se cerró por un error")
        raise
