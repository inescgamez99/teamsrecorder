import logging
import os
import re
import subprocess
import threading
from pathlib import Path

from config import PROJECT_DIR, CLAUDE_BIN as _CLAUDE_BIN, clean_env as _clean_env

log = logging.getLogger(__name__)

_SYSTEM_PROMPT_BASE = """Eres un asistente especializado en generar minutas profesionales de reuniones de trabajo tecnologico.

Tu output es siempre markdown estructurado, limpio y listo para usar directamente.
{language_instruction}

## PRIMERA LINEA OBLIGATORIA

La primera linea de tu respuesta debe ser SIEMPRE exactamente en este formato (sin markdown, sin #):
TITULO: [3-5 palabras que describan el tema principal, en el idioma de las minutas]

Ejemplos validos:
TITULO: Planificacion Sprint Octubre
TITULO: Revision Diseño App Movil
TITULO: Q3 Project Kickoff
TITULO: Backend Team Daily Standup
TITULO: Daily Standup Equipo Backend
TITULO: Cierre Trimestre Ventas

Despues del titulo: una linea en blanco y luego el markdown completo de las minutas.

## Seccion de Acciones Pendientes — regla critica

Hay UNA SOLA seccion para todas las acciones: "Acciones Pendientes" (o "Pending Actions" en ingles).
No uses secciones separadas de "Next Steps", "Cambios Tecnicos" ni similares.

Esta seccion tiene dos partes:

### Parte 1: Tabla de acciones (TODAS las acciones de la reunion)

| Accion | Responsable | Fecha limite |
|--------|-------------|--------------|
| [descripcion concisa] | [nombre o "-"] | [fecha o "-"] |

Incluye en la tabla TODAS las acciones acordadas: manuales, tecnicas, y las que Claude puede ejecutar.
Para las acciones que Claude puede ejecutar, añade "(Claude)" junto al responsable en la tabla.
Ejemplo: | Refactorizar modulo de autenticacion | Ana (Claude) | 15 Jun |

### Parte 2: Bloques tecnicos (uno por cada accion que Claude puede ejecutar)

Despues de la tabla, incluye un bloque por cada accion marcada como "(Claude)" en la tabla.
Usa el formato adecuado segun el tipo:

Caso A — Cambio de codigo / configuracion:
~~~[lenguaje]
// ARCHIVO: ruta/del/archivo.ext   (si se menciono; sino escribe "A determinar")
// CONTEXTO: Que hace este cambio y por que se acordo en la reunion
// INSTRUCCION PARA CLAUDE CODE: [imperativo directo]

[codigo o configuracion exacta mencionada, o la mejor aproximacion]
~~~

Caso B — Instruccion tecnica sin codigo concreto (UI, diseño, arquitectura, etc.):
~~~instruction-for-claude
[Instruccion directa lista para Claude Code. Debe:
 - Empezar con verbo imperativo (Crea, Modifica, Añade, Elimina, Refactoriza...)
 - Referenciar archivos o componentes especificos si se mencionaron
 - Ser lo suficientemente especifica para ser accionable]
~~~

Caso C — Cambio en documento Office (Word, Excel, PowerPoint):
~~~document-change
// ARCHIVO: nombre-del-archivo.ext
// CONTEXTO: Descripcion del cambio
// INSTRUCCION: [Descripcion precisa del cambio a realizar en el documento]
~~~

Si una accion tecnica no tiene suficiente detalle, incluye el bloque de todas formas y anota:
"DETALLE INSUFICIENTE EN REUNION: [lo que falta]"

Todos los bloques deben ser autocontenidos: quien los lea debe poder actuar sin contexto adicional."""


_LANG_INSTRUCTIONS = {
    'auto': (
        "Detect the language of the meeting from the transcript content and write the minutes "
        "entirely in that same language. If the meeting is clearly multilingual, use the predominant language."
    ),
    'en': "Write always in English, even if some parts of the meeting were in another language.",
    'es': "Escribe siempre en español, aunque alguna parte de la reunion sea en otro idioma.",
}
_LANG_SECTIONS = {
    'en': [
        "Executive Summary",
        "Attendees",
        "Topics Discussed",
        "Decisions Made",
        "Pending Actions (first: table with ALL actions — columns: Action | Owner | Deadline; mark Claude-executable actions with '(Claude)' next to the owner. Then: one technical block per Claude-executable action, in the formats described above)",
        "Additional Notes",
    ],
    'es': [
        "Resumen Ejecutivo",
        "Asistentes",
        "Temas Tratados",
        "Decisiones Tomadas",
        "Acciones Pendientes (primero: tabla con TODAS las acciones — columnas: Acción | Responsable | Fecha límite; marca las ejecutables por Claude con '(Claude)' junto al responsable. Después: un bloque técnico por cada acción Claude, en los formatos descritos arriba)",
        "Notas Adicionales",
    ],
}

def _get_system_prompt(language: str = 'auto') -> str:
    lang = language if language in _LANG_INSTRUCTIONS else 'auto'
    instruction = _LANG_INSTRUCTIONS[lang]
    return _SYSTEM_PROMPT_BASE.format(language_instruction=instruction)


def _build_prompt(transcript: str, recording_path: Path, extra_context: str | None = None, language: str = 'auto') -> str:
    # Extraer fecha/hora del stem
    m = re.match(r'(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})', recording_path.stem)
    fecha = m.group(1) if m else 'desconocida'
    hora = f"{m.group(2)}:{m.group(3)}" if m else 'desconocida'

    # Estimar duración desde el último timestamp del transcript
    duracion = 'desconocida'
    times = re.findall(r'\[(\d{2}):(\d{2})\]', transcript)
    if times:
        last_m, last_s = int(times[-1][0]), int(times[-1][1])
        duracion = f"{last_m}m {last_s}s"

    lang = language if language in _LANG_SECTIONS else 'en'
    sections = _LANG_SECTIONS[lang]
    section_label = "Required minutes structure" if lang == 'en' else "Estructura requerida de las minutas"
    date_label    = f"Date: {fecha}  Start time: {hora}  Estimated duration: {duracion}" if lang == 'en' \
                    else f"Fecha: {fecha}  Hora de inicio: {hora}  Duración estimada: {duracion}"
    ctx_label     = "## Additional context from user:" if lang == 'en' else "## Contexto adicional del usuario:"

    parts = [
        date_label,
        "",
        "## Transcript" if lang == 'en' else "## Transcripción",
        transcript,
        "",
        f"## {section_label}",
    ] + [f"- {s}" for s in sections]

    if extra_context:
        parts.insert(3, f"{ctx_label}\n{extra_context}\n")

    return '\n'.join(parts)


def _generate_via_cli(transcript: str, recording_path: Path, extra_context: str | None = None, language: str = 'auto') -> str | None:
    if not _CLAUDE_BIN:
        log.error("claude CLI no encontrado en PATH")
        return None

    user_prompt = _build_prompt(transcript, recording_path, extra_context, language)
    system_prompt = _get_system_prompt(language).replace('```', '~~~')
    full_prompt = system_prompt + '\n\n' + user_prompt

    try:
        if os.name == 'nt':
            import ctypes
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            CREATE_NO_WINDOW = 0x08000000
        else:
            si = None
            CREATE_NO_WINDOW = 0

        proc = subprocess.Popen(
            [_CLAUDE_BIN, '-p'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            env=_clean_env(),
            startupinfo=si if os.name == 'nt' else None,
            creationflags=CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        try:
            stdout, stderr = proc.communicate(input=full_prompt, timeout=900)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            log.error("claude -p timeout (900s)")
            return None
        if proc.returncode != 0:
            log.error(f"claude -p error (rc={proc.returncode}): {stderr[:500]}")
            return None
        return stdout.strip()
    except Exception as e:
        log.error(f"Error llamando claude CLI: {e}")
        return None


def extract_title_from_minutes(raw_text: str) -> tuple[str, str]:
    lines = raw_text.strip().splitlines()
    if lines and lines[0].startswith('TITULO:'):
        title = lines[0].removeprefix('TITULO:').strip()
        content = '\n'.join(lines[1:]).lstrip('\n')
        return title or 'Reunion', content
    return 'Reunion', raw_text


def save_minutes(minutes: str, output_path: Path) -> bool:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(minutes, encoding='utf-8')
        log.info(f"Minutas guardadas: {output_path}")
        return True
    except Exception as e:
        log.error(f"Error guardando minutas: {e}")
        return False


def generate_minutes(
    transcript: str,
    recording_path: Path,
    extra_context: str | None = None,
    on_complete=None,
    language: str = 'auto',
) -> str | None:
    """
    Si on_complete es callable, ejecuta en thread daemon y devuelve None.
    Si no, bloquea y devuelve el texto de las minutas.
    """
    def _run():
        log.info(f"Generando minutas con claude CLI (idioma: {language})...")
        result = _generate_via_cli(transcript, recording_path, extra_context, language)
        if on_complete:
            on_complete(result)
        return result

    if on_complete:
        t = threading.Thread(target=_run, daemon=True, name='MinutesGenerator')
        t.start()
        return None
    return _run()
