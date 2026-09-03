#requires -Version 5.1
<#
.SYNOPSIS
Показывает PNCC State Snapshot: русский статус по умолчанию или machine JSON с -Json.
.DESCRIPTION
Единая read-only команда поверх Get-PnccStateSnapshot.ps1 и Format-PnccStateSnapshot.ps1. Принимает caller-supplied deterministic state JSON, не выполняет live probes и не создаёт Physical Runtime Truth. Промежуточный snapshot передаётся в памяти.
.PARAMETER InputPath
Путь к UTF-8 JSON с детерминированными входными состояниями PNCC.
.PARAMETER Json
Возвращает machine-readable PNCC_STATE_SNAPSHOT JSON вместо русского текста.
.PARAMETER JsonDepth
Глубина JSON от 4 до 32.
.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Show-PnccStateSnapshot.ps1 -InputPath .\state-input.json
.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Show-PnccStateSnapshot.ps1 -InputPath .\state-input.json -Json
.NOTES
1081 = PRIMARY_AUTO/AUTO. 1080 = RESERVE_MANUAL/MANUAL_ONLY; automation may not manage 1080 lifecycle. CI VERIFIED != RUNTIME VERIFIED.
#>
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
