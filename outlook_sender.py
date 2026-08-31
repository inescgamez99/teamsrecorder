"""
Detecta participantes del calendario de Outlook y envía minutas por email.
"""
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

def _get_outlook():
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass
    import win32com.client
    return win32com.client.Dispatch('Outlook.Application')


def find_meeting_participants(recording_time: datetime, window_minutes: int = 15) -> list[dict]:
    """
    Busca en el calendario de Outlook la reunión más cercana a recording_time
    y devuelve la lista de participantes con nombre y email.
    """
    try:
        outlook = _get_outlook()
        ns = outlook.GetNamespace('MAPI')
        calendar = ns.GetDefaultFolder(9)  # olFolderCalendar

        start = recording_time - timedelta(minutes=window_minutes)
        end   = recording_time + timedelta(hours=3)

        items = calendar.Items
        items.Sort('[Start]')
        items.IncludeRecurrences = True

        filter_str = (
            f"[Start] >= '{start.strftime('%m/%d/%Y %I:%M %p')}' AND "
            f"[Start] <= '{end.strftime('%m/%d/%Y %I:%M %p')}'"
        )
        filtered = items.Restrict(filter_str)

        participants = []
        best_item = None
        min_diff = timedelta(hours=3)

        for item in filtered:
            try:
                item_start = item.Start
                if hasattr(item_start, 'year'):
                    diff = abs(item_start - recording_time.replace(tzinfo=None))
                    if diff < min_diff:
                        min_diff = diff
                        best_item = item
            except Exception:
                continue

        if best_item:
            log.info(f"Reunión encontrada en calendario: {best_item.Subject}")
            for rec in best_item.Recipients:
                try:
                    participants.append({
                        'name': rec.Name,
                        'email': rec.Address,
                    })
                except Exception:
                    pass

        return participants
    except Exception as e:
        log.warning(f"No se pudieron obtener participantes de Outlook: {e}")
        return []


def send_minutes_email(
    minutes_path: Path,
    html_path: Path,
    title: str,
    participants: list[dict],
    recording_time: datetime | None = None,
    language: str = 'es',
) -> bool:
    """
    Abre un borrador de email en Outlook con las minutas en HTML limpio (sin colores).
    El usuario puede revisar y enviar manualmente.
    """
    try:
        outlook = _get_outlook()
        mail = outlook.CreateItem(0)

        # Asunto
        date_str = recording_time.strftime('%d/%m/%Y') if recording_time else ''
        if language == 'en':
            mail.Subject = f"Meeting notes: {title}" + (f" — {date_str}" if date_str else '')
        else:
            mail.Subject = f"Notas de reunión: {title}" + (f" — {date_str}" if date_str else '')

        # Destinatarios
        for p in participants:
            mail.Recipients.Add(p.get('email') or p.get('name', ''))

        # Construir HTML limpio
        minutes_text = minutes_path.read_text(encoding='utf-8') if minutes_path.exists() else ''
        mail.HTMLBody = _build_email_html(minutes_text, title, date_str, participants, language)

        mail.Display()
        log.info(f"Borrador creado en Outlook con {len(participants)} destinatarios")
        return True

    except Exception as e:
        log.error(f"Error creando email en Outlook: {e}")
        return False


def _build_email_html(minutes_text: str, title: str, date_str: str, participants: list[dict], language: str = 'es') -> str:
    """Convierte las minutas markdown a HTML de email limpio, sin colores."""
    import json as _json

    # Nombre del usuario desde settings.json
    user_name = ''
    try:
        from pathlib import Path as _Path
        settings_path = _Path(__file__).parent / 'settings.json'
        if settings_path.exists():
            user_name = _json.loads(settings_path.read_text(encoding='utf-8')).get('user_name', '')
    except Exception:
        pass

    body_html = _md_to_email_html(minutes_text)

    if language == 'en':
        saludo  = "Hi All,"
        intro   = f"Please find below the notes from our meeting <strong>{title}</strong>{(' on ' + date_str) if date_str else ''}. Review the key decisions and action items assigned."
        closing = f"Best regards,<br><strong>{user_name}</strong>" if user_name else "Best regards,"
    else:
        saludo  = "Hola a todos,"
        intro   = f"Os comparto las notas de nuestra reunión <strong>{title}</strong>{(' del ' + date_str) if date_str else ''}. A continuación encontraréis el resumen, las decisiones tomadas y las acciones pendientes."
        closing = f"Un saludo,<br><strong>{user_name}</strong>" if user_name else "Un saludo,"

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Calibri,Arial,sans-serif;font-size:14px;color:#1a1a1a;max-width:680px;line-height:1.5">
<p style="margin:0 0 12px">{saludo}</p>
<p style="margin:0 0 20px">{intro}</p>
<p style="margin:0 0 24px">{closing}</p>
<hr style="border:none;border-top:1px solid #ddd;margin:0 0 16px">
{body_html}
</body></html>"""


def _md_to_email_html(md_text: str) -> str:
    """Convierte markdown a HTML limpio sin colores, con tablas reales."""
    lines = md_text.splitlines()
    output = []
    i = 0
    in_list = False
    list_type = ''  # 'ul' o 'ol'
    in_code = False

    while i < len(lines):
        line = lines[i]

        # Bloques de código — omitir (no relevantes en email)
        if line.strip().startswith('~~~') or line.strip().startswith('```'):
            in_code = not in_code
            i += 1
            continue
        if in_code:
            i += 1
            continue

        # Tabla markdown: detectar bloque completo
        if '|' in line and i + 1 < len(lines) and re.match(r'[\|\s\-:]+', lines[i + 1]):
            table_lines = []
            while i < len(lines) and '|' in lines[i]:
                table_lines.append(lines[i])
                i += 1
            output.append(_md_table_to_html(table_lines))
            continue

        # Headings
        if line.startswith('### '):
            if in_list: output.append(f'</{list_type}>'); in_list = False; list_type = ''
            output.append(f'<h3 style="font-size:14px;margin:18px 0 6px;border-bottom:1px solid #eee;padding-bottom:4px">{_inline(line[4:])}</h3>')
        elif line.startswith('## '):
            if in_list: output.append(f'</{list_type}>'); in_list = False; list_type = ''
            output.append(f'<h2 style="font-size:15px;margin:22px 0 8px;border-bottom:1px solid #ccc;padding-bottom:4px">{_inline(line[3:])}</h2>')
        elif line.startswith('# '):
            if in_list: output.append(f'</{list_type}>'); in_list = False; list_type = ''
            output.append(f'<h2 style="font-size:16px;margin:22px 0 8px">{_inline(line[2:])}</h2>')

        # Listas
        elif re.match(r'^[-*]\s', line):
            if not in_list:
                output.append('<ul style="margin:6px 0;padding-left:20px">')
                in_list = True; list_type = 'ul'
            output.append(f'<li style="margin-bottom:4px">{_inline(line[2:])}</li>')
        elif re.match(r'^\d+\.\s', line):
            if not in_list:
                output.append('<ol style="margin:6px 0;padding-left:20px">')
                in_list = True; list_type = 'ol'
            output.append(f'<li style="margin-bottom:4px">{_inline(re.sub(r"^\d+\.\s", "", line))}</li>')

        # Línea vacía — solo añadir espacio si la anterior no era ya vacía
        elif line.strip() == '':
            if in_list: output.append(f'</{list_type}>'); in_list = False; list_type = ''
            if output and output[-1] != '':
                output.append('')

        # Párrafo normal
        else:
            if in_list: output.append(f'</{list_type}>'); in_list = False; list_type = ''
            output.append(f'<p style="margin:4px 0">{_inline(line)}</p>')

        i += 1

    if in_list:
        output.append(f'</{list_type}>')

    return '\n'.join(output)


def _md_table_to_html(table_lines: list[str]) -> str:
    """Convierte un bloque de tabla markdown a tabla HTML limpia."""
    rows = [
        [cell.strip() for cell in line.strip().strip('|').split('|')]
        for line in table_lines
        if not re.match(r'^[\|\s\-:]+$', line)
    ]
    if not rows:
        return ''

    header = rows[0]
    body   = rows[1:]

    th_cells = ''.join(
        f'<th style="text-align:left;padding:8px 12px;background:#f0f0f0;border:1px solid #ccc;font-weight:bold">{_inline(h)}</th>'
        for h in header
    )
    tr_rows = ''
    for ridx, row in enumerate(body):
        bg = '#fafafa' if ridx % 2 else '#ffffff'
        td_cells = ''.join(
            f'<td style="padding:7px 12px;border:1px solid #ddd;background:{bg}">{_inline(c if ci < len(row) else "")}</td>'
            for ci, c in enumerate(row)
        )
        tr_rows += f'<tr>{td_cells}</tr>\n'

    return (
        '<table style="border-collapse:collapse;width:100%;margin:12px 0;font-size:13px">'
        f'<thead><tr>{th_cells}</tr></thead>'
        f'<tbody>{tr_rows}</tbody>'
        '</table>'
    )


def _inline(text: str) -> str:
    """Aplica formato inline de markdown: negrita, cursiva, código."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>',         text)
    text = re.sub(r'`(.+?)`',       r'<code style="background:#f0f0f0;padding:1px 4px;border-radius:3px;font-size:12px">\1</code>', text)
    return text


def get_my_email() -> str | None:
    """Obtiene el email del usuario actual en Outlook."""
    try:
        outlook = _get_outlook()
        ns = outlook.GetNamespace('MAPI')
        accounts = ns.Accounts
        if accounts.Count > 0:
            return accounts.Item(1).SmtpAddress
    except Exception:
        pass
    return None
