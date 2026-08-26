import logging
import threading
import time

from config import TEAMS_POLL_INTERVAL, TEAMS_REQUIRED_CONFIRMATIONS

log = logging.getLogger(__name__)

_TEAMS_PROCESSES = {'ms-teams.exe', 'teams.exe', 'msteams.exe'}

# Teams classic keywords
CALL_TITLE_KEYWORDS = [
    'microsoft teams meeting', 'teams meeting',
    'in a call', 'en llamada', 'teams call', 'en curso',
]

# Pages that appear in Teams 2.0 title bar when NOT in a call
_TEAMS_GENERIC_PAGES = {
    'microsoft teams', 'teams', 'calendar', 'chat', 'activity',
    'calls', 'files', 'apps', 'help', '', 'copilot',
}


def _teams_pids() -> list[int]:
    try:
        import psutil
        return [p.pid for p in psutil.process_iter(['name'])
                if (p.info['name'] or '').lower() in _TEAMS_PROCESSES]
    except Exception:
        return []


def _check_window_titles(pids: list[int]) -> tuple[bool, str | None]:
    try:
        import win32gui
        import win32process

        meeting_name = None
        found = False

        def cb(hwnd, _):
            nonlocal found, meeting_name
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in pids:
                    return
                raw = win32gui.GetWindowText(hwnd)
                if not raw:
                    return
                title_lower = raw.lower()

                # Teams classic: keyword match
                if any(kw in title_lower for kw in CALL_TITLE_KEYWORDS):
                    found = True
                    if '|' in raw:
                        candidate = raw.split('|')[0].strip()
                        if candidate.lower() not in _TEAMS_GENERIC_PAGES:
                            meeting_name = candidate
                    return

                # Teams 2.0: "<Meeting> | <Org> | <email@...> | Microsoft Teams"
                if raw.endswith('Microsoft Teams') and raw.count('|') >= 2:
                    parts = [p.strip() for p in raw.split('|')]
                    first = parts[0].strip()
                    has_email = any('@' in p for p in parts)
                    if first.lower() not in _TEAMS_GENERIC_PAGES and has_email:
                        found = True
                        if meeting_name is None:
                            meeting_name = first
            except Exception:
                pass

        win32gui.EnumWindows(cb, None)
        return found, meeting_name
    except Exception:
        return False, None


def _check_audio_session(pids: list[int]) -> bool:
    """Detecta si Teams tiene sesión de audio activa (State=1)."""
    try:
        from pycaw.pycaw import AudioUtilities
        for s in AudioUtilities.GetAllSessions():
            if s.Process and s.Process.pid in pids and s.State == 1:
                return True
        return False
    except Exception:
        return False


def get_current_meeting_name() -> str | None:
    pids = _teams_pids()
    if not pids:
        return None
    _, name = _check_window_titles(pids)
    return name


class TeamsCallDetector:
    def __init__(self, poll_interval=TEAMS_POLL_INTERVAL, required_confirmations=TEAMS_REQUIRED_CONFIRMATIONS):
        self._poll = poll_interval
        self._required          = required_confirmations              # polls para detectar inicio (2 = 6s)
        self._required_end      = max(required_confirmations * 20, 40) # polls para detectar fin (40 = 2min)
        self._required_name_chg = max(required_confirmations * 5, 10)  # polls para cambio de reunión (10 = 30s)
        self._in_call = False
        self._call_streak = 0
        self._no_call_streak = 0
        self._current_meeting_name: str | None = None
        self._name_change_candidate: str | None = None
        self._name_change_streak = 0
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self.on_call_started = None
        self.on_call_ended = None
        # Si está definido, se llama sin args y debe devolver bool.
        # Cuando devuelve True los cambios de nombre no disparan eventos (se absorben silenciosamente).
        self.is_active_recording = None

    @property
    def in_call(self) -> bool:
        return self._in_call

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='TeamsDetector')
        self._thread.start()
        log.info("TeamsCallDetector iniciado")

    def stop(self):
        self._stop_event.set()

    def _loop(self):
        _com_initialized = False
        try:
            import pythoncom
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            _com_initialized = True
        except Exception:
            pass

        try:
            while not self._stop_event.is_set():
                try:
                    pids = _teams_pids()
                    detected_name = None
                    if pids:
                        active = _check_audio_session(pids)
                        title_active, detected_name = _check_window_titles(pids)
                        if not active:
                            active = title_active
                    else:
                        active = False

                    if active:
                        self._call_streak += 1
                        self._no_call_streak = 0
                    else:
                        self._no_call_streak += 1
                        self._call_streak = 0
                        detected_name = None

                    if not self._in_call and self._call_streak >= self._required:
                        self._in_call = True
                        self._current_meeting_name = detected_name
                        log.info("Llamada Teams detectada")
                        if self.on_call_started:
                            threading.Thread(target=self.on_call_started, daemon=True,
                                             name='TeamsCallStarted').start()

                    elif (self._in_call and active
                          and detected_name and self._current_meeting_name
                          and detected_name != self._current_meeting_name):
                        # Nombre diferente — confirmar durante N polls antes de tratarlo como reunión nueva
                        if detected_name == self._name_change_candidate:
                            self._name_change_streak += 1
                        else:
                            self._name_change_candidate = detected_name
                            self._name_change_streak = 1
                        if self._name_change_streak >= self._required_name_chg:
                            recording_active = self.is_active_recording and self.is_active_recording()
                            if recording_active:
                                # Hay grabación en curso: el cambio de título es un evento de Teams
                                # (compartir pantalla, ver pantalla ajena, etc.) dentro de la misma
                                # reunión — sólo actualizar el nombre, sin disparar eventos.
                                log.info(f"Nombre actualizado (grabando): '{self._current_meeting_name}' → '{detected_name}'")
                            else:
                                log.info(f"Cambio de reunión confirmado: '{self._current_meeting_name}' → '{detected_name}'")
                                if self.on_call_ended:
                                    threading.Thread(target=self.on_call_ended, daemon=True,
                                                     name='TeamsCallEnded').start()
                                time.sleep(0.5)
                                if self.on_call_started:
                                    threading.Thread(target=self.on_call_started, daemon=True,
                                                     name='TeamsCallStarted').start()
                            self._current_meeting_name = detected_name
                            self._name_change_candidate = None
                            self._name_change_streak = 0

                    else:
                        # Nombre estable — resetear cualquier candidato de cambio pendiente
                        self._name_change_candidate = None
                        self._name_change_streak = 0

                    if self._in_call and self._no_call_streak >= self._required_end:
                        self._in_call = False
                        self._current_meeting_name = None
                        self._name_change_candidate = None
                        self._name_change_streak = 0
                        log.info("Llamada Teams finalizada")
                        if self.on_call_ended:
                            threading.Thread(target=self.on_call_ended, daemon=True,
                                             name='TeamsCallEnded').start()

                except Exception as e:
                    log.warning(f"TeamsDetector error: {e}")

                self._stop_event.wait(self._poll)
        finally:
            if _com_initialized:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
