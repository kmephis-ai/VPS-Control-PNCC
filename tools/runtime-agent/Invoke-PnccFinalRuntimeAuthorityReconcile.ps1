#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Live','Plan')][string]$Mode='Live',
 [string]$ReconciledEightOfNinePath,
 [string]$ProxifierQualificationPath,
 [string]$V631Path,
 [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-FINAL-RUNTIME-AUTHORITY-WU036',
 [string]$FixturePath
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$ExpectedV631Sha='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$Scopes=@('WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','WATCHDOG_LIFECYCLE','PROXIFIER_DESCENDANT_CLEANUP','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080','CREDENTIAL_HOSTKEY','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY')
function Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function WriteJson($Value,[string]$Path){$d=Split-Path -Parent $Path;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 16),(New-Object Text.UTF8Encoding($true)))}
function GetCheck($Source,[string]$Scope){@($Source.checks|Where-Object{[string]$_.scope -eq $Scope}|Select-Object -First 1)}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$log=Join-Path $OutputDirectory 'PNCC-FINAL-RUNTIME-AUTHORITY-WU036.log'
Start-Transcript $log -Force|Out-Null
try {
 if($Mode -eq 'Plan'){
  if(!$FixturePath -or !(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
  $f=Get-Content -LiteralPath $FixturePath -Raw|ConvertFrom-Json
  foreach($n in @('eight_of_nine_valid','proxifier_pass','zero_descendants','reserve_listening','primary_listening','rollback_identity')){if(-not [bool]$f.$n){throw ('plan fixture failed: '+$n)}}
  Write-Output 'PNCC_FINAL_RUNTIME_AUTHORITY=PLAN_PASS RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false'
  exit 0
 }
 if(!$ReconciledEightOfNinePath -or !(Test-Path -LiteralPath $ReconciledEightOfNinePath -PathType Leaf)){throw 'ReconciledEightOfNinePath missing'}
 if(!$ProxifierQualificationPath -or !(Test-Path -LiteralPath $ProxifierQualificationPath -PathType Leaf)){throw 'ProxifierQualificationPath missing'}
 if(!$V631Path -or !(Test-Path -LiteralPath $V631Path -PathType Leaf)){throw 'V631Path missing'}
 if((Sha $V631Path) -ne $ExpectedV631Sha){throw 'immutable V6.3.1 identity mismatch'}
 $base=Get-Content -LiteralPath $ReconciledEightOfNinePath -Raw|ConvertFrom-Json
 if([string]$base.contract_id -ne 'PNCC_RUNTIME_QUALIFICATION_RESULT_V1'){throw '8/9 contract mismatch'}
 if([string]$base.qualification_state -ne 'BLOCKED' -or [string]$base.next_scope -ne 'PROXIFIER_DESCENDANT_CLEANUP'){throw '8/9 prerequisite state mismatch'}
 if([bool]$base.runtime_authority -or [bool]$base.promotion_eligible){throw '8/9 prerequisite already claims authority'}
 foreach($s in @('WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','WATCHDOG_LIFECYCLE','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080','CREDENTIAL_HOSTKEY','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY')){$c=@(GetCheck $base $s);if($c.Count -ne 1 -or [string]$c[0].result -ne 'PASS'){throw ('8/9 required PASS missing: '+$s)}}
 $pending=@(GetCheck $base 'PROXIFIER_DESCENDANT_CLEANUP');if($pending.Count-ne1 -or [string]$pending[0].result-ne'NOT_EXECUTED'){throw '8/9 proxifier prerequisite mismatch'}
 $prox=Get-Content -LiteralPath $ProxifierQualificationPath -Raw|ConvertFrom-Json
 if([string]$prox.contract_id -notin @('PNCC_PROXIFIER_DESCENDANT_QUALIFICATION_V2','PNCC_PROXIFIER_DESCENDANT_QUALIFICATION_V3')){throw 'proxifier qualification contract mismatch'}
 if([string]$prox.result -ne 'PASS' -or [int]$prox.max_proxifier_descendants -ne 0){throw 'proxifier qualification is not PASS/zero'}
 if([bool]$prox.runtime_mutation -or [bool]$prox.reserve_1080_mutation){throw 'proxifier evidence reports forbidden mutation'}
 if(-not [bool]$prox.reserve_1080_listening_before -or -not [bool]$prox.reserve_1080_listening_after){throw 'proxifier evidence lost 1080'}
 if(-not [bool]$prox.primary_1081_listening_before -or -not [bool]$prox.primary_1081_listening_after){throw 'proxifier evidence lost 1081'}
 $reserveLive=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1080 -ErrorAction SilentlyContinue)
 $primaryLive=@(Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort 1081 -ErrorAction SilentlyContinue)
 if($reserveLive.Count-lt1){throw '1080 reserve live observation missing'}
 if($primaryLive.Count-lt1){throw '1081 primary live observation missing'}
 $checks=New-Object Collections.ArrayList
 foreach($s in $Scopes){
  if($s -eq 'PROXIFIER_DESCENDANT_CLEANUP'){
   [void]$checks.Add([ordered]@{scope=$s;result='PASS';exit_code=0;failure_class=$null;evidence_refs=@('wu035-proxifier-descendant-qualification')})
  } else {
   $c=@(GetCheck $base $s);[void]$checks.Add([ordered]@{scope=$s;result='PASS';exit_code=0;failure_class=$null;evidence_refs=@($c[0].evidence_refs)})
  }
 }
 if(@($checks|Where-Object{[string]$_.result -eq 'PASS'}).Count -ne 9){throw 'final check count mismatch'}
 $result=[ordered]@{
  schema_version=1
  contract_id='PNCC_RUNTIME_QUALIFICATION_RESULT_V1'
  request_id='PNCC-RQ-RC14.39-90C9E8698C64'
  producer=[ordered]@{source_plane='PRIVATE_RUNTIME';agent_id='PNCC_WINDOWS_FINAL_RUNTIME_AUTHORITY_WU036';runtime_agent_version='0.1.0'}
  checks=@($checks)
  live_observation=[ordered]@{reserve_1080_listening=$true;primary_1081_listening=$true;runtime_mutation=$false;reserve_1080_mutation=$false}
  qualification_state='PASS'
  failure_classification=$null
  next_scope=$null
  runtime_authority=$true
  promotion_eligible=$true
 }
 $rp=Join-Path $OutputDirectory 'runtime-qualification-final-result.json';WriteJson $result $rp
 Write-Output 'PNCC_FINAL_RUNTIME_AUTHORITY=PASS PASS_SCOPES=9 RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=true PROMOTION_ELIGIBLE=true'
 Write-Output "RESULT=$rp";Write-Output "LOG_PATH=$log";exit 0
} catch {
 Write-Output ('PNCC_FINAL_RUNTIME_AUTHORITY=BLOCKED ERROR='+$_.Exception.Message+' RUNTIME_MUTATION=false RESERVE_1080_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
 Write-Output "LOG_PATH=$log";exit 50
} finally {try{Stop-Transcript|Out-Null}catch{}}
