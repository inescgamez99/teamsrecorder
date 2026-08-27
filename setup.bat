@echo off
echo Instalando dependencias de TeamsRecorder...
pip install -r requirements.txt
if not exist .env (copy .env.example .env && echo Creado .env desde plantilla)
echo.
echo Verificando imports clave...
python -c "import sounddevice; print('sounddevice OK')"
python -c "import faster_whisper; print('faster-whisper OK')"
python -c "import pystray; print('pystray OK')"
python -c "import pyaudiowpatch; print('pyaudiowpatch OK')"
echo.
echo Verificando claude CLI...
claude --version
if errorlevel 1 (
    echo [AVISO] claude CLI no encontrado. Ejecuta:
    echo   npm install -g @anthropic-ai/claude-code
    echo   claude login
) else (
    echo claude CLI OK
)
echo.
echo Setup completado.
pause
