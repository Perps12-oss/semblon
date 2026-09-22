@echo off
setlocal
rem Repo-root / MSI-install launcher: double-click = tk Home; args = power-user CLI.
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
set "INTERACTIVE=%ROOT%\tools\semblon-interactive.ps1"
set "MSI_MARKER=%ROOT%\.semblon-msi-install"
set "MSI_BOOTSTRAP=%ROOT%\tools\msi\bootstrap-install.ps1"
set "INSTALL_PS1=%ROOT%\tools\install-windows.ps1"

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

rem Prefer python -m. Never run stale semblon.exe when import fails.
if exist "%VENV_PY%" (
  "%VENV_PY%" -c "import semblon" >nul 2>&1
  if not errorlevel 1 (
    "%VENV_PY%" -m semblon %*
    exit /b %ERRORLEVEL%
  )
  echo Semblon package missing in .venv. Reinstalling editable install...
  "%VENV_PY%" -m pip install -e "%ROOT%"
  if errorlevel 1 (
    echo Reinstall failed. Run:
    echo   powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
    exit /b 1
  )
  "%VENV_PY%" -c "import semblon" >nul 2>&1
  if errorlevel 1 (
    echo Semblon still not importable after reinstall. Run:
    echo   powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
    exit /b 1
  )
  "%VENV_PY%" -m semblon %*
  exit /b %ERRORLEVEL%
)

rem MSI / first-run: create .venv before CLI args.
if exist "%MSI_MARKER%" if exist "%MSI_BOOTSTRAP%" (
  echo Semblon MSI: bootstrapping .venv (code only; no buffalo_l^)...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%MSI_BOOTSTRAP%" -Root "%ROOT%"
  if errorlevel 1 (
    echo MSI bootstrap failed. Install Python 3.12 ^(py launcher^), then retry.
    exit /b 1
  )
  if exist "%VENV_PY%" (
    "%VENV_PY%" -m semblon %*
    exit /b %ERRORLEVEL%
  )
)

if exist "%INSTALL_PS1%" (
  echo Semblon: .venv missing — running install-windows.ps1...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%INSTALL_PS1%" -Root "%ROOT%"
  if errorlevel 1 exit /b 1
  if exist "%VENV_PY%" (
    "%VENV_PY%" -m semblon %*
    exit /b %ERRORLEVEL%
  )
)

set "ALT_ROOT=%ROOT%\semblon"
set "ALT_PY=%ALT_ROOT%\.venv\Scripts\python.exe"
if exist "%ALT_PY%" (
  "%ALT_PY%" -c "import semblon" >nul 2>&1
  if not errorlevel 1 (
    "%ALT_PY%" -m semblon %*
    exit /b %ERRORLEVEL%
  )
  echo Semblon package missing in nested .venv. Reinstalling editable install...
  "%ALT_PY%" -m pip install -e "%ALT_ROOT%"
  if errorlevel 1 (
    echo Reinstall failed. Run tools\install-windows.ps1 from the checkout root.
    exit /b 1
  )
  "%ALT_PY%" -c "import semblon" >nul 2>&1
  if errorlevel 1 (
    echo Semblon still not importable after reinstall.
    exit /b 1
  )
  "%ALT_PY%" -m semblon %*
  exit /b %ERRORLEVEL%
)

echo Semblon: repo .venv not found.
echo From this folder, once:
echo   powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
echo Then double-click semblon.cmd, or run:  semblon.cmd process "D:\photos\dump"
exit /b 1
