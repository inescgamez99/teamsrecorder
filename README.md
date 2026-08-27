# TeamsRecorder

Daemon de Windows que detecta automáticamente reuniones de Teams, graba el audio, transcribe con Whisper y genera minutas estructuradas usando Claude AI. Todo accesible desde un icono en la bandeja del sistema.

## Qué hace

- Detecta llamadas de Teams automáticamente
- Graba micrófono + audio del sistema (loopback)
- Transcribe con faster-whisper (modelo local, sin coste)
- Genera minutas con Claude: resumen, decisiones, acciones
- Extrae y enriquece action items (asignados a personas y proyectos)
- Exporta a HTML y a carpetas de proyecto (SharePoint, etc.)
- Chat con Claude sobre cualquier reunión usando el transcript completo
- Interfaz web local para ver y gestionar todas las notas

## Requisitos

- **Windows 10/11**
- **Python 3.11+** — [python.org](https://python.org)
- **Claude CLI** — instalar con `npm install -g @anthropic-ai/claude-code` y hacer `claude login`
- **Git** (para recibir actualizaciones)

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/TU_REPO.git TeamsRecorder
cd TeamsRecorder
```

### 2. Instalar dependencias Python

```bash
pip install -r requirements.txt
```

### 3. Configurar las API keys

Crea un archivo `.env` en la raíz del proyecto:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

> La clave de Anthropic la puedes pedir a quien te compartió el repo.

### 4. Instalar el arranque automático con Windows

Ejecuta (doble clic o desde terminal):

```
install_autostart.bat
```

Esto registra el watchdog en el inicio de Windows. A partir del siguiente reinicio arranca solo.

### 5. Arrancar por primera vez (sin reiniciar)

```bash
python main.py
```

O doble clic en `start_watchdog.vbs` para arrancar sin ventana de consola.

El icono gris aparecerá en la bandeja del sistema (esquina inferior derecha). Si está oculto, búscalo en el menú de iconos ocultos (flechita ^).

## Uso

| Acción | Cómo |
|---|---|
| Ver minutas | Click en el icono → "Ver minutas y acciones" |
| Añadir contexto mientras grabas | Click derecho en el icono → "Añadir contexto a grabación" |
| Chat sobre una reunión | Abre la reunión → "Chat con Claude" |
| Regenerar minutas con foco | Abre la reunión → "Regenerar minutas" |
| Exportar a carpeta de proyecto | Abre la reunión → "Exportar a proyecto" |

## Recibir actualizaciones

Cuando haya una nueva versión:

```bash
cd TeamsRecorder
git pull
```

Después reinicia el daemon: click derecho en el icono de la bandeja → "Salir", y vuelve a ejecutar `start_watchdog.vbs` (o reinicia Windows).

> El watchdog se encarga de reiniciar automáticamente si el daemon se cae.

## Configuración avanzada

### Cambiar el modelo Whisper

En la app → Ajustes → Grabación. Modelos disponibles: `tiny`, `base`, `small`, `medium` (por defecto), `large-v3`. Más grande = más preciso pero más lento.

### Configurar proyectos y carpetas de exportación

En la app → Ajustes → Proyectos. Puedes asociar un proyecto (ej: "MiProyecto") a una carpeta local (ej: ruta mapeada de SharePoint). Cada reunión detectada como de ese proyecto exportará automáticamente transcript, HTML y versión email a esa carpeta.

### Directorio de salida personalizado

En `.env`:

```env
OUTPUT_DIR=C:\ruta\donde\guardar\todo
```

## Estructura del proyecto

```
TeamsRecorder/
├── main.py                 # Entrada principal del daemon
├── tray_app.py             # Icono bandeja + pipeline de procesamiento
├── popup.py                # Popup de confirmación de grabación
├── audio_recorder.py       # Grabación mic + loopback
├── transcriber.py          # Transcripción con faster-whisper
├── minutes_generator.py    # Generación de minutas con Claude
├── actions_parser.py       # Extracción de action items
├── actions_enricher.py     # Enriquecimiento con Claude (proyecto, asignado)
├── project_exporter.py     # Exportación a carpetas de proyecto
├── html_exporter.py        # Exportación a HTML
├── app_window.py           # Interfaz web (pywebview + API Python)
├── web/                    # Frontend (HTML, JS, CSS)
├── storage.py              # Rutas y almacenamiento
├── config.py               # Configuración global
├── watchdog.ps1            # Script de auto-reinicio
├── start_watchdog.vbs      # Lanzador silencioso del watchdog
├── install_autostart.bat   # Registra el arranque con Windows
└── requirements.txt
```

## Troubleshooting

**El icono no aparece**: Busca en los iconos ocultos (^). Si no está, ejecuta `start_watchdog.vbs`.

**El daemon no arranca / lock file**: Si ves errores de "already running", ejecuta en PowerShell:
```powershell
Remove-Item "C:\ruta\a\TeamsRecorder\.lock" -Force
```

**Claude no genera minutas**: Asegúrate de que `claude` está en el PATH y has hecho `claude login`.

**No detecta Teams**: Teams debe estar ejecutándose con una llamada activa. La detección tarda ~6 segundos en confirmarse.
