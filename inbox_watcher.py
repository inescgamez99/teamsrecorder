import logging
import shutil
import subprocess
import threading
import time
from pathlib import Path

from config import INBOX_DIR, RECORDINGS_DIR

log = logging.getLogger(__name__)

AUDIO_EXTS = {'.wav', '.mp3', '.m4a', '.aac', '.ogg', '.flac', '.opus', '.wma'}
VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.wmv', '.ts'}
ALL_EXTS   = AUDIO_EXTS | VIDEO_EXTS


def _find_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which('ffmpeg')


class InboxWatcher:
    def __init__(self, on_wav_ready=None):
        self._on_wav_ready = on_wav_ready
        self._seen: set[Path] = set()
        self._ffmpeg = _find_ffmpeg()
        if not self._ffmpeg:
            log.warning("ffmpeg no encontrado — solo se procesarán .wav en inbox/")

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name='InboxWatcher').start()

    def _loop(self):
        while True:
            try:
                for f in list(INBOX_DIR.iterdir()):
                    if f.suffix.lower() not in ALL_EXTS:
                        continue
                    if f in self._seen or f.suffix == '.error':
                        continue
                    self._seen.add(f)
                    threading.Thread(
                        target=self._process_stable, args=(f,), daemon=True,
                        name=f'InboxProcess-{f.name}',
                    ).start()
            except Exception as e:
                log.warning(f"InboxWatcher error: {e}")
            time.sleep(5)

    def _is_stable(self, f: Path) -> bool:
        try:
            s1 = f.stat().st_size
            time.sleep(3)
            s2 = f.stat().st_size
            return s1 == s2 and s1 > 0
        except Exception:
            return False

    def _process_stable(self, f: Path):
        """Espera a que el fichero esté estable antes de procesar (en hilo propio)."""
        if not self._is_stable(f):
            self._seen.discard(f)
            return
        self._process(f)

    def _process(self, f: Path):
        from datetime import datetime
        ts = datetime.now().strftime('%Y-%m-%d_%H-%M')
        dest_name = f"{ts}_{f.name}"

        try:
            if f.suffix.lower() == '.wav' and not self._ffmpeg:
                wav_path = RECORDINGS_DIR / dest_name
                shutil.move(str(f), str(wav_path))
            else:
                if not self._ffmpeg:
                    log.warning(f"ffmpeg no disponible, no se puede convertir {f.name}")
                    return
                wav_name = dest_name.rsplit('.', 1)[0] + '.wav'
                wav_path = RECORDINGS_DIR / wav_name
                orig_dest = RECORDINGS_DIR / dest_name
                result = subprocess.run(
                    [self._ffmpeg, '-y', '-i', str(f),
                     '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
                     str(wav_path)],
                    capture_output=True, timeout=300,
                )
                if result.returncode != 0:
                    f.rename(f.parent / (f.name + '.error'))
                    log.error(f"ffmpeg falló convirtiendo {f.name}")
                    return
                shutil.move(str(f), str(orig_dest))

            log.info(f"Inbox: {f.name} → {wav_path.name}")
            if self._on_wav_ready:
                self._on_wav_ready(wav_path)
        except Exception as e:
            log.error(f"Error procesando {f.name}: {e}")
            try:
                f.rename(f.parent / (f.name + '.error'))
            except Exception:
                pass
