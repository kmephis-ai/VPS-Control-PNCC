[CmdletBinding()]
param(
    [string]$Root = 'E:\!Chrome_Downloads',
    [string]$Repository = 'kmephis-ai/VPS-Control-PNCC',
    [Parameter(Mandatory=$true)][string]$RepositorySha,
    [Parameter(Mandatory=$true)][long]$RequestProviderArtifactId,
    [Parameter(Mandatory=$true)][long]$RequestProviderBuildRunId,
    [Parameter(Mandatory=$true)][string]$ExpectedRequestArtifactName,
    [Parameter(Mandatory=$true)][string]$ExpectedRequestProviderDigest,
    [Parameter(Mandatory=$true)][string]$ExpectedRequestSourceSha
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ExpectedV631Sha = '385e5178f10e79b0b234376e6a6671b64ce523a3971b2b4341ec94ce1efee11e'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$runRoot = Join-Path $Root ("PNCC-PHYSICAL-PREFLIGHT-$stamp")
$checkout = Join-Path $runRoot 'repo'
$runtimeRoot = Join-Path $runRoot 'runtime'
$logPath = Join-Path $runRoot 'PNCC-PHYSICAL-PREFLIGHT.log'
$returnZip = Join-Path $Root ("PNCC-PHYSICAL-PREFLIGHT-RETURN-$stamp.zip")
New-Item -ItemType Directory -Force -Path $runRoot,$runtimeRoot | Out-Null
Start-Transcript -LiteralPath $logPath -Force | Out-Null
$exitCode = 1

function Invoke-NativeCaptured([string]$FilePath,[object[]]$Arguments){
    $saved = $ErrorActionPreference
    $nativeOut = @()
    $nativeRc = 1
    try {
        $ErrorActionPreference = 'Continue'
        $nativeOut = @(& $FilePath @Arguments 2>&1)
        $nativeRc = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $saved
    }
    return [pscustomobject]@{
        ExitCode = [int]$nativeRc
        Output = @($nativeOut | ForEach-Object { [string]$_ })
    }
}

function Test-LowerHex([string]$Value,[int]$Length){
    if([string]::IsNullOrWhiteSpace($Value) -or $Value.Length -ne $Length){ return $false }
    return ($Value -cmatch ('^[0-9a-f]{' + $Length + '}$'))
}

try {
    Write-Host 'PNCC Owner Physical Preflight v2'
    Write-Host "ROOT=$runRoot"
    Write-Host "HARNESS_PIN=$RepositorySha"
    Write-Host "REQUEST_PROVIDER_ARTIFACT_ID=$RequestProviderArtifactId"
    Write-Host "REQUEST_PROVIDER_BUILD_RUN_ID=$RequestProviderBuildRunId"
    Write-Host "REQUEST_PROVIDER_NAME=$ExpectedRequestArtifactName"
    Write-Host "REQUEST_PROVIDER_SOURCE_SHA=$ExpectedRequestSourceSha"
    Write-Host 'RUNTIME_MUTATION=false'

    if(-not (Test-LowerHex $RepositorySha 40)){ throw 'RepositorySha must be lowercase 40-hex' }
    if(-not (Test-LowerHex $ExpectedRequestSourceSha 40)){ throw 'ExpectedRequestSourceSha must be lowercase 40-hex' }
    if($ExpectedRequestProviderDigest -cnotmatch '^sha256:[0-9a-f]{64}$'){ throw 'ExpectedRequestProviderDigest must be sha256:<64 lowercase hex>' }
    if($RequestProviderArtifactId -le 0 -or $RequestProviderBuildRunId -le 0){ throw 'request provider ids must be positive' }

    foreach($name in @('git','gh')) {
        if($null -eq (Get-Command $name -ErrorAction SilentlyContinue)) { throw "required command missing: $name" }
    }
    $ghAuth = Invoke-NativeCaptured 'gh' @('auth','status')
    $ghAuth.Output | ForEach-Object { Write-Host $_ }
    if($ghAuth.ExitCode -ne 0){ throw 'gh authentication unavailable' }

    & git clone --filter=blob:none --no-checkout ("https://github.com/{0}.git" -f $Repository) $checkout
    if($LASTEXITCODE -ne 0){ throw 'git clone failed' }
    Push-Location $checkout
    try {
        & git fetch --depth=1 origin $RepositorySha
        if($LASTEXITCODE -ne 0){ throw 'exact SHA fetch failed' }
        & git checkout --detach $RepositorySha
        if($LASTEXITCODE -ne 0){ throw 'exact SHA checkout failed' }
        $actualSha = (& git rev-parse HEAD).Trim()
        if($actualSha -cne $RepositorySha){ throw "checkout SHA mismatch: $actualSha" }
        Write-Host "HARNESS_SHA=$actualSha"

        $bootstrapArgs = @(
            '-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File','.\tools\runtime-agent\Initialize-PnccRuntimeQualificationWorkspace.ps1',
            '-OutputRoot',$runtimeRoot,
            '-Mode','Provider',
            '-RequestProviderArtifactId',[string]$RequestProviderArtifactId,
            '-RequestProviderBuildRunId',[string]$RequestProviderBuildRunId,
            '-ExpectedRequestArtifactName',$ExpectedRequestArtifactName,
            '-ExpectedRequestProviderDigest',$ExpectedRequestProviderDigest,
            '-ExpectedRequestSourceSha',$ExpectedRequestSourceSha
        )
        $bootstrap = Invoke-NativeCaptured 'powershell.exe' $bootstrapArgs
        $bootstrap.Output | ForEach-Object { Write-Host $_ }
        if($bootstrap.ExitCode -ne 0){ throw "workspace bootstrap failed rc=$($bootstrap.ExitCode)" }
        $workspaceLine = @($bootstrap.Output | Where-Object { $_ -like 'WORKSPACE=*' } | Select-Object -Last 1)
        if($workspaceLine.Count -ne 1){ throw 'workspace path not emitted' }
        $workspace = $workspaceLine[0].Substring('WORKSPACE='.Length)
        if(-not (Test-Path -LiteralPath $workspace -PathType Container)){ throw 'emitted workspace path not found' }
        $workspaceManifest = Get-Content -LiteralPath (Join-Path $workspace 'workspace-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if([int]$workspaceManifest.schema_version -ne 2){ throw 'workspace manifest V2 required' }
        Write-Host "REQUEST_ID=$($workspaceManifest.request_provider.request_id)"
        Write-Host "CANDIDATE_ID=$($workspaceManifest.candidate.candidate_id)"
        Write-Host "CANDIDATE_SHA256=$($workspaceManifest.candidate.artifact_sha256)"

        $rollbackPath = $null
        $candidateRoots = @('M:\YandexDisk\!Coding\VPS-Control','E:\!Chrome_Downloads') | Where-Object { Test-Path -LiteralPath $_ -PathType Container }
        foreach($rootCandidate in $candidateRoots){
            $files = @(Get-ChildItem -LiteralPath $rootCandidate -Recurse -File -Filter '*.ps1' -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '6[._-]?3[._-]?1|v6[._-]?3' })
            foreach($file in $files){
                try {
                    $h = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
                    if($h -eq $ExpectedV631Sha){ $rollbackPath = $file.FullName; break }
                } catch {}
            }
            if($rollbackPath){ break }
        }
        if($rollbackPath){ Write-Host "V631_PATH=$rollbackPath" } else { Write-Host 'V631_PATH=NOT_FOUND' }

        $preflightPath = Join-Path $workspace 'private-evidence\physical-preflight.json'
        $preflightArgs = @('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File','.\tools\runtime-agent\Invoke-PnccPrivateRuntimePreflight.ps1','-WorkspacePath',$workspace,'-OutputPath',$preflightPath,'-Mode','Live')
        if($rollbackPath){ $preflightArgs += @('-V631Path',$rollbackPath) }
        $preflight = Invoke-NativeCaptured 'powershell.exe' $preflightArgs
        $preflight.Output | ForEach-Object { Write-Host $_ }
        if($preflight.ExitCode -ne 0){ throw "private preflight failed rc=$($preflight.ExitCode)" }
        if(-not (Test-Path -LiteralPath $preflightPath -PathType Leaf)){ throw 'preflight result missing' }
        $result = Get-Content -LiteralPath $preflightPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if([string]$result.request_id -cne [string]$workspaceManifest.request_provider.request_id){ throw 'preflight/workspace request id mismatch' }
        if([string]$result.candidate_id -cne [string]$workspaceManifest.candidate.candidate_id){ throw 'preflight/workspace candidate id mismatch' }
        Write-Host "PREFLIGHT_STATE=$($result.preflight_state)"
        Write-Host "FAILURE_CLASSIFICATION=$($result.failure_classification)"
        Write-Host "FAILED_CHECKS=$(@($result.checks | Where-Object { -not $_.pass }).Count)"
        Write-Host 'RUNTIME_MUTATION=false'
        Write-Host 'RUNTIME_AUTHORITY=false'
        Write-Host 'PROMOTION_ELIGIBLE=false'
        $exitCode = 0
    } finally {
        Pop-Location
    }
} catch {
    Write-Error $_
    $exitCode = 1
} finally {
    try { Stop-Transcript | Out-Null } catch {}
    try {
        if(Test-Path -LiteralPath $returnZip){ Remove-Item -LiteralPath $returnZip -Force }
        Compress-Archive -Path (Join-Path $runRoot '*') -DestinationPath $returnZip -CompressionLevel Optimal -Force
    } catch {
        Write-Warning ("return bundle creation failed: " + $_.Exception.Message)
    }
    Write-Host "EXIT_CODE=$exitCode"
    Write-Host "LOG_PATH=$logPath"
    Write-Host "RETURN_ZIP=$returnZip"
}
exit $exitCode
