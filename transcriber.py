import gc
import logging
import os
import threading
from pathlib import Path

from config import WHISPER_MODEL, WHISPER_LANGUAGE, OPENAI_API_KEY

log = logging.getLogger(__name__)

_model = None
_model_name: str | None = None
_model_lock = threading.Lock()

_LANG_REMAP = {
    'gl': 'es', 'ca': 'es', 'eu': 'es',
    'pt': 'es', 'it': 'es', 'fr': 'es', 'la': 'es',
    'cy': 'en', 'ga': 'en', 'gd': 'en',
}

# Modelos de mayor a menor. Si no hay memoria para el configurado se va bajando:
# una transcripción con un modelo pequeño es infinitamente mejor que ninguna.
_MODEL_LADDER = ['large-v3', 'large-v2', 'large', 'medium', 'small', 'base', 'tiny']

# Segundos por trozo al transcribir troceado. faster-whisper calcula el
# espectrograma del audio completo de una vez (~290 MB en complex128 para 16
# minutos); troceando, el pico baja en proporción.
_CHUNK_SECS = 300


def _is_memory_error(exc: Exception) -> bool:
    if isinstance(exc, MemoryError):
        return True
    msg = str(exc).lower()
    return any(s in msg for s in (
        'mkl_malloc', 'failed to allocate', 'unable to allocate',
        'bad_alloc', 'out of memory', 'cannot allocate',
    ))


def _fallback_plan(start: str) -> list[tuple[str, bool]]:
    """Intentos (modelo, troceado) del más capaz al más ligero."""
    try:
        models = _MODEL_LADDER[_MODEL_LADDER.index(start):]
    except ValueError:
        models = [start, 'small', 'base', 'tiny']
    plan = []
    for name in models:
        plan.append((name, False))
        plan.append((name, True))
    return plan


def _release_model():
    """Descarga el modelo actual. Imprescindible antes de probar uno más
    pequeño: si el grande sigue en memoria, el pequeño tampoco entra."""
    global _model, _model_name
    with _model_lock:
        _model = None
        _model_name = None
    gc.collect()


def _get_model(name: str | None = None):
    global _model, _model_name
    name = name or WHISPER_MODEL
    with _model_lock:
        if _model is None or _model_name != name:
            _model = None
            _model_name = None
            gc.collect()
            from faster_whisper import WhisperModel
            try:
                import psutil
                threads = psutil.cpu_count(logical=False) or os.cpu_count() or 4
            except Exception:
                threads = os.cpu_count() or 4
            log.info(f"Cargando modelo Whisper '{name}' (cpu_threads={threads})...")
            _model = WhisperModel(
                name, device='auto', compute_type='int8', cpu_threads=threads,
            )
            _model_name = name
            log.info("Modelo Whisper cargado")
        return _model


def _format_time(secs: float) -> str:
    m = int(secs // 60)
    s = int(secs % 60)
    return f"[{m:02d}:{s:02d}]"


def _remap(detected: str | None) -> str:
    detected = detected or 'es'
    if detected in _LANG_REMAP:
        remapped = _LANG_REMAP[detected]
        log.info(f"Idioma detectado '{detected}' → remap a '{remapped}'")
        detected = remapped
    return detected


_TRANSCRIBE_ARGS = dict(
    language=None,  # always auto-detect; forcing a language translates instead of transcribing
    beam_size=1,
    condition_on_previous_text=False,
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500, threshold=0.3),
)


def _transcribe_whole(model, audio_path: Path, on_progress=None, on_segment=None):
    segments, info = model.transcribe(str(audio_path), **_TRANSCRIBE_ARGS)
    detected = _remap(getattr(info, 'language', None))
    log.info(f"Idioma de la reunión: {detected}")

    lines = []
    duration = getattr(info, 'duration', None)
    for seg in segments:
        line = f"{_format_time(seg.start)} {seg.text.strip()}"
        lines.append(line)
        if on_segment:
            on_segment(line)
        if on_progress and duration:
            on_progress(min(int(seg.end / duration * 100), 100))
    return '\n'.join(lines), detected


def _transcribe_chunks(model, audio_path: Path, on_progress=None, on_segment=None):
    """Igual que _transcribe_whole pero por trozos, para acotar la memoria."""
    import numpy as np
    import soundfile as sf

    info = sf.info(str(audio_path))
    sr, total = info.samplerate, info.frames
    step = _CHUNK_SECS * sr
    duration = total / sr if sr else 0
    log.info(f"Transcribiendo por trozos de {_CHUNK_SECS}s ({duration/60:.1f} min en total)")

    lines: list[str] = []
    detected = None
    with sf.SoundFile(str(audio_path)) as f:
        pos = 0
        while pos < total:
            f.seek(pos)
            block = f.read(min(step, total - pos), dtype='float32', always_2d=False)
            if not len(block):
                break
            segments, cinfo = model.transcribe(np.ascontiguousarray(block), **_TRANSCRIBE_ARGS)
            if detected is None:
                detected = _remap(getattr(cinfo, 'language', None))
                log.info(f"Idioma de la reunión: {detected}")
            offset = pos / sr
            for seg in segments:
                line = f"{_format_time(offset + seg.start)} {seg.text.strip()}"
                lines.append(line)
                if on_segment:
                    on_segment(line)
            pos += len(block)
            del block
            gc.collect()
            if on_progress and duration:
                on_progress(min(int(pos / sr / duration * 100), 100))
    return '\n'.join(lines), (detected or 'es')


def _transcribe_local(audio_path: Path, on_progress=None, on_segment=None) -> tuple[str, str]:
    """Recorre el plan de fallback hasta que uno funcione.

    Antes, cualquier fallo saltaba directamente a la API de OpenAI y, sin
    OPENAI_API_KEY, la reunión se quedaba sin transcripción. Los fallos por
    memoria son recuperables: basta trocear el audio o usar un modelo menor.
    """
    plan = _fallback_plan(WHISPER_MODEL)
    last_exc: Exception | None = None

    for name, chunked in plan:
        if last_exc is not None:
            log.warning(
                f"Reintentando con modelo '{name}'{' troceado' if chunked else ''} "
                f"(el intento anterior se quedó sin memoria)"
            )
        try:
            model = _get_model(name)
            fn = _transcribe_chunks if chunked else _transcribe_whole
            return fn(model, audio_path, on_progress=on_progress, on_segment=on_segment)
        except Exception as e:
            last_exc = e
            if not _is_memory_error(e):
                raise
            log.warning(f"Sin memoria con '{name}'{' troceado' if chunked else ''}: {e}")
            _release_model()

    raise last_exc if last_exc else RuntimeError("transcripción local sin intentos")


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
