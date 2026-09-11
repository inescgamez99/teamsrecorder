"""
Subprocess aislado para captura WASAPI loopback.
Protocolo stdout: 4 bytes samplerate (uint32 LE) + 4 bytes channels (uint32 LE) + stream float32 raw.

El header se escribe SOLO despues de abrir el stream con exito: si se escribiera
antes, el padre daria el loopback por arrancado y se quedaria esperando un audio
que nunca llega, grabando solo el microfono sin avisar.

Todo fallo se explica por stderr. El padre lo registra en el log; sin esto, el
worker moria en silencio y no habia forma de saber por que una reunion se grabo
sin el audio de los demas.
"""
import struct
import sys
import time


def fail(msg: str):
    sys.stderr.write(msg)
    sys.stderr.flush()
    sys.exit(1)


def main():
    try:
        import pyaudiowpatch as pyaudio
    except ImportError as e:
        fail(f"pyaudiowpatch no disponible: {e}")

    pa = pyaudio.PyAudio()
    try:
        wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError as e:
        pa.terminate()
        fail(f"WASAPI no disponible en este equipo: {e}")

    try:
        default_speakers = pa.get_device_info_by_index(wasapi_info['defaultOutputDevice'])
    except Exception as e:
        pa.terminate()
        fail(f"no se puede leer el dispositivo de salida por defecto: {e}")

    # Candidatos ordenados: el loopback del dispositivo de salida actual primero
    # y el resto despues. Antes solo se aceptaba el que coincidia por nombre y,
    # si ese estaba ocupado, se descartaba la captura teniendo otros validos.
    candidates = []
    if default_speakers.get('isLoopbackDevice', False):
        candidates.append(default_speakers)
    else:
        others = []
        for i in range(pa.get_device_count()):
            try:
                info = pa.get_device_info_by_index(i)
            except Exception:
                continue
            if not info.get('isLoopbackDevice', False):
                continue
            if default_speakers['name'] in info['name']:
                candidates.append(info)
            else:
                others.append(info)
        candidates.extend(others)

    if not candidates:
        pa.terminate()
        fail(f"no hay ningun dispositivo loopback (salida por defecto: "
             f"'{default_speakers['name']}')")

    errors = []
    for dev in candidates:
        n_ch = min(int(dev['maxInputChannels']), 2)
        if n_ch < 1:
            errors.append(f"'{dev['name']}': sin canales de entrada")
            continue
        sr = int(dev['defaultSampleRate'])

        def callback(in_data, frame_count, time_info, status):
            sys.stdout.buffer.write(in_data)
            sys.stdout.buffer.flush()
            return (None, pyaudio.paContinue)

        try:
            stream = pa.open(
                format=pyaudio.paFloat32,
                channels=n_ch,
                rate=sr,
                input=True,
                input_device_index=dev['index'],
                frames_per_buffer=int(sr * 0.1),
                stream_callback=callback,
            )
            stream.start_stream()
        except Exception as e:
            errors.append(f"'{dev['name']}': {e}")
            continue

        # Stream vivo: ahora si se puede prometer audio al padre.
        sys.stdout.buffer.write(struct.pack('<I', sr))
        sys.stdout.buffer.write(struct.pack('<I', n_ch))
        sys.stdout.buffer.flush()
        sys.stderr.write(f"loopback activo: '{dev['name']}' ({sr}Hz, {n_ch}ch)")
        sys.stderr.flush()

        try:
            while stream.is_active():
                time.sleep(0.1)
        except Exception:
            pass
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
        return

    pa.terminate()
    fail("ningun dispositivo loopback se pudo abrir -> " + " | ".join(errors))


if __name__ == '__main__':
    main()
