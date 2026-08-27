@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PSEXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "LAUNCH=%~dp0VPS-Control-v7-launch.ps1"
set "EXTRA="
if /I "%~1"=="--demo" set "EXTRA=-Demo"

if not exist "%PSEXE%" (
  echo Windows PowerShell 5.1 was not found:
  echo %PSEXE%
  pause
  exit /b 2
)
if not exist "%LAUNCH%" (
  echo VPS-Control-v7-launch.ps1 was not found next to this launcher.
  pause
  exit /b 3
)

"%PSEXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -STA -File "%LAUNCH%" %EXTRA%
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" exit /b 0

echo.
echo VPS Control Center failed to start. Exit code: %RC%
echo See VPS-Control-Data\logs\launch.log or the custom data folder selected in V7.
pause
exit /b %RC%
