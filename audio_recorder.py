import logging
import subprocess
import struct
import sys
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from config import SAMPLE_RATE, PROJECT_DIR

log = logging.getLogger(__name__)

_LOOPBACK_WORKER = str(PROJECT_DIR / 'wasapi_loopback_worker.py')


class AudioRecorder:
    def __init__(self):
        self._mic_chunks: list[np.ndarray] = []
        self._loop_chunks: list[np.ndarray] = []
        self._loop_sr: int = SAMPLE_RATE
        self._loop_ch: int = 1
        self._mic_lock = threading.Lock()
        self._loop_lock = threading.Lock()
        self._recording = False
        self._output_path: Path | None = None
        self._save_event = threading.Event()
        self._loopback_proc: subprocess.Popen | None = None
        self._stream: sd.InputStream | None = None
        self._stereo_stream: sd.InputStream | None = None
        self._chunk_mic_pos: int = 0

        self.on_recording_stopped = None  # callable(wav_path)
        self.on_chunk = None              # callable(audio, offset_secs) — no usado en esta versión

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, output_path: Path):
        if self._recording:
            return
        # Si hay un guardado en curso del ciclo anterior, esperar a que termine
        # antes de limpiar los buffers, para no perder datos.
        if not self._save_event.is_set():
            self._save_event.wait(timeout=30)
        with self._mic_lock:
            self._mic_chunks.clear()
        with self._loop_lock:
            self._loop_chunks.clear()
        self._chunk_mic_pos = 0
        self._save_event.clear()
        self._output_path = output_path

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='float32',
            blocksize=int(SAMPLE_RATE * 0.1),
            callback=self._mic_cb,
        )
        self._stream.start()

        if not self._start_wasapi_loopback():
            self._start_stereo_mix_loopback()

        self._recording = True

        if self.on_chunk:
            t = threading.Thread(target=self._emit_chunks, daemon=True, name='ChunkEmitter')
            t.start()

        log.info(f"Recording started → {output_path}")

    def stop(self) -> Path | None:
        if not self._recording:
            return None
        self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if self._stereo_stream:
            try:
                self._stereo_stream.stop()
                self._stereo_stream.close()
            except Exception:
                pass
            self._stereo_stream = None

        if self._loopback_proc:
            try:
                self._loopback_proc.terminate()
                self._loopback_proc.wait(timeout=3)
            except Exception:
                pass
            self._loopback_proc = None

        # Capturar los datos ahora con el lock, antes de que un start() concurrente
        # haga clear() y borre los chunks de esta grabación.
        with self._mic_lock:
            mic_data = list(self._mic_chunks)
        with self._loop_lock:
            loop_data = list(self._loop_chunks)

        t = threading.Thread(
            target=self._process_and_save, args=(mic_data, loop_data),
            daemon=True, name='AudioProcessor',
        )
        t.start()
        return self._output_path

    def cancel(self) -> None:
        """Para la grabación y descarta el audio sin guardar ni procesar."""
        if not self._recording:
            return
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._stereo_stream:
            try:
                self._stereo_stream.stop()
                self._stereo_stream.close()
            except Exception:
                pass
            self._stereo_stream = None
        if self._loopback_proc:
            try:
                self._loopback_proc.terminate()
                self._loopback_proc.wait(timeout=3)
            except Exception:
                pass
            self._loopback_proc = None
        with self._mic_lock:
            self._mic_chunks.clear()
        with self._loop_lock:
            self._loop_chunks.clear()
        self._save_event.set()
        log.info("Recording cancelled — audio discarded")

    def wait_for_save(self, timeout: int = 60) -> bool:
        return self._save_event.wait(timeout=timeout)

    # ── private ──────────────────────────────────────────────────────────────

    def _mic_cb(self, indata, frames, time_info, status):
        with self._mic_lock:
            self._mic_chunks.append(indata.copy().flatten())

    def _start_wasapi_loopback(self) -> bool:
        try:
            proc = subprocess.Popen(
                [sys.executable, _LOOPBACK_WORKER],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            # Leer header con timeout para evitar deadlock si el worker se cuelga
            header_result = [b'']
            def _read_header():
                header_result[0] = proc.stdout.read(8)
            t = threading.Thread(target=_read_header, daemon=True)
            t.start()
            t.join(timeout=5.0)
            header = header_result[0]
            if not header or len(header) < 8:
                proc.terminate()
                return False
            sr = struct.unpack('<I', header[:4])[0]
            n_ch = struct.unpack('<I', header[4:8])[0]
            self._loop_sr = sr
            self._loop_ch = n_ch
            self._loopback_proc = proc
            t = threading.Thread(
                target=self._wasapi_reader, args=(proc, sr, n_ch),
                daemon=True, name='WasapiLoopbackReader',
            )
            t.start()
            log.info(f"WASAPI loopback started ({sr}Hz, {n_ch}ch)")
            return True
        except Exception as e:
            log.warning(f"WASAPI loopback failed: {e}")
            return False

    def _wasapi_reader(self, proc, sr, n_ch):
        bytes_per_frame = 4 * n_ch
        chunk_size = int(sr * 0.1) * bytes_per_frame
        try:
            while self._recording or proc.poll() is None:
                data = proc.stdout.read(chunk_size)
                if not data:
                    break
                arr = np.frombuffer(data, dtype=np.float32)
                with self._loop_lock:
                    self._loop_chunks.append(arr.copy())
        except Exception:
            pass

    def _start_stereo_mix_loopback(self) -> bool:
        keywords = ('stereo mix', 'mezcla estereo', 'what u hear', 'wave out mix', 'loopback')
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                name = dev['name'].lower()
                if dev['max_input_channels'] > 0 and any(k in name for k in keywords):
                    def cb(indata, frames, time_info, status):
                        with self._loop_lock:
                            self._loop_chunks.append(indata.copy().flatten())
                    self._stereo_stream = sd.InputStream(
                        device=i, samplerate=SAMPLE_RATE, channels=1,
                        dtype='float32', blocksize=int(SAMPLE_RATE * 0.1), callback=cb,
                    )
                    self._stereo_stream.start()
                    log.info(f"Stereo Mix loopback: {dev['name']}")
                    return True
        except Exception as e:
            log.warning(f"Stereo Mix failed: {e}")
        log.warning("No loopback device found — mic only")
        return False

    def _process_and_save(self, mic_data: list, loop_data: list):
        try:
            if not mic_data:
                log.warning("No mic data recorded")
                self._save_event.set()
                return

            mic = np.concatenate(mic_data)
            peak = np.abs(mic).max()
            if peak > 0:
                mic = mic * (0.8 / peak)

            final = mic
            if loop_data:
                loop = np.concatenate(loop_data)
                # promedio a mono si multi-canal
                if self._loop_ch > 1:
                    remainder = len(loop) % self._loop_ch
                    if remainder:
                        loop = loop[:-remainder]
                    loop = loop.reshape(-1, self._loop_ch).mean(axis=1)
                # resamplear si SR distinto
                if self._loop_sr != SAMPLE_RATE:
                    ratio = SAMPLE_RATE / self._loop_sr
                    new_len = int(len(loop) * ratio)
                    loop = np.interp(
                        np.linspace(0, len(loop) - 1, new_len),
                        np.arange(len(loop)),
                        loop,
                    )
                # descartar loopback si es ruido de fondo
                loop_peak = np.abs(loop).max()
                if loop_peak < 0.02 or len(loop) < len(mic) * 0.1:
                    log.info("Loopback descartado (peak bajo o duración insuficiente)")
                else:
                    # alinear longitudes
                    min_len = min(len(mic), len(loop))
                    final = mic[:min_len] + loop[:min_len]
                    peak = np.abs(final).max()
                    if peak > 1.0:
                        final = final * (0.9 / peak)

            path = self._output_path
            sf.write(str(path), final.astype(np.float32), SAMPLE_RATE, subtype='PCM_16')
            log.info(f"WAV guardado: {path}")

            if self.on_recording_stopped:
                threading.Thread(
                    target=self.on_recording_stopped, args=(path,), daemon=True,
                ).start()
        except Exception as e:
            log.error(f"Error guardando WAV: {e}", exc_info=True)
        finally:
            self._save_event.set()

    def _emit_chunks(self):
        import time
        while self._recording:
            time.sleep(60)
            if self.on_chunk and self._recording:
                self._emit_one_chunk()

    def _emit_one_chunk(self):
        with self._mic_lock:
            mic_data = list(self._mic_chunks)
        new_mic = mic_data[self._chunk_mic_pos:]
        if not new_mic:
            return
        samples = sum(len(c) for c in new_mic)
        if samples < SAMPLE_RATE * 10:
            return
        mic = np.concatenate(new_mic)
        peak = np.abs(mic).max()
        if peak > 0:
            mic = mic * (0.8 / peak)
        # offset en segundos: suma de samples anteriores dividido por sample rate
        offset_samples = sum(len(c) for c in mic_data[:self._chunk_mic_pos])
        offset = offset_samples / SAMPLE_RATE
        self._chunk_mic_pos += len(new_mic)
        if self.on_chunk:
            self.on_chunk(mic, offset)
