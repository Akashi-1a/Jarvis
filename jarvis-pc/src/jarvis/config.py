"""Carga de configuración: valores por defecto + archivo editable del usuario."""
import json
import logging

from .paths import datos_usuario, recurso


def _fusionar(base, extra):
    resultado = dict(base)
    for clave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(resultado.get(clave), dict):
            resultado[clave] = _fusionar(resultado[clave], valor)
        else:
            resultado[clave] = valor
    return resultado


def ruta_config():
    return datos_usuario() / "config.json"


def cargar_config():
    defecto = json.loads(recurso("resources", "default_config.json").read_text(encoding="utf-8"))
    ruta = ruta_config()
    if not ruta.exists():
        ruta.write_text(json.dumps(defecto, indent=2, ensure_ascii=False), encoding="utf-8")
        return defecto
    try:
        usuario = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        logging.exception("config.json tiene un error; se usan los valores por defecto")
        return defecto
    return _fusionar(defecto, usuario)
