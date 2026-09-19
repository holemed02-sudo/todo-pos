@echo off
setlocal
cd /d "%~dp0"
echo ===== ToDo diagnostic =====
echo Folder: %CD%
echo.

where py
where python
echo.

if exist "%~dp0todo\app.py" (
    echo app.py: FOUND
) else (
    echo app.py: MISSING
)

echo.
echo Starting ToDo...
echo.

where py >nul 2>nul
if not errorlevel 1 (
    cd todo
    py -3 app.py
    goto END
)

where python >nul 2>nul
if not errorlevel 1 (
    cd todo
    python app.py
    goto END
)

echo Python not found.

:END
echo.
echo ===== Program ended =====
pause
