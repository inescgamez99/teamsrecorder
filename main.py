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

        _popup_active      = [False]   # guard para evitar popups múltiples
        _active_generation = [None]    # generación capturada en el último on_call_started
        _popup_lock        = threading.Lock()  # hace atómico el check-and-set de _popup_active

        def on_call_started():
            from teams_detector import get_current_meeting_name
            meeting = get_current_meeting_name() or 'reunion'

            try:
                is_reconnect = tray.has_pending_session(meeting)
            except Exception:
                is_reconnect = False

            with _popup_lock:
                if recorder.is_recording or _popup_active[0]:
                    return
                # call_declined bloquea reuniones nuevas, no reconexiones a la misma
                if not is_reconnect and detector.call_declined:
                    return
                _popup_active[0]      = True
                _active_generation[0] = detector.call_generation

            try:
                from popup import RecordingPopup
                try:
                    from config import get_ui_language
                    _lang = get_ui_language()
                except Exception:
                    _lang = 'es'

                def _start_recording(continuing):
                    _popup_active[0] = False
                    if continuing:
                        tray.request_continuation()
                    path = get_recording_path(meeting)
                    recorder.start(path)
                    tray.set_recording(True, path)
                    log.info(f"{'Continuando (reconexión)' if continuing else 'Grabación iniciada'}: {path.name}")

                if is_reconnect:
                    def on_yes():
                        _start_recording(continuing=True)

                    def on_no():
                        _popup_active[0] = False
                        tray.finalize_pending_now()
                        log.info("Reconexión: usuario NO continúa — se cierra la reunión anterior")

                    if _lang == 'en':
                        RecordingPopup(on_yes=on_yes, on_no=on_no,
                                       title='Same meeting detected',
                                       subtitle='Keep recording and merge with the previous one?',
                                       yes_label='  Keep  ', no_label='No, close').show()
                    else:
                        RecordingPopup(on_yes=on_yes, on_no=on_no,
                                       title='Misma reunión detectada',
                                       subtitle='¿Seguir grabando y unirla a la anterior?',
                                       yes_label='  Seguir  ', no_label='No, cerrar').show()
                else:
                    def on_yes():
                        _start_recording(continuing=False)

                    def on_no():
                        _popup_active[0] = False
                        detector.set_declined()
                        log.info("Usuario rechazó grabar")

                    RecordingPopup(on_yes=on_yes, on_no=on_no).show()

            except Exception as e:
                _popup_active[0] = False
                log.error(f"Error mostrando popup: {e}")

        def on_call_ended():
            if detector.call_generation != _active_generation[0]:
                log.info("on_call_ended ignorado: generación obsoleta")
                return
            if recorder.is_recording:
                recorder.stop()
                tray.set_recording(False)
                log.info("Grabación detenida: llamada Teams finalizada")

        detector.on_call_started     = on_call_started
        detector.on_call_ended       = on_call_ended
        detector.is_active_recording = lambda: recorder.is_recording

        recorder.on_recording_stopped = tray._on_recording_done

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
