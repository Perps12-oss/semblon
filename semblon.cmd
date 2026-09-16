@echo off
setlocal
rem Repo-root launcher: use local .venv without activating it.
set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "VENV_SEMBLON=%ROOT%.venv\Scripts\semblon.exe"

if exist "%VENV_SEMBLON%" (
  "%VENV_SEMBLON%" %*
  exit /b %ERRORLEVEL%
)

if exist "%VENV_PY%" (
  "%VENV_PY%" -m semblon %*
  exit /b %ERRORLEVEL%
)

echo Semblon: repo .venv not found.
echo From this folder, once:
echo   py -3.12 -m venv .venv
echo   .venv\Scripts\python.exe -m pip install -U pip
echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
echo   .venv\Scripts\python.exe -m pip install -e .
echo Then run:  semblon.cmd process "D:\photos\dump"
exit /b 1
