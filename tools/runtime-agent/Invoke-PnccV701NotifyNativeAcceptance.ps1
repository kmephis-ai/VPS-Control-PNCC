#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$CandidateZipPath,
    [string]$EvidenceDirectory = '',
    [ValidateRange(15,180)][int]$WindowTimeoutSeconds = 90,
    [ValidateRange(5,60)][int]$MenuTimeoutSeconds = 15,
    [ValidateRange(10,120)][int]$CleanExitTimeoutSeconds = 30
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Convert-CodePointsToString {
    param([Parameter(Mandatory=$true)][int[]]$CodePoints)
    $b = New-Object Text.StringBuilder
    foreach ($cp in @($CodePoints)) { [void]$b.Append([char]$cp) }
    return $b.ToString()
}

$script:RunnerVersion = '1.2.0'
$script:ExpectedCandidateSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'
$script:ExpectedUiVersion = '7.0.1'
$script:ExpectedDemoText = Convert-CodePointsToString @(0x0414,0x0415,0x041C,0x041E)
$script:ExpectedWindowTitle = 'VPS Control Center v7.0.1 ' + [char]0x00B7 + ' ' + $script:ExpectedDemoText
$script:ExpectedExitMenuText = Convert-CodePointsToString @(0x0417,0x0430,0x043A,0x0440,0x044B,0x0442,0x044C,0x0020,0x0438,0x043D,0x0442,0x0435,0x0440,0x0444,0x0435,0x0439,0x0441,0x0020,0x0028,0x043C,0x0430,0x0440,0x0448,0x0440,0x0443,0x0442,0x0438,0x0437,0x0430,0x0446,0x0438,0x044F,0x0020,0x043E,0x0441,0x0442,0x0430,0x043D,0x0435,0x0442,0x0441,0x044F,0x0029)
$script:ProtectedPorts = @(1080,1081)
$script:ModuleNames = @('OpenAI','GitHub','DevPackages','Firefox','Claude','Gemini','Docker','Telegram','YandexBrowser','Edge','CustomExe','CustomSite')
$script:WmTrayMouseMessage = 0x0800
$script:WmRButtonUp = 0x0205
$script:TestOwnedProcessId = 0
$script:TestOwnedStartTicksUtc = 0L
$script:TestOwnedExecutablePath = ''
$script:TestOwnedLauncherPath = ''
$script:ProductBaseDir = ''
$script:NotifyWindowHandle = 0L
$script:NotifyWindowClass = ''
$script:UiObserved = $false
$script:CleanExit = $false
$script:CleanupMode = 'NOT_STARTED'
$script:FailureClass = ''
$script:FailureDetail = ''
$script:WorkRootPreserved = $false
$script:Evidence = New-Object Collections.ArrayList
$script:WindowSamples = New-Object Collections.ArrayList
$script:NotifyProbeSamples = New-Object Collections.ArrayList

if (-not $EvidenceDirectory) {
    $parent = Split-Path -Parent ([IO.Path]::GetFullPath($CandidateZipPath))
    $EvidenceDirectory = Join-Path $parent ('PNCC-WU084-NATIVE-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
if (-not (Test-Path -LiteralPath $EvidenceDirectory)) { New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null }
$script:LogPath = Join-Path $EvidenceDirectory 'PNCC-WU084-NATIVE.log'
$script:ResultPath = Join-Path $EvidenceDirectory 'wu084-notify-native-result.json'
$script:PortsBeforePath = Join-Path $EvidenceDirectory 'ports-before.json'
$script:PortsAfterPath = Join-Path $EvidenceDirectory 'ports-after.json'
$script:WindowEvidencePath = Join-Path $EvidenceDirectory 'pid-window-samples.json'
$script:NotifyProbePath = Join-Path $EvidenceDirectory 'notify-native-probes.json'
$script:ProductLaunchLogEvidencePath = Join-Path $EvidenceDirectory 'product-launch.log'

function Write-RunnerLog {
    param([string]$Text)
    $line = ('{0:yyyy-MM-dd HH:mm:ss.fff}  {1}' -f (Get-Date),$Text)
    Write-Host $line
    Add-Content -LiteralPath $script:LogPath -Encoding UTF8 -Value $line
}

function Add-EvidenceEvent {
    param([string]$Type,[string]$Detail)
    [void]$script:Evidence.Add([pscustomobject]@{ Timestamp=(Get-Date).ToString('o'); Type=$Type; Detail=$Detail })
    Write-RunnerLog ($Type + ' :: ' + $Detail)
}

function Write-JsonUtf8Bom {
    param([string]$Path,$Value,[int]$Depth=8)
    [IO.File]::WriteAllText($Path,($Value | ConvertTo-Json -Depth $Depth),(New-Object Text.UTF8Encoding($true)))
}

function Get-Sha256 {
    param([string]$Path)
    return ([string](Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
}

function Get-ProtectedListenerSnapshot {
    $rows = New-Object Collections.ArrayList
    try {
        foreach ($c in @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $script:ProtectedPorts -contains [int]$_.LocalPort })) {
            [void]$rows.Add([pscustomobject]@{ LocalAddress=[string]$c.LocalAddress; LocalPort=[int]$c.LocalPort; OwningProcess=[int]$c.OwningProcess })
        }
    }
    catch {
        foreach ($line in @(& netstat.exe -ano -p tcp 2>$null)) {
            if ($line -notmatch '^\s*TCP\s+(\S+):(1080|1081)\s+\S+\s+LISTENING\s+(\d+)\s*$') { continue }
            [void]$rows.Add([pscustomobject]@{ LocalAddress=[string]$Matches[1]; LocalPort=[int]$Matches[2]; OwningProcess=[int]$Matches[3] })
        }
    }
    return @($rows | Sort-Object LocalPort,LocalAddress,OwningProcess)
}

function Get-SnapshotFingerprint {
    param($Snapshot)
    return (@($Snapshot) | ConvertTo-Json -Depth 5 -Compress)
}

function Assert-NoLiveV7ProcessBaseline {
    $rows = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.ProcessId -ne $PID -and $_.Name -in @('powershell.exe','pwsh.exe') -and $_.CommandLine -and
        (($_.CommandLine -match '(?i)VPS-Control-v7-launch\.ps1') -or ($_.CommandLine -match '(?i)VPS-Control-v7\.ps1'))
    })
    if ($rows.Count -gt 0) {
        $script:FailureClass = 'LIVE_V7_PROCESS_BASELINE'
        throw ('LIVE_V7_PROCESS_BASELINE count=' + $rows.Count + '; processIds=' + ((@($rows | ForEach-Object { [int]$_.ProcessId })) -join ','))
    }
    Add-EvidenceEvent 'LIVE_V7_PROCESS_BASELINE_CLEAN' 'No live V7 PowerShell process exists; stale Explorer tray artifacts are ignored.'
}

function Assert-PackageManifest {
    param([string]$BaseDir)
    $manifest = Join-Path $BaseDir 'VPS-Control-v7-SHA256.txt'
    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw 'PACKAGE_MANIFEST_MISSING' }
    $count=0
    foreach ($line in Get-Content -LiteralPath $manifest -ErrorAction Stop) {
        if (-not $line -or $line.TrimStart().StartsWith('#')) { continue }
        if ($line -notmatch '^([0-9a-fA-F]{64})\s+(.+)$') { throw ('PACKAGE_MANIFEST_INVALID_LINE: ' + $line) }
        $path = Join-Path $BaseDir $Matches[2].Trim()
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('PACKAGE_FILE_MISSING: ' + $Matches[2].Trim()) }
        if ((Get-Sha256 $path) -ne $Matches[1].ToLowerInvariant()) { throw ('PACKAGE_HASH_MISMATCH: ' + $Matches[2].Trim()) }
        $count++
    }
    if ($count -lt 1) { throw 'PACKAGE_MANIFEST_EMPTY' }
    return $count
}

function Assert-PowerShellAst {
    param([string]$BaseDir)
    $files = @(Get-ChildItem -LiteralPath $BaseDir -Recurse -Filter '*.ps1' -File -ErrorAction Stop | Sort-Object FullName)
    foreach ($file in $files) {
        $tokens=$null; $errors=$null
        [void][System.Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors)
        if (@($errors).Count -gt 0) { throw ('POWERSHELL_AST_FAIL file=' + $file.Name + '; count=' + @($errors).Count) }
    }
    return $files.Count
}

function Invoke-FunctionalConsistency {
    param([string]$BaseDir)
    . (Join-Path $BaseDir 'modules\V7-Consistency.ps1')
    $r = Test-V7FunctionalConsistency -BaseDir $BaseDir -UiVersion $script:ExpectedUiVersion -ModuleNames $script:ModuleNames
    if (-not $r -or -not [bool]$r.Ok) { throw 'FUNCTIONAL_CONSISTENCY_FAIL' }
    if ([int]$r.Summary.Checks -ne 203 -or [int]$r.Summary.Passed -ne 203) { throw ('FUNCTIONAL_CONSISTENCY_UNEXPECTED_COUNT checks=' + $r.Summary.Checks + '; passed=' + $r.Summary.Passed) }
    return $r
}

if (-not ('Pncc.Wu084.NotifyNative' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
namespace Pncc.Wu084 {
    public sealed class NotifyWindowRecord {
        public long Handle { get; set; }
        public string Title { get; set; }
        public string ClassName { get; set; }
        public bool Visible { get; set; }
    }
    public static class NotifyNative {
        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
        [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
        [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hWnd);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);
        [DllImport("user32.dll")] private static extern int GetWindowTextLength(IntPtr hWnd);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetClassName(IntPtr hWnd, StringBuilder className, int maxCount);
        [DllImport("user32.dll", SetLastError=true)] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
        public static NotifyWindowRecord[] ForProcess(int processId) {
            var rows = new List<NotifyWindowRecord>();
            EnumWindows(delegate(IntPtr hWnd, IntPtr lParam) {
                uint owner; GetWindowThreadProcessId(hWnd,out owner);
                if (owner != (uint)processId) return true;
                int len=GetWindowTextLength(hWnd);
                var title=new StringBuilder(Math.Max(len+1,2)); GetWindowText(hWnd,title,title.Capacity);
                var cls=new StringBuilder(256); GetClassName(hWnd,cls,cls.Capacity);
                rows.Add(new NotifyWindowRecord { Handle=hWnd.ToInt64(), Title=title.ToString(), ClassName=cls.ToString(), Visible=IsWindowVisible(hWnd) });
                return true;
            },IntPtr.Zero);
            return rows.ToArray();
        }
        public static bool PostTrayRightButtonUp(long handle) {
            return PostMessage(new IntPtr(handle),0x0800,IntPtr.Zero,new IntPtr(0x0205));
        }
    }
    public static class NotifyMouse {
        [DllImport("user32.dll")] private static extern bool SetCursorPos(int X,int Y);
        [DllImport("user32.dll")] private static extern void mouse_event(uint flags,uint dx,uint dy,uint data,UIntPtr extraInfo);
        public static void LeftClick(int x,int y) { SetCursorPos(x,y); mouse_event(0x0002,0,0,0,UIntPtr.Zero); mouse_event(0x0004,0,0,0,UIntPtr.Zero); }
    }
}
'@
}

function Get-ProcessTopLevelWindows {
    param([int]$TargetProcessId)
    return @([Pncc.Wu084.NotifyNative]::ForProcess($TargetProcessId) | ForEach-Object { [pscustomobject]@{ Handle=[long]$_.Handle; Title=[string]$_.Title; ClassName=[string]$_.ClassName; Visible=[bool]$_.Visible } })
}

function Add-WindowSample {
    param([int]$TargetProcessId,$Windows,[string]$Reason)
    if ($script:WindowSamples.Count -ge 40) { return }
    [void]$script:WindowSamples.Add([pscustomobject]@{ Timestamp=(Get-Date).ToString('o'); ProcessId=$TargetProcessId; Reason=$Reason; ProcessAlive=[bool](Get-Process -Id $TargetProcessId -ErrorAction SilentlyContinue); Windows=@($Windows) })
}

function Wait-ExpectedPidWindow {
    param([int]$TargetProcessId,[int]$TimeoutSeconds)
    $deadline=(Get-Date).AddSeconds($TimeoutSeconds); $last=''; $lastPeriodic=[datetime]::MinValue
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $TargetProcessId -ErrorAction SilentlyContinue)) { Add-WindowSample -TargetProcessId $TargetProcessId -Windows @() -Reason 'PROCESS_EXITED_BEFORE_UI'; return $null }
        $windows=@(Get-ProcessTopLevelWindows -TargetProcessId $TargetProcessId)
        $fp=$windows | ConvertTo-Json -Depth 4 -Compress; $now=Get-Date
        if ($fp -ne $last -or ($now-$lastPeriodic).TotalSeconds -ge 5) { Add-WindowSample -TargetProcessId $TargetProcessId -Windows $windows -Reason $(if($fp -ne $last){'WINDOW_SET_CHANGE'}else{'PERIODIC'}); $last=$fp; $lastPeriodic=$now }
        foreach ($w in $windows) { if ($w.Visible -and [string]::Equals([string]$w.Title,$script:ExpectedWindowTitle,[StringComparison]::Ordinal)) { Add-WindowSample -TargetProcessId $TargetProcessId -Windows $windows -Reason 'EXPECTED_VISIBLE_WINDOW'; return $w } }
        Start-Sleep -Milliseconds 350
    }
    Add-WindowSample -TargetProcessId $TargetProcessId -Windows @(Get-ProcessTopLevelWindows -TargetProcessId $TargetProcessId) -Reason 'WINDOW_TIMEOUT'
    return $null
}

function Initialize-Uia {
    Add-Type -AssemblyName UIAutomationClient -ErrorAction Stop
    Add-Type -AssemblyName UIAutomationTypes -ErrorAction Stop
}

function Get-UiaExactNameElements {
    param([string]$Name)
    Initialize-Uia
    $root=[System.Windows.Automation.AutomationElement]::RootElement
    $condition=New-Object -TypeName System.Windows.Automation.PropertyCondition -ArgumentList @([System.Windows.Automation.AutomationElement]::NameProperty,$Name)
    $found=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
    $rows=New-Object Collections.ArrayList
    for($i=0;$i -lt $found.Count;$i++){[void]$rows.Add($found.Item($i))}
    return @($rows)
}

function Get-ClickableExactNameElement {
    param([string]$Name)
    foreach($element in @(Get-UiaExactNameElements -Name $Name)) {
        try { $r=$element.Current.BoundingRectangle; if(-not $element.Current.IsOffscreen -and $r.Width -gt 2 -and $r.Height -gt 2){return $element} } catch {}
    }
    return $null
}

function Invoke-UiaElement {
    param($Element)
    if(-not $Element){return $false}
    try { $p=$Element.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern); if($p){([System.Windows.Automation.InvokePattern]$p).Invoke();return $true} } catch {}
    try { $r=$Element.Current.BoundingRectangle; if($r.Width -gt 2 -and $r.Height -gt 2){[Pncc.Wu084.NotifyMouse]::LeftClick([int]($r.Left+$r.Width/2),[int]($r.Top+$r.Height/2));return $true} } catch {}
    return $false
}

function Wait-ExactExitMenuItem {
    param([int]$TimeoutSeconds)
    $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
    while((Get-Date)-lt$deadline){$item=Get-ClickableExactNameElement -Name $script:ExpectedExitMenuText;if($item){return $item};Start-Sleep -Milliseconds 150}
    return $null
}

function Get-NotifyNativeWindowCandidates {
    param([int]$TargetProcessId)
    return @(Get-ProcessTopLevelWindows -TargetProcessId $TargetProcessId | Where-Object {
        -not $_.Visible -and -not $_.Title -and $_.ClassName -like 'WindowsForms10.Window.0.app.*'
    })
}

function Invoke-ExactProcessNotifyNativeExit {
    param([int]$TargetProcessId,[int]$MenuWaitSeconds)
    $candidates=@(Get-NotifyNativeWindowCandidates -TargetProcessId $TargetProcessId)
    Add-EvidenceEvent 'NOTIFY_NATIVE_CANDIDATES' ('count=' + $candidates.Count + '; handles=' + ((@($candidates | ForEach-Object { $_.Handle })) -join ','))
    if($candidates.Count -lt 1){throw 'NOTIFY_NATIVE_WINDOW_CANDIDATE_NOT_FOUND'}
    foreach($candidate in $candidates){
        $probe=[ordered]@{Timestamp=(Get-Date).ToString('o');Handle=[long]$candidate.Handle;ClassName=[string]$candidate.ClassName;PostMessage=$false;ExitMenuObserved=$false}
        try{
            $probe.PostMessage=[bool][Pncc.Wu084.NotifyNative]::PostTrayRightButtonUp([long]$candidate.Handle)
            if(-not $probe.PostMessage){[void]$script:NotifyProbeSamples.Add([pscustomobject]$probe);continue}
            $item=Wait-ExactExitMenuItem -TimeoutSeconds $MenuWaitSeconds
            if($item){
                $probe.ExitMenuObserved=$true
                [void]$script:NotifyProbeSamples.Add([pscustomobject]$probe)
                $script:NotifyWindowHandle=[long]$candidate.Handle
                $script:NotifyWindowClass=[string]$candidate.ClassName
                Add-EvidenceEvent 'NOTIFY_NATIVE_WINDOW_PROVEN' ('handle=' + $script:NotifyWindowHandle + '; class=' + $script:NotifyWindowClass + '; callback=WM_USER+1024; event=WM_RBUTTONUP')
                if(-not(Invoke-UiaElement -Element $item)){throw 'PRODUCT_NATIVE_EXIT_MENU_INVOKE_FAILED'}
                Add-EvidenceEvent 'PRODUCT_NATIVE_EXIT_INVOKED' 'Exact exit menu invoked after direct NotifyIconNativeWindow callback; Explorer tray identity was not used.'
                return $true
            }
            [void]$script:NotifyProbeSamples.Add([pscustomobject]$probe)
        }
        catch{
            $probe.Error=$_.Exception.Message
            [void]$script:NotifyProbeSamples.Add([pscustomobject]$probe)
        }
    }
    throw 'NOTIFY_NATIVE_WINDOW_NOT_PROVEN_BY_EXIT_MENU'
}

function Wait-ProcessExit {
    param([int]$TargetProcessId,[int]$TimeoutSeconds)
    $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
    while((Get-Date)-lt$deadline){if(-not(Get-Process -Id $TargetProcessId -ErrorAction SilentlyContinue)){return $true};Start-Sleep -Milliseconds 250}
    return (-not(Get-Process -Id $TargetProcessId -ErrorAction SilentlyContinue))
}

function Assert-ExactTestOwnedProcessIdentity {
    param([int]$TargetProcessId)
    if($TargetProcessId -le 0 -or $TargetProcessId -ne $script:TestOwnedProcessId){throw 'TEST_OWNED_PID_GUARD_REJECTED'}
    $p=Get-Process -Id $TargetProcessId -ErrorAction SilentlyContinue;if(-not$p){return $false}
    if($p.StartTime.ToUniversalTime().Ticks -ne $script:TestOwnedStartTicksUtc){throw 'TEST_OWNED_CREATION_TIME_MISMATCH'}
    $c=Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $TargetProcessId) -ErrorAction Stop
    if(-not$c){throw 'TEST_OWNED_CIM_IDENTITY_MISSING'}
    if(-not[string]::Equals([string]$c.ExecutablePath,$script:TestOwnedExecutablePath,[StringComparison]::OrdinalIgnoreCase)){throw 'TEST_OWNED_EXECUTABLE_PATH_MISMATCH'}
    if(-not([string]$c.CommandLine).Contains($script:TestOwnedLauncherPath)){throw 'TEST_OWNED_COMMAND_MARKER_MISSING'}
    if(-not([string]$c.CommandLine).Contains('-Demo')){throw 'TEST_OWNED_DEMO_MARKER_MISSING'}
    return $true
}

function Stop-ExactTestOwnedProcessEmergency {
    param([int]$TargetProcessId)
    if(-not(Assert-ExactTestOwnedProcessIdentity -TargetProcessId $TargetProcessId)){return $true}
    Stop-Process -Id $script:TestOwnedProcessId -Force -ErrorAction Stop
    return (Wait-ProcessExit -TargetProcessId $TargetProcessId -TimeoutSeconds 10)
}

function Copy-ProductLaunchLog {
    if(-not$script:ProductBaseDir -or -not(Test-Path -LiteralPath $script:ProductBaseDir -PathType Container)){return}
    try{$logs=@(Get-ChildItem -LiteralPath $script:ProductBaseDir -Recurse -File -Filter 'launch.log' -ErrorAction SilentlyContinue|Sort-Object LastWriteTime -Descending);if($logs.Count -gt 0){Copy-Item -LiteralPath $logs[0].FullName -Destination $script:ProductLaunchLogEvidencePath -Force;Add-EvidenceEvent 'PRODUCT_LAUNCH_LOG_CAPTURED' ('source=' + $logs[0].FullName)}}catch{Add-EvidenceEvent 'PRODUCT_LAUNCH_LOG_CAPTURE_FAIL' $_.Exception.Message}
}

$start=Get-Date
$workRoot=Join-Path $env:TEMP ('PNCC-WU084-NATIVE-' + [guid]::NewGuid().ToString('N'))
$extractRoot=Join-Path $workRoot 'candidate'
$portsBefore=@();$portsAfter=@();$consistency=$null;$packageCount=0;$astCount=0;$success=$false

try{
    Add-EvidenceEvent 'RUNNER_START' ('version=' + $script:RunnerVersion + '; PS=' + $PSVersionTable.PSVersion)
    if($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){throw 'WINDOWS_POWERSHELL_5_1_REQUIRED'}
    if(-not(Test-Path -LiteralPath $CandidateZipPath -PathType Leaf)){throw 'CANDIDATE_ZIP_NOT_FOUND'}
    $candidateSha=Get-Sha256 $CandidateZipPath
    if($candidateSha -ne $script:ExpectedCandidateSha256){throw ('CANDIDATE_SHA256_MISMATCH: ' + $candidateSha)}
    Add-EvidenceEvent 'CANDIDATE_VERIFIED' $candidateSha

    $portsBefore=@(Get-ProtectedListenerSnapshot);Write-JsonUtf8Bom -Path $script:PortsBeforePath -Value $portsBefore -Depth 5;Add-EvidenceEvent 'PORT_BASELINE_BEFORE' (Get-SnapshotFingerprint $portsBefore)
    Assert-NoLiveV7ProcessBaseline

    New-Item -ItemType Directory -Path $extractRoot -Force|Out-Null
    Expand-Archive -LiteralPath $CandidateZipPath -DestinationPath $extractRoot -Force
    $launchers=@(Get-ChildItem -LiteralPath $extractRoot -Recurse -Filter 'VPS-Control-v7-launch.ps1' -File -ErrorAction Stop)
    if($launchers.Count -ne 1){throw ('EXPECTED_ONE_LAUNCHER_GOT_' + $launchers.Count)}
    $baseDir=Split-Path -Parent $launchers[0].FullName;$script:ProductBaseDir=$baseDir;Add-EvidenceEvent 'FRESH_EXTRACT_PASS' ('base=' + $baseDir)
    $packageCount=Assert-PackageManifest -BaseDir $baseDir;Add-EvidenceEvent 'PACKAGE_MANIFEST_PASS' ('entries=' + $packageCount)
    $astCount=Assert-PowerShellAst -BaseDir $baseDir;Add-EvidenceEvent 'POWERSHELL_AST_PASS' ('files=' + $astCount)
    $consistency=Invoke-FunctionalConsistency -BaseDir $baseDir;Add-EvidenceEvent 'FUNCTIONAL_CONSISTENCY_PASS' ('checks=' + $consistency.Summary.Checks + '; passed=' + $consistency.Summary.Passed)

    $powerShellExe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe';$launcherPath=Join-Path $baseDir 'VPS-Control-v7-launch.ps1'
    $args='-NoLogo -NoProfile -ExecutionPolicy Bypass -STA -File "' + $launcherPath + '" -Demo'
    $proc=Start-Process -FilePath $powerShellExe -ArgumentList $args -WorkingDirectory $baseDir -PassThru;$proc.Refresh()
    $script:TestOwnedProcessId=[int]$proc.Id;$script:TestOwnedStartTicksUtc=[long]$proc.StartTime.ToUniversalTime().Ticks;$script:TestOwnedExecutablePath=$powerShellExe;$script:TestOwnedLauncherPath=$launcherPath;$script:CleanupMode='PRODUCT_NATIVE_NOTIFY_WINDOW_EXIT_PENDING'
    Add-EvidenceEvent 'PRODUCT_STARTED' ('processId=' + $script:TestOwnedProcessId + '; startTicksUtc=' + $script:TestOwnedStartTicksUtc)

    $window=Wait-ExpectedPidWindow -TargetProcessId $script:TestOwnedProcessId -TimeoutSeconds $WindowTimeoutSeconds
    if(-not$window){$script:FailureClass='OWNER_RUNNER_ACCEPTANCE_DEFECT / UI_WINDOW_NOT_OBSERVED';throw 'EXPECTED_PID_OWNED_VISIBLE_WINDOW_NOT_OBSERVED'}
    $script:UiObserved=$true;Add-EvidenceEvent 'EXPECTED_UI_OBSERVED' ('processId=' + $script:TestOwnedProcessId + '; hwnd=' + $window.Handle)

    [void](Invoke-ExactProcessNotifyNativeExit -TargetProcessId $script:TestOwnedProcessId -MenuWaitSeconds $MenuTimeoutSeconds)
    if(-not(Wait-ProcessExit -TargetProcessId $script:TestOwnedProcessId -TimeoutSeconds $CleanExitTimeoutSeconds)){$script:FailureClass='OWNER_RUNNER_ACCEPTANCE_DEFECT / CLEAN_EXIT_TIMEOUT';throw 'PRODUCT_NATIVE_NOTIFY_EXIT_DID_NOT_TERMINATE_PROCESS'}
    $script:CleanExit=$true;$script:CleanupMode='PRODUCT_NATIVE_NOTIFY_WINDOW_EXIT';Add-EvidenceEvent 'CLEAN_EXIT_PASS' ('processId=' + $script:TestOwnedProcessId)

    $portsAfter=@(Get-ProtectedListenerSnapshot);Write-JsonUtf8Bom -Path $script:PortsAfterPath -Value $portsAfter -Depth 5
    if((Get-SnapshotFingerprint $portsBefore) -ne (Get-SnapshotFingerprint $portsAfter)){$script:FailureClass='RUNTIME_BASELINE_CHANGED';throw 'PROTECTED_PORT_BASELINE_CHANGED'}
    Add-EvidenceEvent 'PORT_BASELINE_UNCHANGED' '1080/1081 exact listener snapshot unchanged.';$success=$true
}
catch{
    if(-not$script:FailureClass){$script:FailureClass='RUNNER_OR_ENVIRONMENT_FAILURE'};$script:FailureDetail=$_.Exception.Message;Add-EvidenceEvent 'FAIL' ($script:FailureClass + ' :: ' + $script:FailureDetail)
}
finally{
    try{if($script:WindowSamples.Count -gt 0){Write-JsonUtf8Bom -Path $script:WindowEvidencePath -Value $script:WindowSamples -Depth 8}}catch{}
    try{if($script:NotifyProbeSamples.Count -gt 0){Write-JsonUtf8Bom -Path $script:NotifyProbePath -Value $script:NotifyProbeSamples -Depth 8}}catch{}
    $alive=$false;if($script:TestOwnedProcessId -gt 0){$alive=[bool](Get-Process -Id $script:TestOwnedProcessId -ErrorAction SilentlyContinue)}
    if($alive){try{[void](Stop-ExactTestOwnedProcessEmergency -TargetProcessId $script:TestOwnedProcessId);$script:CleanupMode='FORCED_EXACT_IDENTITY_TEST_OWNED_PROCESS_ONLY';$script:CleanExit=$false;$success=$false;if(-not$script:FailureClass){$script:FailureClass='OWNER_RUNNER_ACCEPTANCE_DEFECT / EMERGENCY_CLEANUP_REQUIRED'};Add-EvidenceEvent 'EMERGENCY_CLEANUP' ('exact identity test-owned processId=' + $script:TestOwnedProcessId)}catch{$script:CleanupMode='EMERGENCY_CLEANUP_BLOCKED_OR_FAILED';$script:CleanExit=$false;$success=$false;if(-not$script:FailureClass){$script:FailureClass='EMERGENCY_CLEANUP_FAILURE'};Add-EvidenceEvent 'EMERGENCY_CLEANUP_FAIL' $_.Exception.Message}}
    Copy-ProductLaunchLog
    try{if($portsAfter.Count -eq 0){$portsAfter=@(Get-ProtectedListenerSnapshot);Write-JsonUtf8Bom -Path $script:PortsAfterPath -Value $portsAfter -Depth 5}}catch{}
    $portsUnchanged=$false;try{$portsUnchanged=((Get-SnapshotFingerprint $portsBefore) -eq (Get-SnapshotFingerprint $portsAfter))}catch{}
    if(-not$portsUnchanged){$success=$false;if(-not$script:FailureClass){$script:FailureClass='RUNTIME_BASELINE_CHANGED'}}
    if(-not$script:CleanExit){$success=$false}
    $aliveAfter=$false;if($script:TestOwnedProcessId -gt 0){$aliveAfter=[bool](Get-Process -Id $script:TestOwnedProcessId -ErrorAction SilentlyContinue)}
    if($aliveAfter){$script:WorkRootPreserved=$true;Add-EvidenceEvent 'WORKROOT_PRESERVED' ('process still alive; path=' + $workRoot)}
    $result=[ordered]@{schema_version=1;contract='PNCC_V7_0_1_NOTIFY_NATIVE_ACCEPTANCE';runner_version=$script:RunnerVersion;started_at=$start.ToString('o');completed_at=(Get-Date).ToString('o');candidate_sha256_expected=$script:ExpectedCandidateSha256;package_manifest_entries=$packageCount;powershell_ast_files=$astCount;functional_consistency_checks=$(if($consistency){[int]$consistency.Summary.Checks}else{0});functional_consistency_passed=$(if($consistency){[int]$consistency.Summary.Passed}else{0});test_process_id=$script:TestOwnedProcessId;ui_observed=[bool]$script:UiObserved;notify_native_window_handle=[long]$script:NotifyWindowHandle;notify_native_window_class=$script:NotifyWindowClass;notify_callback_message='WM_USER+1024 (0x0800)';notify_callback_event='WM_RBUTTONUP (0x0205)';explorer_tray_identity_used=$false;clean_exit=[bool]$script:CleanExit;cleanup_mode=$script:CleanupMode;work_root_preserved=[bool]$script:WorkRootPreserved;reserve_1080_unchanged=[bool]$portsUnchanged;primary_1081_unchanged=[bool]$portsUnchanged;ports_1080_1081_unchanged=[bool]$portsUnchanged;runtime_mutation=$false;runtime_authority=$false;promotion_eligible=$false;release_or_tag_authorized=$false;success=[bool]$success;failure_class=$script:FailureClass;failure_detail=$script:FailureDetail;evidence=@($script:Evidence)}
    try{Write-JsonUtf8Bom -Path $script:ResultPath -Value $result -Depth 10}catch{}
    if(-not$script:WorkRootPreserved){try{if(Test-Path -LiteralPath $workRoot){Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue}}catch{}}
}

if($success){Write-RunnerLog 'WU084_NATIVE_ACCEPTANCE=PASS ui_observed=true notify_native_exit=true clean_exit=true ports_unchanged=true';exit 0}
Write-RunnerLog ('WU084_NATIVE_ACCEPTANCE=FAIL class=' + $script:FailureClass + ' cleanup=' + $script:CleanupMode);exit 1
