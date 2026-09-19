@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -B -m unittest discover -s tests -v
    goto END
)
python -B -m unittest discover -s tests -v
:END
pause
