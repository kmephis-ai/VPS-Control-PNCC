[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [ValidateSet('Provider','Fixture')][string]$Mode = 'Provider',
    [string]$FixtureBundleDirectory,
    [string]$Repository = 'kmephis-ai/VPS-Control-PNCC',
    [long]$ProviderArtifactId = 9661221985,
    [long]$ProviderBuildRunId = 33107824902
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$ExpectedArtifactName = 'PNCC-RC14.39-90c9e8698c6468d576aecbc60d940be9d5c6baab'
$ExpectedRequestId = 'PNCC-RQ-RC14.39-90C9E8698C64'
$ExpectedCandidateId = 'PNCC-RC14.39-90C9E8698C64'
$ExpectedSourceSha = '90c9e8698c6468d576aecbc60d940be9d5c6baab'
$ExpectedInnerName = 'VPS-Control-v7.0.0-rc14.39.zip'
$ExpectedInnerSha256 = '8caad796469886b90d9928fba385fc4a4f0f3d60bcb6ee6b7cb98c4c2e4390b3'
$ExpectedInnerSize = 700961L
$ExpectedProviderDigest = 'sha256:eaf9844e8901cce7b1ebc866550e37cfd72393afc67075c27cba6703a415b68e'
$ExpectedRequestRelative = '.pncc-dev/requests/runtime-qualification-rc14.39.json'
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

if ($Mode -eq 'Provider') {
    Assert-Command 'gh'
    $authStatus = & gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) { Fail-Closed ('gh auth status failed: ' + ($authStatus -join ' ')) 3 }
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$workspace = Join-Path $OutputRoot ("PNCC-RUNTIME-QUALIFICATION-RC14.39-$stamp")
$providerDir = Join-Path $workspace 'provider-artifact'
$privateDir = Join-Path $workspace 'private-evidence'
$publicDir = Join-Path $workspace 'public-safe'
$agentDir = Join-Path $workspace 'agent'
$requestDir = Join-Path $workspace 'request'
@($workspace,$providerDir,$privateDir,$publicDir,$agentDir,$requestDir) | ForEach-Object { New-Item -ItemType Directory -Path $_ -Force | Out-Null }

$metadata = $null
if ($Mode -eq 'Provider') {
    $metaRaw = & gh api ("repos/{0}/actions/artifacts/{1}" -f $Repository,$ProviderArtifactId) 2>&1
    if ($LASTEXITCODE -ne 0) { Fail-Closed ('artifact metadata acquisition failed: ' + ($metaRaw -join ' ')) 4 }
    try { $metadata = (($metaRaw -join "`n") | ConvertFrom-Json) } catch { Fail-Closed ('artifact metadata JSON invalid: ' + $_.Exception.Message) 4 }
    if ([long]$metadata.id -ne $ProviderArtifactId) { Fail-Closed 'provider artifact id mismatch' 4 }
    if ([string]$metadata.name -ne $ExpectedArtifactName) { Fail-Closed 'provider artifact name mismatch' 4 }
    if ([bool]$metadata.expired) { Fail-Closed 'provider artifact is expired' 4 }
    if ([string]$metadata.digest -ne $ExpectedProviderDigest) { Fail-Closed 'provider artifact digest metadata mismatch' 4 }
    if ([long]$metadata.workflow_run.id -ne $ProviderBuildRunId) { Fail-Closed 'provider build run id mismatch' 4 }
    if ([string]$metadata.workflow_run.head_sha -ne $ExpectedSourceSha) { Fail-Closed 'provider source SHA mismatch' 4 }

    $downloadOutput = & gh run download $ProviderBuildRunId --repo $Repository --name $ExpectedArtifactName --dir $providerDir 2>&1
    if ($LASTEXITCODE -ne 0) { Fail-Closed ('provider artifact download failed: ' + ($downloadOutput -join ' ')) 4 }
} else {
    if ([string]::IsNullOrWhiteSpace($FixtureBundleDirectory)) { Fail-Closed 'FixtureBundleDirectory is required in Fixture mode' 2 }
    if (-not (Test-Path -LiteralPath $FixtureBundleDirectory -PathType Container)) { Fail-Closed 'fixture bundle directory not found' 2 }
    Get-ChildItem -LiteralPath $FixtureBundleDirectory -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $providerDir -Recurse -Force
    }
}

$inner = Join-Path $providerDir $ExpectedInnerName
if (-not (Test-Path -LiteralPath $inner -PathType Leaf)) { Fail-Closed "inner candidate missing: $ExpectedInnerName" 5 }
$innerInfo = Get-Item -LiteralPath $inner
if ([long]$innerInfo.Length -ne $ExpectedInnerSize) { Fail-Closed "inner candidate size mismatch: $($innerInfo.Length)" 5 }
$innerSha = Get-FileSha256 $inner
if ($innerSha -ne $ExpectedInnerSha256) { Fail-Closed "inner candidate SHA-256 mismatch: $innerSha" 5 }

$requestSource = Join-Path (Get-Location) $ExpectedRequestRelative
$agentSource = Join-Path (Get-Location) $ExpectedAgentRelative
if (-not (Test-Path -LiteralPath $requestSource -PathType Leaf)) { Fail-Closed 'governed request source missing from repository checkout' 6 }
if (-not (Test-Path -LiteralPath $agentSource -PathType Leaf)) { Fail-Closed 'runtime agent source missing from repository checkout' 6 }
Copy-Item -LiteralPath $requestSource -Destination (Join-Path $requestDir 'runtime-qualification-request.json') -Force
Copy-Item -LiteralPath $agentSource -Destination (Join-Path $agentDir 'Invoke-PnccRuntimeQualificationAgent.ps1') -Force

$manifest = [ordered]@{
    schema_version = 1
    bootstrap_id = 'PNCC_RUNTIME_WORKSPACE_BOOTSTRAP_V1'
    created_utc = [DateTime]::UtcNow.ToString('o')
    mode = $Mode
    repository = $Repository
    candidate = [ordered]@{
        source_sha = $ExpectedSourceSha
        artifact_filename = $ExpectedInnerName
        artifact_sha256 = $innerSha
        artifact_size_bytes = [long]$innerInfo.Length
        provider_artifact_id = $ProviderArtifactId
        provider_artifact_digest = $ExpectedProviderDigest
        provider_build_run_id = $ProviderBuildRunId
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
    -RequestPath (Join-Path $requestDir 'runtime-qualification-request.json') `
    -OutputDirectory $agentOutput `
    -ExpectedRequestId $ExpectedRequestId `
    -ExpectedCandidateId $ExpectedCandidateId `
    -ExpectedSourceSha $ExpectedSourceSha `
    -ExpectedArtifactSha256 $ExpectedInnerSha256 `
    -DryRun
if ($LASTEXITCODE -ne 0) { Fail-Closed "runtime agent dry-run failed with exit code $LASTEXITCODE" 7 }

Write-Output "PNCC_RUNTIME_BOOTSTRAP=PASS MODE=$Mode SOURCE_SHA=$ExpectedSourceSha ARTIFACT_SHA256=$innerSha RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false"
Write-Output "WORKSPACE=$workspace"
Write-Output "MANIFEST=$manifestPath"
Write-Output "PRIVATE_EVIDENCE=$privateDir"
Write-Output "PUBLIC_SAFE=$publicDir"
exit 0
