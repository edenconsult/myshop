$env:PYTHONUNBUFFERED = '1'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$logDir = Join-Path $env:LOCALAPPDATA 'myshop\services\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("celery-worker-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))

# Two workers on one queue would double-consume imports, so refuse to stack.
$existing = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'myshopproject worker' } |
    Select-Object -First 1 -ExpandProperty ProcessId
if ($existing) {
    "skip: worker already running as pid $existing at $(Get-Date -Format 's')" |
        Out-File -FilePath $log -Append -Encoding ascii
    exit 0
}

"--- worker start $(Get-Date -Format 's') ---" | Out-File -FilePath $log -Append -Encoding ascii

# cmd owns the redirection: Celery logs to stderr, and PowerShell's stream merge
# both re-encodes it and treats it as a terminating error.
& cmd.exe /c "cd /d `"$root`" && `"$root\.venv\Scripts\celery.exe`" -A myshopproject worker -l info --pool=solo >> `"$log`" 2>&1"
exit $LASTEXITCODE
