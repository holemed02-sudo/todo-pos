@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 IMPORT_OLD_DATA.pyw
    goto END
)
where python >nul 2>nul
if not errorlevel 1 (
    python IMPORT_OLD_DATA.pyw
    goto END
)
echo Python 3.10 or newer is required.
:END
pause
