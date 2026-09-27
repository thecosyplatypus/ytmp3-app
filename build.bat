@echo off
setlocal
cd /d "%~dp0"

rem Builds a standalone dist\YTMP3.exe (no Python needed on the target PC).

set "PY="
for %%C in ("py -3" python python3) do (
    if not defined PY (
        %%~C -c "import sys" >nul 2>&1 && set "PY=%%~C"
    )
)
if not defined PY (
    echo Python 3.8+ is required to BUILD the app. Install from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Building with %PY% ...
%PY% -m pip install --upgrade --disable-pip-version-check pyinstaller yt-dlp PyQt6

%PY% -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name YTMP3 ^
    --collect-all yt_dlp ^
    --exclude-module PyQt6.QtWebEngineCore ^
    --exclude-module PyQt6.QtWebEngineWidgets ^
    --exclude-module PyQt6.QtQuick ^
    --exclude-module PyQt6.Qt3DCore ^
    main.py

if errorlevel 1 (
    echo.
    echo Build FAILED.
    pause
    exit /b 1
)

echo.
echo Done: %CD%\dist\YTMP3.exe
echo Ship that single file to your friends - no Python required.
pause
