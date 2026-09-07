@echo off
chcp 65001 >nul 2>&1
title TeamsRecorder - Instalador

echo.
echo ========================================
echo   TeamsRecorder - Instalacion
echo ========================================
echo.

claude --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Claude Code no esta instalado.
    echo.
    echo   Pasos para instalarlo:
    echo     1. Descarga Node.js desde https://nodejs.org/  ^(version LTS^)
    echo     2. En PowerShell: npm install -g @anthropic-ai/claude-code
    echo     3. En PowerShell: claude login
    echo     4. Vuelve a ejecutar este archivo
    echo.
    pause
    exit /b 1
)

echo   Abriendo Claude Code...
echo.
echo   Cuando Claude arranque, escribe exactamente:
echo.
echo       /teamsrecorder
echo.
echo   Claude instalara todo automaticamente.
echo   Pulsa cualquier tecla para continuar...
pause >nul
claude
