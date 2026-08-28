#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Fixture')][string]$Mode='Fixture',
    [Parameter(Mandatory=$true)][string]$FixturePath,
    [string]$OutputPath='E:\!Chrome_Downloads\PNCC-STABLE-PRIMARY-1081-MUTATION-AUTHORIZATION.json'
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'

function WriteJson($Value,[string]$Path){
    $dir=Split-Path -Parent $Path
    if($dir){New-Item -ItemType Directory -Force -Path $dir|Out-Null}
    [IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($true)))
}

if(-not(Test-Path -LiteralPath $FixturePath -PathType Leaf)){throw 'FixturePath required'}
$f=Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8|ConvertFrom-Json

$checks=[ordered]@{
    ownership_contract=([string]$f.ownership_contract -ceq 'PNCC_STABLE_PRIMARY_1081_OWNERSHIP_V1')
    ownership_state=([string]$f.ownership_state -ceq 'OWNERSHIP_ADMITTED')
    ownership_receipt_fresh=[bool]$f.ownership_receipt_fresh
    primary_process_identity_match=[bool]$f.primary_process_identity_match
    primary_command_fingerprint_match=[bool]$f.primary_command_fingerprint_match
    primary_single=[bool]$f.primary_single
    primary_putty=[bool]$f.primary_putty
    primary_binding_1081=[bool]$f.primary_binding_1081
    primary_pwfile=[bool]$f.primary_pwfile
    primary_no_plain_pw=[bool]$f.primary_no_plain_pw
    watchdog_registered=[bool]$f.watchdog_registered
    watchdog_fresh=[bool]$f.watchdog_fresh
    watchdog_exact_engine=[bool]$f.watchdog_exact_engine
    immediate_revalidation=[bool]$f.immediate_revalidation
    reserve_manual_only=[bool]$f.reserve_manual_only
    reserve_1080_untouched=[bool]$f.reserve_1080_untouched
    mutation_scope_primary_1081_only=[bool]$f.mutation_scope_primary_1081_only
    parentage_not_authority=[bool]$f.parentage_not_authority
    pid_only_not_authority=[bool]$f.pid_only_not_authority
    broad_process_kill_forbidden=[bool]$f.broad_process_kill_forbidden
}
$failed=@($checks.GetEnumerator()|Where-Object{-not[bool]$_.Value}|ForEach-Object{$_.Key})
$admitted=($failed.Count-eq0)
$result=[ordered]@{
    schema_version=1
    contract_id='PNCC_STABLE_PRIMARY_1081_MUTATION_AUTHORIZATION_V1'
    mode='Fixture'
    state=$(if($admitted){'AUTHORIZATION_ADMITTED'}else{'BLOCKED'})
    checks=$checks
    failed_checks=$failed
    authorization_ephemeral=$true
    mutation_executed=$false
    runtime_mutation=$false
    reserve_1080_mutation=$false
    primary_1081_tunnel_mutation=$false
    parentage_authority=$false
    pid_only_authority=$false
    runtime_authority=$false
    promotion_eligible=$false
}
WriteJson $result $OutputPath
Write-Output ('PNCC_STABLE_PRIMARY_1081_MUTATION_AUTHORIZATION='+$result.state+' MUTATION_EXECUTED=false RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false')
Write-Output ('OUTPUT='+$OutputPath)
if($admitted){exit 0}else{exit 50}
