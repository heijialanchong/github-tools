@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

echo.
echo GitHub Tools - Anaconda/pip environment setup
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0anaconda_pip_install.ps1"
set "install_result=%ERRORLEVEL%"

echo.
if "%install_result%"=="0" (
    echo Anaconda/pip environment setup succeeded.
) else (
    echo Anaconda/pip environment setup failed. See the error above.
)
echo.
pause
exit /b %install_result%
