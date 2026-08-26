@echo off
echo Instalando dependencias de TeamsRecorder...
pip install -r requirements.txt
if not exist .env (copy .env.example .env && echo Creado .env desde plantilla)
echo.
echo Verificando imports clave...
python -c "import sounddevice; print('sounddevice OK')"
python -c "import faster_whisper; print('faster-whisper OK')"
python -c "import pystray; print('pystray OK')"
python -c "import anthropic; print('anthropic OK')"
python -c "import pyaudiowpatch; print('pyaudiowpatch OK')"
echo.
echo Setup completado.
pause
