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
        view_minutes='Ver minutas y acciones',
        quit='Salir',
        recordings_queued='{n} grabaciones en cola',
        recordings_pending='{n} grabacion(es) pendiente(s) de procesar',
        action_items='Generando acciones...',
        ready='Minutas y acciones listas',
    ),
    'en': dict(
        record_now='Record now', stop='Stop recording',
        add_context='Add context to recording',
        view_minutes='View minutes and actions',
        quit='Quit',
        recordings_queued='{n} recordings in queue',
        recordings_pending='{n} recording(s) pending processing',
        action_items='Generating action items...',
        ready='Meeting minutes & action items ready',
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
        self._recording_start: float | None = None
        self._recording_path: Path | None = None
        self._ticker_stop = threading.Event()

        threading.Thread(target=self._pipeline_loop, daemon=True, name='PipelineWorker').start()
        threading.Thread(target=self._recover_pending, daemon=True, name='PipelineRecovery').start()

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
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(s['view_minutes'], self._open_actions_ui),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(s['quit'], self._quit),
            )
        )
        self._icon.run()

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
            self._set_icon(_ICON_IDLE, 'TeamsRecorder')

    def set_processing(self, msg: str = ''):
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
                self._set_icon(_ICON_RECORDING, f'TeamsRecorder - Recording {m:02d}:{s:02d}')

    def _on_recording_done(self, wav_path: Path):
        self._pipeline_queue.put(wav_path)
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

        transcript_path = get_transcript_path(wav_path)
        partial_path = wav_path.parent / f"{wav_path.stem}.partial"

        detected_language = 'auto'  # Claude auto-detects from transcript; overridden by Whisper detection below

        # Paso 1: transcribir (o saltar si ya existe)
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
                self.set_processing('')
                return

            transcript_text, detected_language = result
            lang_path.write_text(detected_language)

            if not transcript_text:
                log.error(f"Transcripción fallida para {wav_path.name}")
                self.set_processing('')
                return

            transcript_path.write_text(transcript_text, encoding='utf-8')

        # Leer contexto opcional del usuario (sidecar .context junto al WAV)
        extra_context = None
        context_path = wav_path.with_suffix('.context')
        if not context_path.exists():
            # También buscar en processed/ si el WAV ya fue movido
            context_path = RECORDINGS_DIR / 'processed' / wav_path.with_suffix('.context').name
        if context_path.exists():
            try:
                extra_context = context_path.read_text(encoding='utf-8').strip() or None
                context_path.unlink()
            except Exception:
                pass

        # Paso 2: generar minutas
        self.set_processing('Generando minutas...')
        raw = generate_minutes(transcript_text, wav_path, extra_context=extra_context, language=detected_language)
        if not raw:
            log.error("Generación de minutas fallida")
            self.set_processing('')
            return

        title, content = extract_title_from_minutes(raw)
        minutes_path = get_minutes_path(wav_path, title)
        save_minutes(content, minutes_path)

        # Guardar copia del transcript junto al .md para que regenerar siempre funcione
        try:
            transcript_copy = minutes_path.with_name(minutes_path.stem + '_transcript.txt')
            transcript_copy.write_text(transcript_text, encoding='utf-8')
        except Exception as e:
            log.warning(f"No se pudo copiar transcript a minutes: {e}")

        # Mover WAV + transcript original a processed/
        self._move_to_processed(wav_path, transcript_path)

        # Extraer fecha/hora de la grabación para buscar en calendario
        rec_time = None
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})', wav_path.stem)
        if m:
            from datetime import datetime as _dt
            rec_time = _dt(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                           int(m.group(4)), int(m.group(5)))

        # Buscar participantes en calendario de Outlook
        participants = []
        try:
            from outlook_sender import find_meeting_participants
            if rec_time:
                participants = find_meeting_participants(rec_time)
                log.info(f"Participantes detectados: {len(participants)}")
        except Exception as e:
            log.warning(f"No se pudieron detectar participantes: {e}")

        # Exportar a HTML (sin abrir navegador automáticamente)
        try:
            mins_text = minutes_path.read_text(encoding='utf-8')
            title, _ = extract_title_from_minutes(mins_text) if mins_text.startswith('TITULO:') else (minutes_path.stem, mins_text)
            export_to_html(minutes_path, title, participants=participants, open_browser=False)
        except Exception as e:
            log.warning(f"Error exportando HTML: {e}")

        s = _STR.get(get_ui_language(), _STR['en'])
        self._notify('TeamsRecorder', s['action_items'])

        # Paso 3: enriquecer acciones y notificar
        _transcript_for_export = transcript_text  # captura para el closure

        def on_done():
            self.set_processing('')
            self._notify('TeamsRecorder', s['ready'])
            # Exportar a carpeta de proyecto si está configurada
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
        # El transcript ya fue copiado a minutes/ — lo eliminamos aquí en lugar de moverlo
        if transcript_path.exists():
            try:
                transcript_path.unlink()
            except Exception as e:
                log.warning(f"No se pudo eliminar {transcript_path.name}: {e}")
        # Limpiar archivos auxiliares del stem
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
            stem_ts = wav.stem[:16]  # YYYY-MM-DD_HH-MM (16 chars)
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
            self._recorder.on_recording_stopped = self._on_recording_done
            self._recorder.start(path)
            self.set_recording(True, path)

    def _add_context(self):
        """Muestra un diálogo para añadir contexto/objetivo a la grabación en curso."""
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
