@echo off
REM EagleSignal — one-click NVIDIA dGPU recovery (self-elevating).
REM Double-click this file and approve the UAC prompt.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fix-nvidia-gpu.ps1"
echo.
pause
