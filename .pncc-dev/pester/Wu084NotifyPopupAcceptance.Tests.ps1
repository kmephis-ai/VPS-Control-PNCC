BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $runnerPath = Join-Path $repoRoot 'tools\runtime-agent\Invoke-PnccV701NotifyPopupAcceptance.ps1'
    $runnerText = [IO.File]::ReadAllText($runnerPath)
    $tokens=$null; $errors=$null
    $ast=[System.Management.Automation.Language.Parser]::ParseFile($runnerPath,[ref]$tokens,[ref]$errors)
}

Describe 'PIPE-WU-084 PID-native NotifyIcon popup acceptance' {
    It 'is Windows PowerShell 5.1 parse-safe' { @($errors).Count | Should -Be 0 }

    It 'does not declare a parameter named Pid' {
        $parameterNames=@($ast.FindAll({param($node)$node -is [System.Management.Automation.Language.ParameterAst]},$true)|ForEach-Object{$_.Name.VariablePath.UserPath})
        @($parameterNames|Where-Object{$_ -ieq 'Pid'}).Count | Should -Be 0
    }

    It 'pins the exact frozen candidate and UI version' {
        $runnerText | Should -Match ([regex]::Escape("RunnerVersion = '1.3.0'"))
        $runnerText | Should -Match ([regex]::Escape("ExpectedCandidateSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'"))
        $runnerText | Should -Match ([regex]::Escape("ExpectedUiVersion = '7.0.1'"))
    }

    It 'does not use Explorer or UI Automation menu identity' {
        $runnerText | Should -Not -Match 'UIAutomationClient|AutomationElement|GetRuntimeId|Shell_TrayWnd|TrayNotifyWnd'
        $runnerText | Should -Match 'explorer_tray_identity_used=\$false'
        $runnerText | Should -Match 'uia_menu_identity_used=\$false'
    }

    It 'proves exact PID-owned main UI and hidden NotifyIcon candidate' {
        $runnerText | Should -Match 'GetWindowThreadProcessId'
        $runnerText | Should -Match 'Wait-ExpectedPidWindow'
        $runnerText | Should -Match 'Get-NotifyNativeCandidates'
        $runnerText | Should -Match "WindowsForms10\\\.Window\\\.0\\\.app"
    }

    It 'pins the NotifyIcon callback message and right-button event' {
        $runnerText | Should -Match '\[uint32\]0x0800'
        $runnerText | Should -Match '\[IntPtr\]0x0205'
        $runnerText | Should -Match "notify_callback_message='WM_USER\+1024 \(0x0800\)'"
        $runnerText | Should -Match "notify_callback_event='WM_RBUTTONUP \(0x0205\)'"
    }

    It 'requires a non-destructive popup proof before exit' {
        $runnerText | Should -Match 'Probe-NotifyPopup'
        $runnerText | Should -Match 'NOTIFY_POPUP_PROBE_PASS'
        $runnerText | Should -Match 'PROBE_POPUP_DID_NOT_CLOSE_ON_ESCAPE'
        $runnerText | Should -Match 'PRODUCT_EXITED_DURING_NONDESTRUCTIVE_POPUP_PROBE'
        $runnerText | Should -Match 'POPUP_PROBE_REQUIRED_BEFORE_EXIT'
    }

    It 'proves the exact frozen product has Exit as the final tray menu item' {
        $runnerText | Should -Match 'Assert-ExitLastItemContract'
        $runnerText | Should -Match 'EXIT_MENU_ITEM_IS_NOT_LAST'
        $runnerText | Should -Match 'EXIT_LAST_ITEM_CONTRACT_PASS'
        $runnerText | Should -Match 'EXIT_LAST_ITEM_CONTRACT_REQUIRED_BEFORE_EXIT'
    }

    It 'selects only the last item of the proven product-owned popup' {
        $runnerText | Should -Match 'Invoke-ExitThroughProvenNotifyPopup'
        $runnerText | Should -Match 'VirtualKey 0x23'
        $runnerText | Should -Match 'VirtualKey 0x0D'
        $runnerText | Should -Match 'PRODUCT_NATIVE_EXIT_KEY_SEQUENCE'
    }

    It 'requires the popup window to be newly visible and owned by exact test PID' {
        $runnerText | Should -Match 'Wait-NewPopupWindow'
        $runnerText | Should -Match 'BaselineVisibleHandles'
        $runnerText | Should -Match 'AMBIGUOUS_NEW_PRODUCT_POPUP_WINDOWS'
        $runnerText | Should -Match 'NOTIFY_CALLBACK_DID_NOT_CREATE_UNIQUE_PRODUCT_POPUP'
    }

    It 'keeps forced termination exact-identity emergency only' {
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
}
