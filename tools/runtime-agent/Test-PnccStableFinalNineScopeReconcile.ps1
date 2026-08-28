#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Fixture','LiveManifest')][string]$Mode='Fixture',
 [string]$InputPath,
 [string]$OutputDirectory='E:\!Chrome_Downloads\PNCC-STABLE-FINAL-NINE-SCOPE-RECONCILE'
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$Scopes=@('WINDOWS_BASELINE','PROCESS_OWNERSHIP_BASELINE','WATCHDOG_LIFECYCLE','PROXIFIER_DESCENDANT_CLEANUP','PRIMARY_AUTO_1081','RESERVE_MANUAL_1080','CREDENTIAL_HOSTKEY','NETWORK_QUALIFICATION','ROLLBACK_IDENTITY')
$ExpectedStableSha='1407f82b15ea2b70ba56b7406bb8dd0d9097c459b630d016d6a7b5f10a49e599'
$ExpectedRollbackSha='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$ExpectedEngineSha='843c006b896607da19406998b54d4e6897fa8eb62d3e6bc92cc77255fe4833cf'
function WJ($v,[string]$p){$d=Split-Path -Parent $p;if($d){New-Item -ItemType Directory -Force -Path $d|Out-Null};[IO.File]::WriteAllText($p,($v|ConvertTo-Json -Depth 20),(New-Object Text.UTF8Encoding($true)))}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$rp=Join-Path $OutputDirectory 'stable-final-nine-scope-reconcile-result.json'
if(!$InputPath -or !(Test-Path -LiteralPath $InputPath -PathType Leaf)){throw 'InputPath required'}
$m=Get-Content -LiteralPath $InputPath -Raw -Encoding UTF8|ConvertFrom-Json
if([string]$m.contract_id -ne 'PNCC_STABLE_FINAL_NINE_SCOPE_INPUT_V1'){throw 'input contract mismatch'}
if([string]$m.stable_artifact_sha256 -cne $ExpectedStableSha){throw 'Stable artifact SHA mismatch'}
if([string]$m.rollback_v631_sha256 -cne $ExpectedRollbackSha){throw 'rollback SHA mismatch'}
if([string]$m.stable_engine_sha256 -cne $ExpectedEngineSha){throw 'Stable engine SHA mismatch'}
if([bool]$m.rc_runtime_truth_used){throw 'RC Runtime Truth transfer forbidden'}
if([bool]$m.runtime_mutation){throw 'final reconcile must be READ_ONLY'}
if(-not [bool]$m.reserve_1080_untouched){throw '1080 invariant not proven'}
if(-not [bool]$m.primary_1081_secure){throw '1081 secure invariant not proven'}
if(-not [bool]$m.watchdog_exact_and_fresh){throw 'Watchdog continuity not proven'}
if(-not [bool]$m.proxifier_descendant_clean){throw 'Proxifier descendant cleanliness not proven'}
if(-not [bool]$m.credential_hostkey_fail_closed){throw 'credential/hostkey invariant not proven'}
$checks=@()
foreach($s in $Scopes){
 $c=@($m.scopes|Where-Object{[string]$_.scope -ceq $s})
 if($c.Count-ne1){throw ('scope cardinality invalid: '+$s)}
 if([string]$c[0].result -cne 'PASS'){throw ('scope not PASS: '+$s)}
 if(-not [bool]$c[0].fresh_stable_evidence){throw ('scope lacks fresh Stable evidence: '+$s)}
 $checks += [ordered]@{scope=$s;result='PASS';fresh_stable_evidence=$true;evidence_class=[string]$c[0].evidence_class}
}
$r=[ordered]@{
 schema_version=1
 contract_id='PNCC_STABLE_FINAL_NINE_SCOPE_RECONCILE_V1'
 mode=$Mode
 state='STABLE_NINE_SCOPE_RECONCILE_PASS'
 stable_artifact_sha256=$ExpectedStableSha
 rollback_v631_sha256=$ExpectedRollbackSha
 stable_engine_sha256=$ExpectedEngineSha
 checks=$checks
 all_nine_scopes_pass=$true
 rc_runtime_truth_used=$false
 reserve_1080_untouched=$true
 primary_1081_secure=$true
 watchdog_exact_and_fresh=$true
 proxifier_descendant_clean=$true
 credential_hostkey_fail_closed=$true
 runtime_mutation=$false
 runtime_authority=$false
 runtime_authority_candidate=$true
 promotion_eligible=$false
 release_or_tag_authorized=$false
}
WJ $r $rp
Write-Output 'PNCC_STABLE_FINAL_NINE_SCOPE_RECONCILE=PASS SCOPES=9 RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false RUNTIME_AUTHORITY_CANDIDATE=true PROMOTION_ELIGIBLE=false'
Write-Output ('RESULT='+$rp)
exit 0
