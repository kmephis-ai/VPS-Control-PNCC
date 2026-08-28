[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$WorkspacePath,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [ValidateSet('Live','Fixture')][string]$Mode = 'Live',
    [string]$FixturePath,
    [string]$V631Path,
    [string]$ProxifierPath = 'C:\Program Files (x86)\Proxifier\Proxifier.exe'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$PolicyV631Sha = '385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$PolicyPrimaryPort = 1081
$PolicyReservePort = 1080
$PolicyReserveLifecycle = 'MANUAL_ONLY'
$PolicyPuttyPasswordArgument = '-pwfile'

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function New-Check([string]$Name, [bool]$Pass, [string]$Reason) {
    return [ordered]@{ name=$Name; pass=$Pass; reason=$Reason }
}

function Get-ListenerObservation([int]$Port) {
    try {
        $rows = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop)
        $owners = @()
        foreach($row in $rows) {
            $pidValue = [int]$row.OwningProcess
            $procName = $null
            try { $procName = (Get-Process -Id $pidValue -ErrorAction Stop).ProcessName } catch { $procName = 'UNKNOWN' }
            $owners += [ordered]@{ pid=$pidValue; process=$procName }
        }
        return [ordered]@{ port=$Port; listening=($rows.Count -gt 0); owners=$owners; observation_error=$null }
    } catch {
        return [ordered]@{ port=$Port; listening=$false; owners=@(); observation_error=$_.Exception.Message }
    }
}

function Get-ObservedProcesses {
    $names = @('Proxifier','powershell','pwsh')
    $rows = @()
    foreach($p in @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $names -contains $_.ProcessName -or $_.ProcessName -like '*VPS*' -or $_.ProcessName -like '*PNCC*' })) {
        $rows += [ordered]@{ pid=[int]$p.Id; name=[string]$p.ProcessName }
    }
    return @($rows | Sort-Object name,pid)
}

if (-not (Test-Path -LiteralPath $WorkspacePath -PathType Container)) {
    throw "workspace not found: $WorkspacePath"
}

$checks = @()
$observations = [ordered]@{}
$expectedCandidateName = $null
$expectedCandidateSha = $null
$expectedCandidateSize = 0L
$expectedCandidateId = $null
$expectedRequestId = $null
$expectedV631Sha = $PolicyV631Sha
$expectedPrimaryPort = $PolicyPrimaryPort
$expectedReservePort = $PolicyReservePort

if ($Mode -eq 'Fixture') {
    if ([string]::IsNullOrWhiteSpace($FixturePath) -or -not (Test-Path -LiteralPath $FixturePath -PathType Leaf)) { throw 'FixturePath is required in Fixture mode' }
    $fixture = Get-Content -LiteralPath $FixturePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $checks += New-Check 'WINDOWS_BASELINE' ([bool]$fixture.windows_baseline) 'fixture'
    $checks += New-Check 'POWERSHELL_BASELINE' ([bool]$fixture.powershell_baseline) 'fixture'
    $checks += New-Check 'CANDIDATE_IDENTITY' ([bool]$fixture.candidate_identity) 'fixture'
    $checks += New-Check 'PROXIFIER_PRESENT' ([bool]$fixture.proxifier_present) 'fixture'
    $checks += New-Check 'GH_AUTH' ([bool]$fixture.gh_auth) 'fixture'
    $checks += New-Check 'ROLLBACK_IDENTITY' ([bool]$fixture.rollback_identity) 'fixture'
    $observations.listeners = @($fixture.listeners)
    $observations.processes = @($fixture.processes)
} else {
    $manifestPath = Join-Path $WorkspacePath 'workspace-manifest.json'
    $requestPath = Join-Path $WorkspacePath 'request\runtime-qualification-request.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'workspace-manifest.json missing' }
    if (-not (Test-Path -LiteralPath $requestPath -PathType Leaf)) { throw 'runtime qualification request missing from workspace' }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $request = Get-Content -LiteralPath $requestPath -Raw -Encoding UTF8 | ConvertFrom-Json

    if ([int]$manifest.schema_version -ne 2 -or [string]$manifest.bootstrap_id -ne 'PNCC_RUNTIME_WORKSPACE_BOOTSTRAP_V2') { throw 'workspace bootstrap V2 required' }
    if ([bool]$manifest.boundaries.runtime_mutation_permitted -or [bool]$manifest.boundaries.runtime_authority -or [bool]$manifest.boundaries.promotion_eligible) { throw 'workspace authority boundary violation' }
    if ([string]$request.contract_id -ne 'PNCC_RUNTIME_QUALIFICATION_REQUEST_V1' -or [string]$request.state -ne 'RUNTIME_PENDING') { throw 'governed pending runtime request required' }
    if ([bool]$request.runtime_authority -or [bool]$request.promotion_eligible) { throw 'request cannot carry runtime/promotion authority' }

    $expectedCandidateName = [string]$request.candidate.artifact_filename
    $expectedCandidateSha = [string]$request.candidate.artifact_sha256
    $expectedCandidateSize = [long]$request.candidate.artifact_size_bytes
    $expectedCandidateId = [string]$request.candidate.candidate_id
    $expectedRequestId = [string]$request.request_id
    $expectedV631Sha = [string]$request.expected_invariants.v6_3_1_sha256
    $expectedPrimaryPort = [int]$request.expected_invariants.primary_auto_port
    $expectedReservePort = [int]$request.expected_invariants.reserve_manual_port

    if ($expectedV631Sha -ne $PolicyV631Sha) { throw 'V6.3.1 request invariant differs from policy' }
    if ($expectedPrimaryPort -ne $PolicyPrimaryPort) { throw 'PRIMARY_AUTO request invariant differs from policy' }
    if ($expectedReservePort -ne $PolicyReservePort) { throw 'RESERVE_MANUAL request invariant differs from policy' }
    if ([string]$request.expected_invariants.reserve_manual_lifecycle -ne $PolicyReserveLifecycle) { throw '1080 lifecycle request invariant differs from policy' }
    if ([string]$request.expected_invariants.putty_password_argument -ne $PolicyPuttyPasswordArgument) { throw 'PuTTY transport request invariant differs from policy' }
    if ([bool]$request.expected_invariants.plaintext_pw_allowed) { throw 'plaintext password transport cannot be allowed' }
    if ([bool]$request.expected_invariants.hostkey_verification_disable_allowed) { throw 'host-key verification cannot be disabled' }

    if ([string]$manifest.request_provider.request_id -ne $expectedRequestId) { throw 'workspace/request request_id mismatch' }
    if ([string]$manifest.candidate.candidate_id -ne $expectedCandidateId) { throw 'workspace/request candidate_id mismatch' }
    if ([string]$manifest.candidate.source_sha -ne [string]$request.candidate.source_sha) { throw 'workspace/request source SHA mismatch' }
    if ([string]$manifest.candidate.artifact_filename -ne $expectedCandidateName) { throw 'workspace/request candidate filename mismatch' }
    if ([string]$manifest.candidate.artifact_sha256 -ne $expectedCandidateSha) { throw 'workspace/request candidate SHA mismatch' }
    if ([long]$manifest.candidate.artifact_size_bytes -ne $expectedCandidateSize) { throw 'workspace/request candidate size mismatch' }

    $isWindows = ($env:OS -eq 'Windows_NT')
    $windowsReason = 'Windows_NT not observed'
    if($isWindows){ $windowsReason = 'Windows_NT observed' }
    $checks += New-Check 'WINDOWS_BASELINE' $isWindows $windowsReason

    $psOk = ($PSVersionTable.PSVersion.Major -gt 5 -or ($PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -ge 1))
    $checks += New-Check 'POWERSHELL_BASELINE' $psOk ("PowerShell " + $PSVersionTable.PSVersion.ToString())

    $candidate = Join-Path (Join-Path $WorkspacePath 'candidate-provider-artifact') $expectedCandidateName
    $candidatePass = $false
    $candidateReason = 'candidate missing'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $info = Get-Item -LiteralPath $candidate
        $sha = Get-Sha256 $candidate
        $candidatePass = ([long]$info.Length -eq $expectedCandidateSize -and $sha -eq $expectedCandidateSha)
        $candidateReason = "candidate_id=$expectedCandidateId sha256=$sha bytes=$($info.Length)"
    }
    $checks += New-Check 'CANDIDATE_IDENTITY' $candidatePass $candidateReason

    $proxifierPresent = Test-Path -LiteralPath $ProxifierPath -PathType Leaf
    $proxifierReason = 'Proxifier executable not found at governed path'
    if($proxifierPresent){ $proxifierReason = $ProxifierPath }
    $checks += New-Check 'PROXIFIER_PRESENT' $proxifierPresent $proxifierReason

    $gh = Get-Command gh -ErrorAction SilentlyContinue
    $ghOk = $false
    $ghReason = 'gh command missing'
    if ($null -ne $gh) {
        & gh auth status 1>$null 2>$null
        $ghOk = ($LASTEXITCODE -eq 0)
        if($ghOk){ $ghReason = 'gh authenticated' } else { $ghReason = 'gh auth status failed' }
    }
    $checks += New-Check 'GH_AUTH' $ghOk $ghReason

    $rollbackOk = $false
    $rollbackReason = 'V6.3.1 path not supplied'
    if (-not [string]::IsNullOrWhiteSpace($V631Path) -and (Test-Path -LiteralPath $V631Path -PathType Leaf)) {
        $rollbackSha = Get-Sha256 $V631Path
        $rollbackOk = ($rollbackSha -eq $expectedV631Sha)
        $rollbackReason = "sha256=$rollbackSha"
    }
    $checks += New-Check 'ROLLBACK_IDENTITY' $rollbackOk $rollbackReason

    $observations.listeners = @((Get-ListenerObservation $expectedReservePort),(Get-ListenerObservation $expectedPrimaryPort))
    $observations.processes = @(Get-ObservedProcesses)
}

$failed = @($checks | Where-Object { -not $_.pass })
$state = 'BLOCKED'
$failureClass = 'ENVIRONMENT_OR_BASELINE_BLOCKER'
if($failed.Count -eq 0){
    $state = 'READY'
    $failureClass = $null
}
$workspaceValue = [IO.Path]::GetFullPath($WorkspacePath)
if($Mode -eq 'Fixture'){ $workspaceValue = 'FIXTURE_WORKSPACE' }

$result = [ordered]@{
    schema_version = 2
    contract_id = 'PNCC_PRIVATE_RUNTIME_PREFLIGHT_V2'
    mode = $Mode
    workspace = $workspaceValue
    request_id = $expectedRequestId
    candidate_id = $expectedCandidateId
    expected = [ordered]@{
        candidate_filename = $expectedCandidateName
        candidate_sha256 = $expectedCandidateSha
        candidate_size_bytes = $expectedCandidateSize
        v6_3_1_sha256 = $expectedV631Sha
        reserve_manual_port = $expectedReservePort
        primary_auto_port = $expectedPrimaryPort
    }
    checks = $checks
    observations = $observations
    preflight_state = $state
    failure_classification = $failureClass
    runtime_mutation_permitted = $false
    runtime_authority = $false
    promotion_eligible = $false
}

$parent = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
$result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output "PNCC_PRIVATE_RUNTIME_PREFLIGHT=$state MODE=$Mode REQUEST_ID=$expectedRequestId CANDIDATE_ID=$expectedCandidateId FAILED_CHECKS=$($failed.Count) RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false"
Write-Output "PREFLIGHT_RESULT=$OutputPath"
exit 0
