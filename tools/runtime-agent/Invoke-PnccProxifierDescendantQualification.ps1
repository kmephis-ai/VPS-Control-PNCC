#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Live','Plan')][string]$Mode='Live',
    [string]$ReconciledResultPath,
    [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-PROXIFIER-DESCENDANT-QUALIFICATION-WU033',
    [int]$SampleIntervalSeconds=50,
    [int]$SampleCount=3,
    [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
function Get-Proc([int]$Id){try{return Get-CimInstance Win32_Process -Filter ("ProcessId="+$Id) -ErrorAction Stop}catch{return $null}}
function Get-AllProcs{return @(Get-CimInstance Win32_Process -ErrorAction Stop)}
function Get-AncestorIds([object]$Proc,[hashtable]$ById,[int]$MaxDepth=12){$ids=@();$seen=@{};$cur=[int]$Proc.ParentProcessId;for($i=0;$i -lt $MaxDepth -and $cur -gt 0;$i++){if($seen.ContainsKey($cur)){break};$seen[$cur]=$true;$ids+=$cur;if(-not $ById.ContainsKey($cur)){break};$cur=[int]$ById[$cur].ParentProcessId};return @($ids)}
function Get-RedactedFingerprint([string]$Cmd){if([string]::IsNullOrWhiteSpace($Cmd)){return ''};$s=[regex]::Replace([string]$Cmd,'(?i)(-pw\s+)("[^"]*"|\S+)','$1<redacted>');$s=[regex]::Replace($s,'(?i)(-pwfile\s+)("[^"]*"|\S+)','$1<redacted-path>');$sha=$null;try{$sha=[Security.Cryptography.SHA256]::Create();return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($s)))).Replace('-','').ToLowerInvariant()}finally{if($sha){$sha.Dispose()}}}
function Get-Snapshot([int]$WatchdogPid){$all=Get-AllProcs;$by=@{};foreach($p in $all){$by[[int]$p.ProcessId]=$p};$desc=New-Object Collections.ArrayList;foreach($p in @($all|Where-Object{[string]$_.Name -ieq 'Proxifier.exe'})){$anc=@(Get-AncestorIds $p $by);if($anc -contains $WatchdogPid){[void]$desc.Add([ordered]@{pid=[int]$p.ProcessId;parent_pid=[int]$p.ParentProcessId;name=[string]$p.Name;command_fingerprint=(Get-RedactedFingerprint ([string]$p.CommandLine))})}};return [ordered]@{timestamp=(Get-Date).ToString('o');proxifier_descendant_count=$desc.Count;descendants=@($desc)}}
function Write-Json($v,[string]$p){$d=Split-Path -Parent $p;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($p,($v|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($true)))}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$log=Join-Path $OutputDirectory 'PNCC-PROXIFIER-DESCENDANT-QUALIFICATION-WU033.log'
Start-Transcript $log -Force|Out-Null
try{
 if($Mode -eq 'Plan'){
  if(!$FixturePath -or !(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
  $f=Get-Content -LiteralPath $FixturePath -Raw|ConvertFrom-Json
  if(-not [bool]$f.reconciled_eight_pass){throw 'reconciled eight-pass prerequisite missing'}
  if(-not [bool]$f.watchdog_present){throw 'watchdog prerequisite missing'}
  if([int]$f.max_descendants -ne 0){throw 'fixture must prove zero descendants'}
  Write-Output 'PNCC_PROXIFIER_DESCENDANT_QUALIFICATION=PLAN_PASS RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false'
  exit 0
 }
 if(!$ReconciledResultPath -or !(Test-Path -LiteralPath $ReconciledResultPath -PathType Leaf)){throw 'ReconciledResultPath missing'}
 $r=Get-Content -LiteralPath $ReconciledResultPath -Raw|ConvertFrom-Json
 if([string]$r.contract_id -ne 'PNCC_RUNTIME_QUALIFICATION_RESULT_V1'){throw 'reconciled contract mismatch'}
 if([string]$r.qualification_state -ne 'BLOCKED' -or [string]$r.next_scope -ne 'PROXIFIER_DESCENDANT_CLEANUP'){throw 'reconciled prerequisite mismatch'}
 $checks=@($r.checks)
 if(@($checks|Where-Object{[string]$_.result -eq 'PASS'}).Count -ne 8){throw 'expected exactly eight PASS scopes'}
 if(@($checks|Where-Object{[string]$_.scope -eq 'PROXIFIER_DESCENDANT_CLEANUP' -and [string]$_.result -eq 'NOT_EXECUTED'}).Count -ne 1){throw 'proxifier scope prerequisite mismatch'}
 $pidFile=Join-Path (Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3') 'watchdog.pid'
 if(!(Test-Path -LiteralPath $pidFile -PathType Leaf)){throw 'watchdog pid file missing'}
 $watchPid=[int](Get-Content -LiteralPath $pidFile -Raw).Trim();$wp=Get-Proc $watchPid
 if($null -eq $wp -or [string]$wp.Name -notmatch '(?i)^powershell\.exe$'){throw 'live watchdog process missing'}
 $reserveBefore=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1080 -ErrorAction SilentlyContinue);$primaryBefore=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1081 -ErrorAction SilentlyContinue)
 if($reserveBefore.Count -lt 1){throw '1080 reserve listener missing'};if($primaryBefore.Count -lt 1){throw '1081 primary listener missing'}
 if($SampleCount -lt 2 -or $SampleCount -gt 5){throw 'SampleCount must be 2..5'};if($SampleIntervalSeconds -lt 45 -or $SampleIntervalSeconds -gt 120){throw 'SampleIntervalSeconds must be 45..120'}
 $samples=New-Object Collections.ArrayList
 for($i=0;$i -lt $SampleCount;$i++){$live=Get-Proc $watchPid;if($null-eq$live){throw 'watchdog exited during observation'};[void]$samples.Add((Get-Snapshot $watchPid));if($i -lt ($SampleCount-1)){Start-Sleep -Seconds $SampleIntervalSeconds}}
 $reserveAfter=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1080 -ErrorAction SilentlyContinue);$primaryAfter=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1081 -ErrorAction SilentlyContinue)
 if($reserveAfter.Count -lt 1){throw '1080 reserve listener lost during observation'};if($primaryAfter.Count -lt 1){throw '1081 primary listener lost during observation'}
 $max=0;foreach($s in @($samples)){if([int]$s.proxifier_descendant_count -gt $max){$max=[int]$s.proxifier_descendant_count}};$pass=($max -eq 0)
 $result=[ordered]@{schema_version=1;contract_id='PNCC_PROXIFIER_DESCENDANT_QUALIFICATION_V1';source_plane='PRIVATE_RUNTIME';runtime_mutation=$false;reserve_1080_mutation=$false;sample_interval_seconds=$SampleIntervalSeconds;sample_count=$SampleCount;samples=@($samples);max_proxifier_descendants=$max;reserve_1080_listening_before=($reserveBefore.Count-gt0);reserve_1080_listening_after=($reserveAfter.Count-gt0);primary_1081_listening_before=($primaryBefore.Count-gt0);primary_1081_listening_after=($primaryAfter.Count-gt0);result=$(if($pass){'PASS'}else{'BLOCKED'});failure_classification=$(if($pass){$null}else{'ENVIRONMENT_OR_BASELINE_BLOCKER'});runtime_authority=$false;promotion_eligible=$false}
 $rp=Join-Path $OutputDirectory 'proxifier-descendant-qualification-result.json';Write-Json $result $rp
 if($pass){Write-Output 'PNCC_PROXIFIER_DESCENDANT_QUALIFICATION=PASS MAX_DESCENDANTS=0 RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false';Write-Output "RESULT=$rp";Write-Output "LOG_PATH=$log";exit 0}
 Write-Output ("PNCC_PROXIFIER_DESCENDANT_QUALIFICATION=BLOCKED MAX_DESCENDANTS=$max RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false");Write-Output "RESULT=$rp";Write-Output "LOG_PATH=$log";exit 50
}catch{Write-Output ('PNCC_PROXIFIER_DESCENDANT_QUALIFICATION=BLOCKED ERROR='+$_.Exception.Message+' RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false');Write-Output "LOG_PATH=$log";exit 50}finally{try{Stop-Transcript|Out-Null}catch{}}
