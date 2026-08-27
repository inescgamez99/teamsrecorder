---
name: teamsrecorder
description: Instala o actualiza TeamsRecorder en Windows. TeamsRecorder detecta llamadas de Microsoft Teams automáticamente, graba el audio y genera minutas estructuradas con IA (Whisper + Claude). Úsalo la primera vez para instalar, o cuando el administrador publique una actualización.
---

# TeamsRecorder — Instalación y actualización

Esta skill es exclusiva para Windows. Si el usuario no está en Windows, infórmale y termina.

## Paso 0 — Detectar estado actual

Comprueba si TeamsRecorder ya está instalado:

```powershell
Test-Path "$env:USERPROFILE\Documents\TeamsRecorder\.git"
```

- Si devuelve `True` → ir al **flujo de actualización**
- Si devuelve `False` → ir al **flujo de instalación**

---

## Flujo de instalación (primera vez)

### 1. Clonar el repositorio

```powershell
git clone https://github.com/inescgamez99/teamsrecorder "$env:USERPROFILE\Documents\TeamsRecorder"
```

### 2. Instalar dependencias Python

```powershell
pip install -r "$env:USERPROFILE\Documents\TeamsRecorder\requirements.txt"
```

Si hay errores de dependencias, muéstralos al usuario y ayúdale a resolverlos.

### 3. Configurar el fichero `.env`

```powershell
Copy-Item "$env:USERPROFILE\Documents\TeamsRecorder\.env.example" "$env:USERPROFILE\Documents\TeamsRecorder\.env"
```

Luego pide al usuario que abra `.env` (en su editor o con `notepad "$env:USERPROFILE\Documents\TeamsRecorder\.env"`) y rellene:

- `ANTHROPIC_API_KEY` — clave de Anthropic (https://console.anthropic.com). Necesaria para generar minutas.
- `WHISPER_MODEL` — modelo de transcripción. Recomendado: `medium`. Opciones: `tiny`, `base`, `small`, `medium`, `large`.
- `WHISPER_LANGUAGE` — idioma principal de las reuniones: `es` para español, `en` para inglés, o déjarlo vacío para autodetección.

Espera a que el usuario confirme que ha guardado el `.env` antes de continuar.

### 4. Configurar el arranque automático con Windows

```powershell
Start-Process -FilePath "$env:USERPROFILE\Documents\TeamsRecorder\install_autostart.bat" -Wait -WorkingDirectory "$env:USERPROFILE\Documents\TeamsRecorder"
```

Esto registra TeamsRecorder en el Programador de tareas de Windows para que arranque automáticamente.

### 5. Arrancar la app por primera vez

```powershell
Start-Process python -ArgumentList "main.py" -WorkingDirectory "$env:USERPROFILE\Documents\TeamsRecorder" -WindowStyle Hidden
```

Espera 3 segundos y verifica que el proceso está corriendo:

```powershell
Start-Sleep -Seconds 3
Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, StartTime
```

### 6. Confirmar instalación

Informa al usuario:
- El icono de TeamsRecorder aparecerá en la bandeja del sistema (esquina inferior derecha, puede estar oculto bajo la flecha `^`)
- La próxima vez que entre en una reunión de Teams, aparecerá un popup preguntando si quiere grabar
- Para actualizar en el futuro, solo tiene que ejecutar `/teamsrecorder` de nuevo

---

## Flujo de actualización (ya instalado)

### 1. Parar el daemon si está corriendo

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1
```

### 2. Actualizar el código

```powershell
git -C "$env:USERPROFILE\Documents\TeamsRecorder" pull
```

Muestra al usuario qué ficheros han cambiado.

### 3. Actualizar dependencias (por si han cambiado)

```powershell
pip install -r "$env:USERPROFILE\Documents\TeamsRecorder\requirements.txt" --quiet
```

### 4. Reiniciar el daemon

```powershell
Start-Process python -ArgumentList "main.py" -WorkingDirectory "$env:USERPROFILE\Documents\TeamsRecorder" -WindowStyle Hidden
Start-Sleep -Seconds 3
Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, StartTime
```

Confirma al usuario que TeamsRecorder está actualizado y corriendo con la última versión.
