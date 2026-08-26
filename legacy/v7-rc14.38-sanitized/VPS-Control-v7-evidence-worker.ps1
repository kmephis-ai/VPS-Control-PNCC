#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BaseDir,
    [Parameter(Mandatory=$true)][string]$DataRoot,
    [Parameter(Mandatory=$true)][string]$StateDir,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [string]$Reason='background',
    [string]$UiVersion='unknown'
)

$ErrorActionPreference='SilentlyContinue'
$logsDir=Join-Path $DataRoot 'logs'
$telemetryDir=Join-Path $DataRoot 'telemetry'
$runtimeDir=Join-Path $DataRoot 'runtime'
$exportsDir=Join-Path $DataRoot 'exports'
$workerStateFile=Join-Path $runtimeDir 'evidence-worker-state.json'
foreach($d in @($logsDir,$telemetryDir,$runtimeDir,$exportsDir)){if($d -and -not(Test-Path -LiteralPath $d)){New-Item -ItemType Directory -Path $d -Force|Out-Null}}
$workerLog=Join-Path $logsDir 'evidence-worker.log'
function WLog([string]$Text){try{Add-Content -LiteralPath $workerLog -Encoding UTF8 -Value ('{0:yyyy-MM-dd HH:mm:ss.fff}  {1}' -f (Get-Date),$Text)}catch{}}
function Safe([string]$Text){
    if($null -eq $Text){return ''}
    $s=[string]$Text
    $s=[regex]::Replace($s,'(?i)(-pw\s+)("[^"]*"|\S+)','$1<redacted>')
    $s=[regex]::Replace($s,'(?i)(password\s*[=:]\s*)([^\s;\r\n]+)','$1<redacted>')
    $s=[regex]::Replace($s,'(?i)(authorization\s*:\s*bearer\s+)[^\s\r\n]+','$1<redacted>')
    $s=[regex]::Replace($s,'(?i)((?:api[_-]?key|token|secret)\s*[=:]\s*)[^\s;\r\n]+','$1<redacted>')
    $s=[regex]::Replace($s,'(?is)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----','<redacted-private-key>')
    return $s
}
function AddLine($List,[string]$Text){[void]$List.Add((Safe $Text))}
function AddSection($List,[string]$Title){AddLine $List '';AddLine $List ('=== '+$Title+' ===')}
function Tail([string]$Path,[int]$Lines=300){
    try{if(Test-Path -LiteralPath $Path -PathType Leaf){return @(Get-Content -LiteralPath $Path -Encoding UTF8 -Tail $Lines -ErrorAction SilentlyContinue|ForEach-Object{Safe ([string]$_)})}}catch{}
    return @()
}
function WriteWorkerState([string]$Status,[long]$DurationMs=0,[string]$ErrorText=''){
    try{
        $obj=[pscustomobject]@{SchemaVersion=1;Timestamp=(Get-Date).ToString('o');Status=$Status;Pid=$PID;Reason=$Reason;OutputPath=$OutputPath;DurationMs=$DurationMs;Error=(Safe $ErrorText)}
        $tmp=$workerStateFile+'.tmp.'+$PID
        [IO.File]::WriteAllText($tmp,($obj|ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding($true)))
        Move-Item -LiteralPath $tmp -Destination $workerStateFile -Force
    }catch{}
}
function FileMeta([string]$Path){
    try{if(-not(Test-Path -LiteralPath $Path -PathType Leaf)){return $null};$f=Get-Item -LiteralPath $Path -ErrorAction Stop;$sha='';try{$sha=(Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash}catch{};return [pscustomobject]@{Path=$Path;Bytes=[long]$f.Length;Modified=$f.LastWriteTime.ToString('o');Sha256=$sha}}catch{return $null}
}

$mutex=$null;$acquired=$false
try{
    $created=$false
    $mutex=New-Object Threading.Mutex($false,('Local\VPSControlV7EvidenceWorker-'+$env:USERNAME),[ref]$created)
    $acquired=$mutex.WaitOne(0)
    if(-not $acquired){
        WLog "SKIP another evidence worker is active; reason=$Reason"
        try{[IO.File]::WriteAllText($OutputPath,("Evidence worker skipped: another forensic collection is already active.`r`nReason=$Reason`r`nCreatedAt=$((Get-Date).ToString('o'))"),(New-Object Text.UTF8Encoding($true)))}catch{}
        exit 31
    }
    WLog "START reason=$Reason output=$OutputPath ui=$UiVersion pid=$PID"
    WriteWorkerState 'RUNNING' 0 ''
    $sw=[Diagnostics.Stopwatch]::StartNew()
    $lines=New-Object Collections.ArrayList
    AddLine $lines '=== VPS CONTROL CENTER · BACKGROUND FORENSIC EVIDENCE ==='
    AddLine $lines ('CreatedAt='+(Get-Date).ToString('o'))
    AddLine $lines ('UiVersion='+$UiVersion)
    AddLine $lines ('Reason='+$Reason)
    AddLine $lines ('WorkerPid='+$PID)
    AddLine $lines 'SecretsIncluded=false'
    AddLine $lines 'NOTE: DPAPI blobs, password/private-key contents and credential command lines are excluded/redacted.'

    AddSection $lines 'HOST / POWERSHELL'
    AddLine $lines ('ComputerName='+$env:COMPUTERNAME)
    AddLine $lines ('User='+$env:USERNAME)
    AddLine $lines ('PowerShell='+[string]$PSVersionTable.PSVersion)
    AddLine $lines ('Process64Bit='+[Environment]::Is64BitProcess+' OS64Bit='+[Environment]::Is64BitOperatingSystem)
    try{$os=Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue;if($os){AddLine $lines (Safe ($os|Select-Object Caption,Version,BuildNumber,LastBootUpTime,FreePhysicalMemory,TotalVisibleMemorySize|ConvertTo-Json -Compress -Depth 4))}}catch{}
    try{$cpu=Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue|Select-Object Name,LoadPercentage,NumberOfCores,NumberOfLogicalProcessors;foreach($x in @($cpu)){AddLine $lines (Safe ($x|ConvertTo-Json -Compress -Depth 4))}}catch{}

    AddSection $lines 'PATHS / PACKAGE FILES'
    AddLine $lines ('BaseDir='+$BaseDir);AddLine $lines ('DataRoot='+$DataRoot);AddLine $lines ('StateDir='+$StateDir)
    foreach($f in @(Get-ChildItem -LiteralPath $BaseDir -File -ErrorAction SilentlyContinue|Where-Object{$_.Name -like 'VPS-Control-v7*' -or $_.Name -like 'VPS-Control-v6.5*'}|Sort-Object Name)){
        if($f.Name -match '(?i)\.zip$'){continue};$m=FileMeta $f.FullName;if($m){AddLine $lines ($m|ConvertTo-Json -Compress -Depth 3)}
    }
    $moduleDir=Join-Path $BaseDir 'modules'
    foreach($f in @(Get-ChildItem -LiteralPath $moduleDir -Filter '*.ps1' -File -ErrorAction SilentlyContinue|Sort-Object Name)){$m=FileMeta $f.FullName;if($m){AddLine $lines ($m|ConvertTo-Json -Compress -Depth 3)}}

    AddSection $lines 'PORTABLE PUTTY ARTIFACT METADATA'
    $portable=Join-Path $BaseDir 'PuTTY PORTABLE'
    if(Test-Path -LiteralPath $portable -PathType Container){
        AddLine $lines ('Path='+$portable)
        foreach($d in @(Get-ChildItem -LiteralPath $portable -Directory -ErrorAction SilentlyContinue|Sort-Object Name)){AddLine $lines ('DIR '+$d.Name)}
        foreach($f in @(Get-ChildItem -LiteralPath $portable -File -Recurse -ErrorAction SilentlyContinue|Sort-Object FullName|Select-Object -First 300)){
            $rel=$f.FullName.Substring($portable.Length).TrimStart('\')
            $sha='';if([long]$f.Length -le 10485760){try{$sha=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256 -ErrorAction Stop).Hash}catch{}}
            AddLine $lines ("FILE $rel | $($f.Length) bytes | $($f.LastWriteTime.ToString('o')) | sha256=$sha")
        }
    }else{AddLine $lines 'NOT_FOUND'}

    AddSection $lines 'NETWORK ADAPTERS / IP / DNS / DEFAULT ROUTES'
    try{foreach($x in @(Get-NetAdapter -ErrorAction SilentlyContinue|Select-Object Name,Status,LinkSpeed,InterfaceDescription,ifIndex)){AddLine $lines ($x|ConvertTo-Json -Compress -Depth 4)}}catch{}
    try{foreach($x in @(Get-NetIPAddress -ErrorAction SilentlyContinue|Where-Object{$_.IPAddress -and [string]$_.AddressState -ne 'Tentative'}|Select-Object InterfaceAlias,AddressFamily,IPAddress,PrefixLength,Type)){AddLine $lines ($x|ConvertTo-Json -Compress -Depth 4)}}catch{}
    try{foreach($x in @(Get-DnsClientServerAddress -ErrorAction SilentlyContinue|Where-Object{@($_.ServerAddresses).Count -gt 0}|Select-Object InterfaceAlias,AddressFamily,ServerAddresses)){AddLine $lines ($x|ConvertTo-Json -Compress -Depth 5)}}catch{}
    try{foreach($x in @(Get-NetRoute -ErrorAction SilentlyContinue|Where-Object{$_.DestinationPrefix -in @('0.0.0.0/0','::/0')}|Select-Object DestinationPrefix,NextHop,InterfaceAlias,RouteMetric,InterfaceMetric,State)){AddLine $lines ($x|ConvertTo-Json -Compress -Depth 4)}}catch{}
    try{foreach($x in @(Get-NetAdapterStatistics -ErrorAction SilentlyContinue|Select-Object Name,ReceivedBytes,SentBytes,ReceivedUnicastPackets,SentUnicastPackets,ReceivedDiscardedPackets,OutboundDiscardedPackets,ReceivedPacketErrors,OutboundPacketErrors)){AddLine $lines ($x|ConvertTo-Json -Compress -Depth 4)}}catch{}

    AddSection $lines 'RELEVANT PROCESSES'
    $allCim=@();try{$allCim=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)}catch{}
    $cimByPid=@{};foreach($c in $allCim){try{$cimByPid[[int]$c.ProcessId]=$c}catch{}}
    $names=@('putty','putty_portable','plink','pageant','Proxifier','powershell','pwsh')
    $pids=New-Object Collections.ArrayList
    foreach($n in $names){foreach($p in @(Get-Process -Name $n -ErrorAction SilentlyContinue)){
        [void]$pids.Add([int]$p.Id);$c=$null;if($cimByPid.ContainsKey([int]$p.Id)){$c=$cimByPid[[int]$p.Id]}
        $path='';try{$path=[string]$p.MainModule.FileName}catch{};if(-not $path -and $c){$path=[string]$c.ExecutablePath}
        $start='';try{$start=$p.StartTime.ToString('o')}catch{}
        $parent=0;if($c){try{$parent=[int]$c.ParentProcessId}catch{}}
        $obj=[pscustomobject]@{Name=$p.ProcessName;Pid=[int]$p.Id;ParentPid=$parent;Path=$path;StartTime=$start;CpuSeconds=$(try{[math]::Round([double]$p.CPU,3)}catch{0});WorkingSetBytes=$(try{[long]$p.WorkingSet64}catch{0});PrivateBytes=$(try{[long]$p.PrivateMemorySize64}catch{0});Handles=$(try{[int]$p.HandleCount}catch{0});Threads=$(try{@($p.Threads).Count}catch{0})}
        AddLine $lines ($obj|ConvertTo-Json -Compress -Depth 4)
    }}

    AddSection $lines 'RELEVANT SOCKETS'
    $pidSet=@{};foreach($id in $pids){$pidSet[[int]$id]=$true}
    try{foreach($c in @(Get-NetTCPConnection -ErrorAction SilentlyContinue)){
        if(([int]$c.LocalPort -notin @(1080,1081,3000)) -and ([int]$c.RemotePort -notin @(22,27)) -and -not $pidSet.ContainsKey([int]$c.OwningProcess)){continue}
        $pn='';try{$pn=[string](Get-Process -Id ([int]$c.OwningProcess) -ErrorAction SilentlyContinue).ProcessName}catch{}
        AddLine $lines (([pscustomobject]@{Protocol='TCP';State=[string]$c.State;LocalAddress=[string]$c.LocalAddress;LocalPort=[int]$c.LocalPort;RemoteAddress=[string]$c.RemoteAddress;RemotePort=[int]$c.RemotePort;OwningProcess=[int]$c.OwningProcess;ProcessName=$pn})|ConvertTo-Json -Compress -Depth 3)
    }}catch{}
    try{foreach($u in @(Get-NetUDPEndpoint -ErrorAction SilentlyContinue)){
        if(([int]$u.LocalPort -notin @(1080,1081)) -and -not $pidSet.ContainsKey([int]$u.OwningProcess)){continue}
        $pn='';try{$pn=[string](Get-Process -Id ([int]$u.OwningProcess) -ErrorAction SilentlyContinue).ProcessName}catch{}
        AddLine $lines (([pscustomobject]@{Protocol='UDP';LocalAddress=[string]$u.LocalAddress;LocalPort=[int]$u.LocalPort;OwningProcess=[int]$u.OwningProcess;ProcessName=$pn})|ConvertTo-Json -Compress -Depth 3)
    }}catch{}

    $sections=@(
        [pscustomobject]@{Title='RUNTIME METRICS';Path=(Join-Path $telemetryDir 'runtime-metrics.jsonl');Tail=800},
        [pscustomobject]@{Title='DIAGNOSTIC TRACE';Path=(Join-Path $telemetryDir 'diagnostic-trace.jsonl');Tail=800},
        [pscustomobject]@{Title='OPERATION EVIDENCE';Path=(Join-Path $telemetryDir 'operation-evidence.jsonl');Tail=600},
        [pscustomobject]@{Title='SOCKS RUNTIME TRACE';Path=(Join-Path $logsDir 'socks-runtime.log');Tail=1000},
        [pscustomobject]@{Title='SOCKS ENGINE TRACE';Path=(Join-Path $logsDir 'socks-engine.log');Tail=1000},
        [pscustomobject]@{Title='UI LOG';Path=(Join-Path $logsDir 'ui.log');Tail=600},
        [pscustomobject]@{Title='LAUNCH LOG';Path=(Join-Path $logsDir 'launch.log');Tail=500},
        [pscustomobject]@{Title='V7 EVENTS';Path=(Join-Path $logsDir 'events.jsonl');Tail=700},
        [pscustomobject]@{Title='V6.3 CONTROLLER LOG';Path=(Join-Path $StateDir 'controller.log');Tail=700},
        [pscustomobject]@{Title='V6.3 WATCHDOG LOG';Path=(Join-Path $StateDir 'watchdog.log');Tail=700},
        [pscustomobject]@{Title='ROUTE DECISIONS';Path=(Join-Path $StateDir 'route-decisions.log');Tail=700},
        [pscustomobject]@{Title='ENGINE TELEMETRY';Path=(Join-Path $StateDir 'telemetry.jsonl');Tail=500},
        [pscustomobject]@{Title='ENGINE INCIDENTS';Path=(Join-Path $StateDir 'incidents.jsonl');Tail=500},
        [pscustomobject]@{Title='RUNTIME STATE';Path=(Join-Path $StateDir 'runtime-state.json');Tail=2200},
        [pscustomobject]@{Title='OPERATIONAL STATS';Path=(Join-Path $StateDir 'operational-stats.json');Tail=2200}
    )
    foreach($s in $sections){AddSection $lines $s.Title;AddLine $lines ('Path='+$s.Path);foreach($x in @(Tail -Path $s.Path -Lines $s.Tail)){[void]$lines.Add($x)}}

    AddSection $lines 'RELEVANT WINDOWS APPLICATION EVENTS'
    try{
        $start=(Get-Date).AddHours(-8);$providers=@('Application Error','.NET Runtime','Windows Error Reporting','Windows PowerShell','PowerShell')
        foreach($ev in @(Get-WinEvent -FilterHashtable @{LogName='Application';StartTime=$start} -ErrorAction SilentlyContinue|Where-Object{$providers -contains [string]$_.ProviderName}|Select-Object -First 150)){
            $msg=Safe ([string]$ev.Message);if($msg -and $msg -notmatch '(?i)VPS-Control|powershell|putty|proxifier|\.ps1'){continue}
            AddLine $lines (([pscustomobject]@{TimeCreated=$(try{$ev.TimeCreated.ToString('o')}catch{''});Provider=[string]$ev.ProviderName;Id=[int]$ev.Id;Level=[string]$ev.LevelDisplayName;Message=$msg})|ConvertTo-Json -Compress -Depth 4)
        }
    }catch{}

    $sw.Stop();AddSection $lines 'WORKER SUMMARY';AddLine $lines ('DurationMs='+$sw.ElapsedMilliseconds);AddLine $lines ('CompletedAt='+(Get-Date).ToString('o'))
    $parent=Split-Path -Parent $OutputPath;if($parent -and -not(Test-Path -LiteralPath $parent)){New-Item -ItemType Directory -Path $parent -Force|Out-Null}
    [IO.File]::WriteAllText($OutputPath,(@($lines)-join "`r`n"),(New-Object Text.UTF8Encoding($true)))
    WLog "PASS reason=$Reason durationMs=$($sw.ElapsedMilliseconds) output=$OutputPath"
    WriteWorkerState 'PASS' $sw.ElapsedMilliseconds ''
    exit 0
}catch{
    WLog ('FAIL reason='+$Reason+' error='+$_.Exception.Message)
    try{WriteWorkerState 'FAIL' $(if($sw){$sw.ElapsedMilliseconds}else{0}) $_.Exception.Message}catch{}
    try{[IO.File]::WriteAllText($OutputPath,("Evidence worker failed: "+(Safe $_.Exception.ToString())),(New-Object Text.UTF8Encoding($true)))}catch{}
    exit 30
}finally{
    try{if($acquired -and $mutex){$mutex.ReleaseMutex()}}catch{};try{if($mutex){$mutex.Dispose()}}catch{}
}
