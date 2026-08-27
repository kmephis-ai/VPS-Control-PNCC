#requires -Version 5.1
# VPS Control Center RC14.13 telemetry coordinator.
# IMPORTANT: WinForms/UI thread performs LIGHT telemetry only.
# Heavy forensic collection is delegated to VPS-Control-v7-evidence-worker.ps1.

function Rotate-V7EvidenceLog([string]$Path,[long]$MaxBytes=8388608,[int]$Keep=3) {
    try {
        if(-not $Path -or -not(Test-Path -LiteralPath $Path -PathType Leaf)){return}
        if([long](Get-Item -LiteralPath $Path -ErrorAction Stop).Length -lt $MaxBytes){return}
        for($i=$Keep;$i -ge 1;$i--){
            $src=if($i -eq 1){$Path}else{"$Path."+($i-1)}
            $dst="$Path.$i"
            if(Test-Path -LiteralPath $src -PathType Leaf){Move-Item -LiteralPath $src -Destination $dst -Force -ErrorAction SilentlyContinue}
        }
    } catch { }
}

function Write-V7EvidenceJsonLine([string]$Path,$Object,[long]$MaxBytes=8388608) {
    try {
        if(-not $Path -or $null -eq $Object){return}
        $dir=Split-Path -Parent $Path
        if($dir -and -not(Test-Path -LiteralPath $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
        Rotate-V7EvidenceLog -Path $Path -MaxBytes $MaxBytes -Keep 3
        $json=ConvertTo-V7TraceSafeText ([string]($Object|ConvertTo-Json -Depth 10 -Compress))
        $sw=New-Object IO.StreamWriter($Path,$true,(New-Object Text.UTF8Encoding($false)))
        try{$sw.WriteLine($json)}finally{$sw.Dispose()}
    } catch { }
}

function Write-V7OperationEvidence {
    param(
        [Parameter(Mandatory=$true)][string]$Component,
        [Parameter(Mandatory=$true)][string]$Action,
        [int]$ExitCode=-999,
        [int]$DurationMs=0,
        [string]$Text='',
        [string]$Meta=''
    )
    try {
        $safeText=ConvertTo-V7TraceSafeText ([string]$Text)
        if($safeText.Length -gt 24000){$safeText=$safeText.Substring($safeText.Length-24000)}
        $obj=[pscustomobject]@{
            SchemaVersion=1;Timestamp=(Get-Date).ToString('o');Component=$Component;Action=$Action;
            ExitCode=$ExitCode;DurationMs=[math]::Max(0,$DurationMs);Meta=(ConvertTo-V7TraceSafeText ([string]$Meta));OutputTail=$safeText
        }
        Write-V7EvidenceJsonLine -Path $V7OperationEvidenceFile -Object $obj
    } catch { }
}

function Get-V7ModuleRuntimeEvidence($Runtime,$Config) {
    $rows=New-Object Collections.ArrayList
    foreach($module in @($ModuleNames)){
        $desired='';$effective='';$health='';$latency=0;$failure='';$http=0
        try{$desired=[string]$Config.$module}catch{}
        try{$effective=[string]$Runtime.Effective.$module}catch{}
        try{$health=[string]$Runtime.Health.$module}catch{}
        $metric=$null;try{$metric=$Runtime.Metrics.$module}catch{}
        if($metric){try{$latency=[int]$metric.LatencyMs}catch{};try{$failure=[string]$metric.FailureClass}catch{};try{$http=[int]$metric.HttpStatus}catch{}}
        [void]$rows.Add([pscustomobject]@{Module=$module;Desired=$desired;Effective=$effective;Health=$health;LatencyMs=$latency;FailureClass=$failure;HttpStatus=$http})
    }
    return @($rows)
}

function Get-V7LightProcessCounts {
    $result=[ordered]@{PowerShell=0;Proxifier=0;Putty=0;Plink=0;Pageant=0}
    try{$result.PowerShell=@(Get-Process -Name powershell,pwsh -ErrorAction SilentlyContinue).Count}catch{}
    try{$result.Proxifier=@(Get-Process -Name Proxifier -ErrorAction SilentlyContinue).Count}catch{}
    try{$result.Putty=@(Get-Process -Name putty,putty_portable -ErrorAction SilentlyContinue).Count}catch{}
    try{$result.Plink=@(Get-Process -Name plink -ErrorAction SilentlyContinue).Count}catch{}
    try{$result.Pageant=@(Get-Process -Name pageant -ErrorAction SilentlyContinue).Count}catch{}
    return [pscustomobject]$result
}

function Get-V7RuntimeMetricRecord([string]$Reason='periodic') {
    # LIGHT ONLY. Do not add CIM, full socket inventory, adapter statistics, hashing,
    # Windows Event Log reads or recursive filesystem walks here: this runs on WinForms timer.
    $runtime=Read-JsonFile $RuntimeFile
    $config=Get-ConfigSnapshot
    $watch=Get-WatchdogUiStatus
    $socks=Test-TcpListener '127.0.0.1' 1081 180
    $tunnels=Get-V7TunnelLightMatrix
    $routingTunnelId='PRIMARY_AUTO'
    try{$selection=Read-JsonFile (Join-Path $UiRuntimeDir 'tunnel-routing.json');if($selection -and [string]$selection.SelectedTunnelId -in @('PRIMARY_AUTO','RESERVE_MANUAL')){$routingTunnelId=[string]$selection.SelectedTunnelId}}catch{}
    $prox=Get-ProxifierUiStatus
    $age=Get-V7RuntimeEvidenceAgeSeconds -Path $RuntimeFile
    $uiProc=$null
    try {
        $p=Get-Process -Id $PID -ErrorAction Stop
        $uiProc=[pscustomobject]@{Pid=$PID;CpuSeconds=[math]::Round([double]$p.CPU,3);WorkingSetBytes=[long]$p.WorkingSet64;PrivateBytes=[long]$p.PrivateMemorySize64;Handles=[int]$p.HandleCount;Threads=@($p.Threads).Count}
    } catch { }
    $profile=$null;try{$profile=Get-ActiveVpsProfile}catch{}
    $activeSafe=$null
    if($profile){$activeSafe=[pscustomobject]@{Id=[string]$profile.Id;Name=[string]$profile.Name;AuthMode=[string]$profile.AuthMode;SavedSession=[string]$profile.SavedSession;ExpectedExitIp=[string]$profile.ExpectedExitIp}}
    $counts=Get-V7LightProcessCounts
    $workerState=$null;try{$workerState=Read-JsonFile (Join-Path $UiRuntimeDir 'evidence-worker-state.json')}catch{}
    return [pscustomobject]@{
        SchemaVersion=2;DetailLevel='LIGHT';Timestamp=(Get-Date).ToString('o');Reason=$Reason;UiVersion=$UiVersion;EngineVersion=$EngineVersion;Demo=[bool]$Demo;
        UiProcess=$uiProc;
        Socks=[pscustomobject]@{Listening=[bool]$socks;Endpoint='127.0.0.1:1081';Owner=(Get-V7SocksListenerOwnerText)};
        Tunnels=@($tunnels);RoutingTunnelId=$routingTunnelId;
        Watchdog=[pscustomobject]@{State=[string]$watch.State;Fresh=[bool]$watch.Fresh;Pid=[int]$watch.Pid;HeartbeatAgeSeconds=[int]$watch.HeartbeatAge};
        Proxifier=[pscustomobject]@{Running=[bool]$prox.Running;Pid=[int]$prox.Pid;ProcessCount=[int]$counts.Proxifier};
        ProcessCounts=$counts;
        EvidenceWorker=$workerState;
        Runtime=[pscustomobject]@{EvidenceAgeSeconds=$age;Fresh=(Test-V7RuntimeEvidenceFresh -AgeSeconds $age);RecoveryAttempts=[int]$script:RuntimeRecoveryAttempts;RecoveryNextAt=$(if($script:RuntimeRecoveryNextAt -gt [datetime]::MinValue){$script:RuntimeRecoveryNextAt.ToString('o')}else{''});RecoveryInFlight=[bool]$script:RuntimeRecoveryAction;EngineAction=[string]$script:EngineAction};
        ActiveVps=$activeSafe;
        Modules=@(Get-V7ModuleRuntimeEvidence -Runtime $runtime -Config $config)
    }
}

function Get-V7StateFingerprintObject($Metric) {
    if(-not $Metric){return $null}
    $mods=@($Metric.Modules|ForEach-Object{"$($_.Module)=$($_.Desired)/$($_.Effective)/$($_.Health)/$($_.FailureClass)"}) -join ','
    $tm=@($Metric.Tunnels|ForEach-Object{"$($_.Id)=$($_.Listening)/$($_.LifecycleMode)"})-join','
    return [pscustomobject]@{Socks=[bool]$Metric.Socks.Listening;Tunnels=$tm;RoutingTunnelId=[string]$Metric.RoutingTunnelId;Watchdog=[string]$Metric.Watchdog.State;WatchdogFresh=[bool]$Metric.Watchdog.Fresh;Proxifier=[bool]$Metric.Proxifier.Running;ProxifierCount=[int]$Metric.Proxifier.ProcessCount;RecoveryAttempts=[int]$Metric.Runtime.RecoveryAttempts;RecoveryInFlight=[bool]$Metric.Runtime.RecoveryInFlight;Modules=$mods}
}

function Trim-V7EvidenceExports([string]$OutputDir,[string]$Prefix='AUTO-incident',[int]$Keep=20) {
    try {
        if(-not $OutputDir -or -not(Test-Path -LiteralPath $OutputDir -PathType Container)){return}
        $files=@(Get-ChildItem -LiteralPath $OutputDir -Filter ($Prefix+'-*.txt') -File -ErrorAction SilentlyContinue|Sort-Object LastWriteTime -Descending)
        foreach($f in @($files|Select-Object -Skip ([math]::Max(1,$Keep)))){Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue}
    } catch { }
}

function Start-V7EvidenceWorker {
    param([Parameter(Mandatory=$true)][string]$OutputPath,[Parameter(Mandatory=$true)][string]$Reason)
    try {
        $baseDir=Split-Path -Parent $EngineSourcePath
        $worker=Join-Path $baseDir 'VPS-Control-v7-evidence-worker.ps1'
        if(-not(Test-Path -LiteralPath $worker -PathType Leaf)){throw "Не найден background evidence worker: $worker"}
        $argText='-NoLogo -NoProfile -ExecutionPolicy Bypass -File "'+$worker+'" -BaseDir "'+$baseDir+'" -DataRoot "'+([string]$StorageLayout.Root)+'" -StateDir "'+$StateDir+'" -OutputPath "'+$OutputPath+'" -Reason "'+($Reason.Replace('"',''))+'" -UiVersion "'+$UiVersion+'"'
        try {
            $placeholder = "=== VPS CONTROL CENTER · FORENSIC EVIDENCE QUEUED ===`r`nQueuedAt=$((Get-Date).ToString('o'))`r`nReason=$Reason`r`nStatus=BACKGROUND_WORKER_RUNNING`r`n"
            [IO.File]::WriteAllText($OutputPath,$placeholder,(New-Object Text.UTF8Encoding($true)))
        } catch { }
        $proc=Start-Process -FilePath $PowerShellExe -ArgumentList $argText -WindowStyle Hidden -PassThru
        Write-V7EvidenceJsonLine -Path $V7DiagnosticTraceFile -Object ([pscustomobject]@{Timestamp=(Get-Date).ToString('o');Type='EVIDENCE_WORKER_QUEUED';Reason=$Reason;Path=$OutputPath;Pid=[int]$proc.Id})
        Write-V7SocksTrace 'EVIDENCE_WORKER' ("queued pid=$($proc.Id); reason=$Reason; output=$OutputPath")
        return [pscustomobject]@{Started=$true;Path=$OutputPath;Pid=[int]$proc.Id}
    } catch {
        Write-V7SocksTrace 'EVIDENCE_WORKER' ("start-failed reason=$Reason error="+$_.Exception.Message)
        return [pscustomobject]@{Started=$false;Path=$OutputPath;Pid=0;Error=$_.Exception.Message}
    }
}

function New-V7FullDebugReport {
    param([Parameter(Mandatory=$true)][string]$OutputDir,[string]$Prefix='FULL-debug',[string]$Reason='manual')
    if(-not(Test-Path -LiteralPath $OutputDir)){New-Item -ItemType Directory -Path $OutputDir -Force|Out-Null}
    $path=Join-Path $OutputDir ("{0}-{1}.txt" -f $Prefix,(Get-Date -Format 'yyyyMMdd-HHmmss'))
    $r=Start-V7EvidenceWorker -OutputPath $path -Reason $Reason
    if(-not $r.Started){throw "Не удалось запустить background evidence worker: $($r.Error)"}
    return $path
}

function Invoke-V7AutoIncidentCapture([string]$Reason,[switch]$Force) {
    try {
        $now=Get-Date
        if(-not $Force -and $script:V7LastAutoIncidentAt -and (($now-$script:V7LastAutoIncidentAt).TotalSeconds -lt 300)){return ''}
        $script:V7LastAutoIncidentAt=$now
        $path=New-V7FullDebugReport -OutputDir $UiExportsDir -Prefix 'AUTO-incident' -Reason $Reason
        Trim-V7EvidenceExports -OutputDir $UiExportsDir -Prefix 'AUTO-incident' -Keep 20
        Write-V7EvidenceJsonLine -Path $V7DiagnosticTraceFile -Object ([pscustomobject]@{Timestamp=$now.ToString('o');Type='AUTO_INCIDENT_QUEUED';Reason=$Reason;Path=$path})
        try{Write-UiEvent 'DIAGNOSTICS' 'Автоматический forensic evidence поставлен в очередь' "$Reason; $path" 'WARN'}catch{}
        return $path
    } catch {Write-V7SocksTrace 'TELEMETRY_ERROR' ("auto-incident: "+$_.Exception.Message);return ''}
}

function Initialize-V7DeepTelemetry {
    try {
        $script:V7LastMetricAt=[datetime]::MinValue;$script:V7LastAutoIncidentAt=[datetime]::MinValue;$script:V7LastStateFingerprint='';$script:V7ProxifierFanoutWarned=$false
        Trim-V7EvidenceExports -OutputDir $UiExportsDir -Prefix 'AUTO-incident' -Keep 20
        $metric=Get-V7RuntimeMetricRecord -Reason 'ui-start'
        Write-V7EvidenceJsonLine -Path $V7RuntimeMetricsFile -Object $metric
        $script:V7LastMetricAt=Get-Date
        $script:V7LastStateFingerprint=((Get-V7StateFingerprintObject $metric)|ConvertTo-Json -Compress -Depth 5)
        Write-V7EvidenceJsonLine -Path $V7DiagnosticTraceFile -Object ([pscustomobject]@{Timestamp=(Get-Date).ToString('o');Type='TELEMETRY_START';Mode='LIGHT_UI_PLUS_ASYNC_FORENSIC';IntervalSeconds=30;UiVersion=$UiVersion;MetricPath=$V7RuntimeMetricsFile;TracePath=$V7DiagnosticTraceFile;OperationPath=$V7OperationEvidenceFile})
        Write-V7SocksTrace 'TELEMETRY' 'initialized mode=LIGHT_UI_PLUS_ASYNC_FORENSIC interval=30s'
    } catch {Write-V7SocksTrace 'TELEMETRY_ERROR' ("initialize: "+$_.Exception.Message)}
}

function Invoke-V7DeepTelemetryTick([switch]$Force) {
    try {
        $now=Get-Date
        if(-not $Force -and (($now-$script:V7LastMetricAt).TotalSeconds -lt 30)){return}
        $metric=Get-V7RuntimeMetricRecord -Reason $(if($Force){'forced-light'}else{'periodic-light'})
        Write-V7EvidenceJsonLine -Path $V7RuntimeMetricsFile -Object $metric
        $script:V7LastMetricAt=$now
        if([int]$metric.Proxifier.ProcessCount -gt 5 -and -not $script:V7ProxifierFanoutWarned){
            $script:V7ProxifierFanoutWarned=$true
            Write-V7EvidenceJsonLine -Path $V7DiagnosticTraceFile -Object ([pscustomobject]@{Timestamp=$now.ToString('o');Type='PROCESS_FANOUT_WARN';Process='Proxifier';Count=[int]$metric.Proxifier.ProcessCount})
            Write-V7SocksTrace 'PROCESS_FANOUT' ("Proxifier count=$([int]$metric.Proxifier.ProcessCount); deep process/socket enumeration deferred to background worker")
        }
        $state=Get-V7StateFingerprintObject $metric;$fingerprint=$state|ConvertTo-Json -Compress -Depth 5
        if($fingerprint -ne $script:V7LastStateFingerprint){
            Write-V7EvidenceJsonLine -Path $V7DiagnosticTraceFile -Object ([pscustomobject]@{Timestamp=$now.ToString('o');Type='STATE_CHANGE';State=$state})
            Write-V7SocksTrace 'STATE_CHANGE' (ConvertTo-V7TraceSafeText $fingerprint)
            $script:V7LastStateFingerprint=$fingerprint
            $effectiveVps=@($metric.Modules|Where-Object{$_.Effective -eq 'VPS'}).Count
            $badModule=@($metric.Modules|Where-Object{$_.Health -eq 'FAILED'}).Count
            if((-not [bool]$metric.Socks.Listening -and $effectiveVps -gt 0) -or (-not [bool]$metric.Watchdog.Fresh) -or $badModule -gt 0){
                Invoke-V7AutoIncidentCapture -Reason ("state-change socks=$([bool]$metric.Socks.Listening) effectiveVps=$effectiveVps watchdog=$([string]$metric.Watchdog.State)/$([bool]$metric.Watchdog.Fresh) failedModules=$badModule")|Out-Null
            }
        }
    } catch {Write-V7SocksTrace 'TELEMETRY_ERROR' ("tick: "+$_.Exception.Message)}
}
