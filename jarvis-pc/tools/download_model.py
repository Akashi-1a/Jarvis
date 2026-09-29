"""Descarga el modelo de voz offline (Vosk, español, ~40 MB) a la carpeta models/."""
import sys
import urllib.request
import zipfile
from pathlib import Path

MODELO = "vosk-model-small-es-0.42"  # debe coincidir con "modelo_vosk" en resources/default_config.json
URL = f"https://alphacephei.com/vosk/models/{MODELO}.zip"

destino = Path(__file__).resolve().parents[1] / "models"
if (destino / MODELO).exists():
    print("El modelo ya está descargado.")
    sys.exit(0)

destino.mkdir(exist_ok=True)
archivo = destino / f"{MODELO}.zip"
print("Descargando", URL)
urllib.request.urlretrieve(URL, archivo)
with zipfile.ZipFile(archivo) as z:
    z.extractall(destino)
archivo.unlink()
print("Modelo listo en", destino / MODELO)
