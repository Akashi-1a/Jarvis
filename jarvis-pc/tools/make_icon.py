"""Genera assets/jarvis.ico (ícono de la app y del instalador)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

destino = Path(__file__).resolve().parents[1] / "assets"
destino.mkdir(exist_ok=True)

img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.ellipse((8, 8, 248, 248), fill=(20, 24, 38, 255), outline=(79, 195, 247, 255), width=10)
d.ellipse((60, 60, 196, 196), outline=(79, 195, 247, 255), width=8)
try:
    fuente = ImageFont.truetype("arialbd.ttf", 110)
except OSError:
    fuente = ImageFont.load_default()
d.text((128, 128), "J", fill=(255, 255, 255, 255), font=fuente, anchor="mm")
img.save(destino / "jarvis.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("Ícono creado en", destino / "jarvis.ico")
