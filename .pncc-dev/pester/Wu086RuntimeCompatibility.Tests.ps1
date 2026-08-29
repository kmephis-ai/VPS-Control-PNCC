BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $agentPath = Join-Path $repoRoot 'tools\runtime-agent\Invoke-PnccRuntimeQualificationAgent.ps1'
    $bootstrapPath = Join-Path $repoRoot 'tools\runtime-agent\Initialize-PnccRuntimeQualificationWorkspace.ps1'
    $agentText = [IO.File]::ReadAllText($agentPath)
    $bootstrapText = [IO.File]::ReadAllText($bootstrapPath)
}

Describe 'PIPE-WU-086 runtime qualification compatibility' {
    It 'keeps agent and bootstrap Windows PowerShell 5.1 parse-safe' {
        foreach ($path in @($agentPath,$bootstrapPath)) {
            $tokens=$null; $errors=$null
            [void][System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
            @($errors).Count | Should -Be 0
        }
    }

    It 'admits governed Stable 7.0.x candidate and request identities' {
        $agentText | Should -Match '\^PNCC-V7\\\.0\\\.\[0-9\]\+-\(\[0-9A-F\]\{12\}\)\$'
        $agentText | Should -Match '\^PNCC-V\(7\\\.0\\\.\[0-9\]\+\)-\(\[0-9A-F\]\{12\}\)\$'
        $agentText | Should -Match ([regex]::Escape('PNCC-RQ-V'))
    }

    It 'preserves historical RC14.39 identity admission' {
        $agentText | Should -Match 'PNCC-RC14\\\.39'
        $bootstrapText | Should -Match 'PNCC-RC14\\\.39'
    }

    It 'derives Stable provider bundle names from the exact 7.0.x version and source sha' {
        $bootstrapText | Should -Match '\^PNCC-V\(7\\\.0\\\.\[0-9\]\+\)-'
        $bootstrapText | Should -Match ([regex]::Escape("'PNCC-V' + `$stableVersion + '-' + `$sourceSha"))
        $bootstrapText | Should -Not -Match "PNCC-V7\\\.0\\\.0-' \+ \$sourceSha"
    }

    It 'requires provider build run identity and cannot grant runtime authority in dry-run' {
        $agentText | Should -Match ([regex]::Escape('provider_build_run_id must be positive'))
        $agentText | Should -Match ([regex]::Escape('runtime_mutation_permitted = $false'))
        $agentText | Should -Match ([regex]::Escape('public_ci_runtime_authority = $false'))
        $agentText | Should -Match ([regex]::Escape('promotion_eligible = $false'))
        $bootstrapText | Should -Match ([regex]::Escape('request and candidate provider build runs must match'))
    }

    It 'keeps fixed tunnel and credential safety invariants' {
        $agentText | Should -Match ([regex]::Escape('PRIMARY_AUTO port invariant mismatch'))
        $agentText | Should -Match ([regex]::Escape('RESERVE_MANUAL port invariant mismatch'))
        $agentText | Should -Match ([regex]::Escape('1080 lifecycle invariant mismatch'))
        $agentText | Should -Match ([regex]::Escape('plaintext -pw cannot be allowed'))
        $agentText | Should -Match ([regex]::Escape('host-key verification cannot be disabled'))
    }
}
