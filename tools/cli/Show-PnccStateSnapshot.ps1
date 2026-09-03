#requires -Version 5.1
<#
.SYNOPSIS
Показывает PNCC State Snapshot: русский статус по умолчанию или machine JSON с -Json.
.DESCRIPTION
Единая read-only команда поверх Test-PnccStateSnapshotInput.ps1, Get-PnccStateSnapshot.ps1 и Format-PnccStateSnapshot.ps1. Перед построением snapshot выполняет fail-closed preflight caller-supplied deterministic state JSON. Невалидный input возвращает только нормализованный код без raw exception/path. Команда не выполняет live probes и не создаёт Physical Runtime Truth.
.PARAMETER InputPath
Путь к UTF-8 JSON с детерминированными входными состояниями PNCC.
.PARAMETER Json
Возвращает machine-readable PNCC_STATE_SNAPSHOT JSON вместо русского текста.
.PARAMETER JsonDepth
Глубина JSON от 4 до 32.
.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Show-PnccStateSnapshot.ps1 -InputPath .\tools\cli\examples\state-input.example.json
.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Show-PnccStateSnapshot.ps1 -InputPath .\tools\cli\examples\state-input.example.json -Json
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

$validatorPath = Join-Path $PSScriptRoot 'Test-PnccStateSnapshotInput.ps1'
$getPath = Join-Path $PSScriptRoot 'Get-PnccStateSnapshot.ps1'
$formatPath = Join-Path $PSScriptRoot 'Format-PnccStateSnapshot.ps1'

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) { throw 'PNCC_STATE_SNAPSHOT_VALIDATOR_NOT_FOUND' }
if (-not (Test-Path -LiteralPath $getPath -PathType Leaf)) { throw 'PNCC_STATE_SNAPSHOT_GET_NOT_FOUND' }
if (-not (Test-Path -LiteralPath $formatPath -PathType Leaf)) { throw 'PNCC_STATE_SNAPSHOT_FORMAT_NOT_FOUND' }

try {
    $validationJson = [string](& $validatorPath -InputPath $InputPath -Json -JsonDepth $JsonDepth)
}
catch {
    throw 'PNCC_STATE_SNAPSHOT_VALIDATOR_FAILED'
}

try {
    $validation = $validationJson | ConvertFrom-Json
    $validationContractValid = (
        $validation.SchemaVersion -eq 1 -and
        $validation.Contract -eq 'PNCC_STATE_SNAPSHOT_INPUT_VALIDATION' -and
        $validation.ReadOnly -eq $true -and
        $null -ne $validation.Valid -and
        -not [string]::IsNullOrWhiteSpace([string]$validation.Code) -and
        ([string]$validation.Code -match '^[A-Z0-9_]+$')
    )
}
catch {
    throw 'PNCC_STATE_SNAPSHOT_VALIDATOR_INVALID_RESULT'
}

if (-not $validationContractValid) { throw 'PNCC_STATE_SNAPSHOT_VALIDATOR_INVALID_RESULT' }
if (-not [bool]$validation.Valid) {
    throw ('PNCC_STATE_SNAPSHOT_INPUT_INVALID:{0}' -f [string]$validation.Code)
}

$snapshotJson = [string](& $getPath -InputPath $InputPath -JsonDepth $JsonDepth)
if ([string]::IsNullOrWhiteSpace($snapshotJson)) { throw 'PNCC_STATE_SNAPSHOT_GENERATION_EMPTY' }

if ($Json) {
    $snapshotJson
    return
}

& $formatPath -SnapshotJson $snapshotJson
