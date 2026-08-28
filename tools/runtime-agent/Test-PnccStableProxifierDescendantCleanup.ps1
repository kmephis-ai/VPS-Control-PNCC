#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Fixture','LiveObservation')][string]$Mode='Fixture',
    [string]$FixturePath,
    [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-STABLE-PROXIFIER-DESCENDANT-CLEANUP',
    [int]$SampleCount=3,
    [int]$SampleIntervalSeconds=50
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
function ReadHeartbeat(){if(-not(Test-Path -LiteralPath $Heartbeat -PathType Leaf)){throw 'watchdog heartbeat missing'};$hb=Get-Content -LiteralPath $Heartbeat -Raw|ConvertFrom-Json;if(-not$hb.Timestamp-or-not$hb.Pid){throw 'watchdog heartbeat Pid/Timestamp missing'};$ts=[datetime]$hb.Timestamp;[pscustomobject]@{Timestamp=$ts;Pid=[int]$hb.Pid;AgeSeconds=[int][math]::Round(((Get-Date)-$ts).TotalSeconds)}}
function Ancestors([object]$P,[hashtable]$ById,[int]$MaxDepth=16){$ids=@();$seen=@{};$cur=[int]$P.ParentProcessId;for($i=0;$i-lt$MaxDepth-and$cur-gt0;$i++){if($seen.ContainsKey($cur)){break};$seen[$cur]=$true;$ids+=$cur;if(-not$ById.ContainsKey($cur)){break};$cur=[int]$ById[$cur].ParentProcessId};@($ids)}
function DescendantSnapshot([int]$WatchdogPid){$all=@(Get-CimInstance Win32_Process -ErrorAction Stop);$by=@{};foreach($p in $all){$by[[int]$p.ProcessId]=$p};$prox=@($all|Where-Object{[string]$_.Name -ieq 'Proxifier.exe'});$desc=@();foreach($p in $prox){$anc=@(Ancestors $p $by);if($anc-contains$WatchdogPid){$desc+=[ordered]@{pid=[int]$p.ProcessId;parent_pid=[int]$p.ParentProcessId;command_fingerprint=Fingerprint ([string]$p.CommandLine)}}};[ordered]@{timestamp=(Get-Date).ToString('o');all_proxifier_count=$prox.Count;proxifier_descendant_count=$desc.Count;descendants=@($desc)}}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$resultPath=Join-Path $OutputDirectory 'stable-proxifier-descendant-cleanup-result.json'
if($Mode-ceq'Fixture'){
    if(-not$FixturePath-or-not(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
    $f=Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8|ConvertFrom-Json
    $checks=[ordered]@{wu070_watchdog_pass=[bool]$f.wu070_watchdog_pass;exact_watchdog_identity=[bool]$f.exact_watchdog_identity;heartbeat_pid_bound=[bool]$f.heartbeat_pid_bound;zero_descendants_required=[bool]$f.zero_descendants_required;parentage_observation_only=[bool]$f.parentage_observation_only;legacy_rc_not_authority=[bool]$f.legacy_rc_not_authority;reserve_1080_untouched=[bool]$f.reserve_1080_untouched;primary_1081_observation_only=[bool]$f.primary_1081_observation_only;broad_process_kill_forbidden=[bool]$f.broad_process_kill_forbidden;runtime_authority_false=[bool]$f.runtime_authority_false;promotion_eligible_false=[bool]$f.promotion_eligible_false}
    $failed=@($checks.GetEnumerator()|Where-Object{-not[bool]$_.Value}|ForEach-Object{$_.Key});$ok=($failed.Count-eq0)
    $r=[ordered]@{schema_version=1;contract_id='PNCC_STABLE_PROXIFIER_DESCENDANT_CLEANUP_V1';mode='Fixture';state=$(if($ok){'PROXIFIER_DESCENDANT_CONTRACT_ADMITTED'}else{'BLOCKED'});checks=$checks;failed_checks=$failed;physical_cleanup_allowed=$false;parentage_is_authority=$false;runtime_mutation=$false;reserve_1080_mutation=$false;primary_1081_tunnel_mutation=$false;runtime_authority=$false;promotion_eligible=$false}
    WriteJson $r $resultPath;Write-Output ('PNCC_STABLE_PROXIFIER_DESCENDANT_CLEANUP='+$r.state+' RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false');if($ok){exit 0}else{exit 50}
}
if($env:OS-cne'Windows_NT'){throw 'LiveObservation requires Windows'}
if($SampleCount-lt2-or$SampleCount-gt5){throw 'SampleCount must be 2..5'};if($SampleIntervalSeconds-lt45-or$SampleIntervalSeconds-gt120){throw 'SampleIntervalSeconds must be 45..120'}
$reserveBefore=Snap 1080;$primaryBefore=Snap 1081;if(-not$reserveBefore.listening){throw '1080 reserve is not listening'};if(-not$primaryBefore.listening){throw '1081 primary is not listening'}
if(-not(Test-Path -LiteralPath $PidFile -PathType Leaf)){throw 'watchdog pid registration missing'};$watchdogPid=[int](Get-Content -LiteralPath $PidFile -Raw).Trim();$wp=Proc $watchdogPid;if($null-eq$wp){throw 'registered Watchdog missing'};$cmd=[string]$wp.CommandLine;if($cmd-notmatch'(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)'){throw 'registered process is not exact Watchdog action'};$engine=FileArg $cmd;if(-not$engine-or-not(Test-Path -LiteralPath $engine -PathType Leaf)-or(Sha $engine)-cne$ExpectedEngineSha){throw 'exact Stable Watchdog engine mismatch'};$hb=ReadHeartbeat;if($hb.Pid-ne$watchdogPid-or$hb.AgeSeconds-lt0-or$hb.AgeSeconds-gt240){throw 'Watchdog heartbeat binding/freshness failed'}
$watchFp=Fingerprint $cmd;$samples=@();for($i=0;$i-lt$SampleCount;$i++){if($null-eq(Proc $watchdogPid)){throw 'Watchdog exited during observation'};$cur=Proc $watchdogPid;if((Fingerprint ([string]$cur.CommandLine))-cne$watchFp){throw 'Watchdog identity changed during observation'};$samples+=DescendantSnapshot $watchdogPid;if($i-lt($SampleCount-1)){Start-Sleep -Seconds $SampleIntervalSeconds}}
$reserveAfter=Snap 1080;$primaryAfter=Snap 1081;if((Key $reserveBefore)-cne(Key $reserveAfter)){throw 'CRITICAL 1080 snapshot changed during read-only observation'};if((Key $primaryBefore)-cne(Key $primaryAfter)){throw '1081 snapshot changed during read-only observation'}
$max=0;foreach($s in $samples){if([int]$s.proxifier_descendant_count-gt$max){$max=[int]$s.proxifier_descendant_count}};$pass=($max-eq0)
$r=[ordered]@{schema_version=1;contract_id='PNCC_STABLE_PROXIFIER_DESCENDANT_CLEANUP_V1';mode='LiveObservation';state=$(if($pass){'PROXIFIER_DESCENDANT_CLEAN_PASS'}else{'PROXIFIER_DESCENDANTS_PRESENT'});exact_engine_sha256=$ExpectedEngineSha;heartbeat_pid_bound=$true;sample_count=$SampleCount;sample_interval_seconds=$SampleIntervalSeconds;max_proxifier_descendants=$max;samples=$samples;reserve_1080_unchanged=$true;primary_1081_unchanged=$true;parentage_is_authority=$false;physical_cleanup_allowed=$false;runtime_mutation=$false;reserve_1080_mutation=$false;primary_1081_tunnel_mutation=$false;runtime_authority=$false;promotion_eligible=$false}
WriteJson $r $resultPath;Write-Output ('PNCC_STABLE_PROXIFIER_DESCENDANT_CLEANUP='+$r.state+' MAX_DESCENDANTS='+$max+' RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false PRIMARY_1081_TUNNEL_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false');Write-Output ('RESULT='+$resultPath);if($pass){exit 0}else{exit 50}
