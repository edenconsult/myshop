$ErrorActionPreference = 'Stop'

# Creates the two logon tasks that keep the dev store reachable and the import
# queue draining. Re-run any time the launchers move; -Force replaces in place.

$common = Join-Path $PSScriptRoot 'service-common.ps1'
if (-not (Test-Path -LiteralPath $common -PathType Leaf)) {
    throw "Missing service helper: $common"
}
. $common

$context = New-MyshopServiceContext
$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$powershell = Join-Path $PSHOME 'powershell.exe'
if (-not (Test-Path -LiteralPath $powershell -PathType Leaf)) {
    throw "Could not locate Windows PowerShell at $powershell"
}
if (-not (Get-Command Register-ScheduledTask -ErrorAction SilentlyContinue)) {
    throw 'Task Scheduler PowerShell cmdlets are unavailable. Use install-startup.ps1 instead.'
}
Assert-MyshopServicePrerequisites -Context $context -Worker

function Register-MyshopTask {
    param([string]$Name, [string]$Script, [string]$Description)

    if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) {
        throw "Cannot register $Name; launcher not found: $Script"
    }

    # -NonInteractive is not cosmetic: a hidden host that stops on a prompt keeps
    # the task instance Running forever, and IgnoreNew then blocks every later run.
    $action = New-ScheduledTaskAction -Execute $powershell `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`""

    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
    $trigger.Delay = 'PT30S'
    $principal = New-ScheduledTaskPrincipal -UserId $currentUser `
        -LogonType Interactive -RunLevel Limited

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero)

    try {
        Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger `
            -Principal $principal -Settings $settings -Description $Description -Force | Out-Null
    } catch {
        throw "Could not register task '$Name' for '$currentUser'. Run this in that user's PowerShell session and check Task Scheduler permissions. $($_.Exception.Message)"
    }

    $t = Get-ScheduledTask -TaskName $Name
    "{0,-22} state={1,-9} runs={2}" -f $Name, $t.State, $t.Actions[0].Arguments
}

Register-MyshopTask -Name 'myshop-devserver' `
    -Script (Join-Path $PSScriptRoot 'start-devserver.ps1') `
    -Description 'Django dev server on 127.0.0.1:8000 for the myshop POS project'

Register-MyshopTask -Name 'myshop-celery-worker' `
    -Script (Join-Path $PSScriptRoot 'start-celery-worker.ps1') `
    -Description 'Celery solo-pool worker for myshop import and bulk-remove tasks'

"Logs: $(Join-Path $env:LOCALAPPDATA 'myshop\services\logs')"
"Remove: Unregister-ScheduledTask -TaskName myshop-devserver,myshop-celery-worker -Confirm:`$false"
