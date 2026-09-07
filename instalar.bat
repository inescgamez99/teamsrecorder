@echo off
chcp 65001 >nul 2>&1
title TeamsRecorder - Instalador
setlocal enabledelayedexpansion

rem -- Relanzarse dentro de cmd /k para que la ventana nunca se cierre sola --
if not defined TR_STARTED (
    set TR_STARTED=1
    cmd /k "%~f0"
    exit /b
)

echo.
echo ========================================
echo   TeamsRecorder - Instalacion
echo ========================================
echo.

rem -------------------------------------------------------
rem 1. Python  (usar "where" para evitar abrir la Tienda de Windows)
rem -------------------------------------------------------
echo [1/3] Comprobando Python...
where python >nul 2>&1
if errorlevel 1 (
    echo   Python no encontrado. Instalando via winget...
    winget install --id Python.Python.3.11 --source winget --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo   No se pudo instalar Python automaticamente.
        echo   Instalalo manualmente desde: https://www.python.org/downloads/
        echo   Marca "Add Python to PATH" durante la instalacion, cierra
        echo   esta ventana y vuelve a hacer doble clic en instalar.bat
        echo.
        goto :end
    )
    echo   Python instalado. Abre una nueva ventana y vuelve a ejecutar instalar.bat
    echo   para que Windows reconozca la instalacion.
    goto :end
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   Python %%v encontrado.
)
echo.

rem -------------------------------------------------------
rem 2. Node.js
rem -------------------------------------------------------
echo [2/3] Comprobando Node.js...
where npm >nul 2>&1
if errorlevel 1 (
    echo   Node.js no encontrado. Instalando via winget...
    winget install --id OpenJS.NodeJS.LTS --source winget --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo   No se pudo instalar Node.js automaticamente.
        echo   Instalalo manualmente desde: https://nodejs.org/ ^(version LTS^)
        echo   Cierra esta ventana y vuelve a hacer doble clic en instalar.bat
        echo.
        goto :end
    )
    echo   Node.js instalado. Abre una nueva ventana y vuelve a ejecutar instalar.bat.
    goto :end
) else (
    for /f %%v in ('npm --version 2^>^&1') do echo   npm %%v encontrado.
)
echo.

rem -------------------------------------------------------
rem 3. Claude CLI
rem -------------------------------------------------------
echo [3/3] Comprobando Claude CLI...
where claude >nul 2>&1
if errorlevel 1 (
    echo   Claude CLI no encontrado. Instalando...
    npm install -g @anthropic-ai/claude-code
    if errorlevel 1 (
        echo.
        echo   No se pudo instalar Claude CLI.
        echo   Intentalo manualmente: npm install -g @anthropic-ai/claude-code
        echo.
        goto :end
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

:end
echo.
echo   Pulsa cualquier tecla para cerrar esta ventana.
pause >nul
