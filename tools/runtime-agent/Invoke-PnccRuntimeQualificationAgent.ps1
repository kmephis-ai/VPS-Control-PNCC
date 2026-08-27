[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RequestPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [switch]$DryRun
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$AgentId = 'PNCC_WINDOWS_RUNTIME_AGENT'
$AgentVersion = '0.1.0'
$ExpectedRequestContract = 'PNCC_RUNTIME_QUALIFICATION_REQUEST_V1'
$ExpectedCandidateId = 'PNCC-RC14.39-90C9E8698C64'
$ExpectedSourceSha = '90c9e8698c6468d576aecbc60d940be9d5c6baab'
$ExpectedArtifactSha256 = '8caad796469886b90d9928fba385fc4a4f0f3d60bcb6ee6b7cb98c4c2e4390b3'
$ExpectedScopes = @(
    'WINDOWS_BASELINE',
    'PROCESS_OWNERSHIP_BASELINE',
    'WATCHDOG_LIFECYCLE',
    'PROXIFIER_DESCENDANT_CLEANUP',
    'PRIMARY_AUTO_1081',
    'RESERVE_MANUAL_1080',
    'CREDENTIAL_HOSTKEY',
    'NETWORK_QUALIFICATION',
    'ROLLBACK_IDENTITY'
)

function Fail-Closed([string]$Message, [int]$Code = 2) {
    [Console]::Error.WriteLine("PNCC_RUNTIME_AGENT=FAIL ERROR=$Message")
    exit $Code
}

if (-not $DryRun) {
    Fail-Closed 'real runtime execution is not enabled by PIPE-WU-016; -DryRun is required' 4
}
if (-not (Test-Path -LiteralPath $RequestPath -PathType Leaf)) {
    Fail-Closed "request file not found: $RequestPath"
}

try {
    $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Fail-Closed ("request JSON parse failed: " + $_.Exception.Message)
}

if ($request.schema_version -ne 1) { Fail-Closed 'request schema_version must be 1' }
if ([string]$request.contract_id -ne $ExpectedRequestContract) { Fail-Closed 'request contract mismatch' }
if ([string]$request.candidate.candidate_id -ne $ExpectedCandidateId) { Fail-Closed 'candidate_id substitution rejected' }
if ([string]$request.candidate.source_sha -ne $ExpectedSourceSha) { Fail-Closed 'source_sha substitution rejected' }
if ([string]$request.candidate.artifact_sha256 -ne $ExpectedArtifactSha256) { Fail-Closed 'artifact_sha256 substitution rejected' }
if ([bool]$request.runtime_authority) { Fail-Closed 'request cannot grant runtime authority' }
if ([bool]$request.promotion_eligible) { Fail-Closed 'request cannot grant promotion eligibility' }
if ([string]$request.state -ne 'RUNTIME_PENDING') { Fail-Closed 'request state must be RUNTIME_PENDING' }
if ([int]$request.expected_invariants.primary_auto_port -ne 1081) { Fail-Closed 'PRIMARY_AUTO port invariant mismatch' }
if ([int]$request.expected_invariants.reserve_manual_port -ne 1080) { Fail-Closed 'RESERVE_MANUAL port invariant mismatch' }
if ([string]$request.expected_invariants.reserve_manual_lifecycle -ne 'MANUAL_ONLY') { Fail-Closed '1080 lifecycle invariant mismatch' }
if ([bool]$request.expected_invariants.plaintext_pw_allowed) { Fail-Closed 'plaintext -pw cannot be allowed' }
if ([bool]$request.expected_invariants.hostkey_verification_disable_allowed) { Fail-Closed 'host-key verification cannot be disabled' }

$actualScopes = @($request.required_scopes | ForEach-Object { [string]$_ })
if ($actualScopes.Count -ne $ExpectedScopes.Count) { Fail-Closed 'required scope count mismatch' }
for ($i = 0; $i -lt $ExpectedScopes.Count; $i++) {
    if ($actualScopes[$i] -ne $ExpectedScopes[$i]) { Fail-Closed ("required scope mismatch at index $i") }
}

$privateRoot = Join-Path $OutputDirectory 'private-evidence'
$publicRoot = Join-Path $OutputDirectory 'public-safe'
New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null
New-Item -ItemType Directory -Force -Path $publicRoot | Out-Null

$steps = @()
foreach ($scope in $ExpectedScopes) {
    $mutationAllowed = $false
    if ($scope -eq 'PRIMARY_AUTO_1081') { $mutationAllowed = $false }
    if ($scope -eq 'RESERVE_MANUAL_1080') { $mutationAllowed = $false }
    $steps += [ordered]@{
        scope = $scope
        mode = 'DRY_RUN'
        mutation_allowed = $mutationAllowed
        evidence_class = 'PRIVATE_RUNTIME'
        status = 'PLANNED'
    }
}

$plan = [ordered]@{
    schema_version = 1
    plan_id = 'PNCC_RUNTIME_AGENT_EXECUTION_PLAN_V1'
    request_id = [string]$request.request_id
    candidate_id = [string]$request.candidate.candidate_id
    source_sha = [string]$request.candidate.source_sha
    artifact_sha256 = [string]$request.candidate.artifact_sha256
    dry_run = $true
    runtime_mutation_permitted = $false
    public_ci_runtime_authority = $false
    private_evidence_root = 'private-evidence'
    public_safe_projection_root = 'public-safe'
    steps = $steps
}

$checks = @()
foreach ($scope in $ExpectedScopes) {
    $checks += [ordered]@{
        scope = $scope
        result = 'NOT_EXECUTED'
        exit_code = 0
        failure_class = $null
        evidence_refs = @()
    }
}

$resultSkeleton = [ordered]@{
    schema_version = 1
    contract_id = 'PNCC_RUNTIME_QUALIFICATION_RESULT_V1'
    request_id = [string]$request.request_id
    candidate = [ordered]@{}
    producer = [ordered]@{
        source_plane = 'PRIVATE_RUNTIME'
        agent_id = $AgentId
        runtime_agent_version = $AgentVersion
        validation_lab_version = 'NOT_EXECUTED_DRY_RUN'
    }
    environment = [ordered]@{
        windows_version = 'NOT_EXECUTED_DRY_RUN'
        powershell_version = $PSVersionTable.PSVersion.ToString()
    }
    checks = $checks
    evidence_bundle = [ordered]@{
        sha256 = ('0' * 64)
        private_location_ref = 'private-evidence/PENDING'
        sanitation_state = 'NOT_EVALUATED'
    }
    qualification_state = 'BLOCKED'
    failure_classification = 'ENVIRONMENT_OR_BASELINE_BLOCKER'
    runtime_authority = $false
    promotion_eligible = $false
}

$planPath = Join-Path $OutputDirectory 'execution-plan.json'
$resultPath = Join-Path $OutputDirectory 'runtime-result.skeleton.json'
$plan | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $planPath -Encoding UTF8
$resultSkeleton | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resultPath -Encoding UTF8

Write-Output "PNCC_RUNTIME_AGENT=PASS MODE=DRY_RUN REQUEST_ID=$($request.request_id) CANDIDATE_ID=$ExpectedCandidateId SCOPES=$($ExpectedScopes.Count) RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false"
Write-Output "EXECUTION_PLAN=$planPath"
Write-Output "RESULT_SKELETON=$resultPath"
exit 0
