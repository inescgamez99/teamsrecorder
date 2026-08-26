"""
Fusiona los WAVs de la reunion de hoy en un único archivo y lanza el pipeline completo.
Uso: python _merge_wavs.py wav1 wav2 wav3 ...
Los WAVs deben pasarse en orden cronológico.
"""
import sys
import logging
from pathlib import Path

import numpy as np
import soundfile as sf

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
log = logging.getLogger(__name__)


def merge_wavs(paths: list[Path], output: Path) -> Path:
    arrays = []
    target_sr = 16000

    for p in paths:
        log.info(f"Cargando {p.name} ({p.stat().st_size/1024/1024:.1f} MB)...")
        data, sr = sf.read(str(p), dtype='float32', always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != target_sr:
            log.info(f"  Resampleando {sr}Hz → {target_sr}Hz")
            new_len = int(len(data) * target_sr / sr)
            data = np.interp(
                np.linspace(0, len(data) - 1, new_len),
                np.arange(len(data)),
                data,
            )
        arrays.append(data.astype(np.float32))
        log.info(f"  {len(data)/target_sr:.1f}s de audio")

    merged = np.concatenate(arrays)
    peak = np.abs(merged).max()
    if peak > 0:
        merged = merged * (0.9 / peak)

    sf.write(str(output), merged, target_sr, subtype='PCM_16')
    total_min = len(merged) / target_sr / 60
    log.info(f"Fusionado: {output.name} ({total_min:.1f} min total)")
    return output


if __name__ == '__main__':
    from config import RECORDINGS_DIR

    if len(sys.argv) < 2:
        # Auto: coge los WAVs de hoy de las últimas 4 horas en orden cronológico
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(hours=4)
        candidates = []
        for d in (RECORDINGS_DIR, RECORDINGS_DIR / 'processed'):
            for w in d.glob('*.wav'):
                if datetime.fromtimestamp(w.stat().st_mtime) >= cutoff:
                    candidates.append(w)
        candidates.sort(key=lambda p: p.stat().st_mtime)
        if not candidates:
            log.error("No se encontraron WAVs recientes. Pasa las rutas como argumentos.")
            sys.exit(1)
        log.info(f"WAVs a fusionar ({len(candidates)}):")
        for c in candidates:
            log.info(f"  {c.parent.name}/{c.name}")
    else:
        candidates = [Path(a) for a in sys.argv[1:]]

    if len(candidates) < 2:
        log.error("Se necesitan al menos 2 WAVs para fusionar.")
        sys.exit(1)

    # Nombre del merged basado en el primero (timestamp más antiguo)
    first = candidates[0]
    output_name = first.stem.split('_')[0:2]  # YYYY-MM-DD_HH-MM
    ts = '_'.join(output_name)
    output = RECORDINGS_DIR / f"{ts}_merged.wav"

    merged_path = merge_wavs(candidates, output)

    log.info("Lanzando pipeline completo (transcripción + minutas)...")
    from transcriber import transcribe
    from minutes_generator import generate_minutes, extract_title_from_minutes, save_minutes
    from storage import get_transcript_path, get_minutes_path
    from html_exporter import export_to_html

    transcript_path = get_transcript_path(merged_path)
    segments = []

    def on_seg(line):
        segments.append(line)
        sys.stdout.write(f"\r{len(segments)} segmentos...")
        sys.stdout.flush()

    def on_prog(pct):
        sys.stdout.write(f"\rTranscribiendo {pct}%...   ")
        sys.stdout.flush()

    result = transcribe(merged_path, on_progress=on_prog, on_segment=on_seg)
    print()

    if not result:
        log.error("Transcripción fallida.")
        sys.exit(1)

    text, lang = result
    transcript_path.write_text(text, encoding='utf-8')
    log.info(f"Transcript: {transcript_path.name} (idioma: {lang})")

    log.info("Generando minutas con Claude...")
    raw = generate_minutes(text, merged_path, language=lang)
    if not raw:
        log.error("Generación de minutas fallida.")
        sys.exit(1)

    title, content = extract_title_from_minutes(raw)
    minutes_path = get_minutes_path(merged_path, title)
    save_minutes(content, minutes_path)
    log.info(f"Minutas: {minutes_path.name}")

    try:
        export_to_html(minutes_path, title, open_browser=True)
    except Exception as e:
        log.warning(f"HTML: {e}")

    log.info("Listo.")
