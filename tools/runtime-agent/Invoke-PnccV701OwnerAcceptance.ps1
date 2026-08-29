#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$CandidateZipPath,
    [Parameter(Mandatory=$true)][string]$CoreRunnerPath,
    [string]$EvidenceDirectory = '',
    [ValidateRange(10,120)][int]$BaselineCleanupTimeoutSeconds = 30
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

$script:WrapperVersion = '1.0.1'
$script:ExpectedCandidateSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'
$script:ExpectedTrayName = 'VPS Control Center'
$script:ExpectedWindowTitlePrefix = 'VPS Control Center v7.'
$script:ExpectedExitMenuText = Convert-CodePointsToString @(0x0417,0x0430,0x043A,0x0440,0x044B,0x0442,0x044C,0x0020,0x0438,0x043D,0x0442,0x0435,0x0440,0x0444,0x0435,0x0439,0x0441,0x0020,0x0028,0x043C,0x0430,0x0440,0x0448,0x0440,0x0443,0x0442,0x0438,0x0437,0x0430,0x0446,0x0438,0x044F,0x0020,0x043E,0x0441,0x0442,0x0430,0x043D,0x0435,0x0442,0x0441,0x044F,0x0029)
$script:HiddenIconsRu1 = Convert-CodePointsToString @(0x041E,0x0442,0x043E,0x0431,0x0440,0x0430,0x0436,0x0430,0x0442,0x044C,0x0020,0x0441,0x043A,0x0440,0x044B,0x0442,0x044B,0x0435,0x0020,0x0437,0x043D,0x0430,0x0447,0x043A,0x0438)
$script:HiddenIconsRu2 = Convert-CodePointsToString @(0x041F,0x043E,0x043A,0x0430,0x0437,0x0430,0x0442,0x044C,0x0020,0x0441,0x043A,0x0440,0x044B,0x0442,0x044B,0x0435,0x0020,0x0437,0x043D,0x0430,0x0447,0x043A,0x0438)
$script:ProtectedPorts = @(1080,1081)
$script:BaselineAutoReconciled = $false
$script:BaselineProcessId = 0
$script:FailureClass = ''
$script:FailureDetail = ''
$script:CoreExitCode = -1
$script:Evidence = New-Object Collections.ArrayList

if (-not $EvidenceDirectory) {
    $parent = Split-Path -Parent ([IO.Path]::GetFullPath($CandidateZipPath))
    $EvidenceDirectory = Join-Path $parent ('PNCC-WU084-OWNER-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
if (-not (Test-Path -LiteralPath $EvidenceDirectory)) {
    New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
}
$script:LogPath = Join-Path $EvidenceDirectory 'baseline-reconciler.log'
$script:ResultPath = Join-Path $EvidenceDirectory 'owner-acceptance-result.json'
$script:PortsBeforePath = Join-Path $EvidenceDirectory 'baseline-ports-before.json'
$script:PortsAfterCleanupPath = Join-Path $EvidenceDirectory 'baseline-ports-after-cleanup.json'
$script:CoreEvidenceDirectory = Join-Path $EvidenceDirectory 'core'

function Write-WrapperLog {
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
    Write-WrapperLog ($Type + ' :: ' + $Detail)
}

function Get-Sha256 {
    param([string]$Path)
    return ([string](Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
}

function Write-JsonUtf8Bom {
    param([string]$Path,$Value,[int]$Depth = 8)
    [IO.File]::WriteAllText($Path,($Value | ConvertTo-Json -Depth $Depth),(New-Object Text.UTF8Encoding($true)))
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
        foreach ($line in @(& netstat.exe -ano -p tcp 2>$null)) {
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

if (-not ('Pncc.Wu084.BaselineNativeWindow' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
namespace Pncc.Wu084 {
    public sealed class BaselineWindowRecord {
        public long Handle { get; set; }
        public string Title { get; set; }
        public bool Visible { get; set; }
    }
    public static class BaselineNativeWindow {
        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
        [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
        [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hWnd);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowTextLength(IntPtr hWnd);
        public static BaselineWindowRecord[] ForProcess(int processId) {
            var rows = new List<BaselineWindowRecord>();
            EnumWindows(delegate(IntPtr hWnd, IntPtr lParam) {
                uint owner;
                GetWindowThreadProcessId(hWnd, out owner);
                if (owner != (uint)processId) return true;
                int len = GetWindowTextLength(hWnd);
                var title = new StringBuilder(Math.Max(len + 1, 2));
                GetWindowText(hWnd, title, title.Capacity);
                rows.Add(new BaselineWindowRecord {
                    Handle = hWnd.ToInt64(),
                    Title = title.ToString(),
                    Visible = IsWindowVisible(hWnd)
                });
                return true;
            }, IntPtr.Zero);
            return rows.ToArray();
        }
    }
    public static class BaselineMouse {
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
            [Pncc.Wu084.BaselineMouse]::LeftClick([int]($rect.Left + ($rect.Width / 2)),[int]($rect.Top + ($rect.Height / 2)))
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

function Get-V7TrayElements {
    $elements = @(Get-UiaElementsByExactName -Name $script:ExpectedTrayName)
    if ($elements.Count -eq 0) {
        [void](Open-HiddenTrayIconsIfAvailable)
        $elements = @(Get-UiaElementsByExactName -Name $script:ExpectedTrayName)
    }
    return @($elements)
}

function Get-ProcessTopLevelWindows {
    param([int]$TargetProcessId)
    return @([Pncc.Wu084.BaselineNativeWindow]::ForProcess($TargetProcessId) | ForEach-Object {
        [pscustomobject]@{
            Handle = [long]$_.Handle
            Title = [string]$_.Title
            Visible = [bool]$_.Visible
        }
    })
}

function Get-ProvenV7UiProcesses {
    $rows = New-Object Collections.ArrayList
    $processes = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.ProcessId -ne $PID -and
        $_.Name -in @('powershell.exe','pwsh.exe') -and
        $_.CommandLine -and
        (($_.CommandLine -match '(?i)VPS-Control-v7-launch\.ps1') -or ($_.CommandLine -match '(?i)VPS-Control-v7\.ps1'))
    })
    foreach ($process in $processes) {
        $windows = @(Get-ProcessTopLevelWindows -TargetProcessId ([int]$process.ProcessId))
        $matchingWindows = @($windows | Where-Object { $_.Title -and $_.Title.StartsWith($script:ExpectedWindowTitlePrefix,[StringComparison]::Ordinal) })
        if ($matchingWindows.Count -eq 0) { continue }
        [void]$rows.Add([pscustomobject]@{
            ProcessId = [int]$process.ProcessId
            Name = [string]$process.Name
            ExecutablePath = [string]$process.ExecutablePath
            CommandLine = [string]$process.CommandLine
            Windows = @($matchingWindows)
        })
    }
    return @($rows)
}

function Wait-ProcessExit {
    param([int]$TargetProcessId,[int]$TimeoutSeconds)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $TargetProcessId -ErrorAction SilentlyContinue)) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return (-not (Get-Process -Id $TargetProcessId -ErrorAction SilentlyContinue))
}

function Invoke-ProductNativeTrayExitForBaseline {
    param($TrayElement)
    if (-not $TrayElement) { throw 'BASELINE_TRAY_ELEMENT_MISSING' }
    $rect = $TrayElement.Current.BoundingRectangle
    if ($rect.Width -le 2 -or $rect.Height -le 2) { throw 'BASELINE_TRAY_ELEMENT_NOT_CLICKABLE' }
    [Pncc.Wu084.BaselineMouse]::RightClick([int]($rect.Left + ($rect.Width / 2)),[int]($rect.Top + ($rect.Height / 2)))
    $deadline = (Get-Date).AddSeconds(10)
    $menuItem = $null
    while ((Get-Date) -lt $deadline -and -not $menuItem) {
        $menuItem = Get-UiaClickableElementByExactName -Name $script:ExpectedExitMenuText
        if (-not $menuItem) { Start-Sleep -Milliseconds 200 }
    }
    if (-not $menuItem) { throw 'BASELINE_PRODUCT_NATIVE_EXIT_MENU_NOT_FOUND' }
    if (-not (Invoke-UiaElement -Element $menuItem)) { throw 'BASELINE_PRODUCT_NATIVE_EXIT_INVOKE_FAILED' }
}

function Assert-OrReconcileV7UiBaseline {
    $trayElements = @(Get-V7TrayElements)
    $provenProcesses = @(Get-ProvenV7UiProcesses)
    Add-EvidenceEvent 'UI_BASELINE_OBSERVED' ('tray=' + $trayElements.Count + '; provenV7Processes=' + $provenProcesses.Count)

    if ($trayElements.Count -eq 0 -and $provenProcesses.Count -eq 0) {
        Add-EvidenceEvent 'UI_BASELINE_CLEAN' 'No pre-existing V7 UI process or tray was observed.'
        return
    }

    if ($trayElements.Count -ne 1 -or $provenProcesses.Count -ne 1) {
        $script:FailureClass = 'DIRTY_UI_BASELINE_UNSAFE'
        throw ('AMBIGUOUS_V7_UI_BASELINE tray=' + $trayElements.Count + '; provenV7Processes=' + $provenProcesses.Count)
    }

    $process = $provenProcesses[0]
    $script:BaselineProcessId = [int]$process.ProcessId
    Add-EvidenceEvent 'BASELINE_AUTO_RECONCILE_AUTHORIZED' ('processId=' + $script:BaselineProcessId + '; processName=' + $process.Name + '; matchingWindowCount=' + @($process.Windows).Count)

    Invoke-ProductNativeTrayExitForBaseline -TrayElement $trayElements[0]
    if (-not (Wait-ProcessExit -TargetProcessId $script:BaselineProcessId -TimeoutSeconds $BaselineCleanupTimeoutSeconds)) {
        $script:FailureClass = 'DIRTY_UI_BASELINE_NATIVE_EXIT_TIMEOUT'
        throw ('PROVEN_V7_UI_DID_NOT_EXIT processId=' + $script:BaselineProcessId)
    }

    $deadline = (Get-Date).AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 250
        $remainingTray = @(Get-V7TrayElements)
        $remainingProcesses = @(Get-ProvenV7UiProcesses)
    } while ((Get-Date) -lt $deadline -and ($remainingTray.Count -gt 0 -or $remainingProcesses.Count -gt 0))

    if ($remainingTray.Count -gt 0 -or $remainingProcesses.Count -gt 0) {
        $script:FailureClass = 'DIRTY_UI_BASELINE_NOT_CLEAN_AFTER_NATIVE_EXIT'
        throw ('V7_UI_BASELINE_REMAINS tray=' + $remainingTray.Count + '; provenV7Processes=' + $remainingProcesses.Count)
    }

    $script:BaselineAutoReconciled = $true
    Add-EvidenceEvent 'BASELINE_AUTO_RECONCILED' ('processId=' + $script:BaselineProcessId + '; method=PRODUCT_NATIVE_TRAY_EXIT')
}

function Quote-ProcessArgument {
    param([string]$Value)
    return '"' + $Value.Replace('"','\"') + '"'
}

$start = Get-Date
$portsBefore = @()
$portsAfterCleanup = @()
$success = $false

try {
    Add-EvidenceEvent 'OWNER_ACCEPTANCE_START' ('wrapperVersion=' + $script:WrapperVersion + '; PS=' + $PSVersionTable.PSVersion)
    if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) { throw 'WINDOWS_POWERSHELL_5_1_REQUIRED' }
    if (-not (Test-Path -LiteralPath $CandidateZipPath -PathType Leaf)) { throw 'CANDIDATE_ZIP_NOT_FOUND' }
    if (-not (Test-Path -LiteralPath $CoreRunnerPath -PathType Leaf)) { throw 'CORE_RUNNER_NOT_FOUND' }

    $candidateSha = Get-Sha256 $CandidateZipPath
    if ($candidateSha -ne $script:ExpectedCandidateSha256) { throw ('CANDIDATE_SHA256_MISMATCH: ' + $candidateSha) }
    Add-EvidenceEvent 'CANDIDATE_VERIFIED' $candidateSha

    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($CoreRunnerPath,[ref]$tokens,[ref]$errors)
    if (@($errors).Count -gt 0) { throw ('CORE_RUNNER_AST_FAIL count=' + @($errors).Count) }
    Add-EvidenceEvent 'CORE_RUNNER_AST_PASS' ([IO.Path]::GetFileName($CoreRunnerPath))

    $portsBefore = @(Get-ProtectedListenerSnapshot)
    Write-JsonUtf8Bom -Path $script:PortsBeforePath -Value $portsBefore -Depth 5
    Add-EvidenceEvent 'PORT_BASELINE_BEFORE' (Get-SnapshotFingerprint $portsBefore)

    Assert-OrReconcileV7UiBaseline

    $portsAfterCleanup = @(Get-ProtectedListenerSnapshot)
    Write-JsonUtf8Bom -Path $script:PortsAfterCleanupPath -Value $portsAfterCleanup -Depth 5
    if ((Get-SnapshotFingerprint $portsBefore) -ne (Get-SnapshotFingerprint $portsAfterCleanup)) {
        $script:FailureClass = 'BASELINE_RECONCILIATION_CHANGED_PROTECTED_PORTS'
        throw '1080_OR_1081_LISTENER_BASELINE_CHANGED_DURING_UI_CLEANUP'
    }
    Add-EvidenceEvent 'PORT_BASELINE_UNCHANGED_AFTER_UI_RECONCILIATION' '1080/1081 exact listener snapshot unchanged.'

    if (-not (Test-Path -LiteralPath $script:CoreEvidenceDirectory)) {
        New-Item -ItemType Directory -Path $script:CoreEvidenceDirectory -Force | Out-Null
    }
    $powerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File ' + (Quote-ProcessArgument $CoreRunnerPath) + ' -CandidateZipPath ' + (Quote-ProcessArgument $CandidateZipPath) + ' -EvidenceDirectory ' + (Quote-ProcessArgument $script:CoreEvidenceDirectory)
    Add-EvidenceEvent 'CORE_RUNNER_START' ('exe=' + $powerShellExe)
    $child = Start-Process -FilePath $powerShellExe -ArgumentList $arguments -Wait -PassThru
    $script:CoreExitCode = [int]$child.ExitCode
    Add-EvidenceEvent 'CORE_RUNNER_EXIT' ('exitCode=' + $script:CoreExitCode)
    $success = ($script:CoreExitCode -eq 0)
    if (-not $success -and -not $script:FailureClass) { $script:FailureClass = 'CORE_ACCEPTANCE_FAILED' }
}
catch {
    if (-not $script:FailureClass) { $script:FailureClass = 'OWNER_ACCEPTANCE_WRAPPER_FAILURE' }
    $script:FailureDetail = $_.Exception.Message
    Add-EvidenceEvent 'FAIL' ($script:FailureClass + ' :: ' + $script:FailureDetail)
}
finally {
    $portsUnchanged = $false
    try {
        if ($portsAfterCleanup.Count -eq 0) { $portsAfterCleanup = @(Get-ProtectedListenerSnapshot) }
        $portsUnchanged = ((Get-SnapshotFingerprint $portsBefore) -eq (Get-SnapshotFingerprint $portsAfterCleanup))
    }
    catch { }
    if (-not $portsUnchanged) { $success = $false }

    $result = [ordered]@{
        schema_version = 1
        contract = 'PNCC_V7_0_1_OWNER_ACCEPTANCE_BASELINE_RECONCILIATION'
        wrapper_version = $script:WrapperVersion
        started_at = $start.ToString('o')
        completed_at = (Get-Date).ToString('o')
        candidate_sha256_expected = $script:ExpectedCandidateSha256
        baseline_auto_reconciled = [bool]$script:BaselineAutoReconciled
        baseline_process_id = [int]$script:BaselineProcessId
        baseline_cleanup_method = $(if ($script:BaselineAutoReconciled) { 'PRODUCT_NATIVE_TRAY_EXIT' } else { 'NONE' })
        ports_1080_1081_unchanged_during_baseline_cleanup = [bool]$portsUnchanged
        core_exit_code = [int]$script:CoreExitCode
        runtime_mutation = $false
        runtime_authority = $false
        promotion_eligible = $false
        success = [bool]$success
        failure_class = $script:FailureClass
        failure_detail = $script:FailureDetail
        evidence = @($script:Evidence)
    }
    try { Write-JsonUtf8Bom -Path $script:ResultPath -Value $result -Depth 10 } catch { }
}

if ($success) {
    Write-WrapperLog 'OWNER_ACCEPTANCE=PASS'
    exit 0
}
Write-WrapperLog ('OWNER_ACCEPTANCE=FAIL class=' + $script:FailureClass + '; coreExit=' + $script:CoreExitCode)
exit 1
