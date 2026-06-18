@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Export-WeChatRecords.ps1" %*
echo.
pause
