@echo off
setlocal
cd /d "%~dp0"
title AI Python Offline
set "PY=%~dp0sistema\python\python.exe"
if not exist "%PY%" goto manca
"%PY%" -B -E -s "%~dp0sistema\app\assistente.py" %*
if errorlevel 1 pause
exit /b

:manca
echo.
echo  La chiavetta non e' ancora pronta.
echo  Prima avvia PREPARA_CHIAVETTA.bat su un PC con internet (solo la prima volta).
echo.
pause
