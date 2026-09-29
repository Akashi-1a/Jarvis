# -*- mode: python ; coding: utf-8 -*-
# Compilar con:  pyinstaller --noconfirm jarvis.spec
#
# Decisiones pensadas para reducir falsos positivos de antivirus:
#   - "onedir" (carpeta) en vez de "onefile": el .exe autoextraíble es lo que más se marca.
#   - upx=False: los ejecutables comprimidos con UPX se marcan con frecuencia.
#   - Con metadatos de versión (version_info.txt) e ícono propio.
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("resources", "resources"), ("models", "models")]
binaries = []
hidden = collect_submodules("jarvis.plugins") + collect_submodules("pyttsx3")

for paquete in ("vosk", "_sounddevice_data", "pycaw", "pystray"):
    d, b, h = collect_all(paquete)
    datas += d
    binaries += b
    hidden += h

a = Analysis(
    ["run_jarvis.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "numpy.tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Jarvis",
    console=False,
    icon="assets/jarvis.ico",
    version="version_info.txt",
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Jarvis")
