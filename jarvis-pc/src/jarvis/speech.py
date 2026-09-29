"""Voz: reconocimiento OFFLINE con Vosk y respuestas habladas con el motor de Windows."""
import json
import logging
import queue
import threading
import time

from .paths import recurso


class Oido:
    """Convierte lo que se dice al micrófono en texto. El audio nunca sale de la PC."""

    def __init__(self, config):
        self.config = config
        self._modelo = None
        self._lock = threading.Lock()

    def precargar(self):
        with self._lock:
            if self._modelo is None:
                from vosk import Model, SetLogLevel

                SetLogLevel(-1)
                ruta = recurso("models", self.config["modelo_vosk"])
                if not ruta.exists():
                    raise FileNotFoundError(f"No se encontró el modelo de voz en {ruta}")
                self._modelo = Model(str(ruta))
        return self._modelo

    def escuchar(self, max_seg=8, espera_inicio=4):
        import sounddevice as sd
        from vosk import KaldiRecognizer

        rec = KaldiRecognizer(self.precargar(), 16000)
        cola = queue.Queue()

        def cb(datos, frames, tiempo, estado):
            cola.put(bytes(datos))

        inicio = time.monotonic()
        hablo = False
        with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype="int16", channels=1,
                               callback=cb, device=self.config.get("dispositivo_microfono")):
            while time.monotonic() - inicio < max_seg:
                try:
                    datos = cola.get(timeout=0.5)
                except queue.Empty:
                    continue
                if rec.AcceptWaveform(datos):
                    texto = json.loads(rec.Result()).get("text", "").strip()
                    if texto:
                        return texto
                elif json.loads(rec.PartialResult()).get("partial"):
                    hablo = True
                elif not hablo and time.monotonic() - inicio > espera_inicio:
                    return ""
        return json.loads(rec.FinalResult()).get("text", "").strip()


class Voz:
    """Respuestas habladas (offline). Espera a terminar de hablar para no grabarse a sí misma."""

    def __init__(self, activa=True):
        self.activa = activa
        self._cola = queue.Queue()
        if activa:
            threading.Thread(target=self._bucle, daemon=True).start()

    def decir(self, texto, esperar=True):
        if not self.activa or not texto:
            return
        evento = threading.Event()
        self._cola.put((texto, evento))
        if esperar:
            evento.wait(timeout=30)

    @staticmethod
    def _elegir_voz():
        import pyttsx3

        for v in pyttsx3.init().getProperty("voices"):
            datos = f"{v.name} {v.id}".lower()
            if "spanish" in datos or "español" in datos or "es-" in datos or "_es_" in datos:
                return v.id
        return None

    def _bucle(self):
        try:
            import comtypes
            comtypes.CoInitialize()  # el motor de voz de Windows necesita COM en este hilo
        except Exception:
            pass
        try:
            voz_id = self._elegir_voz()
        except Exception:
            logging.exception("No se pudo elegir la voz")
            voz_id = None
        while True:
            texto, evento = self._cola.get()
            try:
                import pyttsx3

                motor = pyttsx3.init()  # un motor nuevo por frase evita que se quede mudo
                motor.setProperty("rate", 185)
                if voz_id:
                    motor.setProperty("voice", voz_id)
                motor.say(texto)
                motor.runAndWait()
                motor.stop()
            except Exception:
                logging.exception("Error al hablar")
            finally:
                evento.set()
