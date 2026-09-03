#requires -Version 5.1
<#
.SYNOPSIS
Проверяет caller-supplied JSON перед построением PNCC State Snapshot.
.DESCRIPTION
Read-only preflight для детерминированного входного JSON. Не выполняет live probes и не создаёт Physical Runtime Truth. Семантическая проверка делегируется существующему Get-PnccStateSnapshot.ps1. Ошибки нормализуются и не раскрывают путь к файлу или raw exception text.
.PARAMETER InputPath
Путь к UTF-8 JSON с детерминированными входными состояниями PNCC.
.PARAMETER Json
Возвращает machine-readable PNCC_STATE_SNAPSHOT_INPUT_VALIDATION JSON.
.PARAMETER JsonDepth
Глубина внутреннего snapshot JSON от 4 до 32.
.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Test-PnccStateSnapshotInput.ps1 -InputPath .\tools\cli\examples\state-input.example.json
.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Test-PnccStateSnapshotInput.ps1 -InputPath .\tools\cli\examples\state-input.example.json -Json
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
$valid = $false
$code = 'VALIDATION_FAILED'

if (-not (Test-Path -LiteralPath $getPath -PathType Leaf)) {
    $code = 'VALIDATOR_DEPENDENCY_MISSING'
}
elseif (-not (Test-Path -LiteralPath $InputPath -PathType Leaf)) {
    $code = 'INPUT_NOT_FOUND'
}
else {
    $raw = $null
    try {
        $resolved = Resolve-Path -LiteralPath $InputPath -ErrorAction Stop
        $raw = Get-Content -LiteralPath $resolved.ProviderPath -Raw -Encoding UTF8
    }
    catch {
        $code = 'INPUT_UNREADABLE'
    }

    if ($null -ne $raw) {
        if ([string]::IsNullOrWhiteSpace([string]$raw)) {
            $code = 'INPUT_EMPTY'
        }
        else {
            $syntaxValid = $false
            try {
                $null = $raw | ConvertFrom-Json
                $syntaxValid = $true
            }
            catch {
                $code = 'JSON_INVALID'
            }

            if ($syntaxValid) {
                try {
                    $snapshotJson = [string](& $getPath -InputPath $InputPath -JsonDepth $JsonDepth)
                    if ([string]::IsNullOrWhiteSpace($snapshotJson)) {
                        $code = 'SNAPSHOT_CONTRACT_INVALID'
                    }
                    else {
                        $snapshot = $snapshotJson | ConvertFrom-Json
                        if ($snapshot.SchemaVersion -eq 1 -and
                            $snapshot.Contract -eq 'PNCC_STATE_SNAPSHOT' -and
                            $snapshot.ReadOnly -eq $true -and
                            $snapshot.SecretsIncluded -eq $false) {
                            $valid = $true
                            $code = 'VALID'
                        }
                        else {
                            $code = 'SNAPSHOT_CONTRACT_INVALID'
                        }
                    }
                }
                catch {
                    $code = 'SEMANTIC_INVALID'
                }
            }
        }
    }
}

$result = [ordered]@{
    SchemaVersion = 1
    Contract = 'PNCC_STATE_SNAPSHOT_INPUT_VALIDATION'
    ReadOnly = $true
    Valid = [bool]$valid
    Code = [string]$code
}

if ($Json) {
    $result | ConvertTo-Json -Compress
    return
}

if ($valid) {
    'PNCC State Snapshot input: КОРРЕКТЕН (VALID)'
}
else {
    'PNCC State Snapshot input: НЕКОРРЕКТЕН ({0})' -f $code
}
