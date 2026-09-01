#requires -Version 5.1
# PNCC Product State Snapshot Contract Foundation (PIPE-WU-143).
# Pure/read-only projection over state already observed by existing V7 modules.
# This file performs no probes, persistence, routing mutation, tunnel lifecycle action,
# process control, network request, credential access, or UI operation.

function Get-V7StateSnapshotMember {
    [CmdletBinding()]
    param(
        $Object,
        [Parameter(Mandatory=$true)][string]$Name
    )

    if ($null -eq $Object) { return $null }
    try {
        if ($Object -is [System.Collections.IDictionary]) {
            if ($Object.Contains($Name)) { return $Object[$Name] }
            return $null
        }
        $property = $Object.PSObject.Properties[$Name]
        if ($null -ne $property) { return $property.Value }
    }
    catch { }
    return $null
}

function Get-V7StateSnapshotModuleValue {
    [CmdletBinding()]
    param(
        $Runtime,
        [Parameter(Mandatory=$true)][string[]]$ContainerNames,
        [Parameter(Mandatory=$true)][string]$Module
    )

    foreach ($containerName in @($ContainerNames)) {
        $container = Get-V7StateSnapshotMember -Object $Runtime -Name $containerName
        if ($null -eq $container) { continue }
        $value = Get-V7StateSnapshotMember -Object $container -Name $Module
        if ($null -ne $value) { return $value }
    }
    return $null
}

function ConvertTo-V7StateSnapshotMode {
    [CmdletBinding()]
    param(
        $Value,
        [string]$Fallback = 'DIRECT'
    )

    $fallbackMode = ([string]$Fallback).Trim().ToUpperInvariant()
    if (@('DIRECT','AUTO','VPS') -notcontains $fallbackMode) { $fallbackMode = 'DIRECT' }
    if ($null -eq $Value) { return $fallbackMode }
    $mode = ([string]$Value).Trim().ToUpperInvariant()
    if (@('DIRECT','AUTO','VPS') -contains $mode) { return $mode }
    return $fallbackMode
}

function New-V7StateSnapshotContract {
    [CmdletBinding()]
    param(
        $Config,
        $Runtime,
        $Watchdog,
        $ProxifierStatus,
        [string[]]$ModuleNames = @(),
        [string]$OverallState = 'UNKNOWN',
        [bool]$PrimarySocksListening = $false,
        [bool]$ReserveSocksListening = $false,
        [string]$RoutingTunnelId = 'PRIMARY_AUTO',
        [bool]$LastKnownGoodPresent = $false,
        [int]$RuntimeAgeSeconds = -1,
        [datetime]$CapturedAt = [datetime]::MinValue
    )

    if ($CapturedAt -eq [datetime]::MinValue) { $CapturedAt = Get-Date }

    $moduleRows = @()
    foreach ($module in @($ModuleNames)) {
        if ([string]::IsNullOrWhiteSpace([string]$module)) { continue }

        $configuredRaw = Get-V7StateSnapshotMember -Object $Config -Name ([string]$module)
        $configured = ConvertTo-V7StateSnapshotMode -Value $configuredRaw -Fallback 'DIRECT'
        $observed = Get-V7StateSnapshotModuleValue -Runtime $Runtime -ContainerNames @('Observed','ObservedState') -Module ([string]$module)
        $effective = Get-V7StateSnapshotModuleValue -Runtime $Runtime -ContainerNames @('Effective') -Module ([string]$module)
        $reason = Get-V7StateSnapshotModuleValue -Runtime $Runtime -ContainerNames @('Reason','DecisionReason','LastReason') -Module ([string]$module)
        $health = Get-V7StateSnapshotModuleValue -Runtime $Runtime -ContainerNames @('Health') -Module ([string]$module)
        $metrics = Get-V7StateSnapshotModuleValue -Runtime $Runtime -ContainerNames @('Metrics') -Module ([string]$module)
        $latencyMs = Get-V7StateSnapshotMember -Object $metrics -Name 'LatencyMs'
        $failureClass = Get-V7StateSnapshotMember -Object $metrics -Name 'FailureClass'

        $moduleRows += [pscustomobject][ordered]@{
            Id = [string]$module
            Desired = $configured
            Configured = $configured
            Observed = $observed
            Effective = $effective
            Reason = $reason
            Health = $health
            LatencyMs = $latencyMs
            FailureClass = $failureClass
        }
    }

    $watchdogState = Get-V7StateSnapshotMember -Object $Watchdog -Name 'State'
    $watchdogDetail = Get-V7StateSnapshotMember -Object $Watchdog -Name 'Detail'
    $watchdogFresh = Get-V7StateSnapshotMember -Object $Watchdog -Name 'Fresh'
    $watchdogPid = Get-V7StateSnapshotMember -Object $Watchdog -Name 'Pid'
    $watchdogHeartbeatAge = Get-V7StateSnapshotMember -Object $Watchdog -Name 'HeartbeatAge'

    $proxifierRunning = Get-V7StateSnapshotMember -Object $ProxifierStatus -Name 'Running'
    $proxifierPid = Get-V7StateSnapshotMember -Object $ProxifierStatus -Name 'Pid'
    $proxifierText = Get-V7StateSnapshotMember -Object $ProxifierStatus -Name 'Text'

    $runtimeFresh = $null
    if ($RuntimeAgeSeconds -ge 0) { $runtimeFresh = [bool]($RuntimeAgeSeconds -le 300) }

    $primaryTunnel = [pscustomobject][ordered]@{
        Id = 'PRIMARY_AUTO'
        Host = '127.0.0.1'
        Port = 1081
        Lifecycle = 'AUTO'
        Listening = [bool]$PrimarySocksListening
        SelectedForVpsRules = [bool]($RoutingTunnelId -eq 'PRIMARY_AUTO')
        AutomationMayManageLifecycle = $true
    }
    $reserveTunnel = [pscustomobject][ordered]@{
        Id = 'RESERVE_MANUAL'
        Host = '127.0.0.1'
        Port = 1080
        Lifecycle = 'MANUAL_ONLY'
        Listening = [bool]$ReserveSocksListening
        SelectedForVpsRules = [bool]($RoutingTunnelId -eq 'RESERVE_MANUAL')
        AutomationMayManageLifecycle = $false
    }

    return [pscustomobject][ordered]@{
        SchemaVersion = 1
        Contract = 'PNCC_STATE_SNAPSHOT'
        CapturedAt = $CapturedAt.ToString('o')
        ReadOnly = $true
        SecretsIncluded = $false
        Overall = [pscustomobject][ordered]@{
            State = [string]$OverallState
        }
        RuntimeEvidence = [pscustomobject][ordered]@{
            Present = [bool]($null -ne $Runtime)
            AgeSeconds = [int]$RuntimeAgeSeconds
            Fresh = $runtimeFresh
        }
        RoutingTunnelId = [string]$RoutingTunnelId
        Tunnels = @($primaryTunnel, $reserveTunnel)
        Modules = @($moduleRows)
        Watchdog = [pscustomobject][ordered]@{
            State = $watchdogState
            Detail = $watchdogDetail
            Fresh = $watchdogFresh
            Pid = $watchdogPid
            HeartbeatAge = $watchdogHeartbeatAge
        }
        Proxifier = [pscustomobject][ordered]@{
            Running = $proxifierRunning
            Pid = $proxifierPid
            Text = $proxifierText
        }
        LastKnownGood = [pscustomobject][ordered]@{
            Present = [bool]$LastKnownGoodPresent
        }
    }
}
