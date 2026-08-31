"""
Genera un resumen ejecutivo de los cambios de git y lo envia por email al equipo
via Outlook. Llamado desde el daemon de TeamsRecorder (tray_app.py) para que
claude corra en el contexto correcto con autenticacion.
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from config import CLAUDE_BIN as _CLAUDE_BIN, clean_env

_PULL_CMD = r'git -C "$env:USERPROFILE\Documents\TeamsRecorder" pull'

_PROMPT_TEMPLATE = """Eres el asistente de comunicación de TeamsRecorder, una app de Windows que graba reuniones de Teams y genera minutas automáticas con IA.

El equipo ha publicado una nueva versión. Estos son los cambios (mensajes de commit de git):
{commits}

Escribe el cuerpo de un email de notificación con estas reglas:
- Tono: profesional y cercano, como las notas de actualización de iOS/Apple
- Máximo 150 palabras
- Sin jerga técnica: nada de nombres de ficheros, funciones, variables ni errores de código
- Si hay correcciones de errores, di algo como "Se han corregido problemas en [funcionalidad en lenguaje de usuario]"
- Agrupa los cambios en categorías si tiene sentido: Nuevas funciones · Mejoras · Correcciones
- Termina siempre con este párrafo exacto (cópialo literalmente, sin backticks, sin markdown, sin caracteres especiales):

Para actualizar, abre PowerShell y ejecuta:

{pull_cmd}

La app se reiniciará automáticamente.
- Responde solo con el cuerpo del email, en español, sin asunto ni firma, sin ningún formato markdown
"""


def send_update_email(commits_text: str) -> bool:
    """Genera el resumen con Claude y manda el email al equipo. Devuelve True si éxito."""
    recipients_file = PROJECT_DIR / 'team' / 'recipients.txt'
    if not recipients_file.exists():
        return False

    recipients = [
        r.strip() for r in recipients_file.read_text(encoding='utf-8').splitlines()
        if r.strip() and not r.startswith('#') and '@' in r
    ]
    if not recipients:
        return False

    body = _generate_body(commits_text)
    subject = f"TeamsRecorder — Novedades {datetime.now().strftime('%d/%m/%Y')}"

    try:
        import win32com.client
        outlook = win32com.client.Dispatch('Outlook.Application')
        mail = outlook.CreateItem(0)
        mail.Subject = subject
        mail.Body = body
        for email in recipients:
            mail.Recipients.Add(email)
        mail.Recipients.ResolveAll()
        mail.Send()
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"send_update_email Outlook error: {e}")
        return False


def _generate_body(commits_text: str) -> str:
    """Intenta resumen IA; si falla, devuelve formato manual."""
    if _CLAUDE_BIN:
        prompt = _PROMPT_TEMPLATE.format(commits=commits_text, pull_cmd=_PULL_CMD)
        try:
            result = subprocess.run(
                [_CLAUDE_BIN, '-p'],
                input=prompt,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=90,
                env=clean_env(),
            )
            body = result.stdout.strip()
            if body:
                return body
        except Exception:
            pass

    # Fallback: formato manual con el comando de pull
    lines = [l.strip().lstrip('- ') for l in commits_text.splitlines() if l.strip()]
    bullets = '\n'.join(f'  • {l}' for l in lines)
    return (
        f"Hola,\n\n"
        f"TeamsRecorder ha recibido una nueva actualización con los siguientes cambios:\n\n"
        f"{bullets}\n\n"
        f"Para actualizar, abre PowerShell y ejecuta:\n\n"
        f"    {_PULL_CMD}\n\n"
        f"La app se reiniciará automáticamente."
    )
