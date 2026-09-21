@echo off
setlocal
rem Repo-root launcher: double-click = tk Home; args = power-user CLI.
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

rem Prefer python -m so a stale semblon.exe cannot hide a broken install.
if exist "%VENV_PY%" (
  "%VENV_PY%" -c "import semblon" >nul 2>&1
  if not errorlevel 1 (
    "%VENV_PY%" -m semblon %*
    exit /b %ERRORLEVEL%
  )
)

if exist "%VENV_SEMBLON%" (
  "%VENV_SEMBLON%" %*
  exit /b %ERRORLEVEL%
)

if exist "%VENV_PY%" (
  echo Semblon package missing in .venv. Reinstall:
  echo   powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
  exit /b 1
)

set "ALT_PY=%ROOT%\semblon\.venv\Scripts\python.exe"
set "ALT_SEMBLON=%ROOT%\semblon\.venv\Scripts\semblon.exe"
if exist "%ALT_PY%" (
  "%ALT_PY%" -c "import semblon" >nul 2>&1
  if not errorlevel 1 (
    "%ALT_PY%" -m semblon %*
    exit /b %ERRORLEVEL%
  )
)
if exist "%ALT_SEMBLON%" (
  "%ALT_SEMBLON%" %*
  exit /b %ERRORLEVEL%
)

echo Semblon: repo .venv not found.
echo From this folder, once:
echo   powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
echo Then double-click semblon.cmd, or run:  semblon.cmd process "D:\photos\dump"
exit /b 1
