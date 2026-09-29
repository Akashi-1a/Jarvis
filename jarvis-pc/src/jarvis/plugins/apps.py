"""Módulo 1: abrir y cerrar cualquier aplicación por voz."""
import difflib
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

from .. import winutil
from ..comun import Respuesta, es_no, es_si, normalizar
from ..paths import datos_usuario
from .base import Plugin as PluginBase

SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

VERBOS_ABRIR = {"abre", "abrir", "abri", "ejecuta", "ejecutar", "inicia", "iniciar",
                "lanza", "lanzar", "arranca"}
VERBOS_CERRAR = {"cierra", "cerrar", "cerra"}
RELLENO = {"la", "el", "los", "las", "un", "una", "de", "del", "por", "favor", "porfa",
           "aplicacion", "programa", "app", "ventana", "me", "mi", "mis", "al", "y",
           "puedes", "podrias", "ahora", "en", "windows"}
ORDINALES = {"primero": 0, "primera": 0, "uno": 0, "1": 0, "segundo": 1, "segunda": 1,
             "dos": 1, "2": 1, "tercero": 2, "tercera": 2, "tres": 2, "3": 2,
             "cuarto": 3, "cuarta": 3, "cuatro": 3, "4": 3}
SINONIMOS = {"explorador": "explorer"}  # nombre hablado -> nombre del proceso
NO_MATAR = {"applicationframehost"}  # aloja apps de la Tienda: se cierran por ventana, nunca por proceso
EXCLUIR_NOMBRES = ("desinstal", "uninstall", "leeme", "readme", "manual", "ayuda", "help",
                   "licencia", "license", "documentacion", "sitio web", "website")
EXE_DESCARTADOS = ("unins", "setup", "install", "update", "crash", "helper", "report",
                   "service", "elevat", "notification")


# ---------------------------------------------------------------------------
# Detección de aplicaciones instaladas
# ---------------------------------------------------------------------------

def _sin_exe(nombre):
    return nombre[:-4] if nombre.lower().endswith(".exe") else nombre


class IndiceApps:
    """Lista de apps: menú Inicio, Microsoft Store y Program Files."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.entradas = []
        self._cache = datos_usuario() / "apps_cache.json"

    def cargar_cache(self):
        try:
            self.entradas = json.loads(self._cache.read_text(encoding="utf-8"))
        except Exception:
            self.entradas = []

    def actualizar(self):
        try:
            encontradas = {}
            fuentes = [self._menu_inicio]
            if self.cfg.get("incluir_tienda", True):
                fuentes.append(self._tienda)
            if self.cfg.get("escanear_program_files", True):
                fuentes.append(self._program_files)
            for fuente in fuentes:
                try:
                    for e in fuente():
                        encontradas.setdefault(e["norm"], e)
                except Exception:
                    logging.exception("Falló la fuente de apps %s", fuente.__name__)
            if encontradas:
                self.entradas = list(encontradas.values())
                self._cache.write_text(json.dumps(self.entradas, ensure_ascii=False), encoding="utf-8")
            logging.info("Aplicaciones detectadas: %d", len(self.entradas))
        except Exception:
            logging.exception("No se pudo actualizar la lista de aplicaciones")

    def _menu_inicio(self):
        carpetas = [Path(os.environ.get("ProgramData", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
                    Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"]
        for carpeta in carpetas:
            if not carpeta.exists():
                continue
            for lnk in carpeta.rglob("*.lnk"):
                norm = normalizar(lnk.stem)
                if norm and not any(x in norm for x in EXCLUIR_NOMBRES):
                    yield {"nombre": lnk.stem, "norm": norm, "kind": "ruta", "destino": str(lnk)}

    def _tienda(self):
        """Apps de la Microsoft Store (y el resto del menú Inicio) vía Get-StartApps."""
        comando = ("try { [Console]::OutputEncoding=[Text.Encoding]::UTF8 } catch {}; "
                   "Get-StartApps | ForEach-Object { $_.Name + '|' + $_.AppID }")
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
                           capture_output=True, timeout=45, creationflags=SIN_VENTANA)
        for linea in r.stdout.decode("utf-8-sig", errors="ignore").splitlines():
            if "|" not in linea:
                continue
            nombre, appid = linea.split("|", 1)
            norm = normalizar(nombre)
            if norm and appid.strip() and not any(x in norm for x in EXCLUIR_NOMBRES):
                yield {"nombre": nombre.strip(), "norm": norm, "kind": "aumid", "destino": appid.strip()}

    def _program_files(self):
        bases = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                 str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs")]
        for base in filter(None, bases):
            base = Path(base)
            if not base.exists():
                continue
            for carpeta in base.iterdir():
                if not carpeta.is_dir():
                    continue
                exe = self._mejor_exe(carpeta)
                if exe:
                    yield {"nombre": carpeta.name, "norm": normalizar(carpeta.name),
                           "kind": "ruta", "destino": str(exe)}

    @staticmethod
    def _mejor_exe(carpeta):
        objetivo = normalizar(carpeta.name)
        candidatos = list(carpeta.glob("*.exe")) + list((carpeta / "bin").glob("*.exe"))
        mejor, mejor_ratio = None, 0.6
        for exe in candidatos:
            stem = normalizar(exe.stem)
            if any(x in stem for x in EXE_DESCARTADOS):
                continue
            ratio = difflib.SequenceMatcher(None, stem, objetivo).ratio()
            if ratio > mejor_ratio:
                mejor, mejor_ratio = exe, ratio
        return mejor

    def buscar(self, consulta):
        """Mejores candidatos para lo que se dijo (varios = ambiguo)."""
        tokens = consulta.split()
        exactos = [e for e in self.entradas if e["norm"] == consulta]
        if exactos:
            return exactos[:1]

        def extra(e):
            return len(e["norm"].split()) - len(tokens)

        contienen = [e for e in self.entradas if all(t in e["norm"].split() for t in tokens)]
        if contienen:
            contienen.sort(key=extra)
            return [e for e in contienen if extra(e) == extra(contienen[0])][:4]

        nombres = [e["norm"] for e in self.entradas]
        cerca = difflib.get_close_matches(consulta, nombres, n=3, cutoff=0.72)
        return [next(e for e in self.entradas if e["norm"] == n) for n in cerca]

    def por_nombre(self, nombre):
        norm = normalizar(nombre)
        return next((e for e in self.entradas if e["norm"] == norm), None) or \
            next(iter(self.buscar(norm)[:1]), None)


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class Plugin(PluginBase):
    nombre = "apps"
    prioridad = 60

    def __init__(self, ctx):
        super().__init__(ctx)
        self.cfg = ctx.config["apps"]
        self.aliases = {normalizar(k): v for k, v in ctx.config.get("aliases", {}).items()}
        self.protegidas = {normalizar(x) for x in self.cfg["protegidas"]}
        self.confirmar = {normalizar(x) for x in self.cfg["confirmar_antes_de_cerrar"]}
        self.palabras_av = [normalizar(x) for x in self.cfg["palabras_antivirus"]]
        self.indice = IndiceApps(self.cfg)
        self.indice.cargar_cache()
        threading.Thread(target=self.indice.actualizar, daemon=True).start()

    def ayuda(self):
        return "abrir y cerrar aplicaciones, por ejemplo: abre Chrome o cierra Discord"

    def manejar(self, t):
        w = set(t.split())
        if "actualiza" in w and w & {"aplicaciones", "apps", "programas"}:
            threading.Thread(target=self.indice.actualizar, daemon=True).start()
            return Respuesta("Actualizando la lista de aplicaciones.")
        consulta = self._limpiar(t)
        if w & VERBOS_ABRIR:
            return self.abrir(consulta)
        if w & VERBOS_CERRAR:
            return self.cerrar(consulta)
        return None

    def _limpiar(self, t):
        for clave in self.aliases:  # un alias dicho completo tiene prioridad ("mis juegos")
            if f" {clave} " in f" {t} ":
                return clave
        return " ".join(x for x in t.split()
                        if x not in RELLENO and x not in VERBOS_ABRIR and x not in VERBOS_CERRAR)

    # --- abrir -----------------------------------------------------------
    def abrir(self, consulta):
        if not consulta:
            return Respuesta("¿Qué aplicación desea abrir?",
                             seguimiento=lambda t: self.abrir(self._limpiar(t)))

        if consulta in self.aliases:
            valor = self.aliases[consulta]
            if isinstance(valor, list):
                cands = [e for e in (self.indice.por_nombre(n) for n in valor) if e]
                return self._preguntar_cual(cands) if cands else Respuesta("No encontré esas aplicaciones.")
            if os.path.exists(valor) or "://" in valor or valor.startswith(("shell:", "spotify:")):
                return self._lanzar({"nombre": consulta, "kind": "ruta", "destino": valor})
            consulta = normalizar(valor)

        cands = self.indice.buscar(consulta)
        if not cands:
            if not self.indice.entradas:
                return Respuesta("Todavía estoy leyendo las aplicaciones instaladas. Intente en unos segundos.")
            return Respuesta("No encontré esa aplicación.")
        if len(cands) == 1:
            return self._lanzar(cands[0])
        return self._preguntar_cual(cands)

    def _preguntar_cual(self, cands):
        if len(cands) == 1:
            return self._lanzar(cands[0])
        nombres = [c["nombre"] for c in cands]
        texto = "Encontré varias: " + ", ".join(nombres[:-1]) + f" y {nombres[-1]}. ¿Cuál abro?"
        return Respuesta(texto, seguimiento=lambda t: self._elegir(cands, t))

    def _elegir(self, cands, t):
        if es_no(t):
            return Respuesta("Cancelado.")
        for w in t.split():
            if w in ORDINALES and ORDINALES[w] < len(cands):
                return self._lanzar(cands[ORDINALES[w]])
        palabras = [w for w in t.split() if w not in RELLENO and w not in VERBOS_ABRIR]
        for c in cands:
            if any(p in c["norm"].split() for p in palabras):
                return self._lanzar(c)
        return Respuesta("No entendí cuál. Cancelado.")

    def _lanzar(self, e):
        try:
            if e["kind"] == "aumid":
                os.startfile(f"shell:AppsFolder\\{e['destino']}")
            else:
                os.startfile(e["destino"])
            return Respuesta(f"Abriendo {e['nombre']}.")
        except Exception:
            logging.exception("No se pudo abrir %s", e["nombre"])
            return Respuesta(f"No pude abrir {e['nombre']}.")

    # --- cerrar ----------------------------------------------------------
    @staticmethod
    def _puntaje(tokens, exe, titulo):
        p = 0
        palabras_titulo = titulo.split()
        for t in tokens:
            if len(t) < 3:
                continue
            if t == exe:
                p = max(p, 4)
            elif t in exe or (len(exe) >= 4 and exe in t):
                p = max(p, 3)
            elif t in palabras_titulo:
                p = max(p, 2)
            elif t in titulo:
                p = max(p, 1)
        return p

    def _protegida(self, exe):
        return exe in self.protegidas or any(k in exe for k in self.palabras_av)

    def cerrar(self, consulta):
        if not consulta:
            return Respuesta("¿Qué aplicación desea cerrar?",
                             seguimiento=lambda t: self.cerrar(self._limpiar(t)))

        valor = self.aliases.get(consulta)
        if isinstance(valor, str):
            consulta = normalizar(valor)
        tokens = [SINONIMOS.get(x, x) for x in consulta.split()]

        grupos = {}
        for v in winutil.ventanas():
            if not v["titulo"] or v["pid"] == os.getpid():
                continue
            exe = normalizar(_sin_exe(v["exe"]))
            p = self._puntaje(tokens, exe, normalizar(v["titulo"]))
            if p:
                g = grupos.setdefault(exe, {"puntaje": 0, "ventanas": [], "nombre": _sin_exe(v["exe"])})
                g["puntaje"] = max(g["puntaje"], p)
                g["ventanas"].append(v)

        if not grupos:
            return Respuesta("No encontré esa aplicación abierta.")
        mejor = max(g["puntaje"] for g in grupos.values())
        top = {e: g for e, g in grupos.items() if g["puntaje"] == mejor}

        if len(top) > 1:
            lista = list(top.items())
            nombres = [g["nombre"] for _, g in lista]
            return Respuesta("Hay varias abiertas: " + ", ".join(nombres) + ". ¿Cuál cierro?",
                             seguimiento=lambda t: self._elegir_cierre(lista, t))
        exe, g = next(iter(top.items()))
        if exe not in self.protegidas:
            g["nombre"] = consulta.title()  # "Word" suena mejor que "WINWORD"
        return self._iniciar_cierre(exe, g)

    def _elegir_cierre(self, lista, t):
        if es_no(t):
            return Respuesta("Cancelado.")
        for w in t.split():
            if w in ORDINALES and ORDINALES[w] < len(lista):
                return self._iniciar_cierre(*lista[ORDINALES[w]])
        for exe, g in lista:
            if any(p in normalizar(g["nombre"]) for p in t.split() if len(p) >= 3):
                return self._iniciar_cierre(exe, g)
        return Respuesta("No entendí cuál. Cancelado.")

    def _iniciar_cierre(self, exe, g):
        nombre = g["nombre"]
        if self._protegida(exe):
            return Respuesta(f"No cierro {nombre} por seguridad.")
        if exe in self.confirmar:
            return Respuesta(
                f"¿Confirma que cierro {nombre}? Podría haber trabajo sin guardar.",
                seguimiento=lambda t: self._cierre_amable(exe, g) if es_si(t) else Respuesta("Entendido, no lo cierro."))
        return self._cierre_amable(exe, g)

    def _cierre_amable(self, exe, g):
        """Primero como si se apretara la X. Solo se fuerza si el usuario lo confirma."""
        nombre = g["nombre"]
        hwnds = [v["hwnd"] for v in g["ventanas"]]
        pids = {v["pid"] for v in g["ventanas"]} if exe not in NO_MATAR else set()
        for h in hwnds:
            winutil.cerrar_ventana(h)

        limite = time.monotonic() + self.cfg.get("segundos_espera_cierre", 5)
        while time.monotonic() < limite:
            if not any(winutil.ventana_visible(h) for h in hwnds) and not winutil.procesos_vivos(pids):
                return Respuesta(f"Listo, cerré {nombre}.")
            time.sleep(0.25)

        if any(winutil.ventana_visible(h) for h in hwnds):
            if any(winutil.ventana_colgada(h) for h in hwnds if winutil.ventana_existe(h)) and pids:
                return Respuesta(f"{nombre} no responde. ¿Fuerzo el cierre?",
                                 seguimiento=lambda t: self._forzar(nombre, pids) if es_si(t) else Respuesta("Entendido."))
            return Respuesta(f"{nombre} sigue abierto; quizás esté pidiendo guardar cambios.")
        if pids:
            return Respuesta(f"Cerré la ventana de {nombre}, pero sigue en segundo plano. ¿Lo cierro por completo?",
                             seguimiento=lambda t: self._forzar(nombre, pids) if es_si(t) else Respuesta("Entendido."))
        return Respuesta(f"Listo, cerré {nombre}.")

    def _forzar(self, nombre, pids):
        winutil.terminar_arbol(pids)
        return Respuesta(f"Listo, cerré {nombre} por completo.")
