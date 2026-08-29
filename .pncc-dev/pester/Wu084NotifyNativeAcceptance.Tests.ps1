BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $runnerPath = Join-Path $repoRoot 'tools\runtime-agent\Invoke-PnccV701NotifyNativeAcceptance.ps1'
    $runnerText = [IO.File]::ReadAllText($runnerPath)
    $tokens=$null; $errors=$null
    $ast=[System.Management.Automation.Language.Parser]::ParseFile($runnerPath,[ref]$tokens,[ref]$errors)
}

Describe 'PIPE-WU-084 PID-native NotifyIcon acceptance' {
    It 'is Windows PowerShell 5.1 parse-safe' { @($errors).Count | Should -Be 0 }

    It 'does not declare a parameter named Pid' {
        $names=@($ast.FindAll({param($node) $node -is [System.Management.Automation.Language.ParameterAst]},$true)|ForEach-Object{$_.Name.VariablePath.UserPath})
        @($names|Where-Object{$_ -ieq 'Pid'}).Count | Should -Be 0
    }

    It 'pins the exact frozen candidate and v7.0.1 UI' {
        $runnerText | Should -Match ([regex]::Escape("RunnerVersion = '1.2.0'"))
        $runnerText | Should -Match ([regex]::Escape("ExpectedCandidateSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'"))
        $runnerText | Should -Match ([regex]::Escape("ExpectedUiVersion = '7.0.1'"))
    }

    It 'ignores Explorer tray identity and blocks only a live V7 process baseline' {
        $runnerText | Should -Match 'Assert-NoLiveV7ProcessBaseline'
        $runnerText | Should -Match 'LIVE_V7_PROCESS_BASELINE'
        $runnerText | Should -Match 'stale Explorer tray artifacts are ignored'
        $runnerText | Should -Match 'explorer_tray_identity_used=\$false'
        $runnerText | Should -Not -Match 'GetRuntimeId|Wait-NewTrayElement|TrayDeltaSignature'
    }

    It 'observes the exact launched process by PID-owned HWND' {
        $runnerText | Should -Match 'GetWindowThreadProcessId'
        $runnerText | Should -Match 'Wait-ExpectedPidWindow'
        $runnerText | Should -Match '\[StringComparison\]::Ordinal'
        $runnerText | Should -Not -Match 'MainWindowTitle'
    }

    It 'uses the .NET Framework NotifyIcon callback contract directly' {
        $runnerText | Should -Match ([regex]::Escape('$script:WmTrayMouseMessage = 0x0800'))
        $runnerText | Should -Match ([regex]::Escape('$script:WmRButtonUp = 0x0205'))
        $runnerText | Should -Match 'PostTrayRightButtonUp'
        $runnerText | Should -Match 'PostMessage\(new IntPtr\(handle\),0x0800,IntPtr.Zero,new IntPtr\(0x0205\)\)'
        $runnerText | Should -Match 'WindowsForms10\.Window\.0\.app\.\*'
    }

    It 'proves the NotifyIcon native window by observing the exact product exit menu' {
        $runnerText | Should -Match 'Invoke-ExactProcessNotifyNativeExit'
        $runnerText | Should -Match 'NOTIFY_NATIVE_WINDOW_PROVEN'
        $runnerText | Should -Match 'Wait-ExactExitMenuItem'
        $runnerText | Should -Match 'PRODUCT_NATIVE_EXIT_INVOKED'
        $runnerText | Should -Match 'Explorer tray identity was not used'
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

    It 'keeps 1080 and 1081 observational with exact before-after equality' {
        $runnerText | Should -Match ([regex]::Escape('$script:ProtectedPorts = @(1080,1081)'))
        $runnerText | Should -Match 'Get-NetTCPConnection -State Listen'
        $runnerText | Should -Match 'PROTECTED_PORT_BASELINE_CHANGED'
        $runnerText | Should -Not -Match 'Invoke-PnccPrimary1081Recovery|RestartTunnel'
        $runnerText | Should -Match 'runtime_mutation=\$false'
        $runnerText | Should -Match 'runtime_authority=\$false'
        $runnerText | Should -Match 'promotion_eligible=\$false'
    }

    It 'preserves product launch evidence and live workroot safety' {
        $runnerText | Should -Match 'PRODUCT_LAUNCH_LOG_CAPTURED'
        $runnerText | Should -Match 'WORKROOT_PRESERVED'
        $runnerText | Should -Match 'work_root_preserved=\[bool\]\$script:WorkRootPreserved'
    }
}
