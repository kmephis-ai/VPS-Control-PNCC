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

function Convert-CodePointsToString {
    param([Parameter(Mandatory=$true)][int[]]$CodePoints)
    $builder = New-Object Text.StringBuilder
    foreach ($codePoint in @($CodePoints)) {
        [void]$builder.Append([char]$codePoint)
    }
    return $builder.ToString()
}

$script:RunnerVersion = '1.0.3'
$script:ExpectedCandidateSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'
$script:ExpectedUiVersion = '7.0.1'
$script:ExpectedDemoText = Convert-CodePointsToString @(0x0414,0x0415,0x041C,0x041E)
$script:ExpectedWindowTitle = 'VPS Control Center v7.0.1 ' + [char]0x00B7 + ' ' + $script:ExpectedDemoText
$script:ExpectedTrayName = 'VPS Control Center'
$script:ExpectedExitMenuText = Convert-CodePointsToString @(0x0417,0x0430,0x043A,0x0440,0x044B,0x0442,0x044C,0x0020,0x0438,0x043D,0x0442,0x0435,0x0440,0x0444,0x0435,0x0439,0x0441,0x0020,0x0028,0x043C,0x0430,0x0440,0x0448,0x0440,0x0443,0x0442,0x0438,0x0437,0x0430,0x0446,0x0438,0x044F,0x0020,0x043E,0x0441,0x0442,0x0430,0x043D,0x0435,0x0442,0x0441,0x044F,0x0029)
$script:HiddenIconsRu1 = Convert-CodePointsToString @(0x041E,0x0442,0x043E,0x0431,0x0440,0x0430,0x0436,0x0430,0x0442,0x044C,0x0020,0x0441,0x043A,0x0440,0x044B,0x0442,0x044B,0x0435,0x0020,0x0437,0x043D,0x0430,0x0447,0x043A,0x0438)
$script:HiddenIconsRu2 = Convert-CodePointsToString @(0x041F,0x043E,0x043A,0x0430,0x0437,0x0430,0x0442,0x044C,0x0020,0x0441,0x043A,0x0440,0x044B,0x0442,0x044B,0x0435,0x0020,0x0437,0x043D,0x0430,0x0447,0x043A,0x0438)
$script:ProtectedPorts = @(1080,1081)
$script:ModuleNames = @('OpenAI','GitHub','DevPackages','Firefox','Claude','Gemini','Docker','Telegram','YandexBrowser','Edge','CustomExe','CustomSite')
$script:TestOwnedPid = 0
$script:TestOwnedStartTicksUtc = 0L
$script:TestOwnedExecutablePath = ''
$script:TestOwnedLauncherPath = ''
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

function Write-RunnerLog {
    param([string]$Text)
    $line = ('{0:yyyy-MM-dd HH:mm:ss.fff}  {1}' -f (Get-Date), $Text)
    Write-Host $line
    Add-Content -LiteralPath $script:LogPath -Encoding UTF8 -Value $line
}

function Add-EvidenceEvent {
    param([string]$Type,[string]$Detail)
    [void]$script:Evidence.Add([pscustomobject]@{
        Timestamp = (Get-Date).ToString('o')
        Type = $Type
        Detail = $Detail
    })
    Write-RunnerLog ($Type + ' :: ' + $Detail)
}

function Get-Sha256 {
    param([string]$Path)
    return ([string](Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
}

function Write-JsonUtf8Bom {
    param([string]$Path,$Value,[int]$Depth = 8)
    $json = $Value | ConvertTo-Json -Depth $Depth
    [IO.File]::WriteAllText($Path,$json,(New-Object Text.UTF8Encoding($true)))
}

function Get-ProtectedListenerSnapshot {
    $rows = New-Object Collections.ArrayList
    try {
        $connections = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $script:ProtectedPorts -contains [int]$_.LocalPort })
        foreach ($connection in $connections) {
            [void]$rows.Add([pscustomobject]@{
                LocalAddress = [string]$connection.LocalAddress
                LocalPort = [int]$connection.LocalPort
                OwningProcess = [int]$connection.OwningProcess
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

function Get-SnapshotFingerprint {
    param($Snapshot)
    return (@($Snapshot) | ConvertTo-Json -Depth 5 -Compress)
}

function Assert-PackageManifest {
    param([string]$BaseDir)
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
        if ((Get-Sha256 $path) -ne $expected) { throw ('PACKAGE_HASH_MISMATCH: ' + $relative) }
        $count++
    }
    if ($count -lt 1) { throw 'PACKAGE_MANIFEST_EMPTY' }
    return $count
}

function Assert-PowerShellAst {
    param([string]$BaseDir)
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

function Invoke-FunctionalConsistency {
    param([string]$BaseDir)
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
        [DllImport("user32.dll")] private static extern int GetWindowTextLength(IntPtr hWnd);
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

function Get-PidTopLevelWindows {
    param([int]$Pid)
    return @([Pncc.Wu084.NativeWindow]::ForProcess($Pid) | ForEach-Object {
        [pscustomobject]@{
            Handle = [long]$_.Handle
            Title = [string]$_.Title
            ClassName = [string]$_.ClassName
            Visible = [bool]$_.Visible
        }
    })
}

function Add-WindowSample {
    param([int]$Pid,$Windows,[string]$Reason)
    if ($script:WindowSamples.Count -ge 40) { return }
    [void]$script:WindowSamples.Add([pscustomobject]@{
        Timestamp = (Get-Date).ToString('o')
        Pid = $Pid
        Reason = $Reason
        ProcessAlive = [bool](Get-Process -Id $Pid -ErrorAction SilentlyContinue)
        Windows = @($Windows)
    })
}

function Wait-ExpectedPidWindow {
    param([int]$Pid,[int]$TimeoutSeconds)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastFingerprint = ''
    $lastPeriodic = [datetime]::MinValue
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $Pid -ErrorAction SilentlyContinue)) {
            Add-WindowSample -Pid $Pid -Windows @() -Reason 'PROCESS_EXITED_BEFORE_UI'
            return $null
        }
        $windows = @(Get-PidTopLevelWindows -Pid $Pid)
        $fingerprint = $windows | ConvertTo-Json -Depth 4 -Compress
        $now = Get-Date
        if ($fingerprint -ne $lastFingerprint -or ($now - $lastPeriodic).TotalSeconds -ge 5) {
            $reason = if ($fingerprint -ne $lastFingerprint) { 'WINDOW_SET_CHANGE' } else { 'PERIODIC' }
            Add-WindowSample -Pid $Pid -Windows $windows -Reason $reason
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

function Initialize-Uia {
    Add-Type -AssemblyName UIAutomationClient -ErrorAction Stop
    Add-Type -AssemblyName UIAutomationTypes -ErrorAction Stop
}

function Get-UiaElementsByExactName {
    param([string]$Name)
    Initialize-Uia
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $condition = New-Object -TypeName System.Windows.Automation.PropertyCondition -ArgumentList @([System.Windows.Automation.AutomationElement]::NameProperty,$Name)
    $found = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
    $rows = New-Object Collections.ArrayList
    for ($index = 0; $index -lt $found.Count; $index++) {
        [void]$rows.Add($found.Item($index))
    }
    return @($rows)
}

function Get-UiaClickableElementByExactName {
    param([string]$Name)
    foreach ($element in @(Get-UiaElementsByExactName -Name $Name)) {
        try {
            $rect = $element.Current.BoundingRectangle
            if (-not $element.Current.IsOffscreen -and $rect.Width -gt 2 -and $rect.Height -gt 2) { return $element }
        }
        catch { }
    }
    return $null
}

function Invoke-UiaElement {
    param($Element)
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
    foreach ($name in @($script:HiddenIconsRu1,$script:HiddenIconsRu2,'Show hidden icons')) {
        $button = Get-UiaClickableElementByExactName -Name $name
        if ($button -and (Invoke-UiaElement -Element $button)) {
            Start-Sleep -Milliseconds 700
            return $true
        }
    }
    return $false
}

function Assert-CleanUiBaseline {
    $existingTray = @(Get-UiaElementsByExactName -Name $script:ExpectedTrayName)
    $existingWindow = @(Get-UiaElementsByExactName -Name $script:ExpectedWindowTitle)
    if ($existingTray.Count -eq 0 -and $existingWindow.Count -eq 0) {
        [void](Open-HiddenTrayIconsIfAvailable)
        $existingTray = @(Get-UiaElementsByExactName -Name $script:ExpectedTrayName)
        $existingWindow = @(Get-UiaElementsByExactName -Name $script:ExpectedWindowTitle)
    }
    if ($existingTray.Count -gt 0 -or $existingWindow.Count -gt 0) {
        $script:FailureClass = 'DIRTY_UI_BASELINE'
        throw ('PREEXISTING_VPS_CONTROL_UI_DETECTED tray=' + $existingTray.Count + ' window=' + $existingWindow.Count)
    }
    Add-EvidenceEvent 'UI_BASELINE_CLEAN' 'No pre-existing exact VPS Control Center tray or expected window was observable.'
}

function Invoke-ProductNativeTrayExit {
    Add-EvidenceEvent 'CLEAN_EXIT_BEGIN' ('tray=' + $script:ExpectedTrayName)
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
    Add-EvidenceEvent 'CLEAN_EXIT_ACTION' 'Product tray exit menu item invoked by UI Automation.'
}

function Wait-ProcessExit {
    param([int]$Pid,[int]$TimeoutSeconds)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $Pid -ErrorAction SilentlyContinue)) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return (-not (Get-Process -Id $Pid -ErrorAction SilentlyContinue))
}

function Assert-ExactTestOwnedProcessIdentity {
    param([int]$Pid)
    if ($Pid -le 0 -or $Pid -ne $script:TestOwnedPid) { throw 'TEST_OWNED_PID_GUARD_REJECTED' }
    $process = Get-Process -Id $Pid -ErrorAction SilentlyContinue
    if (-not $process) { return $false }
    if ($process.StartTime.ToUniversalTime().Ticks -ne $script:TestOwnedStartTicksUtc) { throw 'TEST_OWNED_CREATION_TIME_MISMATCH' }
    $cim = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $Pid) -ErrorAction Stop
    if (-not $cim) { throw 'TEST_OWNED_CIM_IDENTITY_MISSING' }
    if (-not [string]::Equals([string]$cim.ExecutablePath,$script:TestOwnedExecutablePath,[StringComparison]::OrdinalIgnoreCase)) { throw 'TEST_OWNED_EXECUTABLE_PATH_MISMATCH' }
    if (-not ([string]$cim.CommandLine).Contains($script:TestOwnedLauncherPath)) { throw 'TEST_OWNED_COMMAND_MARKER_MISSING' }
    if (-not ([string]$cim.CommandLine).Contains('-Demo')) { throw 'TEST_OWNED_DEMO_MARKER_MISSING' }
    return $true
}

function Stop-ExactTestOwnedProcessEmergency {
    param([int]$Pid)
    if (-not (Assert-ExactTestOwnedProcessIdentity -Pid $Pid)) { return $true }
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
$success = $false

try {
    Add-EvidenceEvent 'RUNNER_START' ('version=' + $script:RunnerVersion + '; PS=' + $PSVersionTable.PSVersion)
    if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) { throw 'WINDOWS_POWERSHELL_5_1_REQUIRED' }
    if (-not (Test-Path -LiteralPath $CandidateZipPath -PathType Leaf)) { throw 'CANDIDATE_ZIP_NOT_FOUND' }

    $candidateSha = Get-Sha256 $CandidateZipPath
    if ($candidateSha -ne $script:ExpectedCandidateSha256) { throw ('CANDIDATE_SHA256_MISMATCH: ' + $candidateSha) }
    Add-EvidenceEvent 'CANDIDATE_VERIFIED' $candidateSha

    $portsBefore = @(Get-ProtectedListenerSnapshot)
    Write-JsonUtf8Bom -Path $script:PortsBeforePath -Value $portsBefore -Depth 5
    Add-EvidenceEvent 'PORT_BASELINE_BEFORE' (Get-SnapshotFingerprint $portsBefore)

    Assert-CleanUiBaseline

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
    $productProcess.Refresh()
    $script:TestOwnedPid = [int]$productProcess.Id
    $script:TestOwnedStartTicksUtc = [long]$productProcess.StartTime.ToUniversalTime().Ticks
    $script:TestOwnedExecutablePath = $powerShellExe
    $script:TestOwnedLauncherPath = $launcherPath
    $script:CleanupMode = 'PRODUCT_NATIVE_TRAY_EXIT_PENDING'
    Add-EvidenceEvent 'PRODUCT_STARTED' ('pid=' + $script:TestOwnedPid + '; startTicksUtc=' + $script:TestOwnedStartTicksUtc)

    $window = Wait-ExpectedPidWindow -Pid $script:TestOwnedPid -TimeoutSeconds $WindowTimeoutSeconds
    if (-not $window) {
        $script:FailureClass = 'OWNER_RUNNER_ACCEPTANCE_DEFECT / UI_WINDOW_NOT_OBSERVED'
        throw 'EXPECTED_PID_OWNED_VISIBLE_WINDOW_NOT_OBSERVED'
    }
    $script:UiObserved = $true
    Add-EvidenceEvent 'EXPECTED_UI_OBSERVED' ('pid=' + $script:TestOwnedPid + '; hwnd=' + $window.Handle)

    Invoke-ProductNativeTrayExit
    if (-not (Wait-ProcessExit -Pid $script:TestOwnedPid -TimeoutSeconds $CleanExitTimeoutSeconds)) {
        $script:FailureClass = 'OWNER_RUNNER_ACCEPTANCE_DEFECT / CLEAN_EXIT_TIMEOUT'
        throw 'PRODUCT_NATIVE_TRAY_EXIT_DID_NOT_TERMINATE_PROCESS'
    }
    $script:CleanExit = $true
    $script:CleanupMode = 'PRODUCT_NATIVE_TRAY_EXIT'
    Add-EvidenceEvent 'CLEAN_EXIT_PASS' ('pid=' + $script:TestOwnedPid)

    $portsAfter = @(Get-ProtectedListenerSnapshot)
    Write-JsonUtf8Bom -Path $script:PortsAfterPath -Value $portsAfter -Depth 5
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
        if ($script:WindowSamples.Count -gt 0) { Write-JsonUtf8Bom -Path $script:WindowEvidencePath -Value $script:WindowSamples -Depth 8 }
    }
    catch { }

    $stillRunning = $false
    if ($script:TestOwnedPid -gt 0) { $stillRunning = [bool](Get-Process -Id $script:TestOwnedPid -ErrorAction SilentlyContinue) }
    if ($stillRunning) {
        try {
            [void](Stop-ExactTestOwnedProcessEmergency -Pid $script:TestOwnedPid)
            $script:CleanupMode = 'FORCED_EXACT_IDENTITY_TEST_OWNED_PROCESS_ONLY'
            $script:CleanExit = $false
            $success = $false
            if (-not $script:FailureClass) { $script:FailureClass = 'OWNER_RUNNER_ACCEPTANCE_DEFECT / EMERGENCY_CLEANUP_REQUIRED' }
            Add-EvidenceEvent 'EMERGENCY_CLEANUP' ('exact identity test-owned pid=' + $script:TestOwnedPid)
        }
        catch {
            $script:CleanupMode = 'EMERGENCY_CLEANUP_BLOCKED_OR_FAILED'
            $script:CleanExit = $false
            $success = $false
            if (-not $script:FailureClass) { $script:FailureClass = 'EMERGENCY_CLEANUP_FAILURE' }
            Add-EvidenceEvent 'EMERGENCY_CLEANUP_FAIL' $_.Exception.Message
        }
    }

    try {
        if ($portsAfter.Count -eq 0) {
            $portsAfter = @(Get-ProtectedListenerSnapshot)
            Write-JsonUtf8Bom -Path $script:PortsAfterPath -Value $portsAfter -Depth 5
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
        schema_version = 2
        contract = 'PNCC_V7_0_1_PHYSICAL_CLEAN_STARTUP_V2'
        runner_version = $script:RunnerVersion
        started_at = $start.ToString('o')
        completed_at = (Get-Date).ToString('o')
        candidate_sha256_expected = $script:ExpectedCandidateSha256
        expected_window_title_codepoint_safe = $true
        package_manifest_entries = $packageManifestCount
        powershell_ast_files = $astCount
        functional_consistency_checks = $(if ($consistency) { [int]$consistency.Summary.Checks } else { 0 })
        functional_consistency_passed = $(if ($consistency) { [int]$consistency.Summary.Passed } else { 0 })
        test_process_pid = $script:TestOwnedPid
        test_process_identity_guard = 'pid+creation_time+executable_path+launcher_marker+demo_marker'
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
    try { Write-JsonUtf8Bom -Path $script:ResultPath -Value $result -Depth 10 } catch { }
    try { if (Test-Path -LiteralPath $workRoot) { Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue } } catch { }
}

if ($success) {
    Write-RunnerLog 'WU084_ACCEPTANCE=PASS ui_observed=true clean_exit=true ports_unchanged=true'
    exit 0
}
Write-RunnerLog ('WU084_ACCEPTANCE=FAIL class=' + $script:FailureClass + ' cleanup=' + $script:CleanupMode)
exit 1
