@echo off
cd /d "%~dp0"
if exist "%~dp0AbuFahad_AudioStudio\AbuFahad_AudioStudio.exe" (
    start "" "%~dp0AbuFahad_AudioStudio\AbuFahad_AudioStudio.exe"
    exit /b 0
)
start "" pythonw.exe "%~dp0app.py"
if errorlevel 1 (
    python "%~dp0app.py"
    pause
)
