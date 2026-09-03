#requires -Version 5.1

Describe 'PIPE-WU-165 State Snapshot CLI help surface' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $cliRoot = Join-Path $repoRoot 'tools\cli'
        $showPath = Join-Path $cliRoot 'Show-PnccStateSnapshot.ps1'
        $getPath = Join-Path $cliRoot 'Get-PnccStateSnapshot.ps1'
        $formatPath = Join-Path $cliRoot 'Format-PnccStateSnapshot.ps1'
        $readmePath = Join-Path $cliRoot 'README.md'
    }

    It 'exposes comment-based help for all three CLI commands under PowerShell 5.1' {
        foreach ($path in @($showPath,$getPath,$formatPath)) {
            $help = Get-Help $path -Full
            [string]$help.Synopsis | Should -Not -BeNullOrEmpty
            @($help.Examples.Example).Count | Should -BeGreaterThan 0
        }
    }

    It 'documents deterministic input and fixed runtime truth boundaries' {
        $text = Get-Content -LiteralPath $readmePath -Raw -Encoding UTF8
        $text | Should -Match 'caller-supplied deterministic state JSON'
        $text | Should -Match '127\.0\.0\.1:1081.*PRIMARY_AUTO.*AUTO'
        $text | Should -Match '127\.0\.0\.1:1080.*RESERVE_MANUAL.*MANUAL_ONLY'
        $text | Should -Match 'CI VERIFIED != RUNTIME VERIFIED'
        $text | Should -Match 'Physical Runtime Truth'
    }

    It 'keeps help text explicitly read-only and non-probing' {
        $combined = @($showPath,$getPath,$formatPath) | ForEach-Object { Get-Content -LiteralPath $_ -Raw -Encoding UTF8 }
        ($combined -join "`n") | Should -Match 'read-only'
        ($combined -join "`n") | Should -Match 'не выполняет live probes'
        ($combined -join "`n") | Should -Match '1080.*MANUAL_ONLY'
    }
}
