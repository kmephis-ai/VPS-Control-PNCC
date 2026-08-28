[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [ValidateSet('Provider','Fixture')][string]$Mode = 'Provider',
    [string]$FixtureBundleDirectory,
    [string]$Repository = 'kmephis-ai/VPS-Control-PNCC',
    [Parameter(Mandatory=$true)][long]$RequestProviderArtifactId,
    [Parameter(Mandatory=$true)][long]$RequestProviderBuildRunId,
    [Parameter(Mandatory=$true)][string]$ExpectedRequestArtifactName,
    [Parameter(Mandatory=$true)][string]$ExpectedRequestProviderDigest,
    [Parameter(Mandatory=$true)][string]$ExpectedRequestSourceSha
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$ExpectedRequestContract = 'PNCC_RUNTIME_QUALIFICATION_REQUEST_V1'
$ExpectedAgentRelative = 'tools/runtime-agent/Invoke-PnccRuntimeQualificationAgent.ps1'

function Fail-Closed([string]$Message, [int]$Code = 2) {
    [Console]::Error.WriteLine("PNCC_RUNTIME_BOOTSTRAP=FAIL ERROR=$Message")
    exit $Code
}

function Assert-Command([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { Fail-Closed "required command missing: $Name" 3 }
}

function Get-FileSha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-LowerHex([string]$Value, [int]$Length) {
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value.Length -ne $Length) { return $false }
    return ($Value -cmatch ('^[0-9a-f]{' + $Length + '}$'))
}

function Get-ProviderMetadata([long]$ArtifactId) {
    $raw = & gh api ("repos/{0}/actions/artifacts/{1}" -f $Repository,$ArtifactId) 2>&1
    if ($LASTEXITCODE -ne 0) { Fail-Closed ('artifact metadata acquisition failed: ' + ($raw -join ' ')) 4 }
    try { return (($raw -join "`n") | ConvertFrom-Json) } catch { Fail-Closed ('artifact metadata JSON invalid: ' + $_.Exception.Message) 4 }
}

if ($RequestProviderArtifactId -le 0 -or $RequestProviderBuildRunId -le 0) { Fail-Closed 'request provider ids must be positive' }
if (-not (Test-LowerHex $ExpectedRequestSourceSha 40)) { Fail-Closed 'ExpectedRequestSourceSha must be lowercase 40-hex' }
if ($ExpectedRequestProviderDigest -cnotmatch '^sha256:[0-9a-f]{64}$') { Fail-Closed 'ExpectedRequestProviderDigest must be sha256:<64 lowercase hex>' }
if ([string]::IsNullOrWhiteSpace($ExpectedRequestArtifactName)) { Fail-Closed 'ExpectedRequestArtifactName is required' }

if ($Mode -eq 'Provider') {
    Assert-Command 'gh'
    $authStatus = & gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) { Fail-Closed ('gh auth status failed: ' + ($authStatus -join ' ')) 3 }
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$workspace = Join-Path $OutputRoot ("PNCC-RUNTIME-QUALIFICATION-$stamp")
$requestProviderDir = Join-Path $workspace 'request-provider-artifact'
$candidateProviderDir = Join-Path $workspace 'candidate-provider-artifact'
$privateDir = Join-Path $workspace 'private-evidence'
$publicDir = Join-Path $workspace 'public-safe'
$agentDir = Join-Path $workspace 'agent'
$requestDir = Join-Path $workspace 'request'
@($workspace,$requestProviderDir,$candidateProviderDir,$privateDir,$publicDir,$agentDir,$requestDir) | ForEach-Object { New-Item -ItemType Directory -Path $_ -Force | Out-Null }

$requestMetadata = $null
if ($Mode -eq 'Provider') {
    $requestMetadata = Get-ProviderMetadata $RequestProviderArtifactId
    if ([long]$requestMetadata.id -ne $RequestProviderArtifactId) { Fail-Closed 'request provider artifact id mismatch' 4 }
    if ([string]$requestMetadata.name -cne $ExpectedRequestArtifactName) { Fail-Closed 'request provider artifact name mismatch' 4 }
    if ([bool]$requestMetadata.expired) { Fail-Closed 'request provider artifact is expired' 4 }
    if ([string]$requestMetadata.digest -cne $ExpectedRequestProviderDigest) { Fail-Closed 'request provider artifact digest mismatch' 4 }
    if ([long]$requestMetadata.workflow_run.id -ne $RequestProviderBuildRunId) { Fail-Closed 'request provider build run mismatch' 4 }
    if ([string]$requestMetadata.workflow_run.head_sha -cne $ExpectedRequestSourceSha) { Fail-Closed 'request provider source SHA mismatch' 4 }

    $downloadRequest = & gh run download $RequestProviderBuildRunId --repo $Repository --name $ExpectedRequestArtifactName --dir $requestProviderDir 2>&1
    if ($LASTEXITCODE -ne 0) { Fail-Closed ('request artifact download failed: ' + ($downloadRequest -join ' ')) 4 }
} else {
    if ([string]::IsNullOrWhiteSpace($FixtureBundleDirectory)) { Fail-Closed 'FixtureBundleDirectory is required in Fixture mode' 2 }
    if (-not (Test-Path -LiteralPath $FixtureBundleDirectory -PathType Container)) { Fail-Closed 'fixture bundle directory not found' 2 }
    $fixtureRequest = Join-Path $FixtureBundleDirectory 'request-provider-artifact'
    $fixtureCandidate = Join-Path $FixtureBundleDirectory 'candidate-provider-artifact'
    if (-not (Test-Path -LiteralPath $fixtureRequest -PathType Container)) { Fail-Closed 'fixture request-provider-artifact directory missing' 2 }
    if (-not (Test-Path -LiteralPath $fixtureCandidate -PathType Container)) { Fail-Closed 'fixture candidate-provider-artifact directory missing' 2 }
    Copy-Item -LiteralPath (Join-Path $fixtureRequest '*') -Destination $requestProviderDir -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $fixtureCandidate '*') -Destination $candidateProviderDir -Recurse -Force
}

$requestFiles = @(Get-ChildItem -LiteralPath $requestProviderDir -File -Filter '*.json')
if ($requestFiles.Count -ne 1) { Fail-Closed "exactly one runtime request JSON required; found $($requestFiles.Count)" 5 }
$requestPath = $requestFiles[0].FullName
try { $request = Get-Content -LiteralPath $requestPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { Fail-Closed ('runtime request JSON invalid: ' + $_.Exception.Message) 5 }

if ([int]$request.schema_version -ne 1) { Fail-Closed 'request schema_version mismatch' 5 }
if ([string]$request.contract_id -cne $ExpectedRequestContract) { Fail-Closed 'request contract mismatch' 5 }
if ([string]$request.state -cne 'RUNTIME_PENDING') { Fail-Closed 'request state must be RUNTIME_PENDING' 5 }
if ([bool]$request.runtime_authority) { Fail-Closed 'request cannot grant runtime authority' 5 }
if ([bool]$request.promotion_eligible) { Fail-Closed 'request cannot grant promotion eligibility' 5 }

$requestId = [string]$request.request_id
$candidateId = [string]$request.candidate.candidate_id
$sourceSha = [string]$request.candidate.source_sha
$innerName = [string]$request.candidate.artifact_filename
$innerExpectedSha = [string]$request.candidate.artifact_sha256
$innerExpectedSize = [long]$request.candidate.artifact_size_bytes
$candidateProviderArtifactId = [long]$request.candidate.provider_artifact_id
$candidateProviderDigestRaw = [string]$request.candidate.provider_artifact_digest
$candidateProviderBuildRunId = [long]$request.candidate.provider_build_run_id

if ($sourceSha -cne $ExpectedRequestSourceSha) { Fail-Closed 'request source SHA differs from pinned request artifact source' 5 }
if ($candidateProviderBuildRunId -ne $RequestProviderBuildRunId) { Fail-Closed 'request and candidate provider build runs must match' 5 }
if (-not (Test-LowerHex $innerExpectedSha 64)) { Fail-Closed 'request inner artifact SHA-256 invalid' 5 }
if (-not (Test-LowerHex $candidateProviderDigestRaw 64)) { Fail-Closed 'request candidate provider digest invalid' 5 }
if ($innerExpectedSize -le 0 -or $candidateProviderArtifactId -le 0) { Fail-Closed 'request candidate size/provider id invalid' 5 }
if ([string]::IsNullOrWhiteSpace($innerName) -or [IO.Path]::GetFileName($innerName) -cne $innerName) { Fail-Closed 'request artifact filename must be a basename' 5 }

if ($candidateId -cmatch '^PNCC-V7\.0\.0-([0-9A-F]{12})$') {
    $expectedCandidateProviderName = 'PNCC-V7.0.0-' + $sourceSha
} elseif ($candidateId -cmatch '^PNCC-RC14\.39-([0-9A-F]{12})$') {
    $expectedCandidateProviderName = 'PNCC-RC14.39-' + $sourceSha
} else {
    Fail-Closed 'unsupported candidate id for provider bootstrap' 5
}
if ($Matches[1] -cne $sourceSha.Substring(0,12).ToUpperInvariant()) { Fail-Closed 'candidate/source suffix mismatch' 5 }

if ($Mode -eq 'Provider') {
    $candidateMetadata = Get-ProviderMetadata $candidateProviderArtifactId
    if ([long]$candidateMetadata.id -ne $candidateProviderArtifactId) { Fail-Closed 'candidate provider artifact id mismatch' 6 }
    if ([string]$candidateMetadata.name -cne $expectedCandidateProviderName) { Fail-Closed 'candidate provider artifact name mismatch' 6 }
    if ([bool]$candidateMetadata.expired) { Fail-Closed 'candidate provider artifact is expired' 6 }
    if ([string]$candidateMetadata.digest -cne ('sha256:' + $candidateProviderDigestRaw)) { Fail-Closed 'candidate provider digest/request mismatch' 6 }
    if ([long]$candidateMetadata.workflow_run.id -ne $candidateProviderBuildRunId) { Fail-Closed 'candidate provider build run mismatch' 6 }
    if ([string]$candidateMetadata.workflow_run.head_sha -cne $sourceSha) { Fail-Closed 'candidate provider source SHA mismatch' 6 }

    $downloadCandidate = & gh run download $candidateProviderBuildRunId --repo $Repository --name $expectedCandidateProviderName --dir $candidateProviderDir 2>&1
    if ($LASTEXITCODE -ne 0) { Fail-Closed ('candidate artifact download failed: ' + ($downloadCandidate -join ' ')) 6 }
}

$inner = Join-Path $candidateProviderDir $innerName
if (-not (Test-Path -LiteralPath $inner -PathType Leaf)) { Fail-Closed "inner candidate missing: $innerName" 7 }
$innerInfo = Get-Item -LiteralPath $inner
if ([long]$innerInfo.Length -ne $innerExpectedSize) { Fail-Closed "inner candidate size mismatch: $($innerInfo.Length)" 7 }
$innerSha = Get-FileSha256 $inner
if ($innerSha -cne $innerExpectedSha) { Fail-Closed "inner candidate SHA-256 mismatch: $innerSha" 7 }

$candidateManifestPath = Join-Path $candidateProviderDir 'candidate-manifest.json'
if (-not (Test-Path -LiteralPath $candidateManifestPath -PathType Leaf)) { Fail-Closed 'candidate-manifest.json missing from provider bundle' 7 }
try { $candidateManifest = Get-Content -LiteralPath $candidateManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { Fail-Closed ('candidate manifest JSON invalid: ' + $_.Exception.Message) 7 }
if ([string]$candidateManifest.candidate_id -cne $candidateId) { Fail-Closed 'candidate manifest/request candidate_id mismatch' 7 }
if ([string]$candidateManifest.source.commit_sha -cne $sourceSha) { Fail-Closed 'candidate manifest/request source SHA mismatch' 7 }
if ([string]$candidateManifest.artifact.filename -cne $innerName) { Fail-Closed 'candidate manifest/request filename mismatch' 7 }
if ([string]$candidateManifest.artifact.sha256 -cne $innerExpectedSha) { Fail-Closed 'candidate manifest/request artifact SHA mismatch' 7 }
if ([long]$candidateManifest.artifact.size_bytes -ne $innerExpectedSize) { Fail-Closed 'candidate manifest/request artifact size mismatch' 7 }
if ([string]$candidateManifest.runtime.qualification_state -cne 'NOT_VERIFIED') { Fail-Closed 'candidate manifest must remain NOT_VERIFIED before PRIVATE_RUNTIME' 7 }
if ([bool]$candidateManifest.runtime.promotion_eligible) { Fail-Closed 'candidate manifest cannot be promotion eligible' 7 }

$governedRequestPath = Join-Path $requestDir 'runtime-qualification-request.json'
Copy-Item -LiteralPath $requestPath -Destination $governedRequestPath -Force
$agentSource = Join-Path (Get-Location) $ExpectedAgentRelative
if (-not (Test-Path -LiteralPath $agentSource -PathType Leaf)) { Fail-Closed 'runtime agent source missing from repository checkout' 8 }
Copy-Item -LiteralPath $agentSource -Destination (Join-Path $agentDir 'Invoke-PnccRuntimeQualificationAgent.ps1') -Force

$manifest = [ordered]@{
    schema_version = 2
    bootstrap_id = 'PNCC_RUNTIME_WORKSPACE_BOOTSTRAP_V2'
    created_utc = [DateTime]::UtcNow.ToString('o')
    mode = $Mode
    repository = $Repository
    request_provider = [ordered]@{
        artifact_id = $RequestProviderArtifactId
        artifact_name = $ExpectedRequestArtifactName
        artifact_digest = $ExpectedRequestProviderDigest
        provider_build_run_id = $RequestProviderBuildRunId
        source_sha = $ExpectedRequestSourceSha
        request_id = $requestId
    }
    candidate = [ordered]@{
        candidate_id = $candidateId
        source_sha = $sourceSha
        artifact_filename = $innerName
        artifact_sha256 = $innerSha
        artifact_size_bytes = [long]$innerInfo.Length
        provider_artifact_id = $candidateProviderArtifactId
        provider_artifact_name = $expectedCandidateProviderName
        provider_artifact_digest = ('sha256:' + $candidateProviderDigestRaw)
        provider_build_run_id = $candidateProviderBuildRunId
    }
    boundaries = [ordered]@{
        private_evidence = 'private-evidence'
        public_safe = 'public-safe'
        runtime_mutation_permitted = $false
        runtime_authority = $false
        promotion_eligible = $false
    }
}
$manifestPath = Join-Path $workspace 'workspace-manifest.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$agentOutput = Join-Path $workspace 'agent-dry-run'
& (Join-Path $agentDir 'Invoke-PnccRuntimeQualificationAgent.ps1') `
    -RequestPath $governedRequestPath `
    -OutputDirectory $agentOutput `
    -ExpectedRequestId $requestId `
    -ExpectedCandidateId $candidateId `
    -ExpectedSourceSha $sourceSha `
    -ExpectedArtifactSha256 $innerExpectedSha `
    -DryRun
if ($LASTEXITCODE -ne 0) { Fail-Closed "runtime agent dry-run failed with exit code $LASTEXITCODE" 8 }

Write-Output "PNCC_RUNTIME_BOOTSTRAP=PASS MODE=$Mode REQUEST_ID=$requestId CANDIDATE_ID=$candidateId SOURCE_SHA=$sourceSha ARTIFACT_SHA256=$innerSha RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false"
Write-Output "WORKSPACE=$workspace"
Write-Output "MANIFEST=$manifestPath"
Write-Output "PRIVATE_EVIDENCE=$privateDir"
Write-Output "PUBLIC_SAFE=$publicDir"
exit 0
