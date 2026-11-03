@echo off
rem Started by the Startup shortcut, or by hand. Both launchers refuse to
stack (busy port, existing worker), so a second run is a no-op.
set "svc=%~dp0"
start "myshop-devserver" /min powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%svc%start-devserver.ps1"
start "myshop-celery-worker" /min powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%svc%start-celery-worker.ps1"
