#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Live','Plan')][string]$Mode='Live',
 [string]$WorkspacePath,
 [string]$StageBAdmissionEvidencePath,
 [string]$V631Path,
 [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-WATCHDOG-BOOTSTRAP-WU054',
 [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$PsExe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$ExpectedV631Sha='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$ExpectedPrimaryPort=1081
$ExpectedReservePort=1080
$StateDir=Join-Path $env:LOCALAPPDATA 'VPS-Control-v6.3'
$Heartbeat=Join-Path $StateDir 'watchdog-heartbeat.json'
function Sha([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
function Proc([int]$ProcessId){try{Get-CimInstance Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction Stop}catch{$null}}
function FileArg([string]$CommandLine){if(-not $CommandLine){return ''};$m=[regex]::Match($CommandLine,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|''([^'']+)''|(\S+))');if(!$m.Success){return ''};foreach($i in 1..3){if($m.Groups[$i].Success){return [string]$m.Groups[$i].Value}};return ''}
function Snap([int]$Port){$r=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $Port -ErrorAction SilentlyContinue);$o=@();foreach($x in $r){$p=Proc ([int]$x.OwningProcess);$o+=[ordered]@{pid=[int]$x.OwningProcess;name=$(if($p){[string]$p.Name}else{''});exe=$(if($p){[string]$p.ExecutablePath}else{''})}};[ordered]@{port=$Port;listening=($r.Count-gt0);owners=@($o|Sort-Object pid)}}
function Key($v){$v|ConvertTo-Json -Depth 8 -Compress}
function WriteJson($v,[string]$p){$d=Split-Path -Parent $p;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($p,($v|ConvertTo-Json -Depth 16),(New-Object Text.UTF8Encoding($true)))}
function Run([string]$f,[string]$a,[int]$sec=120){$o=Join-Path $OutputDirectory ('n-'+[guid]::NewGuid().ToString('N')+'.out');$e=Join-Path $OutputDirectory ('n-'+[guid]::NewGuid().ToString('N')+'.err');$p=Start-Process $f -ArgumentList $a -PassThru -WindowStyle Hidden -RedirectStandardOutput $o -RedirectStandardError $e;if(-not$p.WaitForExit($sec*1000)){try{$p.Kill()}catch{};throw 'native timeout'};$p.Refresh();$so=$(if(Test-Path $o){Get-Content $o -Raw}else{''});$se=$(if(Test-Path $e){Get-Content $e -Raw}else{''});Remove-Item $o,$e -Force -ErrorAction SilentlyContinue;[pscustomobject]@{ExitCode=[int]$p.ExitCode;Stdout=[string]$so;Stderr=[string]$se}}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$log=Join-Path $OutputDirectory 'PNCC-WATCHDOG-BOOTSTRAP-WU054.log'
Start-Transcript $log -Force|Out-Null
try{
 if($Mode -eq 'Plan'){
  if(!$FixturePath -or !(Test-Path -LiteralPath $FixturePath)){throw 'FixturePath required'}
  $f=Get-Content -LiteralPath $FixturePath -Raw|ConvertFrom-Json
  foreach($n in @('stage_b_only_watchdog_blocked','candidate_identity','rollback_identity','reserve_1080_listening','primary_1081_listening','exact_engine_generation','security_contract','watchdog_absent','fresh_heartbeat','listeners_unchanged')){if(-not[bool]$f.$n){throw ('plan fixture failed: '+$n)}}
  Write-Output 'PNCC_WATCHDOG_BOOTSTRAP_WU054=PLAN_PASS RUNTIME_MUTATION=watchdog_bootstrap RESERVE_1080_MUTATION=false PRIMARY_1081_TUNNEL_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false';exit 0
 }
 if($env:OS -ne 'Windows_NT'){throw 'Windows required'}
 if(!$WorkspacePath -or !(Test-Path -LiteralPath $WorkspacePath -PathType Container)){throw 'WorkspacePath missing'}
 if(!$StageBAdmissionEvidencePath -or !(Test-Path -LiteralPath $StageBAdmissionEvidencePath -PathType Leaf)){throw 'StageBAdmissionEvidencePath missing'}
 if(!$V631Path -or !(Test-Path -LiteralPath $V631Path -PathType Leaf)){throw 'V631Path missing'}
 if((Sha $V631Path)-ne$ExpectedV631Sha){throw 'V6.3.1 SHA mismatch'}
 $manifest=Get-Content -LiteralPath (Join-Path $WorkspacePath 'workspace-manifest.json') -Raw|ConvertFrom-Json
 if([int]$manifest.schema_version-ne2-or[string]$manifest.bootstrap_id-ne'PNCC_RUNTIME_WORKSPACE_BOOTSTRAP_V2'){throw 'Stable V2 workspace required'}
 $request=Get-Content -LiteralPath (Join-Path $WorkspacePath 'request\runtime-qualification-request.json') -Raw|ConvertFrom-Json
 if([string]$manifest.request_provider.request_id-ne[string]$request.request_id){throw 'request/workspace mismatch'}
 if([string]$manifest.candidate.candidate_id-ne[string]$request.candidate.candidate_id){throw 'candidate/workspace mismatch'}
 $artifactName=[string]$request.candidate.artifact_filename;$artifactSha=[string]$request.candidate.artifact_sha256;$artifactSize=[long]$request.candidate.artifact_size_bytes
 $artifact=Join-Path (Join-Path $WorkspacePath 'candidate-provider-artifact') $artifactName
 if(!(Test-Path -LiteralPath $artifact -PathType Leaf)){throw 'candidate artifact missing'}
 $ai=Get-Item -LiteralPath $artifact;if([long]$ai.Length-ne$artifactSize-or(Sha $artifact)-ne$artifactSha){throw 'candidate identity mismatch'}
 $ev=Get-Content -LiteralPath $StageBAdmissionEvidencePath -Raw|ConvertFrom-Json
 if([string]$ev.contract_id-ne'PNCC_RUNTIME_STAGE_B_ADMISSION_EVIDENCE_V2'){throw 'Stage-B V2 evidence required'}
 $expectedFalse=@('watchdog_exact_engine','watchdog_fresh','watchdog_present')|Sort-Object
 $actualFalse=@($ev.checks.PSObject.Properties|Where-Object{-not[bool]$_.Value}|ForEach-Object{$_.Name}|Sort-Object)
 if(($actualFalse-join'|')-ne($expectedFalse-join'|')){throw ('Stage-B blocker shape mismatch: '+($actualFalse-join','))}
 foreach($p in $ev.checks.PSObject.Properties){if($p.Name -notin $expectedFalse-and-not[bool]$p.Value){throw ('non-watchdog Stage-B check failed: '+$p.Name)}}
 $reserveBefore=Snap $ExpectedReservePort;$primaryBefore=Snap $ExpectedPrimaryPort
 if(-not$reserveBefore.listening){throw '1080 reserve missing'};if(-not$primaryBefore.listening){throw '1081 primary missing'}
 $stage=Join-Path $OutputDirectory 'candidate-stage';Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue;New-Item -ItemType Directory -Force -Path $stage|Out-Null
 Expand-Archive -LiteralPath $artifact -DestinationPath $stage -Force
 $upgrade=@(Get-ChildItem -LiteralPath $stage -Filter 'VPS-Control-v7-engine-upgrade.ps1' -File -Recurse|Select-Object -First 1);if($upgrade.Count-ne1){throw 'generator missing'}
 $candidateRoot=Split-Path -Parent $upgrade[0].FullName;$sourceCopy=Join-Path $candidateRoot 'VPS-Control-v6.3.1.ps1';Copy-Item -LiteralPath $V631Path -Destination $sourceCopy -Force
 $generated=Join-Path $candidateRoot 'VPS-Control-v6.5.ps1';$gr=Run $PsExe ('-NoLogo -NoProfile -ExecutionPolicy Bypass -File "'+$upgrade[0].FullName+'" -SourcePath "'+$sourceCopy+'" -DestinationPath "'+$generated+'"')
 if($gr.ExitCode-ne0-or!(Test-Path -LiteralPath $generated -PathType Leaf)){throw 'exact engine generation failed'}
 $generatedSha=Sha $generated;$raw=Get-Content -LiteralPath $generated -Raw
 if($raw-notmatch '(?i)-pwfile'){throw 'generated engine lacks -pwfile'}
 if($raw-match '(?i)\$arguments\s*\+=\s*@\(\s*["'']-pw["'']'){throw 'generated engine constructs plaintext -pw'}
 if($raw-notmatch 'Ensure-V7OfficialPuttyHostKeyTrust'){throw 'generated engine lacks host-key fail-closed contract'}
 $runtimeDir=Split-Path -Parent $V631Path;$installed=Join-Path $runtimeDir 'VPS-Control-v6.5.ps1';$oldSha=$(if(Test-Path -LiteralPath $installed){Sha $installed}else{''})
 $all=@(Get-CimInstance Win32_Process -ErrorAction Stop);foreach($p in @($all|Where-Object{[string]$_.Name-match'(?i)^powershell\.exe$'})){$cmd=[string]$p.CommandLine;if($cmd-match'(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)'){throw 'Watchdog concurrency detected; bootstrap refused'}}
 Copy-Item -LiteralPath $generated -Destination $installed -Force;if((Sha $installed)-ne$generatedSha){throw 'installed exact engine SHA mismatch'}
 $moduleSource=Join-Path $candidateRoot 'VPS-Control-v6.5-modules.json';$moduleInstalled=Join-Path $runtimeDir 'VPS-Control-v6.5-modules.json';if(Test-Path -LiteralPath $moduleSource -PathType Leaf){Copy-Item -LiteralPath $moduleSource -Destination $moduleInstalled -Force;if((Sha $moduleSource)-ne(Sha $moduleInstalled)){throw 'module catalog install mismatch'}}
 $wd=Start-Process $PsExe -ArgumentList ('-NoLogo -NoProfile -ExecutionPolicy Bypass -File "'+$installed+'" -Action Watchdog -WatchIntervalSeconds 45 -NoAppLaunch') -WindowStyle Hidden -PassThru
 $fresh=$false;$age=-1;$deadline=(Get-Date).AddSeconds(90);while((Get-Date)-lt$deadline){Start-Sleep 2;$wp=Proc ([int]$wd.Id);if($null-eq$wp){break};if(Test-Path -LiteralPath $Heartbeat){$age=[int]((Get-Date)-(Get-Item -LiteralPath $Heartbeat).LastWriteTime).TotalSeconds;if($age-ge0-and$age-le15){$fresh=$true;break}}}
 if(-not$fresh){throw 'fresh watchdog heartbeat not established'}
 $live=Proc ([int]$wd.Id);if($null-eq$live){throw 'fresh watchdog exited'};$cmdLive=[string]$live.CommandLine;if($cmdLive-notmatch'(?i)(?:^|\s)-Action\s+Watchdog(?:\s|$)'){throw 'fresh process is not Watchdog action'};$fileLive=FileArg $cmdLive;if(!$fileLive-or(Sha $fileLive)-ne$generatedSha){throw 'fresh watchdog exact engine mismatch'}
 $reserveAfter=Snap $ExpectedReservePort;$primaryAfter=Snap $ExpectedPrimaryPort
 if((Key $reserveBefore)-ne(Key $reserveAfter)){throw 'CRITICAL 1080 snapshot changed'}
 if((Key $primaryBefore)-ne(Key $primaryAfter)){throw 'CRITICAL 1081 snapshot changed'}
 $result=[ordered]@{schema_version=1;contract_id='PNCC_WATCHDOG_BOOTSTRAP_FROM_STAGE_B_V1';request_id=[string]$request.request_id;candidate_id=[string]$request.candidate.candidate_id;runtime_mutation='watchdog_bootstrap';engine_install_mutation=($oldSha-ne$generatedSha);reserve_1080_mutation=$false;primary_1081_tunnel_mutation=$false;old_engine_sha256=$oldSha;installed_engine_sha256=$generatedSha;fresh_watchdog_pid=[int]$wd.Id;heartbeat_age_seconds=$age;reserve_before=$reserveBefore;reserve_after=$reserveAfter;primary_before=$primaryBefore;primary_after=$primaryAfter;result='PASS';runtime_authority=$false;promotion_eligible=$false}
 $rp=Join-Path $OutputDirectory 'watchdog-bootstrap-result.json';WriteJson $result $rp
 Write-Output ('PNCC_WATCHDOG_BOOTSTRAP_WU054=PASS ENGINE_INSTALL_MUTATION='+[string]$result.engine_install_mutation+' HEARTBEAT_AGE='+$age+' RUNTIME_MUTATION=watchdog_bootstrap RESERVE_1080_MUTATION=false PRIMARY_1081_TUNNEL_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false');Write-Output "RESULT=$rp";Write-Output "LOG_PATH=$log";exit 0
}catch{Write-Output ('PNCC_WATCHDOG_BOOTSTRAP_WU054=BLOCKED ERROR='+$_.Exception.Message+' RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false');Write-Output "LOG_PATH=$log";exit 50}finally{try{Stop-Transcript|Out-Null}catch{}}
