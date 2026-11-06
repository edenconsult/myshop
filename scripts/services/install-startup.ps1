param([switch]$Remove)

# Alternative to the Task Scheduler route, for the case where the scheduler
# cannot launch the action at all: Explorer starts the shortcut in this folder
# when the user signs in, and no task engine is involved.

$startup = [Environment]::GetFolderPath('Startup')
$link = Join-Path $startup 'myshop-services.lnk'

if ($Remove) {
    if (Test-Path $link) {
        Remove-Item $link -Force
        "removed $link"
    } else {
        "nothing to remove at $link"
    }
    exit 0
}

$cmd = Join-Path $PSScriptRoot 'start-both.cmd'
if (-not (Test-Path $cmd)) {
    throw "$cmd is missing; restore it from git before installing the shortcut"
}

$common = Join-Path $PSScriptRoot 'service-common.ps1'
if (-not (Test-Path -LiteralPath $common -PathType Leaf)) {
    throw "Missing service helper: $common"
}
. $common
$context = New-MyshopServiceContext
Assert-MyshopServicePrerequisites -Context $context
Assert-MyshopServicePrerequisites -Context $context -Worker

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = $cmd
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.WindowStyle = 7
$shortcut.Description = 'Start the myshop dev server and Celery worker at logon'
$shortcut.Save()

"installed: $link"
"  -> $cmd"
"logs go to $($context.LogDir)"
"remove it with: powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Remove"
