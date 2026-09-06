#requires -Version 5.1
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2

$expectedBase='ee39986227964198ab2e22fae63f2cd64f43b398'
$contractPath='.pncc-dev/contracts/pipe-wu-219-primary-auto-1081-requalification-readiness.json'
$enginePath='src/windows-v7/VPS-Control-v7-engine-upgrade.ps1'
$v631Path='src/rollback-base/VPS-Control-v6.3.1.ps1'
$expectedV631Sha='385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$expectedV631Blob='fbcf80dac2d619c421b8a40b5612cd13d5da4a73'
$expectedEngineBlob='9c5f991b6f215961aead21152a715ac242d833ff'

function Assert-True([bool]$Condition,[string]$Message){if(-not $Condition){throw $Message}}
function Git-One([string[]]$Args){
    $value=& git @Args
    if($LASTEXITCODE -ne 0){throw ('git '+($Args -join ' ')+' failed')}
    return ([string]($value | Select-Object -First 1)).Trim()
}

Assert-True (Test-Path -LiteralPath $contractPath -PathType Leaf) 'WU219 contract missing'
Assert-True (Test-Path -LiteralPath $enginePath -PathType Leaf) 'V7 engine missing'
Assert-True (Test-Path -LiteralPath $v631Path -PathType Leaf) 'immutable V6.3.1 missing'

$contract=Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
Assert-True ($contract.work_unit -eq 'PIPE-WU-219') 'wrong work unit'
Assert-True ($contract.exact_base_main -eq $expectedBase) 'exact base binding drifted'
Assert-True (-not [bool]$contract.runtime_required) 'WU219 must remain runtime_required=false'
Assert-True (-not [bool]$contract.runtime_authorized) 'WU219 must not authorize runtime'
Assert-True ($contract.future_runtime_target.channel -eq 'PRIMARY_AUTO') 'future target must be PRIMARY_AUTO'
Assert-True ([int]$contract.future_runtime_target.port -eq 1081) 'future target must be 1081'
Assert-True ([bool]$contract.future_runtime_target.requires_fresh_explicit_owner_runtime_authorization) 'fresh explicit runtime authorization must be required'
Assert-True (-not [bool]$contract.future_runtime_target.generic_continue_is_runtime_authorization) 'generic continue must not authorize runtime'
Assert-True ([int]$contract.reserve_manual.port -eq 1080) 'reserve port must remain 1080'
Assert-True ($contract.reserve_manual.policy -eq 'OBSERVATION_ONLY') '1080 must remain observation-only'
Assert-True (-not [bool]$contract.reserve_manual.lifecycle_mutation_allowed) '1080 lifecycle mutation must remain forbidden'

$engineBlob=Git-One @('rev-parse',('HEAD:'+$enginePath))
Assert-True ($engineBlob -eq $expectedEngineBlob) ('WU218 engine blob drifted: '+$engineBlob)
$engine=Get-Content -LiteralPath $enginePath -Raw
foreach($marker in @('WU218_SAVEDSESSION_FALLBACK_V1','Get-V7ObservedReservePuttyExecutableCandidates','PORTABLE_RESERVE_1080_OBSERVED','reserve-1080-observed','Ensure-V7OfficialPuttyHostKeyTrust','-pwfile')){
    Assert-True ($engine.Contains($marker)) ('missing WU218/security marker: '+$marker)
}
$helper=[regex]::Match($engine,'(?s)function Get-V7ObservedReservePuttyExecutableCandidates \{.*?\r?\n\}').Value
Assert-True ([bool]$helper) 'cannot isolate WU218 reserve-observation helper'
Assert-True ($helper -notmatch '(?i)CommandLine') '1080 process command-line read is forbidden'
Assert-True ($helper -notmatch '(?i)Stop-Process|Start-Process|Restart-Computer|\.Kill\(') '1080 lifecycle mutation is forbidden'
Assert-True ($helper -match 'Get-NetTCPConnection') '1080 fallback must remain listener-observation based'

$v631Blob=Git-One @('rev-parse',('HEAD:'+$v631Path))
Assert-True ($v631Blob -eq $expectedV631Blob) ('V6.3.1 git blob drifted: '+$v631Blob)
$v631Sha=(Get-FileHash -LiteralPath $v631Path -Algorithm SHA256).Hash.ToLowerInvariant()
Assert-True ($v631Sha -eq $expectedV631Sha) ('V6.3.1 SHA-256 drifted: '+$v631Sha)

$allowed=@(
    '.github/workflows/pipe-wu-219-primary-auto-1081-requalification-readiness.yml',
    '.pncc-dev/contracts/pipe-wu-219-primary-auto-1081-requalification-readiness.json',
    'tests/pipe-wu-219-primary-auto-1081-requalification-readiness.ps1'
)
& git cat-file -e ($expectedBase+'^{commit}') 2>$null
if($LASTEXITCODE -ne 0){throw 'exact WU219 base commit unavailable; full-history checkout required'}
$changed=@(& git diff --name-only $expectedBase HEAD)
if($LASTEXITCODE -ne 0){throw 'unable to calculate WU219 bounded diff'}
foreach($path in $changed){Assert-True ($allowed -contains [string]$path) ('out-of-scope WU219 path: '+$path)}
foreach($path in $allowed){Assert-True ($changed -contains $path) ('expected WU219 path absent from bounded diff: '+$path)}

Assert-True (-not ($contract.forbidden -contains $null)) 'forbidden contract list invalid'
foreach($required in @('1080 lifecycle mutation','1081 runtime execution in PIPE-WU-219','V6.3.1 mutation','plaintext -pw','self-hosted runner','release/tag/Stable','force/bypass')){
    Assert-True ($contract.forbidden -contains $required) ('missing forbidden invariant: '+$required)
}

if(& git status --porcelain){throw 'readiness regression mutated repository'}
Write-Host 'PIPE-WU-219 PASS: control-plane-only readiness contract is fail-closed and runtime remains unauthorized.'
