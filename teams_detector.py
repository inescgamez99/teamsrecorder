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

                # Teams 2.0: "<Meeting> | <Org> [| email] | Microsoft Teams"
                # Requiere 2+ pipes para evitar falsos positivos con chats
                # en ventana propia ("Persona | MS Teams", 1 pipe).
                if raw.endswith('Microsoft Teams') and raw.count('|') >= 2:
                    parts = [p.strip() for p in raw.split('|')]
                    first = parts[0].strip()
                    if first.lower() not in _TEAMS_GENERIC_PAGES:
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
        self._required_end      = max(required_confirmations * 10, 20) # polls fin conservador (20 = 1min)
        self._required_end_fast = 5   # polls fin rápido cuando título es genérico (5 = 15s)
        self._required_name_chg = max(required_confirmations * 5, 10)  # polls cambio de reunión (10 = 30s)
        self._in_call = False
        self._call_streak = 0
        self._call_streak_has_title = False  # True si algún poll del streak tuvo título
        self._no_call_streak = 0
        self._current_meeting_name: str | None = None
        self._name_change_candidate: str | None = None
        self._name_change_streak = 0
        self._title_went_generic = False  # título volvió a genérico mientras en llamada
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
                    audio_active = False
                    title_active = False
                    if pids:
                        audio_active = _check_audio_session(pids)
                        title_active, detected_name = _check_window_titles(pids)

                    # Para INICIAR: título O audio. Audio solo cubre llamadas 1:1 en
                    # Teams 2.0 donde el título siempre es genérico. Para evitar falsos
                    # positivos por notificaciones (< 18s) se exige 6 polls cuando es
                    # audio sin título, vs 2 polls cuando hay título confirmado.
                    # Para MANTENER: audio O título es suficiente.
                    active = title_active or audio_active

                    # Detectar cuándo el título vuelve a ser genérico (señal fuerte de fin)
                    if self._in_call and not title_active:
                        self._title_went_generic = True

                    if active:
                        self._call_streak += 1
                        if title_active:
                            self._call_streak_has_title = True
                        self._no_call_streak = 0
                    else:
                        self._no_call_streak += 1
                        self._call_streak = 0
                        self._call_streak_has_title = False
                        detected_name = None

                    required_now = self._required if self._call_streak_has_title else self._required * 3
                    if not self._in_call and self._call_streak >= required_now:
                        self._in_call = True
                        self._title_went_generic = False
                        self._call_streak_has_title = False
                        self._current_meeting_name = detected_name
                        log.info("Llamada Teams detectada")
                        if self.on_call_started:
                            threading.Thread(target=self.on_call_started, daemon=True,
                                             name='TeamsCallStarted').start()

                    elif (self._in_call and active
                          and detected_name and self._current_meeting_name
                          and detected_name != self._current_meeting_name):
                        # Nombre diferente — confirmar durante N polls antes de tratarlo como reunión nueva.
                        # Si el título ya fue genérico (llamada anterior terminó brevemente), confirmar
                        # más rápido: la reunión anterior terminó y empezó una nueva.
                        required_chg = (max(self._required, 2)
                                        if self._title_went_generic
                                        else self._required_name_chg)
                        if detected_name == self._name_change_candidate:
                            self._name_change_streak += 1
                        else:
                            self._name_change_candidate = detected_name
                            self._name_change_streak = 1
                        if self._name_change_streak >= required_chg:
                            recording_active = self.is_active_recording and self.is_active_recording()
                            if recording_active and not self._title_went_generic:
                                # Cambio de título dentro de la misma reunión (compartir pantalla, etc.)
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
                            self._title_went_generic = False
                            self._name_change_candidate = None
                            self._name_change_streak = 0

                    else:
                        # Nombre estable — resetear cualquier candidato de cambio pendiente
                        self._name_change_candidate = None
                        self._name_change_streak = 0

                    # Fin rápido: título claramente genérico + sin audio por _required_end_fast polls (15s)
                    # Cubre el caso de colgar y llamar rápido a otra persona (el streak largo nunca llegaría).
                    fast_end = (self._title_went_generic and not audio_active
                                and self._no_call_streak >= self._required_end_fast)
                    slow_end = self._no_call_streak >= self._required_end

                    if self._in_call and (fast_end or slow_end):
                        self._in_call = False
                        self._title_went_generic = False
                        self._current_meeting_name = None
                        self._name_change_candidate = None
                        self._name_change_streak = 0
                        log.info(f"Llamada Teams finalizada ({'rapido' if fast_end else 'normal'})")
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
