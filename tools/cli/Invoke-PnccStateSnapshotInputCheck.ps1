#requires -Version 5.1
<#
.SYNOPSIS
Проверяет PNCC State Snapshot input как отдельный процесс с детерминированным exit code.
.DESCRIPTION
Process-oriented read-only wrapper вокруг Test-PnccStateSnapshotInput.ps1. Предназначен для запуска через powershell.exe -File в автоматизации. Не выполняет live probes и не создаёт Physical Runtime Truth. Exit codes: 0 = VALID, 2 = caller input invalid, 3 = validator dependency/internal contract failure.
.PARAMETER InputPath
Путь к UTF-8 JSON с детерминированными входными состояниями PNCC.
.PARAMETER Json
Возвращает machine-readable PNCC_STATE_SNAPSHOT_INPUT_VALIDATION JSON.
.PARAMETER JsonDepth
Глубина внутреннего snapshot JSON от 4 до 32.
.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Invoke-PnccStateSnapshotInputCheck.ps1 -InputPath .\tools\cli\examples\state-input.example.json -Json; echo $LASTEXITCODE
.NOTES
Этот wrapper предназначен для отдельного процесса и завершает его через exit. Для composable/in-process проверки используйте Test-PnccStateSnapshotInput.ps1. 1081 = PRIMARY_AUTO/AUTO. 1080 = RESERVE_MANUAL/MANUAL_ONLY. CI VERIFIED != RUNTIME VERIFIED.
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

function New-PnccValidationResult {
    param([bool]$Valid, [string]$Code)
    [ordered]@{
        SchemaVersion = 1
        Contract = 'PNCC_STATE_SNAPSHOT_INPUT_VALIDATION'
        ReadOnly = $true
        Valid = [bool]$Valid
        Code = [string]$Code
    }
}

$validatorPath = Join-Path $PSScriptRoot 'Test-PnccStateSnapshotInput.ps1'
$result = $null
$exitCode = 3

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    $result = New-PnccValidationResult -Valid $false -Code 'VALIDATOR_DEPENDENCY_MISSING'
}
else {
    try {
        $validationJson = [string](& $validatorPath -InputPath $InputPath -Json -JsonDepth $JsonDepth)
        if ([string]::IsNullOrWhiteSpace($validationJson)) { throw 'EMPTY_VALIDATOR_RESULT' }
        $candidate = $validationJson | ConvertFrom-Json
        $contractValid = (
            $candidate.SchemaVersion -eq 1 -and
            $candidate.Contract -eq 'PNCC_STATE_SNAPSHOT_INPUT_VALIDATION' -and
            $candidate.ReadOnly -eq $true -and
            $null -ne $candidate.Valid -and
            -not [string]::IsNullOrWhiteSpace([string]$candidate.Code) -and
            ([string]$candidate.Code -match '^[A-Z0-9_]+$')
        )
        if (-not $contractValid) { throw 'INVALID_VALIDATOR_RESULT' }

        $result = New-PnccValidationResult -Valid ([bool]$candidate.Valid) -Code ([string]$candidate.Code)
        if ($result.Valid) { $exitCode = 0 } else { $exitCode = 2 }
    }
    catch {
        $result = New-PnccValidationResult -Valid $false -Code 'VALIDATOR_INTERNAL_FAILURE'
        $exitCode = 3
    }
}

if ($Json) {
    $result | ConvertTo-Json -Compress
}
elseif ($result.Valid) {
    'PNCC State Snapshot input: КОРРЕКТЕН ({0}); ExitCode=0' -f $result.Code
}
else {
    'PNCC State Snapshot input: НЕКОРРЕКТЕН ({0}); ExitCode={1}' -f $result.Code, $exitCode
}

exit $exitCode
