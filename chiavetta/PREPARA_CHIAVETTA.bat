@echo off
setlocal
cd /d "%~dp0"
title Preparazione chiavetta AI Python Offline
set "PY=%~dp0sistema\python\python.exe"
set "PYURL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
set "PYZIP=%~dp0sistema\python.zip"
if exist "%PY%" goto python_pronto

echo.
echo  Scarico Python portatile (circa 11 MB)...
if not exist "%~dp0sistema" mkdir "%~dp0sistema"
curl.exe -L --fail --retry 3 -o "%PYZIP%" "%PYURL%"
if errorlevel 1 del "%PYZIP%" 2>nul
if exist "%PYZIP%" goto estrai
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -UseBasicParsing -Uri $env:PYURL -OutFile $env:PYZIP"
if not exist "%PYZIP%" goto errore_download

:estrai
if not exist "%~dp0sistema\python" mkdir "%~dp0sistema\python"
tar -xf "%PYZIP%" -C "%~dp0sistema\python"
if not exist "%PY%" powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -LiteralPath $env:PYZIP -DestinationPath ($env:PYZIP -replace 'python.zip$','python')"
del "%PYZIP%" 2>nul
if not exist "%PY%" goto errore_estrai

:python_pronto
"%PY%" -B -E -s "%~dp0sistema\app\prepara.py" %*
echo.
pause
exit /b

:errore_download
echo.
echo  [X] Download di Python non riuscito. Controlla la connessione a internet e riprova.
pause
exit /b 1

:errore_estrai
echo.
echo  [X] Non riesco a estrarre Python. Riprova.
pause
exit /b 1
