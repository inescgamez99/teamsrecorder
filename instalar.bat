@echo off
chcp 65001 >nul 2>&1
title TeamsRecorder - Instalador
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   TeamsRecorder - Instalacion
echo ========================================
echo.

rem -------------------------------------------------------
rem 1. Python
rem -------------------------------------------------------
echo [1/3] Comprobando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   Python no encontrado. Instalando via winget...
    winget install --id Python.Python.3.11 --source winget --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo   No se pudo instalar Python automaticamente.
        echo   Instalalo manualmente desde: https://www.python.org/downloads/
        echo   Marca "Add Python to PATH" durante la instalacion.
        echo.
        pause
        exit /b 1
    )
    echo   Python instalado. Recargando PATH...
    call RefreshEnv.cmd >nul 2>&1
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   Python %%v encontrado.
)
echo.

rem -------------------------------------------------------
rem 2. Node.js
rem -------------------------------------------------------
echo [2/3] Comprobando Node.js...
npm --version >nul 2>&1
if errorlevel 1 (
    echo   Node.js no encontrado. Instalando via winget...
    winget install --id OpenJS.NodeJS.LTS --source winget --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo   No se pudo instalar Node.js automaticamente.
        echo   Instalalo manualmente desde: https://nodejs.org/ ^(version LTS^)
        echo.
        pause
        exit /b 1
    )
    echo   Node.js instalado. Recargando PATH...
    for /f "tokens=*" %%p in ('where node 2^>nul') do set "NODEDIR=%%~dpp"
    set "PATH=!NODEDIR!;!NODEDIR!node_modules\.bin;%PATH%"
) else (
    for /f %%v in ('npm --version 2^>^&1') do echo   npm %%v encontrado.
)
echo.

rem -------------------------------------------------------
rem 3. Claude CLI
rem -------------------------------------------------------
echo [3/3] Comprobando Claude CLI...
claude --version >nul 2>&1
if errorlevel 1 (
    echo   Claude CLI no encontrado. Instalando...
    npm install -g @anthropic-ai/claude-code
    if errorlevel 1 (
        echo.
        echo   No se pudo instalar Claude CLI.
        echo   Intentalo manualmente: npm install -g @anthropic-ai/claude-code
        echo.
        pause
        exit /b 1
    )
    echo   Claude CLI instalado.
) else (
    for /f "tokens=*" %%v in ('claude --version 2^>^&1') do echo   Claude CLI %%v encontrado.
)
echo.

rem -------------------------------------------------------
rem Abrir Claude
rem -------------------------------------------------------
echo ========================================
echo   Todo listo. Abriendo Claude...
echo ========================================
echo.
echo   Cuando Claude arranque, escribe exactamente:
echo.
echo       /teamsrecorder
echo.
echo   Claude instalara el resto automaticamente.
echo   Pulsa cualquier tecla para continuar...
pause >nul
claude
