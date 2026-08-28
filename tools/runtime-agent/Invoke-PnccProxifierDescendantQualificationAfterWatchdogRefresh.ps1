#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Live','Plan')][string]$Mode='Live',
 [string]$ReconciledResultPath,
 [string]$WatchdogRefreshResultPath,
 [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-PROXIFIER-DESCENDANT-QUALIFICATION-WU038',
 [int]$SampleIntervalSeconds=50,
 [int]$SampleCount=3,
 [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
function Proc([int]$ProcessId){try{Get-CimInstance Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction Stop}catch{$null}}
function Ancestors($p,$by,[int]$Max=12){$a=@();$seen=@{};$cur=[int]$p.ParentProcessId;for($i=0;$i-lt$Max-and$cur-gt0;$i++){if($seen.ContainsKey($cur)){break};$seen[$cur]=$true;$a+=$cur;if(!$by.ContainsKey($cur)){break};$cur=[int]$by[$cur].ParentProcessId};@($a)}
function Finger([string]$s){if(!$s){return ''};$s=[regex]::Replace($s,'(?i)(-pw\s+)("[^"]*"|\S+)','$1<redacted>');$s=[regex]::Replace($s,'(?i)(-pwfile\s+)("[^"]*"|\S+)','$1<redacted-path>');$h=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($h.ComputeHash([Text.Encoding]::UTF8.GetBytes($s)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
function Snapshot([int]$WatchdogPid){$all=@(Get-CimInstance Win32_Process -ErrorAction Stop);$by=@{};foreach($p in $all){$by[[int]$p.ProcessId]=$p};$d=New-Object Collections.ArrayList;foreach($p in @($all|Where-Object{[string]$_.Name -ieq 'Proxifier.exe'})){if(@(Ancestors $p $by)-contains$WatchdogPid){[void]$d.Add([ordered]@{pid=[int]$p.ProcessId;parent_pid=[int]$p.ParentProcessId;command_fingerprint=(Finger ([string]$p.CommandLine))})}};[ordered]@{timestamp=(Get-Date).ToString('o');proxifier_descendant_count=$d.Count;descendants=@($d)}}
function WriteJson($v,[string]$p){$d=Split-Path -Parent $p;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($p,($v|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($true)))}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$log=Join-Path $OutputDirectory 'PNCC-PROXIFIER-DESCENDANT-QUALIFICATION-WU038.log'
Start-Transcript $log -Force|Out-Null
try {
 if($Mode-eq'Plan'){
  if(!$FixturePath-or!(Test-Path -LiteralPath $FixturePath)){throw 'FixturePath required'}
  $f=Get-Content -LiteralPath $FixturePath -Raw|ConvertFrom-Json
  foreach($n in @('reconciled_eight_pass','watchdog_refresh_pass','watchdog_only_mutation','watchdog_live','heartbeat_fresh','zero_descendants','listeners_preserved')){if(-not [bool]$f.$n){throw ('plan fixture failed: '+$n)}}
  Write-Output 'PNCC_PROXIFIER_DESCENDANT_QUALIFICATION_WU038=PLAN_PASS RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false'
  exit 0
 }
 if(!$ReconciledResultPath-or!(Test-Path -LiteralPath $ReconciledResultPath)){throw 'ReconciledResultPath missing'}
 if(!$WatchdogRefreshResultPath-or!(Test-Path -LiteralPath $WatchdogRefreshResultPath)){throw 'WatchdogRefreshResultPath missing'}
 $r=Get-Content -LiteralPath $ReconciledResultPath -Raw|ConvertFrom-Json
 if([string]$r.contract_id-ne'PNCC_RUNTIME_QUALIFICATION_RESULT_V1'-or[string]$r.next_scope-ne'PROXIFIER_DESCENDANT_CLEANUP'){throw 'reconciled prerequisite mismatch'}
 if(@($r.checks|Where-Object{$_.result-eq'PASS'}).Count-ne8){throw 'expected eight PASS scopes'}
 $wr=Get-Content -LiteralPath $WatchdogRefreshResultPath -Raw|ConvertFrom-Json
 if([string]$wr.contract_id-ne'PNCC_WATCHDOG_REFRESH_V1'-or[string]$wr.result-ne'PASS'){throw 'watchdog refresh prerequisite mismatch'}
 if([string]$wr.runtime_mutation-ne'watchdog_only'-or[bool]$wr.reserve_1080_mutation-or[bool]$wr.primary_1081_tunnel_mutation-or[bool]$wr.proxifier_mutation){throw 'watchdog refresh mutation contract mismatch'}
 $watchdogPid=[int]$wr.fresh_watchdog_pid;if($watchdogPid-le0){throw 'fresh watchdog PID missing'}
 $p=Proc $watchdogPid;if($null-eq$p-or[string]$p.Name-notmatch'(?i)^powershell\.exe$'){throw 'fresh watchdog process is no longer live'}
 $cmd=[string]$p.CommandLine;if($cmd-notmatch'(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)'){throw 'fresh process is not watchdog action'}
 $hb=Join-Path (Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3') 'watchdog-heartbeat.json';if(!(Test-Path -LiteralPath $hb)){throw 'watchdog heartbeat missing'}
 $age=[int]((Get-Date)-(Get-Item -LiteralPath $hb).LastWriteTime).TotalSeconds;if($age-lt0-or$age-gt60){throw 'watchdog heartbeat not fresh'}
 $rb=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1080 -ErrorAction SilentlyContinue);$pb=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1081 -ErrorAction SilentlyContinue)
 if($rb.Count-lt1){throw '1080 missing'};if($pb.Count-lt1){throw '1081 missing'}
 if($SampleCount-lt2-or$SampleCount-gt5){throw 'SampleCount must be 2..5'};if($SampleIntervalSeconds-lt45-or$SampleIntervalSeconds-gt120){throw 'SampleIntervalSeconds must be 45..120'}
 $samples=New-Object Collections.ArrayList
 for($i=0;$i-lt$SampleCount;$i++){if($null-eq(Proc $watchdogPid)){throw 'watchdog exited during observation'};[void]$samples.Add((Snapshot $watchdogPid));if($i-lt($SampleCount-1)){Start-Sleep -Seconds $SampleIntervalSeconds}}
 $ra=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1080 -ErrorAction SilentlyContinue);$pa=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1081 -ErrorAction SilentlyContinue)
 if($ra.Count-lt1){throw '1080 lost'};if($pa.Count-lt1){throw '1081 lost'}
 $max=0;foreach($s in @($samples)){if([int]$s.proxifier_descendant_count-gt$max){$max=[int]$s.proxifier_descendant_count}}
 $pass=($max-eq0)
 $res=[ordered]@{schema_version=1;contract_id='PNCC_PROXIFIER_DESCENDANT_QUALIFICATION_V3';source_plane='PRIVATE_RUNTIME';watchdog_identity_source='WU037_REFRESH_EVIDENCE';watchdog_heartbeat_age_seconds=$age;runtime_mutation=$false;reserve_1080_mutation=$false;sample_interval_seconds=$SampleIntervalSeconds;sample_count=$SampleCount;samples=@($samples);max_proxifier_descendants=$max;reserve_1080_listening_before=($rb.Count-gt0);reserve_1080_listening_after=($ra.Count-gt0);primary_1081_listening_before=($pb.Count-gt0);primary_1081_listening_after=($pa.Count-gt0);result=$(if($pass){'PASS'}else{'BLOCKED'});failure_classification=$(if($pass){$null}else{'ENVIRONMENT_OR_BASELINE_BLOCKER'});runtime_authority=$false;promotion_eligible=$false}
 $rp=Join-Path $OutputDirectory 'proxifier-descendant-qualification-result.json';WriteJson $res $rp
 if($pass){Write-Output 'PNCC_PROXIFIER_DESCENDANT_QUALIFICATION_WU038=PASS MAX_DESCENDANTS=0 RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false';Write-Output "RESULT=$rp";Write-Output "LOG_PATH=$log";exit 0}
 Write-Output ("PNCC_PROXIFIER_DESCENDANT_QUALIFICATION_WU038=BLOCKED MAX_DESCENDANTS=$max RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false");Write-Output "RESULT=$rp";Write-Output "LOG_PATH=$log";exit 50
} catch {Write-Output ('PNCC_PROXIFIER_DESCENDANT_QUALIFICATION_WU038=BLOCKED ERROR='+$_.Exception.Message+' RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false');Write-Output "LOG_PATH=$log";exit 50} finally {try{Stop-Transcript|Out-Null}catch{}}
