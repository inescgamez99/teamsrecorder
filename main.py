import logging
import os
import sys
import time
import threading
from pathlib import Path

from config import PROJECT_DIR, LOG_FILE, CLI_CONTROL_FILE, TEAMS_POLL_INTERVAL

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

LOCK_FILE = PROJECT_DIR / '.lock'


def _check_single_instance() -> bool:
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            import psutil
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                if 'python' in proc.name().lower():
                    log.error(f"Ya hay una instancia corriendo (PID {pid})")
                    return False
        except Exception:
            pass
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _start_cli_listener(recorder, tray, get_recording_path):
    def _loop():
        while True:
            time.sleep(0.5)
            try:
                if CLI_CONTROL_FILE.exists():
                    cmd = CLI_CONTROL_FILE.read_text().strip()
                    CLI_CONTROL_FILE.unlink()
                    if cmd == 'start' and not recorder.is_recording:
                        path = get_recording_path('cli')
                        recorder.on_recording_stopped = tray._on_recording_done
                        recorder.start(path)
                        tray.set_recording(True, path)
                        log.info("Grabación iniciada por CLI")
                    elif cmd == 'stop' and recorder.is_recording:
                        recorder.stop()
                        tray.set_recording(False)
                        log.info("Grabación detenida por CLI")
            except Exception as e:
                log.warning(f"CLI listener error: {e}")

    threading.Thread(target=_loop, daemon=True, name='CLIListener').start()


def main():
    if not _check_single_instance():
        sys.exit(1)

    try:
        from storage import ensure_directories, cleanup_old_recordings
        from audio_recorder import AudioRecorder
        from teams_detector import TeamsCallDetector
        from tray_app import TrayApp
        from inbox_watcher import InboxWatcher
        from storage import get_recording_path

        ensure_directories()
        cleanup_old_recordings()

        recorder  = AudioRecorder()
        detector  = TeamsCallDetector()
        tray      = TrayApp(recorder, detector)

        _popup_active   = [False]   # guard para evitar popups múltiples
        _last_popup_at  = [0.0]    # timestamp del último popup mostrado
        _POPUP_COOLDOWN = 600      # no repetir popup en la misma reunión (10 min)
        _popup_lock     = threading.Lock()  # hace atómico el check-and-set de _popup_active

        def on_call_started():
            import time as _time
            with _popup_lock:
                if recorder.is_recording or _popup_active[0]:
                    return
                if (_time.time() - _last_popup_at[0]) < _POPUP_COOLDOWN:
                    return
                _popup_active[0]  = True
                _last_popup_at[0] = _time.time()
            try:
                from popup import RecordingPopup
                from teams_detector import get_current_meeting_name

                meeting = get_current_meeting_name() or 'reunion'

                def on_yes():
                    _popup_active[0] = False
                    path = get_recording_path(meeting)
                    recorder.on_recording_stopped = tray._on_recording_done
                    recorder.start(path)
                    tray.set_recording(True, path)
                    log.info(f"Grabación iniciada: {path.name}")

                def on_no():
                    _popup_active[0] = False
                    log.info("Usuario rechazó grabar")

                RecordingPopup(on_yes=on_yes, on_no=on_no).show()
            except Exception as e:
                _popup_active[0] = False
                log.error(f"Error mostrando popup: {e}")

        def on_call_ended():
            if recorder.is_recording:
                recorder.stop()
                tray.set_recording(False)
                log.info("Grabación detenida: llamada Teams finalizada")

        detector.on_call_started    = on_call_started
        detector.on_call_ended      = on_call_ended
        detector.is_active_recording = lambda: recorder.is_recording

        detector.start()
        InboxWatcher(on_wav_ready=tray._on_recording_done).start()
        _start_cli_listener(recorder, tray, get_recording_path)

        log.info("TeamsRecorder iniciado")
        tray.start()  # bloquea el hilo principal (requerido por pystray en Windows)

    except Exception as e:
        log.error(f"Error fatal: {e}", exc_info=True)
    finally:
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass


if __name__ == '__main__':
    main()
