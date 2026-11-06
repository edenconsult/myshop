$ErrorActionPreference = 'Stop'
$env:PYTHONUNBUFFERED = '1'
$common = Join-Path $PSScriptRoot 'service-common.ps1'
if (-not (Test-Path -LiteralPath $common -PathType Leaf)) {
    throw "Missing service helper: $common"
}
. $common

$context = New-MyshopServiceContext
$root = $context.Root
$logDir = $context.LogDir
$log = Join-Path $logDir ("celery-worker-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
# The running service holds its own log for writing only, so decisions go to a
# separate file: appending here would fail exactly when a service is up.

try {
    Assert-MyshopServicePrerequisites -Context $context -Worker
} catch {
    Write-MyshopServiceStatus -Context $context -Message "ERROR worker preflight: $($_.Exception.Message)"
    throw
}

# Two workers on one queue would double-consume imports, so refuse to stack.
$existing = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'myshopproject worker' } |
    Select-Object -First 1 -ExpandProperty ProcessId
if ($existing) {
    Write-MyshopServiceStatus -Context $context -Message "skip: worker already running as pid $existing"
    exit 0
}

try {
    Wait-MyshopDependencies -Context $context
} catch {
    Write-MyshopServiceStatus -Context $context -Message "ERROR worker dependencies: $($_.Exception.Message)"
    throw
}

Write-MyshopServiceStatus -Context $context -Message 'start: celery worker'

# cmd owns the redirection: Celery logs to stderr, and PowerShell's stream merge
# both re-encodes it and treats it as a terminating error.
& cmd.exe /c "cd /d `"$root`" && `"$root\.venv\Scripts\celery.exe`" -A myshopproject worker -l info --pool=solo >> `"$log`" 2>&1"
$result = $LASTEXITCODE
if ($result -ne 0) {
    Write-MyshopServiceStatus -Context $context -Message "ERROR worker exited with code $result; see $log"
}
exit $result
