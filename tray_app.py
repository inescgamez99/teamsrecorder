import logging
import queue
import re
import shutil
import threading
import time
from pathlib import Path

from config import MINUTES_DIR, RECORDINGS_DIR, PROJECT_DIR, get_ui_language

_STR = {
    'es': dict(
        record_now='Grabar ahora', stop='Parar grabacion',
        add_context='Añadir contexto a grabacion',
        cancel_recording='Cancelar grabacion (sin guardar)',
        view_minutes='Abrir la aplicacion',
        quit='Salir',
        recordings_queued='{n} grabaciones en cola',
        recordings_pending='{n} grabacion(es) pendiente(s) de procesar',
        action_items='Generando acciones...',
        ready='Minutas y acciones listas',
        transcription_failed='No se pudo transcribir la grabación. Revisa el log para más detalles.',
        minutes_failed='No se pudieron generar las minutas. Revisa el log para más detalles.',
    ),
    'en': dict(
        record_now='Record now', stop='Stop recording',
        add_context='Add context to recording',
        cancel_recording='Cancel recording (discard)',
        view_minutes='Open the app',
        quit='Quit',
        recordings_queued='{n} recordings in queue',
        recordings_pending='{n} recording(s) pending processing',
        action_items='Generating action items...',
        ready='Meeting minutes & action items ready',
        transcription_failed='Transcription failed. Check the log for details.',
        minutes_failed='Minutes generation failed. Check the log for details.',
    ),
}

log = logging.getLogger(__name__)


def _make_icon(color: str):
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill=color)
    return img


_ICON_IDLE       = _make_icon('#6c7086')
_ICON_RECORDING  = _make_icon('#f38ba8')
_ICON_PROCESSING = _make_icon('#f9e2af')


class TrayApp:
    def __init__(self, recorder, detector):
        self._recorder = recorder
        self._detector = detector
        self._icon = None
        self._pipeline_queue: queue.Queue = queue.Queue()
        self._pipeline_queued: list = []
        self._recording_start: float | None = None
        self._recording_path: Path | None = None
        self._ticker_stop = threading.Event()
        self._processing_msg: str = ''
        self._current_job: dict = {}

        self._session: dict | None = None
        self._session_lock = threading.RLock()
        self._MERGE_GRACE = 90

        threading.Thread(target=self._pipeline_loop, daemon=True, name='PipelineWorker').start()
        threading.Thread(target=self._recover_pending, daemon=True, name='PipelineRecovery').start()
        threading.Thread(target=self._notification_poller, daemon=True, name='NotificationPoller').start()

    def start(self):
        import pystray
        s = _STR.get(get_ui_language(), _STR['en'])
        self._icon = pystray.Icon(
            'TeamsRecorder',
            _ICON_IDLE,
            'TeamsRecorder',
            menu=pystray.Menu(
                pystray.MenuItem(lambda _: s['stop'] if self._recorder.is_recording else s['record_now'],
                                 self._toggle_recording),
                pystray.MenuItem(s['add_context'],
                                 self._add_context,
                                 visible=lambda _: bool(self._recorder.is_recording)),
                pystray.MenuItem(s['cancel_recording'],
                                 self._cancel_recording,
                                 visible=lambda _: bool(self._recorder.is_recording)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(s['view_minutes'], self._open_actions_ui, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(s['quit'], self._quit),
            )
        )
        self._icon.run()

    def _write_status(self):
        import json as _json
        import re as _re
        from config import PROJECT_DIR
        jobs = []
        if self._recording_start:
            elapsed = int(time.time() - self._recording_start)
            m, s = divmod(elapsed, 60)
            _rm = _re.match(r'\d{4}-\d{2}-\d{2}_(\d{2})-(\d{2})(?:_(.+))?', self._recording_path.stem) if self._recording_path else None
            _rtitle = _rm.group(3).replace('_', ' ').title() if (_rm and _rm.group(3)) else None
            _rtime  = f"{_rm.group(1)}:{_rm.group(2)}" if _rm else None
            jobs.append({'stage': 'recording', 'label': f'Recording {m:02d}:{s:02d}', 'elapsed': elapsed, 'pct': None,
                         'title': _rtitle, 'time': _rtime, 'step': 0, 'total_steps': 3, 'step_label': 'Grabando'})
        if self._processing_msg:
            pct_m = _re.search(r'(\d+)%', self._processing_msg)
            job = {'stage': 'processing', 'label': self._processing_msg, 'pct': int(pct_m.group(1)) if pct_m else None}
            job.update(self._current_job)
            jobs.append(job)
        for name in self._pipeline_queued:
            jobs.append({'stage': 'queued', 'label': name, 'pct': 0})
        try:
            (PROJECT_DIR / '.pipeline_status.json').write_text(_json.dumps({'jobs': jobs}), encoding='utf-8')
        except Exception:
            pass

    def set_recording(self, active: bool, path: Path = None):
        if active:
            self._recording_path = path
            self._recording_start = time.time()
            self._ticker_stop.clear()
            t = threading.Thread(target=self._ticker, daemon=True, name='TrayTicker')
            t.start()
            self._set_icon(_ICON_RECORDING, 'TeamsRecorder - Recording 00:00')
        else:
            self._recording_path = None
            self._ticker_stop.set()
            self._recording_start = None
            if self._processing_msg:
                self._set_icon(_ICON_PROCESSING, f'TeamsRecorder - {self._processing_msg}')
            else:
                self._set_icon(_ICON_IDLE, 'TeamsRecorder')
        self._write_status()
        try:
            if self._icon:
                self._icon.update_menu()
        except Exception:
            pass

    def set_processing(self, msg: str = ''):
        self._processing_msg = msg
        self._write_status()
        if not self._recording_start:
            if msg:
                self._set_icon(_ICON_PROCESSING, f'TeamsRecorder - {msg}')
            else:
                self._set_icon(_ICON_IDLE, 'TeamsRecorder')

    def _set_icon(self, img, tooltip: str):
        try:
            if self._icon:
                self._icon.icon = img
                self._icon.title = tooltip
        except Exception:
            pass

    def _ticker(self):
        while not self._ticker_stop.wait(1.0):
            if self._recording_start:
                elapsed = int(time.time() - self._recording_start)
                m, s = divmod(elapsed, 60)
                rec_str = f'Recording {m:02d}:{s:02d}'
                proc = self._processing_msg
                tooltip = f'TeamsRecorder - {rec_str}' + (f' | {proc}' if proc else '')
                try:
                    if self._icon:
                        self._icon.title = tooltip
                except Exception:
                    pass
            self._write_status()
            self._check_pending_notification()

    def _notification_poller(self):
        while True:
            time.sleep(5)
            self._check_pending_notification()

    def _check_pending_notification(self):
        notification_file = PROJECT_DIR / '.pending_notification.txt'
        if not notification_file.exists():
            return
        try:
            commits_text = notification_file.read_text(encoding='utf-8').strip()
            notification_file.unlink()
        except Exception:
            return
        if not commits_text:
            return
        threading.Thread(
            target=self._send_push_notification, args=(commits_text,),
            daemon=True, name='PushNotification',
        ).start()

    def _send_push_notification(self, commits_text: str):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                'send_update_email',
                PROJECT_DIR / 'hooks' / 'send_update_email.py',
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            ok = mod.send_update_email(commits_text)
            log.info(f"Push notification email {'enviado' if ok else 'fallido'}")
        except Exception as e:
            log.error(f"Push notification error: {e}")

    def _on_recording_done(self, wav_path: Path):
        self._register_part_recorded(wav_path)
        self._pipeline_queued.append(wav_path.stem)
        self._pipeline_queue.put(wav_path)
        self._write_status()
        n = self._pipeline_queue.qsize()
        if n > 1:
            s = _STR.get(get_ui_language(), _STR['en'])
            self._notify('TeamsRecorder', s['recordings_queued'].format(n=n))

    def _pipeline_loop(self):
        while True:
            wav_path = self._pipeline_queue.get()
            if wav_path is None:
                break
            try:
                self._pipeline_queued = [n for n in self._pipeline_queued if n != wav_path.stem]
                self._write_status()
                self._run_pipeline_sync(wav_path)
            except Exception as e:
                log.error(f"Pipeline error: {e}", exc_info=True)
                self.set_processing('')

    def _run_pipeline_sync(self, wav_path: Path):
        from storage import get_transcript_path, get_minutes_path
        from transcriber import transcribe
        from minutes_generator import generate_minutes, extract_title_from_minutes, save_minutes
        from html_exporter import export_to_html
        from actions_enricher import enrich_and_save

        s = _STR.get(get_ui_language(), _STR['en'])
        transcript_path = get_transcript_path(wav_path)
        partial_path = wav_path.parent / f"{wav_path.stem}.partial"

        detected_language = 'auto'

        _m = re.match(r'\d{4}-\d{2}-\d{2}_(\d{2})-(\d{2})(?:_(.+))?', wav_path.stem)
        _job_time  = f"{_m.group(1)}:{_m.group(2)}" if _m else ''
        _job_title = _m.group(3).replace('_', ' ').title() if (_m and _m.group(3)) else wav_path.stem
        self._current_job = {'title': _job_title, 'time': _job_time, 'step': 1, 'total_steps': 3, 'step_label': 'Transcribiendo', 'step_started': time.time()}

        lang_path = transcript_path.with_suffix('.lang')
        if transcript_path.exists():
            transcript_text = transcript_path.read_text(encoding='utf-8')
            if lang_path.exists():
                detected_language = lang_path.read_text().strip()
            log.info(f"Transcript ya existe, saltando: {transcript_path.name}")
        else:
            self.set_processing('Transcribiendo 0%...')
            segments = []

            def on_seg(line):
                segments.append(line)
                try:
                    partial_path.write_text('\n'.join(segments), encoding='utf-8')
                except Exception:
                    pass

            def on_progress(pct):
                self.set_processing(f'Transcribiendo {pct}%...')

            result = transcribe(wav_path, on_progress=on_progress, on_segment=on_seg)
            if partial_path.exists():
                partial_path.unlink()

            if not result:
                log.error(f"Transcripción fallida para {wav_path.name}")
                self._notify('TeamsRecorder ⚠', s['transcription_failed'])
                self.set_processing('')
                return

            transcript_text, detected_language = result
            lang_path.write_text(detected_language)

            if not transcript_text:
                log.error(f"Transcripción fallida para {wav_path.name}")
                self._notify('TeamsRecorder ⚠', s['transcription_failed'])
                self.set_processing('')
                return

            transcript_path.write_text(transcript_text, encoding='utf-8')

        self._register_part(wav_path, transcript_text, detected_language)

    # ── Sesión de reunión ─────────────────────────────────────────────────────

    def _norm_key(self, name: str) -> str:
        return re.sub(r'[^a-z0-9]', '', (name or '').lower())

    def _register_part_recorded(self, wav_path):
        _nm = re.match(r'\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_(.+)', wav_path.stem)
        key = self._norm_key(_nm.group(1).replace('_', ' ')) if _nm else ''
        with self._session_lock:
            sess = self._session
            if sess and sess.get('awaiting') and not sess.get('finalized'):
                sess['parts'].append(wav_path)
                sess['transcripts'][wav_path.stem] = None
                sess['awaiting'] = False
                sess['last_at'] = time.time()
                log.info("Reconexión: grabación añadida a la reunión anterior")
            else:
                if sess and not sess.get('finalized'):
                    threading.Thread(target=self._finalize_session, args=(sess,),
                                     daemon=True, name='FinalizeOld').start()
                self._session = {
                    'base_wav': wav_path, 'parts': [wav_path],
                    'transcripts': {wav_path.stem: None}, 'lang': 'auto',
                    'key': key, 'awaiting': False, 'finalized': False,
                    'timer': None, 'last_at': time.time(),
                }

    def _register_part(self, wav_path, transcript_text, detected_language):
        with self._session_lock:
            sess = self._session
            if (not sess or sess.get('finalized')
                    or wav_path.stem not in sess.get('transcripts', {})):
                _nm = re.match(r'\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_(.+)', wav_path.stem)
                key = self._norm_key(_nm.group(1).replace('_', ' ')) if _nm else ''
                sess = {
                    'base_wav': wav_path, 'parts': [wav_path],
                    'transcripts': {wav_path.stem: transcript_text}, 'lang': detected_language,
                    'key': key, 'awaiting': False, 'finalized': False,
                    'timer': None, 'last_at': time.time(),
                }
                self._session = sess
            else:
                sess['transcripts'][wav_path.stem] = transcript_text
                if detected_language and detected_language != 'auto':
                    sess['lang'] = detected_language
                sess['last_at'] = time.time()
            complete = (not sess.get('awaiting')
                        and all(v is not None for v in sess['transcripts'].values()))
        if complete:
            self._schedule_finalize(sess)
            self.set_processing('Transcrito — cerrando (por si te reconectas)')
        else:
            self.set_processing('Transcrito — esperando la reconexión')

    def _schedule_finalize(self, sess):
        with self._session_lock:
            t = sess.get('timer')
            if t:
                try: t.cancel()
                except Exception: pass
            timer = threading.Timer(self._MERGE_GRACE, self._finalize_session, args=(sess,))
            timer.daemon = True
            sess['timer'] = timer
            timer.start()

    def has_pending_session(self, meeting_name: str) -> bool:
        with self._session_lock:
            sess = self._session
            if not sess or sess.get('finalized'):
                return False
            key = self._norm_key(meeting_name)
            skey = sess.get('key') or ''
            if not key or not skey:
                return False
            return key == skey or key in skey or skey in key

    def request_continuation(self):
        with self._session_lock:
            sess = self._session
            if sess and not sess.get('finalized'):
                sess['awaiting'] = True
                t = sess.get('timer')
                if t:
                    try: t.cancel()
                    except Exception: pass
                    sess['timer'] = None
                log.info("Reunión marcada para continuar (esperando la reconexión)")

    def finalize_pending_now(self):
        with self._session_lock:
            sess = self._session
            if sess and not sess.get('finalized'):
                t = sess.get('timer')
                if t:
                    try: t.cancel()
                    except Exception: pass
                threading.Thread(target=self._finalize_session, args=(sess,),
                                 daemon=True, name='FinalizeNow').start()

    def _finalize_session(self, session):
        from storage import get_transcript_path, get_minutes_path
        from minutes_generator import generate_minutes, extract_title_from_minutes, save_minutes
        from html_exporter import export_to_html
        from actions_enricher import enrich_and_save

        with self._session_lock:
            if session.get('finalized'):
                return
            session['finalized'] = True
            _t = session.get('timer')
            if _t:
                try: _t.cancel()
                except Exception: pass

        parts = session.get('parts', [])
        tmap = session.get('transcripts', {})
        transcripts = [t for t in (tmap.get(p.stem) for p in parts) if t]
        if not parts or not transcripts:
            return
        wav_path = session['base_wav']
        detected_language = session.get('lang', 'auto')
        if len(transcripts) > 1:
            transcript_text = "\n\n[--- reconexión: continuación de la reunión ---]\n\n".join(transcripts)
            log.info(f"Cerrando reunión: {len(parts)} grabaciones unidas")
        else:
            transcript_text = transcripts[0]

        s = _STR.get(get_ui_language(), _STR['en'])
        transcript_path = get_transcript_path(wav_path)
        try:
            transcript_path.write_text(transcript_text, encoding='utf-8')
        except Exception:
            pass

        _mj = re.match(r'\d{4}-\d{2}-\d{2}_(\d{2})-(\d{2})(?:_(.+))?', wav_path.stem)
        self._current_job = {
            'title': (_mj.group(3).replace('_', ' ').title() if (_mj and _mj.group(3)) else wav_path.stem),
            'time': f"{_mj.group(1)}:{_mj.group(2)}" if _mj else '',
            'step': 2, 'total_steps': 3, 'step_label': 'Generando minutas', 'step_started': time.time(),
        }

        for extra in parts[1:]:
            try:
                if extra.exists():
                    (RECORDINGS_DIR / 'processed').mkdir(exist_ok=True)
                    shutil.move(str(extra), str((RECORDINGS_DIR / 'processed') / extra.name))
            except Exception as e:
                log.warning(f"mover parte extra {extra.name}: {e}")
            for aux in (extra.with_name(extra.stem + '_transcript.txt'),
                        extra.with_suffix('.lang'), extra.with_suffix('.partial'),
                        extra.with_suffix('.context')):
                try:
                    if aux.exists():
                        aux.unlink()
                except Exception:
                    pass

        extra_context = None
        context_path = wav_path.with_suffix('.context')
        if not context_path.exists():
            context_path = RECORDINGS_DIR / 'processed' / wav_path.with_suffix('.context').name
        if context_path.exists():
            try:
                extra_context = context_path.read_text(encoding='utf-8').strip() or None
                context_path.unlink()
            except Exception:
                pass

        _proj, _ctx_dir = None, None
        try:
            from project_context import prepare_context
            _nm = re.match(r'\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_(.+)', wav_path.stem)
            _mtg_name = _nm.group(1).replace('_', ' ') if _nm else ''
            _proj, _ctx_dir = prepare_context(transcript_text, _mtg_name)
            if _ctx_dir:
                log.info(f"Memoria de proyecto activa: {_proj.get('name')}")
        except Exception as e:
            log.warning(f"No se pudo preparar la memoria de proyecto: {e}")

        self._current_job.update({'step': 2, 'step_label': 'Generando minutas', 'step_started': time.time()})
        self.set_processing('Generando minutas...')
        raw = generate_minutes(transcript_text, wav_path, extra_context=extra_context,
                               language=detected_language, context_dir=_ctx_dir)
        if not raw:
            log.error("Generación de minutas fallida")
            self._notify('TeamsRecorder ⚠', s['minutes_failed'])
            self.set_processing('')
            return

        title, content = extract_title_from_minutes(raw)
        minutes_path = get_minutes_path(wav_path, title)
        save_minutes(content, minutes_path)

        if _proj:
            try:
                from project_context import add_meeting_summary
                _dm = re.match(r'(\d{4}-\d{2}-\d{2})', wav_path.stem)
                add_meeting_summary(_proj.get('id', ''), minutes_path.stem, title,
                                    _dm.group(1) if _dm else '', content)
            except Exception as e:
                log.warning(f"add_meeting_summary: {e}")

        try:
            transcript_copy = minutes_path.with_name(minutes_path.stem + '_transcript.txt')
            transcript_copy.write_text(transcript_text, encoding='utf-8')
        except Exception as e:
            log.warning(f"No se pudo copiar transcript a minutes: {e}")

        self._move_to_processed(wav_path, transcript_path)

        rec_time = None
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})', wav_path.stem)
        if m:
            from datetime import datetime as _dt
            rec_time = _dt(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                           int(m.group(4)), int(m.group(5)))

        name_m = re.match(r'\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_(.+)', wav_path.stem)
        rec_name = name_m.group(1).replace('_', ' ') if name_m else None
        if rec_name and rec_name.strip().lower() in ('manual', 'recording'):
            rec_name = None

        participants = []
        try:
            from outlook_sender import find_meeting_participants
            if rec_time:
                participants = find_meeting_participants(rec_time, meeting_name=rec_name)
                log.info(f"Participantes detectados: {len(participants)}")
        except Exception as e:
            log.warning(f"No se pudieron detectar participantes: {e}")

        try:
            mins_text = minutes_path.read_text(encoding='utf-8')
            title, _ = extract_title_from_minutes(mins_text) if mins_text.startswith('TITULO:') else (minutes_path.stem, mins_text)
            export_to_html(minutes_path, title, participants=participants, open_browser=False)
        except Exception as e:
            log.warning(f"Error exportando HTML: {e}")

        try:
            _pdf_dir = (_proj or {}).get('pdf_output_dir') if _proj else None
            if _pdf_dir and Path(_pdf_dir).is_dir():
                _html_p = MINUTES_DIR / f"{minutes_path.stem}.html"
                _pdf_p  = Path(_pdf_dir) / f"{minutes_path.stem}.pdf"
                _edge   = next((p for p in [
                    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                ] if Path(p).exists()), None)
                if _edge and _html_p.exists():
                    import subprocess as _sp
                    _sp.run([_edge, '--headless', '--disable-gpu', '--no-pdf-header-footer',
                             f'--print-to-pdf={_pdf_p}', f'file:///{_html_p}'],
                            capture_output=True, timeout=60)
                    if _pdf_p.exists():
                        log.info(f"PDF auto-exportado a {_pdf_p}")
        except Exception as _pdf_e:
            log.warning(f"PDF auto-export fallido: {_pdf_e}")

        s = _STR.get(get_ui_language(), _STR['en'])
        self._notify('TeamsRecorder', s['action_items'])
        self._current_job.update({'step': 3, 'step_label': 'Generando acciones', 'step_started': time.time()})
        self.set_processing(s['action_items'])

        _transcript_for_export = transcript_text

        def on_done():
            self._current_job = {}
            self.set_processing('')
            self._notify('TeamsRecorder', s['ready'])
            try:
                from project_exporter import export_to_project_folder
                if export_to_project_folder(minutes_path, _transcript_for_export):
                    log.info(f"Exportado a carpeta de proyecto: {minutes_path.stem}")
            except Exception as e:
                log.warning(f"project_exporter on_done: {e}")
            try:
                from app_window import open_app
                open_app(str(minutes_path))
            except Exception as e:
                log.warning(f"Error abriendo app: {e}")

        enrich_and_save(minutes_path, PROJECT_DIR.parent, on_done=on_done)

    def _move_to_processed(self, wav_path: Path, transcript_path: Path):
        dest = RECORDINGS_DIR / 'processed'
        dest.mkdir(exist_ok=True)
        if wav_path.exists():
            try:
                shutil.move(str(wav_path), str(dest / wav_path.name))
            except Exception as e:
                log.warning(f"No se pudo mover {wav_path.name}: {e}")
        if transcript_path.exists():
            try:
                transcript_path.unlink()
            except Exception as e:
                log.warning(f"No se pudo eliminar {transcript_path.name}: {e}")
        for suffix in ('.lang', '.partial', '.context'):
            aux = wav_path.with_suffix(suffix)
            if aux.exists():
                try:
                    aux.unlink()
                except Exception:
                    pass

    def _recover_pending(self):
        time.sleep(3)
        pending = []
        for wav in RECORDINGS_DIR.glob('*.wav'):
            stem_ts = wav.stem[:16]
            ts_compact = stem_ts[:4] + stem_ts[5:7] + stem_ts[8:10] + '_' + stem_ts[11:13] + stem_ts[14:16]
            has_minutes = any(MINUTES_DIR.glob(f"{ts_compact}_*.md"))
            if not has_minutes:
                pending.append(wav)

        if pending:
            s = _STR.get(get_ui_language(), _STR['en'])
            self._notify('TeamsRecorder', s['recordings_pending'].format(n=len(pending)))
            for wav in pending:
                self._pipeline_queue.put(wav)

    def _toggle_recording(self):
        if self._recorder.is_recording:
            self._recorder.stop()
            self.set_recording(False)
        else:
            from storage import get_recording_path
            path = get_recording_path('manual')
            # on_recording_stopped se asigna una sola vez al inicio (en main.py)
            self._recorder.start(path)
            self.set_recording(True, path)

    def _cancel_recording(self):
        if not self._recorder.is_recording:
            return
        self._recorder.cancel()
        self.set_recording(False)

    def _add_context(self):
        rec_path = self._recording_path
        if not rec_path:
            return
        threading.Thread(target=lambda: self._show_context_dialog(rec_path), daemon=True).start()

    def _show_context_dialog(self, rec_path: Path):
        import tkinter as tk
        from tk_thread import get_root, run_in_tk

        BG = '#1e1e2e'; CARD = '#313244'; FG = '#cdd6f4'; MUTED = '#a6adc8'
        BORDER = '#585b70'; BTN = '#89b4fa'

        def _create():
            root = get_root()
            top = tk.Toplevel(root)
            top.overrideredirect(True)
            top.attributes('-topmost', True)
            top.attributes('-alpha', 0.96)
            top.lift()
            W, H = 360, 130
            sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
            top.geometry(f"{W}x{H}+{sw - W - 20}+{sh - H - 64}")
            top.configure(bg=BORDER)

            frame = tk.Frame(top, bg=BG, padx=14, pady=10)
            frame.pack(fill='both', expand=True, padx=1, pady=1)

            tk.Label(frame, text="Contexto / objetivo de la reunion",
                     font=('Segoe UI', 10, 'bold'), fg=FG, bg=BG).pack(anchor='w')
            tk.Label(frame, text="Se usara al generar las minutas",
                     font=('Segoe UI', 8), fg=MUTED, bg=BG).pack(anchor='w', pady=(2, 6))

            entry = tk.Entry(frame, font=('Segoe UI', 9), bg=CARD, fg=FG,
                             relief='flat', insertbackground=FG, bd=4)
            entry.pack(fill='x')
            entry.focus_set()

            def save():
                ctx = entry.get().strip()
                if ctx:
                    try:
                        rec_path.with_suffix('.context').write_text(ctx, encoding='utf-8')
                        log.info(f"Contexto guardado para {rec_path.name}")
                    except Exception as e:
                        log.warning(f"No se pudo guardar contexto: {e}")
                top.destroy()

            entry.bind('<Return>', lambda _: save())
            entry.bind('<Escape>', lambda _: top.destroy())

            btn_f = tk.Frame(frame, bg=BG)
            btn_f.pack(fill='x', pady=(8, 0))
            tk.Button(btn_f, text="Guardar", font=('Segoe UI', 9, 'bold'),
                      bg=BTN, fg=BG, relief='flat', cursor='hand2',
                      command=save).pack(side='left', padx=(0, 8))
            tk.Button(btn_f, text="Cancelar", font=('Segoe UI', 9),
                      bg='#45475a', fg=FG, relief='flat', cursor='hand2',
                      command=top.destroy).pack(side='left')

        run_in_tk(_create)

    def _open_actions_ui(self):
        try:
            from app_window import open_app
            open_app()
        except Exception as e:
            log.error(f"Error abriendo app: {e}")

    def _notify(self, title: str, msg: str):
        try:
            if self._icon:
                self._icon.notify(msg, title)
        except Exception:
            pass

    def _quit(self):
        if self._recorder.is_recording:
            self._recorder.stop()
            self.set_recording(False)
            self._recorder.wait_for_save(60)
        self._pipeline_queue.put(None)
        self._detector.stop()
        try:
            if self._icon:
                self._icon.stop()
        except Exception:
            pass
