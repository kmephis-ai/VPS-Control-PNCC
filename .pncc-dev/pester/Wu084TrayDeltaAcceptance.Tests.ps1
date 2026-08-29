BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $runnerPath = Join-Path $repoRoot 'tools\runtime-agent\Invoke-PnccV701TrayDeltaAcceptance.ps1'
    $runnerText = [IO.File]::ReadAllText($runnerPath)
    $tokens = $null
    $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($runnerPath,[ref]$tokens,[ref]$errors)
}

Describe 'PIPE-WU-084 stale tray delta acceptance' {
    It 'is Windows PowerShell 5.1 parse-safe' {
        @($errors).Count | Should -Be 0
    }

    It 'does not declare a parameter named Pid' {
        $parameterNames = @($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.ParameterAst] },$true) | ForEach-Object { $_.Name.VariablePath.UserPath })
        @($parameterNames | Where-Object { $_ -ieq 'Pid' }).Count | Should -Be 0
    }

    It 'pins the exact frozen candidate and v7.0.1 UI' {
        $runnerText | Should -Match ([regex]::Escape("RunnerVersion = '1.1.0'"))
        $runnerText | Should -Match ([regex]::Escape("ExpectedCandidateSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'"))
        $runnerText | Should -Match ([regex]::Escape("ExpectedUiVersion = '7.0.1'"))
    }

    It 'allows stale shell tray baseline only when no live V7 process exists' {
        $runnerText | Should -Match 'Get-LiveV7Processes'
        $runnerText | Should -Match "FailureClass='LIVE_V7_PROCESS_BASELINE'"
        $runnerText | Should -Match 'STALE_TRAY_BASELINE_ACCEPTED'
        $runnerText | Should -Match 'no baseline tray element will be clicked or removed'
    }

    It 'tracks tray identity by UI Automation RuntimeId and post-launch delta' {
        $runnerText | Should -Match 'GetRuntimeId'
        $runnerText | Should -Match 'Get-TrayElementSignature'
        $runnerText | Should -Match 'Wait-NewTrayElement'
        $runnerText | Should -Match 'UNIQUE_NEW_TRAY_OBSERVED'
        $runnerText | Should -Match 'UNIQUE_NEW_TRAY_ELEMENT_NOT_OBSERVED'
    }

    It 'observes the exact launched process by PID-owned HWND' {
        $runnerText | Should -Match 'GetWindowThreadProcessId'
        $runnerText | Should -Match 'Wait-ExpectedPidWindow'
        $runnerText | Should -Match '\[StringComparison\]::Ordinal'
        $runnerText | Should -Not -Match 'MainWindowTitle'
    }

    It 'uses product-native exit only on the unique post-launch tray delta' {
        $runnerText | Should -Match 'Invoke-ProductNativeTrayExit -TrayRecord \$newTray'
        $runnerText | Should -Match 'PRODUCT_NATIVE_UNIQUE_TRAY_DELTA_EXIT'
        $runnerText | Should -Match 'Product-native tray exit invoked on the unique post-launch tray delta element'
    }

    It 'keeps forced termination as exact-identity emergency cleanup only' {
        @([regex]::Matches($runnerText,'Stop-Process')).Count | Should -Be 1
        $runnerText | Should -Match ([regex]::Escape('Stop-Process -Id $script:TestOwnedProcessId -Force'))
        $runnerText | Should -Match 'TEST_OWNED_CREATION_TIME_MISMATCH'
        $runnerText | Should -Match 'TEST_OWNED_EXECUTABLE_PATH_MISMATCH'
        $runnerText | Should -Match 'TEST_OWNED_COMMAND_MARKER_MISSING'
        $runnerText | Should -Match 'TEST_OWNED_DEMO_MARKER_MISSING'
        $runnerText | Should -Not -Match '(?i)taskkill|TerminateProcess'
    }

    It 'never counts emergency cleanup as clean acceptance' {
        $runnerText | Should -Match "CleanupMode='FORCED_EXACT_IDENTITY_TEST_OWNED_PROCESS_ONLY'"
        $runnerText | Should -Match '\$script:CleanExit=\$false'
        $runnerText | Should -Match 'if\(-not\$script:CleanExit\)\{\$success=\$false\}'
    }

    It 'keeps 1080 and 1081 observational and requires exact before-after equality' {
        $runnerText | Should -Match ([regex]::Escape('$script:ProtectedPorts = @(1080,1081)'))
        $runnerText | Should -Match 'Get-NetTCPConnection -State Listen'
        $runnerText | Should -Match 'PROTECTED_PORT_BASELINE_CHANGED'
        $runnerText | Should -Not -Match 'Invoke-PnccPrimary1081Recovery|RestartTunnel'
        $runnerText | Should -Match 'runtime_mutation=\$false'
        $runnerText | Should -Match 'runtime_authority=\$false'
        $runnerText | Should -Match 'promotion_eligible=\$false'
    }

    It 'preserves the workroot if exact test process survives cleanup' {
        $runnerText | Should -Match 'WORKROOT_PRESERVED'
        $runnerText | Should -Match 'work_root_preserved=\[bool\]\$script:WorkRootPreserved'
    }
}
