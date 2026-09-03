#requires -Version 5.1
<#
.SYNOPSIS
Проверяет PNCC State Snapshot input как отдельный процесс с детерминированным exit code.
.DESCRIPTION
Process-oriented read-only wrapper вокруг Test-PnccStateSnapshotInput.ps1. Предназначен для запуска через powershell.exe -File в автоматизации. Не выполняет live probes и не создаёт Physical Runtime Truth. Exit codes: 0 = VALID, 2 = caller input invalid, 3 = validator dependency/internal contract failure. Параметры caller input нормализуются внутри wrapper, чтобы отсутствующий InputPath или некорректный JsonDepth не обходили process contract через PowerShell parameter binder.
.PARAMETER InputPath
Путь к UTF-8 JSON с детерминированными входными состояниями PNCC. Отсутствующее/пустое значение нормализуется в INPUT_PATH_REQUIRED / exit 2.
.PARAMETER Json
Возвращает machine-readable PNCC_STATE_SNAPSHOT_INPUT_VALIDATION JSON.
.PARAMETER JsonDepth
Глубина внутреннего snapshot JSON. Допустимо целое число 4..32; по умолчанию 12. Некорректное значение нормализуется в JSON_DEPTH_INVALID / exit 2.
.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\cli\Invoke-PnccStateSnapshotInputCheck.ps1 -InputPath .\tools\cli\examples\state-input.example.json -Json; echo $LASTEXITCODE
.NOTES
Этот wrapper предназначен для отдельного процесса и завершает его через exit. Для composable/in-process проверки используйте Test-PnccStateSnapshotInput.ps1. 1081 = PRIMARY_AUTO/AUTO. 1080 = RESERVE_MANUAL/MANUAL_ONLY. CI VERIFIED != RUNTIME VERIFIED.
#>
[CmdletBinding()]
param(
    [string]$InputPath = '',

    [switch]$Json,

    [object]$JsonDepth = 12
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

$result = $null
$exitCode = 3
$callerInputCodes = @('INPUT_PATH_REQUIRED','JSON_DEPTH_INVALID','INPUT_NOT_FOUND','INPUT_UNREADABLE','INPUT_EMPTY','JSON_INVALID','SEMANTIC_INVALID')
$internalCodes = @('VALIDATOR_DEPENDENCY_MISSING','SNAPSHOT_CONTRACT_INVALID','VALIDATION_FAILED')
$normalizedJsonDepth = 12

if ([string]::IsNullOrWhiteSpace([string]$InputPath)) {
    $result = New-PnccValidationResult -Valid $false -Code 'INPUT_PATH_REQUIRED'
    $exitCode = 2
}
else {
    $depthText = [string]$JsonDepth
    $depthValue = 0
    $depthParsed = [int]::TryParse($depthText, [Globalization.NumberStyles]::Integer, [Globalization.CultureInfo]::InvariantCulture, [ref]$depthValue)
    if (-not $depthParsed -or $depthValue -lt 4 -or $depthValue -gt 32) {
        $result = New-PnccValidationResult -Valid $false -Code 'JSON_DEPTH_INVALID'
        $exitCode = 2
    }
    else {
        $normalizedJsonDepth = $depthValue
        $validatorPath = Join-Path $PSScriptRoot 'Test-PnccStateSnapshotInput.ps1'
        if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
            $result = New-PnccValidationResult -Valid $false -Code 'VALIDATOR_DEPENDENCY_MISSING'
            $exitCode = 3
        }
        else {
            try {
                $validationJson = [string](& $validatorPath -InputPath $InputPath -Json -JsonDepth $normalizedJsonDepth)
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
                if ($result.Valid) {
                    if ($result.Code -eq 'VALID') {
                        $exitCode = 0
                    }
                    else {
                        $result = New-PnccValidationResult -Valid $false -Code 'VALIDATOR_INTERNAL_FAILURE'
                        $exitCode = 3
                    }
                }
                elseif ($callerInputCodes -contains $result.Code) {
                    $exitCode = 2
                }
                elseif ($internalCodes -contains $result.Code) {
                    $exitCode = 3
                }
                else {
                    $result = New-PnccValidationResult -Valid $false -Code 'VALIDATOR_INTERNAL_FAILURE'
                    $exitCode = 3
                }
            }
            catch {
                $result = New-PnccValidationResult -Valid $false -Code 'VALIDATOR_INTERNAL_FAILURE'
                $exitCode = 3
            }
        }
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
