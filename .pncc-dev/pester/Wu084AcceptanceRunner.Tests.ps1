BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $runnerPath = Join-Path $repoRoot 'tools\runtime-agent\Invoke-PnccV701PhysicalCleanStartup.ps1'
    $runnerText = [IO.File]::ReadAllText($runnerPath)
    $tokens = $null
    $parseErrors = $null
    $runnerAst = [System.Management.Automation.Language.Parser]::ParseFile($runnerPath,[ref]$tokens,[ref]$parseErrors)
}

Describe 'PIPE-WU-084 physical acceptance runner' {
    It 'is Windows PowerShell 5.1 parse-safe' {
        @($parseErrors).Count | Should -Be 0
    }

    It 'does not declare a parameter named Pid because PS5.1 PID is read-only' {
        $pidParameters = @($runnerAst.FindAll({
            param($node)
            $node -is [System.Management.Automation.Language.ParameterAst] -and
            [string]::Equals($node.Name.VariablePath.UserPath,'Pid',[StringComparison]::OrdinalIgnoreCase)
        },$true))
        $pidParameters.Count | Should -Be 0
        $runnerText | Should -Match 'TargetProcessId'
    }

    It 'keeps the repository runner ASCII-safe for Windows PowerShell 5.1' {
        @($runnerText.ToCharArray() | Where-Object { [int]$_ -gt 127 }).Count | Should -Be 0
        $runnerText | Should -Match ([regex]::Escape("RunnerVersion = '1.0.4'"))
        $runnerText | Should -Match 'Convert-CodePointsToString'
        $runnerText | Should -Match '0x0414,0x0415,0x041C,0x041E'
        $runnerText | Should -Match '\[char\]0x00B7'
    }

    It 'pins the exact frozen v7.0.1 candidate' {
        $runnerText | Should -Match ([regex]::Escape("ExpectedCandidateSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'"))
        $runnerText | Should -Match ([regex]::Escape("ExpectedUiVersion = '7.0.1'"))
    }

    It 'discovers PID-owned top-level HWNDs rather than relying on MainWindowTitle' {
        $runnerText | Should -Match 'EnumWindows'
        $runnerText | Should -Match 'GetWindowThreadProcessId'
        $runnerText | Should -Match 'IsWindowVisible'
        $runnerText | Should -Not -Match 'MainWindowTitle'
    }

    It 'requires the exact visible title for the exact test process' {
        $runnerText | Should -Match 'Wait-ExpectedPidWindow'
        $runnerText | Should -Match '\$window\.Visible'
        $runnerText | Should -Match '\[StringComparison\]::Ordinal'
        $runnerText | Should -Match 'Wait-ExpectedPidWindow -TargetProcessId \$script:TestOwnedPid'
    }

    It 'fails closed when an old VPS Control UI baseline is observable' {
        $runnerText | Should -Match 'Assert-CleanUiBaseline'
        $runnerText | Should -Match 'DIRTY_UI_BASELINE'
        $runnerText | Should -Match 'PREEXISTING_VPS_CONTROL_UI_DETECTED'
    }

    It 'uses the product tray exit path for clean exit' {
        $runnerText | Should -Match 'UIAutomationClient'
        $runnerText | Should -Match ([regex]::Escape("ExpectedTrayName = 'VPS Control Center'"))
        $runnerText | Should -Match 'ExpectedExitMenuText = Convert-CodePointsToString'
        $runnerText | Should -Match 'Invoke-ProductNativeTrayExit'
    }

    It 'guards emergency termination by complete fresh process identity' {
        $runnerText | Should -Match 'Assert-ExactTestOwnedProcessIdentity'
        $runnerText | Should -Match 'TEST_OWNED_CREATION_TIME_MISMATCH'
        $runnerText | Should -Match 'TEST_OWNED_EXECUTABLE_PATH_MISMATCH'
        $runnerText | Should -Match 'TEST_OWNED_COMMAND_MARKER_MISSING'
        $runnerText | Should -Match 'TEST_OWNED_DEMO_MARKER_MISSING'
        $runnerText | Should -Match 'pid\+creation_time\+executable_path\+launcher_marker\+demo_marker'
    }

    It 'allows Stop-Process only in the exact-identity emergency cleanup path' {
        @([regex]::Matches($runnerText,'Stop-Process')).Count | Should -Be 1
        $runnerText | Should -Match ([regex]::Escape('Stop-Process -Id $script:TestOwnedPid -Force'))
        $runnerText | Should -Not -Match 'Stop-Process\s+-Name'
        $runnerText | Should -Not -Match '(?is)Get-Process[^\r\n]*\|[^\r\n]*Stop-Process'
        $runnerText | Should -Not -Match '(?i)taskkill(\.exe)?'
    }

    It 'never treats emergency forced cleanup as clean acceptance' {
        $runnerText | Should -Match ([regex]::Escape("CleanupMode = 'FORCED_EXACT_IDENTITY_TEST_OWNED_PROCESS_ONLY'"))
        $runnerText | Should -Match ([regex]::Escape('$script:CleanExit = $false'))
        $runnerText | Should -Match ([regex]::Escape('if (-not $script:CleanExit) { $success = $false }'))
    }

    It 'preserves the extracted workroot when the launched process is still alive' {
        $runnerText | Should -Match 'processAliveAfterCleanup'
        $runnerText | Should -Match ([regex]::Escape('$script:WorkRootPreserved = $true'))
        $runnerText | Should -Match 'WORKROOT_PRESERVED'
        $runnerText | Should -Match ([regex]::Escape('if (-not $script:WorkRootPreserved)'))
        $runnerText | Should -Match 'work_root_preserved = \[bool\]\$script:WorkRootPreserved'
    }

    It 'captures the product launch log before temporary cleanup' {
        $runnerText | Should -Match 'Copy-ProductLaunchLog'
        $runnerText | Should -Match 'product-launch\.log'
        $copyIndex = $runnerText.IndexOf('Copy-ProductLaunchLog')
        $removeIndex = $runnerText.LastIndexOf('Remove-Item -LiteralPath $workRoot')
        $copyIndex | Should -BeGreaterThan -1
        $removeIndex | Should -BeGreaterThan $copyIndex
    }

    It 'keeps 1080 and 1081 observational and grants no runtime authority' {
        $runnerText | Should -Match ([regex]::Escape('$script:ProtectedPorts = @(1080,1081)'))
        $runnerText | Should -Match 'Get-NetTCPConnection -State Listen'
        $runnerText | Should -Not -Match "Start-EngineAction\s+'RestartTunnel'"
        $runnerText | Should -Not -Match 'Invoke-PnccPrimary1081Recovery'
        $runnerText | Should -Match 'runtime_mutation = \$false'
        $runnerText | Should -Match 'runtime_authority = \$false'
        $runnerText | Should -Match 'promotion_eligible = \$false'
    }
}
