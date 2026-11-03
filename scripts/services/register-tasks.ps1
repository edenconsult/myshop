$ErrorActionPreference = 'Stop'

# Creates the two logon tasks that keep the dev store reachable and the import
# queue draining. Re-run any time the launchers move; -Force replaces in place.

function Register-MyshopTask {
    param([string]$Name, [string]$Script, [string]$Description)

    # -NonInteractive is not cosmetic: a hidden host that stops on a prompt keeps
    # the task instance Running forever, and IgnoreNew then blocks every later run.
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`""

    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $trigger.Delay = 'PT30S'

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero)

    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger `
        -Settings $settings -Description $Description -Force | Out-Null

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
