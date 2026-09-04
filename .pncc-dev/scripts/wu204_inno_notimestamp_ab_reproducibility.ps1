Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$CompilerUrl = 'https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/innosetup-7.1.0-x64.exe'
$CompilerAsset = 'innosetup-7.1.0-x64.exe'
$ExpectedCompilerSize = 14304168
$ExpectedCompilerSha256 = '0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f'
$ExpectedIssBlob = 'd30a158aef3535a9066608495b45abcf41112926'
$IssPath = 'installer/windows/VPS-Control-PNCC.iss'
$SourcePath = 'src/windows-v7'
$CandidateName = 'VPS-Control-PNCC-v7.0.2-setup.exe'
$CanonicalFilesLine = 'Source: "..\..\src\windows-v7\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs'
$TreatmentFilesLine = $CanonicalFilesLine + ' notimestamp'
$MtimeA = [DateTime]::Parse('2001-01-01T01:01:02Z').ToUniversalTime()
$MtimeB = [DateTime]::Parse('2025-12-30T23:58:57Z').ToUniversalTime()

function Fail([string]$m) { throw $m }
function Sha([string]$p) { (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant() }

$issueBody = $env:PNCC_ISSUE_BODY
$mainSha = $env:PNCC_MAIN_SHA
$runnerTemp = $env:RUNNER_TEMP
if ([string]::IsNullOrWhiteSpace($issueBody)) { Fail 'ISSUE_BODY_MISSING' }
if ([string]::IsNullOrWhiteSpace($mainSha) -or $mainSha -notmatch '^[0-9a-f]{40}$') { Fail 'MAIN_SHA_INVALID' }
if ([string]::IsNullOrWhiteSpace($runnerTemp)) { Fail 'RUNNER_TEMP_MISSING' }
if ($env:RUNNER_ENVIRONMENT -ne 'github-hosted') { Fail 'GITHUB_HOSTED_RUNNER_REQUIRED' }
$marker = '<!--\s*PNCC-WU204-AB-EXECUTE\s+schema=1\s+expected_main=' + [Regex]::Escape($mainSha) + '\s*-->'
if ([Regex]::Matches($issueBody, $marker).Count -ne 1) { Fail 'EXECUTION_MARKER_INVALID' }
if ([Regex]::Matches($issueBody, 'PNCC-WU204-AB-EXECUTE').Count -ne 1) { Fail 'EXECUTION_MARKER_AMBIGUOUS' }

if ((git rev-parse HEAD).Trim() -ne $mainSha) { Fail 'CHECKOUT_IDENTITY_MISMATCH' }
$issBlob = (git rev-parse ($mainSha + ':' + $IssPath)).Trim()
if ($LASTEXITCODE -ne 0 -or $issBlob -ne $ExpectedIssBlob) { Fail 'INSTALLER_DEFINITION_BLOB_MISMATCH' }
$issFull = (Resolve-Path -LiteralPath $IssPath).Path
$canonicalHashBefore = Sha $issFull
$canonicalBytes = [IO.File]::ReadAllBytes($issFull)
$canonicalText = [IO.File]::ReadAllText($issFull)
if ([Regex]::Matches($canonicalText, [Regex]::Escape($CanonicalFilesLine)).Count -ne 1) { Fail 'CANONICAL_FILES_LINE_IDENTITY_MISMATCH' }
if ($canonicalText -match '(?i)\bnotimestamp\b') { Fail 'CANONICAL_ALREADY_HAS_NOTIMESTAMP' }
if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) { Fail 'SOURCE_TREE_MISSING' }

$setup = Join-Path $runnerTemp $CompilerAsset
$inno = Join-Path $runnerTemp 'pncc-wu204-inno-7.1.0'
$root = Join-Path $runnerTemp 'pncc-wu204-ab'
foreach ($p in @($setup,$inno,$root)) { if (Test-Path -LiteralPath $p) { Fail ('EPHEMERAL_PATH_PREEXISTS:' + $p) } }

function New-Tree([string]$name,[DateTime]$mtime,[bool]$treatment) {
    $r = Join-Path $root $name
    $id = Join-Path $r 'installer\windows'
    $sd = Join-Path $r 'src\windows-v7'
    New-Item -ItemType Directory -Path $id -Force | Out-Null
    New-Item -ItemType Directory -Path $sd -Force | Out-Null
    Copy-Item -Path (Join-Path $SourcePath '*') -Destination $sd -Recurse -Force
    $files = @(Get-ChildItem -LiteralPath $sd -File -Recurse)
    if ($files.Count -lt 1) { Fail ('SOURCE_TREE_EMPTY_' + $name) }
    foreach ($f in $files) { $f.LastWriteTimeUtc = $mtime }
    $files = @(Get-ChildItem -LiteralPath $sd -File -Recurse)
    foreach ($f in $files) { if ($f.LastWriteTimeUtc -ne $mtime) { Fail ('SOURCE_MTIME_SET_FAILED_' + $name) } }
    $ti = Join-Path $id 'VPS-Control-PNCC.iss'
    if ($treatment) {
        $text = $canonicalText.Replace($CanonicalFilesLine,$TreatmentFilesLine)
        if ($text -eq $canonicalText) { Fail ('TREATMENT_MUTATION_MISSING_' + $name) }
        if ([Regex]::Matches($text,'(?i)\bnotimestamp\b').Count -ne 1) { Fail ('TREATMENT_NOTIMESTAMP_COUNT_INVALID_' + $name) }
        if ($text.Replace($TreatmentFilesLine,$CanonicalFilesLine) -ne $canonicalText) { Fail ('TREATMENT_HAS_EXTRA_SEMANTIC_CHANGE_' + $name) }
        [IO.File]::WriteAllText($ti,$text,(New-Object Text.UTF8Encoding($false)))
    } else {
        [IO.File]::WriteAllBytes($ti,$canonicalBytes)
    }
    [ordered]@{ iss=$ti; source_file_count=$files.Count; source_mtime_utc=$mtime.ToString('yyyy-MM-ddTHH:mm:ssZ') }
}

function Build([string]$name,[string]$iss,[string]$iscc) {
    $od = Join-Path $root ('out-' + $name)
    $cp = Join-Path $od $CandidateName
    New-Item -ItemType Directory -Path $od -Force | Out-Null
    try {
        $args = @('/Q',('/O' + $od),('/F' + [IO.Path]::GetFileNameWithoutExtension($CandidateName)),$iss)
        $p = Start-Process -FilePath $iscc -ArgumentList $args -Wait -PassThru
        if ($p.ExitCode -ne 0) { Fail ('ISCC_BUILD_FAILED_' + $name + '_' + $p.ExitCode) }
        if (-not (Test-Path -LiteralPath $cp -PathType Leaf)) { Fail ('CANDIDATE_NOT_FOUND_' + $name) }
        $size = (Get-Item -LiteralPath $cp).Length
        if ($size -le 0) { Fail ('CANDIDATE_EMPTY_' + $name) }
        [ordered]@{ candidate_size_bytes=$size; candidate_sha256=(Sha $cp) }
    } finally {
        if (Test-Path -LiteralPath $cp) { Remove-Item -LiteralPath $cp -Force }
        if (Test-Path -LiteralPath $od) { Remove-Item -LiteralPath $od -Recurse -Force }
    }
}

$compilerSize=$null; $compilerSha=$null; $compilerVersion=$null
$results=[ordered]@{}; $classification='EXPERIMENT_NOT_COMPLETED'; $done=$false
try {
    Invoke-WebRequest -Uri $CompilerUrl -OutFile $setup -UseBasicParsing
    $compilerSize=(Get-Item -LiteralPath $setup).Length; $compilerSha=Sha $setup
    if ($compilerSize -ne $ExpectedCompilerSize) { Fail 'COMPILER_SIZE_MISMATCH' }
    if ($compilerSha -ne $ExpectedCompilerSha256) { Fail 'COMPILER_SHA256_MISMATCH' }
    New-Item -ItemType Directory -Path $inno -Force | Out-Null
    $sp=Start-Process -FilePath $setup -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',('/DIR='+$inno)) -Wait -PassThru
    if ($sp.ExitCode -ne 0) { Fail ('COMPILER_EPHEMERAL_INSTALL_FAILED_'+$sp.ExitCode) }
    $iscc=Join-Path $inno 'ISCC.exe'; if (-not (Test-Path -LiteralPath $iscc -PathType Leaf)) { Fail 'ISCC_NOT_FOUND' }
    $compilerVersion=(Get-Item -LiteralPath $iscc).VersionInfo.FileVersion
    New-Item -ItemType Directory -Path $root -Force | Out-Null

    $specs=@(
      [ordered]@{key='baseline_a';tree=(New-Tree 'baseline-a' $MtimeA $false)},
      [ordered]@{key='baseline_b';tree=(New-Tree 'baseline-b' $MtimeB $false)},
      [ordered]@{key='treatment_a';tree=(New-Tree 'treatment-a' $MtimeA $true)},
      [ordered]@{key='treatment_b';tree=(New-Tree 'treatment-b' $MtimeB $true)}
    )
    if ($specs[0].tree.source_mtime_utc -eq $specs[1].tree.source_mtime_utc) { Fail 'SOURCE_MTIMES_NOT_DISTINCT' }
    foreach ($s in $specs) {
        $b=Build $s.key $s.tree.iss $iscc
        $results[$s.key]=[ordered]@{source_file_count=$s.tree.source_file_count;source_mtime_utc=$s.tree.source_mtime_utc;candidate_size_bytes=$b.candidate_size_bytes;candidate_sha256=$b.candidate_sha256}
    }
    $bi=($results.baseline_a.candidate_size_bytes -eq $results.baseline_b.candidate_size_bytes -and $results.baseline_a.candidate_sha256 -eq $results.baseline_b.candidate_sha256)
    $ti=($results.treatment_a.candidate_size_bytes -eq $results.treatment_b.candidate_size_bytes -and $results.treatment_a.candidate_sha256 -eq $results.treatment_b.candidate_sha256)
    if ((-not $bi) -and $ti) { $classification='NOTIMESTAMP_EXECUTION_PROVEN_CAUSE_AND_REMEDIATION_FOR_CONTROLLED_MTIME_EXPERIMENT' }
    elseif ($bi -and $ti) { $classification='NOTIMESTAMP_TREATMENT_REPRODUCIBLE_BUT_BASELINE_CAUSE_NOT_REPRODUCED' }
    elseif (-not $ti) { $classification='NOTIMESTAMP_REMEDIATION_NOT_PROVEN' }
    else { $classification='CONTROLLED_MTIME_EFFECT_INCONCLUSIVE' }
    $done=$true
} finally {
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
    if (Test-Path -LiteralPath $inno) { Remove-Item -LiteralPath $inno -Recurse -Force }
    if (Test-Path -LiteralPath $setup) { Remove-Item -LiteralPath $setup -Force }
}

if (-not $done) { Fail 'EXPERIMENT_NOT_COMPLETED' }
foreach ($p in @($setup,$inno,$root)) { if (Test-Path -LiteralPath $p) { Fail ('EPHEMERAL_PATH_PERSISTED:' + $p) } }
$canonicalHashAfter=Sha $issFull
if ($canonicalHashAfter -ne $canonicalHashBefore) { Fail 'CANONICAL_INSTALLER_DEFINITION_MUTATED' }
if (@(git status --porcelain).Count -ne 0) { Fail 'CHECKOUT_NOT_CLEAN_AFTER_EXPERIMENT' }
$bi=($results.baseline_a.candidate_size_bytes -eq $results.baseline_b.candidate_size_bytes -and $results.baseline_a.candidate_sha256 -eq $results.baseline_b.candidate_sha256)
$ti=($results.treatment_a.candidate_size_bytes -eq $results.treatment_b.candidate_size_bytes -and $results.treatment_a.candidate_sha256 -eq $results.treatment_b.candidate_sha256)
$receipt=[ordered]@{
 schema_version=1;role='INNO_NOTIMESTAMP_AB_REPRODUCIBILITY_RECEIPT';work_unit_id='PIPE-WU-204';main_sha=$mainSha;runner_class='GITHUB_HOSTED';workspace_class='RUNNER_TEMP_EPHEMERAL_ONLY';
 compiler_repository='jrsoftware/issrc';compiler_tag='is-7_1_0';compiler_release_id=369110765;compiler_asset_id=511336600;compiler_asset_name=$CompilerAsset;compiler_expected_size_bytes=$ExpectedCompilerSize;compiler_observed_size_bytes=$compilerSize;compiler_expected_sha256=$ExpectedCompilerSha256;compiler_observed_sha256=$compilerSha;compiler_identity_verified=$true;compiler_file_version=$compilerVersion;
 installer_definition_path=$IssPath;installer_definition_git_blob_sha=$issBlob;canonical_definition_sha256_before=$canonicalHashBefore;canonical_definition_sha256_after=$canonicalHashAfter;canonical_definition_mutated=$false;treatment_mutation='SINGLE_NOTIMESTAMP_INSERTION_EPHEMERAL_ONLY';source_mtimes_distinct=$true;
 baseline_a=$results.baseline_a;baseline_b=$results.baseline_b;treatment_a=$results.treatment_a;treatment_b=$results.treatment_b;baseline_candidates_identical=$bi;treatment_candidates_identical=$ti;classification=$classification;
 candidates_uploaded=$false;candidates_persisted_after_job=$false;compiler_persisted_after_job=$false;product_runtime_mutated=$false;release_created=$false;tag_created=$false;stable_transition=$false;completed_at=(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
}
Write-Output ('PNCC_WU204_AB_RECEIPT=' + ($receipt | ConvertTo-Json -Compress -Depth 6))
