#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Fixture')][string]$Mode='Fixture',
    [Parameter(Mandatory=$true)][string]$FixturePath,
    [string]$OutputPath='E:\!Chrome_Downloads\PNCC-STABLE-PRIMARY-1081-CONTROLLED-RESTART.json'
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'

function WriteJson($Value,[string]$Path){
    $dir=Split-Path -Parent $Path
    if($dir){New-Item -ItemType Directory -Force -Path $dir|Out-Null}
    [IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 14),(New-Object Text.UTF8Encoding($true)))
}

if(-not(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
$f=Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8|ConvertFrom-Json

$pre=[ordered]@{
    authorization_contract=([string]$f.authorization_contract -ceq 'PNCC_STABLE_PRIMARY_1081_MUTATION_AUTHORIZATION_V1')
    authorization_state=([string]$f.authorization_state -ceq 'AUTHORIZATION_ADMITTED')
    authorization_ephemeral=[bool]$f.authorization_ephemeral
    authorization_fresh=[bool]$f.authorization_fresh
    immediate_revalidation=[bool]$f.immediate_revalidation
    exact_target_pid=[bool]$f.exact_target_pid
    exact_target_executable=[bool]$f.exact_target_executable
    exact_command_fingerprint=[bool]$f.exact_command_fingerprint
    exact_binding_1081=[bool]$f.exact_binding_1081
    target_putty_family=[bool]$f.target_putty_family
    target_pwfile=[bool]$f.target_pwfile
    target_no_plain_pw=[bool]$f.target_no_plain_pw
    watchdog_registered=[bool]$f.watchdog_registered
    watchdog_fresh=[bool]$f.watchdog_fresh
    watchdog_exact_engine=[bool]$f.watchdog_exact_engine
    reserve_manual_only=[bool]$f.reserve_manual_only
    reserve_1080_snapshot_protected=[bool]$f.reserve_1080_snapshot_protected
    mutation_scope_primary_1081_only=[bool]$f.mutation_scope_primary_1081_only
    parentage_not_authority=[bool]$f.parentage_not_authority
    pid_only_not_authority=[bool]$f.pid_only_not_authority
    broad_process_kill_forbidden=[bool]$f.broad_process_kill_forbidden
}
$post=[ordered]@{
    exactly_one_primary_1081=[bool]$f.exactly_one_primary_1081
    post_primary_putty=[bool]$f.post_primary_putty
    post_primary_binding_1081=[bool]$f.post_primary_binding_1081
    post_primary_pwfile=[bool]$f.post_primary_pwfile
    post_primary_no_plain_pw=[bool]$f.post_primary_no_plain_pw
    routed_identity_valid=[bool]$f.routed_identity_valid
    post_watchdog_registered=[bool]$f.post_watchdog_registered
    post_watchdog_fresh=[bool]$f.post_watchdog_fresh
    post_watchdog_exact_engine=[bool]$f.post_watchdog_exact_engine
    reserve_1080_unchanged=[bool]$f.reserve_1080_unchanged
}
$preFailed=@($pre.GetEnumerator()|Where-Object{-not[bool]$_.Value}|ForEach-Object{$_.Key})
$postFailed=@($post.GetEnumerator()|Where-Object{-not[bool]$_.Value}|ForEach-Object{$_.Key})
$admitted=($preFailed.Count-eq0 -and $postFailed.Count-eq0)
$result=[ordered]@{
    schema_version=1
    contract_id='PNCC_STABLE_PRIMARY_1081_CONTROLLED_RESTART_V1'
    mode='Fixture'
    state=$(if($admitted){'EXECUTION_PLAN_ADMITTED'}else{'BLOCKED'})
    preconditions=$pre
    postconditions=$post
    failed_preconditions=$preFailed
    failed_postconditions=$postFailed
    physical_execution_allowed=$false
    mutation_executed=$false
    runtime_mutation=$false
    reserve_1080_mutation=$false
    primary_1081_tunnel_mutation=$false
    broad_process_kill=$false
    parentage_authority=$false
    pid_only_authority=$false
    runtime_authority=$false
    promotion_eligible=$false
}
WriteJson $result $OutputPath
Write-Output ('PNCC_STABLE_PRIMARY_1081_CONTROLLED_RESTART='+$result.state+' PHYSICAL_EXECUTION_ALLOWED=false MUTATION_EXECUTED=false RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
Write-Output ('OUTPUT='+$OutputPath)
if($admitted){exit 0}else{exit 50}
