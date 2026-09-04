Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedCompilerSize = 14304168
$ExpectedCompilerSha256 = '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f'
$CompilerUrl = 'https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/innosetup-7.1.0-x64.exe'
$CompilerAsset = 'innosetup-7.1.0-x64.exe'
$ExpectedIssBlob = 'd30a158aef3535a9066608495b45abcf41112926'
$IssPath = 'installer/windows/VPS-Control-PNCC.iss'
$CandidateName = 'VPS-Control-PNCC-v7.0.2-setup.exe'
$Wu199Size = 2230935
$Wu199Sha = '13ea7db85ce1c997f1bcc9566c615c1000eeaf33909a208ab6207f4e5ba22f06'

function Fail([string]$Message) { throw $Message }

$issueBody = [Environment]::GetEnvironmentVariable('PNCC_ISSUE_BODY')
$mainSha = [Environment]::GetEnvironmentVariable('PNCC_MAIN_SHA')
$runnerTemp = [Environment]::GetEnvironmentVariable('RUNNER_TEMP')
$githubOutput = [Environment]::GetEnvironmentVariable('GITHUB_OUTPUT')
if ([string]::IsNullOrWhiteSpace($issueBody)) { Fail 'ISSUE_BODY_MISSING' }
if ([string]::IsNullOrWhiteSpace($mainSha) -or $mainSha -notmatch '^[0-9a-f]{40}$') { Fail 'MAIN_SHA_INVALID' }
if ([string]::IsNullOrWhiteSpace($runnerTemp)) { Fail 'RUNNER_TEMP_MISSING' }
if ([string]::IsNullOrWhiteSpace($githubOutput)) { Fail 'GITHUB_OUTPUT_MISSING' }
$escapedMain = [Regex]::Escape($mainSha)
$markerPattern = '<!--\s*PNCC-WU200-ARTIFACT-BUILD-EXECUTE\s+schema=1\s+expected_main=' + $escapedMain + '\s*-->'
if ([Regex]::Matches($issueBody, $markerPattern).Count -ne 1) { Fail 'EXECUTION_MARKER_INVALID' }
if ([Regex]::Matches($issueBody, 'PNCC-WU200-ARTIFACT-BUILD-EXECUTE').Count -ne 1) { Fail 'EXECUTION_MARKER_AMBIGUOUS' }

$actualHead = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualHead -ne $mainSha) { Fail 'CHECKOUT_IDENTITY_MISMATCH' }
$issBlob = (git rev-parse ($mainSha + ':' + $IssPath)).Trim()
if ($LASTEXITCODE -ne 0 -or $issBlob -ne $ExpectedIssBlob) { Fail 'INSTALLER_DEFINITION_BLOB_MISMATCH' }

$compilerSetup = Join-Path $runnerTemp $CompilerAsset
$innoDir = Join-Path $runnerTemp 'pncc-inno-7.1.0-wu200'
$outputDir = Join-Path $runnerTemp 'pncc-installer-artifact-wu200'
$candidatePath = Join-Path $outputDir $CandidateName
foreach ($path in @($compilerSetup,$innoDir,$outputDir)) { if (Test-Path -LiteralPath $path) { Fail 'PREEXISTING_TEMP_PATH' } }

$compilerObservedSize = $null
$compilerObservedSha = $null
$candidateSize = $null
$candidateSha = $null
$byteIdentical = $false
$buildCompleted = $false
try {
    Invoke-WebRequest -Uri $CompilerUrl -OutFile $compilerSetup -UseBasicParsing
    $compilerObservedSize = (Get-Item -LiteralPath $compilerSetup).Length
    $compilerObservedSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $compilerSetup).Hash.ToLowerInvariant()
    if ($compilerObservedSize -ne $ExpectedCompilerSize) { Fail 'COMPILER_SIZE_MISMATCH' }
    if ($compilerObservedSha -ne $ExpectedCompilerSha256) { Fail 'COMPILER_SHA256_MISMATCH' }

    New-Item -ItemType Directory -Path $innoDir -Force | Out-Null
    $setupProcess = Start-Process -FilePath $compilerSetup -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',('/DIR=' + $innoDir)) -Wait -PassThru
    if ($setupProcess.ExitCode -ne 0) { Fail ('COMPILER_EPHEMERAL_INSTALL_FAILED_' + $setupProcess.ExitCode) }
    $iscc = Join-Path $innoDir 'ISCC.exe'
    if (-not (Test-Path -LiteralPath $iscc -PathType Leaf)) { Fail 'ISCC_NOT_FOUND' }

    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    $issFull = (Resolve-Path -LiteralPath $IssPath).Path
    $compileProcess = Start-Process -FilePath $iscc -ArgumentList @('/Q',('/O' + $outputDir),('/F' + [IO.Path]::GetFileNameWithoutExtension($CandidateName)),$issFull) -Wait -PassThru
    if ($compileProcess.ExitCode -ne 0) { Fail ('ISCC_BUILD_FAILED_' + $compileProcess.ExitCode) }
    if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) { Fail 'EXPECTED_CANDIDATE_NOT_FOUND' }
    $payload = @(Get-ChildItem -LiteralPath $outputDir -File)
    if ($payload.Count -ne 1 -or $payload[0].Name -ne $CandidateName) { Fail 'ARTIFACT_PAYLOAD_NOT_SINGLE_EXACT_CANDIDATE' }

    $candidateSize = $payload[0].Length
    if ($candidateSize -le 0) { Fail 'CANDIDATE_EMPTY' }
    $candidateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $candidatePath).Hash.ToLowerInvariant()
    if ($candidateSha -notmatch '^[0-9a-f]{64}$') { Fail 'CANDIDATE_SHA256_INVALID' }
    $byteIdentical = (($candidateSize -eq $Wu199Size) -and ($candidateSha -eq $Wu199Sha))
    $buildCompleted = $true
}
finally {
    if (Test-Path -LiteralPath $innoDir) { Remove-Item -LiteralPath $innoDir -Recurse -Force }
    if (Test-Path -LiteralPath $compilerSetup) { Remove-Item -LiteralPath $compilerSetup -Force }
}
if (-not $buildCompleted) { if (Test-Path -LiteralPath $outputDir) { Remove-Item -LiteralPath $outputDir -Recurse -Force }; Fail 'BUILD_NOT_COMPLETED' }
if (Test-Path -LiteralPath $compilerSetup) { Fail 'COMPILER_SETUP_NOT_DELETED' }
if (Test-Path -LiteralPath $innoDir) { Fail 'EPHEMERAL_COMPILER_NOT_DELETED' }

@('candidate_path=' + $candidatePath,'candidate_sha256=' + $candidateSha,'candidate_size=' + $candidateSize,'wu199_byte_identical=' + $byteIdentical.ToString().ToLowerInvariant()) | Add-Content -LiteralPath $githubOutput -Encoding utf8
$receipt = [ordered]@{
    schema_version = 1; role = 'REPRODUCIBLE_INSTALLER_ARTIFACT_PREUPLOAD_RECEIPT'; work_unit_id = 'PIPE-WU-200'; main_sha = $mainSha
    runner_class = 'GITHUB_HOSTED'; compiler_expected_size_bytes = $ExpectedCompilerSize; compiler_observed_size_bytes = $compilerObservedSize
    compiler_expected_sha256 = $ExpectedCompilerSha256; compiler_observed_sha256 = $compilerObservedSha; compiler_identity_verified = $true
    installer_definition_path = $IssPath; installer_definition_git_blob_sha = $issBlob; candidate_filename = $CandidateName
    candidate_size_bytes = $candidateSize; candidate_sha256 = $candidateSha; wu199_reference_size_bytes = $Wu199Size; wu199_reference_sha256 = $Wu199Sha
    wu199_byte_identical = $byteIdentical; artifact_payload_count = 1; artifact_upload_authorized = $true
    product_runtime_mutated = $false; release_created = $false; tag_created = $false; stable_transition = $false
    built_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
}
Write-Output ('PNCC_WU200_ARTIFACT_PREUPLOAD_RECEIPT=' + ($receipt | ConvertTo-Json -Compress))
