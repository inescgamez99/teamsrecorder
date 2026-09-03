import logging
import os
import threading
from pathlib import Path

from config import WHISPER_MODEL, WHISPER_LANGUAGE, OPENAI_API_KEY

log = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()

_LANG_REMAP = {
    'gl': 'es', 'ca': 'es', 'eu': 'es',
    'pt': 'es', 'it': 'es', 'fr': 'es', 'la': 'es',
    'cy': 'en', 'ga': 'en', 'gd': 'en',
}


def _get_model():
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            try:
                import psutil
                threads = psutil.cpu_count(logical=False) or os.cpu_count() or 4
            except Exception:
                threads = os.cpu_count() or 4
            log.info(f"Cargando modelo Whisper '{WHISPER_MODEL}' (cpu_threads={threads})...")
            _model = WhisperModel(
                WHISPER_MODEL, device='auto', compute_type='int8', cpu_threads=threads,
            )
            log.info("Modelo Whisper cargado")
        return _model


def _format_time(secs: float) -> str:
    m = int(secs // 60)
    s = int(secs % 60)
    return f"[{m:02d}:{s:02d}]"


def _transcribe_local(audio_path: Path, on_progress=None, on_segment=None) -> tuple[str, str]:
    model = _get_model()
    lang = WHISPER_LANGUAGE
    segments, info = model.transcribe(
        str(audio_path),
        language=lang,
        beam_size=1,
        condition_on_previous_text=False,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500, threshold=0.3),
    )

    detected = getattr(info, 'language', 'es') or 'es'
    if detected in _LANG_REMAP:
        remapped = _LANG_REMAP[detected]
        log.info(f"Idioma detectado '{detected}' → remap a '{remapped}'")
        detected = remapped

    log.info(f"Idioma de la reunión: {detected}")

    lines = []
    duration = getattr(info, 'duration', None)
    for seg in segments:
        line = f"{_format_time(seg.start)} {seg.text.strip()}"
        lines.append(line)
        if on_segment:
            on_segment(line)
        if on_progress and duration:
            pct = min(int(seg.end / duration * 100), 100)
            on_progress(pct)

    return '\n'.join(lines), detected


def _transcribe_openai(audio_path: Path) -> tuple[str, str]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY no configurada")
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    with open(audio_path, 'rb') as f:
        result = client.audio.transcriptions.create(
            model='whisper-1',
            file=f,
            response_format='verbose_json',
            timestamp_granularities=['segment'],
        )
    lines = []
    for seg in result.segments:
        lines.append(f"{_format_time(seg.start)} {seg.text.strip()}")
    lang = getattr(result, 'language', 'es') or 'es'
    return '\n'.join(lines), lang


def transcribe(
    audio_path: Path,
    on_complete=None,
    on_progress=None,
    on_segment=None,
) -> tuple[str, str] | None:
    """
    Devuelve (transcript_text, detected_language) o None si falla.
    Si on_complete es callable, ejecuta en thread daemon — on_complete(text, lang).
    """
    def _run():
        try:
            log.info(f"Transcribiendo {audio_path.name}...")
            text, lang = _transcribe_local(audio_path, on_progress=on_progress, on_segment=on_segment)
        except Exception as e:
            log.warning(f"faster-whisper falló ({e}), intentando OpenAI API...")
            try:
                text, lang = _transcribe_openai(audio_path)
            except Exception as e2:
                log.error(f"Transcripción fallida: {e2}")
                if on_complete:
                    on_complete(None, 'es')
                return None
        if on_complete:
            on_complete(text, lang)
        return text, lang

    if on_complete:
        t = threading.Thread(target=_run, daemon=True, name='Transcriber')
        t.start()
        return None
    return _run()
