"""Utilidades compartidas: normalización, respuestas y números en español."""
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Optional


def normalizar(texto):
    """Minúsculas, sin tildes ni signos: 'Ábre  Chrome!' -> 'abre chrome'."""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return " ".join(t.split())


@dataclass
class Respuesta:
    """Lo que Jarvis dice. Si hay 'seguimiento', escucha una respuesta más y la procesa."""
    texto: str
    seguimiento: Optional[Callable[[str], Optional["Respuesta"]]] = None


_NO = {"no", "cancela", "cancelar", "negativo", "nada", "olvidalo"}
_SI = {"si", "claro", "confirmo", "dale", "adelante", "correcto", "ok", "okay",
       "afirmativo", "seguro", "hazlo"}


def es_no(t):
    return bool(set(t.split()) & _NO)


def es_si(t):
    return bool(set(t.split()) & _SI) and not es_no(t)


_UNIDADES = {
    "cero": 0, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veintidos": 22,
    "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
    "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
}
_DECENAS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
            "setenta": 70, "ochenta": 80, "noventa": 90}


def numero_es(t):
    """Primer número (0-100) de la frase, en dígitos o palabras. None si no hay."""
    m = re.search(r"\d+", t)
    if m:
        return min(int(m.group()), 100)
    palabras = t.split()
    for i, w in enumerate(palabras):
        if w in ("cien", "ciento"):
            return 100
        if w in _DECENAS:
            valor = _DECENAS[w]
            if (i + 2 < len(palabras) and palabras[i + 1] == "y"
                    and _UNIDADES.get(palabras[i + 2], 10) < 10):
                valor += _UNIDADES[palabras[i + 2]]
            return valor
        if w in _UNIDADES:
            return _UNIDADES[w]
    return None
