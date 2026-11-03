@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
set "setup_mode=%~1"
if not defined setup_mode set "setup_mode=auto"

echo.
echo GitHub Tools environment setup
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_environment.ps1" -Mode "%setup_mode%"
set "install_result=%ERRORLEVEL%"

echo.
if "%install_result%"=="0" (
    echo Environment setup succeeded.
) else (
    echo Environment setup failed. See the error above.
)
echo.
pause
exit /b %install_result%
