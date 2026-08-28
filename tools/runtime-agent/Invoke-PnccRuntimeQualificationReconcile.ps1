#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Live','Plan')][string]$Mode='Live',
 [string]$StageAResultPath,
 [string]$Wu030Root,
 [string]$V631Path,
 [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-RUNTIME-QUALIFICATION-RECONCILE-WU031',
 [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$ExpectedV631Sha='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$Scopes=@('WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','WATCHDOG_LIFECYCLE','PROXIFIER_DESCENDANT_CLEANUP','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080','CREDENTIAL_HOSTKEY','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY')
function Sha([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
function WriteJson($v,[string]$p){$d=Split-Path -Parent $p;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($p,($v|ConvertTo-Json -Depth 16),(New-Object Text.UTF8Encoding($true)))}
function GetCheck($src,[string]$scope){@($src.checks|Where-Object{[string]$_.scope -eq $scope}|Select-Object -First 1)}
function AddCheck([System.Collections.ArrayList]$list,[string]$scope,[string]$result,[string]$source){[void]$list.Add([ordered]@{scope=$scope;result=$result;exit_code=0;failure_class=$null;evidence_refs=@($source)})}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$log=Join-Path $OutputDirectory 'PNCC-RUNTIME-QUALIFICATION-RECONCILE-WU031.log'
Start-Transcript $log -Force|Out-Null
try{
 if($Mode -eq 'Plan'){
  if(!$FixturePath -or !(Test-Path -LiteralPath $FixturePath)){throw 'FixturePath required'}
  $f=Get-Content -LiteralPath $FixturePath -Raw|ConvertFrom-Json
  foreach($n in @('stage_a_six_pass','wu030_pass','wu029_pass','wu028_pass','dpapi_pass','pwfile_only','watchdog_pass','network_pass','reserve_unchanged','rollback_pass','proxifier_not_executed')){if(-not [bool]$f.$n){throw "plan fixture failed: $n"}}
  Write-Output 'PNCC_RUNTIME_QUALIFICATION_RECONCILE=PLAN_PASS RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false'
  exit 0
 }
 if(!$StageAResultPath -or !(Test-Path -LiteralPath $StageAResultPath -PathType Leaf)){throw 'StageAResultPath missing'}
 if(!$Wu030Root -or !(Test-Path -LiteralPath $Wu030Root -PathType Container)){throw 'Wu030Root missing'}
 if(!$V631Path -or !(Test-Path -LiteralPath $V631Path -PathType Leaf)){throw 'V631Path missing'}
 if((Sha $V631Path) -ne $ExpectedV631Sha){throw 'immutable V6.3.1 identity mismatch'}
 $stage=Get-Content -LiteralPath $StageAResultPath -Raw|ConvertFrom-Json
 if([string]$stage.contract_id -ne 'PNCC_RUNTIME_QUALIFICATION_RESULT_V1'){throw 'Stage-A contract mismatch'}
 if([string]$stage.producer.source_plane -ne 'PRIVATE_RUNTIME'){throw 'Stage-A source plane mismatch'}
 foreach($s in @('WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY')){$c=GetCheck $stage $s;if($c.Count -ne 1 -or [string]$c[0].result -ne 'PASS'){throw "Stage-A required PASS missing: $s"}}
 $wu29=Join-Path $Wu030Root 'wu029\putty-085-admission-result.json'
 $wu28=Join-Path $Wu030Root 'wu029\wu028-resume\primary-1081-dpapi-recovery-result.json'
 $wu30log=Join-Path $Wu030Root 'PNCC-PUTTY-085-TRACE-FIX-WU030.log'
 foreach($p in @($wu29,$wu28,$wu30log)){if(!(Test-Path -LiteralPath $p -PathType Leaf)){throw ('WU030 evidence missing: '+[IO.Path]::GetFileName($p))}}
 $r29=Get-Content -LiteralPath $wu29 -Raw|ConvertFrom-Json;$r28=Get-Content -LiteralPath $wu28 -Raw|ConvertFrom-Json;$l30=Get-Content -LiteralPath $wu30log -Raw
 if([string]$r29.contract_id -ne 'PNCC_PUTTY_085_ADMISSION_V1' -or [string]$r29.recovery -ne 'PASS' -or -not [bool]$r29.authenticode_valid -or -not [bool]$r29.pwfile_capability -or [bool]$r29.reserve_1080_mutation){throw 'WU029 evidence invalid'}
 if([string]$r28.contract_id -ne 'PNCC_PRIMARY_1081_DPAPI_RECOVERY_V1' -or [string]$r28.state -ne 'PASS' -or -not [bool]$r28.dpapi_decryptable -or -not [bool]$r28.routed_identity_match -or [bool]$r28.reserve_1080_mutation){throw 'WU028 evidence invalid'}
 if(-not $l30.Contains('PNCC_PUTTY_085_TRACE_FIX=PASS')){throw 'WU030 PASS marker missing'}
 $secure=@($r28.steps|Where-Object{[string]$_.step -eq 'secure_1081'}|Select-Object -First 1);$watch=@($r28.steps|Where-Object{[string]$_.step -eq 'watchdog'}|Select-Object -First 1)
 if($secure.Count-ne1 -or [string]$secure[0].result-ne'PASS' -or -not [bool]$secure[0].pwfile -or [bool]$secure[0].plain_pw){throw 'secure 1081 evidence invalid'}
 if($watch.Count-ne1 -or [string]$watch[0].result-ne'PASS' -or [int]$watch[0].heartbeat_age_seconds -gt 15){throw 'watchdog evidence invalid'}
 $reserveLive=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1080 -ErrorAction SilentlyContinue);$primaryLive=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1081 -ErrorAction SilentlyContinue)
 if($reserveLive.Count -lt 1){throw '1080 reserve live observation missing'};if($primaryLive.Count -lt 1){throw '1081 primary live observation missing'}
 $checks=New-Object Collections.ArrayList
 foreach($s in @('WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY')){AddCheck $checks $s 'PASS' 'stage-a'}
 AddCheck $checks 'WATCHDOG_LIFECYCLE' 'PASS' 'wu028-recovery'
 AddCheck $checks 'CREDENTIAL_HOSTKEY' 'PASS' 'wu028+wu029'
 AddCheck $checks 'PROXIFIER_DESCENDANT_CLEANUP' 'NOT_EXECUTED' 'none'
 $ordered=@();foreach($s in $Scopes){$ordered+=@($checks|Where-Object{$_.scope-eq$s}|Select-Object -First 1)}
 $result=[ordered]@{schema_version=1;contract_id='PNCC_RUNTIME_QUALIFICATION_RESULT_V1';request_id='PNCC-RQ-RC14.39-90C9E8698C64';producer=[ordered]@{source_plane='PRIVATE_RUNTIME';agent_id='PNCC_WINDOWS_RUNTIME_RECONCILER_WU031';runtime_agent_version='0.1.0'};checks=$ordered;live_observation=[ordered]@{reserve_1080_listening=$true;primary_1081_listening=$true;runtime_mutation=$false};qualification_state='BLOCKED';failure_classification=$null;next_scope='PROXIFIER_DESCENDANT_CLEANUP';runtime_authority=$false;promotion_eligible=$false}
 $rp=Join-Path $OutputDirectory 'runtime-qualification-reconciled-result.json';WriteJson $result $rp
 Write-Output 'PNCC_RUNTIME_QUALIFICATION_RECONCILE=BLOCKED PASS_SCOPES=8 NOT_EXECUTED_SCOPES=1 NEXT_SCOPE=PROXIFIER_DESCENDANT_CLEANUP RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false'
 Write-Output "RESULT=$rp";Write-Output "LOG_PATH=$log";exit 0
}catch{Write-Output ('PNCC_RUNTIME_QUALIFICATION_RECONCILE=BLOCKED ERROR='+$_.Exception.Message+' RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false');Write-Output "LOG_PATH=$log";exit 50}finally{try{Stop-Transcript|Out-Null}catch{}}
