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

$ExpectedCandidateName = 'VPS-Control-v7.0.0-rc14.39.zip'
$ExpectedCandidateSha = '8caad796469886b90d9928fba385fc4a4f0f3d60bcb6ee6b7cb98c4c2e4390b3'
$ExpectedCandidateSize = 700961L
$ExpectedV631Sha = '385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$ExpectedPrimaryPort = 1081
$ExpectedReservePort = 1080

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
    $isWindows = ($env:OS -eq 'Windows_NT')
    $windowsReason = 'Windows_NT not observed'
    if($isWindows){ $windowsReason = 'Windows_NT observed' }
    $checks += New-Check 'WINDOWS_BASELINE' $isWindows $windowsReason

    $psOk = ($PSVersionTable.PSVersion.Major -gt 5 -or ($PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -ge 1))
    $checks += New-Check 'POWERSHELL_BASELINE' $psOk ("PowerShell " + $PSVersionTable.PSVersion.ToString())

    $candidate = Join-Path (Join-Path $WorkspacePath 'provider-artifact') $ExpectedCandidateName
    $candidatePass = $false
    $candidateReason = 'candidate missing'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $info = Get-Item -LiteralPath $candidate
        $sha = Get-Sha256 $candidate
        $candidatePass = ([long]$info.Length -eq $ExpectedCandidateSize -and $sha -eq $ExpectedCandidateSha)
        $candidateReason = "sha256=$sha bytes=$($info.Length)"
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
        $rollbackOk = ($rollbackSha -eq $ExpectedV631Sha)
        $rollbackReason = "sha256=$rollbackSha"
    }
    $checks += New-Check 'ROLLBACK_IDENTITY' $rollbackOk $rollbackReason

    $observations.listeners = @((Get-ListenerObservation $ExpectedReservePort),(Get-ListenerObservation $ExpectedPrimaryPort))
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
    schema_version = 1
    contract_id = 'PNCC_PRIVATE_RUNTIME_PREFLIGHT_V1'
    mode = $Mode
    workspace = $workspaceValue
    expected = [ordered]@{
        candidate_sha256 = $ExpectedCandidateSha
        candidate_size_bytes = $ExpectedCandidateSize
        v6_3_1_sha256 = $ExpectedV631Sha
        reserve_manual_port = $ExpectedReservePort
        primary_auto_port = $ExpectedPrimaryPort
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
Write-Output "PNCC_PRIVATE_RUNTIME_PREFLIGHT=$state MODE=$Mode FAILED_CHECKS=$($failed.Count) RUNTIME_MUTATION=false RUNTIME_AUTHORITY=false PROMOTION_ELIGIBLE=false"
Write-Output "PREFLIGHT_RESULT=$OutputPath"
exit 0
