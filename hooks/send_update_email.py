"""
Genera un resumen ejecutivo de los cambios de git y lo envia por email al equipo
via Outlook. Se invoca desde el hook pre-push con los commits en stdin.
"""
import subprocess
import sys
import shutil
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

sys.path.insert(0, str(PROJECT_DIR))
try:
    from config import CLAUDE_BIN as _CLAUDE_BIN
except Exception:
    _CLAUDE_BIN = shutil.which('claude')


def _ai_summary(commits_text: str) -> str | None:
    """Intenta generar un resumen ejecutivo con Claude. Devuelve None si falla."""
    if not _CLAUDE_BIN:
        return None
    prompt = f"""Eres el asistente de comunicación de TeamsRecorder, una app de Windows que graba reuniones de Teams y genera minutas automáticas con IA.

El equipo ha publicado una nueva versión. Estos son los cambios (mensajes de commit de git):
{commits_text}

Escribe el cuerpo de un email de notificación con estas reglas:
- Tono: profesional y cercano, como las notas de actualización de iOS/Apple
- Máximo 150 palabras
- Sin jerga técnica: nada de nombres de ficheros, funciones, variables ni errores de código
- Si hay correcciones de errores, di algo como "Se han corregido problemas en [funcionalidad en lenguaje de usuario]"
- Agrupa los cambios en categorías si tiene sentido: Nuevas funciones · Mejoras · Correcciones
- Termina siempre con esta frase exacta: "Haz git pull para recibir los cambios. La app se reiniciará automáticamente."
- Responde solo con el cuerpo del email, en español, sin asunto ni firma
"""
    try:
        result = subprocess.run(
            [_CLAUDE_BIN, '-p'],
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=90,
        )
        body = result.stdout.strip()
        if body:
            return body
        stderr_preview = result.stderr.strip()[:200] if result.stderr else ''
        print(f"send_update_email: Claude exit {result.returncode} — usando formato manual")
        if stderr_preview:
            print(f"send_update_email: {stderr_preview}")
    except Exception as e:
        print(f"send_update_email: Claude no disponible ({e}) — usando formato manual")
    return None


def _manual_body(commits_text: str) -> str:
    """Formatea los commits como email legible sin necesitar IA."""
    lines = [l.strip().lstrip('- ') for l in commits_text.splitlines() if l.strip()]
    bullets = '\n'.join(f'  • {l}' for l in lines)
    return (
        f"Hola,\n\n"
        f"TeamsRecorder ha recibido una nueva actualización con los siguientes cambios:\n\n"
        f"{bullets}\n\n"
        f"Haz git pull para recibir los cambios. La app se reiniciará automáticamente."
    )


def main():
    commits_text = sys.stdin.buffer.read().decode('utf-8', errors='replace').strip()
    if not commits_text:
        return

    recipients_file = PROJECT_DIR / 'team' / 'recipients.txt'
    if not recipients_file.exists():
        print("send_update_email: recipients.txt no encontrado, saltando.")
        return

    recipients = [
        r.strip() for r in recipients_file.read_text(encoding='utf-8').splitlines()
        if r.strip() and not r.startswith('#') and '@' in r
    ]
    if not recipients:
        print("send_update_email: sin destinatarios configurados, saltando.")
        return

    body = _ai_summary(commits_text) or _manual_body(commits_text)
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
        print(f"send_update_email: email enviado a {len(recipients)} destinatario(s).")
    except Exception as e:
        print(f"send_update_email: error enviando via Outlook: {e}")


if __name__ == '__main__':
    main()
