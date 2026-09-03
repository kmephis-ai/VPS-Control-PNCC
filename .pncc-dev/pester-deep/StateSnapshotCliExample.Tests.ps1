#requires -Version 5.1

Describe 'PIPE-WU-166 State Snapshot copy-run example' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $showPath = Join-Path $repoRoot 'tools\cli\Show-PnccStateSnapshot.ps1'
        $examplePath = Join-Path $repoRoot 'tools\cli\examples\state-input.example.json'
        $rootReadmePath = Join-Path $repoRoot 'README.md'
        $cliReadmePath = Join-Path $repoRoot 'tools\cli\README.md'
    }

    It 'ships a synthetic parseable example without private runtime material' {
        Test-Path -LiteralPath $examplePath -PathType Leaf | Should -BeTrue
        $raw = Get-Content -LiteralPath $examplePath -Raw -Encoding UTF8
        { $raw | ConvertFrom-Json } | Should -Not -Throw
        $raw | Should -Not -Match '89\.125\.63\.46|128\.0\.94\.157|AdminVPS|password|secret|token'
    }

    It 'runs the checked-in example through the Russian text path' {
        $lines = @(& $showPath -InputPath $examplePath)
        $lines.Count | Should -BeGreaterThan 3
        ($lines -join "`n") | Should -Match 'PNCC — состояние'
        ($lines -join "`n") | Should -Match 'PRIMARY_AUTO.*127\.0\.0\.1:1081.*lifecycle=AUTO'
        ($lines -join "`n") | Should -Match 'RESERVE_MANUAL.*127\.0\.0\.1:1080.*lifecycle=MANUAL_ONLY'
    }

    It 'runs the same example through the machine JSON path' {
        $json = [string](& $showPath -InputPath $examplePath -Json)
        $snapshot = $json | ConvertFrom-Json
        $snapshot.SchemaVersion | Should -Be 1
        $snapshot.Contract | Should -Be 'PNCC_STATE_SNAPSHOT'
        $snapshot.ReadOnly | Should -BeTrue
        $snapshot.SecretsIncluded | Should -BeFalse
        @($snapshot.Tunnels | Where-Object { $_.Id -eq 'PRIMARY_AUTO' -and $_.Port -eq 1081 -and $_.Lifecycle -eq 'AUTO' }).Count | Should -Be 1
        @($snapshot.Tunnels | Where-Object { $_.Id -eq 'RESERVE_MANUAL' -and $_.Port -eq 1080 -and $_.Lifecycle -eq 'MANUAL_ONLY' -and $_.AutomationMayManageLifecycle -eq $false }).Count | Should -Be 1
    }

    It 'exposes the copy-run path from both readmes without claiming runtime truth' {
        $root = Get-Content -LiteralPath $rootReadmePath -Raw -Encoding UTF8
        $cli = Get-Content -LiteralPath $cliReadmePath -Raw -Encoding UTF8
        foreach ($text in @($root,$cli)) {
            $text | Should -Match 'tools\\cli\\examples\\state-input\.example\.json|tools/cli/examples/state-input\.example\.json'
            $text | Should -Match 'CI VERIFIED != RUNTIME VERIFIED'
        }
        $cli | Should -Match 'синтетическ|synthetic'
        $cli | Should -Match 'не является Runtime Truth|не доказывает'
    }
}
