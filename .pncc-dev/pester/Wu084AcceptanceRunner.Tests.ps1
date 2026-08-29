BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $runnerPath = Join-Path $repoRoot 'tools\runtime-agent\Invoke-PnccV701PhysicalCleanStartup.ps1'
    $runnerText = [IO.File]::ReadAllText($runnerPath)
}

Describe 'PIPE-WU-084 physical acceptance runner' {
    It 'is Windows PowerShell 5.1 parse-safe' {
        $tokens = $null
        $errors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($runnerPath,[ref]$tokens,[ref]$errors)
        @($errors).Count | Should -Be 0
    }

    It 'pins the exact frozen v7.0.1 candidate and UI title' {
        $runnerText | Should -Match [regex]::Escape("ExpectedCandidateSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'")
        $runnerText | Should -Match [regex]::Escape("ExpectedWindowTitle = 'VPS Control Center v7.0.1 · ДЕМО'")
        $runnerText | Should -Match [regex]::Escape("ExpectedUiVersion = '7.0.1'")
    }

    It 'discovers PID-owned top-level HWNDs rather than relying on MainWindowTitle' {
        $runnerText | Should -Match 'EnumWindows'
        $runnerText | Should -Match 'GetWindowThreadProcessId'
        $runnerText | Should -Match 'IsWindowVisible'
        $runnerText | Should -Not -Match 'MainWindowTitle'
    }

    It 'requires exact visible product title for the exact test PID' {
        $runnerText | Should -Match 'Wait-ExpectedPidWindow'
        $runnerText | Should -Match '\$window\.Visible'
        $runnerText | Should -Match '\[StringComparison\]::Ordinal'
    }

    It 'uses the product tray Exit item for clean exit' {
        $runnerText | Should -Match 'UIAutomationClient'
        $runnerText | Should -Match [regex]::Escape("ExpectedTrayName = 'VPS Control Center'")
        $runnerText | Should -Match [regex]::Escape("ExpectedExitMenuText = 'Закрыть интерфейс (маршрутизация останется)'")
        $runnerText | Should -Match 'Invoke-ProductNativeTrayExit'
    }

    It 'allows forced termination only for the exact test-owned PID emergency path' {
        @([regex]::Matches($runnerText,'Stop-Process')).Count | Should -Be 1
        $runnerText | Should -Match [regex]::Escape('Stop-Process -Id $script:TestOwnedPid -Force')
        $runnerText | Should -Not -Match 'Stop-Process\s+-Name'
        $runnerText | Should -Not -Match '(?is)Get-Process[^\r\n]*\|[^\r\n]*Stop-Process'
        $runnerText | Should -Not -Match '(?i)taskkill(\.exe)?'
    }

    It 'never treats emergency forced cleanup as clean acceptance' {
        $runnerText | Should -Match [regex]::Escape("CleanupMode = 'FORCED_TEST_OWNED_PROCESS_ONLY'")
        $runnerText | Should -Match [regex]::Escape('$script:CleanExit = $false')
        $runnerText | Should -Match [regex]::Escape('if (-not $script:CleanExit) { $success = $false }')
    }

    It 'keeps 1080 and 1081 observational and reports no runtime authority' {
        $runnerText | Should -Match [regex]::Escape('$script:ProtectedPorts = @(1080,1081)')
        $runnerText | Should -Match 'Get-NetTCPConnection -State Listen'
        $runnerText | Should -Not -Match "Start-EngineAction\s+'RestartTunnel'"
        $runnerText | Should -Not -Match 'Invoke-PnccPrimary1081Recovery'
        $runnerText | Should -Match 'runtime_mutation = \$false'
        $runnerText | Should -Match 'runtime_authority = \$false'
        $runnerText | Should -Match 'promotion_eligible = \$false'
    }
}
