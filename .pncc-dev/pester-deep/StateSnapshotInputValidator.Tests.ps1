#requires -Version 5.1

Describe 'PIPE-WU-167 State Snapshot input preflight validator' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $validatorPath = Join-Path $repoRoot 'tools\cli\Test-PnccStateSnapshotInput.ps1'
        $examplePath = Join-Path $repoRoot 'tools\cli\examples\state-input.example.json'
    }

    It 'validates the checked-in synthetic example with normalized machine output' {
        $json = [string](& $validatorPath -InputPath $examplePath -Json)
        $result = $json | ConvertFrom-Json
        $result.SchemaVersion | Should -Be 1
        $result.Contract | Should -Be 'PNCC_STATE_SNAPSHOT_INPUT_VALIDATION'
        $result.ReadOnly | Should -BeTrue
        $result.Valid | Should -BeTrue
        $result.Code | Should -Be 'VALID'
        $json | Should -Not -Match [regex]::Escape($examplePath)
        $json | Should -Not -Match '89\.125\.63\.46|128\.0\.94\.157|AdminVPS|password|secret|token'
    }

    It 'renders a Russian valid status by default' {
        [string](& $validatorPath -InputPath $examplePath) | Should -Match 'КОРРЕКТЕН \(VALID\)'
    }

    It 'normalizes malformed JSON without leaking raw input or path' {
        $path = Join-Path $TestDrive 'malformed.json'
        Set-Content -LiteralPath $path -Value '{ broken-json' -Encoding UTF8
        $json = [string](& $validatorPath -InputPath $path -Json)
        $result = $json | ConvertFrom-Json
        $result.Valid | Should -BeFalse
        $result.Code | Should -Be 'JSON_INVALID'
        $json | Should -Not -Match [regex]::Escape($path)
        $json | Should -Not -Match 'broken-json'
    }

    It 'normalizes empty input' {
        $path = Join-Path $TestDrive 'empty.json'
        Set-Content -LiteralPath $path -Value '' -Encoding UTF8
        $result = ([string](& $validatorPath -InputPath $path -Json)) | ConvertFrom-Json
        $result.Valid | Should -BeFalse
        $result.Code | Should -Be 'INPUT_EMPTY'
    }

    It 'normalizes semantic construction failure' {
        $path = Join-Path $TestDrive 'semantic-invalid.json'
        Set-Content -LiteralPath $path -Value '{"RuntimeAgeSeconds":"not-an-int"}' -Encoding UTF8
        $json = [string](& $validatorPath -InputPath $path -Json)
        $result = $json | ConvertFrom-Json
        $result.Valid | Should -BeFalse
        $result.Code | Should -Be 'SEMANTIC_INVALID'
        $json | Should -Not -Match [regex]::Escape($path)
        $json | Should -Not -Match 'not-an-int'
    }

    It 'normalizes a missing input path' {
        $path = Join-Path $TestDrive 'does-not-exist.json'
        $result = ([string](& $validatorPath -InputPath $path -Json)) | ConvertFrom-Json
        $result.Valid | Should -BeFalse
        $result.Code | Should -Be 'INPUT_NOT_FOUND'
    }

    It 'keeps the validator free of live probes and runtime mutation surfaces' {
        $text = Get-Content -LiteralPath $validatorPath -Raw -Encoding UTF8
        $text | Should -Not -Match 'Invoke-WebRequest|Invoke-RestMethod|Test-NetConnection|Start-Process|Stop-Process|Restart-Service|Set-Service|plink|putty|proxifier|1080.*start|1080.*stop'
        $text | Should -Match 'Get-PnccStateSnapshot\.ps1'
        $text | Should -Match 'CI VERIFIED != RUNTIME VERIFIED'
    }
}
