"""
Subprocess aislado para captura WASAPI loopback.
Protocolo stdout: 4 bytes samplerate (uint32 LE) + 4 bytes channels (uint32 LE) + stream float32 raw.
"""
import struct
import sys
import time


def main():
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        sys.exit(1)

    pa = pyaudio.PyAudio()
    try:
        wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        pa.terminate()
        sys.exit(1)

    default_speakers = None
    try:
        default_speakers = pa.get_device_info_by_index(wasapi_info['defaultOutputDevice'])
    except Exception:
        pa.terminate()
        sys.exit(1)

    if not default_speakers.get('isLoopbackDevice', False):
        # Buscar dispositivo loopback correspondiente
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get('isLoopbackDevice', False) and default_speakers['name'] in info['name']:
                default_speakers = info
                break
        else:
            pa.terminate()
            sys.exit(1)

    sr = int(default_speakers['defaultSampleRate'])
    n_ch = min(int(default_speakers['maxInputChannels']), 2)
    if n_ch < 1:
        pa.terminate()
        sys.exit(1)
    chunk = int(sr * 0.1)

    sys.stdout.buffer.write(struct.pack('<I', sr))
    sys.stdout.buffer.write(struct.pack('<I', n_ch))
    sys.stdout.buffer.flush()

    def callback(in_data, frame_count, time_info, status):
        sys.stdout.buffer.write(in_data)
        sys.stdout.buffer.flush()
        return (None, pyaudio.paContinue)

    stream = pa.open(
        format=pyaudio.paFloat32,
        channels=n_ch,
        rate=sr,
        input=True,
        input_device_index=default_speakers['index'],
        frames_per_buffer=chunk,
        stream_callback=callback,
    )
    stream.start_stream()

    try:
        while stream.is_active():
            time.sleep(0.1)
    except Exception:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


if __name__ == '__main__':
    main()
