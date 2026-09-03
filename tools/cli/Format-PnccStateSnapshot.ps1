#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$InputPath
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Get-PnccSnapshotMember {
    param($Object,[Parameter(Mandatory=$true)][string]$Name,$Default=$null)
    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}

function ConvertTo-PnccRuBool {
    param($Value,[string]$Unknown='неизвестно')
    if ($null -eq $Value) { return $Unknown }
    if ([bool]$Value) { return 'да' }
    return 'нет'
}

function ConvertTo-PnccRuValue {
    param($Value,[string]$Unknown='нет данных')
    if ($null -eq $Value) { return $Unknown }
    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) { return $Unknown }
    return $text
}

$resolvedInput = Resolve-Path -LiteralPath $InputPath -ErrorAction Stop
$payloadText = Get-Content -LiteralPath $resolvedInput.ProviderPath -Raw -Encoding UTF8
if ([string]::IsNullOrWhiteSpace($payloadText)) { throw 'PNCC_STATE_SNAPSHOT_INPUT_EMPTY' }
$snapshot = $payloadText | ConvertFrom-Json

if ((Get-PnccSnapshotMember $snapshot 'SchemaVersion') -ne 1) { throw 'PNCC_STATE_SNAPSHOT_SCHEMA_INVALID' }
if ((Get-PnccSnapshotMember $snapshot 'Contract') -ne 'PNCC_STATE_SNAPSHOT') { throw 'PNCC_STATE_SNAPSHOT_CONTRACT_INVALID' }
if ((Get-PnccSnapshotMember $snapshot 'ReadOnly') -ne $true) { throw 'PNCC_STATE_SNAPSHOT_READONLY_REQUIRED' }
if ((Get-PnccSnapshotMember $snapshot 'SecretsIncluded') -ne $false) { throw 'PNCC_STATE_SNAPSHOT_SECRETS_FLAG_INVALID' }

$overall = Get-PnccSnapshotMember $snapshot 'Overall'
$runtime = Get-PnccSnapshotMember $snapshot 'RuntimeEvidence'
$routingTunnelId = ConvertTo-PnccRuValue (Get-PnccSnapshotMember $snapshot 'RoutingTunnelId')
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('PNCC — состояние')
$lines.Add(('Общее состояние: {0}' -f (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $overall 'State'))))
$lines.Add(('Снимок: {0}' -f (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $snapshot 'CapturedAt'))))
$lines.Add(('Runtime: есть={0}; возраст={1} с; свежесть={2}' -f (ConvertTo-PnccRuBool (Get-PnccSnapshotMember $runtime 'Present')), (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $runtime 'AgeSeconds')), (ConvertTo-PnccRuBool (Get-PnccSnapshotMember $runtime 'Fresh'))))
$lines.Add(('Маршрутизирующий туннель: {0}' -f $routingTunnelId))
$lines.Add('Туннели:')
foreach ($tunnel in @((Get-PnccSnapshotMember $snapshot 'Tunnels' @()))) {
    if ($null -eq $tunnel) { continue }
    $id = ConvertTo-PnccRuValue (Get-PnccSnapshotMember $tunnel 'Id')
    $host = ConvertTo-PnccRuValue (Get-PnccSnapshotMember $tunnel 'Host')
    $port = ConvertTo-PnccRuValue (Get-PnccSnapshotMember $tunnel 'Port')
    $lifecycle = ConvertTo-PnccRuValue (Get-PnccSnapshotMember $tunnel 'Lifecycle')
    $listen = ConvertTo-PnccRuBool (Get-PnccSnapshotMember $tunnel 'Listening')
    $selected = ConvertTo-PnccRuBool (Get-PnccSnapshotMember $tunnel 'SelectedForVpsRules')
    $automation = ConvertTo-PnccRuBool (Get-PnccSnapshotMember $tunnel 'AutomationMayManageLifecycle')
    $lines.Add(('  {0} {1}:{2} | lifecycle={3} | слушает={4} | выбран={5} | автоуправление lifecycle={6}' -f $id,$host,$port,$lifecycle,$listen,$selected,$automation))
}
$lines.Add('Модули:')
$modules = @((Get-PnccSnapshotMember $snapshot 'Modules' @()))
if ($modules.Count -eq 0) {
    $lines.Add('  нет данных')
}
else {
    foreach ($module in $modules) {
        $latency = Get-PnccSnapshotMember $module 'LatencyMs'
        $latencyText = if ($null -eq $latency) { 'нет данных' } else { '{0} мс' -f $latency }
        $lines.Add(('  {0} | желаемое={1} | эффективно={2} | здоровье={3} | причина={4} | задержка={5}' -f `
            (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $module 'Id')),
            (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $module 'Desired')),
            (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $module 'Effective')),
            (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $module 'Health')),
            (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $module 'Reason')),
            $latencyText))
    }
}
$watchdog = Get-PnccSnapshotMember $snapshot 'Watchdog'
$lines.Add(('Watchdog: состояние={0}; свежесть={1}; PID={2}; heartbeat={3}' -f `
    (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $watchdog 'State')),
    (ConvertTo-PnccRuBool (Get-PnccSnapshotMember $watchdog 'Fresh')),
    (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $watchdog 'Pid')),
    (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $watchdog 'HeartbeatAge'))))
$proxifier = Get-PnccSnapshotMember $snapshot 'Proxifier'
$lines.Add(('Proxifier: запущен={0}; PID={1}; состояние={2}' -f `
    (ConvertTo-PnccRuBool (Get-PnccSnapshotMember $proxifier 'Running')),
    (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $proxifier 'Pid')),
    (ConvertTo-PnccRuValue (Get-PnccSnapshotMember $proxifier 'Text'))))
$lkg = Get-PnccSnapshotMember $snapshot 'LastKnownGood'
$lines.Add(('Last Known Good: есть={0}' -f (ConvertTo-PnccRuBool (Get-PnccSnapshotMember $lkg 'Present'))))
$lines
