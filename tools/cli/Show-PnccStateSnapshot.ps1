#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$InputPath,

    [switch]$Json,

    [ValidateRange(4,32)]
    [int]$JsonDepth = 12
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$getPath = Join-Path $PSScriptRoot 'Get-PnccStateSnapshot.ps1'
$formatPath = Join-Path $PSScriptRoot 'Format-PnccStateSnapshot.ps1'
if (-not (Test-Path -LiteralPath $getPath -PathType Leaf)) { throw "PNCC_STATE_SNAPSHOT_GET_NOT_FOUND: $getPath" }
if (-not (Test-Path -LiteralPath $formatPath -PathType Leaf)) { throw "PNCC_STATE_SNAPSHOT_FORMAT_NOT_FOUND: $formatPath" }

$snapshotJson = [string](& $getPath -InputPath $InputPath -JsonDepth $JsonDepth)
if ([string]::IsNullOrWhiteSpace($snapshotJson)) { throw 'PNCC_STATE_SNAPSHOT_GENERATION_EMPTY' }

if ($Json) {
    $snapshotJson
    return
}

& $formatPath -SnapshotJson $snapshotJson
