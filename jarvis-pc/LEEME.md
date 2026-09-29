# Jarvis — asistente de voz para Windows 10/11

Controla tu PC con la voz en español: abre y cierra cualquier aplicación y maneja Spotify.
El reconocimiento de voz es **offline** (Vosk): tu audio no sale de la computadora.

---

## 1. Instalar (usuario final)

1. Descargá `Jarvis-Setup-x.y.z.exe` desde la sección **Releases** del repositorio de GitHub.
2. Ejecutalo. Podés marcar *acceso directo en el escritorio* e *iniciar con Windows*. No pide permisos de administrador.
3. Si Windows muestra **"SmartScreen protegió tu PC"**: *Más información → Ejecutar de todos modos*. Pasa con cualquier programa sin firma de código (ver sección 7).
4. Abrí Jarvis: aparece un **ícono en la bandeja** (junto al reloj). Gris = inactivo, verde = escuchando.

## 2. Uso

- Presioná **Ctrl + Alt + J** (o doble clic en el ícono de la bandeja), esperá el pitido... y hablá.
- Si Jarvis te hace una pregunta ("¿Cuál abro?", "¿Confirma?"), responde y él vuelve a escuchar solo.
- Clic derecho en el ícono: iniciar con Windows, editar configuración, actualizar aplicaciones, conectar Spotify, ver registro, salir.

### Ejemplos

| Módulo | Frases |
|---|---|
| Apps | "abre Chrome", "abre la calculadora", "abre Discord", "cierra Discord", "abre mis juegos", "abre Office" (pregunta cuál) |
| Spotify | "abre Spotify", "pausa", "reanuda", "siguiente canción", "canción anterior", "sube el volumen", "volumen al cincuenta", "pon rock", "música para estudiar", "cierra Spotify" |
| General | "qué puedes hacer", "actualiza las aplicaciones" |

Cómo cierra las apps: primero como si apretaras la **X** (la app puede preguntar si guardar). Solo si no responde, o si sigue en segundo plano, te pregunta si quiere **forzar** el cierre. Para Word, Excel, editores de código, etc. pide confirmación antes de empezar. Nunca cierra procesos del sistema, el Explorador de Windows ni antivirus.

## 3. Configurar Spotify

Pausa, siguiente, anterior y volumen funcionan **sin configurar nada** (incluso con cuenta gratuita). Solo "pon rock / música para estudiar" necesita la API de Spotify y una cuenta **Premium**:

1. Entrá a https://developer.spotify.com/dashboard e iniciá sesión → **Create app**.
2. Nombre y descripción libres. En **Redirect URI** poné exactamente `http://127.0.0.1:8888/callback` y agregala.
3. Marcá **Web API** y guardá.
4. Copiá el **Client ID** (no necesitás el Secret).
5. Clic derecho en el ícono de Jarvis → **Editar configuración** → pegalo en `"client_id"` dentro de `"spotify"` → guardá y reiniciá Jarvis.
6. Decí "conecta Spotify" (o menú → *Conectar Spotify*). Se abre el navegador **una sola vez** para autorizar.

Sin Client ID, "pon rock" abre la búsqueda en Spotify pero no reproduce sola.
El volumen afecta **solo a Spotify** (mezclador de Windows), no al del sistema.

## 4. Configuración (`%APPDATA%\Jarvis\config.json`)

- `atajo`: por ejemplo `"ctrl+shift+f9"`.
- `aliases`: `"mis juegos": "Steam"`. Si el valor es una lista, Jarvis pregunta cuál: `"office": ["Word", "Excel"]`. También podés poner una ruta o un enlace.
- `apps.confirmar_antes_de_cerrar`, `apps.protegidas`, `apps.palabras_antivirus`: listas de nombres de proceso (sin `.exe`).
- `hablar_respuestas`: `false` para que no hable (solo registra).
- `spotify.paso_volumen`: cuánto sube/baja cada orden.

## 5. Agregar funciones (plugins)

Cada función es un plugin. Creá un `.py` en `src/jarvis/plugins/` (o en `%APPDATA%\Jarvis\plugins\` sin recompilar) con una clase `Plugin`:

```python
from jarvis.plugins.base import Plugin as Base
from jarvis.comun import Respuesta
import datetime

class Plugin(Base):
    nombre = "hora"
    prioridad = 30
    def ayuda(self): return "decir la hora"
    def manejar(self, t):            # t: frase en minúsculas y sin tildes
        if "hora" in t.split():
            return Respuesta(f"Son las {datetime.datetime.now():%H:%M}.")
```

Devolvé `None` si la frase no es para tu plugin. Con `Respuesta(texto, seguimiento=funcion)` podés hacer una pregunta y procesar la respuesta.

## 6. Compilar el .exe y el instalador

**Opción A — automática con GitHub (recomendada):**
1. Subí este proyecto a un repositorio de GitHub.
2. `git tag v1.0.0` y `git push --tags`.
3. La pestaña **Actions** compila todo en un servidor Windows y publica el instalador en **Releases** (con su hash SHA-256).

**Opción B — en tu PC:** instalá Python 3.11 (64 bits) e Inno Setup 6, y ejecutá `build.bat`.
Resultado: `dist\Jarvis\Jarvis.exe` e instalador en `dist_installer\`.

Ejecutar sin compilar: `pip install -r requirements.txt`, `python tools/download_model.py`, y luego `set PYTHONPATH=src && python -m jarvis`.

## 7. Antivirus y falsos positivos (opción A)

Un programa que abre y cierra procesos, lee el micrófono y se inicia con Windows *parece* sospechoso para las heurísticas. Lo que ya hace este proyecto y lo que te toca a vos:

**Ya incluido en el diseño**
- Empaquetado **onedir** y sin **UPX**: el `.exe` único autoextraíble y los binarios comprimidos son lo que más se marca.
- Metadatos de versión e ícono propios.
- Atajo global con `RegisterHotKey` (API oficial), **sin hooks de teclado** ni lectura de teclas.
- Cerrar apps = mensaje `WM_CLOSE` a sus ventanas (lo mismo que la X). El cierre forzado solo ocurre tras tu confirmación y nunca sobre procesos protegidos.
- Sin inyección de código, sin ofuscación, sin servicios ni tareas programadas: el inicio con Windows usa la clave estándar `HKCU\...\Run`.
- Instalación por usuario (sin administrador). El único programa externo que invoca es `powershell -NoProfile Get-StartApps`, en texto plano, para listar apps de la Tienda (se desactiva con `apps.incluir_tienda: false`).

**Lo que tenés que hacer vos**
1. **Firmar el código** (lo que más reduce alertas y SmartScreen): certificado OV/EV, Azure Trusted Signing (según disponibilidad en tu país) o SignPath, gratis para proyectos de código abierto. El workflow trae el paso de `signtool` comentado. Firmá el `.exe` y el instalador. Con certificado OV la reputación de SmartScreen se construye con las descargas; con EV es inmediata.
2. **Compilar siempre en GitHub Actions** con el código público: es reproducible y transparente.
3. **Publicar el SHA-256** (lo genera el workflow) para que cualquiera verifique la descarga.
4. Antes de publicar cada versión, subirla a https://www.virustotal.com y, si algún motor la marca, enviar el archivo como **falso positivo** al proveedor. Para Microsoft Defender: https://www.microsoft.com/wdsi/filesubmission
5. No agregues técnicas como empaquetadores raros, `-EncodedCommand` ni `-ExecutionPolicy Bypass` en PowerShell, ni descarga de ejecutables en segundo plano.

## 8. Límites conocidos

- El proyecto se probó con pruebas automáticas de la lógica (frases, coincidencias, confirmaciones), pero **no se compiló ni se corrió en un Windows real** durante su creación. Las partes que dependen de Windows (ventanas, mezclador de audio, bandeja, atajo, comandos multimedia a Spotify, PyInstaller) pueden necesitar ajustes en la primera prueba.
- Pausa/reanudar usa el medidor de audio de Spotify para saber si suena. Si no puede medirlo, alterna play/pausa.
- Vosk pequeño reconoce bien frases cortas, pero puede confundir nombres raros de apps; los alias ayudan.
- El volumen por voz solo controla Spotify.
- Al cerrar Discord, Spotify o Chrome, la ventana se cierra pero pueden seguir en segundo plano: Jarvis avisa y ofrece cerrarlos por completo.
