param([int]$Port = 8000)

$env:PYTHONUNBUFFERED = '1'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$logDir = Join-Path $env:LOCALAPPDATA 'myshop\services\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("devserver-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
# The running service holds its own log for writing only, so decisions go to a
# separate file: appending here would fail exactly when a service is up.
$statusLog = Join-Path $logDir 'launcher.log'

# A second server cannot bind the same port, and its failed startup would look
# like a crash to whoever reads the log next.
$owner = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty OwningProcess
if ($owner) {
    "skip: port $Port already held by pid $owner at $(Get-Date -Format 's')" |
        Out-File -FilePath $statusLog -Append -Encoding ascii
    exit 0
}

"--- devserver start $(Get-Date -Format 's') port=$Port ---" |
    Out-File -FilePath $statusLog -Append -Encoding ascii

# cmd owns the redirection: Django logs to stderr, and PowerShell's stream merge
# both re-encodes it and treats it as a terminating error.
& cmd.exe /c "cd /d `"$root`" && `"$root\.venv\Scripts\python.exe`" manage.py runserver 127.0.0.1:$Port >> `"$log`" 2>&1"
exit $LASTEXITCODE
