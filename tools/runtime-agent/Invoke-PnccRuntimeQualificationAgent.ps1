[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RequestPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$ExpectedRequestId,
    [Parameter(Mandatory=$true)][string]$ExpectedCandidateId,
    [Parameter(Mandatory=$true)][string]$ExpectedSourceSha,
    [Parameter(Mandatory=$true)][string]$ExpectedArtifactSha256,
    [switch]$DryRun
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$AgentId = 'PNCC_WINDOWS_RUNTIME_AGENT'
$AgentVersion = '0.2.0'
$ExpectedRequestContract = 'PNCC_RUNTIME_QUALIFICATION_REQUEST_V1'
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

function Test-LowerHex([string]$Value, [int]$Length) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    if ($Value.Length -ne $Length) { return $false }
    return ($Value -cmatch ('^[0-9a-f]{' + $Length + '}$'))
}

function Test-CandidateIdentity([string]$CandidateId, [string]$SourceSha) {
    if ($CandidateId -cnotmatch '^PNCC-(?:RC14\.39|V7\.0\.0)-([0-9A-F]{12})$') { return $false }
    $suffix = $Matches[1]
    return ($suffix -ceq $SourceSha.Substring(0,12).ToUpperInvariant())
}

function Test-RequestIdentity([string]$RequestId, [string]$CandidateId) {
    if ($CandidateId -cmatch '^PNCC-RC14\.39-([0-9A-F]{12})$') {
        return ($RequestId -ceq ('PNCC-RQ-RC14.39-' + $Matches[1]))
    }
    if ($CandidateId -cmatch '^PNCC-V7\.0\.0-([0-9A-F]{12})$') {
        return ($RequestId -ceq ('PNCC-RQ-V7.0.0-' + $Matches[1]))
    }
    return $false
}

if (-not $DryRun) {
    Fail-Closed 'real runtime execution is not enabled; -DryRun is required' 4
}
if (-not (Test-Path -LiteralPath $RequestPath -PathType Leaf)) {
    Fail-Closed "request file not found: $RequestPath"
}
if (-not (Test-LowerHex $ExpectedSourceSha 40)) { Fail-Closed 'caller-pinned ExpectedSourceSha must be lowercase 40-hex' }
if (-not (Test-LowerHex $ExpectedArtifactSha256 64)) { Fail-Closed 'caller-pinned ExpectedArtifactSha256 must be lowercase 64-hex' }
if (-not (Test-CandidateIdentity $ExpectedCandidateId $ExpectedSourceSha)) { Fail-Closed 'caller-pinned candidate/source identity is malformed or incoherent' }
if (-not (Test-RequestIdentity $ExpectedRequestId $ExpectedCandidateId)) { Fail-Closed 'caller-pinned request/candidate identity is malformed or incoherent' }

try {
    $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Fail-Closed ("request JSON parse failed: " + $_.Exception.Message)
}

if ($request.schema_version -ne 1) { Fail-Closed 'request schema_version must be 1' }
if ([string]$request.contract_id -ne $ExpectedRequestContract) { Fail-Closed 'request contract mismatch' }
if ([string]$request.request_id -cne $ExpectedRequestId) { Fail-Closed 'request_id substitution rejected' }
if ([string]$request.candidate.candidate_id -cne $ExpectedCandidateId) { Fail-Closed 'candidate_id substitution rejected' }
if ([string]$request.candidate.source_sha -cne $ExpectedSourceSha) { Fail-Closed 'source_sha substitution rejected' }
if ([string]$request.candidate.artifact_sha256 -cne $ExpectedArtifactSha256) { Fail-Closed 'artifact_sha256 substitution rejected' }
if (-not (Test-LowerHex ([string]$request.candidate.source_sha) 40)) { Fail-Closed 'request source_sha format invalid' }
if (-not (Test-LowerHex ([string]$request.candidate.artifact_sha256) 64)) { Fail-Closed 'request artifact_sha256 format invalid' }
if (-not (Test-LowerHex ([string]$request.candidate.provider_artifact_digest) 64)) { Fail-Closed 'request provider_artifact_digest format invalid' }
if ([int64]$request.candidate.artifact_size_bytes -le 0) { Fail-Closed 'artifact_size_bytes must be positive' }
if ([int64]$request.candidate.provider_artifact_id -le 0) { Fail-Closed 'provider_artifact_id must be positive' }
if ([int64]$request.candidate.provider_build_run_id -le 0) { Fail-Closed 'provider_build_run_id must be positive' }
if (-not (Test-CandidateIdentity ([string]$request.candidate.candidate_id) ([string]$request.candidate.source_sha))) { Fail-Closed 'request candidate/source identity incoherent' }
if (-not (Test-RequestIdentity ([string]$request.request_id) ([string]$request.candidate.candidate_id))) { Fail-Closed 'request_id/candidate identity incoherent' }
if ([bool]$request.runtime_authority) { Fail-Closed 'request cannot grant runtime authority' }
if ([bool]$request.promotion_eligible) { Fail-Closed 'request cannot grant promotion eligibility' }
if ([string]$request.state -ne 'RUNTIME_PENDING') { Fail-Closed 'request state must be RUNTIME_PENDING' }
if ([int]$request.expected_invariants.primary_auto_port -ne 1081) { Fail-Closed 'PRIMARY_AUTO port invariant mismatch' }
if ([int]$request.expected_invariants.reserve_manual_port -ne 1080) { Fail-Closed 'RESERVE_MANUAL port invariant mismatch' }
if ([string]$request.expected_invariants.reserve_manual_lifecycle -ne 'MANUAL_ONLY') { Fail-Closed '1080 lifecycle invariant mismatch' }
if ([string]$request.expected_invariants.v6_3_1_sha256 -ne '385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e') { Fail-Closed 'V6.3.1 identity invariant mismatch' }
if ([string]$request.expected_invariants.putty_password_argument -ne '-pwfile') { Fail-Closed 'PuTTY password transport invariant mismatch' }
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
    $steps += [ordered]@{
        scope = $scope
        mode = 'DRY_RUN'
        mutation_allowed = $false
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
    provider_artifact_id = [int64]$request.candidate.provider_artifact_id
    provider_artifact_digest = [string]$request.candidate.provider_artifact_digest
    provider_build_run_id = [int64]$request.candidate.provider_build_run_id
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
    candidate = [ordered]@{
        candidate_id = [string]$request.candidate.candidate_id
        source_sha = [string]$request.candidate.source_sha
        artifact_filename = [string]$request.candidate.artifact_filename
        artifact_sha256 = [string]$request.candidate.artifact_sha256
        artifact_size_bytes = [int64]$request.candidate.artifact_size_bytes
    }
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

Write-Output "PNCC_RUNTIME_AGENT=PASS MODE=DRY_RUN REQUEST_ID=$ExpectedRequestId CANDIDATE_ID=$ExpectedCandidateId SCOPES=$($ExpectedScopes.Count) RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false"
Write-Output "EXECUTION_PLAN=$planPath"
Write-Output "RESULT_SKELETON=$resultPath"
exit 0
