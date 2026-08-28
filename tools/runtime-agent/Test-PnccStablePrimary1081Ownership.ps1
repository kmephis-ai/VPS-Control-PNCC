#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Live','Fixture')][string]$Mode='Live',
    [string]$FixturePath,
    [string]$OutputPath='E:\!Chrome_Downloads\PNCC-STABLE-PRIMARY-1081-OWNERSHIP.json'
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'

$ExpectedEngineSha='843c006b896607da19406998b54d4e6897fa8eb62d3e6bc92cc77255fe4833cf'
$PrimaryPort=1081
$ReservePort=1080
$StateDir=Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3'
$PidFile=Join-Path $StateDir 'watchdog.pid'
$Heartbeat=Join-Path $StateDir 'watchdog-heartbeat.json'

function Proc([int]$ProcessId){try{Get-CimInstance Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction Stop}catch{$null}}
function FileArg([string]$Cmd){if(-not$Cmd){return ''};$m=[regex]::Match($Cmd,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|''([^'']+)''|(\S+))');if(-not$m.Success){return ''};foreach($i in 1..3){if($m.Groups[$i].Success){return [string]$m.Groups[$i].Value}};return ''}
function Snap([int]$Port){$rows=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $Port -ErrorAction SilentlyContinue);$o=@();foreach($r in $rows){$p=Proc ([int]$r.OwningProcess);$o+=[ordered]@{pid=[int]$r.OwningProcess;name=$(if($p){[string]$p.Name}else{''});exe=$(if($p){[string]$p.ExecutablePath}else{''})}};[ordered]@{port=$Port;listening=($rows.Count-gt0);owners=@($o|Sort-Object pid)}}
function Key($v){$v|ConvertTo-Json -Depth 8 -Compress}
function WriteJson($v,[string]$p){$d=Split-Path -Parent $p;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($p,($v|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($true)))}

if($Mode-eq'Fixture'){
    if(-not$FixturePath-or-not(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
    $f=Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8|ConvertFrom-Json
    $checks=[ordered]@{primary_single=[bool]$f.primary_single;primary_putty=[bool]$f.primary_putty;primary_binding=[bool]$f.primary_binding;primary_pwfile=[bool]$f.primary_pwfile;primary_no_plain_pw=[bool]$f.primary_no_plain_pw;watchdog_registered=[bool]$f.watchdog_registered;watchdog_action=[bool]$f.watchdog_action;watchdog_fresh=[bool]$f.watchdog_fresh;watchdog_exact_engine=[bool]$f.watchdog_exact_engine;reserve_unchanged=[bool]$f.reserve_unchanged}
    $admitted=(@($checks.Values|Where-Object{-not$_}).Count-eq0)
    $e=[ordered]@{schema_version=1;contract_id='PNCC_STABLE_PRIMARY_1081_OWNERSHIP_V1';mode='Fixture';state=$(if($admitted){'OWNERSHIP_ADMITTED'}else{'BLOCKED'});checks=$checks;runtime_mutation=$false;reserve_1080_mutation=$false;primary_1081_tunnel_mutation=$false;runtime_authority=$false;promotion_eligible=$false}
    WriteJson $e $OutputPath
    Write-Output ('PNCC_STABLE_PRIMARY_1081_OWNERSHIP='+$e.state+' RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
    exit 0
}

if($env:OS-ne'Windows_NT'){throw 'Live mode requires Windows'}
$reserveBefore=Snap $ReservePort
$primaryRows=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $PrimaryPort -ErrorAction SilentlyContinue)
$primarySingle=($primaryRows.Count-eq1)
$primaryPutty=$false;$primaryBinding=$false;$primaryPwfile=$false;$primaryNoPlainPw=$false;$primaryPid=0
if($primarySingle){
    $primaryPid=[int]$primaryRows[0].OwningProcess;$p=Proc $primaryPid
    if($p){$cmd=[string]$p.CommandLine;$primaryPutty=([string]$p.Name-match'(?i)^(putty|putty_portable|plink)\.exe$');$primaryBinding=($cmd-match'(?i)(?:^|\s)-D\s+"?127\.0\.0\.1:1081"?(?:\s|$)');$primaryPwfile=($cmd-match'(?i)(?:^|\s)-pwfile(?:\s|=)');$primaryNoPlainPw=($cmd-notmatch'(?i)(?:^|\s)-pw(?:\s|=)')}
}
$watchdogRegistered=$false;$watchdogAction=$false;$watchdogFresh=$false;$watchdogExactEngine=$false;$watchPid=0;$watchEngineSha=''
if(Test-Path -LiteralPath $PidFile -PathType Leaf){
    try{$watchPid=[int](Get-Content -LiteralPath $PidFile -Raw).Trim();$wp=Proc $watchPid;if($wp){$watchdogRegistered=$true;$wcmd=[string]$wp.CommandLine;$watchdogAction=($wcmd-match'(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)');$wf=FileArg $wcmd;if($wf-and(Test-Path -LiteralPath $wf -PathType Leaf)){$watchEngineSha=(Get-FileHash -LiteralPath $wf -Algorithm SHA256).Hash.ToLowerInvariant();$watchdogExactEngine=($watchEngineSha-ceq$ExpectedEngineSha)}}}catch{}
}
$heartbeatAge=-1
if(Test-Path -LiteralPath $Heartbeat -PathType Leaf){$heartbeatAge=[int]((Get-Date)-(Get-Item -LiteralPath $Heartbeat).LastWriteTime).TotalSeconds;$watchdogFresh=($heartbeatAge-ge0-and$heartbeatAge-le240)}
$reserveAfter=Snap $ReservePort
$reserveUnchanged=((Key $reserveBefore)-ceq(Key $reserveAfter))
$checks=[ordered]@{primary_single=$primarySingle;primary_putty=$primaryPutty;primary_binding=$primaryBinding;primary_pwfile=$primaryPwfile;primary_no_plain_pw=$primaryNoPlainPw;watchdog_registered=$watchdogRegistered;watchdog_action=$watchdogAction;watchdog_fresh=$watchdogFresh;watchdog_exact_engine=$watchdogExactEngine;reserve_unchanged=$reserveUnchanged}
$admitted=(@($checks.Values|Where-Object{-not$_}).Count-eq0)
$e=[ordered]@{schema_version=1;contract_id='PNCC_STABLE_PRIMARY_1081_OWNERSHIP_V1';mode='Live';state=$(if($admitted){'OWNERSHIP_ADMITTED'}else{'BLOCKED'});checks=$checks;observations=[ordered]@{primary_pid=$primaryPid;watchdog_pid=$watchPid;watchdog_heartbeat_age_seconds=$heartbeatAge;watchdog_engine_sha256=$watchEngineSha};runtime_mutation=$false;reserve_1080_mutation=$false;primary_1081_tunnel_mutation=$false;runtime_authority=$false;promotion_eligible=$false}
WriteJson $e $OutputPath
Write-Output ('PNCC_STABLE_PRIMARY_1081_OWNERSHIP='+$e.state+' RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
Write-Output ('OUTPUT='+$OutputPath)
exit 0
