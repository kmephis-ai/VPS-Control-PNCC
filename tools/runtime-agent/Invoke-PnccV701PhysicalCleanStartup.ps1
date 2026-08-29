#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$CandidateZipPath,
    [string]$EvidenceDirectory = '',
    [ValidateRange(15,180)][int]$WindowTimeoutSeconds = 90,
    [ValidateRange(10,120)][int]$CleanExitTimeoutSeconds = 30
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$script:RunnerVersion = '1.0.2'
$script:ExpectedCandidateSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'
$script:ExpectedUiVersion = '7.0.1'
$script:ExpectedWindowTitle = 'VPS Control Center v7.0.1 · ДЕМО'
$script:ExpectedTrayName = 'VPS Control Center'
$script:ExpectedExitMenuText = 'Закрыть интерфейс (маршрутизация останется)'
$script:ProtectedPorts = @(1080,1081)
$script:ModuleNames = @('OpenAI','GitHub','DevPackages','Firefox','Claude','Gemini','Docker','Telegram','YandexBrowser','Edge','CustomExe','CustomSite')
$script:TestOwnedPid = 0
$script:Evidence = New-Object Collections.ArrayList
$script:WindowSamples = New-Object Collections.ArrayList
$script:CleanupMode = 'NOT_STARTED'
$script:CleanExit = $false
$script:UiObserved = $false
$script:FailureClass = ''
$script:FailureDetail = ''

if (-not $EvidenceDirectory) {
    $parent = Split-Path -Parent ([IO.Path]::GetFullPath($CandidateZipPath))
    $EvidenceDirectory = Join-Path $parent ('PNCC-WU084-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
if (-not (Test-Path -LiteralPath $EvidenceDirectory)) {
    New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
}
$script:LogPath = Join-Path $EvidenceDirectory 'PNCC-WU084.log'
$script:ResultPath = Join-Path $EvidenceDirectory 'wu084-physical-clean-startup-result.json'
$script:WindowEvidencePath = Join-Path $EvidenceDirectory 'pid-window-samples.json'
$script:PortsBeforePath = Join-Path $EvidenceDirectory 'ports-before.json'
$script:PortsAfterPath = Join-Path $EvidenceDirectory 'ports-after.json'

function Write-RunnerLog([string]$Text) {
    $line = ('{0:yyyy-MM-dd HH:mm:ss.fff}  {1}' -f (Get-Date), $Text)
    Write-Host $line
    Add-Content -LiteralPath $script:LogPath -Encoding UTF8 -Value $line
}

function Add-EvidenceEvent([string]$Type,[string]$Detail) {
    [void]$script:Evidence.Add([pscustomobject]@{
        Timestamp = (Get-Date).ToString('o')
        Type = $Type
        Detail = $Detail
    })
    Write-RunnerLog ($Type + ' :: ' + $Detail)
}

function Get-Sha256([string]$Path) {
    return ([string](Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
}

function Get-ProtectedListenerSnapshot {
    $rows = New-Object Collections.ArrayList
    try {
        $connections = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $script:ProtectedPorts -contains [int]$_.LocalPort })
        foreach ($c in $connections) {
            [void]$rows.Add([pscustomobject]@{
                LocalAddress = [string]$c.LocalAddress
                LocalPort = [int]$c.LocalPort
                OwningProcess = [int]$c.OwningProcess
            })
        }
    }
    catch {
        $netstat = @(& netstat.exe -ano -p tcp 2>$null)
        foreach ($line in $netstat) {
            if ($line -notmatch '^\s*TCP\s+(\S+):(1080|1081)\s+\S+\s+LISTENING\s+(\d+)\s*$') { continue }
            [void]$rows.Add([pscustomobject]@{
                LocalAddress = [string]$Matches[1]
                LocalPort = [int]$Matches[2]
                OwningProcess = [int]$Matches[3]
            })
        }
    }
    return @($rows | Sort-Object LocalPort,LocalAddress,OwningProcess)
}

function Get-SnapshotFingerprint($Snapshot) {
    return (@($Snapshot) | ConvertTo-Json -Depth 5 -Compress)
}

function Assert-PackageManifest([string]$BaseDir) {
    $manifest = Join-Path $BaseDir 'VPS-Control-v7-SHA256.txt'
    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw 'PACKAGE_MANIFEST_MISSING' }
    $count = 0
    foreach ($line in Get-Content -LiteralPath $manifest -ErrorAction Stop) {
        if (-not $line -or $line.TrimStart().StartsWith('#')) { continue }
        if ($line -notmatch '^([0-9a-fA-F]{64})\s+(.+)$') { throw ('PACKAGE_MANIFEST_INVALID_LINE: ' + $line) }
        $expected = $Matches[1].ToLowerInvariant()
        $relative = $Matches[2].Trim()
        $path = Join-Path $BaseDir $relative
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('PACKAGE_FILE_MISSING: ' + $relative) }
        $actual = Get-Sha256 $path
        if ($actual -ne $expected) { throw ('PACKAGE_HASH_MISMATCH: ' + $relative) }
        $count++
    }
    if ($count -lt 1) { throw 'PACKAGE_MANIFEST_EMPTY' }
    return $count
}

function Assert-PowerShellAst([string]$BaseDir) {
    $files = @(Get-ChildItem -LiteralPath $BaseDir -Recurse -Filter '*.ps1' -File -ErrorAction Stop | Sort-Object FullName)
    if ($files.Count -lt 1) { throw 'NO_POWERSHELL_FILES' }
    foreach ($file in $files) {
        $tokens = $null
        $errors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors)
        if (@($errors).Count -gt 0) {
            $detail = (@($errors) | ForEach-Object { 'line ' + $_.Extent.StartLineNumber + ': ' + $_.Message }) -join '; '
            throw ('POWERSHELL_AST_FAIL: ' + $file.Name + ' :: ' + $detail)
        }
    }
    return $files.Count
}

function Invoke-FunctionalConsistency([string]$BaseDir) {
    $module = Join-Path $BaseDir 'modules\V7-Consistency.ps1'
    if (-not (Test-Path -LiteralPath $module -PathType Leaf)) { throw 'V7_CONSISTENCY_MODULE_MISSING' }
    . $module
    $result = Test-V7FunctionalConsistency -BaseDir $BaseDir -UiVersion $script:ExpectedUiVersion -ModuleNames $script:ModuleNames
    if (-not $result -or -not [bool]$result.Ok) {
        $errors = if ($result) { @($result.Errors) -join '; ' } else { 'NO_RESULT' }
        throw ('FUNCTIONAL_CONSISTENCY_FAIL: ' + $errors)
    }
    if ([int]$result.Summary.Checks -ne 203 -or [int]$result.Summary.Passed -ne 203) {
        throw ('FUNCTIONAL_CONSISTENCY_UNEXPECTED_COUNT: checks=' + $result.Summary.Checks + ' passed=' + $result.Summary.Passed)
    }
    return $result
}

if (-not ('Pncc.Wu084.NativeWindow' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
namespace Pncc.Wu084 {
    public sealed class WindowRecord {
        public long Handle { get; set; }
        public string Title { get; set; }
        public string ClassName { get; set; }
        public bool Visible { get; set; }
    }
    public static class NativeWindow {
        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
        [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
        [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hWnd);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowTextLength(IntPtr hWnd);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetClassName(IntPtr hWnd, StringBuilder className, int maxCount);
        public static WindowRecord[] ForProcess(int pid) {
            var rows = new List<WindowRecord>();
            EnumWindows(delegate(IntPtr hWnd, IntPtr lParam) {
                uint owner;
                GetWindowThreadProcessId(hWnd, out owner);
                if (owner != (uint)pid) return true;
                int len = GetWindowTextLength(hWnd);
                var title = new StringBuilder(Math.Max(len + 1, 2));
                GetWindowText(hWnd, title, title.Capacity);
                var cls = new StringBuilder(256);
                GetClassName(hWnd, cls, cls.Capacity);
                rows.Add(new WindowRecord {
                    Handle = hWnd.ToInt64(),
                    Title = title.ToString(),
                    ClassName = cls.ToString(),
                    Visible = IsWindowVisible(hWnd)
                });
                return true;
            }, IntPtr.Zero);
            return rows.ToArray();
        }
    }
    public static class Mouse {
        [DllImport("user32.dll")] private static extern bool SetCursorPos(int X, int Y);
        [DllImport("user32.dll")] private static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);
        public static void RightClick(int x, int y) {
            SetCursorPos(x, y);
            mouse_event(0x0008, 0, 0, 0, UIntPtr.Zero);
            mouse_event(0x0010, 0, 0, 0, UIntPtr.Zero);
        }
        public static void LeftClick(int x, int y) {
            SetCursorPos(x, y);
            mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero);
            mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero);
        }
    }
}
'@
}

function Get-PidTopLevelWindows([int]$Pid) {
    return @([Pncc.Wu084.NativeWindow]::ForProcess($Pid) | ForEach-Object {
        [pscustomobject]@{
            Handle = [long]$_.Handle
            Title = [string]$_.Title
            ClassName = [string]$_.ClassName
            Visible = [bool]$_.Visible
        }
    })
}

function Add-WindowSample([int]$Pid,$Windows,[string]$Reason) {
    if ($script:WindowSamples.Count -ge 40) { return }
    [void]$script:WindowSamples.Add([pscustomobject]@{
        Timestamp = (Get-Date).ToString('o')
        Pid = $Pid
        Reason = $Reason
        ProcessAlive = [bool](Get-Process -Id $Pid -ErrorAction SilentlyContinue)
        Windows = @($Windows)
    })
}

function Wait-ExpectedPidWindow([int]$Pid,[int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastFingerprint = ''
    $lastPeriodic = [datetime]::MinValue
    while ((Get-Date) -lt $deadline) {
        $proc = Get-Process -Id $Pid -ErrorAction SilentlyContinue
        if (-not $proc) {
            Add-WindowSample -Pid $Pid -Windows @() -Reason 'PROCESS_EXITED_BEFORE_UI'
            return $null
        }
        $windows = @(Get-PidTopLevelWindows -Pid $Pid)
        $fingerprint = ($windows | ConvertTo-Json -Depth 4 -Compress)
        $now = Get-Date
        if ($fingerprint -ne $lastFingerprint -or ($now - $lastPeriodic).TotalSeconds -ge 5) {
            Add-WindowSample -Pid $Pid -Windows $windows -Reason $(if ($fingerprint -ne $lastFingerprint) { 'WINDOW_SET_CHANGE' } else { 'PERIODIC' })
            $lastFingerprint = $fingerprint
            $lastPeriodic = $now
        }
        foreach ($window in $windows) {
            if ($window.Visible -and [string]::Equals([string]$window.Title,$script:ExpectedWindowTitle,[StringComparison]::Ordinal)) {
                Add-WindowSample -Pid $Pid -Windows $windows -Reason 'EXPECTED_VISIBLE_WINDOW'
                return $window
            }
        }
        Start-Sleep -Milliseconds 350
    }
    Add-WindowSample -Pid $Pid -Windows @(Get-PidTopLevelWindows -Pid $Pid) -Reason 'WINDOW_TIMEOUT'
    return $null
}

function Get-UiaElementsByExactName([string]$Name) {
    Add-Type -AssemblyName UIAutomationClient -ErrorAction Stop
    Add-Type -AssemblyName UIAutomationTypes -ErrorAction Stop
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$Name)
    return @($root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition))
}

function Get-UiaClickableElementByExactName([string]$Name) {
    foreach ($element in @(Get-UiaElementsByExactName -Name $Name)) {
        try {
            $rect = $element.Current.BoundingRectangle
            if (-not $element.Current.IsOffscreen -and $rect.Width -gt 2 -and $rect.Height -gt 2) { return $element }
        }
        catch { }
    }
    return $null
}

function Invoke-UiaElement($Element) {
    if (-not $Element) { return $false }
    try {
        $pattern = $Element.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
        if ($pattern) {
            ([System.Windows.Automation.InvokePattern]$pattern).Invoke()
            return $true
        }
    }
    catch { }
    try {
        $rect = $Element.Current.BoundingRectangle
        if ($rect.Width -gt 2 -and $rect.Height -gt 2) {
            [Pncc.Wu084.Mouse]::LeftClick([int]($rect.Left + ($rect.Width / 2)),[int]($rect.Top + ($rect.Height / 2)))
            return $true
        }
    }
    catch { }
    return $false
}

function Open-HiddenTrayIconsIfAvailable {
    foreach ($name in @('Отображать скрытые значки','Показать скрытые значки','Show hidden icons')) {
        $button = Get-UiaClickableElementByExactName -Name $name
        if ($button -and (Invoke-UiaElement -Element $button)) {
            Start-Sleep -Milliseconds 700
            return $true
        }
    }
    return $false
}

function Invoke-ProductNativeTrayExit {
    Add-EvidenceEvent 'CLEAN_EXIT_BEGIN' ('tray=' + $script:ExpectedTrayName + '; menu=' + $script:ExpectedExitMenuText)
    $trayElement = Get-UiaClickableElementByExactName -Name $script:ExpectedTrayName
    if (-not $trayElement) {
        [void](Open-HiddenTrayIconsIfAvailable)
        $trayElement = Get-UiaClickableElementByExactName -Name $script:ExpectedTrayName
    }
    if (-not $trayElement) { throw 'TRAY_ICON_NOT_FOUND_BY_UIA' }

    $rect = $trayElement.Current.BoundingRectangle
    [Pncc.Wu084.Mouse]::RightClick([int]($rect.Left + ($rect.Width / 2)),[int]($rect.Top + ($rect.Height / 2)))

    $deadline = (Get-Date).AddSeconds(10)
    $menuItem = $null
    while ((Get-Date) -lt $deadline -and -not $menuItem) {
        $menuItem = Get-UiaClickableElementByExactName -Name $script:ExpectedExitMenuText
        if (-not $menuItem) { Start-Sleep -Milliseconds 200 }
    }
    if (-not $menuItem) { throw 'TRAY_EXIT_MENU_ITEM_NOT_FOUND_BY_UIA' }
    if (-not (Invoke-UiaElement -Element $menuItem)) { throw 'TRAY_EXIT_MENU_ITEM_INVOKE_FAILED' }
    Add-EvidenceEvent 'CLEAN_EXIT_ACTION' 'Product tray Exit menu item invoked by UI Automation.'
}

function Wait-ProcessExit([int]$Pid,[int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $Pid -ErrorAction SilentlyContinue)) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return (-not (Get-Process -Id $Pid -ErrorAction SilentlyContinue))
}

function Stop-ExactTestOwnedProcessEmergency([int]$Pid) {
    if ($Pid -le 0 -or $Pid -ne $script:TestOwnedPid) { throw 'EMERGENCY_CLEANUP_PID_GUARD_REJECTED' }
    $proc = Get-Process -Id $Pid -ErrorAction SilentlyContinue
    if (-not $proc) { return $true }
    if ([string]$proc.ProcessName -notin @('powershell','pwsh')) { throw ('EMERGENCY_CLEANUP_PROCESS_IDENTITY_REJECTED: ' + $proc.ProcessName) }
    Stop-Process -Id $script:TestOwnedPid -Force -ErrorAction Stop
    return (Wait-ProcessExit -Pid $Pid -TimeoutSeconds 10)
}

$start = Get-Date
$workRoot = Join-Path $env:TEMP ('PNCC-WU084-' + [guid]::NewGuid().ToString('N'))
$extractRoot = Join-Path $workRoot 'candidate'
$portsBefore = @()
$portsAfter = @()
$consistency = $null
$packageManifestCount = 0
$astCount = 0
$productProcess = $null
$success = $false

try {
    Add-EvidenceEvent 'RUNNER_START' ('version=' + $script:RunnerVersion + '; PS=' + $PSVersionTable.PSVersion)
    if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) { throw 'WINDOWS_POWERSHELL_5_1_REQUIRED' }
    if (-not (Test-Path -LiteralPath $CandidateZipPath -PathType Leaf)) { throw 'CANDIDATE_ZIP_NOT_FOUND' }

    $candidateSha = Get-Sha256 $CandidateZipPath
    if ($candidateSha -ne $script:ExpectedCandidateSha256) { throw ('CANDIDATE_SHA256_MISMATCH: ' + $candidateSha) }
    Add-EvidenceEvent 'CANDIDATE_VERIFIED' $candidateSha

    $portsBefore = @(Get-ProtectedListenerSnapshot)
    [IO.File]::WriteAllText($script:PortsBeforePath,($portsBefore | ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding($true)))
    Add-EvidenceEvent 'PORT_BASELINE_BEFORE' (Get-SnapshotFingerprint $portsBefore)

    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
    Expand-Archive -LiteralPath $CandidateZipPath -DestinationPath $extractRoot -Force
    $launchers = @(Get-ChildItem -LiteralPath $extractRoot -Recurse -Filter 'VPS-Control-v7-launch.ps1' -File -ErrorAction Stop)
    if ($launchers.Count -ne 1) { throw ('EXPECTED_ONE_LAUNCHER_GOT_' + $launchers.Count) }
    $baseDir = Split-Path -Parent $launchers[0].FullName
    Add-EvidenceEvent 'FRESH_EXTRACT_PASS' ('base=' + $baseDir)

    $packageManifestCount = Assert-PackageManifest -BaseDir $baseDir
    Add-EvidenceEvent 'PACKAGE_MANIFEST_PASS' ('entries=' + $packageManifestCount)

    $astCount = Assert-PowerShellAst -BaseDir $baseDir
    Add-EvidenceEvent 'POWERSHELL_AST_PASS' ('files=' + $astCount)

    $consistency = Invoke-FunctionalConsistency -BaseDir $baseDir
    Add-EvidenceEvent 'FUNCTIONAL_CONSISTENCY_PASS' ('checks=' + $consistency.Summary.Checks + '; passed=' + $consistency.Summary.Passed)

    $powerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $launcherPath = Join-Path $baseDir 'VPS-Control-v7-launch.ps1'
    $arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -STA -File "' + $launcherPath + '" -Demo'
    $productProcess = Start-Process -FilePath $powerShellExe -ArgumentList $arguments -WorkingDirectory $baseDir -PassThru
    $script:TestOwnedPid = [int]$productProcess.Id
    $script:CleanupMode = 'PRODUCT_NATIVE_TRAY_EXIT_PENDING'
    Add-EvidenceEvent 'PRODUCT_STARTED' ('pid=' + $script:TestOwnedPid)

    $window = Wait-ExpectedPidWindow -Pid $script:TestOwnedPid -TimeoutSeconds $WindowTimeoutSeconds
    if (-not $window) {
        $script:FailureClass = 'OWNER_RUNNER_ACCEPTANCE_DEFECT / UI_WINDOW_NOT_OBSERVED'
        throw ('EXPECTED_PID_OWNED_VISIBLE_WINDOW_NOT_OBSERVED: ' + $script:ExpectedWindowTitle)
    }
    $script:UiObserved = $true
    Add-EvidenceEvent 'EXPECTED_UI_OBSERVED' ('pid=' + $script:TestOwnedPid + '; hwnd=' + $window.Handle + '; title=' + $window.Title)

    Invoke-ProductNativeTrayExit
    if (-not (Wait-ProcessExit -Pid $script:TestOwnedPid -TimeoutSeconds $CleanExitTimeoutSeconds)) {
        $script:FailureClass = 'OWNER_RUNNER_ACCEPTANCE_DEFECT / CLEAN_EXIT_TIMEOUT'
        throw 'PRODUCT_NATIVE_TRAY_EXIT_DID_NOT_TERMINATE_PROCESS'
    }
    $script:CleanExit = $true
    $script:CleanupMode = 'PRODUCT_NATIVE_TRAY_EXIT'
    Add-EvidenceEvent 'CLEAN_EXIT_PASS' ('pid=' + $script:TestOwnedPid)

    $portsAfter = @(Get-ProtectedListenerSnapshot)
    [IO.File]::WriteAllText($script:PortsAfterPath,($portsAfter | ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding($true)))
    if ((Get-SnapshotFingerprint $portsBefore) -ne (Get-SnapshotFingerprint $portsAfter)) {
        $script:FailureClass = 'RUNTIME_BASELINE_CHANGED'
        throw 'PROTECTED_PORT_BASELINE_CHANGED'
    }
    Add-EvidenceEvent 'PORT_BASELINE_UNCHANGED' '1080/1081 exact listener snapshot unchanged.'
    $success = $true
}
catch {
    if (-not $script:FailureClass) { $script:FailureClass = 'RUNNER_OR_ENVIRONMENT_FAILURE' }
    $script:FailureDetail = $_.Exception.Message
    Add-EvidenceEvent 'FAIL' ($script:FailureClass + ' :: ' + $script:FailureDetail)
}
finally {
    try {
        if ($script:WindowSamples.Count -gt 0) {
            [IO.File]::WriteAllText($script:WindowEvidencePath,($script:WindowSamples | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($true)))
        }
    }
    catch { }

    $stillRunning = $false
    if ($script:TestOwnedPid -gt 0) { $stillRunning = [bool](Get-Process -Id $script:TestOwnedPid -ErrorAction SilentlyContinue) }
    if ($stillRunning) {
        try {
            [void](Stop-ExactTestOwnedProcessEmergency -Pid $script:TestOwnedPid)
            $script:CleanupMode = 'FORCED_TEST_OWNED_PROCESS_ONLY'
            $script:CleanExit = $false
            $success = $false
            if (-not $script:FailureClass) { $script:FailureClass = 'OWNER_RUNNER_ACCEPTANCE_DEFECT / EMERGENCY_CLEANUP_REQUIRED' }
            Add-EvidenceEvent 'EMERGENCY_CLEANUP' ('exact test-owned pid=' + $script:TestOwnedPid)
        }
        catch {
            $script:CleanupMode = 'EMERGENCY_CLEANUP_FAILED'
            $script:CleanExit = $false
            $success = $false
            if (-not $script:FailureClass) { $script:FailureClass = 'EMERGENCY_CLEANUP_FAILURE' }
            Add-EvidenceEvent 'EMERGENCY_CLEANUP_FAIL' $_.Exception.Message
        }
    }

    try {
        if ($portsAfter.Count -eq 0) {
            $portsAfter = @(Get-ProtectedListenerSnapshot)
            [IO.File]::WriteAllText($script:PortsAfterPath,($portsAfter | ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding($true)))
        }
    }
    catch { }

    $portsUnchanged = $false
    try { $portsUnchanged = ((Get-SnapshotFingerprint $portsBefore) -eq (Get-SnapshotFingerprint $portsAfter)) } catch { }
    if (-not $portsUnchanged) {
        $success = $false
        if (-not $script:FailureClass) { $script:FailureClass = 'RUNTIME_BASELINE_CHANGED' }
    }
    if (-not $script:CleanExit) { $success = $false }

    $result = [ordered]@{
        schema_version = 1
        contract = 'PNCC_V7_0_1_PHYSICAL_CLEAN_STARTUP_V2'
        runner_version = $script:RunnerVersion
        started_at = $start.ToString('o')
        completed_at = (Get-Date).ToString('o')
        candidate_sha256_expected = $script:ExpectedCandidateSha256
        expected_window_title = $script:ExpectedWindowTitle
        package_manifest_entries = $packageManifestCount
        powershell_ast_files = $astCount
        functional_consistency_checks = $(if ($consistency) { [int]$consistency.Summary.Checks } else { 0 })
        functional_consistency_passed = $(if ($consistency) { [int]$consistency.Summary.Passed } else { 0 })
        test_process_pid = $script:TestOwnedPid
        ui_observed = [bool]$script:UiObserved
        clean_exit = [bool]$script:CleanExit
        cleanup_mode = $script:CleanupMode
        reserve_1080_unchanged = [bool]$portsUnchanged
        primary_1081_unchanged = [bool]$portsUnchanged
        ports_1080_1081_unchanged = [bool]$portsUnchanged
        runtime_mutation = $false
        runtime_authority = $false
        promotion_eligible = $false
        release_or_tag_authorized = $false
        success = [bool]$success
        failure_class = $script:FailureClass
        failure_detail = $script:FailureDetail
        evidence = @($script:Evidence)
    }
    try { [IO.File]::WriteAllText($script:ResultPath,($result | ConvertTo-Json -Depth 10),(New-Object Text.UTF8Encoding($true))) } catch { }
    try { if (Test-Path -LiteralPath $workRoot) { Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue } } catch { }
}

if ($success) {
    Write-RunnerLog 'WU084_ACCEPTANCE=PASS ui_observed=true clean_exit=true ports_unchanged=true'
    exit 0
}
Write-RunnerLog ('WU084_ACCEPTANCE=FAIL class=' + $script:FailureClass + ' cleanup=' + $script:CleanupMode)
exit 1
