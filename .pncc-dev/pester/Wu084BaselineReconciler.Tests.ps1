BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $wrapperPath = Join-Path $repoRoot 'tools\runtime-agent\Invoke-PnccV701OwnerAcceptance.ps1'
    $wrapperText = [IO.File]::ReadAllText($wrapperPath)
}

Describe 'PIPE-WU-084 owner acceptance baseline reconciler' {
    It 'is Windows PowerShell 5.1 parse-safe' {
        $tokens = $null
        $errors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($wrapperPath,[ref]$tokens,[ref]$errors)
        @($errors).Count | Should -Be 0
    }

    It 'does not declare a parameter named Pid' {
        $tokens = $null
        $errors = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseFile($wrapperPath,[ref]$tokens,[ref]$errors)
        $parameters = @($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.ParameterAst] },$true))
        @($parameters | Where-Object { $_.Name.VariablePath.UserPath -ieq 'Pid' }).Count | Should -Be 0
    }

    It 'keeps decoded source ASCII-safe and pins the frozen candidate' {
        @($wrapperText.ToCharArray() | Where-Object { [int]$_ -gt 127 }).Count | Should -Be 0
        $wrapperText | Should -Match ([regex]::Escape("WrapperVersion = '1.0.1'"))
        $wrapperText | Should -Match ([regex]::Escape("ExpectedCandidateSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'"))
        $wrapperText | Should -Match 'Convert-CodePointsToString'
    }

    It 'proves V7 UI identity with process command markers and PID-owned windows' {
        $wrapperText | Should -Match 'Get-CimInstance Win32_Process'
        $wrapperText | Should -Match 'VPS-Control-v7-launch\\\.ps1'
        $wrapperText | Should -Match 'VPS-Control-v7\\\.ps1'
        $wrapperText | Should -Match 'BaselineNativeWindow'
        $wrapperText | Should -Match 'GetWindowThreadProcessId'
        $wrapperText | Should -Match ([regex]::Escape("ExpectedWindowTitlePrefix = 'VPS Control Center v7.'"))
        $wrapperText | Should -Match 'StartsWith\(\$script:ExpectedWindowTitlePrefix'
    }

    It 'auto-reconciles only a single proven V7 process with a single tray element' {
        $wrapperText | Should -Match 'trayElements.Count -ne 1 -or \$provenProcesses.Count -ne 1'
        $wrapperText | Should -Match 'DIRTY_UI_BASELINE_UNSAFE'
        $wrapperText | Should -Match 'BASELINE_AUTO_RECONCILE_AUTHORIZED'
        $wrapperText | Should -Match 'BASELINE_AUTO_RECONCILED'
    }

    It 'uses product-native tray exit and has no force-kill primitive' {
        $wrapperText | Should -Match 'UIAutomationClient'
        $wrapperText | Should -Match 'Invoke-ProductNativeTrayExitForBaseline'
        $wrapperText | Should -Match 'ExpectedExitMenuText = Convert-CodePointsToString'
        $wrapperText | Should -Not -Match 'Stop-Process'
        $wrapperText | Should -Not -Match '(?i)taskkill(\.exe)?'
        $wrapperText | Should -Not -Match 'TerminateProcess'
    }

    It 'proves 1080 and 1081 unchanged around baseline cleanup' {
        $wrapperText | Should -Match ([regex]::Escape('$script:ProtectedPorts = @(1080,1081)'))
        $wrapperText | Should -Match 'PORT_BASELINE_BEFORE'
        $wrapperText | Should -Match 'PORT_BASELINE_UNCHANGED_AFTER_UI_RECONCILIATION'
        $wrapperText | Should -Match 'BASELINE_RECONCILIATION_CHANGED_PROTECTED_PORTS'
        $wrapperText | Should -Not -Match "Start-EngineAction\s+'RestartTunnel'"
        $wrapperText | Should -Not -Match 'Invoke-PnccPrimary1081Recovery'
    }

    It 'invokes the core runner as a separate Windows PowerShell 5.1 process' {
        $wrapperText | Should -Match 'CoreRunnerPath'
        $wrapperText | Should -Match 'System32\\WindowsPowerShell\\v1\.0\\powershell\.exe'
        $wrapperText | Should -Match 'Start-Process -FilePath \$powerShellExe'
        $wrapperText | Should -Match 'CORE_RUNNER_EXIT'
    }

    It 'grants no runtime or promotion authority' {
        $wrapperText | Should -Match 'runtime_mutation = \$false'
        $wrapperText | Should -Match 'runtime_authority = \$false'
        $wrapperText | Should -Match 'promotion_eligible = \$false'
    }
}
