@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Bitte zuerst die Entwicklungsumgebung einrichten:
    echo python -m venv .venv
    echo .venv\Scripts\python -m pip install -e .
    pause
    exit /b 1
)
start "Lyrics Studio" ".venv\Scripts\pythonw.exe" -m lyrics_studio
