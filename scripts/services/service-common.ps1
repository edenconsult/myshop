function New-MyshopServiceContext {
    $root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw 'LOCALAPPDATA is not set for this user; the service cannot create its logs.'
    }

    $logDir = Join-Path $env:LOCALAPPDATA 'myshop\services\logs'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null

    [pscustomobject]@{
        Root = $root
        LogDir = $logDir
        StatusLog = Join-Path $logDir 'launcher.log'
    }
}

function Write-MyshopServiceStatus {
    param(
        [Parameter(Mandatory = $true)]$Context,
        [Parameter(Mandatory = $true)][string]$Message
    )

    "{0} {1}" -f (Get-Date -Format 's'), $Message |
        Out-File -FilePath $Context.StatusLog -Append -Encoding ascii
}

function Assert-MyshopServicePrerequisites {
    param(
        [Parameter(Mandatory = $true)]$Context,
        [switch]$Worker
    )

    $requiredFiles = @(
        (Join-Path $Context.Root '.env'),
        (Join-Path $Context.Root 'manage.py'),
        (Join-Path $Context.Root '.venv\Scripts\python.exe')
    )
    if ($Worker) {
        $requiredFiles += Join-Path $Context.Root '.venv\Scripts\celery.exe'
    }

    $missing = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($missing.Count -gt 0) {
        $paths = $missing -join '; '
        throw "Missing service setup files: $paths. Follow the README setup steps, then rerun the service installer."
    }
}

function Get-MyshopEnvironmentValue {
    param(
        [Parameter(Mandatory = $true)]$Context,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Default
    )

    $pattern = '^\s*{0}\s*=\s*(.*?)\s*$' -f [regex]::Escape($Name)
    $line = Get-Content -LiteralPath (Join-Path $Context.Root '.env') |
        Where-Object { $_ -match $pattern } |
        Select-Object -Last 1
    if (-not $line) {
        return $Default
    }

    $line -match $pattern | Out-Null
    $value = $Matches[1].Trim()
    if ($value.Length -ge 2 -and
        (($value.StartsWith('"') -and $value.EndsWith('"')) -or
         ($value.StartsWith("'") -and $value.EndsWith("'")))) {
        return $value.Substring(1, $value.Length - 2)
    }
    return ($value -replace '\s+#.*$', '').Trim()
}

function Test-MyshopTcpEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $client = New-Object System.Net.Sockets.TcpClient
    $attempt = $null
    try {
        $attempt = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $attempt.AsyncWaitHandle.WaitOne(1000)) {
            return $false
        }
        $client.EndConnect($attempt)
        return $true
    } catch [System.Net.Sockets.SocketException] {
        return $false
    } catch [System.ArgumentException] {
        return $false
    } finally {
        if ($attempt) {
            $attempt.AsyncWaitHandle.Close()
        }
        $client.Close()
    }
}

function Wait-MyshopDependencies {
    param(
        [Parameter(Mandatory = $true)]$Context,
        [ValidateRange(1, 3600)][int]$TimeoutSeconds = 300
    )

    $databaseHost = Get-MyshopEnvironmentValue -Context $Context -Name 'POSTGRES_HOST' -Default '127.0.0.1'
    $databasePortText = Get-MyshopEnvironmentValue -Context $Context -Name 'POSTGRES_PORT' -Default '5432'
    $databasePort = 0
    if (-not [int]::TryParse($databasePortText, [ref]$databasePort) -or
        $databasePort -lt 1 -or $databasePort -gt 65535) {
        throw "POSTGRES_PORT in .env must be a valid TCP port; got '$databasePortText'."
    }

    $redisUrl = Get-MyshopEnvironmentValue -Context $Context -Name 'CELERY_BROKER_URL' -Default 'redis://127.0.0.1:6379'
    $redisUri = $null
    if (-not [Uri]::TryCreate($redisUrl, [UriKind]::Absolute, [ref]$redisUri) -or
        $redisUri.Scheme -notin @('redis', 'rediss')) {
        throw "CELERY_BROKER_URL in .env must be an absolute redis:// or rediss:// URL; got '$redisUrl'."
    }
    $redisPort = if ($redisUri.IsDefaultPort) {
        if ($redisUri.Scheme -eq 'rediss') { 6380 } else { 6379 }
    } else {
        $redisUri.Port
    }

    $endpoints = @(
        [pscustomobject]@{ Name = 'PostgreSQL'; Host = $databaseHost; Port = $databasePort },
        [pscustomobject]@{ Name = 'Redis'; Host = $redisUri.Host; Port = $redisPort }
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastStatus = Get-Date '2000-01-01'

    while ($true) {
        $unavailable = @($endpoints | Where-Object {
            -not (Test-MyshopTcpEndpoint -HostName $_.Host -Port $_.Port)
        })
        if ($unavailable.Count -eq 0) {
            return
        }

        $names = ($unavailable | ForEach-Object { "$($_.Name) ($($_.Host):$($_.Port))" }) -join ', '
        if ((Get-Date) -ge $deadline) {
            throw "Timed out waiting for required services: $names. Check that PostgreSQL and Memurai/Redis are running, then start the services again."
        }
        if (((Get-Date) - $lastStatus).TotalSeconds -ge 30) {
            Write-MyshopServiceStatus -Context $Context -Message "waiting for dependencies: $names"
            $lastStatus = Get-Date
        }
        Start-Sleep -Seconds 5
    }
}
