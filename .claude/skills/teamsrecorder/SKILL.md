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

### 3. Iniciar sesión en Claude Code

La app usa `claude -p` (Claude Code CLI) para generar las minutas. Comprueba si ya está disponible:

```powershell
claude --version
```

Si el comando no existe, instálalo:

```powershell
npm install -g @anthropic-ai/claude-code
```

Luego autentícate (abre el navegador):

```powershell
claude login
```

No se necesita ninguna API key en el `.env`. La autenticación de Claude Code es suficiente.

Opcionalmente, crea un `.env` para ajustar el modelo de Whisper:

```powershell
Copy-Item "$env:USERPROFILE\Documents\TeamsRecorder\.env.example" "$env:USERPROFILE\Documents\TeamsRecorder\.env"
```

Los únicos campos relevantes son:
- `WHISPER_MODEL` — Recomendado: `medium`. Opciones: `tiny`, `base`, `small`, `medium`, `large`.
- `WHISPER_LANGUAGE` — `es` para español, `en` para inglés, o vacío para autodetección.

Espera a que el usuario confirme que `claude login` ha ido bien antes de continuar.

### 4. Configurar el arranque automático con Windows

```powershell
Start-Process -FilePath "$env:USERPROFILE\Documents\TeamsRecorder\install_autostart.bat" -Wait -WorkingDirectory "$env:USERPROFILE\Documents\TeamsRecorder"
```

Esto registra TeamsRecorder en el Programador de tareas de Windows para que arranque automáticamente.

### 4b. Instalar los hooks de git

```powershell
Copy-Item "$env:USERPROFILE\Documents\TeamsRecorder\hooks\post-merge" "$env:USERPROFILE\Documents\TeamsRecorder\.git\hooks\post-merge"
Copy-Item "$env:USERPROFILE\Documents\TeamsRecorder\hooks\pre-push"   "$env:USERPROFILE\Documents\TeamsRecorder\.git\hooks\pre-push"
```

El hook `post-merge` reinicia la app automáticamente tras cada `git pull`. El hook `pre-push` solo es relevante para el owner del repo (notificaciones al equipo).

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

### 2b. Asegurarse de que los hooks están instalados

```powershell
Copy-Item "$env:USERPROFILE\Documents\TeamsRecorder\hooks\post-merge" "$env:USERPROFILE\Documents\TeamsRecorder\.git\hooks\post-merge" -Force
Copy-Item "$env:USERPROFILE\Documents\TeamsRecorder\hooks\pre-push"   "$env:USERPROFILE\Documents\TeamsRecorder\.git\hooks\pre-push"   -Force
```

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
