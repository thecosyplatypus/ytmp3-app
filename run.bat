@echo off
setlocal
cd /d "%~dp0"

if exist "YTMP3.exe" goto :exe
if exist "dist\YTMP3.exe" goto :dist_exe

echo No YTMP3.exe found - running from source instead.
echo (Build one with build.bat, or download the release from GitHub)
echo.

set "PY="
for %%C in ("py -3" python python3) do (
    if not defined PY (
        %%~C -c "import sys" >nul 2>&1 && set "PY=%%~C"
    )
)

if not defined PY (
    echo.
    echo  Python 3 was not found on this computer.
    echo.
    echo  Either download the ready-made YTMP3.exe from the GitHub Releases page,
    echo  or install Python 3.8+ from https://www.python.org/downloads/
    echo  (tick "Add python.exe to PATH" during setup).
    echo.
    pause
    exit /b 1
)

%PY% -c "import sys; sys.exit(0 if (3, 8) <= sys.version_info else 1)" >nul 2>&1
if errorlevel 1 (
    echo  "%PY%" is too old - this app needs Python 3.8 or newer.
    pause
    exit /b 1
)

echo  Using: %PY%
%PY% -c "import sys; print('  Interpreter:', sys.executable)"

%PY% -c "import yt_dlp, PyQt6" >nul 2>&1
if errorlevel 1 (
    echo  Installing dependencies, this may take a minute...
    %PY% -m pip install --upgrade --disable-pip-version-check yt-dlp PyQt6
    if errorlevel 1 (
        echo  Failed to install dependencies. Try manually:  %PY% -m pip install yt-dlp PyQt6
        pause
        exit /b 1
    )
)

echo.
%PY% main.py %*

pause
exit /b 0

:exe
echo Starting YTMP3.exe ...
start "" "%~dp0YTMP3.exe"
exit /b 0

:dist_exe
echo Starting dist\YTMP3.exe ...
start "" "%~dp0dist\YTMP3.exe"
exit /b 0
