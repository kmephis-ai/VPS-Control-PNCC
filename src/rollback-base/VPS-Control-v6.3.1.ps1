#requires -Version 5.1
<#
VPS-Control-v6.3.ps1
VPS CONTROL CENTER - VERSION 6.3.1 OBSERVABILITY / SELF-TEST HOTFIX

Goals:
  - Keep the working V6 split-tunneling model.
  - Add per-module modes: DIRECT / AUTO / VPS.
  - AUTO prefers DIRECT, fails over to VPS, and later fails back to DIRECT.
  - Health checks are module-specific; GitHub no longer depends on ChatGPT health.
  - Clear configured/effective routing status.
  - Strong post-load Proxifier verification using dedicated probe executables.
  - Built-in safe GitHub read test and explicit write/push/delete test.
  - Mutation locking, atomic state writes, rotating logs.
  - Network-ready Windows autostart.
  - Persistent observability: route health/latency telemetry, cumulative active
    controller time, route share, switch counts, P95 and 24h summaries.
  - Watchdog heartbeat and stale-loop detection.
  - Read-only controller self-test with optional Windows daily schedule.
  - Sanitized support bundle that excludes controller script/password/LKG profile.
  - Proxifier Standard only. Portable Proxifier remains rejected.
  - GOST is not used. Full Amnezia VPN is not required.

Recommended defaults:
  OpenAI       VPS
  GitHub       AUTO
  DevPackages  AUTO
  Firefox      DIRECT

AUTO behavior:
  DIRECT fails twice -> if VPS is healthy, switch to VPS.
  While on VPS, DIRECT is periodically rechecked.
  DIRECT succeeds three consecutive failback probes -> switch back to DIRECT.

Safety:
  - Default unmatched traffic is always DIRECT.
  - Wrong/unknown VPS exit IP blocks VPS routing fail-closed.
  - Built-in GitHub write test NEVER pushes to main. It uses one unique temporary
    branch, one empty commit, verifies the remote SHA, deletes the branch, and
    verifies remote absence.
  - No global Git proxy configuration is modified.
  - No ADWF architecture/repository changes are made by this controller itself.

Password:
  $PuttyPassword may remain CHANGE_ME if a sibling VPS-Control-v6.ps1 contains
  the previously configured plaintext password. V6.3 can reuse it at runtime.
  Otherwise set $PuttyPassword below.
#>

[CmdletBinding()]
param(
    [ValidateSet(
        'Menu',
        'Apply',
        'Direct',
        'Diagnose',
        'Status',
        'RestartTunnel',
        'StopTunnel',
        'Watchdog',
        'AutoStart',
        'InstallAutostart',
        'RemoveAutostart',
        'GitHubReadTest',
        'GitHubWriteTest',
        'Benchmark',
        'Maintenance',
        'ExportConfig',
        'Cleanup',
        'SelfTest',
        'DailySelfTest',
        'Summary',
        'SupportBundle',
        'InstallDailySelfTest',
        'RemoveDailySelfTest',
        'PresetOpenAI',
        'PresetDevelopment',
        'PresetFirefox'
    )]
    [string]$Action = 'Menu',

    [switch]$NoAppLaunch,

    [int]$WatchIntervalSeconds = 45
)

$ErrorActionPreference = 'Stop'

# ============================================================================
# USER SETTINGS
# ============================================================================

$SocksHost = '127.0.0.1'
$SocksPort = 1080
$ExpectedVpsIp = '89.125.63.46'

$PuttyPath = 'D:\!Cloud\Dropbox\Mephis\PuTTY PORTABLE\putty_portable.exe'
$PuttySession = 'AdminVPS'
$PuttyUser = 'root'

# User explicitly accepted plaintext password storage in the earlier V6 setup.
# You can either set the password here or leave CHANGE_ME and keep the configured
# VPS-Control-v6.1.ps1 or VPS-Control-v6.ps1 next to this V6.3 script.
$PuttyPassword = 'CHANGE_ME'
$ReusePasswordFromSiblingV6 = $true

$TunnelWaitSeconds = 45
$NetworkReadyWaitSeconds = 120

$AutoFailThreshold = 2
$AutoRecoverThreshold = 3
$AutoFailbackProbeSeconds = 300
$AutoLatencyCompareSeconds = 600
$AutoConsiderVpsAboveMs = 1200
$AutoLatencyMinAdvantageMs = 300
$AutoLatencySwitchRatio = 0.75

$MaintenanceRetentionDays = 3
$StateBackupGenerations = 2
$NetworkDnsHost = 'github.com'
$NetworkHttpsUrl = 'https://github.com'

$TelemetrySampleSeconds = 300
$TelemetryRetentionDays = 14
$ObservationSummaryHours = 24
$OperationalStatsMaxGapSeconds = 180
$WatchdogHeartbeatStaleSeconds = 240
$SelfTestDefaultTime = '09:15'

$LogRotateBytes = 2MB
$LogRotateGenerations = 3

$AutostartTaskName = 'VPS Control V6.3 - AutoStart'
$SelfTestTaskName = 'VPS Control V6.3 - Daily SelfTest'

# ============================================================================
# CONSTANTS / PATHS
# ============================================================================

$ControllerVersion = '6.3.1'
$ModuleNames = @('OpenAI', 'GitHub', 'DevPackages', 'Firefox')
$ValidModes = @('DIRECT', 'AUTO', 'VPS')

$StateDir = Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3'
$ConfigFile = Join-Path $StateDir 'routing-config.json'
$RuntimeFile = Join-Path $StateDir 'runtime-state.json'
$ProfilePath = Join-Path $StateDir 'VPS-Control-v6.3-active.ppx'
$DirectProfilePath = Join-Path $StateDir 'VPS-Control-v6.3-direct.ppx'

$DirectProbePath = Join-Path $StateDir 'vps-control-direct-probe.exe'
$VpsProbePath = Join-Path $StateDir 'vps-control-vps-probe.exe'

$WatchdogPidFile = Join-Path $StateDir 'watchdog.pid'
$WatchdogLogFile = Join-Path $StateDir 'watchdog.log'
$ControllerLogFile = Join-Path $StateDir 'controller.log'
$DecisionLogFile = Join-Path $StateDir 'route-decisions.log'
$TelemetryFile = Join-Path $StateDir 'telemetry.jsonl'
$TelemetryMetaFile = Join-Path $StateDir 'telemetry-meta.json'
$OperationalStatsFile = Join-Path $StateDir 'operational-stats.json'
$SelfTestHistoryFile = Join-Path $StateDir 'selftest-history.jsonl'
$WatchdogHeartbeatFile = Join-Path $StateDir 'watchdog-heartbeat.json'
$IncidentFile = Join-Path $StateDir 'incidents.jsonl'
$AttentionFile = Join-Path $StateDir 'attention.json'

$ConfigBackupFile = Join-Path $StateDir 'routing-config.json.bak'
$RuntimeBackupFile = Join-Path $StateDir 'runtime-state.json.bak'
$LastGoodProfilePath = Join-Path $StateDir 'last-known-good.ppx'
$LastGoodProfileMetaPath = Join-Path $StateDir 'last-known-good.json'

$BundledModulesFile = Join-Path $PSScriptRoot 'VPS-Control-v6.3.1-modules.json'
$ModulesFile = Join-Path $StateDir 'modules.json'

$LegacyV62StateDir = Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.2'
$LegacyV62ConfigFile = Join-Path $LegacyV62StateDir 'routing-config.json'
$LegacyV62ModulesFile = Join-Path $LegacyV62StateDir 'modules.json'
$LegacyV62WatchdogPidFile = Join-Path $LegacyV62StateDir 'watchdog.pid'
$LegacyV62AutostartTaskName = 'VPS Control V6.2 - AutoStart'

$LegacyV61StateDir = Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.1'
$LegacyV61ConfigFile = Join-Path $LegacyV61StateDir 'routing-config.json'
$LegacyV61WatchdogPidFile = Join-Path $LegacyV61StateDir 'watchdog.pid'
$LegacyV61AutostartTaskName = 'VPS Control V6.1 - AutoStart'

$LegacyV6StateDir = Join-Path $env:LOCALAPPDATA 'VPS-Control-v6'
$LegacyV6WatchdogPidFile = Join-Path $LegacyV6StateDir 'watchdog.pid'
$LegacyAutostartTaskName = 'VPS Control V6 - Apply Modules'

$ForegroundMutexName = "Local\VPSControlV63Foreground-$env:USERNAME"
$MutationMutexName = "Local\VPSControlV63Mutation-$env:USERNAME"

if (-not (Test-Path -LiteralPath $StateDir)) {
    New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
}

$script:ForegroundMutex = $null
$script:ProbeHelpersReady = $false

# ============================================================================
# OUTPUT / LOGGING
# ============================================================================

function Write-Step([string]$Text) {
    Write-Host "`n=== $Text ===" -ForegroundColor Cyan
}

function Write-Ok([string]$Text) {
    Write-Host "[OK] $Text" -ForegroundColor Green
}

function Write-Warn([string]$Text) {
    Write-Host "[WARN] $Text" -ForegroundColor Yellow
}

function Write-Info([string]$Text) {
    Write-Host "[INFO] $Text" -ForegroundColor DarkGray
}

function Write-Fail([string]$Text) {
    Write-Host "[FAIL] $Text" -ForegroundColor Red
}

function Pause-Control {
    Write-Host ''
    Read-Host 'Нажмите Enter для продолжения' | Out-Null
}

function Rotate-LogIfNeeded([string]$Path) {
    try {
        if (-not (Test-Path -LiteralPath $Path)) {
            return
        }

        $file = Get-Item -LiteralPath $Path -ErrorAction Stop

        if ($file.Length -lt $LogRotateBytes) {
            return
        }

        for ($i = $LogRotateGenerations; $i -ge 1; $i--) {
            $current = "$Path.$i"

            if ($i -eq $LogRotateGenerations) {
                Remove-Item -LiteralPath $current -Force -ErrorAction SilentlyContinue
            }

            $previousIndex = $i - 1

            if ($previousIndex -eq 0) {
                $previous = $Path
            }
            else {
                $previous = "$Path.$previousIndex"
            }

            if (Test-Path -LiteralPath $previous) {
                Move-Item -LiteralPath $previous -Destination $current -Force
            }
        }
    }
    catch {
        # Logging must never break routing.
    }
}

function Write-LogLine(
    [string]$Path,
    [string]$Text
) {
    try {
        Rotate-LogIfNeeded $Path
        $line = '{0:yyyy-MM-dd HH:mm:ss}  {1}' -f (Get-Date), $Text
        Add-Content -LiteralPath $Path -Value $line -Encoding UTF8
    }
    catch {
        # Non-fatal.
    }
}

function Write-ControllerLog([string]$Text) {
    Write-LogLine -Path $ControllerLogFile -Text $Text
}

function Write-WatchdogLog([string]$Text) {
    Write-LogLine -Path $WatchdogLogFile -Text $Text
}

function Write-RouteDecision(
    [string]$Module,
    [string]$From,
    [string]$To,
    [string]$Reason,
    [string]$Detail = ''
) {
    $payload = "module=$Module from=$From to=$To reason=$Reason"

    if ($Detail) {
        $payload += " detail=$Detail"
    }

    Write-LogLine -Path $DecisionLogFile -Text $payload
    Write-ControllerLog "ROUTE_DECISION $payload"

    if ($Reason -match '^AUTO_') {
        Write-IncidentSnapshot `
            -Module $Module `
            -From $From `
            -To $To `
            -Reason $Reason `
            -Detail $Detail
    }
}

function Enter-ForegroundInstance {
    if ($Action -eq 'Watchdog' -or $Action -eq 'AutoStart' -or $Action -eq 'DailySelfTest') {
        return $true
    }

    try {
        $mutex = New-Object System.Threading.Mutex($false, $ForegroundMutexName)
        $acquired = $false

        try {
            $acquired = $mutex.WaitOne(0, $false)
        }
        catch [System.Threading.AbandonedMutexException] {
            $acquired = $true
        }

        if (-not $acquired) {
            $mutex.Dispose()
            Write-Fail 'VPS Control V6.3 уже запущен в другом foreground-процессе.'
            return $false
        }

        $script:ForegroundMutex = $mutex
        return $true
    }
    catch {
        Write-Warn "Single-instance mutex недоступен: $($_.Exception.Message)"
        return $true
    }
}

function Exit-ForegroundInstance {
    if ($script:ForegroundMutex) {
        try {
            $script:ForegroundMutex.ReleaseMutex()
        }
        catch {
            # Ignore.
        }

        try {
            $script:ForegroundMutex.Dispose()
        }
        catch {
            # Ignore.
        }

        $script:ForegroundMutex = $null
    }
}

function Invoke-WithMutationLock {
    param(
        [Parameter(Mandatory=$true)]
        [scriptblock]$ScriptBlock,

        [int]$TimeoutMs = 15000
    )

    $mutex = $null
    $acquired = $false

    try {
        $mutex = New-Object System.Threading.Mutex($false, $MutationMutexName)

        try {
            $acquired = $mutex.WaitOne($TimeoutMs, $false)
        }
        catch [System.Threading.AbandonedMutexException] {
            $acquired = $true
        }

        if (-not $acquired) {
            throw 'Timeout waiting for VPS Control mutation lock.'
        }

        return (& $ScriptBlock)
    }
    finally {
        if ($acquired -and $mutex) {
            try {
                $mutex.ReleaseMutex()
            }
            catch {
                # Ignore.
            }
        }

        if ($mutex) {
            try {
                $mutex.Dispose()
            }
            catch {
                # Ignore.
            }
        }
    }
}

function Write-TextAtomic(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Text
) {
    $directory = Split-Path -Parent $Path

    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $temp = Join-Path $directory (
        ([System.IO.Path]::GetFileName($Path)) +
        ".tmp.$PID." +
        ([guid]::NewGuid().ToString('N'))
    )

    $utf8Bom = New-Object System.Text.UTF8Encoding($true)

    try {
        [System.IO.File]::WriteAllText($temp, $Text, $utf8Bom)

        if (Test-Path -LiteralPath $Path) {
            try {
                [System.IO.File]::Replace($temp, $Path, $null, $true)
                return
            }
            catch {
                Move-Item -LiteralPath $temp -Destination $Path -Force
                return
            }
        }

        Move-Item -LiteralPath $temp -Destination $Path -Force
    }
    finally {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
    }
}

function Write-JsonAtomic(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)]$Object
) {
    $json = $Object | ConvertTo-Json -Depth 10
    Write-TextAtomic -Path $Path -Text $json
}

# ============================================================================
# CONFIG / RUNTIME STATE
# ============================================================================

function Normalize-Mode([string]$Mode, [string]$Fallback = 'DIRECT') {
    if ($Mode) {
        $upper = $Mode.Trim().ToUpperInvariant()

        if ($ValidModes -contains $upper) {
            return $upper
        }
    }

    return $Fallback
}

function New-DefaultConfig {
    return [pscustomobject]@{
        Version = $ControllerVersion
        OpenAI = 'VPS'
        GitHub = 'AUTO'
        DevPackages = 'AUTO'
        Firefox = 'DIRECT'
    }
}

function Normalize-Config($Config) {
    if (-not $Config) {
        return (New-DefaultConfig)
    }

    return [pscustomobject]@{
        Version = $ControllerVersion
        OpenAI = $(Normalize-Mode ([string]$Config.OpenAI) 'VPS')
        GitHub = $(Normalize-Mode ([string]$Config.GitHub) 'AUTO')
        DevPackages = $(Normalize-Mode ([string]$Config.DevPackages) 'AUTO')
        Firefox = $(Normalize-Mode ([string]$Config.Firefox) 'DIRECT')
    }
}

function Save-Config($Config) {
    $normalized = Normalize-Config $Config

    if (Test-Path -LiteralPath $ConfigFile) {
        try {
            Copy-Item -LiteralPath $ConfigFile -Destination $ConfigBackupFile -Force
        }
        catch {
            # Backup failure must not block config save.
        }
    }

    Write-JsonAtomic -Path $ConfigFile -Object $normalized
}

function Get-Config {
    if (-not (Test-Path -LiteralPath $ConfigFile)) {
        foreach ($candidate in @(
            [pscustomobject]@{ Path = $LegacyV62ConfigFile; Label = 'V6.2/6.2.1' },
            [pscustomobject]@{ Path = $LegacyV61ConfigFile; Label = 'V6.1' }
        )) {
            if (-not (Test-Path -LiteralPath $candidate.Path)) {
                continue
            }

            try {
                $legacyRaw = Get-Content -LiteralPath $candidate.Path -Raw -ErrorAction Stop
                $legacyConfig = Normalize-Config ($legacyRaw | ConvertFrom-Json)
                Save-Config $legacyConfig
                Write-ControllerLog "CONFIG migrated from $($candidate.Label)"
                return $legacyConfig
            }
            catch {
                Write-ControllerLog "CONFIG migration from $($candidate.Label) failed: $($_.Exception.Message)"
            }
        }

        $default = New-DefaultConfig
        Save-Config $default
        return $default
    }

    try {
        $raw = Get-Content -LiteralPath $ConfigFile -Raw -ErrorAction Stop
        return Normalize-Config ($raw | ConvertFrom-Json)
    }
    catch {
        Write-Warn 'routing-config.json повреждён. Пробую backup.'
        Write-ControllerLog "CONFIG primary parse failed: $($_.Exception.Message)"

        if (Test-Path -LiteralPath $ConfigBackupFile) {
            try {
                $backupRaw = Get-Content -LiteralPath $ConfigBackupFile -Raw -ErrorAction Stop
                $restored = Normalize-Config ($backupRaw | ConvertFrom-Json)
                Write-JsonAtomic -Path $ConfigFile -Object $restored
                Write-ControllerLog 'CONFIG restored from backup'
                return $restored
            }
            catch {
                Write-ControllerLog "CONFIG backup parse failed: $($_.Exception.Message)"
            }
        }

        $default = New-DefaultConfig
        Save-Config $default
        return $default
    }
}

function New-RouteObject(
    [string]$OpenAI = 'DIRECT',
    [string]$GitHub = 'DIRECT',
    [string]$DevPackages = 'DIRECT',
    [string]$Firefox = 'DIRECT'
) {
    return [pscustomobject]@{
        OpenAI = $(if ($OpenAI -eq 'VPS') { 'VPS' } else { 'DIRECT' })
        GitHub = $(if ($GitHub -eq 'VPS') { 'VPS' } else { 'DIRECT' })
        DevPackages = $(if ($DevPackages -eq 'VPS') { 'VPS' } else { 'DIRECT' })
        Firefox = $(if ($Firefox -eq 'VPS') { 'VPS' } else { 'DIRECT' })
    }
}

function Normalize-Routes($Routes) {
    if (-not $Routes) {
        return (New-RouteObject)
    }

    return New-RouteObject `
        -OpenAI ([string]$Routes.OpenAI) `
        -GitHub ([string]$Routes.GitHub) `
        -DevPackages ([string]$Routes.DevPackages) `
        -Firefox ([string]$Routes.Firefox)
}

function New-HealthObject {
    return [pscustomobject]@{
        OpenAI = 'UNKNOWN'
        GitHub = 'UNKNOWN'
        DevPackages = 'UNKNOWN'
        Firefox = 'UNKNOWN'
    }
}

function Normalize-Health($Health) {
    $result = New-HealthObject

    if (-not $Health) {
        return $result
    }

    foreach ($module in $ModuleNames) {
        $value = [string]$Health.$module

        if ($value) {
            $result.$module = $value.ToUpperInvariant()
        }
    }

    return $result
}


function New-ModuleMetric {
    return [pscustomobject]@{
        Route = 'DIRECT'
        State = 'UNKNOWN'
        LatencyMs = 0
        FailureClass = 'NONE'
        HttpStatus = 0
        LastProbe = ''
        Detail = ''
    }
}

function New-MetricsObject {
    return [pscustomobject]@{
        OpenAI = $(New-ModuleMetric)
        GitHub = $(New-ModuleMetric)
        DevPackages = $(New-ModuleMetric)
        Firefox = $(New-ModuleMetric)
    }
}

function Normalize-ModuleMetric($Metric) {
    $result = New-ModuleMetric

    if (-not $Metric) {
        return $result
    }

    $route = [string]$Metric.Route
    if ($route -eq 'VPS') { $result.Route = 'VPS' }

    if ($Metric.State) { $result.State = ([string]$Metric.State).ToUpperInvariant() }
    if ($Metric.LatencyMs) { $result.LatencyMs = [int]$Metric.LatencyMs }
    if ($Metric.FailureClass) { $result.FailureClass = ([string]$Metric.FailureClass).ToUpperInvariant() }
    if ($Metric.HttpStatus) { $result.HttpStatus = [int]$Metric.HttpStatus }
    if ($Metric.LastProbe) { $result.LastProbe = [string]$Metric.LastProbe }
    if ($Metric.Detail) { $result.Detail = [string]$Metric.Detail }

    return $result
}

function Normalize-Metrics($Metrics) {
    $result = New-MetricsObject

    if (-not $Metrics) {
        return $result
    }

    foreach ($module in $ModuleNames) {
        $result.$module = Normalize-ModuleMetric $Metrics.$module
    }

    return $result
}

function New-AutoModuleState {
    return [pscustomobject]@{
        DirectFails = 0
        DirectRecoveries = 0
        LastFailbackProbe = ''
        LastLatencyCompare = ''
        LastDecision = 'INITIAL'
    }
}

function New-AutoStateObject {
    return [pscustomobject]@{
        OpenAI = $(New-AutoModuleState)
        GitHub = $(New-AutoModuleState)
        DevPackages = $(New-AutoModuleState)
        Firefox = $(New-AutoModuleState)
    }
}

function Normalize-AutoModuleState($State) {
    $result = New-AutoModuleState

    if (-not $State) {
        return $result
    }

    if ($State.DirectFails -ne $null) { $result.DirectFails = [int]$State.DirectFails }
    if ($State.DirectRecoveries -ne $null) { $result.DirectRecoveries = [int]$State.DirectRecoveries }
    if ($State.LastFailbackProbe) { $result.LastFailbackProbe = [string]$State.LastFailbackProbe }
    if ($State.LastLatencyCompare) { $result.LastLatencyCompare = [string]$State.LastLatencyCompare }
    if ($State.LastDecision) { $result.LastDecision = [string]$State.LastDecision }

    return $result
}

function Normalize-AutoState($State) {
    $result = New-AutoStateObject

    if (-not $State) {
        return $result
    }

    foreach ($module in $ModuleNames) {
        $result.$module = Normalize-AutoModuleState $State.$module
    }

    return $result
}

function Convert-ProbeToMetric($Probe, [string]$Route) {
    return [pscustomobject]@{
        Route = $Route
        State = [string]$Probe.State
        LatencyMs = [int]$Probe.LatencyMs
        FailureClass = [string]$Probe.FailureClass
        HttpStatus = [int]$Probe.HttpStatus
        LastProbe = (Get-Date).ToString('o')
        Detail = [string]$Probe.Detail
    }
}

function New-RuntimeState {
    return [pscustomobject]@{
        Version = $ControllerVersion
        Override = 'NONE'
        Effective = $(New-RouteObject)
        Health = $(New-HealthObject)
        Metrics = $(New-MetricsObject)
        AutoState = $(New-AutoStateObject)
        ProfileHash = ''
        UpdatedAt = (Get-Date).ToString('o')
        LastReason = 'INITIAL'
    }
}

function Normalize-Runtime($Runtime) {
    if (-not $Runtime) {
        return (New-RuntimeState)
    }

    $override = [string]$Runtime.Override

    if ($override -ne 'DIRECT') {
        $override = 'NONE'
    }

    return [pscustomobject]@{
        Version = $ControllerVersion
        Override = $override
        Effective = $(Normalize-Routes $Runtime.Effective)
        Health = $(Normalize-Health $Runtime.Health)
        Metrics = $(Normalize-Metrics $Runtime.Metrics)
        AutoState = $(Normalize-AutoState $Runtime.AutoState)
        ProfileHash = [string]$Runtime.ProfileHash
        UpdatedAt = $(if ($Runtime.UpdatedAt) { [string]$Runtime.UpdatedAt } else { (Get-Date).ToString('o') })
        LastReason = $(if ($Runtime.LastReason) { [string]$Runtime.LastReason } else { 'UNKNOWN' })
    }
}

function Save-Runtime($Runtime) {
    $normalized = Normalize-Runtime $Runtime
    $normalized.UpdatedAt = (Get-Date).ToString('o')

    if (Test-Path -LiteralPath $RuntimeFile) {
        try {
            Copy-Item -LiteralPath $RuntimeFile -Destination $RuntimeBackupFile -Force
        }
        catch {
            # Non-fatal.
        }
    }

    Write-JsonAtomic -Path $RuntimeFile -Object $normalized
}

function Get-Runtime {
    if (-not (Test-Path -LiteralPath $RuntimeFile)) {
        $runtime = New-RuntimeState
        Save-Runtime $runtime
        return $runtime
    }

    try {
        $raw = Get-Content -LiteralPath $RuntimeFile -Raw -ErrorAction Stop
        return Normalize-Runtime ($raw | ConvertFrom-Json)
    }
    catch {
        Write-ControllerLog "RUNTIME primary parse failed: $($_.Exception.Message)"

        if (Test-Path -LiteralPath $RuntimeBackupFile) {
            try {
                $backupRaw = Get-Content -LiteralPath $RuntimeBackupFile -Raw -ErrorAction Stop
                $restored = Normalize-Runtime ($backupRaw | ConvertFrom-Json)
                Write-JsonAtomic -Path $RuntimeFile -Object $restored
                Write-ControllerLog 'RUNTIME restored from backup'
                return $restored
            }
            catch {
                Write-ControllerLog "RUNTIME backup parse failed: $($_.Exception.Message)"
            }
        }

        $runtime = New-RuntimeState
        Save-Runtime $runtime
        return $runtime
    }
}

function Get-DesiredMode($Config, [string]$Module) {
    return Normalize-Mode ([string]$Config.$Module)
}

function Set-DesiredMode(
    [ValidateSet('OpenAI','GitHub','DevPackages','Firefox')]
    [string]$Module,

    [ValidateSet('DIRECT','AUTO','VPS')]
    [string]$Mode
) {
    Invoke-WithMutationLock {
        $config = Get-Config
        $config.$Module = $Mode
        Save-Config $config
    } | Out-Null
}

function Cycle-DesiredMode(
    [ValidateSet('OpenAI','GitHub','DevPackages','Firefox')]
    [string]$Module
) {
    Invoke-WithMutationLock {
        $config = Get-Config
        $current = Normalize-Mode ([string]$config.$Module)

        switch ($current) {
            'DIRECT' { $config.$Module = 'AUTO' }
            'AUTO' { $config.$Module = 'VPS' }
            default { $config.$Module = 'DIRECT' }
        }

        Save-Config $config
    } | Out-Null
}

function Set-Preset(
    [ValidateSet('OpenAI','Development','Firefox')]
    [string]$Preset
) {
    Invoke-WithMutationLock {
        switch ($Preset) {
            'OpenAI' {
                $config = [pscustomobject]@{
                    Version = $ControllerVersion
                    OpenAI = 'VPS'
                    GitHub = 'DIRECT'
                    DevPackages = 'DIRECT'
                    Firefox = 'DIRECT'
                }
            }

            'Development' {
                $config = New-DefaultConfig
            }

            'Firefox' {
                $config = [pscustomobject]@{
                    Version = $ControllerVersion
                    OpenAI = 'VPS'
                    GitHub = 'DIRECT'
                    DevPackages = 'DIRECT'
                    Firefox = 'VPS'
                }
            }
        }

        Save-Config $config
    } | Out-Null
}

function Test-AnyEffectiveVps($Routes) {
    $r = Normalize-Routes $Routes

    foreach ($module in $ModuleNames) {
        if ($r.$module -eq 'VPS') {
            return $true
        }
    }

    return $false
}

function Test-NeedsWatchdog($Config, $Routes) {
    foreach ($module in $ModuleNames) {
        $mode = Get-DesiredMode $Config $module

        if ($mode -eq 'AUTO' -or $mode -eq 'VPS') {
            return $true
        }
    }

    return (Test-AnyEffectiveVps $Routes)
}

# ============================================================================
# WINDOWS ARGUMENT / NATIVE PROCESS HELPERS
# ============================================================================

function Convert-ToProcessArgumentString {
    param(
        [Parameter(Mandatory=$true)]
        [string[]]$Items
    )

    $quoted = foreach ($item in $Items) {
        if ($null -eq $item) {
            '""'
            continue
        }

        $value = [string]$item

        if ($value -notmatch '[\s"]') {
            $value
            continue
        }

        $escaped = $value -replace '(\\*)"', '$1$1\"'
        $escaped = $escaped -replace '(\\+)$', '$1$1'
        '"' + $escaped + '"'
    }

    return ($quoted -join ' ')
}

function Invoke-NativeCaptured {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = '',
        [hashtable]$EnvironmentOverrides = $null,
        [switch]$Echo
    )

    $stdoutPath = Join-Path $StateDir ("native-out-" + [guid]::NewGuid().ToString('N') + '.txt')
    $stderrPath = Join-Path $StateDir ("native-err-" + [guid]::NewGuid().ToString('N') + '.txt')
    $savedEnv = @{}

    try {
        if ($EnvironmentOverrides) {
            foreach ($key in $EnvironmentOverrides.Keys) {
                $savedEnv[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
                [Environment]::SetEnvironmentVariable(
                    $key,
                    [string]$EnvironmentOverrides[$key],
                    'Process'
                )
            }
        }

        if ($Echo) {
            Write-Host (
                ([System.IO.Path]::GetFileName($FilePath)) +
                ' ' +
                ($Arguments -join ' ')
            )
        }

        $startParams = @{
            FilePath = $FilePath
            ArgumentList = (Convert-ToProcessArgumentString -Items $Arguments)
            Wait = $true
            PassThru = $true
            NoNewWindow = $true
            RedirectStandardOutput = $stdoutPath
            RedirectStandardError = $stderrPath
        }

        if ($WorkingDirectory) {
            $startParams.WorkingDirectory = $WorkingDirectory
        }

        $process = Start-Process @startParams

        $stdout = @()
        $stderr = @()

        if (Test-Path -LiteralPath $stdoutPath) {
            $stdout = @(Get-Content -LiteralPath $stdoutPath -ErrorAction SilentlyContinue)
        }

        if (Test-Path -LiteralPath $stderrPath) {
            $stderr = @(Get-Content -LiteralPath $stderrPath -ErrorAction SilentlyContinue)
        }

        if ($Echo) {
            foreach ($line in @($stdout + $stderr)) {
                Write-Host "  $line"
            }
        }

        return [pscustomobject]@{
            ExitCode = [int]$process.ExitCode
            StdOut = @($stdout)
            StdErr = @($stderr)
            Output = @($stdout + $stderr)
        }
    }
    catch {
        return [pscustomobject]@{
            ExitCode = 9001
            StdOut = @()
            StdErr = @($_.Exception.Message)
            Output = @($_.Exception.Message)
        }
    }
    finally {
        if ($EnvironmentOverrides) {
            foreach ($key in $EnvironmentOverrides.Keys) {
                [Environment]::SetEnvironmentVariable(
                    $key,
                    $savedEnv[$key],
                    'Process'
                )
            }
        }

        Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

# ============================================================================
# PROBE HELPERS / NETWORK
# ============================================================================

function Ensure-ProbeHelpers {
    if (
        $script:ProbeHelpersReady -and
        (Test-Path -LiteralPath $DirectProbePath) -and
        (Test-Path -LiteralPath $VpsProbePath)
    ) {
        return $true
    }

    $curlCommand = Get-Command curl.exe -ErrorAction SilentlyContinue

    if (-not $curlCommand -or -not $curlCommand.Source) {
        Write-Fail 'curl.exe не найден. AUTO и post-load verification недоступны.'
        return $false
    }

    try {
        $source = $curlCommand.Source

        foreach ($target in @($DirectProbePath, $VpsProbePath)) {
            $needsCopy = $true

            if (Test-Path -LiteralPath $target) {
                try {
                    $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
                    $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash

                    if ($sourceHash -eq $targetHash) {
                        $needsCopy = $false
                    }
                }
                catch {
                    $needsCopy = $true
                }
            }

            if ($needsCopy) {
                Copy-Item -LiteralPath $source -Destination $target -Force
            }
        }

        $script:ProbeHelpersReady = (
            (Test-Path -LiteralPath $DirectProbePath) -and
            (Test-Path -LiteralPath $VpsProbePath)
        )

        return $script:ProbeHelpersReady
    }
    catch {
        Write-Fail "Не удалось подготовить probe helpers: $($_.Exception.Message)"
        return $false
    }
}

function Test-TcpPort(
    [string]$HostName,
    [int]$Port,
    [int]$TimeoutMs = 1200
) {
    $client = $null

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($HostName, $Port, $null, $null)

        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            return $false
        }

        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($client) {
            $client.Close()
        }
    }
}

function Invoke-CurlSimple(
    [Parameter(Mandatory=$true)][string]$Executable,
    [Parameter(Mandatory=$true)][string[]]$Arguments
) {
    return Invoke-NativeCaptured `
        -FilePath $Executable `
        -Arguments $Arguments
}

function Get-ExternalIpByExecutable([string]$Executable) {
    $result = Invoke-CurlSimple `
        -Executable $Executable `
        -Arguments @(
            '--silent',
            '--show-error',
            '--max-time', '12',
            'https://ifconfig.me'
        )

    if ($result.ExitCode -ne 0 -or -not $result.StdOut) {
        return ''
    }

    return (([string]($result.StdOut | Select-Object -First 1)).Trim())
}

function Get-DirectExternalIp {
    if (-not (Ensure-ProbeHelpers)) {
        return ''
    }

    return Get-ExternalIpByExecutable $DirectProbePath
}

function Get-VpsProfileExternalIp {
    if (-not (Ensure-ProbeHelpers)) {
        return ''
    }

    return Get-ExternalIpByExecutable $VpsProbePath
}

function Get-SocksExternalIp {
    $curlCommand = Get-Command curl.exe -ErrorAction SilentlyContinue

    if (-not $curlCommand) {
        return ''
    }

    $result = Invoke-CurlSimple `
        -Executable $curlCommand.Source `
        -Arguments @(
            '--silent',
            '--show-error',
            '--max-time', '12',
            '--proxy', "socks5h://${SocksHost}:$SocksPort",
            'https://ifconfig.me'
        )

    if ($result.ExitCode -ne 0 -or -not $result.StdOut) {
        return ''
    }

    return (([string]($result.StdOut | Select-Object -First 1)).Trim())
}


function Get-CurlFailureClass([int]$ExitCode, [string]$StdErr) {
    switch ($ExitCode) {
        0 { return 'NONE' }
        5 { return 'PROXY_DNS' }
        6 { return 'DNS' }
        7 { return 'CONNECT' }
        28 { return 'TIMEOUT' }
        35 { return 'TLS' }
        52 { return 'EMPTY_REPLY' }
        56 { return 'RECEIVE' }
        60 { return 'TLS_CERT' }
        97 { return 'PROXY_HANDSHAKE' }
        default {
            if ($StdErr -match '(?i)resolve|name resolution|could not resolve') { return 'DNS' }
            if ($StdErr -match '(?i)ssl|tls|certificate') { return 'TLS' }
            if ($StdErr -match '(?i)timed out|timeout') { return 'TIMEOUT' }
            if ($StdErr -match '(?i)connect') { return 'CONNECT' }
            return "CURL_$ExitCode"
        }
    }
}

function Invoke-HttpProbe {
    param(
        [Parameter(Mandatory=$true)]
        [ValidateSet('DIRECT','VPS')]
        [string]$Route,

        [Parameter(Mandatory=$true)]
        [string]$Url
    )

    if (-not (Ensure-ProbeHelpers)) {
        return [pscustomobject]@{
            Success = $false
            HttpStatus = 0
            LatencyMs = 0
            FailureClass = 'PROBE_HELPER'
            Detail = 'probe helper unavailable'
        }
    }

    $format = '%{http_code}|%{time_namelookup}|%{time_connect}|%{time_appconnect}|%{time_starttransfer}|%{time_total}|%{remote_ip}'

    if ($Route -eq 'DIRECT') {
        $exe = $DirectProbePath
        $args = @(
            '--silent',
            '--show-error',
            '--location',
            '--output', 'NUL',
            '--write-out', $format,
            '--max-time', '15',
            $Url
        )
    }
    else {
        $curlCommand = Get-Command curl.exe -ErrorAction SilentlyContinue

        if (-not $curlCommand) {
            return [pscustomobject]@{
                Success = $false
                HttpStatus = 0
                LatencyMs = 0
                FailureClass = 'CURL_MISSING'
                Detail = 'curl.exe missing'
            }
        }

        $exe = $curlCommand.Source
        $args = @(
            '--silent',
            '--show-error',
            '--location',
            '--output', 'NUL',
            '--write-out', $format,
            '--max-time', '15',
            '--proxy', "socks5h://${SocksHost}:$SocksPort",
            $Url
        )
    }

    $result = Invoke-CurlSimple -Executable $exe -Arguments $args
    $stderrText = (@($result.StdErr) -join ' ').Trim()
    $line = ''

    if ($result.StdOut) {
        $line = ([string]($result.StdOut | Select-Object -First 1)).Trim()
    }

    $status = 0
    $latencyMs = 0
    $remoteIp = ''
    $timingDetail = ''

    if ($line -and $line.Contains('|')) {
        $parts = $line.Split('|')

        if ($parts.Count -ge 7) {
            [void][int]::TryParse($parts[0], [ref]$status)

            $total = 0.0

            if ([double]::TryParse(
                $parts[5],
                [System.Globalization.NumberStyles]::Float,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [ref]$total
            )) {
                $latencyMs = [int][math]::Round($total * 1000.0)
            }

            $remoteIp = $parts[6]
            $timingDetail = "dns=$($parts[1]) connect=$($parts[2]) tls=$($parts[3]) ttfb=$($parts[4]) total=$($parts[5]) remote=$remoteIp"
        }
    }

    $failureClass = Get-CurlFailureClass -ExitCode $result.ExitCode -StdErr $stderrText

    if ($result.ExitCode -eq 0 -and -not (Test-AcceptableHttpStatus $status)) {
        $failureClass = "HTTP_$status"
    }

    return [pscustomobject]@{
        Success = ($result.ExitCode -eq 0 -and (Test-AcceptableHttpStatus $status))
        HttpStatus = $status
        LatencyMs = $latencyMs
        FailureClass = $failureClass
        Detail = $(if ($timingDetail) { "$status $Url [$timingDetail]" } elseif ($stderrText) { "$status $Url [$stderrText]" } else { "$status $Url" })
    }
}

function Get-HttpStatus {
    param(
        [Parameter(Mandatory=$true)]
        [ValidateSet('DIRECT','VPS')]
        [string]$Route,

        [Parameter(Mandatory=$true)]
        [string]$Url
    )

    $probe = Invoke-HttpProbe -Route $Route -Url $Url
    return [int]$probe.HttpStatus
}

function Test-AcceptableHttpStatus([int]$Status) {
    if ($Status -ge 200 -and $Status -le 399) {
        return $true
    }

    if (@(401, 404, 405, 429) -contains $Status) {
        return $true
    }

    return $false
}

function Get-ModuleHealthDefinition([string]$Module) {
    $entry = Get-ModuleCatalogEntry $Module

    return [pscustomobject]@{
        Required = [int]$entry.Required
        DegradedLatencyMs = [int]$entry.DegradedLatencyMs
        Urls = @($entry.HealthUrls)
    }
}

function Test-ModuleHealth(
    [Parameter(Mandatory=$true)]
    [ValidateSet('OpenAI','GitHub','DevPackages','Firefox')]
    [string]$Module,

    [Parameter(Mandatory=$true)]
    [ValidateSet('DIRECT','VPS')]
    [string]$Route
) {
    $definition = Get-ModuleHealthDefinition $Module
    $details = New-Object System.Collections.Generic.List[string]
    $latencies = New-Object System.Collections.Generic.List[int]
    $passed = 0
    $lastStatus = 0
    $failureClasses = New-Object System.Collections.Generic.List[string]

    if ($Route -eq 'VPS') {
        if (-not (Test-TcpPort $SocksHost $SocksPort)) {
            return [pscustomobject]@{
                Healthy = $false
                State = 'FAILED'
                Passed = 0
                Total = $definition.Urls.Count
                LatencyMs = 0
                HttpStatus = 0
                FailureClass = 'SOCKS_OFF'
                Detail = 'SOCKS_OFF'
            }
        }
    }

    foreach ($url in $definition.Urls) {
        $probe = Invoke-HttpProbe -Route $Route -Url $url
        $lastStatus = [int]$probe.HttpStatus

        if ($probe.Success) {
            $passed++

            if ($probe.LatencyMs -gt 0) {
                [void]$latencies.Add([int]$probe.LatencyMs)
            }
        }
        else {
            [void]$failureClasses.Add([string]$probe.FailureClass)
        }

        [void]$details.Add([string]$probe.Detail)
    }

    $latencyMs = 0

    if ($latencies.Count -gt 0) {
        $latencyMs = [int][math]::Round(
            (($latencies | Measure-Object -Average).Average)
        )
    }

    if ($passed -lt [int]$definition.Required) {
        $state = 'FAILED'
    }
    elseif (
        $latencyMs -gt 0 -and
        $latencyMs -ge [int]$definition.DegradedLatencyMs
    ) {
        $state = 'DEGRADED'
    }
    else {
        $state = 'HEALTHY'
    }

    $failureClass = 'NONE'

    if ($failureClasses.Count -gt 0) {
        $failureClass = [string]($failureClasses | Select-Object -First 1)
    }
    elseif ($state -eq 'DEGRADED') {
        $failureClass = 'LATENCY'
    }

    return [pscustomobject]@{
        Healthy = ($state -ne 'FAILED')
        State = $state
        Passed = $passed
        Total = $definition.Urls.Count
        LatencyMs = $latencyMs
        HttpStatus = $lastStatus
        FailureClass = $failureClass
        Detail = ($details -join ' | ')
    }
}

function Test-SocksIdentity {
    if (-not (Test-TcpPort $SocksHost $SocksPort)) {
        return $false
    }

    $ip = Get-SocksExternalIp
    return ($ip -and $ip -eq $ExpectedVpsIp)
}

# ============================================================================
# PUTTY / SOCKS
# ============================================================================

function Get-EffectivePuttyPassword {
    if ($PuttyPassword -and $PuttyPassword -ne 'CHANGE_ME') {
        return $PuttyPassword
    }

    if (-not $ReusePasswordFromSiblingV6) {
        return ''
    }

    foreach ($name in @('VPS-Control-v6.3.ps1', 'VPS-Control-v6.2.1.ps1', 'VPS-Control-v6.2.ps1', 'VPS-Control-v6.1.ps1', 'VPS-Control-v6.ps1')) {
        $legacy = Join-Path $PSScriptRoot $name

        if (-not (Test-Path -LiteralPath $legacy)) {
            continue
        }

        try {
            $raw = Get-Content -LiteralPath $legacy -Raw -ErrorAction Stop
            $match = [regex]::Match(
                $raw,
                "(?m)^\s*\`$PuttyPassword\s*=\s*'([^']+)'\s*$"
            )

            if ($match.Success) {
                $value = $match.Groups[1].Value

                if ($value -and $value -ne 'CHANGE_ME') {
                    return $value
                }
            }
        }
        catch {
            # Try next fallback.
        }
    }

    return ''
}

function Test-PuttyConfigured {
    if (-not (Test-Path -LiteralPath $PuttyPath)) {
        Write-Fail 'PuTTY Portable не найден:'
        Write-Fail "  $PuttyPath"
        return $false
    }

    $password = Get-EffectivePuttyPassword

    if (-not $password) {
        Write-Fail 'Пароль VPS не найден.'
        Write-Host "Укажите `$PuttyPassword в VPS-Control-v6.2.ps1"
        Write-Host 'или оставьте рядом настроенный VPS-Control-v6.ps1.'
        return $false
    }

    return $true
}

function Start-PuttyTunnel {
    if (-not (Test-PuttyConfigured)) {
        return $false
    }

    $password = Get-EffectivePuttyPassword
    $arguments = @(
        '-load', $PuttySession,
        '-l', $PuttyUser,
        '-pw', $password
    )

    try {
        Start-Process `
            -FilePath $PuttyPath `
            -ArgumentList (Convert-ToProcessArgumentString -Items $arguments) `
            -WindowStyle Minimized

        return $true
    }
    catch {
        Write-Fail "Не удалось запустить PuTTY: $($_.Exception.Message)"
        return $false
    }
}

function Get-SocksListenerProcess {
    try {
        $conn = Get-NetTCPConnection `
            -LocalAddress $SocksHost `
            -LocalPort $SocksPort `
            -State Listen `
            -ErrorAction SilentlyContinue |
            Select-Object -First 1

        if (-not $conn) {
            return $null
        }

        return Get-CimInstance Win32_Process `
            -Filter "ProcessId=$($conn.OwningProcess)" `
            -ErrorAction SilentlyContinue
    }
    catch {
        return $null
    }
}

function Stop-TunnelProcess([switch]$Quiet) {
    $listener = Get-SocksListenerProcess

    if (-not $listener) {
        if (-not $Quiet) {
            Write-Warn "На ${SocksHost}:$SocksPort нет слушающего процесса."
        }

        return $true
    }

    $name = [string]$listener.Name
    $path = [string]$listener.ExecutablePath
    $cmdline = [string]$listener.CommandLine

    $looksLikePutty = (
        $name -match '(?i)putty|plink' -or
        $path -match '(?i)putty|plink' -or
        $cmdline -match '(?i)AdminVPS|putty|plink'
    )

    if (-not $looksLikePutty) {
        if (-not $Quiet) {
            Write-Fail "Порт $SocksPort занят неизвестным процессом:"
            Write-Fail "  PID=$($listener.ProcessId) Name=$name"
            Write-Warn 'Fail-closed: процесс автоматически не завершается.'
        }

        return $false
    }

    try {
        Stop-Process -Id $listener.ProcessId -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 800

        if (-not $Quiet) {
            Write-Ok "PuTTY/SOCKS PID $($listener.ProcessId) остановлен."
        }

        return $true
    }
    catch {
        if (-not $Quiet) {
            Write-Fail "Не удалось остановить PID $($listener.ProcessId)."
        }

        return $false
    }
}

function Ensure-SocksTunnel([switch]$Quiet) {
    if (Test-SocksIdentity) {
        if (-not $Quiet) {
            Write-Ok "SOCKS5 ${SocksHost}:$SocksPort уже работает через $ExpectedVpsIp."
        }

        return $true
    }

    if (Test-TcpPort $SocksHost $SocksPort) {
        if (-not $Quiet) {
            Write-Warn "Порт $SocksPort открыт, но expected VPS identity не подтверждена."
        }

        [void](Stop-TunnelProcess -Quiet)
        Start-Sleep -Seconds 1
    }

    if (-not $Quiet) {
        Write-Host 'Запускаю AdminVPS через PuTTY...'
    }

    if (-not (Start-PuttyTunnel)) {
        return $false
    }

    $deadline = (Get-Date).AddSeconds($TunnelWaitSeconds)

    while ((Get-Date) -lt $deadline) {
        if (Test-SocksIdentity) {
            if (-not $Quiet) {
                Write-Ok "SOCKS5 поднят; VPS exit=$ExpectedVpsIp."
            }

            return $true
        }

        Start-Sleep -Milliseconds 900
    }

    if (-not $Quiet) {
        Write-Fail "Expected SOCKS/VPS не появился за $TunnelWaitSeconds секунд."
    }

    return $false
}

# ============================================================================
# PROXIFIER STANDARD
# ============================================================================

function Test-IsPortableProxifierPath([string]$Path) {
    if (-not $Path) {
        return $false
    }

    return (
        $Path -match '(?i)portable' -or
        $Path -match '(?i)proxifier\s*pe' -or
        $Path -match '(?i)yandexdisk.*proxifier'
    )
}

function Get-ProxifierRegistryCandidates {
    $result = New-Object System.Collections.Generic.List[string]

    $roots = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )

    foreach ($root in $roots) {
        try {
            Get-ItemProperty $root -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.DisplayName -match '(?i)^Proxifier' -and
                    $_.InstallLocation
                } |
                ForEach-Object {
                    $candidate = Join-Path $_.InstallLocation 'Proxifier.exe'

                    if (Test-Path -LiteralPath $candidate) {
                        [void]$result.Add($candidate)
                    }
                }
        }
        catch {
            # Continue.
        }
    }

    return @($result | Select-Object -Unique)
}

function Find-ProxifierStandard {
    $candidates = New-Object System.Collections.Generic.List[string]

    @(
        "$env:ProgramFiles\Proxifier\Proxifier.exe",
        "${env:ProgramFiles(x86)}\Proxifier\Proxifier.exe",
        "$env:LOCALAPPDATA\Programs\Proxifier\Proxifier.exe"
    ) | ForEach-Object {
        if ($_ -and (Test-Path -LiteralPath $_)) {
            [void]$candidates.Add($_)
        }
    }

    foreach ($candidate in @(Get-ProxifierRegistryCandidates)) {
        if ($candidate) {
            [void]$candidates.Add($candidate)
        }
    }

    try {
        Get-CimInstance Win32_Process `
            -Filter "Name='Proxifier.exe'" `
            -ErrorAction SilentlyContinue |
            ForEach-Object {
                if (
                    $_.ExecutablePath -and
                    (Test-Path -LiteralPath $_.ExecutablePath)
                ) {
                    [void]$candidates.Add($_.ExecutablePath)
                }
            }
    }
    catch {
        # Continue.
    }

    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (-not (Test-IsPortableProxifierPath $candidate)) {
            return $candidate
        }
    }

    return $null
}

function Stop-PortableProxifierInstances([string]$StandardPath) {
    try {
        Get-CimInstance Win32_Process `
            -Filter "Name='Proxifier.exe'" `
            -ErrorAction SilentlyContinue |
            ForEach-Object {
                $path = [string]$_.ExecutablePath

                if (-not $path) {
                    return
                }

                if ($StandardPath -and ($path -ieq $StandardPath)) {
                    return
                }

                if (Test-IsPortableProxifierPath $path) {
                    try {
                        Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
                        Write-Warn "Portable Proxifier остановлен: $path"
                    }
                    catch {
                        Write-Warn "Не удалось остановить Portable Proxifier PID $($_.ProcessId)."
                    }
                }
            }
    }
    catch {
        # Non-fatal.
    }
}

function Test-ProxifierStandardRunning([string]$ExpectedPath) {
    try {
        $process = Get-CimInstance Win32_Process `
            -Filter "Name='Proxifier.exe'" `
            -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ExecutablePath -and
                ($_.ExecutablePath -ieq $ExpectedPath)
            } |
            Select-Object -First 1

        return ($null -ne $process)
    }
    catch {
        return $false
    }
}

# ============================================================================
# ROUTING TARGETS
# ============================================================================


function Get-DefaultModuleCatalogJson {
    return @'
{
  "Version": "1",
  "OpenAI": {
    "Required": 1,
    "DegradedLatencyMs": 3500,
    "HealthUrls": [
      "https://chatgpt.com",
      "https://api.openai.com/v1/models"
    ],
    "Targets": [
      "*.auth.openai.com",
      "*.chatgpt.com",
      "chatgpt.com",
      "*.ct.sendgrid.net",
      "*.intercom.io",
      "*.intercomcdn.com",
      "*.oaistatic.com",
      "*.oaiusercontent.com",
      "*.openai.com",
      "openai.com",
      "*.oaistatsig.com",
      "auth0.openai.com",
      "cdn.openaimerge.com",
      "cdn.workos.com",
      "challenges.cloudflare.com",
      "chat.openai.com",
      "desktop.chat.openai.com",
      "forwarder.workos.com",
      "images.workoscdn.com",
      "js.intercomcdn.com",
      "js.stripe.com",
      "o207216.ingest.sentry.io",
      "o33249.ingest.sentry.io",
      "rum.browser-intake-datadoghq.com",
      "setup.auth.openai.com",
      "setup.workos.com",
      "tcr9i.chat.openai.com",
      "workos.imgix.net"
    ],
    "Applications": ["*ChatGPT*.exe", "*Codex*.exe"]
  },
  "GitHub": {
    "Required": 1,
    "DegradedLatencyMs": 2500,
    "HealthUrls": [
      "https://github.com",
      "https://api.github.com"
    ],
    "Targets": [
      "github.com",
      "*.github.com",
      "api.github.com",
      "ssh.github.com",
      "raw.githubusercontent.com",
      "codeload.github.com",
      "objects.githubusercontent.com",
      "media.githubusercontent.com",
      "user-images.githubusercontent.com",
      "avatars.githubusercontent.com",
      "release-assets.githubusercontent.com",
      "*.githubusercontent.com",
      "*.githubassets.com"
    ],
    "Applications": []
  },
  "DevPackages": {
    "Required": 2,
    "DegradedLatencyMs": 3000,
    "HealthUrls": [
      "https://registry.npmjs.org/npm/latest",
      "https://pypi.org/pypi/pip/json"
    ],
    "Targets": [
      "registry.npmjs.org",
      "*.npmjs.org",
      "npmjs.com",
      "*.npmjs.com",
      "nodejs.org",
      "*.nodejs.org",
      "pypi.org",
      "*.pypi.org",
      "files.pythonhosted.org",
      "*.pythonhosted.org"
    ],
    "Applications": []
  },
  "Firefox": {
    "Required": 1,
    "DegradedLatencyMs": 3000,
    "HealthUrls": [
      "https://www.cloudflare.com/cdn-cgi/trace",
      "https://example.com/"
    ],
    "Targets": [],
    "Applications": ["firefox.exe", "*\\\\firefox.exe"]
  }
}
'@
}

function Ensure-ModuleCatalog {
    if (Test-Path -LiteralPath $ModulesFile) {
        return $true
    }

    try {
        if (Test-Path -LiteralPath $LegacyV62ModulesFile) {
            Copy-Item -LiteralPath $LegacyV62ModulesFile -Destination $ModulesFile -Force
            Write-ControllerLog 'MODULE_CATALOG migrated from V6.2/6.2.1'
        }
        elseif (Test-Path -LiteralPath $BundledModulesFile) {
            Copy-Item -LiteralPath $BundledModulesFile -Destination $ModulesFile -Force
        }
        else {
            Write-TextAtomic -Path $ModulesFile -Text (Get-DefaultModuleCatalogJson)
        }

        return $true
    }
    catch {
        Write-ControllerLog "MODULE_CATALOG create failed: $($_.Exception.Message)"
        return $false
    }
}

function Get-ModuleCatalog {
    if (-not (Ensure-ModuleCatalog)) {
        return ((Get-DefaultModuleCatalogJson) | ConvertFrom-Json)
    }

    try {
        $catalog = (
            Get-Content -LiteralPath $ModulesFile -Raw -ErrorAction Stop |
            ConvertFrom-Json
        )

        # V6.2.1 migration: V6.2 used the enormous PyPI /simple root as a
        # health probe. That measured package-index download time, not route
        # quality. Repair an existing state catalog in place.
        $healthUrls = @($catalog.DevPackages.HealthUrls)
        $needsProbeHotfix = (
            $healthUrls -contains 'https://pypi.org/simple/' -or
            $healthUrls -contains 'https://registry.npmjs.org/'
        )

        if ($needsProbeHotfix) {
            $catalog.DevPackages.HealthUrls = @(
                'https://registry.npmjs.org/npm/latest',
                'https://pypi.org/pypi/pip/json'
            )

            Write-JsonAtomic -Path $ModulesFile -Object $catalog
            Write-ControllerLog 'MODULE_CATALOG V6.2.1 package-probe hotfix applied'
        }

        return $catalog
    }
    catch {
        Write-ControllerLog "MODULE_CATALOG parse failed: $($_.Exception.Message)"
        return ((Get-DefaultModuleCatalogJson) | ConvertFrom-Json)
    }
}

function Get-ModuleCatalogEntry([string]$Module) {
    $catalog = Get-ModuleCatalog
    $entry = $catalog.$Module

    if (-not $entry) {
        throw "Module catalog entry missing: $Module"
    }

    return $entry
}

function Get-OpenAITargets {
    return @((Get-ModuleCatalogEntry 'OpenAI').Targets)
}

function Get-GitHubTargets {
    return @((Get-ModuleCatalogEntry 'GitHub').Targets)
}

function Get-DevPackageTargets {
    return @((Get-ModuleCatalogEntry 'DevPackages').Targets)
}

function New-ProxifierProfile($Routes, [string]$DestinationPath) {
    $r = Normalize-Routes $Routes
    $hasVps = Test-AnyEffectiveVps $r
    $rules = New-Object System.Collections.Generic.List[string]

    [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>Localhost DIRECT</Name>
      <Targets>localhost; 127.0.0.1; ::1; %ComputerName%</Targets>
      <Action type="Direct" />
    </Rule>
"@)

    [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>Tunnel infrastructure DIRECT</Name>
      <Applications>putty.exe; putty_portable.exe; plink.exe; proxifier.exe</Applications>
      <Action type="Direct" />
    </Rule>
"@)

    [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>VPS Control direct probe DIRECT</Name>
      <Applications>vps-control-direct-probe.exe</Applications>
      <Action type="Direct" />
    </Rule>
"@)

    if ($hasVps) {
        [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>VPS Control route verification</Name>
      <Applications>vps-control-vps-probe.exe</Applications>
      <Action type="Proxy">100</Action>
    </Rule>
"@)
    }
    else {
        [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>VPS Control route verification DIRECT</Name>
      <Applications>vps-control-vps-probe.exe</Applications>
      <Action type="Direct" />
    </Rule>
"@)
    }

    if ($r.Firefox -eq 'VPS') {
        [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>MODULE Firefox VPS</Name>
      <Applications>$((@((Get-ModuleCatalogEntry 'Firefox').Applications)) -join '; ')</Applications>
      <Action type="Proxy">100</Action>
    </Rule>
"@)
    }

    if ($r.OpenAI -eq 'VPS') {
        $targets = (Get-OpenAITargets | Select-Object -Unique) -join '; '

        [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>MODULE OpenAI apps VPS</Name>
      <Applications>$((@((Get-ModuleCatalogEntry 'OpenAI').Applications)) -join '; ')</Applications>
      <Action type="Proxy">100</Action>
    </Rule>
"@)

        [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>MODULE OpenAI destinations VPS</Name>
      <Targets>$targets</Targets>
      <Action type="Proxy">100</Action>
    </Rule>
"@)
    }

    if ($r.GitHub -eq 'VPS') {
        $targets = (Get-GitHubTargets | Select-Object -Unique) -join '; '

        [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>MODULE GitHub destinations VPS</Name>
      <Targets>$targets</Targets>
      <Action type="Proxy">100</Action>
    </Rule>
"@)
    }

    if ($r.DevPackages -eq 'VPS') {
        $targets = (Get-DevPackageTargets | Select-Object -Unique) -join '; '

        [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>MODULE DevPackages destinations VPS</Name>
      <Targets>$targets</Targets>
      <Action type="Proxy">100</Action>
    </Rule>
"@)
    }

    [void]$rules.Add(@"
    <Rule enabled="true">
      <Name>Default DIRECT</Name>
      <Action type="Direct" />
    </Rule>
"@)

    if ($hasVps) {
        $proxyXml = @"
  <ProxyList>
    <Proxy id="100" type="SOCKS5">
      <Address>$SocksHost</Address>
      <Port>$SocksPort</Port>
      <Options>48</Options>
    </Proxy>
  </ProxyList>
"@
    }
    else {
        $proxyXml = '  <ProxyList />'
    }

    $ruleXml = $rules -join "`n"

    $xml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ProxifierProfile version="101" platform="Windows" product_id="0" product_minver="310">
  <Options>
    <Resolve>
      <AutoModeDetection enabled="true" />
      <ViaProxy enabled="false">
        <TryLocalDnsFirst enabled="false" />
      </ViaProxy>
      <ExclusionList>%ComputerName%; localhost; *.local</ExclusionList>
    </Resolve>
    <Encryption mode="basic" />
    <HttpProxiesSupport enabled="false" />
    <HandleDirectConnections enabled="false" />
    <ConnectionLoopDetection enabled="true" />
    <ProcessServices enabled="true" />
    <ProcessOtherUsers enabled="false" />
  </Options>

$proxyXml

  <ChainList />

  <RuleList>
$ruleXml
  </RuleList>
</ProxifierProfile>
"@

    Write-TextAtomic -Path $DestinationPath -Text $xml
    return $DestinationPath
}


function Invoke-ProxifierRawLoad(
    [string]$ProxifierPath,
    [string]$ProfileFile
) {
    try {
        $args = @($ProfileFile, 'silent-load')

        Start-Process `
            -FilePath $ProxifierPath `
            -ArgumentList (Convert-ToProcessArgumentString -Items $args)

        Start-Sleep -Seconds 2
        return $true
    }
    catch {
        Write-ControllerLog "PROXIFIER raw load failed: $($_.Exception.Message)"
        return $false
    }
}

function Save-LastGoodProfile(
    [string]$Path,
    $Routes
) {
    try {
        Copy-Item -LiteralPath $Path -Destination $LastGoodProfilePath -Force

        $meta = [pscustomobject]@{
            SavedAt = (Get-Date).ToString('o')
            Hash = (Get-FileHash -LiteralPath $LastGoodProfilePath -Algorithm SHA256).Hash
            Routes = $(Normalize-Routes $Routes)
        }

        Write-JsonAtomic -Path $LastGoodProfileMetaPath -Object $meta
    }
    catch {
        Write-ControllerLog "LKG profile save failed: $($_.Exception.Message)"
    }
}

function Restore-LastGoodProfile([string]$ProxifierPath) {
    if (-not (Test-Path -LiteralPath $LastGoodProfilePath)) {
        return $false
    }

    Write-Warn 'Пробую rollback на last-known-good Proxifier profile.'
    Write-ControllerLog 'PROXIFIER rollback attempt'

    if (-not (Invoke-ProxifierRawLoad -ProxifierPath $ProxifierPath -ProfileFile $LastGoodProfilePath)) {
        return $false
    }

    if (-not (Test-ProxifierStandardRunning $ProxifierPath)) {
        return $false
    }

    Write-ControllerLog 'PROXIFIER rollback loaded'
    return $true
}

function Load-ProxifierProfile(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)]$Routes
) {
    if (-not (Ensure-ProbeHelpers)) {
        return $false
    }

    $proxifier = Find-ProxifierStandard

    if (-not $proxifier) {
        Write-Fail 'Proxifier Standard не найден. Portable Edition запрещён.'
        return $false
    }

    Stop-PortableProxifierInstances $proxifier

    $expectedHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash

    if (-not (Invoke-ProxifierRawLoad -ProxifierPath $proxifier -ProfileFile $Path)) {
        [void](Restore-LastGoodProfile -ProxifierPath $proxifier)
        return $false
    }

    if (-not (Test-ProxifierStandardRunning $proxifier)) {
        Write-Fail 'Proxifier Standard не подтверждён как running после load.'
        [void](Restore-LastGoodProfile -ProxifierPath $proxifier)
        return $false
    }

    $actualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash

    if ($expectedHash -ne $actualHash) {
        Write-Fail 'Generated Proxifier profile hash changed during load.'
        [void](Restore-LastGoodProfile -ProxifierPath $proxifier)
        return $false
    }

    if (Test-AnyEffectiveVps $Routes) {
        $routedIp = Get-VpsProfileExternalIp

        if ($routedIp -ne $ExpectedVpsIp) {
            Write-Fail "Post-load route verification failed: $routedIp != $ExpectedVpsIp"
            [void](Restore-LastGoodProfile -ProxifierPath $proxifier)
            return $false
        }

        Write-Ok "Proxifier post-load VPS route verified: $routedIp"
    }

    $directIp = Get-DirectExternalIp

    if ($directIp) {
        if ($directIp -eq $ExpectedVpsIp) {
            Write-Warn 'Direct probe exit equals VPS IP. Full-system VPN may still be active.'
        }
        else {
            Write-Ok "Direct probe bypass verified: $directIp"
        }
    }

    Save-LastGoodProfile -Path $Path -Routes $Routes
    return $true
}

function Apply-EffectiveRoutesOnly(
    [Parameter(Mandatory=$true)]$Routes,
    [Parameter(Mandatory=$true)][string]$Reason
) {
    $r = Normalize-Routes $Routes

    if (Test-AnyEffectiveVps $r) {
        if (-not (Ensure-SocksTunnel -Quiet)) {
            Write-Fail 'VPS route required but expected SOCKS tunnel is unavailable.'
            return $false
        }
    }

    $path = New-ProxifierProfile -Routes $r -DestinationPath $ProfilePath

    if (-not (Load-ProxifierProfile -Path $path -Routes $r)) {
        return $false
    }

    $runtime = Get-Runtime
    $runtime.Override = 'NONE'
    $runtime.Effective = $r
    $runtime.ProfileHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    $runtime.LastReason = $Reason
    Save-Runtime $runtime

    $routeParts = foreach ($moduleName in $ModuleNames) {
        "$moduleName=$($r.$moduleName)"
    }

    $routeSummary = $routeParts -join ','
    Write-ControllerLog "APPLY reason=$Reason routes=$routeSummary"
    return $true
}


# ============================================================================
# OBSERVABILITY / TELEMETRY / SELF-TEST STATE
# ============================================================================

function Write-JsonLine([string]$Path, $Object) {
    try {
        $line = ($Object | ConvertTo-Json -Depth 12 -Compress)
        Add-Content -LiteralPath $Path -Value $line -Encoding UTF8
        return $true
    }
    catch {
        Write-ControllerLog "JSONL append failed path=$Path error=$($_.Exception.Message)"
        return $false
    }
}

function New-OperationalModuleStats {
    return [pscustomobject]@{
        DirectSeconds = 0.0
        VpsSeconds = 0.0
        HealthySeconds = 0.0
        DegradedSeconds = 0.0
        FailedSeconds = 0.0
        Switches = 0
    }
}

function New-OperationalStats {
    $modules = [pscustomobject]@{}

    foreach ($module in $ModuleNames) {
        Add-Member -InputObject $modules -NotePropertyName $module -NotePropertyValue (New-OperationalModuleStats)
    }

    return [pscustomobject]@{
        Version = $ControllerVersion
        StartedAt = (Get-Date).ToString('o')
        LastUpdatedAt = ''
        LastRoutes = $(New-RouteObject)
        LastHealth = $(New-HealthObject)
        Modules = $modules
    }
}

function Normalize-OperationalModuleStats($InputStats) {
    $result = New-OperationalModuleStats

    if (-not $InputStats) {
        return $result
    }

    foreach ($name in @(
        'DirectSeconds',
        'VpsSeconds',
        'HealthySeconds',
        'DegradedSeconds',
        'FailedSeconds'
    )) {
        if ($InputStats.$name -ne $null) {
            $result.$name = [double]$InputStats.$name
        }
    }

    if ($InputStats.Switches -ne $null) {
        $result.Switches = [int]$InputStats.Switches
    }

    return $result
}

function Get-OperationalStats {
    if (-not (Test-Path -LiteralPath $OperationalStatsFile)) {
        return (New-OperationalStats)
    }

    try {
        $raw = Get-Content -LiteralPath $OperationalStatsFile -Raw -ErrorAction Stop
        $input = $raw | ConvertFrom-Json
        $result = New-OperationalStats

        if ($input.StartedAt) { $result.StartedAt = [string]$input.StartedAt }
        if ($input.LastUpdatedAt) { $result.LastUpdatedAt = [string]$input.LastUpdatedAt }
        $result.LastRoutes = Normalize-Routes $input.LastRoutes
        $result.LastHealth = Normalize-Health $input.LastHealth

        foreach ($module in $ModuleNames) {
            $result.Modules.$module = Normalize-OperationalModuleStats $input.Modules.$module
        }

        return $result
    }
    catch {
        Write-ControllerLog "OP_STATS parse failed: $($_.Exception.Message)"
        return (New-OperationalStats)
    }
}

function Save-OperationalStats($Stats) {
    try {
        $Stats.Version = $ControllerVersion
        Write-JsonAtomic -Path $OperationalStatsFile -Object $Stats
    }
    catch {
        Write-ControllerLog "OP_STATS save failed: $($_.Exception.Message)"
    }
}

function Update-OperationalStats($Routes, $Health) {
    try {
        $now = Get-Date
        $stats = Get-OperationalStats
        $delta = 0.0

        if ($stats.LastUpdatedAt) {
            try {
                $delta = ($now - [datetime]$stats.LastUpdatedAt).TotalSeconds
            }
            catch {
                $delta = 0.0
            }
        }

        if ($delta -lt 0) { $delta = 0.0 }
        if ($delta -gt $OperationalStatsMaxGapSeconds) {
            # Do not count machine sleep/offline time as controller uptime.
            $delta = [double]$OperationalStatsMaxGapSeconds
        }

        foreach ($module in $ModuleNames) {
            $previousRoute = [string]$stats.LastRoutes.$module
            $previousHealth = [string]$stats.LastHealth.$module
            $currentRoute = [string]$Routes.$module
            $currentHealth = [string]$Health.$module
            $m = $stats.Modules.$module

            if ($delta -gt 0) {
                if ($previousRoute -eq 'VPS') {
                    $m.VpsSeconds += $delta
                }
                else {
                    $m.DirectSeconds += $delta
                }

                switch ($previousHealth) {
                    'HEALTHY' { $m.HealthySeconds += $delta }
                    'DEGRADED' { $m.DegradedSeconds += $delta }
                    'FAILED' { $m.FailedSeconds += $delta }
                }
            }

            if (
                $stats.LastUpdatedAt -and
                $previousRoute -and
                $previousRoute -ne $currentRoute
            ) {
                $m.Switches = [int]$m.Switches + 1
            }

            $stats.Modules.$module = $m
            $stats.LastRoutes.$module = $currentRoute
            $stats.LastHealth.$module = $currentHealth
        }

        $stats.LastUpdatedAt = $now.ToString('o')
        Save-OperationalStats $stats
    }
    catch {
        Write-ControllerLog "OP_STATS update failed: $($_.Exception.Message)"
    }
}

function Get-TelemetryLastSampleAt {
    if (-not (Test-Path -LiteralPath $TelemetryMetaFile)) {
        return ''
    }

    try {
        $meta = Get-Content -LiteralPath $TelemetryMetaFile -Raw | ConvertFrom-Json
        return [string]$meta.LastSampleAt
    }
    catch {
        return ''
    }
}

function Record-TelemetrySnapshot($Runtime, [switch]$Force) {
    try {
        $now = Get-Date
        $meta = $null

        if (Test-Path -LiteralPath $TelemetryMetaFile) {
            try {
                $meta = Get-Content -LiteralPath $TelemetryMetaFile -Raw | ConvertFrom-Json
            }
            catch {
                $meta = $null
            }
        }

        $last = if ($meta -and $meta.LastSampleAt) { [string]$meta.LastSampleAt } else { '' }

        if (-not $Force -and $last) {
            try {
                if (($now - [datetime]$last).TotalSeconds -lt $TelemetrySampleSeconds) {
                    return
                }
            }
            catch {
                # Record a fresh sample.
            }
        }

        foreach ($module in $ModuleNames) {
            $metric = Normalize-ModuleMetric $Runtime.Metrics.$module

            $sample = [pscustomobject]@{
                Timestamp = $now.ToString('o')
                Module = $module
                Route = [string]$Runtime.Effective.$module
                State = [string]$metric.State
                LatencyMs = [int]$metric.LatencyMs
                FailureClass = [string]$metric.FailureClass
                LastReason = [string]$Runtime.LastReason
            }

            [void](Write-JsonLine -Path $TelemetryFile -Object $sample)
        }

        $lastTrim = if ($meta -and $meta.LastTrimAt) { [string]$meta.LastTrimAt } else { '' }
        $trimDue = $false

        if (-not $lastTrim) {
            $trimDue = $true
        }
        else {
            try {
                $trimDue = (($now - [datetime]$lastTrim).TotalHours -ge 24)
            }
            catch {
                $trimDue = $true
            }
        }

        if ($trimDue) {
            Trim-TelemetryHistory
            $lastTrim = $now.ToString('o')
        }

        Write-JsonAtomic `
            -Path $TelemetryMetaFile `
            -Object ([pscustomobject]@{
                LastSampleAt = $now.ToString('o')
                LastTrimAt = $lastTrim
            })
    }
    catch {
        Write-ControllerLog "TELEMETRY snapshot failed: $($_.Exception.Message)"
    }
}

function Trim-TelemetryHistory {
    if (-not (Test-Path -LiteralPath $TelemetryFile)) {
        return
    }

    try {
        $cutoff = (Get-Date).AddDays(-$TelemetryRetentionDays)
        $temp = "$TelemetryFile.tmp"

        if (Test-Path -LiteralPath $temp) {
            Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
        }

        foreach ($line in Get-Content -LiteralPath $TelemetryFile -ErrorAction Stop) {
            if (-not $line) { continue }

            try {
                $item = $line | ConvertFrom-Json

                if ([datetime]$item.Timestamp -ge $cutoff) {
                    Add-Content -LiteralPath $temp -Value $line -Encoding UTF8
                }
            }
            catch {
                # Drop corrupt telemetry line.
            }
        }

        if (Test-Path -LiteralPath $temp) {
            Move-Item -LiteralPath $temp -Destination $TelemetryFile -Force
        }
    }
    catch {
        Write-ControllerLog "TELEMETRY trim failed: $($_.Exception.Message)"
    }
}

function Get-Percentile([double[]]$Values, [double]$Percentile) {
    if (-not $Values -or $Values.Count -eq 0) {
        return 0
    }

    $sorted = @($Values | Sort-Object)

    if ($sorted.Count -eq 1) {
        return [int][math]::Round($sorted[0])
    }

    $rank = ($Percentile / 100.0) * ($sorted.Count - 1)
    $lower = [int][math]::Floor($rank)
    $upper = [int][math]::Ceiling($rank)

    if ($lower -eq $upper) {
        return [int][math]::Round($sorted[$lower])
    }

    $weight = $rank - $lower
    $value = ($sorted[$lower] * (1.0 - $weight)) + ($sorted[$upper] * $weight)
    return [int][math]::Round($value)
}

function Get-ObservationSummary([int]$Hours = $ObservationSummaryHours) {
    # WinPS 5.1 compatibility: do not use @($GenericList[object]).
    $cutoff = (Get-Date).AddHours(-$Hours)
    $grouped = @{}

    foreach ($module in $ModuleNames) {
        $grouped[$module] = New-Object System.Collections.ArrayList
    }

    if (Test-Path -LiteralPath $TelemetryFile) {
        foreach ($line in Get-Content -LiteralPath $TelemetryFile -ErrorAction SilentlyContinue) {
            if (-not $line) { continue }

            try {
                $item = $line | ConvertFrom-Json

                if (
                    [datetime]$item.Timestamp -ge $cutoff -and
                    $grouped.ContainsKey([string]$item.Module)
                ) {
                    [void]$grouped[[string]$item.Module].Add($item)
                }
            }
            catch {
                # Ignore malformed historical sample.
            }
        }
    }

    $rows = New-Object System.Collections.ArrayList

    foreach ($module in $ModuleNames) {
        $items = @($grouped[$module].ToArray())
        $count = $items.Count
        $healthyPct = 0
        $directPct = 0
        $avg = 0
        $p95 = 0
        $failures = 0

        if ($count -gt 0) {
            $healthy = @($items | Where-Object { $_.State -eq 'HEALTHY' }).Count
            $direct = @($items | Where-Object { $_.Route -eq 'DIRECT' }).Count
            $failures = @($items | Where-Object { $_.State -eq 'FAILED' }).Count
            $latencies = @(
                $items |
                    Where-Object { [int]$_.LatencyMs -gt 0 } |
                    ForEach-Object { [double]$_.LatencyMs }
            )

            $healthyPct = [int][math]::Round(($healthy * 100.0) / $count)
            $directPct = [int][math]::Round(($direct * 100.0) / $count)

            if ($latencies.Count -gt 0) {
                $avg = [int][math]::Round(
                    ($latencies | Measure-Object -Average).Average
                )
                $p95 = Get-Percentile -Values $latencies -Percentile 95
            }
        }

        [void]$rows.Add([pscustomobject]@{
            Module = $module
            Samples = $count
            HealthyPct = $healthyPct
            DirectPct = $directPct
            AvgMs = $avg
            P95Ms = $p95
            FailedSamples = $failures
        })
    }

    return $rows.ToArray()
}

function Show-ObservationSummary([int]$Hours = $ObservationSummaryHours) {
    Write-Step "Observability summary - last ${Hours}h"

    $rows = Get-ObservationSummary -Hours $Hours

    Write-Host (
        '  {0,-14} {1,7} {2,9} {3,9} {4,8} {5,8} {6,8}' -f
        'Module','Samples','Healthy%','Direct%','Avg ms','P95 ms','Failed'
    )
    Write-Host (
        '  {0,-14} {1,7} {2,9} {3,9} {4,8} {5,8} {6,8}' -f
        '------','-------','--------','-------','------','------','------'
    )

    foreach ($row in $rows) {
        Write-Host (
            '  {0,-14} {1,7} {2,9} {3,9} {4,8} {5,8} {6,8}' -f
            $row.Module,
            $row.Samples,
            $row.HealthyPct,
            $row.DirectPct,
            $row.AvgMs,
            $row.P95Ms,
            $row.FailedSamples
        )
    }

    $stats = Get-OperationalStats

    Write-Host ''
    Write-Host 'Cumulative active-controller statistics (sleep/offline gaps excluded):'
    Write-Host (
        '  {0,-14} {1,10} {2,10} {3,10} {4,9}' -f
        'Module','DIRECT h','VPS h','Healthy%','Switches'
    )

    foreach ($module in $ModuleNames) {
        $m = $stats.Modules.$module
        $directH = [math]::Round(([double]$m.DirectSeconds / 3600.0), 2)
        $vpsH = [math]::Round(([double]$m.VpsSeconds / 3600.0), 2)
        $healthTotal = [double]$m.HealthySeconds + [double]$m.DegradedSeconds + [double]$m.FailedSeconds
        $healthyPct = 0

        if ($healthTotal -gt 0) {
            $healthyPct = [int][math]::Round(([double]$m.HealthySeconds * 100.0) / $healthTotal)
        }

        Write-Host (
            '  {0,-14} {1,10} {2,10} {3,10} {4,9}' -f
            $module,
            $directH,
            $vpsH,
            $healthyPct,
            $m.Switches
        )
    }
}

function Write-WatchdogHeartbeat($Runtime) {
    try {
        $payload = [pscustomobject]@{
            Timestamp = (Get-Date).ToString('o')
            Pid = $PID
            Routes = $(Normalize-Routes $Runtime.Effective)
            Health = $(Normalize-Health $Runtime.Health)
        }

        Write-JsonAtomic -Path $WatchdogHeartbeatFile -Object $payload
    }
    catch {
        Write-ControllerLog "HEARTBEAT write failed: $($_.Exception.Message)"
    }
}

function Get-WatchdogHeartbeatStatus {
    if (-not (Test-Path -LiteralPath $WatchdogHeartbeatFile)) {
        return [pscustomobject]@{
            Present = $false
            AgeSeconds = 0
            Stale = $true
            Timestamp = ''
            Pid = 0
        }
    }

    try {
        $hb = Get-Content -LiteralPath $WatchdogHeartbeatFile -Raw | ConvertFrom-Json
        $age = ((Get-Date) - [datetime]$hb.Timestamp).TotalSeconds

        return [pscustomobject]@{
            Present = $true
            AgeSeconds = [int][math]::Round($age)
            Stale = ($age -gt $WatchdogHeartbeatStaleSeconds)
            Timestamp = [string]$hb.Timestamp
            Pid = [int]$hb.Pid
        }
    }
    catch {
        return [pscustomobject]@{
            Present = $true
            AgeSeconds = 0
            Stale = $true
            Timestamp = ''
            Pid = 0
        }
    }
}

function Write-IncidentSnapshot(
    [string]$Module,
    [string]$From,
    [string]$To,
    [string]$Reason,
    [string]$Detail
) {
    try {
        $runtime = Get-Runtime
        $snapshot = [pscustomobject]@{
            Timestamp = (Get-Date).ToString('o')
            Module = $Module
            From = $From
            To = $To
            Reason = $Reason
            Detail = $Detail
            Routes = $(Normalize-Routes $runtime.Effective)
            Health = $(Normalize-Health $runtime.Health)
            Metrics = $(Normalize-Metrics $runtime.Metrics)
        }

        [void](Write-JsonLine -Path $IncidentFile -Object $snapshot)
    }
    catch {
        Write-ControllerLog "INCIDENT snapshot failed: $($_.Exception.Message)"
    }
}

function Get-DailySelfTestTask {
    try {
        return Get-ScheduledTask -TaskName $SelfTestTaskName -ErrorAction SilentlyContinue
    }
    catch {
        return $null
    }
}

function Get-LastSelfTestResult {
    if (-not (Test-Path -LiteralPath $SelfTestHistoryFile)) {
        return $null
    }

    try {
        $line = Get-Content -LiteralPath $SelfTestHistoryFile -Tail 1 -ErrorAction Stop

        if (-not $line) {
            return $null
        }

        return ($line | ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

function Add-SelfTestResult(
    [System.Collections.IList]$Items,
    [string]$Name,
    [ValidateSet('PASS','WARN','FAIL')]
    [string]$State,
    [string]$Detail
) {
    [void]$Items.Add([pscustomobject]@{
        Name = $Name
        State = $State
        Detail = $Detail
    })
}

function Invoke-ReadOnlySelfTest([switch]$Quiet) {
    if (-not $Quiet) {
        Write-Step 'V6.3.1 READ-ONLY SELF-TEST'
    }

    $items = New-Object System.Collections.ArrayList
    $runtime = $null
    $config = $null

    try {
        $config = Get-Config
        $runtime = Get-Runtime
        Add-SelfTestResult $items 'State' 'PASS' 'config/runtime readable'
    }
    catch {
        Add-SelfTestResult $items 'State' 'FAIL' $_.Exception.Message
    }

    $directIp = Get-DirectExternalIp

    if ($directIp) {
        if ($directIp -eq $ExpectedVpsIp) {
            Add-SelfTestResult $items 'Direct exit' 'WARN' "DIRECT=$directIp equals VPS; full-system VPN possible"
        }
        else {
            Add-SelfTestResult $items 'Direct exit' 'PASS' $directIp
        }
    }
    else {
        Add-SelfTestResult $items 'Direct exit' 'FAIL' 'unable to resolve direct public IP'
    }

    if ($runtime -and (Test-AnyEffectiveVps $runtime.Effective)) {
        if (Test-SocksIdentity) {
            Add-SelfTestResult $items 'SOCKS/VPS' 'PASS' $ExpectedVpsIp
        }
        else {
            Add-SelfTestResult $items 'SOCKS/VPS' 'FAIL' 'expected VPS identity not confirmed'
        }
    }

    $proxifier = Find-ProxifierStandard

    if ($proxifier -and (Test-ProxifierStandardRunning $proxifier)) {
        Add-SelfTestResult $items 'Proxifier' 'PASS' $proxifier
    }
    else {
        Add-SelfTestResult $items 'Proxifier' 'FAIL' 'Proxifier Standard not running'
    }

    if ($runtime -and $config -and $runtime.Override -ne 'DIRECT' -and (Test-NeedsWatchdog -Config $config -Routes $runtime.Effective)) {
        $watchPid = Get-WatchdogPid

        if ($watchPid) {
            $heartbeat = Get-WatchdogHeartbeatStatus

            if (-not $heartbeat.Present) {
                Add-SelfTestResult $items 'Watchdog' 'WARN' "PID=$watchPid, heartbeat not yet present"
            }
            elseif ($heartbeat.Stale) {
                Add-SelfTestResult $items 'Watchdog' 'FAIL' "PID=$watchPid heartbeat stale age=$($heartbeat.AgeSeconds)s"
            }
            else {
                Add-SelfTestResult $items 'Watchdog' 'PASS' "PID=$watchPid heartbeat age=$($heartbeat.AgeSeconds)s"
            }
        }
        else {
            Add-SelfTestResult $items 'Watchdog' 'FAIL' 'expected running but PID not verified'
        }
    }

    if ($runtime) {
        foreach ($module in $ModuleNames) {
            $route = [string]$runtime.Effective.$module
            $probe = Test-ModuleHealth -Module $module -Route $route

            if ($probe.State -eq 'FAILED') {
                Add-SelfTestResult $items $module 'FAIL' "$route $($probe.FailureClass) $($probe.Detail)"
            }
            elseif ($probe.State -eq 'DEGRADED') {
                Add-SelfTestResult $items $module 'WARN' "$route latency=$($probe.LatencyMs)ms"
            }
            else {
                Add-SelfTestResult $items $module 'PASS' "$route latency=$($probe.LatencyMs)ms"
            }
        }
    }

    if (Get-Command git.exe -ErrorAction SilentlyContinue) {
        try {
            $repoUrl = 'https://github.com/kmephis-ai/AI-Development-Framework.git'
            $ls = Invoke-Git -Arguments @('ls-remote','--heads',$repoUrl,'main')
            $sha = Get-FirstGitSha $ls

            if ($ls.ExitCode -eq 0 -and $sha) {
                Add-SelfTestResult $items 'GitHub git' 'PASS' "ls-remote main=$sha"
            }
            else {
                Add-SelfTestResult $items 'GitHub git' 'FAIL' 'ls-remote failed'
            }
        }
        catch {
            Add-SelfTestResult $items 'GitHub git' 'FAIL' $_.Exception.Message
        }
    }
    else {
        Add-SelfTestResult $items 'GitHub git' 'WARN' 'git.exe not found'
    }

    $failCount = @($items | Where-Object { $_.State -eq 'FAIL' }).Count
    $warnCount = @($items | Where-Object { $_.State -eq 'WARN' }).Count
    $overall = if ($failCount -gt 0) { 'FAIL' } elseif ($warnCount -gt 0) { 'WARN' } else { 'PASS' }

    $result = [pscustomobject]@{
        Timestamp = (Get-Date).ToString('o')
        Version = $ControllerVersion
        Overall = $overall
        Failures = $failCount
        Warnings = $warnCount
        Items = $items.ToArray()
    }

    [void](Write-JsonLine -Path $SelfTestHistoryFile -Object $result)

    if ($overall -eq 'FAIL') {
        try {
            Write-JsonAtomic -Path $AttentionFile -Object ([pscustomobject]@{
                Timestamp = $result.Timestamp
                Source = 'SELF_TEST'
                State = 'FAIL'
                Failures = $failCount
            })
        }
        catch {
            # Non-fatal.
        }
    }
    else {
        Remove-Item -LiteralPath $AttentionFile -Force -ErrorAction SilentlyContinue
    }

    if (-not $Quiet) {
        Write-Host ''
        foreach ($item in $items) {
            switch ($item.State) {
                'PASS' { Write-Ok "$($item.Name): $($item.Detail)" }
                'WARN' { Write-Warn "$($item.Name): $($item.Detail)" }
                'FAIL' { Write-Fail "$($item.Name): $($item.Detail)" }
            }
        }

        Write-Host ''
        if ($overall -eq 'PASS') {
            Write-Ok 'READ-ONLY SELF-TEST: PASS'
        }
        elseif ($overall -eq 'WARN') {
            Write-Warn 'READ-ONLY SELF-TEST: WARN'
        }
        else {
            Write-Fail 'READ-ONLY SELF-TEST: FAIL'
        }
    }

    return $result
}

function Install-DailySelfTest([string]$AtTime = $SelfTestDefaultTime) {
    Write-Step 'Daily read-only self-test'

    if ($AtTime -notmatch '^(?:[01]\d|2[0-3]):[0-5]\d$') {
        Write-Fail "Некорректное время: $AtTime. Формат HH:mm."
        return $false
    }

    try {
        $parts = $AtTime.Split(':')
        $when = [datetime]::Today.AddHours([int]$parts[0]).AddMinutes([int]$parts[1])

        $taskAction = New-ScheduledTaskAction `
            -Execute 'powershell.exe' `
            -Argument (
                '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden ' +
                "-File `"$PSCommandPath`" -Action DailySelfTest -NoAppLaunch"
            )

        $trigger = New-ScheduledTaskTrigger -Daily -At $when
        $settings = New-ScheduledTaskSettingsSet `
            -StartWhenAvailable `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

        Register-ScheduledTask `
            -TaskName $SelfTestTaskName `
            -Action $taskAction `
            -Trigger $trigger `
            -Settings $settings `
            -Description 'VPS Control V6.3 read-only daily route/self-test. No GitHub writes.' `
            -Force | Out-Null

        Write-Ok "Daily self-test installed: $AtTime"
        return $true
    }
    catch {
        Write-Fail "Daily self-test install failed: $($_.Exception.Message)"
        return $false
    }
}

function Remove-DailySelfTest {
    try {
        $task = Get-DailySelfTestTask

        if ($task) {
            Unregister-ScheduledTask -TaskName $SelfTestTaskName -Confirm:$false
            Write-Ok 'Daily self-test task removed.'
        }
        else {
            Write-Info 'Daily self-test task is not installed.'
        }

        return $true
    }
    catch {
        Write-Fail "Daily self-test removal failed: $($_.Exception.Message)"
        return $false
    }
}

function Copy-SanitizedTextFile([string]$Source, [string]$Destination) {
    if (-not (Test-Path -LiteralPath $Source)) {
        return
    }

    try {
        $raw = Get-Content -LiteralPath $Source -Raw -ErrorAction Stop
        $raw = [regex]::Replace($raw, '(?i)(-pw\s+)(\S+)', '$1<REDACTED>')
        $raw = [regex]::Replace($raw, '(?i)(github_pat_[A-Za-z0-9_]+)', '<REDACTED_GITHUB_TOKEN>')
        $raw = [regex]::Replace($raw, '(?i)(ghp_[A-Za-z0-9]+)', '<REDACTED_GITHUB_TOKEN>')
        $raw = [regex]::Replace($raw, '(?i)(sk-[A-Za-z0-9_-]{12,})', '<REDACTED_API_KEY>')
        Set-Content -LiteralPath $Destination -Value $raw -Encoding UTF8
    }
    catch {
        Write-ControllerLog "SUPPORT sanitize copy failed source=$Source error=$($_.Exception.Message)"
    }
}

function New-SupportBundle {
    Write-Step 'Sanitized support bundle'

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $desktop = [Environment]::GetFolderPath('Desktop')

    if (-not $desktop) {
        $desktop = $env:USERPROFILE
    }

    $work = Join-Path $env:TEMP "VPS-Control-v6.3-support-$stamp"
    $zip = Join-Path $desktop "VPS-Control-v6.3-support-$stamp.zip"

    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $work -Force | Out-Null

    try {
        $manifest = [pscustomobject]@{
            Version = $ControllerVersion
            CreatedAt = (Get-Date).ToString('o')
            Computer = $env:COMPUTERNAME
            User = $env:USERNAME
            OsVersion = [Environment]::OSVersion.VersionString
            PasswordIncluded = $false
            ControllerScriptIncluded = $false
            LastGoodProfileIncluded = $false
        }

        Write-JsonAtomic -Path (Join-Path $work 'manifest.json') -Object $manifest

        foreach ($file in @(
            $ConfigFile,
            $RuntimeFile,
            $ModulesFile,
            $OperationalStatsFile,
            $LastGoodProfileMetaPath,
            $TelemetryMetaFile,
            $WatchdogHeartbeatFile,
            $AttentionFile
        )) {
            if (Test-Path -LiteralPath $file) {
                Copy-Item -LiteralPath $file -Destination (Join-Path $work ([IO.Path]::GetFileName($file))) -Force
            }
        }

        foreach ($file in @(
            $ControllerLogFile,
            $WatchdogLogFile,
            $DecisionLogFile,
            $SelfTestHistoryFile,
            $IncidentFile,
            $TelemetryFile
        )) {
            if (Test-Path -LiteralPath $file) {
                Copy-SanitizedTextFile `
                    -Source $file `
                    -Destination (Join-Path $work ([IO.Path]::GetFileName($file)))
            }
        }

        Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
        Compress-Archive -Path (Join-Path $work '*') -DestinationPath $zip -CompressionLevel Optimal -Force
        Write-Ok "Support bundle created: $zip"
        Write-Host 'Пароль, controller .ps1 и last-known-good.ppx в bundle НЕ включаются.'
        return $true
    }
    catch {
        Write-Fail "Support bundle failed: $($_.Exception.Message)"
        return $false
    }
    finally {
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }
}


# ============================================================================
# ROUTE RESOLUTION / APPLY
# ============================================================================


function Test-PreferVpsForLatency($DirectProbe, $VpsProbe) {
    if (-not $DirectProbe -or -not $VpsProbe) {
        return $false
    }

    if ($DirectProbe.State -eq 'FAILED') {
        return ($VpsProbe.State -ne 'FAILED')
    }

    if ($VpsProbe.State -eq 'FAILED') {
        return $false
    }

    $directMs = [int]$DirectProbe.LatencyMs
    $vpsMs = [int]$VpsProbe.LatencyMs

    if ($directMs -le 0 -or $vpsMs -le 0) {
        return $false
    }

    if ($directMs -lt $AutoConsiderVpsAboveMs -and $DirectProbe.State -eq 'HEALTHY') {
        return $false
    }

    $advantage = $directMs - $vpsMs
    $ratioOk = ($vpsMs -le [int][math]::Round($directMs * $AutoLatencySwitchRatio))
    $advantageOk = ($advantage -ge $AutoLatencyMinAdvantageMs)

    return ($ratioOk -and $advantageOk)
}

function Get-SecondsSince([string]$IsoValue) {
    if (-not $IsoValue) {
        return [double]::PositiveInfinity
    }

    try {
        return ((Get-Date) - [datetime]$IsoValue).TotalSeconds
    }
    catch {
        return [double]::PositiveInfinity
    }
}

function Get-ProvisionalRoutes($Config, $Runtime) {
    $routes = New-RouteObject
    $previous = Normalize-Routes $Runtime.Effective

    foreach ($module in $ModuleNames) {
        $mode = Get-DesiredMode $Config $module

        switch ($mode) {
            'VPS' {
                $routes.$module = 'VPS'
            }

            'DIRECT' {
                $routes.$module = 'DIRECT'
            }

            'AUTO' {
                if ($previous.$module -eq 'VPS') {
                    $routes.$module = 'VPS'
                }
                else {
                    $routes.$module = 'DIRECT'
                }
            }
        }
    }

    return $routes
}

function Resolve-AutoRoutes($Config, $ProvisionalRoutes) {
    $resolved = Normalize-Routes $ProvisionalRoutes
    $health = New-HealthObject
    $metrics = New-MetricsObject
    $decisions = @{}

    foreach ($module in $ModuleNames) {
        $mode = Get-DesiredMode $Config $module

        if ($mode -eq 'DIRECT') {
            $probe = Test-ModuleHealth -Module $module -Route DIRECT
            $health.$module = $probe.State
            $metrics.$module = Convert-ProbeToMetric $probe 'DIRECT'
            $resolved.$module = 'DIRECT'
            $decisions[$module] = 'CONFIG_DIRECT'
            continue
        }

        if ($mode -eq 'VPS') {
            if (-not (Ensure-SocksTunnel -Quiet)) {
                throw "Explicit VPS mode for $module cannot be satisfied."
            }

            $probe = Test-ModuleHealth -Module $module -Route VPS
            $health.$module = $probe.State
            $metrics.$module = Convert-ProbeToMetric $probe 'VPS'
            $resolved.$module = 'VPS'
            $decisions[$module] = 'CONFIG_VPS'
            continue
        }

        # AUTO: DIRECT first, then use VPS only for failure or a material,
        # stable latency advantage.
        $directProbe = Test-ModuleHealth -Module $module -Route DIRECT

        if ($directProbe.State -eq 'HEALTHY' -and $directProbe.LatencyMs -lt $AutoConsiderVpsAboveMs) {
            $resolved.$module = 'DIRECT'
            $health.$module = $directProbe.State
            $metrics.$module = Convert-ProbeToMetric $directProbe 'DIRECT'
            $decisions[$module] = 'AUTO_DIRECT_HEALTHY'
            continue
        }

        if (-not (Ensure-SocksTunnel -Quiet)) {
            $resolved.$module = 'DIRECT'
            $health.$module = $directProbe.State
            $metrics.$module = Convert-ProbeToMetric $directProbe 'DIRECT'
            $decisions[$module] = 'AUTO_VPS_UNAVAILABLE'
            continue
        }

        $vpsProbe = Test-ModuleHealth -Module $module -Route VPS

        if (
            $directProbe.State -eq 'FAILED' -and
            $vpsProbe.State -ne 'FAILED'
        ) {
            $resolved.$module = 'VPS'
            $health.$module = $vpsProbe.State
            $metrics.$module = Convert-ProbeToMetric $vpsProbe 'VPS'
            $decisions[$module] = 'AUTO_DIRECT_FAILED'
            continue
        }

        if (Test-PreferVpsForLatency $directProbe $vpsProbe) {
            $resolved.$module = 'VPS'
            $health.$module = $vpsProbe.State
            $metrics.$module = Convert-ProbeToMetric $vpsProbe 'VPS'
            $decisions[$module] = 'AUTO_VPS_FASTER'
        }
        else {
            $resolved.$module = 'DIRECT'
            $health.$module = $directProbe.State
            $metrics.$module = Convert-ProbeToMetric $directProbe 'DIRECT'
            $decisions[$module] = 'AUTO_DIRECT_PREFERRED'
        }
    }

    return [pscustomobject]@{
        Routes = $resolved
        Health = $health
        Metrics = $metrics
        Decisions = $decisions
    }
}

function Start-AppsForConfig($Config) {
    if ($NoAppLaunch) {
        return
    }

    if ((Get-DesiredMode $Config 'OpenAI') -ne 'DIRECT') {
        [void](Start-StartMenuApp '(?i)^ChatGPT$|ChatGPT' 'ChatGPT')
        [void](Start-StartMenuApp '(?i)^Codex$|Codex' 'Codex')
    }

    if ((Get-DesiredMode $Config 'Firefox') -ne 'DIRECT') {
        [void](Start-Firefox)
    }
}

function Apply-RoutingConfiguration {
    return Invoke-WithMutationLock {
        Write-Step 'Apply V6.3.1 routing'

        Stop-LegacyV62Watchdogs
        Stop-LegacyV61Watchdog
        Stop-LegacyV6Watchdog

        if (-not (Ensure-ProbeHelpers)) {
            return $false
        }

        $config = Get-Config
        $runtime = Get-Runtime
        $runtime.Override = 'NONE'
        Save-Runtime $runtime

        $provisional = Get-ProvisionalRoutes -Config $config -Runtime $runtime

        # Provisional profile installs dedicated DIRECT/VPS probe rules, making
        # subsequent AUTO direct probes independent from module destination rules.
        if (Test-AnyEffectiveVps $provisional) {
            if (-not (Ensure-SocksTunnel)) {
                return $false
            }
        }

        $provisionalPath = New-ProxifierProfile `
            -Routes $provisional `
            -DestinationPath $ProfilePath

        if (-not (Load-ProxifierProfile -Path $provisionalPath -Routes $provisional)) {
            return $false
        }

        try {
            $resolution = Resolve-AutoRoutes `
                -Config $config `
                -ProvisionalRoutes $provisional
        }
        catch {
            Write-Fail $_.Exception.Message
            return $false
        }

        if (-not (Apply-EffectiveRoutesOnly `
            -Routes $resolution.Routes `
            -Reason 'MANUAL_APPLY')) {
            return $false
        }

        $runtime = Get-Runtime
        $runtime.Health = $resolution.Health
        $runtime.Metrics = $resolution.Metrics

        foreach ($moduleName in $ModuleNames) {
            $previousRoute = [string]$provisional.$moduleName
            $resolvedRoute = [string]$resolution.Routes.$moduleName

            if ($previousRoute -ne $resolvedRoute) {
                Write-RouteDecision `
                    -Module $moduleName `
                    -From $previousRoute `
                    -To $resolvedRoute `
                    -Reason ([string]$resolution.Decisions[$moduleName]) `
                    -Detail "initial-resolution"
            }

            if ($resolution.Decisions.ContainsKey($moduleName)) {
                $runtime.AutoState.$moduleName.LastDecision = [string]$resolution.Decisions[$moduleName]
            }
        }

        Save-Runtime $runtime
        Update-OperationalStats -Routes $runtime.Effective -Health $runtime.Health
        Record-TelemetrySnapshot -Runtime $runtime -Force

        Stop-Watchdog

        if (Test-NeedsWatchdog -Config $config -Routes $resolution.Routes) {
            [void](Start-Watchdog)
        }

        Start-AppsForConfig $config

        Write-Ok 'V6.3.1 configuration applied.'
        Show-RoutingTable
        return $true
    }
}

function Enable-DirectOverride {
    return Invoke-WithMutationLock {
        Write-Step 'DIRECT override'

        Stop-LegacyV62Watchdogs
        Stop-LegacyV61Watchdog
        Stop-LegacyV6Watchdog
        Stop-Watchdog
        $routes = New-RouteObject
        $path = New-ProxifierProfile -Routes $routes -DestinationPath $DirectProfilePath

        if (-not (Load-ProxifierProfile -Path $path -Routes $routes)) {
            return $false
        }

        $runtime = Get-Runtime
        $runtime.Override = 'DIRECT'
        $runtime.Effective = $routes
        $runtime.Health = New-HealthObject
        $runtime.ProfileHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        $runtime.LastReason = 'DIRECT_OVERRIDE'
        Save-Runtime $runtime
        Update-OperationalStats -Routes $runtime.Effective -Health $runtime.Health
        Record-TelemetrySnapshot -Runtime $runtime -Force

        Write-Ok 'Все module routes временно DIRECT. Config modes сохранены.'
        return $true
    }
}

# ============================================================================
# APP LAUNCH
# ============================================================================

function Start-StartMenuApp(
    [string]$NameRegex,
    [string]$FriendlyName
) {
    try {
        $app = Get-StartApps |
            Where-Object { $_.Name -match $NameRegex } |
            Select-Object -First 1

        if ($app -and $app.AppID) {
            Start-Process explorer.exe "shell:AppsFolder\$($app.AppID)"
            Write-Ok "$FriendlyName запущен."
            return $true
        }
    }
    catch {
        # Non-fatal.
    }

    Write-Info "$FriendlyName сейчас не запущен / автоматически не найден."
    return $false
}

function Start-Firefox {
    $candidates = @(
        "$env:ProgramFiles\Mozilla Firefox\firefox.exe",
        "${env:ProgramFiles(x86)}\Mozilla Firefox\firefox.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            Start-Process -FilePath $candidate
            Write-Ok 'Firefox запущен.'
            return $true
        }
    }

    try {
        $command = Get-Command firefox.exe -ErrorAction SilentlyContinue

        if ($command -and $command.Source) {
            Start-Process -FilePath $command.Source
            Write-Ok 'Firefox запущен.'
            return $true
        }
    }
    catch {
        # Non-fatal.
    }

    Write-Info 'Firefox сейчас не запущен / автоматически не найден.'
    return $false
}

# ============================================================================
# LEGACY V6 COEXISTENCE
# ============================================================================


function Stop-LegacyWatchdogByPidFile(
    [string]$PidFile,
    [string]$ExpectedScriptPattern,
    [string]$Label
) {
    if (-not (Test-Path -LiteralPath $PidFile)) {
        return
    }

    try {
        $legacyPid = [int](Get-Content -LiteralPath $PidFile -Raw).Trim()
        $proc = Get-CimInstance Win32_Process `
            -Filter "ProcessId=$legacyPid" `
            -ErrorAction SilentlyContinue

        if ($proc -and ([string]$proc.CommandLine) -match $ExpectedScriptPattern) {
            Stop-Process -Id $legacyPid -Force -ErrorAction SilentlyContinue
            Write-ControllerLog "$Label watchdog stopped pid=$legacyPid"
        }

        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
    catch {
        Write-ControllerLog "$Label watchdog cleanup failed: $($_.Exception.Message)"
    }
}


function Stop-LegacyV62Watchdogs {
    try {
        Get-CimInstance Win32_Process `
            -Filter "Name='powershell.exe'" `
            -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ProcessId -ne $PID -and
                ([string]$_.CommandLine) -match '(?i)VPS-Control-v6\.2(?:\.1)?\.ps1' -and
                ([string]$_.CommandLine) -match '(?i)-Action\s+Watchdog'
            } |
            ForEach-Object {
                try {
                    Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
                    Write-ControllerLog "LEGACY_V62_WATCHDOG_STOP pid=$($_.ProcessId)"
                }
                catch {
                    Write-ControllerLog "LEGACY_V62_WATCHDOG_STOP_FAILED pid=$($_.ProcessId)"
                }
            }

        Remove-Item -LiteralPath $LegacyV62WatchdogPidFile -Force -ErrorAction SilentlyContinue
    }
    catch {
        Write-ControllerLog "LEGACY_V62_WATCHDOG_SCAN_FAILED $($_.Exception.Message)"
    }
}

function Disable-LegacyV62AutostartIfPresent {
    try {
        $task = Get-ScheduledTask `
            -TaskName $LegacyV62AutostartTaskName `
            -ErrorAction SilentlyContinue

        if ($task) {
            Disable-ScheduledTask -TaskName $LegacyV62AutostartTaskName -ErrorAction SilentlyContinue | Out-Null
            Write-ControllerLog 'Legacy V6.2/6.2.1 autostart disabled'
        }
    }
    catch {
        Write-ControllerLog "Legacy V6.2 autostart disable failed: $($_.Exception.Message)"
    }
}

function Stop-LegacyV61Watchdog {
    Stop-LegacyWatchdogByPidFile `
        -PidFile $LegacyV61WatchdogPidFile `
        -ExpectedScriptPattern '(?i)VPS-Control-v6\.1\.ps1.*-Action\s+Watchdog' `
        -Label 'V6.1'
}

function Stop-LegacyV6Watchdog {
    if (-not (Test-Path -LiteralPath $LegacyV6WatchdogPidFile)) {
        return
    }

    try {
        $legacyPid = [int](Get-Content -LiteralPath $LegacyV6WatchdogPidFile -Raw).Trim()
        $process = Get-CimInstance Win32_Process `
            -Filter "ProcessId=$legacyPid" `
            -ErrorAction SilentlyContinue

        if (-not $process) {
            Remove-Item -LiteralPath $LegacyV6WatchdogPidFile -Force -ErrorAction SilentlyContinue
            return
        }

        $cmdline = [string]$process.CommandLine
        $name = [string]$process.Name

        if (
            $name -match '(?i)powershell' -and
            $cmdline -match '(?i)VPS-Control-v6\.ps1' -and
            $cmdline -match '(?i)Watchdog'
        ) {
            Stop-Process -Id $legacyPid -Force -ErrorAction Stop
            Remove-Item -LiteralPath $LegacyV6WatchdogPidFile -Force -ErrorAction SilentlyContinue
            Write-Warn "Legacy V6 watchdog PID=$legacyPid остановлен, чтобы не конфликтовать с V6.3."
            Write-ControllerLog "LEGACY_V6_WATCHDOG_STOP pid=$legacyPid"
        }
        else {
            Write-Warn "Legacy watchdog PID file указывает на непроверенный process PID=$legacyPid; process не остановлен."
        }
    }
    catch {
        Write-Warn "Legacy V6 watchdog check failed: $($_.Exception.Message)"
    }
}


function Disable-LegacyV61AutostartIfPresent {
    try {
        $task = Get-ScheduledTask `
            -TaskName $LegacyV61AutostartTaskName `
            -ErrorAction SilentlyContinue

        if ($task) {
            Disable-ScheduledTask -TaskName $LegacyV61AutostartTaskName -ErrorAction SilentlyContinue | Out-Null
            Write-ControllerLog 'Legacy V6.1 autostart disabled'
        }
    }
    catch {
        Write-ControllerLog "Legacy V6.1 autostart disable failed: $($_.Exception.Message)"
    }
}

function Disable-LegacyV6AutostartIfPresent {
    try {
        $legacyTask = Get-ScheduledTask `
            -TaskName $LegacyAutostartTaskName `
            -ErrorAction SilentlyContinue

        if ($legacyTask -and $legacyTask.State -ne 'Disabled') {
            Disable-ScheduledTask -TaskName $LegacyAutostartTaskName | Out-Null
            Write-Warn "Legacy autostart '$LegacyAutostartTaskName' disabled to prevent profile races."
            Write-ControllerLog "LEGACY_V6_AUTOSTART_DISABLED"
        }
    }
    catch {
        Write-Warn "Could not inspect/disable legacy V6 autostart: $($_.Exception.Message)"
    }
}

# ============================================================================
# WATCHDOG
# ============================================================================

function Stop-OrphanV63Watchdogs {
    try {
        Get-CimInstance Win32_Process `
            -Filter "Name='powershell.exe'" `
            -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ProcessId -ne $PID -and
                ([string]$_.CommandLine) -match '(?i)VPS-Control-v6\.3(?:\.1)?\.ps1' -and
                ([string]$_.CommandLine) -match '(?i)-Action\s+Watchdog'
            } |
            ForEach-Object {
                try {
                    Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
                    Write-ControllerLog "ORPHAN_V63_WATCHDOG_STOP pid=$($_.ProcessId)"
                }
                catch {
                    Write-ControllerLog "ORPHAN_V63_WATCHDOG_STOP_FAILED pid=$($_.ProcessId) error=$($_.Exception.Message)"
                }
            }
    }
    catch {
        Write-ControllerLog "ORPHAN_V63_WATCHDOG_SCAN_FAILED $($_.Exception.Message)"
    }
}

function Get-WatchdogPid {
    if (-not (Test-Path -LiteralPath $WatchdogPidFile)) {
        return $null
    }

    try {
        $value = [int](Get-Content -LiteralPath $WatchdogPidFile -Raw).Trim()
        $process = Get-CimInstance Win32_Process `
            -Filter "ProcessId=$value" `
            -ErrorAction SilentlyContinue

        if (-not $process) {
            Remove-Item -LiteralPath $WatchdogPidFile -Force -ErrorAction SilentlyContinue
            return $null
        }

        $name = [string]$process.Name
        $cmdline = [string]$process.CommandLine

        if (
            $name -match '(?i)powershell' -and
            $cmdline -match '(?i)VPS-Control-v6\.3(?:\.1)?\.ps1' -and
            $cmdline -match '(?i)-Action\s+Watchdog'
        ) {
            return $value
        }

        # PID was reused by another process. Never kill it.
        Remove-Item -LiteralPath $WatchdogPidFile -Force -ErrorAction SilentlyContinue
        Write-ControllerLog "STALE_WATCHDOG_PID_REUSED pid=$value"
        return $null
    }
    catch {
        return $null
    }
}

function Stop-Watchdog {
    $watchPid = Get-WatchdogPid

    if ($watchPid) {
        try {
            Stop-Process -Id $watchPid -Force -ErrorAction Stop
            Write-ControllerLog "WATCHDOG_STOP pid=$watchPid"
        }
        catch {
            Write-Warn "Watchdog PID=$watchPid could not be stopped: $($_.Exception.Message)"
        }
    }

    Remove-Item -LiteralPath $WatchdogPidFile -Force -ErrorAction SilentlyContinue
}

function Start-Watchdog {
    Stop-OrphanV63Watchdogs
    Stop-Watchdog

    $arguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-WindowStyle', 'Hidden',
        '-File', $PSCommandPath,
        '-Action', 'Watchdog',
        '-WatchIntervalSeconds', [string]$WatchIntervalSeconds,
        '-NoAppLaunch'
    )

    try {
        $process = Start-Process `
            -FilePath 'powershell.exe' `
            -ArgumentList (Convert-ToProcessArgumentString -Items $arguments) `
            -WindowStyle Hidden `
            -PassThru

        Write-TextAtomic `
            -Path $WatchdogPidFile `
            -Text ([string]$process.Id)

        Write-ControllerLog "WATCHDOG_START_REQUESTED pid=$($process.Id)"

        Start-Sleep -Milliseconds 900
        $verifiedPid = Get-WatchdogPid

        if ($verifiedPid -eq $process.Id) {
            Write-Ok "Watchdog PID=$($process.Id), interval=${WatchIntervalSeconds}s."
            Write-ControllerLog "WATCHDOG_START_VERIFIED pid=$($process.Id)"
            return $true
        }

        Write-Warn "Watchdog process did not survive startup verification (requested PID=$($process.Id))."
        Write-ControllerLog "WATCHDOG_START_VERIFY_FAILED requested_pid=$($process.Id)"
        return $false
    }
    catch {
        Write-Warn "Watchdog не запущен: $($_.Exception.Message)"
        return $false
    }
}

function Invoke-Watchdog {
    Write-WatchdogLog "START pid=$PID interval=${WatchIntervalSeconds}s"

    try {
        Write-WatchdogHeartbeat -Runtime (Get-Runtime)
    }
    catch {
        # Non-fatal.
    }

    while ($true) {
        try {
            $config = Get-Config
            $runtime = Get-Runtime

            if ($runtime.Override -eq 'DIRECT') {
                Write-WatchdogLog 'EXIT direct override active'
                break
            }

            if (-not (Test-NeedsWatchdog -Config $config -Routes $runtime.Effective)) {
                Write-WatchdogLog 'EXIT no AUTO/VPS routing needs monitoring'
                break
            }

            $routes = Normalize-Routes $runtime.Effective
            $health = Normalize-Health $runtime.Health
            $metrics = Normalize-Metrics $runtime.Metrics
            $autoState = Normalize-AutoState $runtime.AutoState
            $routesChanged = $false
            $reason = ''

            if (Test-AnyEffectiveVps $routes) {
                if (-not (Test-SocksIdentity)) {
                    Write-WatchdogLog 'SOCKS identity failed; attempting repair'

                    [void](Stop-TunnelProcess -Quiet)
                    Start-Sleep -Seconds 1

                    if (-not (Ensure-SocksTunnel -Quiet)) {
                        Write-WatchdogLog 'SOCKS repair failed'
                    }
                    else {
                        Write-WatchdogLog 'SOCKS repair succeeded'
                    }
                }
            }

            foreach ($module in $ModuleNames) {
                $mode = Get-DesiredMode $config $module
                $route = [string]$routes.$module
                $moduleAuto = $autoState.$module

                if ($mode -eq 'DIRECT') {
                    if ($route -ne 'DIRECT') {
                        $old = $route
                        $routes.$module = 'DIRECT'
                        $routesChanged = $true
                        $reason = "WATCHDOG_CONFIG_DIRECT_$module"
                        Write-RouteDecision $module $old 'DIRECT' 'CONFIG_DIRECT'
                    }

                    $probe = Test-ModuleHealth -Module $module -Route DIRECT
                    $health.$module = $probe.State
                    $metrics.$module = Convert-ProbeToMetric $probe 'DIRECT'
                    continue
                }

                if ($mode -eq 'VPS') {
                    if ($route -ne 'VPS') {
                        $old = $route
                        $routes.$module = 'VPS'
                        $routesChanged = $true
                        $reason = "WATCHDOG_CONFIG_VPS_$module"
                        Write-RouteDecision $module $old 'VPS' 'CONFIG_VPS'
                    }

                    if (Test-SocksIdentity) {
                        $probe = Test-ModuleHealth -Module $module -Route VPS
                        $health.$module = $probe.State
                        $metrics.$module = Convert-ProbeToMetric $probe 'VPS'
                    }
                    else {
                        $health.$module = 'FAILED'
                        $metrics.$module.State = 'FAILED'
                        $metrics.$module.FailureClass = 'SOCKS_IDENTITY'
                    }

                    continue
                }

                # AUTO ------------------------------------------------------
                if ($route -eq 'DIRECT') {
                    $directProbe = Test-ModuleHealth -Module $module -Route DIRECT
                    $health.$module = $directProbe.State
                    $metrics.$module = Convert-ProbeToMetric $directProbe 'DIRECT'

                    if ($directProbe.State -eq 'FAILED') {
                        $moduleAuto.DirectFails = [int]$moduleAuto.DirectFails + 1
                    }
                    else {
                        $moduleAuto.DirectFails = 0
                    }

                    $mustCompareLatency = (
                        $directProbe.State -eq 'DEGRADED' -or
                        (
                            $directProbe.LatencyMs -ge $AutoConsiderVpsAboveMs -and
                            (Get-SecondsSince $moduleAuto.LastLatencyCompare) -ge $AutoLatencyCompareSeconds
                        )
                    )

                    $mustFailover = ($moduleAuto.DirectFails -ge $AutoFailThreshold)

                    if ($mustFailover -or $mustCompareLatency) {
                        $moduleAuto.LastLatencyCompare = (Get-Date).ToString('o')

                        if (Ensure-SocksTunnel -Quiet) {
                            $vpsProbe = Test-ModuleHealth -Module $module -Route VPS
                            $switchReason = ''

                            if ($mustFailover -and $vpsProbe.State -ne 'FAILED') {
                                $switchReason = 'AUTO_DIRECT_FAILED'
                            }
                            elseif (Test-PreferVpsForLatency $directProbe $vpsProbe) {
                                $switchReason = 'AUTO_VPS_FASTER'
                            }

                            if ($switchReason) {
                                $routes.$module = 'VPS'
                                $routesChanged = $true
                                $reason = "${switchReason}_$module"
                                $health.$module = $vpsProbe.State
                                $metrics.$module = Convert-ProbeToMetric $vpsProbe 'VPS'
                                $moduleAuto.DirectFails = 0
                                $moduleAuto.DirectRecoveries = 0
                                $moduleAuto.LastFailbackProbe = (Get-Date).ToString('o')
                                $moduleAuto.LastDecision = $switchReason

                                Write-RouteDecision `
                                    -Module $module `
                                    -From 'DIRECT' `
                                    -To 'VPS' `
                                    -Reason $switchReason `
                                    -Detail "direct=$($directProbe.State)/$($directProbe.LatencyMs)ms vps=$($vpsProbe.State)/$($vpsProbe.LatencyMs)ms"

                                Write-WatchdogLog "AUTO $module DIRECT->VPS reason=$switchReason"
                            }
                        }
                    }
                }
                else {
                    $vpsProbe = $null

                    if (Test-SocksIdentity) {
                        $vpsProbe = Test-ModuleHealth -Module $module -Route VPS
                        $health.$module = $vpsProbe.State
                        $metrics.$module = Convert-ProbeToMetric $vpsProbe 'VPS'
                    }
                    else {
                        $health.$module = 'FAILED'
                        $metrics.$module.State = 'FAILED'
                        $metrics.$module.FailureClass = 'SOCKS_IDENTITY'
                    }

                    $elapsed = Get-SecondsSince $moduleAuto.LastFailbackProbe

                    if (
                        $elapsed -ge $AutoFailbackProbeSeconds -or
                        ($vpsProbe -and $vpsProbe.State -eq 'FAILED')
                    ) {
                        $moduleAuto.LastFailbackProbe = (Get-Date).ToString('o')
                        $directProbe = Test-ModuleHealth -Module $module -Route DIRECT

                        $directAcceptable = ($directProbe.State -eq 'HEALTHY')

                        if (
                            -not $directAcceptable -and
                            $vpsProbe -and
                            $vpsProbe.State -eq 'FAILED' -and
                            $directProbe.State -ne 'FAILED'
                        ) {
                            $directAcceptable = $true
                        }

                        if ($directAcceptable) {
                            $moduleAuto.DirectRecoveries = [int]$moduleAuto.DirectRecoveries + 1
                        }
                        else {
                            $moduleAuto.DirectRecoveries = 0
                        }

                        if ($moduleAuto.DirectRecoveries -ge $AutoRecoverThreshold) {
                            $routes.$module = 'DIRECT'
                            $routesChanged = $true
                            $reason = "AUTO_FAILBACK_$module"
                            $health.$module = $directProbe.State
                            $metrics.$module = Convert-ProbeToMetric $directProbe 'DIRECT'
                            $moduleAuto.DirectRecoveries = 0
                            $moduleAuto.LastDecision = 'AUTO_DIRECT_RECOVERED'

                            Write-RouteDecision `
                                -Module $module `
                                -From 'VPS' `
                                -To 'DIRECT' `
                                -Reason 'AUTO_DIRECT_RECOVERED' `
                                -Detail "direct=$($directProbe.State)/$($directProbe.LatencyMs)ms"

                            Write-WatchdogLog "AUTO $module VPS->DIRECT"
                        }
                    }
                }

                $autoState.$module = $moduleAuto
            }

            $proxifier = Find-ProxifierStandard
            $proxifierRunning = $false

            if ($proxifier) {
                $proxifierRunning = Test-ProxifierStandardRunning $proxifier
            }

            $profileDrift = $false

            if (
                $runtime.ProfileHash -and
                (Test-Path -LiteralPath $ProfilePath)
            ) {
                try {
                    $diskHash = (Get-FileHash -LiteralPath $ProfilePath -Algorithm SHA256).Hash

                    if ($diskHash -ne $runtime.ProfileHash) {
                        $profileDrift = $true
                        Write-WatchdogLog "PROFILE_DRIFT expected=$($runtime.ProfileHash) actual=$diskHash"
                    }
                }
                catch {
                    $profileDrift = $true
                }
            }

            if ($routesChanged -or -not $proxifierRunning -or $profileDrift) {
                Invoke-WithMutationLock {
                    $applyReason = if ($routesChanged) {
                        $reason
                    }
                    elseif ($profileDrift) {
                        'WATCHDOG_PROFILE_DRIFT_RECOVERY'
                    }
                    else {
                        'WATCHDOG_PROXIFIER_RECOVERY'
                    }

                    if (Apply-EffectiveRoutesOnly -Routes $routes -Reason $applyReason) {
                        $updatedRuntime = Get-Runtime
                        $updatedRuntime.Health = $health
                        $updatedRuntime.Metrics = $metrics
                        $updatedRuntime.AutoState = $autoState
                        Save-Runtime $updatedRuntime
                    }
                    else {
                        Write-WatchdogLog 'Profile apply/recovery failed'
                    }
                } | Out-Null
            }
            else {
                Invoke-WithMutationLock {
                    $latestRuntime = Get-Runtime

                    if ($latestRuntime.Override -ne 'DIRECT') {
                        $latestRuntime.Health = $health
                        $latestRuntime.Metrics = $metrics
                        $latestRuntime.AutoState = $autoState
                        Save-Runtime $latestRuntime
                    }
                } | Out-Null
            }
        }
        catch {
            Write-WatchdogLog "ERROR $($_.Exception.Message)"
        }

        try {
            $observationRuntime = Get-Runtime
            Update-OperationalStats `
                -Routes $observationRuntime.Effective `
                -Health $observationRuntime.Health
            Record-TelemetrySnapshot -Runtime $observationRuntime
            Write-WatchdogHeartbeat -Runtime $observationRuntime
        }
        catch {
            Write-WatchdogLog "OBSERVABILITY_ERROR $($_.Exception.Message)"
        }

        Start-Sleep -Seconds $WatchIntervalSeconds
    }

    Remove-Item -LiteralPath $WatchdogPidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $WatchdogHeartbeatFile -Force -ErrorAction SilentlyContinue
    Write-WatchdogLog 'STOP'
}

function Show-RoutingTable {
    $config = Get-Config
    $runtime = Get-Runtime

    Write-Host ''
    Write-Host 'Routing:' -ForegroundColor White
    Write-Host ('  {0,-14} {1,-9} {2,-10} {3,-10} {4,8} {5,-16}' -f 'Module', 'Config', 'Effective', 'State', 'Latency', 'Failure')
    Write-Host ('  {0,-14} {1,-9} {2,-10} {3,-10} {4,8} {5,-16}' -f '------', '------', '---------', '-----', '-------', '-------')

    foreach ($module in $ModuleNames) {
        $configured = Get-DesiredMode $config $module
        $effective = [string]$runtime.Effective.$module
        $metric = Normalize-ModuleMetric $runtime.Metrics.$module
        $latency = if ($metric.LatencyMs -gt 0) { "$($metric.LatencyMs)ms" } else { '-' }

        Write-Host (
            '  {0,-14} {1,-9} {2,-10} {3,-10} {4,8} {5,-16}' -f
            $module,
            $configured,
            $effective,
            $metric.State,
            $latency,
            $metric.FailureClass
        )
    }

    Write-Host ''
    Write-Host "Global override: $($runtime.Override)"
    Write-Host "Last reason:     $($runtime.LastReason)"
    Write-Host "Updated:         $($runtime.UpdatedAt)"
}

function Show-Status {
    $runtime = Get-Runtime
    $watchPid = Get-WatchdogPid
    $proxifier = Find-ProxifierStandard
    $listener = Get-SocksListenerProcess

    Write-Host ''
    Write-Host 'VPS CONTROL V6.3.1 STATUS' -ForegroundColor Cyan

    if ($listener) {
        Write-Host "SOCKS:       LISTEN ${SocksHost}:$SocksPort PID=$($listener.ProcessId)" -ForegroundColor Green
    }
    else {
        Write-Host "SOCKS:       OFF ${SocksHost}:$SocksPort" -ForegroundColor Yellow
    }

    if ($proxifier) {
        $running = Test-ProxifierStandardRunning $proxifier

        if ($running) {
            Write-Host "Proxifier:   RUNNING $proxifier" -ForegroundColor Green
        }
        else {
            Write-Host "Proxifier:   FOUND but not running $proxifier" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host 'Proxifier:   Standard NOT FOUND' -ForegroundColor Red
    }

    if ($watchPid) {
        $hb = Get-WatchdogHeartbeatStatus

        if ($hb.Present -and -not $hb.Stale) {
            Write-Host "Watchdog:    RUNNING PID=$watchPid heartbeat=$($hb.AgeSeconds)s" -ForegroundColor Green
        }
        elseif ($hb.Present -and $hb.Stale) {
            Write-Host "Watchdog:    RUNNING PID=$watchPid HEARTBEAT STALE=$($hb.AgeSeconds)s" -ForegroundColor Yellow
        }
        else {
            Write-Host "Watchdog:    RUNNING PID=$watchPid heartbeat=pending" -ForegroundColor Green
        }
    }
    else {
        $configForWatchdog = Get-Config

        if (
            $runtime.Override -ne 'DIRECT' -and
            (Test-NeedsWatchdog -Config $configForWatchdog -Routes $runtime.Effective)
        ) {
            Write-Host 'Watchdog:    OFF (EXPECTED RUNNING)' -ForegroundColor Red
        }
        else {
            Write-Host 'Watchdog:    OFF'
        }
    }

    if (Test-Path -LiteralPath $LastGoodProfilePath) {
        Write-Host 'LKG profile: PRESENT' -ForegroundColor Green
    }
    else {
        Write-Host 'LKG profile: not created yet'
    }

    $daily = Get-DailySelfTestTask
    if ($daily) {
        Write-Host "Daily test:  INSTALLED state=$($daily.State)" -ForegroundColor Green
    }
    else {
        Write-Host 'Daily test:  OFF'
    }

    $lastSelfTest = Get-LastSelfTestResult
    if ($lastSelfTest) {
        $selfTestText = "Last test:   $($lastSelfTest.Overall) $($lastSelfTest.Timestamp)"

        if ($lastSelfTest.Overall -eq 'FAIL') {
            Write-Host $selfTestText -ForegroundColor Red
        }
        elseif ($lastSelfTest.Overall -eq 'WARN') {
            Write-Host $selfTestText -ForegroundColor Yellow
        }
        else {
            Write-Host $selfTestText -ForegroundColor Green
        }
    }
    else {
        Write-Host 'Last test:   not run yet'
    }

    Show-RoutingTable
}

function Test-DnsResolution([string]$HostName) {
    try {
        $addresses = [System.Net.Dns]::GetHostAddresses($HostName)

        if ($addresses -and $addresses.Count -gt 0) {
            return [pscustomobject]@{
                Success = $true
                Detail = (($addresses | ForEach-Object { $_.IPAddressToString }) -join ',')
            }
        }
    }
    catch {
        return [pscustomobject]@{
            Success = $false
            Detail = $_.Exception.Message
        }
    }

    return [pscustomobject]@{
        Success = $false
        Detail = 'NO_ADDRESSES'
    }
}

function Invoke-RouteBenchmark {
    Write-Step 'DIRECT vs VPS route benchmark'

    if (-not (Ensure-SocksTunnel -Quiet)) {
        Write-Warn 'VPS tunnel unavailable; DIRECT-only benchmark.'
    }

    Write-Host ('  {0,-14} {1,-10} {2,10} {3,-10} {4,10} {5}' -f 'Module', 'Direct', 'D.ms', 'VPS', 'V.ms', 'Recommendation')
    Write-Host ('  {0,-14} {1,-10} {2,10} {3,-10} {4,10} {5}' -f '------', '------', '----', '---', '----', '--------------')

    foreach ($module in $ModuleNames) {
        $direct = Test-ModuleHealth -Module $module -Route DIRECT
        $vps = $null

        if (Test-SocksIdentity) {
            $vps = Test-ModuleHealth -Module $module -Route VPS
        }

        $vpsState = if ($vps) { $vps.State } else { 'N/A' }
        $vpsLatency = if ($vps) { $vps.LatencyMs } else { 0 }
        $recommendation = 'DIRECT'

        if ($vps -and (Test-PreferVpsForLatency $direct $vps)) {
            $recommendation = 'VPS'
        }
        elseif ($direct.State -eq 'FAILED' -and $vps -and $vps.State -ne 'FAILED') {
            $recommendation = 'VPS'
        }
        elseif ($direct.State -eq 'FAILED' -and (-not $vps -or $vps.State -eq 'FAILED')) {
            $recommendation = 'NONE'
        }

        Write-Host (
            '  {0,-14} {1,-10} {2,10} {3,-10} {4,10} {5}' -f
            $module,
            $direct.State,
            $direct.LatencyMs,
            $vpsState,
            $vpsLatency,
            $recommendation
        )
    }
}

function Invoke-Diagnostics {
    Write-Step 'Full diagnostics'

    Show-Status

    $directIp = Get-DirectExternalIp
    $socksIp = ''

    if (Test-TcpPort $SocksHost $SocksPort) {
        $socksIp = Get-SocksExternalIp
    }

    Write-Host ''
    Write-Host 'Network exits:'
    Write-Host "  Direct probe: $directIp"
    Write-Host "  SOCKS probe:  $socksIp"
    Write-Host "  Expected VPS: $ExpectedVpsIp"

    if ($socksIp -eq $ExpectedVpsIp) {
        Write-Ok 'SOCKS expected VPS identity PASS.'
    }
    elseif ($socksIp) {
        Write-Fail 'SOCKS exit does not match expected VPS.'
    }

    if ($directIp -and $socksIp -and $directIp -ne $socksIp) {
        Write-Ok 'Direct and VPS exits are distinct.'
    }
    elseif ($directIp -and $socksIp -and $directIp -eq $socksIp) {
        Write-Warn 'Direct and VPS exits are equal; full-system VPN may be active.'
    }

    Write-Host ''
    Write-Host 'DNS diagnostics:'

    foreach ($hostName in @('chatgpt.com','github.com','registry.npmjs.org','pypi.org')) {
        $dns = Test-DnsResolution $hostName

        if ($dns.Success) {
            Write-Ok "$hostName -> $($dns.Detail)"
        }
        else {
            Write-Fail "$hostName -> $($dns.Detail)"
        }
    }

    $runtime = Get-Runtime

    Write-Host ''
    Write-Host 'Fresh module health:'

    foreach ($module in $ModuleNames) {
        $route = [string]$runtime.Effective.$module
        $probe = Test-ModuleHealth -Module $module -Route $route

        Write-Host (
            '  {0,-14} route={1,-6} state={2,-9} latency={3,5}ms failure={4,-12} {5}' -f
            $module,
            $route,
            $probe.State,
            $probe.LatencyMs,
            $probe.FailureClass,
            $probe.Detail
        )
    }

    if (Get-Command git.exe -ErrorAction SilentlyContinue) {
        $gitVersion = & git.exe --version
        Write-Ok ([string]$gitVersion)
    }
    else {
        Write-Warn 'git.exe not found in PATH.'
    }

    if (Get-Command gh.exe -ErrorAction SilentlyContinue) {
        Write-Ok 'gh.exe found.'
    }

    Write-Host ''
    $hb = Get-WatchdogHeartbeatStatus
    if ($hb.Present) {
        if ($hb.Stale) {
            Write-Warn "Watchdog heartbeat stale: age=$($hb.AgeSeconds)s"
        }
        else {
            Write-Ok "Watchdog heartbeat fresh: age=$($hb.AgeSeconds)s"
        }
    }

    Show-ObservationSummary -Hours $ObservationSummaryHours

    if (Test-Path -LiteralPath $DecisionLogFile) {
        Write-Host ''
        Write-Host 'Route decisions tail:'
        Get-Content -LiteralPath $DecisionLogFile -Tail 10 -ErrorAction SilentlyContinue |
            ForEach-Object { Write-Host "  $_" }
    }

    if (Test-Path -LiteralPath $WatchdogLogFile) {
        Write-Host ''
        Write-Host 'Watchdog tail:'

        Get-Content `
            -LiteralPath $WatchdogLogFile `
            -Tail 10 `
            -ErrorAction SilentlyContinue |
            ForEach-Object { Write-Host "  $_" }
    }
}

function Get-GitAuthEnvironment {
    return @{
        GIT_TERMINAL_PROMPT = '0'
        GCM_INTERACTIVE = 'Never'
        GIT_HTTP_LOW_SPEED_LIMIT = '1'
        GIT_HTTP_LOW_SPEED_TIME = '20'
    }
}

function Invoke-Git {
    param(
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [string]$WorkingDirectory = '',
        [switch]$Echo
    )

    $git = Get-Command git.exe -ErrorAction SilentlyContinue

    if (-not $git) {
        return [pscustomobject]@{
            ExitCode = 9002
            StdOut = @()
            StdErr = @('git.exe not found')
            Output = @('git.exe not found')
        }
    }

    return Invoke-NativeCaptured `
        -FilePath $git.Source `
        -Arguments $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -EnvironmentOverrides (Get-GitAuthEnvironment) `
        -Echo:$Echo
}

function Get-FirstGitSha($Result) {
    foreach ($item in @($Result.Output)) {
        $line = [string]$item

        if ($line -match '^([0-9a-fA-F]{40})(?:\s+|$)') {
            return $Matches[1].ToLowerInvariant()
        }
    }

    return ''
}

function Get-FirstGitStdOutLine($Result) {
    foreach ($item in @($Result.StdOut)) {
        $line = ([string]$item).Trim()

        if ($line) {
            return $line
        }
    }

    return ''
}

function Invoke-GitHubReadSelfTest {
    Write-Step 'GitHub READ self-test'

    $repoUrl = 'https://github.com/kmephis-ai/AI-Development-Framework.git'
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $workDir = Join-Path $env:TEMP "VPS-Control-GitHub-read-$stamp"
    $cloneDir = Join-Path $workDir 'repo'
    New-Item -ItemType Directory -Path $workDir -Force | Out-Null

    try {
        $ls = Invoke-Git `
            -Arguments @('ls-remote', '--heads', $repoUrl, 'main') `
            -Echo

        $remoteSha = Get-FirstGitSha $ls

        if ($ls.ExitCode -ne 0 -or -not $remoteSha) {
            Write-Fail 'git ls-remote FAIL.'
            return $false
        }

        Write-Ok "ls-remote main=$remoteSha"

        $clone = Invoke-Git `
            -Arguments @(
                'clone',
                '--single-branch',
                '--branch', 'main',
                '--no-tags',
                $repoUrl,
                $cloneDir
            ) `
            -Echo

        if (
            $clone.ExitCode -ne 0 -or
            -not (Test-Path -LiteralPath (Join-Path $cloneDir '.git'))
        ) {
            Write-Fail 'git clone FAIL.'
            return $false
        }

        Write-Ok 'git clone PASS.'

        $fetch = Invoke-Git `
            -Arguments @('fetch', '--prune', '--no-tags', 'origin', 'main') `
            -WorkingDirectory $cloneDir `
            -Echo

        if ($fetch.ExitCode -ne 0) {
            Write-Fail 'git fetch FAIL.'
            return $false
        }

        Write-Ok 'git fetch PASS.'

        $fsck = Invoke-Git `
            -Arguments @('fsck', '--full', '--no-dangling') `
            -WorkingDirectory $cloneDir `
            -Echo

        if ($fsck.ExitCode -ne 0) {
            Write-Fail 'git fsck FAIL.'
            return $false
        }

        Write-Ok 'git fsck PASS.'
        Write-Ok 'GitHub READ self-test PASS.'
        return $true
    }
    finally {
        Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-GitHubWriteSelfTest {
    Write-Step 'GitHub WRITE self-test'

    Write-Warn 'Этот тест создаст и сразу удалит одноразовую remote branch.'
    Write-Host 'main не изменяется; commit пустой; PR не создаётся.'

    $confirm = (Read-Host 'Введите YES для запуска write-test').Trim()

    if ($confirm -cne 'YES') {
        Write-Warn 'Write-test отменён.'
        return $false
    }

    $repoUrl = 'https://github.com/kmephis-ai/AI-Development-Framework.git'
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $suffix = ([guid]::NewGuid().ToString('N')).Substring(0, 8)
    $branch = "vps-control-write-test-$stamp-$suffix"

    $workDir = Join-Path $env:TEMP "VPS-Control-GitHub-write-$stamp"
    $cloneDir = Join-Path $workDir 'repo'
    New-Item -ItemType Directory -Path $workDir -Force | Out-Null

    $remoteMayExist = $false

    try {
        $ls = Invoke-Git `
            -Arguments @('ls-remote', '--heads', $repoUrl, 'main') `
            -Echo

        $mainBefore = Get-FirstGitSha $ls

        if ($ls.ExitCode -ne 0 -or -not $mainBefore) {
            Write-Fail 'Fresh main read FAIL.'
            return $false
        }

        $clone = Invoke-Git `
            -Arguments @(
                'clone',
                '--single-branch',
                '--branch', 'main',
                '--no-tags',
                $repoUrl,
                $cloneDir
            ) `
            -Echo

        if ($clone.ExitCode -ne 0) {
            Write-Fail 'Disposable clone FAIL.'
            return $false
        }

        $cloneHeadResult = Invoke-Git `
            -Arguments @('rev-parse', 'HEAD') `
            -WorkingDirectory $cloneDir

        $cloneHeadSha = Get-FirstGitStdOutLine $cloneHeadResult

        if ($cloneHeadResult.ExitCode -ne 0 -or $cloneHeadSha -ne $mainBefore) {
            Write-Fail "Clone HEAD does not match fresh main: clone=$cloneHeadSha main=$mainBefore"
            return $false
        }

        Write-Ok 'Disposable clone HEAD exactly matches fresh remote main.'

        $switch = Invoke-Git `
            -Arguments @('switch', '-c', $branch) `
            -WorkingDirectory $cloneDir `
            -Echo

        if ($switch.ExitCode -ne 0) {
            Write-Fail 'Local test branch creation FAIL.'
            return $false
        }

        $commit = Invoke-Git `
            -Arguments @(
                '-c', 'user.name=VPS Control Write Test',
                '-c', 'user.email=vps-control-test@local.invalid',
                'commit',
                '--allow-empty',
                '-m', '[VPS-CONTROL] temporary GitHub write-path verification'
            ) `
            -WorkingDirectory $cloneDir `
            -Echo

        if ($commit.ExitCode -ne 0) {
            Write-Fail 'Empty commit FAIL.'
            return $false
        }

        $head = Invoke-Git `
            -Arguments @('rev-parse', 'HEAD') `
            -WorkingDirectory $cloneDir

        $headSha = Get-FirstGitStdOutLine $head

        if ($headSha -notmatch '^[0-9a-fA-F]{40}$') {
            Write-Fail 'Could not resolve test commit SHA.'
            return $false
        }

        $dry = Invoke-Git `
            -Arguments @(
                'push',
                '--dry-run',
                'origin',
                "HEAD:refs/heads/$branch"
            ) `
            -WorkingDirectory $cloneDir `
            -Echo

        if ($dry.ExitCode -ne 0) {
            Write-Fail 'git push --dry-run FAIL.'
            return $false
        }

        $push = Invoke-Git `
            -Arguments @(
                'push',
                '--set-upstream',
                'origin',
                "HEAD:refs/heads/$branch"
            ) `
            -WorkingDirectory $cloneDir `
            -Echo

        if ($push.ExitCode -ne 0) {
            Write-Fail 'REAL git push FAIL.'
            return $false
        }

        $remoteMayExist = $true

        $verify = Invoke-Git `
            -Arguments @(
                'ls-remote',
                '--heads',
                'origin',
                "refs/heads/$branch"
            ) `
            -WorkingDirectory $cloneDir `
            -Echo

        $remoteSha = Get-FirstGitSha $verify

        if ($verify.ExitCode -ne 0 -or $remoteSha -ne $headSha) {
            Write-Fail "Remote exact-SHA verification FAIL local=$headSha remote=$remoteSha"
            return $false
        }

        Write-Ok "Remote exact SHA PASS: $remoteSha"

        $delete = Invoke-Git `
            -Arguments @('push', 'origin', '--delete', $branch) `
            -WorkingDirectory $cloneDir `
            -Echo

        if ($delete.ExitCode -ne 0) {
            Write-Fail "Remote branch deletion FAIL. Branch may remain: $branch"
            return $false
        }

        $remoteMayExist = $false

        $absence = Invoke-Git `
            -Arguments @(
                'ls-remote',
                '--heads',
                'origin',
                "refs/heads/$branch"
            ) `
            -WorkingDirectory $cloneDir

        if ($absence.ExitCode -ne 0 -or (Get-FirstGitSha $absence)) {
            Write-Fail "Remote branch absence verification FAIL: $branch"
            return $false
        }

        $mainAfterResult = Invoke-Git `
            -Arguments @('ls-remote', '--heads', 'origin', 'main') `
            -WorkingDirectory $cloneDir

        $mainAfter = Get-FirstGitSha $mainAfterResult

        if ($mainAfter -eq $mainBefore) {
            Write-Ok "main unchanged: $mainAfter"
        }
        else {
            Write-Warn "main moved concurrently: before=$mainBefore after=$mainAfter"
            Write-Warn 'Тест никогда не выполнял push в main.'
        }

        Write-Ok 'GitHub WRITE push/verify/delete self-test PASS.'
        return $true
    }
    finally {
        if ($remoteMayExist -and (Test-Path -LiteralPath $cloneDir)) {
            Write-Warn "Cleanup retry for remote branch: $branch"

            [void](Invoke-Git `
                -Arguments @('push', 'origin', '--delete', $branch) `
                -WorkingDirectory $cloneDir `
                -Echo)
        }

        Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ============================================================================
# TUNNEL CONTROL
# ============================================================================

function Restart-Tunnel {
    return Invoke-WithMutationLock {
        Write-Step 'Restart PuTTY/SOCKS'

        $runtime = Get-Runtime
        $routes = Normalize-Routes $runtime.Effective

        [void](Stop-TunnelProcess)
        Start-Sleep -Seconds 1

        if (-not (Ensure-SocksTunnel)) {
            return $false
        }

        if (Test-AnyEffectiveVps $routes) {
            if (-not (Apply-EffectiveRoutesOnly `
                -Routes $routes `
                -Reason 'MANUAL_TUNNEL_RESTART')) {
                return $false
            }
        }

        Write-Ok 'Tunnel restarted.'
        return $true
    }
}

function Stop-Tunnel {
    return Invoke-WithMutationLock {
        Write-Step 'Stop tunnel'

        Stop-LegacyV62Watchdogs
        Stop-LegacyV61Watchdog
        Stop-LegacyV6Watchdog
        Stop-Watchdog

        $routes = New-RouteObject
        $path = New-ProxifierProfile -Routes $routes -DestinationPath $DirectProfilePath

        [void](Load-ProxifierProfile -Path $path -Routes $routes)

        $runtime = Get-Runtime
        $runtime.Override = 'DIRECT'
        $runtime.Effective = $routes
        $runtime.Health = New-HealthObject
        $runtime.LastReason = 'STOP_TUNNEL'
        Save-Runtime $runtime
        Update-OperationalStats -Routes $runtime.Effective -Health $runtime.Health
        Record-TelemetrySnapshot -Runtime $runtime -Force

        if (Stop-TunnelProcess) {
            Write-Ok 'Proxifier DIRECT; PuTTY/SOCKS stopped.'
            return $true
        }

        return $false
    }
}

# ============================================================================
# NETWORK-READY AUTOSTART
# ============================================================================

function Test-BasicNetworkReady {
    $dns = Test-DnsResolution $NetworkDnsHost

    if (-not $dns.Success) {
        return $false
    }

    if (-not (Ensure-ProbeHelpers)) {
        return $false
    }

    $probe = Invoke-HttpProbe -Route DIRECT -Url $NetworkHttpsUrl
    return [bool]$probe.Success
}

function Wait-NetworkReady {
    $deadline = (Get-Date).AddSeconds($NetworkReadyWaitSeconds)

    while ((Get-Date) -lt $deadline) {
        if (Test-BasicNetworkReady) {
            return $true
        }

        Start-Sleep -Seconds 3
    }

    return $false
}

function Invoke-AutoStart {
    Write-ControllerLog 'AUTOSTART begin'

    if (-not (Wait-NetworkReady)) {
        Write-ControllerLog "AUTOSTART no network after ${NetworkReadyWaitSeconds}s"
        return $false
    }

    Write-ControllerLog 'AUTOSTART network ready'
    return (Apply-RoutingConfiguration)
}

function Install-Autostart {
    Write-Step 'Windows autostart'

    Disable-LegacyV62AutostartIfPresent
    Disable-LegacyV61AutostartIfPresent
    Disable-LegacyV6AutostartIfPresent

    try {
        $taskAction = New-ScheduledTaskAction `
            -Execute 'powershell.exe' `
            -Argument (
                '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden ' +
                "-File `"$PSCommandPath`" -Action AutoStart -NoAppLaunch"
            )

        $taskTrigger = New-ScheduledTaskTrigger `
            -AtLogOn `
            -User $env:USERNAME

        $settings = New-ScheduledTaskSettingsSet `
            -StartWhenAvailable `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

        Register-ScheduledTask `
            -TaskName $AutostartTaskName `
            -Action $taskAction `
            -Trigger $taskTrigger `
            -Settings $settings `
            -Description 'VPS Control V6.3: wait for DNS+HTTPS network readiness and apply saved adaptive routing modes.' `
            -Force | Out-Null

        Write-Ok "Autostart installed: $AutostartTaskName"
        return $true
    }
    catch {
        Write-Fail "Autostart install failed: $($_.Exception.Message)"
        Write-Warn 'При необходимости запустите Control Center от администратора.'
        return $false
    }
}

function Remove-Autostart {
    Write-Step 'Remove Windows autostart'

    try {
        $task = Get-ScheduledTask `
            -TaskName $AutostartTaskName `
            -ErrorAction SilentlyContinue

        if (-not $task) {
            Write-Warn 'Autostart task not found.'
            return $true
        }

        Unregister-ScheduledTask `
            -TaskName $AutostartTaskName `
            -Confirm:$false

        Write-Ok 'Autostart removed.'
        return $true
    }
    catch {
        Write-Fail "Autostart remove failed: $($_.Exception.Message)"
        return $false
    }
}

# ============================================================================
# MENU
# ============================================================================


function Export-VpsControlConfig {
    try {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $desktop = [Environment]::GetFolderPath('Desktop')

        if (-not $desktop) {
            $desktop = $env:USERPROFILE
        }

        $path = Join-Path $desktop "VPS-Control-v6.3-export-$stamp.json"
        $payload = [pscustomobject]@{
            Version = $ControllerVersion
            ExportedAt = (Get-Date).ToString('o')
            RoutingConfig = $(Get-Config)
            Modules = $(Get-ModuleCatalog)
            PasswordIncluded = $false
        }

        Write-JsonAtomic -Path $path -Object $payload
        Write-Ok "Export created: $path"
        Write-Host 'Пароль VPS в export НЕ включён.'
        return $true
    }
    catch {
        Write-Fail "Export failed: $($_.Exception.Message)"
        return $false
    }
}

function Invoke-MaintenanceCleanup {
    Write-Step 'Maintenance cleanup'

    $cutoff = (Get-Date).AddDays(-$MaintenanceRetentionDays)
    $removed = 0

    foreach ($pattern in @(
        'ADWF-git-*',
        'VPS-Control-*test*'
    )) {
        try {
            Get-ChildItem -LiteralPath $env:TEMP -Directory -Filter $pattern -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -lt $cutoff } |
                ForEach-Object {
                    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
                    $removed++
                }
        }
        catch {
            Write-Warn "TEMP cleanup warning: $($_.Exception.Message)"
        }
    }

    foreach ($log in @(
        $WatchdogLogFile,
        $ControllerLogFile,
        $DecisionLogFile,
        $SelfTestHistoryFile,
        $IncidentFile
    )) {
        Rotate-LogIfNeeded $log
    }

    Trim-TelemetryHistory

    Write-Ok "Maintenance complete. Removed old temp directories: $removed"
    return $true
}

function Show-MaintenanceMenu {
    while ($true) {
        Clear-Host
        Write-Host '============================================================' -ForegroundColor DarkCyan
        Write-Host '          VPS CONTROL V6.3 - MAINTENANCE' -ForegroundColor Cyan
        Write-Host '============================================================' -ForegroundColor DarkCyan
        Write-Host ''
        Write-Host '  1  Export config + module catalog (NO password)'
        Write-Host '  2  Cleanup old test TEMP + telemetry/log retention'
        Write-Host '  3  Sanitized support bundle'
        Write-Host '  4  Show state folder'
        Write-Host '  5  Daily read-only self-test ON / change time'
        Write-Host '  6  Daily read-only self-test OFF'
        Write-Host '  0  Back'
        Write-Host ''

        $choice = (Read-Host 'Выберите пункт').Trim()

        switch ($choice) {
            '1' {
                [void](Export-VpsControlConfig)
                Pause-Control
            }

            '2' {
                [void](Invoke-MaintenanceCleanup)
                Pause-Control
            }

            '3' {
                [void](New-SupportBundle)
                Pause-Control
            }

            '4' {
                Write-Host "State folder: $StateDir"
                Write-Host "Modules:      $ModulesFile"
                Write-Host "LKG profile:  $LastGoodProfilePath"
                Write-Host "Telemetry:    $TelemetryFile"
                Write-Host "Stats:        $OperationalStatsFile"
                Write-Host "Self-tests:   $SelfTestHistoryFile"
                Pause-Control
            }

            '5' {
                $value = (Read-Host "Время HH:mm [Enter=$SelfTestDefaultTime]").Trim()
                if (-not $value) { $value = $SelfTestDefaultTime }
                [void](Install-DailySelfTest -AtTime $value)
                Pause-Control
            }

            '6' {
                [void](Remove-DailySelfTest)
                Pause-Control
            }

            '0' {
                return
            }
        }
    }
}

function Format-Mode([string]$Mode) {
    switch ($Mode) {
        'VPS' { return '[VPS]' }
        'AUTO' { return '[AUTO]' }
        default { return '[DIRECT]' }
    }
}

function Show-DiagnosticsMenu {
    while ($true) {
        Clear-Host
        Write-Host '============================================================' -ForegroundColor DarkCyan
        Write-Host '          VPS CONTROL V6.3.1 - DIAGNOSTICS' -ForegroundColor Cyan
        Write-Host '============================================================' -ForegroundColor DarkCyan
        Write-Host ''
        Write-Host '  1  Status'
        Write-Host '  2  Full diagnostics / module health'
        Write-Host '  3  GitHub READ: ls-remote + clone + fetch + fsck'
        Write-Host '  4  GitHub WRITE: temp branch + push + verify + delete'
        Write-Host '  5  DIRECT vs VPS latency / health benchmark'
        Write-Host '  6  READ-ONLY controller self-test'
        Write-Host '  7  24h observability / uptime summary'
        Write-Host '  8  Sanitized support bundle'
        Write-Host '  0  Back'
        Write-Host ''

        $choice = (Read-Host 'Выберите пункт').Trim()

        switch ($choice) {
            '1' {
                Show-Status
                Pause-Control
            }

            '2' {
                Invoke-Diagnostics
                Pause-Control
            }

            '3' {
                [void](Invoke-GitHubReadSelfTest)
                Pause-Control
            }

            '4' {
                [void](Invoke-GitHubWriteSelfTest)
                Pause-Control
            }

            '5' {
                Invoke-RouteBenchmark
                Pause-Control
            }

            '6' {
                [void](Invoke-ReadOnlySelfTest)
                Pause-Control
            }

            '7' {
                Show-ObservationSummary -Hours $ObservationSummaryHours
                Pause-Control
            }

            '8' {
                [void](New-SupportBundle)
                Pause-Control
            }

            '0' {
                return
            }
        }
    }
}

function Show-Menu {
    while ($true) {
        Clear-Host

        $config = Get-Config
        $runtime = Get-Runtime

        Write-Host '============================================================' -ForegroundColor DarkCyan
        Write-Host '       VPS CONTROL CENTER - VERSION 6.3 OBSERVABILITY' -ForegroundColor Cyan
        Write-Host '============================================================' -ForegroundColor DarkCyan
        Write-Host ''
        Write-Host 'РЕЖИМЫ: DIRECT -> AUTO -> VPS -> DIRECT' -ForegroundColor White
        Write-Host ''
        Write-Host ("  1  {0,-8} OpenAI       ChatGPT / Codex / OpenAI" -f (Format-Mode $config.OpenAI))
        Write-Host ("  2  {0,-8} GitHub       Git / gh / API / raw / assets" -f (Format-Mode $config.GitHub))
        Write-Host ("  3  {0,-8} DevPackages  npm / Node / PyPI / Python" -f (Format-Mode $config.DevPackages))
        Write-Host ("  4  {0,-8} Firefox      весь TCP-трафик Firefox" -f (Format-Mode $config.Firefox))
        Write-Host ''
        Write-Host '  5  APPLY       применить config + AUTO resolution'
        Write-Host '  6  DIRECT      временный global DIRECT override'
        Write-Host '  7  DIAGNOSTICS health / self-test / statistics / GitHub'
        Write-Host '  8  RESTART     перезапустить PuTTY/SOCKS'
        Write-Host '  9  STOP        DIRECT + остановить tunnel'
        Write-Host ''
        Write-Host '  A  Preset OpenAI       OpenAI=VPS, остальное DIRECT'
        Write-Host '  D  Preset Development  OpenAI=VPS, GitHub/AUTO, Packages/AUTO'
        Write-Host '  F  Preset Firefox      OpenAI=VPS + Firefox=VPS'
        Write-Host ''
        Write-Host '  S  Autostart ON        DNS+HTTPS ready + apply at logon'
        Write-Host '  R  Autostart OFF'
        Write-Host '  M  Maintenance         support bundle / daily test / cleanup'
        Write-Host ''
        Write-Host '  0  Exit'
        Write-Host ''

        if (Test-Path -LiteralPath $AttentionFile) {
            Write-Host 'ATTENTION: last read-only self-test FAILED. Open Diagnostics -> Self-test.' -ForegroundColor Red
            Write-Host ''
        }

        Write-Host 'Current effective:' -ForegroundColor Yellow

        foreach ($module in $ModuleNames) {
            $metric = Normalize-ModuleMetric $runtime.Metrics.$module
            $latency = if ($metric.LatencyMs -gt 0) { "$($metric.LatencyMs)ms" } else { '-' }

            Write-Host (
                '  {0,-14} configured={1,-7} effective={2,-6} health={3,-9} latency={4}' -f
                $module,
                $config.$module,
                $runtime.Effective.$module,
                $metric.State,
                $latency
            )
        }

        Write-Host "  Override: $($runtime.Override)"
        Write-Host ''

        $choice = (Read-Host 'Выберите пункт').Trim().ToUpperInvariant()

        switch ($choice) {
            '1' {
                Cycle-DesiredMode 'OpenAI'
            }

            '2' {
                Cycle-DesiredMode 'GitHub'
            }

            '3' {
                Cycle-DesiredMode 'DevPackages'
            }

            '4' {
                Cycle-DesiredMode 'Firefox'
            }

            '5' {
                [void](Apply-RoutingConfiguration)
                Pause-Control
            }

            '6' {
                [void](Enable-DirectOverride)
                Pause-Control
            }

            '7' {
                Show-DiagnosticsMenu
            }

            '8' {
                [void](Restart-Tunnel)
                Pause-Control
            }

            '9' {
                [void](Stop-Tunnel)
                Pause-Control
            }

            'A' {
                Set-Preset 'OpenAI'
                [void](Apply-RoutingConfiguration)
                Pause-Control
            }

            'D' {
                Set-Preset 'Development'
                [void](Apply-RoutingConfiguration)
                Pause-Control
            }

            'F' {
                Set-Preset 'Firefox'
                [void](Apply-RoutingConfiguration)
                Pause-Control
            }

            'S' {
                [void](Install-Autostart)
                Pause-Control
            }

            'R' {
                [void](Remove-Autostart)
                Pause-Control
            }

            'M' {
                Show-MaintenanceMenu
            }

            '0' {
                return
            }
        }
    }
}

# ============================================================================
# ENTRY POINT
# ============================================================================

if (-not (Enter-ForegroundInstance)) {
    exit 70
}

try {
    switch ($Action) {
        'Menu' {
            Show-Menu
        }

        'Apply' {
            if (-not (Apply-RoutingConfiguration)) {
                exit 1
            }
        }

        'Direct' {
            if (-not (Enable-DirectOverride)) {
                exit 1
            }
        }

        'Diagnose' {
            Invoke-Diagnostics
        }

        'Status' {
            Show-Status
        }

        'RestartTunnel' {
            if (-not (Restart-Tunnel)) {
                exit 1
            }
        }

        'StopTunnel' {
            if (-not (Stop-Tunnel)) {
                exit 1
            }
        }

        'Watchdog' {
            Invoke-Watchdog
        }

        'AutoStart' {
            if (-not (Invoke-AutoStart)) {
                exit 1
            }
        }

        'InstallAutostart' {
            if (-not (Install-Autostart)) {
                exit 1
            }
        }

        'RemoveAutostart' {
            if (-not (Remove-Autostart)) {
                exit 1
            }
        }

        'GitHubReadTest' {
            if (-not (Invoke-GitHubReadSelfTest)) {
                exit 1
            }
        }

        'GitHubWriteTest' {
            if (-not (Invoke-GitHubWriteSelfTest)) {
                exit 1
            }
        }

        'Benchmark' {
            Invoke-RouteBenchmark
        }

        'Maintenance' {
            Show-MaintenanceMenu
        }

        'ExportConfig' {
            if (-not (Export-VpsControlConfig)) {
                exit 1
            }
        }

        'Cleanup' {
            if (-not (Invoke-MaintenanceCleanup)) {
                exit 1
            }
        }

        'SelfTest' {
            $result = Invoke-ReadOnlySelfTest
            if ($result.Overall -eq 'FAIL') {
                exit 1
            }
        }

        'DailySelfTest' {
            $result = Invoke-ReadOnlySelfTest -Quiet
            if ($result.Overall -eq 'FAIL') {
                exit 1
            }
        }

        'Summary' {
            Show-ObservationSummary -Hours $ObservationSummaryHours
        }

        'SupportBundle' {
            if (-not (New-SupportBundle)) {
                exit 1
            }
        }

        'InstallDailySelfTest' {
            if (-not (Install-DailySelfTest -AtTime $SelfTestDefaultTime)) {
                exit 1
            }
        }

        'RemoveDailySelfTest' {
            if (-not (Remove-DailySelfTest)) {
                exit 1
            }
        }

        'PresetOpenAI' {
            Set-Preset 'OpenAI'

            if (-not (Apply-RoutingConfiguration)) {
                exit 1
            }
        }

        'PresetDevelopment' {
            Set-Preset 'Development'

            if (-not (Apply-RoutingConfiguration)) {
                exit 1
            }
        }

        'PresetFirefox' {
            Set-Preset 'Firefox'

            if (-not (Apply-RoutingConfiguration)) {
                exit 1
            }
        }
    }
}
finally {
    Exit-ForegroundInstance
}
