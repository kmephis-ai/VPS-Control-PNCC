Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedCompilerSize = 14304168
$ExpectedCompilerSha256 = '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f'
$CompilerUrl = 'https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/innosetup-7.1.0-x64.exe'
$CompilerAsset = 'innosetup-7.1.0-x64.exe'
$ExpectedIssBlob = 'd30a158aef3535a9066608495b45abcf41112926'
$IssPath = 'installer/windows/VPS-Control-PNCC.iss'
$ExpectedCandidate = 'VPS-Control-PNCC-v7.0.2-setup.exe'

function Fail([string]$Message) { throw $Message }

$issueBody = [Environment]::GetEnvironmentVariable('PNCC_ISSUE_BODY')
$mainSha = [Environment]::GetEnvironmentVariable('PNCC_MAIN_SHA')
$runnerTemp = [Environment]::GetEnvironmentVariable('RUNNER_TEMP')
if ([string]::IsNullOrWhiteSpace($issueBody)) { Fail 'ISSUE_BODY_MISSING' }
if ([string]::IsNullOrWhiteSpace($mainSha) -or $mainSha -notmatch '^[0-9a-f]{40}$') { Fail 'MAIN_SHA_INVALID' }
if ([string]::IsNullOrWhiteSpace($runnerTemp)) { Fail 'RUNNER_TEMP_MISSING' }
$escapedMain = [Regex]::Escape($mainSha)
$markerPattern = '<!--\s*PNCC-WU199-BUILD-EXECUTE\s+schema=1\s+expected_main=' + $escapedMain + '\s*-->'
$matches = [Regex]::Matches($issueBody, $markerPattern)
if ($matches.Count -ne 1) { Fail 'EXECUTION_MARKER_INVALID' }
if ([Regex]::Matches($issueBody, 'PNCC-WU199-BUILD-EXECUTE').Count -ne 1) { Fail 'EXECUTION_MARKER_AMBIGUOUS' }

$actualHead = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualHead -ne $mainSha) { Fail 'CHECKOUT_IDENTITY_MISMATCH' }
$issBlob = (git rev-parse ($mainSha + ':' + $IssPath)).Trim()
if ($LASTEXITCODE -ne 0 -or $issBlob -ne $ExpectedIssBlob) { Fail 'INSTALLER_DEFINITION_BLOB_MISMATCH' }

$compilerSetup = Join-Path $runnerTemp $CompilerAsset
$innoDir = Join-Path $runnerTemp 'pncc-inno-7.1.0'
$outputDir = Join-Path $runnerTemp 'pncc-installer-output'
$candidatePath = Join-Path $outputDir $ExpectedCandidate

if (Test-Path -LiteralPath $compilerSetup) { Fail 'COMPILER_SETUP_PREEXISTS' }
if (Test-Path -LiteralPath $innoDir) { Fail 'INNO_DIR_PREEXISTS' }
if (Test-Path -LiteralPath $outputDir) { Fail 'OUTPUT_DIR_PREEXISTS' }

$compilerObservedSize = $null
$compilerObservedSha = $null
$candidateSize = $null
$candidateSha = $null
$compilerVersion = $null
$buildCompleted = $false

try {
    Invoke-WebRequest -Uri $CompilerUrl -OutFile $compilerSetup -UseBasicParsing
    $compilerObservedSize = (Get-Item -LiteralPath $compilerSetup).Length
    $compilerObservedSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $compilerSetup).Hash.ToLowerInvariant()
    if ($compilerObservedSize -ne $ExpectedCompilerSize) { Fail 'COMPILER_SIZE_MISMATCH' }
    if ($compilerObservedSha -ne $ExpectedCompilerSha256) { Fail 'COMPILER_SHA256_MISMATCH' }

    New-Item -ItemType Directory -Path $innoDir -Force | Out-Null
    $setupArgs = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',('/DIR=' + $innoDir))
    $setupProcess = Start-Process -FilePath $compilerSetup -ArgumentList $setupArgs -Wait -PassThru
    if ($setupProcess.ExitCode -ne 0) { Fail ('COMPILER_EPHEMERAL_INSTALL_FAILED_' + $setupProcess.ExitCode) }

    $iscc = Join-Path $innoDir 'ISCC.exe'
    if (-not (Test-Path -LiteralPath $iscc -PathType Leaf)) { Fail 'ISCC_NOT_FOUND' }
    $compilerVersion = (Get-Item -LiteralPath $iscc).VersionInfo.FileVersion

    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    $issFull = (Resolve-Path -LiteralPath $IssPath).Path
    $isccArgs = @('/Q',('/O' + $outputDir),('/F' + [IO.Path]::GetFileNameWithoutExtension($ExpectedCandidate)),$issFull)
    $compileProcess = Start-Process -FilePath $iscc -ArgumentList $isccArgs -Wait -PassThru
    if ($compileProcess.ExitCode -ne 0) { Fail ('ISCC_BUILD_FAILED_' + $compileProcess.ExitCode) }
    if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) { Fail 'EXPECTED_CANDIDATE_NOT_FOUND' }

    $candidateSize = (Get-Item -LiteralPath $candidatePath).Length
    if ($candidateSize -le 0) { Fail 'CANDIDATE_EMPTY' }
    $candidateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $candidatePath).Hash.ToLowerInvariant()
    if ($candidateSha -notmatch '^[0-9a-f]{64}$') { Fail 'CANDIDATE_SHA256_INVALID' }
    $buildCompleted = $true
}
finally {
    if (Test-Path -LiteralPath $candidatePath) { Remove-Item -LiteralPath $candidatePath -Force }
    if (Test-Path -LiteralPath $outputDir) { Remove-Item -LiteralPath $outputDir -Recurse -Force }
    if (Test-Path -LiteralPath $innoDir) { Remove-Item -LiteralPath $innoDir -Recurse -Force }
    if (Test-Path -LiteralPath $compilerSetup) { Remove-Item -LiteralPath $compilerSetup -Force }
}

if (-not $buildCompleted) { Fail 'BUILD_NOT_COMPLETED' }
if (Test-Path -LiteralPath $candidatePath) { Fail 'CANDIDATE_NOT_DELETED' }
if (Test-Path -LiteralPath $compilerSetup) { Fail 'COMPILER_SETUP_NOT_DELETED' }
if (Test-Path -LiteralPath $innoDir) { Fail 'EPHEMERAL_COMPILER_NOT_DELETED' }

$receipt = [ordered]@{
    schema_version = 1
    role = 'FIRST_INSTALLER_CANDIDATE_BUILD_PROVENANCE_RECEIPT'
    work_unit_id = 'PIPE-WU-199'
    main_sha = $mainSha
    runner_class = 'GITHUB_HOSTED'
    workspace_class = 'RUNNER_TEMP_EPHEMERAL_ONLY'
    compiler_repository = 'jrsoftware/issrc'
    compiler_tag = 'is-7_1_0'
    compiler_release_id = 369110765
    compiler_asset_id = 511336600
    compiler_asset_name = $CompilerAsset
    compiler_expected_size_bytes = $ExpectedCompilerSize
    compiler_observed_size_bytes = $compilerObservedSize
    compiler_expected_sha256 = $ExpectedCompilerSha256
    compiler_observed_sha256 = $compilerObservedSha
    compiler_identity_verified = $true
    compiler_file_version = $compilerVersion
    installer_definition_path = $IssPath
    installer_definition_git_blob_sha = $issBlob
    candidate_filename = $ExpectedCandidate
    candidate_size_bytes = $candidateSize
    candidate_sha256 = $candidateSha
    candidate_built = $true
    candidate_uploaded = $false
    candidate_persisted_after_job = $false
    compiler_persisted_after_job = $false
    product_runtime_mutated = $false
    release_created = $false
    tag_created = $false
    stable_transition = $false
    built_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
}
$compact = $receipt | ConvertTo-Json -Compress
Write-Output ('PNCC_WU199_BUILD_PROVENANCE_RECEIPT=' + $compact)
