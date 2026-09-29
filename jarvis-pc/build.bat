@echo off
REM Construye Jarvis.exe y el instalador. Requiere Python 3.11 (64 bits) e Inno Setup 6.
setlocal
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"

py -3.11 -m venv .venv || goto :error
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip || goto :error
pip install -r requirements.txt || goto :error
python tools\make_icon.py || goto :error
python tools\download_model.py || goto :error
pyinstaller --noconfirm jarvis.spec || goto :error

if not exist "%ISCC%" echo No se encontro Inno Setup 6 - se omite el instalador. Descargalo de jrsoftware.org
if exist "%ISCC%" "%ISCC%" installer\jarvis.iss || goto :error

echo.
echo Listo:
echo   Programa:    dist\Jarvis\Jarvis.exe
echo   Instalador:  dist_installer\
exit /b 0

:error
echo Fallo la compilacion.
exit /b 1
