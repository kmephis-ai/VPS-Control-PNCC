#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Live','Plan')][string]$Mode='Live',
 [string]$Wu028ResultPath,
 [string]$V631Path,
 [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-WATCHDOG-REFRESH-WU037',
 [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$PsExe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$Heartbeat=Join-Path (Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3') 'watchdog-heartbeat.json'
function Sha([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
function Proc([int]$ProcessId){try{Get-CimInstance Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction Stop}catch{$null}}
function FileArg([string]$CommandLine){if(-not $CommandLine){return ''};$m=[regex]::Match($CommandLine,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|''([^'']+)''|(\S+))');if(!$m.Success){return ''};foreach($i in 1..3){if($m.Groups[$i].Success){return [string]$m.Groups[$i].Value}};return ''}
function Snap([int]$Port){$r=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $Port -ErrorAction SilentlyContinue);$o=@();foreach($x in $r){$p=Proc ([int]$x.OwningProcess);$o+=[ordered]@{pid=[int]$x.OwningProcess;name=$(if($p){[string]$p.Name}else{''});exe=$(if($p){[string]$p.ExecutablePath}else{''})}};[ordered]@{port=$Port;listening=($r.Count-gt0);owners=@($o|Sort-Object pid)}}
function Key($v){$v|ConvertTo-Json -Depth 8 -Compress}
function WriteJson($v,[string]$p){$d=Split-Path -Parent $p;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($p,($v|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($true)))}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$log=Join-Path $OutputDirectory 'PNCC-WATCHDOG-REFRESH-WU037.log'
Start-Transcript $log -Force|Out-Null
try {
 if($Mode -eq 'Plan'){
   if(!$FixturePath -or !(Test-Path -LiteralPath $FixturePath)){throw 'FixturePath required'}
   $f=Get-Content -LiteralPath $FixturePath -Raw|ConvertFrom-Json
   foreach($n in @('wu028_pass','exact_engine','reserve_1080_listening','primary_1081_listening','stale_watchdog_exact_owned','watchdog_only_mutation','fresh_heartbeat','listeners_unchanged')){if(-not [bool]$f.$n){throw ('plan fixture failed: '+$n)}}
   Write-Output 'PNCC_WATCHDOG_REFRESH_WU037=PLAN_PASS RUNTIME_MUTATION=watchdog_only RESERVE_1080_MUTATION=false TUNNEL_MUTATION=false PROXIFIER_MUTATION=false'
   exit 0
 }
 if($env:OS -ne 'Windows_NT'){throw 'Windows required'}
 if(!$Wu028ResultPath -or !(Test-Path -LiteralPath $Wu028ResultPath -PathType Leaf)){throw 'Wu028ResultPath missing'}
 if(!$V631Path -or !(Test-Path -LiteralPath $V631Path -PathType Leaf)){throw 'V631Path missing'}
 $wu=Get-Content -LiteralPath $Wu028ResultPath -Raw|ConvertFrom-Json
 if([string]$wu.contract_id -ne 'PNCC_PRIMARY_1081_DPAPI_RECOVERY_V1' -or [string]$wu.state -ne 'PASS'){throw 'WU028 prerequisite mismatch'}
 $expectedSha=[string]$wu.installed_engine_sha256;if([string]::IsNullOrWhiteSpace($expectedSha)){throw 'WU028 installed engine SHA missing'}
 $runtimeDir=Split-Path -Parent $V631Path;$engine=Join-Path $runtimeDir 'VPS-Control-v6.5.ps1'
 if(!(Test-Path -LiteralPath $engine -PathType Leaf)){throw 'installed V6.5 engine missing'}
 if((Sha $engine) -ne $expectedSha.ToLowerInvariant()){throw 'installed V6.5 engine identity mismatch'}
 $reserveBefore=Snap 1080;$primaryBefore=Snap 1081
 if(-not $reserveBefore.listening){throw '1080 reserve missing'};if(-not $primaryBefore.listening){throw '1081 primary missing'}
 $all=@(Get-CimInstance Win32_Process -ErrorAction Stop)
 $owned=New-Object Collections.ArrayList
 foreach($p in @($all|Where-Object{[string]$_.Name -match '(?i)^powershell\.exe$'})){
   $cmd=[string]$p.CommandLine
   if($cmd -notmatch '(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)'){continue}
   $file=FileArg $cmd;if(!$file){continue}
   try{$full=[IO.Path]::GetFullPath($file)}catch{continue}
   if(-not [string]::Equals($full,[IO.Path]::GetFullPath($engine),[StringComparison]::OrdinalIgnoreCase)){continue}
   if(!(Test-Path -LiteralPath $full -PathType Leaf)){continue}
   if((Sha $full) -ne $expectedSha.ToLowerInvariant()){throw 'owned watchdog file hash mismatch'}
   [void]$owned.Add([int]$p.ProcessId)
 }
 $ageBefore=-1;if(Test-Path -LiteralPath $Heartbeat){$ageBefore=[int]((Get-Date)-(Get-Item -LiteralPath $Heartbeat).LastWriteTime).TotalSeconds}
 foreach($processId in @($owned)){Stop-Process -Id $processId -Force -ErrorAction Stop}
 Start-Sleep -Milliseconds 500
 foreach($processId in @($owned)){if($null -ne (Proc $processId)){throw 'exact-owned stale watchdog did not stop'}}
 $wd=Start-Process $PsExe -ArgumentList ('-NoLogo -NoProfile -ExecutionPolicy Bypass -File "'+$engine+'" -Action Watchdog -WatchIntervalSeconds 45 -NoAppLaunch') -WindowStyle Hidden -PassThru
 $fresh=$false;$ageAfter=-1;$deadline=(Get-Date).AddSeconds(90)
 while((Get-Date)-lt$deadline){Start-Sleep 2;$wp=Proc ([int]$wd.Id);if($null-eq$wp){break};if(Test-Path -LiteralPath $Heartbeat){$ageAfter=[int]((Get-Date)-(Get-Item -LiteralPath $Heartbeat).LastWriteTime).TotalSeconds;if($ageAfter-ge0-and$ageAfter-le15){$fresh=$true;break}}}
 if(!$fresh){throw 'fresh watchdog heartbeat not established'}
 $live=Proc ([int]$wd.Id);if($null-eq$live){throw 'fresh watchdog exited'};$cmdLive=[string]$live.CommandLine
 if($cmdLive -notmatch '(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)'){throw 'fresh process is not watchdog action'}
 $fileLive=FileArg $cmdLive;if(!$fileLive -or (Sha $fileLive)-ne$expectedSha.ToLowerInvariant()){throw 'fresh watchdog engine mismatch'}
 $reserveAfter=Snap 1080;$primaryAfter=Snap 1081
 if((Key $reserveBefore)-ne(Key $reserveAfter)){throw 'CRITICAL 1080 snapshot changed'}
 if((Key $primaryBefore)-ne(Key $primaryAfter)){throw 'CRITICAL 1081 snapshot changed'}
 $res=[ordered]@{schema_version=1;contract_id='PNCC_WATCHDOG_REFRESH_V1';source_plane='PRIVATE_RUNTIME';runtime_mutation='watchdog_only';reserve_1080_mutation=$false;primary_1081_tunnel_mutation=$false;proxifier_mutation=$false;exact_engine_sha256=$expectedSha;stopped_exact_owned_watchdogs=$owned.Count;fresh_watchdog_pid=[int]$wd.Id;heartbeat_age_before_seconds=$ageBefore;heartbeat_age_after_seconds=$ageAfter;reserve_before=$reserveBefore;reserve_after=$reserveAfter;primary_before=$primaryBefore;primary_after=$primaryAfter;result='PASS';runtime_authority=$false;promotion_eligible=$false}
 $rp=Join-Path $OutputDirectory 'watchdog-refresh-result.json';WriteJson $res $rp
 Write-Output ('PNCC_WATCHDOG_REFRESH_WU037=PASS STOPPED_EXACT_WATCHDOGS='+$owned.Count+' HEARTBEAT_AGE='+$ageAfter+' RUNTIME_MUTATION=watchdog_only RESERVE_1080_MUTATION=false TUNNEL_MUTATION=false PROXIFIER_MUTATION=false')
 Write-Output "RESULT=$rp";Write-Output "LOG_PATH=$log";exit 0
} catch {
 Write-Output ('PNCC_WATCHDOG_REFRESH_WU037=BLOCKED ERROR='+$_.Exception.Message+' RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
 Write-Output "LOG_PATH=$log";exit 50
} finally {try{Stop-Transcript|Out-Null}catch{}}
