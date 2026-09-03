#requires -Version 5.1

Describe 'PIPE-WU-168 Show State Snapshot fail-closed input validation' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $show = Join-Path $repoRoot 'tools\cli\Show-PnccStateSnapshot.ps1'
        $get = Join-Path $repoRoot 'tools\cli\Get-PnccStateSnapshot.ps1'
        $example = Join-Path $repoRoot 'tools\cli\examples\state-input.example.json'
        $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('PNCC-WU168-PRIVATE-SENTINEL-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    }

    AfterAll {
        if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue }
    }

    It 'preserves valid machine snapshot semantics exactly' {
        $showJson = [string](& $show -InputPath $example -Json)
        $getJson = [string](& $get -InputPath $example)
        $result = $showJson | ConvertFrom-Json
        $result.Contract | Should -Be 'PNCC_STATE_SNAPSHOT'
        $result.SchemaVersion | Should -Be 1
        $result.ReadOnly | Should -BeTrue
        $result.SecretsIncluded | Should -BeFalse
        $showJson | Should -Be $getJson
    }

    It 'preserves valid Russian text path without validation chatter' {
        $text = @(& $show -InputPath $example) -join "`n"
        $text | Should -Match 'PRIMARY_AUTO'
        $text | Should -Match 'RESERVE_MANUAL'
        $text | Should -Not -Match 'КОРРЕКТЕН'
        $text | Should -Not -Match 'PNCC_STATE_SNAPSHOT_INPUT_VALIDATION'
    }

    It 'normalizes malformed JSON without leaking path or parser details' {
        $path = Join-Path $tempRoot 'malformed-private-input.json'
        Set-Content -LiteralPath $path -Value '{ broken json' -Encoding UTF8
        $message = $null
        try { & $show -InputPath $path -Json | Out-Null; throw 'EXPECTED_FAILURE_NOT_RAISED' } catch { $message = [string]$_.Exception.Message }
        $message | Should -Be 'PNCC_STATE_SNAPSHOT_INPUT_INVALID:JSON_INVALID'
        $message | Should -Not -Match [regex]::Escape($tempRoot)
        $message | Should -Not -Match 'ConvertFrom-Json'
        $message | Should -Not -Match 'broken json'
    }

    It 'normalizes empty input without leaking path' {
        $path = Join-Path $tempRoot 'empty-private-input.json'
        Set-Content -LiteralPath $path -Value '' -Encoding UTF8
        $message = $null
        try { & $show -InputPath $path | Out-Null; throw 'EXPECTED_FAILURE_NOT_RAISED' } catch { $message = [string]$_.Exception.Message }
        $message | Should -Be 'PNCC_STATE_SNAPSHOT_INPUT_INVALID:INPUT_EMPTY'
        $message | Should -Not -Match [regex]::Escape($tempRoot)
    }

    It 'normalizes semantic invalid input without leaking path or raw exception' {
        $path = Join-Path $tempRoot 'semantic-private-input.json'
        Set-Content -LiteralPath $path -Value '{"CapturedAt":"definitely-not-a-date"}' -Encoding UTF8
        $message = $null
        try { & $show -InputPath $path -Json | Out-Null; throw 'EXPECTED_FAILURE_NOT_RAISED' } catch { $message = [string]$_.Exception.Message }
        $message | Should -Be 'PNCC_STATE_SNAPSHOT_INPUT_INVALID:SEMANTIC_INVALID'
        $message | Should -Not -Match [regex]::Escape($tempRoot)
        $message | Should -Not -Match 'definitely-not-a-date'
    }

    It 'normalizes missing input without echoing caller path' {
        $path = Join-Path $tempRoot 'missing-private-input.json'
        $message = $null
        try { & $show -InputPath $path | Out-Null; throw 'EXPECTED_FAILURE_NOT_RAISED' } catch { $message = [string]$_.Exception.Message }
        $message | Should -Be 'PNCC_STATE_SNAPSHOT_INPUT_INVALID:INPUT_NOT_FOUND'
        $message | Should -Not -Match [regex]::Escape($tempRoot)
        $message | Should -Not -Match 'missing-private-input'
    }
}
