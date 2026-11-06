@echo off
rem Started by the Startup shortcut, or by hand. Keep each long-running
rem launcher hidden; service output and errors are written to the log files.
set "svc=%~dp0"
start "myshop-devserver" /min powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "%svc%start-devserver.ps1"
start "myshop-celery-worker" /min powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "%svc%start-celery-worker.ps1"
