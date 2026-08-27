[CmdletBinding()]
param(
    [string]$Root = 'E:\!Chrome_Downloads',
    [string]$Repository = 'kmephis-ai/VPS-Control-PNCC',
    [string]$RepositorySha = '010c44db41094c79a6c0df96c95a70a36da868c0'
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

try {
    Write-Host "PNCC Owner Physical Preflight"
    Write-Host "ROOT=$runRoot"
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
        if($actualSha -ne $RepositorySha){ throw "checkout SHA mismatch: $actualSha" }
        Write-Host "HARNESS_SHA=$actualSha"

        $bootstrap = Invoke-NativeCaptured 'powershell.exe' @('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File','.\tools\runtime-agent\Initialize-PnccRuntimeQualificationWorkspace.ps1','-OutputRoot',$runtimeRoot)
        $bootstrap.Output | ForEach-Object { Write-Host $_ }
        if($bootstrap.ExitCode -ne 0){ throw "workspace bootstrap failed rc=$($bootstrap.ExitCode)" }
        $workspaceLine = @($bootstrap.Output | Where-Object { $_ -like 'WORKSPACE=*' } | Select-Object -Last 1)
        if($workspaceLine.Count -ne 1){ throw 'workspace path not emitted' }
        $workspace = $workspaceLine[0].Substring('WORKSPACE='.Length)

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
        Write-Host "PREFLIGHT_STATE=$($result.preflight_state)"
        Write-Host "FAILURE_CLASSIFICATION=$($result.failure_classification)"
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
    } catch {}
    Write-Host "LOG_PATH=$logPath"
    Write-Host "RETURN_ZIP=$returnZip"
}
exit $exitCode
