"""
Envía un mensaje al chat de la reunión activa de Teams via UIA.
"""
import logging
import time

import comtypes
import comtypes.client
import win32api
import win32clipboard
import win32con
import win32gui
import win32process
import psutil

log = logging.getLogger(__name__)

DEFAULT_MESSAGE = (
    "\U0001f534 This meeting is being recorded for documentation purposes. "
    "If you prefer not to be recorded, please let the organizer know."
)


def _get_teams_pids() -> set[int]:
    pids = set()
    for proc in psutil.process_iter(['pid', 'name']):
        name = (proc.info.get('name') or '').lower()
        if 'teams' in name:
            pids.add(proc.info['pid'])
    return pids


def _get_meeting_hwnd(teams_pids: set[int]) -> int | None:
    """
    Devuelve el hwnd de la ventana de la reunión activa.
    Excluye ventanas de chat directo ('Chat | ...') y de calendario.
    """
    candidates: list[tuple[int, str]] = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return
        if pid not in teams_pids:
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        tl = title.lower()
        # Excluir ventanas que NO son la reunión
        if tl.startswith('chat |') or 'calendar' in tl:
            return
        candidates.append((hwnd, title))

    win32gui.EnumWindows(_cb, None)
    log.info(f"teams_chat: ventanas reunión candidatas: {[t for _, t in candidates]}")

    # Preferir ventana con palabras clave de reunión
    for hwnd, title in candidates:
        tl = title.lower()
        if any(k in tl for k in ('meeting', 'call', 'reuni', '| accenture', '| microsoft teams')):
            return hwnd
    return candidates[0][0] if candidates else None


def _click_chat_button(uia, hwnd: int) -> bool:
    """
    Busca el botón de Chat en la toolbar de la reunión via UIA y lo invoca.
    Funciona sin robar foco global porque usa InvokePattern.
    """
    try:
        from comtypes.gen import UIAutomationClient as uiac

        root = uia.ElementFromHandle(hwnd)
        if not root:
            return False

        cond_btn = uia.CreatePropertyCondition(
            uiac.UIA_ControlTypePropertyId, uiac.UIA_ButtonControlTypeId
        )
        buttons = root.FindAll(uiac.TreeScope_Descendants, cond_btn)
        log.info(f"teams_chat: {buttons.Length} botones en ventana reunión")

        chat_kw = ('chat', 'conversation', 'conversaci', 'show chat', 'mostrar')
        for i in range(buttons.Length):
            btn = buttons.GetElement(i)
            try:
                name = (btn.CurrentName or '').lower()
                if any(k in name for k in chat_kw):
                    log.info(f"teams_chat: botón chat encontrado: '{btn.CurrentName}'")
                    pattern = btn.GetCurrentPattern(uiac.UIA_InvokePatternId)
                    ip = pattern.QueryInterface(uiac.IUIAutomationInvokePattern)
                    ip.Invoke()
                    return True
            except Exception:
                continue

        log.warning("teams_chat: botón chat no encontrado en toolbar")
        return False

    except Exception as e:
        log.warning(f"teams_chat: error buscando botón chat — {e}")
        return False


def _find_chat_input(uia, hwnd: int):
    """Busca el input del chat de la reunión en el árbol UIA."""
    try:
        from comtypes.gen import UIAutomationClient as uiac

        root = uia.ElementFromHandle(hwnd)
        if not root:
            return None

        cond_edit = uia.CreatePropertyCondition(
            uiac.UIA_ControlTypePropertyId, uiac.UIA_EditControlTypeId
        )
        cond_doc = uia.CreatePropertyCondition(
            uiac.UIA_ControlTypePropertyId, uiac.UIA_DocumentControlTypeId
        )
        cond_any = uia.CreateOrCondition(cond_edit, cond_doc)
        elements = root.FindAll(uiac.TreeScope_Descendants, cond_any)

        count = elements.Length
        log.info(f"teams_chat: {count} controles Edit/Document encontrados")

        chat_keywords = ('type a message', 'escribe un mensaje', 'message', 'mensaje')
        last_edit = None
        for i in range(count):
            el = elements.GetElement(i)
            try:
                name = el.CurrentName or ''
                log.info(f"teams_chat: control [{i}] tipo={el.CurrentControlType} nombre='{name}'")
                if any(k in name.lower() for k in chat_keywords):
                    log.info(f"teams_chat: input encontrado por nombre: '{name}'")
                    return el
                if el.CurrentControlType == uiac.UIA_EditControlTypeId:
                    last_edit = el
            except Exception:
                continue

        if last_edit:
            log.info("teams_chat: usando último Edit como fallback")
        return last_edit

    except Exception as e:
        log.warning(f"teams_chat: error buscando input UIA — {e}")
        return None


def _send_text(element, text: str) -> bool:
    """Envía texto al elemento via ValuePattern o SetFocus + Ctrl+V."""
    try:
        from comtypes.gen import UIAutomationClient as uiac

        # SetFocus en el input de chat + pegar desde clipboard + Enter
        # ValuePattern.SetValue no funciona en el WebView2 de Teams (no dispara eventos del renderer)
        element.SetFocus()
        time.sleep(0.5)

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()

        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(ord('V'), 0, 0, 0)
        win32api.keybd_event(ord('V'), 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.4)
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        log.info("teams_chat: enviado via SetFocus + Ctrl+V + Enter")
        return True

    except Exception as e:
        log.warning(f"teams_chat: error enviando texto — {e}")
        return False


def send_recording_notice(message: str | None = None) -> bool:
    log.info("teams_chat: iniciando envío de aviso via UIA")

    # Re-read settings.json each call so the toggle takes effect without restart
    try:
        import json as _json
        from config import PROJECT_DIR
        _sf = PROJECT_DIR / 'settings.json'
        _s = _json.loads(_sf.read_text(encoding='utf-8')) if _sf.exists() else {}
        if not _s.get('teams_chat_notice_enabled', False):
            log.info("teams_chat: aviso desactivado en ajustes")
            return False
        _custom_msg = _s.get('teams_chat_message', '')
    except Exception:
        _custom_msg = ''

    try:
        from config import TEAMS_CHAT_MESSAGE
    except Exception:
        TEAMS_CHAT_MESSAGE = ''

    msg = (message or _custom_msg or TEAMS_CHAT_MESSAGE or DEFAULT_MESSAGE).strip()
    if not msg:
        return False

    try:
        comtypes.client.GetModule("UIAutomationCore.dll")
    except Exception as e:
        log.warning(f"teams_chat: no se pudo cargar UIAutomationCore — {e}")
        return False

    from comtypes.gen import UIAutomationClient as uiac

    teams_pids = _get_teams_pids()
    if not teams_pids:
        log.warning("teams_chat: Teams no está en ejecución")
        return False

    hwnd = _get_meeting_hwnd(teams_pids)
    if not hwnd:
        log.warning("teams_chat: ventana de reunión no encontrada")
        return False

    try:
        uia = comtypes.client.CreateObject(uiac.CUIAutomation, interface=uiac.IUIAutomation)
    except Exception as e:
        log.warning(f"teams_chat: no se pudo crear CUIAutomation — {e}")
        return False

    # 1º intento: buscar el input directamente (puede que el chat ya esté abierto)
    chat_input = _find_chat_input(uia, hwnd)

    if not chat_input:
        # Abrir panel de chat via UIA InvokePattern en el botón Chat
        opened = _click_chat_button(uia, hwnd)
        if opened:
            time.sleep(2.5)
            chat_input = _find_chat_input(uia, hwnd)

    if not chat_input:
        log.warning("teams_chat: input de chat no encontrado")
        return False

    return _send_text(chat_input, msg)
