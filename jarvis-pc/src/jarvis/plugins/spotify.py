"""Módulo 2: control de Spotify.

- Pausa / reanudar / siguiente / anterior: comandos multimedia enviados SOLO a la ventana de Spotify.
- Volumen: mezclador de Windows, únicamente la sesión de audio de Spotify (no el volumen del sistema).
- "pon rock" / "música para estudiar": Spotify Web API (requiere Client ID y una cuenta Premium).
"""
import logging
import os
import re
import time
import urllib.parse

from .. import winutil
from ..comun import Respuesta, numero_es
from ..paths import datos_usuario
from .base import Plugin as PluginBase

APPCOMMAND_NEXT, APPCOMMAND_PREV, APPCOMMAND_PLAY_PAUSE = 11, 12, 14

VERBOS_ABRIR = {"abre", "abrir", "abri", "ejecuta", "ejecutar", "inicia", "iniciar", "lanza", "lanzar"}
VERBOS_CERRAR = {"cierra", "cerrar", "cerra"}
SUBIR = {"sube", "subir", "aumenta", "aumentar", "mas", "alto"}
BAJAR = {"baja", "bajar", "reduce", "reducir", "menos", "bajo", "disminuye"}

_PON = (r"(?:pon|pone|ponme|poneme|reproduce|reproduci|reproducime|quiero escuchar|"
        r"quiero oir|escuchar|escucha)")


class ApiSpotify:
    """Spotify Web API con OAuth PKCE (no necesita Client Secret)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._sp = None

    def configurada(self):
        return bool(self.cfg.get("client_id"))

    def cliente(self):
        if self._sp is None:
            import spotipy
            from spotipy.cache_handler import CacheFileHandler
            from spotipy.oauth2 import SpotifyPKCE

            auth = SpotifyPKCE(
                client_id=self.cfg["client_id"],
                redirect_uri=self.cfg.get("redirect_uri", "http://127.0.0.1:8888/callback"),
                scope="user-modify-playback-state user-read-playback-state",
                cache_handler=CacheFileHandler(cache_path=str(datos_usuario() / "spotify_token.json")),
                open_browser=True)
            self._sp = spotipy.Spotify(auth_manager=auth)
        return self._sp

    def _dispositivo(self, sp):
        for intento in range(2):
            dispositivos = sp.devices().get("devices", [])
            activo = next((d for d in dispositivos if d.get("is_active")), None)
            pc = next((d for d in dispositivos if d.get("type") == "Computer"), None)
            if activo or pc:
                return (activo or pc)["id"]
            if intento == 0:
                os.startfile("spotify:")  # abre la app y espera a que aparezca como dispositivo
                time.sleep(7)
        raise RuntimeError("Spotify no aparece como dispositivo")

    def reproducir_playlist(self, consulta):
        sp = self.cliente()
        resultado = sp.search(q=consulta, type="playlist", limit=5)
        items = [i for i in resultado.get("playlists", {}).get("items", []) if i]
        if not items:
            return None
        sp.start_playback(device_id=self._dispositivo(sp), context_uri=items[0]["uri"])
        return items[0]["name"]


class Plugin(PluginBase):
    nombre = "spotify"
    prioridad = 40

    def __init__(self, ctx):
        super().__init__(ctx)
        self.cfg = ctx.config["spotify"]
        self.api = ApiSpotify(self.cfg)

    def ayuda(self):
        return "controlar Spotify: pausa, siguiente, volumen, o poner un género como rock"

    # --- reconocimiento de órdenes -----------------------------------
    def manejar(self, t):
        w = set(t.split())
        if "spotify" in w:
            if w & VERBOS_ABRIR:
                return self.abrir()
            if w & VERBOS_CERRAR:
                return self.cerrar()
            if w & {"conecta", "conectar", "vincula", "vincular"}:
                return Respuesta(self.conectar())
        if "volumen" in w:
            return self.volumen(t, w)
        if w & {"siguiente", "proxima", "proximo", "salta", "saltar", "next"} or \
                ("pasa" in w and w & {"cancion", "tema"}):
            return self.saltar(APPCOMMAND_NEXT, "Siguiente canción.")
        if w & {"anterior", "previa", "previo"} and (w & {"cancion", "tema", "musica"} or len(w) <= 2):
            return self.saltar(APPCOMMAND_PREV, "Canción anterior.")
        if w & {"pausa", "pausar", "pausala", "pausalo"} or \
                (w & {"para", "deten", "detene", "frena"} and w & {"musica", "cancion", "spotify"}):
            return self.pausa(True)
        if w & {"reanuda", "reanudar", "continua", "continuar", "play", "despausa"} or \
                (w & {"reproduce", "pon"} and len(w) == 1):
            return self.pausa(False)
        consulta = self._consulta_reproduccion(t)
        if consulta == "spotify":
            return self.abrir()
        if consulta:
            return self.reproducir(consulta)
        return None

    @staticmethod
    def _consulta_reproduccion(t):
        m = re.search(r"(?:^|\s)(musica (?:para|de|del) .+)$", t)
        if m:
            return m.group(1)
        m = re.match(rf"^{_PON}\s+(?:un poco de\s+|algo de\s+)?(?:musica\s+)?(?:de\s+|del\s+)?(.+)$", t)
        if m and m.group(1) not in {"musica", "algo", "una cancion", "la musica"}:
            return m.group(1)
        return None

    # --- abrir / cerrar ------------------------------------------------
    def _procesos(self):
        import psutil

        return [p.pid for p in psutil.process_iter(["name"])
                if (p.info["name"] or "").lower() == "spotify.exe"]

    def abrir(self):
        if self._procesos():
            return Respuesta("Spotify ya está abierto.")
        try:
            os.startfile("spotify:")  # protocolo que registra el instalador de Spotify
            return Respuesta("Abriendo Spotify.")
        except Exception:
            apps = self.ctx.motor.plugin("apps")
            return apps.abrir("spotify") if apps else Respuesta("No pude abrir Spotify.")

    def cerrar(self):
        apps = self.ctx.motor.plugin("apps")
        return apps.cerrar("spotify") if apps else Respuesta("No pude cerrar Spotify.")

    # --- transporte ----------------------------------------------------
    def _ventana(self):
        candidatas = [v for v in winutil.ventanas(incluir_ocultas=True)
                      if v["exe"].lower() == "spotify.exe" and v["clase"].startswith("Chrome_WidgetWin")]
        candidatas.sort(key=lambda v: (v["visible"], bool(v["titulo"])), reverse=True)
        return candidatas[0]["hwnd"] if candidatas else None

    def _sesiones(self):
        from pycaw.pycaw import AudioUtilities

        return [s for s in AudioUtilities.GetAllSessions()
                if s.Process and s.Process.name().lower() == "spotify.exe"]

    def _sonando(self):
        """True/False según el medidor de audio de Spotify; None si no se puede saber."""
        try:
            from pycaw.pycaw import IAudioMeterInformation

            medidores = [s._ctl.QueryInterface(IAudioMeterInformation) for s in self._sesiones()]
            if not medidores:
                return False
            for _ in range(6):
                if any(m.GetPeakValue() > 0.001 for m in medidores):
                    return True
                time.sleep(0.08)
            return False
        except Exception:
            logging.exception("No se pudo medir el audio de Spotify")
            return None

    def _comando(self, comando):
        hwnd = self._ventana()
        if hwnd is None:
            return False
        winutil.enviar_appcommand(hwnd, comando)
        return True

    def pausa(self, pausar):
        if not self._procesos():
            return Respuesta("Spotify no está abierto.")
        sonando = self._sonando()
        if sonando is not None and sonando == (not pausar):
            return Respuesta("Spotify ya está en pausa." if pausar else "Spotify ya está sonando.")
        if not self._comando(APPCOMMAND_PLAY_PAUSE):
            return Respuesta("No pude comunicarme con la ventana de Spotify.")
        return Respuesta("Pausado." if pausar else "Reanudando.")

    def saltar(self, comando, texto):
        if not self._procesos():
            return Respuesta("Spotify no está abierto.")
        return Respuesta(texto if self._comando(comando) else "No pude comunicarme con la ventana de Spotify.")

    # --- volumen (solo Spotify) ------------------------------------------
    def volumen(self, t, w):
        try:
            sesiones = self._sesiones()
        except Exception:
            logging.exception("No se pudo acceder al mezclador de Windows")
            return Respuesta("No pude acceder al volumen de Spotify.")
        if not sesiones:
            return Respuesta("No encuentro el volumen de Spotify. Reproduzca algo primero.")

        actual = round(sesiones[0].SimpleAudioVolume.GetMasterVolume() * 100)
        paso = int(self.cfg.get("paso_volumen", 10))
        numero = numero_es(t)
        if numero is not None and re.search(r"\b(al|a|en|hasta)\b", t):
            nuevo = numero
        elif w & SUBIR:
            nuevo = min(100, actual + paso)
        elif w & BAJAR:
            nuevo = max(0, actual - paso)
        else:
            return Respuesta("¿Subo o bajo el volumen de Spotify?")

        for s in sesiones:
            s.SimpleAudioVolume.SetMasterVolume(nuevo / 100, None)
        return Respuesta(f"Volumen de Spotify al {nuevo} por ciento.")

    # --- géneros y playlists ---------------------------------------------
    def reproducir(self, consulta):
        if not self.api.configurada():
            try:
                os.startfile("spotify:search:" + urllib.parse.quote(consulta))
            except Exception:
                logging.exception("No se pudo abrir la búsqueda de Spotify")
            return Respuesta("Abrí la búsqueda en Spotify. Para que empiece a sonar sola, "
                             "configure el Client ID como indica el archivo LEEME.")
        try:
            nombre = self.api.reproducir_playlist(consulta)
        except Exception as e:
            logging.exception("Error de la API de Spotify")
            if getattr(e, "http_status", None) == 403:
                return Respuesta("Spotify solo permite iniciar listas desde aquí con una cuenta Premium.")
            return Respuesta("No pude iniciar esa música en Spotify.")
        if nombre is None:
            return Respuesta("No encontré una lista para eso.")
        return Respuesta(f"Reproduciendo {nombre}.")

    def conectar(self):
        """Inicia el inicio de sesión de Spotify (abre el navegador una sola vez)."""
        if not self.api.configurada():
            return "Falta el Client ID de Spotify en la configuración."
        try:
            if self.ctx.app:
                self.ctx.app.notificar("Se abrirá el navegador para autorizar Spotify.")
            self.api.cliente().devices()
            return "Spotify conectado."
        except Exception:
            logging.exception("No se pudo conectar con Spotify")
            return "No pude conectar con Spotify."
