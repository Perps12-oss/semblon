@echo off
setlocal
rem Repo-root launcher: double-click = folder picker + process; args = power-user CLI.
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
set "VENV_SEMBLON=%ROOT%\.venv\Scripts\semblon.exe"
set "INTERACTIVE=%ROOT%\tools\semblon-interactive.ps1"

if "%~1"=="" (
  if not exist "%INTERACTIVE%" (
    echo Semblon: missing %INTERACTIVE%
    echo.
    pause
    exit /b 1
  )
  powershell -NoProfile -ExecutionPolicy Bypass -Sta -File "%INTERACTIVE%" -Root "%ROOT%"
  if errorlevel 1 (
    echo.
    echo Semblon launcher failed. See messages above.
    pause
    exit /b 1
  )
  exit /b 0
)

if exist "%VENV_SEMBLON%" (
  "%VENV_SEMBLON%" %*
  exit /b %ERRORLEVEL%
)

if exist "%VENV_PY%" (
  "%VENV_PY%" -m semblon %*
  exit /b %ERRORLEVEL%
)

set "ALT_SEMBLON=%ROOT%\semblon\.venv\Scripts\semblon.exe"
set "ALT_PY=%ROOT%\semblon\.venv\Scripts\python.exe"
if exist "%ALT_SEMBLON%" (
  "%ALT_SEMBLON%" %*
  exit /b %ERRORLEVEL%
)
if exist "%ALT_PY%" (
  "%ALT_PY%" -m semblon %*
  exit /b %ERRORLEVEL%
)

echo Semblon: repo .venv not found.
echo From this folder, once:
echo   py -3.12 -m venv .venv
echo   .venv\Scripts\python.exe -m pip install -U pip
echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
echo   .venv\Scripts\python.exe -m pip install -e .
echo Then double-click semblon.cmd, or run:  semblon.cmd process "D:\photos\dump"
exit /b 1
