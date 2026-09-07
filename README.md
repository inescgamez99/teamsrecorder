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

Antes de instalar, necesitas tener estas cuatro cosas en tu equipo. Para comprobar si ya las tienes, abre PowerShell (búscalo en el menú Inicio) y ejecuta cada comando:

| Herramienta | Cómo verificar | Si no la tienes |
|---|---|---|
| Python 3.11+ | `python --version` → debe decir 3.11 o superior | [python.org/downloads](https://www.python.org/downloads/) — marca "Add Python to PATH" al instalar |
| Node.js 18+ | `node --version` → debe decir v18 o superior | [nodejs.org](https://nodejs.org) — descarga la versión LTS |
| Git | `git --version` | [git-scm.com/download/win](https://git-scm.com/download/win) — opciones por defecto |
| Claude CLI | `claude --version` | Ver paso 2 más abajo |

No necesitas ninguna API key. La app usa tu cuenta de claude.ai.

## Instalación

### Paso 1 — Descargar el proyecto

Abre PowerShell (menú Inicio → escribe "PowerShell" → Enter) y pega este comando:

```powershell
git clone https://github.com/inescgamez99/teamsrecorder.git "$env:USERPROFILE\Documents\TeamsRecorder"
```

Esto descarga la app en tu carpeta `Documentos\TeamsRecorder`. Verás unas líneas de texto mientras descarga — cuando vuelva a aparecer el cursor, ha terminado.

### Paso 2 — Instalar Claude CLI (si no lo tienes)

Si `claude --version` te dio error en los requisitos previos, ejecuta en PowerShell:

```powershell
npm install -g @anthropic-ai/claude-code
claude login
```

`claude login` abre el navegador. Inicia sesión con tu cuenta de claude.ai y acepta el acceso. Cuando la página confirme que todo fue bien, puedes cerrarla.

### Paso 3 — Ejecutar el instalador

Abre el Explorador de archivos (el icono de carpeta en la barra de tareas), navega a `Documentos\TeamsRecorder` y haz doble clic en **`instalar.bat`**.

Se abre una ventana negra que verifica los requisitos y después lanza Claude. Cuando veas que Claude está listo, escribe exactamente esto y pulsa Enter:

```
/teamsrecorder
```

Claude hace todo lo demás solo: instala las dependencias, configura el arranque automático con Windows y arranca la app por primera vez. El proceso tarda entre 5 y 15 minutos dependiendo de tu conexión.

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
