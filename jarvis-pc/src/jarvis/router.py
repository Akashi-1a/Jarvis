"""Motor de órdenes: carga los plugins y reparte cada frase al que la entienda."""
import importlib
import importlib.util
import logging
import pkgutil

from .comun import Respuesta, normalizar
from .paths import datos_usuario

ACTIVACION = {"jarvis", "yarvis", "jarbis", "jarvi"}


class Contexto:
    """Lo que los plugins pueden usar: configuración, la app y el motor."""

    def __init__(self, config, app=None):
        self.config = config
        self.app = app
        self.motor = None


class Motor:
    def __init__(self, ctx):
        self.ctx = ctx
        ctx.motor = self
        self.plugins = []

    def plugin(self, nombre):
        return next((p for p in self.plugins if p.nombre == nombre), None)

    def cargar_plugins(self):
        from . import plugins as paquete

        for info in pkgutil.iter_modules(paquete.__path__):
            if info.name.startswith("_") or info.name == "base":
                continue
            try:
                modulo = importlib.import_module(f"{paquete.__name__}.{info.name}")
                self._instanciar(modulo, info.name)
            except Exception:
                logging.exception("No se pudo cargar el plugin %s", info.name)

        carpeta = datos_usuario() / "plugins"  # plugins propios del usuario
        carpeta.mkdir(exist_ok=True)
        for archivo in sorted(carpeta.glob("*.py")):
            try:
                spec = importlib.util.spec_from_file_location(f"jarvis_usuario_{archivo.stem}", archivo)
                modulo = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(modulo)
                self._instanciar(modulo, archivo.name)
            except Exception:
                logging.exception("No se pudo cargar el plugin de usuario %s", archivo.name)

        self.plugins.sort(key=lambda p: p.prioridad)
        logging.info("Plugins: %s", [p.nombre for p in self.plugins])

    def _instanciar(self, modulo, origen):
        clase = getattr(modulo, "Plugin", None)
        if clase is None:
            logging.warning("%s no define la clase Plugin", origen)
            return
        self.plugins.append(clase(self.ctx))

    def procesar(self, texto):
        palabras = [w for w in normalizar(texto).split() if w not in ACTIVACION]
        t = " ".join(palabras)
        if not t:
            return Respuesta("Dígame.")

        if "ayuda" in palabras or {"que", "puedes", "hacer"} <= set(palabras):
            partes = [p.ayuda() for p in self.plugins if p.ayuda()]
            return Respuesta("Puedo " + "; ".join(partes) + ".")

        for plugin in self.plugins:
            try:
                respuesta = plugin.manejar(t)
            except Exception:
                logging.exception("Error en el plugin %s", plugin.nombre)
                return Respuesta("Ocurrió un error al ejecutar esa orden.")
            if respuesta:
                return respuesta
        return Respuesta("No entendí esa orden.")
