param([int]$Port = 8000)

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
$log = Join-Path $logDir ("devserver-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
# The running service holds its own log for writing only, so decisions go to a
# separate file: appending here would fail exactly when a service is up.

try {
    Assert-MyshopServicePrerequisites -Context $context
} catch {
    Write-MyshopServiceStatus -Context $context -Message "ERROR devserver preflight: $($_.Exception.Message)"
    throw
}

# A second server cannot bind the same port, and its failed startup would look
# like a crash to whoever reads the log next.
$owner = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty OwningProcess
if ($owner) {
    Write-MyshopServiceStatus -Context $context -Message "skip: devserver port $Port already held by pid $owner"
    exit 0
}

try {
    Wait-MyshopDependencies -Context $context
} catch {
    Write-MyshopServiceStatus -Context $context -Message "ERROR devserver dependencies: $($_.Exception.Message)"
    throw
}

Write-MyshopServiceStatus -Context $context -Message "start: devserver port=$Port"

# cmd owns the redirection: Django logs to stderr, and PowerShell's stream merge
# both re-encodes it and treats it as a terminating error.
& cmd.exe /c "cd /d `"$root`" && `"$root\.venv\Scripts\python.exe`" manage.py runserver 127.0.0.1:$Port >> `"$log`" 2>&1"
$result = $LASTEXITCODE
if ($result -ne 0) {
    Write-MyshopServiceStatus -Context $context -Message "ERROR devserver exited with code $result; see $log"
}
exit $result
