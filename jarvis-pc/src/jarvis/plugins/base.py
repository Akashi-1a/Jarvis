"""Base de los plugins.

Para agregar una función nueva: creá un archivo .py en esta carpeta (o en
%APPDATA%\\Jarvis\\plugins) con una clase llamada `Plugin`.
  - manejar(t): recibe la frase ya normalizada (minúsculas, sin tildes).
    Devuelve una Respuesta si la entiende, o None para pasarla al siguiente plugin.
  - prioridad: número menor = se consulta antes.
  - ayuda(): frase corta que Jarvis dice cuando le preguntan qué puede hacer.
"""
from ..comun import Respuesta  # noqa: F401  (se re-exporta para comodidad)


class Plugin:
    nombre = "base"
    prioridad = 50

    def __init__(self, ctx):
        self.ctx = ctx

    def manejar(self, t):
        return None

    def ayuda(self):
        return ""
