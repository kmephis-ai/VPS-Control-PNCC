#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$InputPath,

    [ValidateRange(4, 32)]
    [int]$JsonDepth = 12
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Get-PnccCliInputMember {
    [CmdletBinding()]
    param(
        $Object,
        [Parameter(Mandatory=$true)][string]$Name,
        $Default = $null
    )

    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$foundationPath = Join-Path $repoRoot 'src\foundations\windows-v7\V7-StateSnapshot.ps1'
if (-not (Test-Path -LiteralPath $foundationPath -PathType Leaf)) {
    throw "PNCC_STATE_SNAPSHOT_FOUNDATION_NOT_FOUND: $foundationPath"
}

. $foundationPath

$resolvedInput = Resolve-Path -LiteralPath $InputPath -ErrorAction Stop
$payloadText = Get-Content -LiteralPath $resolvedInput.ProviderPath -Raw -Encoding UTF8
if ([string]::IsNullOrWhiteSpace($payloadText)) {
    throw 'PNCC_STATE_SNAPSHOT_INPUT_EMPTY'
}
$payload = $payloadText | ConvertFrom-Json

$moduleNamesRaw = Get-PnccCliInputMember -Object $payload -Name 'ModuleNames' -Default @()
$moduleNames = @($moduleNamesRaw | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

$capturedAt = [datetime]::MinValue
$capturedAtRaw = Get-PnccCliInputMember -Object $payload -Name 'CapturedAt'
if ($null -ne $capturedAtRaw -and -not [string]::IsNullOrWhiteSpace([string]$capturedAtRaw)) {
    $capturedAt = [datetime]$capturedAtRaw
}

$runtimeAgeSeconds = [int](Get-PnccCliInputMember -Object $payload -Name 'RuntimeAgeSeconds' -Default -1)
$overallState = [string](Get-PnccCliInputMember -Object $payload -Name 'OverallState' -Default 'UNKNOWN')
$routingTunnelId = [string](Get-PnccCliInputMember -Object $payload -Name 'RoutingTunnelId' -Default 'PRIMARY_AUTO')

$snapshot = New-V7StateSnapshotContract `
    -Config (Get-PnccCliInputMember -Object $payload -Name 'Config') `
    -Runtime (Get-PnccCliInputMember -Object $payload -Name 'Runtime') `
    -Watchdog (Get-PnccCliInputMember -Object $payload -Name 'Watchdog') `
    -ProxifierStatus (Get-PnccCliInputMember -Object $payload -Name 'ProxifierStatus') `
    -ModuleNames $moduleNames `
    -OverallState $overallState `
    -PrimarySocksListening ([bool](Get-PnccCliInputMember -Object $payload -Name 'PrimarySocksListening' -Default $false)) `
    -ReserveSocksListening ([bool](Get-PnccCliInputMember -Object $payload -Name 'ReserveSocksListening' -Default $false)) `
    -RoutingTunnelId $routingTunnelId `
    -LastKnownGoodPresent ([bool](Get-PnccCliInputMember -Object $payload -Name 'LastKnownGoodPresent' -Default $false)) `
    -RuntimeAgeSeconds $runtimeAgeSeconds `
    -CapturedAt $capturedAt

$snapshot | ConvertTo-Json -Depth $JsonDepth -Compress
