@echo off
setlocal
cd /d "%~dp0"

set "PY2EXE_DIR=%CD%"
for %%I in ("%PY2EXE_DIR%\..") do set "PROJECT_DIR=%%~fI"

set "APP_NAME=waltrone1-System-Diagnostics-Report"
set "ENTRY_FILE=%PROJECT_DIR%\app.py"
set "ICON_FILE=%PROJECT_DIR%\waltrone1-System-Diagnostics-Report.ico"
set "VERSION_FILE=%PROJECT_DIR%\version_info.txt"
set "SPEC_FILE=%PY2EXE_DIR%\waltrone1-System-Diagnostics-Report_py2exe.spec"
set "DIST_DIR=%PY2EXE_DIR%\dist"
set "WORK_DIR=%PY2EXE_DIR%\build"

cls
echo ==================================================
echo  %APP_NAME% - EXE Build
echo ==================================================
echo.
echo py2exe-Ordner:  %PY2EXE_DIR%
echo Projekt-Ordner: %PROJECT_DIR%
echo Startdatei:     %ENTRY_FILE%
echo Icon-Datei:     %ICON_FILE%
echo Version-Datei:  %VERSION_FILE%
echo Ausgabe-Ordner: %DIST_DIR%
echo.

if not exist "%ENTRY_FILE%" (
    echo FEHLER: Startdatei wurde nicht gefunden:
    echo %ENTRY_FILE%
    pause
    exit /b 1
)

if not exist "%ICON_FILE%" (
    echo FEHLER: Icon wurde nicht gefunden:
    echo %ICON_FILE%
    pause
    exit /b 1
)

if not exist "%VERSION_FILE%" (
    echo HINWEIS: version_info.txt wurde nicht gefunden.
    echo Die EXE wird trotzdem gebaut, aber ohne eigene Windows-Dateiversionsinformationen.
    echo Erwartet:
    echo %VERSION_FILE%
    echo.
)

where py >nul 2>nul
if %errorlevel% neq 0 (
    echo FEHLER: Python Launcher ^(py^) wurde nicht gefunden.
    echo Bitte Python 3 installieren und "Add python.exe to PATH" aktivieren.
    pause
    exit /b 1
)

echo [1/6] Virtuelle Python-Umgebung in py2exe anlegen / pruefen...
if not exist "%PY2EXE_DIR%\.venv\Scripts\python.exe" (
    py -3 -m venv "%PY2EXE_DIR%\.venv"
)

if not exist "%PY2EXE_DIR%\.venv\Scripts\python.exe" (
    echo FEHLER: Virtuelle Umgebung konnte nicht angelegt werden.
    pause
    exit /b 1
)

echo [2/6] Virtuelle Umgebung aktivieren...
call "%PY2EXE_DIR%\.venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo [3/6] Build-Pakete installieren / aktualisieren...
python -m pip install -U pip setuptools wheel
if errorlevel 1 goto :fail
pip install -r "%PY2EXE_DIR%\requirements.txt"
if errorlevel 1 goto :fail

echo [4/6] Alte Build-Ausgaben im py2exe-Ordner loeschen...
rmdir /s /q "%WORK_DIR%" 2>nul
rmdir /s /q "%DIST_DIR%" 2>nul

echo [5/6] EXE mit PyInstaller bauen...
pyinstaller --clean --noconfirm --distpath "%DIST_DIR%" --workpath "%WORK_DIR%" "%SPEC_FILE%"
if errorlevel 1 goto :fail

echo [6/6] Ergebnis pruefen...
if exist "%DIST_DIR%\%APP_NAME%.exe" (
    echo.
    echo FERTIG:
    echo %DIST_DIR%\%APP_NAME%.exe
    echo.
    echo Das Hauptverzeichnis bleibt sauber. Alle Build-Dateien liegen im Ordner py2exe.
    pause
    exit /b 0
)

echo FEHLER: Build wurde beendet, aber die EXE wurde nicht gefunden.
echo Erwartet wurde:
echo %DIST_DIR%\%APP_NAME%.exe
pause
exit /b 1

:fail
echo.
echo FEHLER: Build fehlgeschlagen. Bitte Meldungen oberhalb pruefen.
pause
exit /b 1
