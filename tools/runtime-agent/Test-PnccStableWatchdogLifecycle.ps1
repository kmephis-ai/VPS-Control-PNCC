#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Fixture','LiveObservation')][string]$Mode='Fixture',
    [string]$FixturePath,
    [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-STABLE-WATCHDOG-LIFECYCLE',
    [ValidateRange(2,120)][int]$ObservationSeconds=6
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$ExpectedEngineSha='843c006b896607da19406998b54d4e6897fa8eb62d3e6bc92cc77255fe4833cf'
$StateDir=Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3'
$PidFile=Join-Path $StateDir 'watchdog.pid'
$Heartbeat=Join-Path $StateDir 'watchdog-heartbeat.json'
function WriteJson($Value,[string]$Path){$d=Split-Path -Parent $Path;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 16),(New-Object Text.UTF8Encoding($true)))}
function Proc([int]$ProcessId){if($ProcessId-le0){return $null};try{Get-CimInstance Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction Stop}catch{$null}}
function FileArg([string]$Cmd){if(-not$Cmd){return ''};$m=[regex]::Match($Cmd,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|''([^'']+)''|(\S+))');if(-not$m.Success){return ''};foreach($i in 1..3){if($m.Groups[$i].Success){return [string]$m.Groups[$i].Value}};return ''}
function Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Fingerprint([string]$Cmd){if([string]::IsNullOrWhiteSpace($Cmd)){return ''};$s=[regex]::Replace($Cmd,'(?i)(-pwfile\s+)(?:"[^"]*"|''[^'']*''|\S+)','$1<redacted-path>');$s=[regex]::Replace($s,'(?i)(-pw\s+)(?:"[^"]*"|''[^'']*''|\S+)','$1<redacted>');$b=[Text.Encoding]::UTF8.GetBytes($s);$h=[Security.Cryptography.SHA256]::Create();try{return([BitConverter]::ToString($h.ComputeHash($b))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
function Snap([int]$Port){$r=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $Port -ErrorAction SilentlyContinue);[ordered]@{port=$Port;listening=($r.Count-gt0);listener_count=$r.Count;owner_pids=@($r|ForEach-Object{[int]$_.OwningProcess}|Sort-Object)}}
function Key($Value){$Value|ConvertTo-Json -Depth 8 -Compress}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$resultPath=Join-Path $OutputDirectory 'stable-watchdog-lifecycle-result.json'
if($Mode-ceq'Fixture'){
    if(-not$FixturePath-or-not(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
    $f=Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8|ConvertFrom-Json
    $checks=[ordered]@{
        registered_single_watchdog=[bool]$f.registered_single_watchdog
        exact_watchdog_action=[bool]$f.exact_watchdog_action
        exact_stable_engine=[bool]$f.exact_stable_engine
        heartbeat_fresh=[bool]$f.heartbeat_fresh
        heartbeat_advances=[bool]$f.heartbeat_advances
        exact_identity_revalidation_required=[bool]$f.exact_identity_revalidation_required
        reserve_1080_untouched=[bool]$f.reserve_1080_untouched
        primary_1081_observation_only=[bool]$f.primary_1081_observation_only
        broad_process_kill_forbidden=[bool]$f.broad_process_kill_forbidden
        plaintext_pw_forbidden=[bool]$f.plaintext_pw_forbidden
        hostkey_bypass_forbidden=[bool]$f.hostkey_bypass_forbidden
        owner_one_shot_required=[bool]$f.owner_one_shot_required
        runtime_authority_false=[bool]$f.runtime_authority_false
        promotion_eligible_false=[bool]$f.promotion_eligible_false
    }
    $failed=@($checks.GetEnumerator()|Where-Object{-not[bool]$_.Value}|ForEach-Object{$_.Key})
    $ok=($failed.Count-eq0)
    $r=[ordered]@{schema_version=1;contract_id='PNCC_STABLE_WATCHDOG_LIFECYCLE_V1';mode='Fixture';state=$(if($ok){'WATCHDOG_LIFECYCLE_CONTRACT_ADMITTED'}else{'BLOCKED'});checks=$checks;failed_checks=$failed;physical_execution_allowed=$false;runtime_mutation=$false;reserve_1080_mutation=$false;primary_1081_tunnel_mutation=$false;runtime_authority=$false;promotion_eligible=$false}
    WriteJson $r $resultPath
    Write-Output ('PNCC_STABLE_WATCHDOG_LIFECYCLE='+$r.state+' PHYSICAL_EXECUTION_ALLOWED=false RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
    if($ok){exit 0}else{exit 50}
}
if($env:OS-cne'Windows_NT'){throw 'LiveObservation requires Windows'}
$reserveBefore=Snap 1080;$primaryBefore=Snap 1081
if(-not$reserveBefore.listening){throw '1080 reserve is not listening'}
if(-not$primaryBefore.listening){throw '1081 primary is not listening'}
if(-not(Test-Path -LiteralPath $PidFile -PathType Leaf)){throw 'watchdog pid registration missing'}
$watchdogPid=[int](Get-Content -LiteralPath $PidFile -Raw).Trim();$p1=Proc $watchdogPid
if($null-eq$p1){throw 'registered watchdog process missing'}
$cmd1=[string]$p1.CommandLine
if($cmd1-notmatch'(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)'){throw 'registered process is not exact Watchdog action'}
$engine=FileArg $cmd1;if(-not$engine-or-not(Test-Path -LiteralPath $engine -PathType Leaf)){throw 'watchdog engine path missing'}
if((Sha $engine)-cne$ExpectedEngineSha){throw 'watchdog engine SHA mismatch'}
if(-not(Test-Path -LiteralPath $Heartbeat -PathType Leaf)){throw 'watchdog heartbeat missing'}
$hb1=Get-Item -LiteralPath $Heartbeat;$hb1Time=$hb1.LastWriteTimeUtc;$age1=[int]((Get-Date).ToUniversalTime()-$hb1Time).TotalSeconds
if($age1-lt0-or$age1-gt240){throw 'watchdog heartbeat stale'}
$fp1=Fingerprint $cmd1
Start-Sleep -Seconds $ObservationSeconds
$p2=Proc $watchdogPid;if($null-eq$p2){throw 'watchdog process disappeared during observation'}
$cmd2=[string]$p2.CommandLine;$engine2=FileArg $cmd2
if((Fingerprint $cmd2)-cne$fp1-or$engine2-cne$engine-or(Sha $engine2)-cne$ExpectedEngineSha){throw 'watchdog exact identity changed during observation'}
$hb2=Get-Item -LiteralPath $Heartbeat;$hb2Time=$hb2.LastWriteTimeUtc;$age2=[int]((Get-Date).ToUniversalTime()-$hb2Time).TotalSeconds
if($hb2Time-le$hb1Time){throw 'watchdog heartbeat did not advance'}
if($age2-lt0-or$age2-gt240){throw 'watchdog heartbeat not fresh after observation'}
$reserveAfter=Snap 1080;$primaryAfter=Snap 1081
if((Key $reserveBefore)-cne(Key $reserveAfter)){throw 'CRITICAL 1080 snapshot changed during read-only observation'}
if((Key $primaryBefore)-cne(Key $primaryAfter)){throw '1081 snapshot changed during read-only observation'}
$r=[ordered]@{schema_version=1;contract_id='PNCC_STABLE_WATCHDOG_LIFECYCLE_V1';mode='LiveObservation';state='WATCHDOG_OBSERVATION_ADMITTED';watchdog_pid=$watchdogPid;watchdog_fingerprint=$fp1;exact_engine_sha256=$ExpectedEngineSha;heartbeat_advanced=$true;heartbeat_age_before_seconds=$age1;heartbeat_age_after_seconds=$age2;reserve_1080_unchanged=$true;primary_1081_unchanged=$true;physical_execution_allowed=$false;runtime_mutation=$false;reserve_1080_mutation=$false;primary_1081_tunnel_mutation=$false;runtime_authority=$false;promotion_eligible=$false}
WriteJson $r $resultPath
Write-Output 'PNCC_STABLE_WATCHDOG_LIFECYCLE=WATCHDOG_OBSERVATION_ADMITTED PHYSICAL_EXECUTION_ALLOWED=false RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false PRIMARY_1081_TUNNEL_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false'
Write-Output ('RESULT='+$resultPath)
exit 0
