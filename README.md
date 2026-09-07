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

## Requisitos previos

Solo necesitas instalar **Git** manualmente. El resto (Python, Node.js, Claude CLI) lo instala el instalador automáticamente.

**Git** — comprueba si ya lo tienes abriendo PowerShell (menú Inicio → escribe "PowerShell" → Enter) y ejecutando:

```powershell
git --version
```

Si ves un número de versión, ya lo tienes. Si no, descárgalo desde [git-scm.com/download/win](https://git-scm.com/download/win) e instálalo con las opciones por defecto.

No necesitas ninguna API key. La app usa tu cuenta de claude.ai.

## Instalación

### Paso 1 — Descargar el proyecto

Abre PowerShell y pega este comando:

```powershell
git clone https://github.com/inescgamez99/teamsrecorder.git "$env:USERPROFILE\Documents\TeamsRecorder"
```

Esto descarga la app en tu carpeta `Documentos\TeamsRecorder`. Verás unas líneas de texto mientras descarga — cuando vuelva a aparecer el cursor, ha terminado.

### Paso 2 — Ejecutar el instalador

Abre el Explorador de archivos (el icono de carpeta en la barra de tareas), navega a `Documentos\TeamsRecorder` y haz doble clic en **`instalar.bat`**.

Se abre una ventana negra que instala automáticamente Python, Node.js y Claude CLI si no los tienes. Cuando termine y veas que Claude está listo, escribe exactamente esto y pulsa Enter:

```
/teamsrecorder
```

Claude hace todo lo demás solo: instala las dependencias de la app, configura el arranque automático con Windows y la arranca por primera vez. El proceso tarda entre 5 y 15 minutos dependiendo de tu conexión.

Al terminar, verás un pequeño icono gris en la esquina inferior derecha de la pantalla (en la bandeja del sistema). Si no lo ves, haz clic en la flechita `^` de esa zona para ver los iconos ocultos.

> A partir de este momento, la app arranca sola cada vez que enciendes el ordenador.

## Uso

| Acción | Cómo |
|---|---|
| Ver minutas | Click en el icono → "Ver minutas y acciones" |
| Añadir contexto mientras grabas | Click derecho en el icono → "Añadir contexto a grabación" |
| Chat sobre una reunión | Abre la reunión → "Chat con Claude" |
| Regenerar minutas con foco | Abre la reunión → "Regenerar minutas" |
| Exportar a carpeta de proyecto | Abre la reunión → "Exportar a proyecto" |

## Recibir actualizaciones

Cuando haya una nueva versión disponible, abre PowerShell, ve a la carpeta del proyecto y abre Claude:

```powershell
cd "$env:USERPROFILE\Documents\TeamsRecorder"
claude
```

Cuando Claude esté listo, escribe `/teamsrecorder`. Detecta automáticamente que ya está instalado, descarga los cambios y reinicia la app sin que tengas que hacer nada más.

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
