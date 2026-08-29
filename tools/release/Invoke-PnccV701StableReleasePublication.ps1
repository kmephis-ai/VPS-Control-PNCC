#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$Execute,
    [string]$OutputRoot = 'E:\!Chrome_Downloads'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Repo = 'kmephis-ai/VPS-Control-PNCC'
$AuthorizationMergeMain = 'ddd90993ed182c20a928f9b5692393bab0fe03ff'
$AuthorizationReceiptBlob = 'a8011f0c1d7aafe6257c779b41dd04d3fe5e6346'
$AuthorizedPromotionBlob = 'd574d3ce50758a4c96ace4d32f828e2e14ccd55b'
$PreparationMain = '41e8c9c8bed2cc37423c33750d0748c49ff941b7'
$PreparedPromotionBlob = 'f20891555e6db3a0b5bb57488bac5e8ccf36eb71'
$ArtifactName = 'VPS-Control-v7.0.1.zip'
$ArtifactSha256 = '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'
$ArtifactSize = [int64]701893
$RequestId = 'PNCC-RQ-V7.0.1-D58023321360'
$CandidateId = 'PNCC-V7.0.1-D58023321360'
$SourceSha = 'd5802332136087339482c9b3171c1c5c9c18411e'
$ProviderArtifactId = [int64]9711822972
$ProviderArtifactName = 'PNCC-CANDIDATE-d5802332136087339482c9b3171c1c5c9c18411e'
$ProviderArtifactDigest = 'sha256:47b036f4d328d516e193e0eda5ea480ae08bbabce32235da26692b931154dfd5'
$ProviderBuildRunId = [int64]33242642394
$TargetTag = 'v7.0.1'
$ReleaseName = 'VPS Control PNCC v7.0.1'
$AuthorizationScope = 'RELEASE_TAG_STABLE_PROMOTION_ONLY'

$RunStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$RunId = [guid]::NewGuid().ToString('N')
$EvidenceDir = Join-Path $OutputRoot ('PNCC-WU090-PUBLISH-' + $RunStamp)
$WorkRoot = Join-Path ([IO.Path]::GetTempPath()) ('PNCC-WU090-PUBLISH-WORK-' + $RunId)
$ProviderDir = Join-Path $WorkRoot 'provider'
$VerifyDir = Join-Path $WorkRoot 'release-verify'
$LogPath = Join-Path $EvidenceDir 'PNCC-WU090-PUBLISH.log'
$ResultPath = Join-Path $EvidenceDir 'wu090-publication-result.json'
$ProviderEvidencePath = Join-Path $EvidenceDir 'provider-artifact-readback.json'
$ReleaseEvidencePath = Join-Path $EvidenceDir 'release-readback.json'
$TagEvidencePath = Join-Path $EvidenceDir 'tag-readback.json'
$NotesPath = Join-Path $WorkRoot 'release-notes.md'
$ReturnZip = Join-Path $OutputRoot ('PNCC-WU090-PUBLISH-RETURN-' + $RunStamp + '.zip')

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null
New-Item -ItemType Directory -Path $ProviderDir -Force | Out-Null
New-Item -ItemType Directory -Path $VerifyDir -Force | Out-Null

$script:GhPath = $null
$script:PublicationAttempted = $false
$script:TranscriptStarted = $false
$exitCode = 1

$result = [ordered]@{
    schema_version = 1
    contract_id = 'PNCC_V7_0_1_OWNER_RELEASE_PUBLICATION_RESULT_V1'
    run_id = $RunId
    started_utc = (Get-Date).ToUniversalTime().ToString('o')
    finished_utc = $null
    state = 'INITIALIZING'
    success = $false
    execution_requested = [bool]$Execute
    repository = $Repo
    authorization_merge_main = $AuthorizationMergeMain
    authorization_receipt_blob = $AuthorizationReceiptBlob
    authorized_promotion_blob = $AuthorizedPromotionBlob
    authorized_preparation_main = $PreparationMain
    authorized_prepared_promotion_blob = $PreparedPromotionBlob
    authorization_scope = $AuthorizationScope
    request_id = $RequestId
    candidate_id = $CandidateId
    source_sha = $SourceSha
    artifact_filename = $ArtifactName
    artifact_sha256 = $ArtifactSha256
    artifact_size_bytes = $ArtifactSize
    provider_artifact_id = $ProviderArtifactId
    provider_artifact_name = $ProviderArtifactName
    provider_artifact_digest = $ProviderArtifactDigest
    provider_build_run_id = $ProviderBuildRunId
    target_tag = $TargetTag
    target_release_name = $ReleaseName
    target_tag_commit = $PreparationMain
    current_main_observed = $null
    provider_metadata_verified = $false
    provider_inner_artifact_verified = $false
    publication_attempted = $false
    tag_created_observed = $false
    tag_target_verified = $false
    release_created_observed = $false
    release_name_verified = $false
    release_non_draft_verified = $false
    release_non_prerelease_verified = $false
    release_asset_verified = $false
    release_asset_server_digest = $null
    independent_release_download_sha256 = $null
    independent_release_download_size_bytes = $null
    artifact_rebuilt = $false
    artifact_substituted = $false
    product_bytes_mutated = $false
    runtime_bytes_mutated = $false
    runtime_mutation = $false
    private_runtime_payload_published = $false
    reserve_1080_lifecycle_mutation = $false
    primary_1081_lifecycle_mutation = $false
    cleanup_mode = 'LOCAL_TEMP_ONLY'
    failure_class = $null
    failure_detail = $null
    evidence_directory = $EvidenceDir
    log_path = $LogPath
    return_zip = $ReturnZip
}

function Write-Audit {
    param([Parameter(Mandatory=$true)][string]$Message)
    $line = '{0}  {1}' -f ((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')), $Message
    Write-Host $line
}

function Invoke-GhText {
    param(
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [switch]$AllowFailure
    )
    Write-Audit ('GH :: gh ' + ($Arguments -join ' '))
    $raw = @(& $script:GhPath @Arguments 2>&1)
    $code = $LASTEXITCODE
    $text = ($raw | ForEach-Object { [string]$_ }) -join "`n"
    if ($text) { Write-Host $text }
    if (($code -ne 0) -and (-not $AllowFailure)) {
        throw ('gh failed rc={0}: {1}' -f $code, $text)
    }
    [pscustomobject]@{ ExitCode = $code; Text = $text }
}

function Invoke-GhJson {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)
    $r = Invoke-GhText -Arguments $Arguments
    if ([string]::IsNullOrWhiteSpace($r.Text)) { throw 'gh returned empty JSON' }
    try { return ($r.Text | ConvertFrom-Json) }
    catch { throw ('Invalid JSON from gh: ' + $_.Exception.Message) }
}

function Convert-Base64Utf8 {
    param([Parameter(Mandatory=$true)][string]$Value)
    $compact = $Value -replace '\s',''
    [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($compact))
}

function Get-RepoContentObject {
    param([Parameter(Mandatory=$true)][string]$Path,[Parameter(Mandatory=$true)][string]$Ref)
    $endpoint = 'repos/{0}/contents/{1}?ref={2}' -f $Repo, $Path, $Ref
    $obj = Invoke-GhJson -Arguments @('api',$endpoint)
    if ($obj.type -ne 'file') { throw ('Expected file content for ' + $Path) }
    $text = Convert-Base64Utf8 -Value ([string]$obj.content)
    [pscustomobject]@{ Sha = [string]$obj.sha; Text = $text; Json = ($text | ConvertFrom-Json) }
}

function Get-GitBlobJson {
    param([Parameter(Mandatory=$true)][string]$BlobSha)
    $obj = Invoke-GhJson -Arguments @('api',('repos/{0}/git/blobs/{1}' -f $Repo,$BlobSha))
    if ([string]$obj.sha -ne $BlobSha) { throw ('Git blob SHA mismatch for ' + $BlobSha) }
    $text = Convert-Base64Utf8 -Value ([string]$obj.content)
    return ($text | ConvertFrom-Json)
}

function Assert-TargetNamespaceAbsent {
    $refs = Invoke-GhJson -Arguments @('api',('repos/{0}/git/matching-refs/tags/{1}' -f $Repo,$TargetTag))
    if (@($refs).Count -ne 0) { throw ('Target tag namespace already exists: ' + $TargetTag) }
    Write-Audit ('TAG_NAMESPACE_ABSENT :: ' + $TargetTag)

    $releaseProbe = Invoke-GhText -Arguments @('api',('repos/{0}/releases/tags/{1}' -f $Repo,$TargetTag)) -AllowFailure
    if ($releaseProbe.ExitCode -eq 0) { throw ('Target release already exists: ' + $TargetTag) }
    if ($releaseProbe.Text -notmatch '(?i)(HTTP\s+404|Not Found)') {
        throw ('Release namespace probe failed for a reason other than 404: ' + $releaseProbe.Text)
    }
    Write-Audit ('RELEASE_NAMESPACE_ABSENT :: ' + $TargetTag)
}

function Resolve-TagTarget {
    $tag = Invoke-GhJson -Arguments @('api',('repos/{0}/git/ref/tags/{1}' -f $Repo,$TargetTag))
    $objectType = [string]$tag.object.type
    $objectSha = [string]$tag.object.sha
    if ($objectType -eq 'commit') {
        return [pscustomobject]@{ Ref = [string]$tag.ref; Type = $objectType; TargetSha = $objectSha; ObjectSha = $objectSha }
    }
    if ($objectType -eq 'tag') {
        $annotated = Invoke-GhJson -Arguments @('api',('repos/{0}/git/tags/{1}' -f $Repo,$objectSha))
        if ([string]$annotated.object.type -ne 'commit') { throw 'Annotated tag does not resolve directly to a commit' }
        return [pscustomobject]@{ Ref = [string]$tag.ref; Type = $objectType; TargetSha = [string]$annotated.object.sha; ObjectSha = $objectSha }
    }
    throw ('Unsupported tag object type: ' + $objectType)
}

function Get-ReleaseReadback {
    return (Invoke-GhJson -Arguments @('api',('repos/{0}/releases/tags/{1}' -f $Repo,$TargetTag)))
}

function Get-MatchingReleaseAsset {
    param([Parameter(Mandatory=$true)]$Release)
    $matches = @($Release.assets | Where-Object { [string]$_.name -eq $ArtifactName })
    if ($matches.Count -ne 1) { throw ('Expected exactly one release asset named ' + $ArtifactName + '; count=' + $matches.Count) }
    return $matches[0]
}

function Save-Json {
    param([Parameter(Mandatory=$true)]$Object,[Parameter(Mandatory=$true)][string]$Path)
    $Object | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Path -Encoding UTF8
}

try {
    Start-Transcript -LiteralPath $LogPath -Force | Out-Null
    $script:TranscriptStarted = $true
    Write-Audit 'PNCC WU-090 v7.0.1 Owner Release Publication executor start'
    Write-Audit ('MODE :: ' + $(if ($Execute) { 'EXECUTE' } else { 'PLAN_ONLY' }))

    $gh = Get-Command gh -ErrorAction Stop
    $script:GhPath = $gh.Source
    Write-Audit ('GH_PATH :: ' + $script:GhPath)
    $null = Invoke-GhText -Arguments @('--version')
    $null = Invoke-GhText -Arguments @('auth','status','--hostname','github.com')

    $branch = Invoke-GhJson -Arguments @('api',('repos/{0}/branches/main' -f $Repo))
    $currentMain = [string]$branch.commit.sha
    $result.current_main_observed = $currentMain
    if ($currentMain.Length -ne 40) { throw 'Invalid current main SHA' }
    Write-Audit ('CURRENT_MAIN :: ' + $currentMain)

    $authFile = Get-RepoContentObject -Path '.pncc-dev/attestations/stable-release-tag-owner-authorization-v7.0.1.json' -Ref 'main'
    if ($authFile.Sha -ne $AuthorizationReceiptBlob) { throw ('Authorization receipt blob drift: ' + $authFile.Sha) }
    $auth = $authFile.Json
    if ([string]$auth.contract_id -ne 'PNCC_STABLE_RELEASE_TAG_OWNER_AUTHORIZATION_V1') { throw 'Authorization contract mismatch' }
    if ([string]$auth.authorized_preparation_main -ne $PreparationMain) { throw 'Authorization preparation main mismatch' }
    if ([string]$auth.authorized_prepared_promotion_contract_blob_sha -ne $PreparedPromotionBlob) { throw 'Authorization prepared blob mismatch' }
    if ([string]$auth.owner_release_authorization_scope -ne $AuthorizationScope) { throw 'Authorization scope mismatch' }
    if ($auth.owner_release_authorization_present -ne $true -or $auth.owner_release_authorization_binding_complete -ne $true) { throw 'Authorization binding incomplete' }
    foreach ($key in @('promotion_eligibility_authorized','tag_creation_authorized','release_creation_authorized','release_asset_upload_authorized','release_asset_server_digest_verification_required','stable_declaration_authorized','overwrite_existing_tag_forbidden','move_existing_tag_forbidden','overwrite_existing_release_forbidden')) {
        if ($auth.$key -ne $true) { throw ('Authorization required true missing: ' + $key) }
    }
    foreach ($key in @('artifact_rebuild_authorized','artifact_substitution_authorized','product_bytes_mutation_authorized','runtime_bytes_mutation_authorized','private_runtime_payload_publication_authorized','reserve_1080_lifecycle_mutation_authorized','primary_1081_lifecycle_mutation_authorized')) {
        if ($auth.$key -ne $false) { throw ('Forbidden authority unexpectedly true: ' + $key) }
    }
    foreach ($pair in @(
        @('stable_artifact_filename',$ArtifactName),
        @('stable_artifact_sha256',$ArtifactSha256),
        @('stable_artifact_size_bytes',$ArtifactSize),
        @('request_id',$RequestId),
        @('candidate_id',$CandidateId),
        @('source_sha',$SourceSha),
        @('target_tag',$TargetTag),
        @('target_release_name',$ReleaseName),
        @('target_tag_commit',$PreparationMain),
        @('provider_artifact_id',$ProviderArtifactId),
        @('provider_artifact_digest',$ProviderArtifactDigest),
        @('provider_build_run_id',$ProviderBuildRunId)
    )) {
        $key = [string]$pair[0]
        $expected = $pair[1]
        if ([string]$auth.$key -ne [string]$expected) { throw ('Authorization identity mismatch: ' + $key) }
    }
    Write-Audit 'OWNER_RELEASE_AUTHORIZATION=PASS'

    $promotionFile = Get-RepoContentObject -Path '.pncc-dev/attestations/stable-release-tag-promotion-v7.0.1.json' -Ref 'main'
    if ($promotionFile.Sha -ne $AuthorizedPromotionBlob) { throw ('Authorized promotion blob drift: ' + $promotionFile.Sha) }
    $promotion = $promotionFile.Json
    if ([string]$promotion.promotion_state -ne 'AUTHORIZED_PENDING_EXECUTION') { throw 'Promotion state is not AUTHORIZED_PENDING_EXECUTION' }
    if ($promotion.runtime_authority -ne $true -or $promotion.promotion_eligible -ne $true -or $promotion.release_or_tag_authorized -ne $true) { throw 'Promotion authority flags incomplete' }
    if ($promotion.tag_created -ne $false -or $promotion.release_created -ne $false -or $promotion.release_asset_verified -ne $false -or $promotion.stable_declared -ne $false) { throw 'Repository claims publication before provider execution' }
    if ([string]$promotion.target_tag_commit -ne $PreparationMain) { throw 'Promotion target commit mismatch' }
    Write-Audit 'AUTHORIZED_PENDING_EXECUTION=PASS'

    $prepared = Get-GitBlobJson -BlobSha $PreparedPromotionBlob
    if ([string]$prepared.contract_id -ne 'PNCC_STABLE_RELEASE_TAG_PROMOTION_V2') { throw 'Prepared blob contract mismatch' }
    if ([string]$prepared.promotion_state -ne 'WAITING_OWNER_RELEASE_AUTHORIZATION') { throw 'Prepared blob was not default-deny waiting state' }
    if ($prepared.owner_release_authorization_present -ne $false -or $prepared.promotion_eligible -ne $false -or $prepared.release_or_tag_authorized -ne $false) { throw 'Prepared blob default-deny semantics mismatch' }
    Write-Audit 'PREPARED_PROMOTION_BLOB=PASS'

    $authCommit = Invoke-GhJson -Arguments @('api',('repos/{0}/commits/{1}' -f $Repo,$AuthorizationMergeMain))
    if ([string]$authCommit.sha -ne $AuthorizationMergeMain) { throw 'Authorization merge commit is unavailable' }

    Assert-TargetNamespaceAbsent

    $providerMeta = Invoke-GhJson -Arguments @('api',('repos/{0}/actions/artifacts/{1}' -f $Repo,$ProviderArtifactId))
    if ([int64]$providerMeta.id -ne $ProviderArtifactId) { throw 'Provider artifact id mismatch' }
    if ([string]$providerMeta.name -ne $ProviderArtifactName) { throw 'Provider artifact name mismatch' }
    if ([string]$providerMeta.digest -ne $ProviderArtifactDigest) { throw 'Provider artifact digest mismatch' }
    if ($providerMeta.expired -ne $false) { throw 'Provider artifact is expired' }
    if ([int64]$providerMeta.workflow_run.id -ne $ProviderBuildRunId) { throw 'Provider build run mismatch' }
    if ([string]$providerMeta.workflow_run.head_sha -ne $SourceSha) { throw 'Provider source SHA mismatch' }

    $runArtifacts = Invoke-GhJson -Arguments @('api',('repos/{0}/actions/runs/{1}/artifacts?per_page=100' -f $Repo,$ProviderBuildRunId))
    $exactProvider = @($runArtifacts.artifacts | Where-Object { [int64]$_.id -eq $ProviderArtifactId -and [string]$_.name -eq $ProviderArtifactName })
    if ($exactProvider.Count -ne 1) { throw ('Exact provider artifact not unique in build run; count=' + $exactProvider.Count) }
    if ([string]$exactProvider[0].digest -ne $ProviderArtifactDigest) { throw 'Provider run artifact digest mismatch' }

    $providerEvidence = [ordered]@{
        id = [int64]$providerMeta.id
        name = [string]$providerMeta.name
        digest = [string]$providerMeta.digest
        expired = [bool]$providerMeta.expired
        provider_build_run_id = [int64]$providerMeta.workflow_run.id
        source_sha = [string]$providerMeta.workflow_run.head_sha
    }
    Save-Json -Object $providerEvidence -Path $ProviderEvidencePath
    $result.provider_metadata_verified = $true
    Write-Audit 'PROVIDER_METADATA_VERIFIED=PASS'

    if (-not $Execute) {
        $result.state = 'PLAN_PASS'
        $result.success = $true
        $exitCode = 0
        Write-Audit 'PNCC_WU090_PUBLICATION=PLAN_PASS :: no provider mutation executed'
    }
    else {
        $download = Invoke-GhText -Arguments @('run','download',[string]$ProviderBuildRunId,'--repo',$Repo,'--name',$ProviderArtifactName,'--dir',$ProviderDir)
        $candidateFiles = @(Get-ChildItem -LiteralPath $ProviderDir -Recurse -File -Filter $ArtifactName -ErrorAction Stop)
        if ($candidateFiles.Count -ne 1) { throw ('Expected exactly one inner candidate; count=' + $candidateFiles.Count) }
        $candidate = $candidateFiles[0]
        if ([int64]$candidate.Length -ne $ArtifactSize) { throw ('Inner artifact size mismatch: ' + $candidate.Length) }
        $candidateHash = (Get-FileHash -LiteralPath $candidate.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($candidateHash -ne $ArtifactSha256) { throw ('Inner artifact SHA256 mismatch: ' + $candidateHash) }
        $result.provider_inner_artifact_verified = $true
        Write-Audit ('PROVIDER_INNER_ARTIFACT_VERIFIED=PASS :: sha256=' + $candidateHash + '; size=' + $candidate.Length)

        @(
            '# VPS Control PNCC v7.0.1',
            '',
            'Stable patch release using the exact governed and physically qualified artifact.',
            '',
            '- Candidate: `PNCC-V7.0.1-D58023321360`',
            '- Request: `PNCC-RQ-V7.0.1-D58023321360`',
            '- Artifact: `VPS-Control-v7.0.1.zip`',
            '- SHA-256: `22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72`',
            '- Size: `701893` bytes',
            '- Physical startup acceptance: PASS',
            '- Fresh nine-scope Runtime Qualification: 9/9 PASS',
            '- Repository Runtime Authority: Owner-granted',
            '',
            'Safety invariants remain unchanged: 1080 is RESERVE_MANUAL/MANUAL_ONLY; 1081 is PRIMARY_AUTO; V6.3.1 rollback remains immutable; no artifact rebuild or substitution was used for this release.'
        ) | Set-Content -LiteralPath $NotesPath -Encoding UTF8

        Assert-TargetNamespaceAbsent
        $script:PublicationAttempted = $true
        $result.publication_attempted = $true
        Write-Audit ('PUBLICATION_BEGIN :: tag=' + $TargetTag + '; target=' + $PreparationMain)
        $null = Invoke-GhText -Arguments @('release','create',$TargetTag,$candidate.FullName,'--repo',$Repo,'--target',$PreparationMain,'--title',$ReleaseName,'--notes-file',$NotesPath)
        Write-Audit 'GH_RELEASE_CREATE_RETURNED_SUCCESS'

        $tagResolved = Resolve-TagTarget
        $tagEvidence = [ordered]@{
            ref = $tagResolved.Ref
            object_type = $tagResolved.Type
            object_sha = $tagResolved.ObjectSha
            resolved_target_commit = $tagResolved.TargetSha
        }
        Save-Json -Object $tagEvidence -Path $TagEvidencePath
        $result.tag_created_observed = $true
        if ($tagResolved.TargetSha -ne $PreparationMain) { throw ('Tag target mismatch: ' + $tagResolved.TargetSha) }
        $result.tag_target_verified = $true
        Write-Audit ('TAG_TARGET_VERIFIED=PASS :: ' + $tagResolved.TargetSha)

        $release = Get-ReleaseReadback
        $result.release_created_observed = $true
        if ([string]$release.tag_name -ne $TargetTag) { throw 'Release tag_name mismatch' }
        if ([string]$release.name -ne $ReleaseName) { throw ('Release name mismatch: ' + [string]$release.name) }
        $result.release_name_verified = $true
        if ($release.draft -ne $false) { throw 'Release is draft' }
        $result.release_non_draft_verified = $true
        if ($release.prerelease -ne $false) { throw 'Release is prerelease' }
        $result.release_non_prerelease_verified = $true
        if ([string]$release.target_commitish -ne $PreparationMain) { throw ('Release target_commitish mismatch: ' + [string]$release.target_commitish) }

        $asset = $null
        for ($attempt = 1; $attempt -le 12; $attempt++) {
            $release = Get-ReleaseReadback
            $asset = Get-MatchingReleaseAsset -Release $release
            $serverDigest = [string]$asset.digest
            Write-Audit ('ASSET_DIGEST_POLL :: attempt=' + $attempt + '; digest=' + $serverDigest)
            if ($serverDigest -eq ('sha256:' + $ArtifactSha256)) { break }
            if ($attempt -lt 12) { Start-Sleep -Seconds 5 }
        }
        if ([int64]$asset.size -ne $ArtifactSize) { throw ('Release asset size mismatch: ' + [string]$asset.size) }
        if ([string]$asset.digest -ne ('sha256:' + $ArtifactSha256)) { throw ('Release asset server digest mismatch/unavailable: ' + [string]$asset.digest) }
        $result.release_asset_server_digest = [string]$asset.digest

        $releaseEvidence = [ordered]@{
            id = [int64]$release.id
            html_url = [string]$release.html_url
            tag_name = [string]$release.tag_name
            name = [string]$release.name
            draft = [bool]$release.draft
            prerelease = [bool]$release.prerelease
            target_commitish = [string]$release.target_commitish
            asset = [ordered]@{
                id = [int64]$asset.id
                name = [string]$asset.name
                size = [int64]$asset.size
                digest = [string]$asset.digest
                state = [string]$asset.state
            }
        }
        Save-Json -Object $releaseEvidence -Path $ReleaseEvidencePath

        $null = Invoke-GhText -Arguments @('release','download',$TargetTag,'--repo',$Repo,'--pattern',$ArtifactName,'--dir',$VerifyDir)
        $downloaded = @(Get-ChildItem -LiteralPath $VerifyDir -File -Filter $ArtifactName -ErrorAction Stop)
        if ($downloaded.Count -ne 1) { throw ('Independent release download count mismatch: ' + $downloaded.Count) }
        $verifiedFile = $downloaded[0]
        $verifiedHash = (Get-FileHash -LiteralPath $verifiedFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $verifiedSize = [int64]$verifiedFile.Length
        $result.independent_release_download_sha256 = $verifiedHash
        $result.independent_release_download_size_bytes = $verifiedSize
        if ($verifiedHash -ne $ArtifactSha256) { throw ('Independent release download SHA256 mismatch: ' + $verifiedHash) }
        if ($verifiedSize -ne $ArtifactSize) { throw ('Independent release download size mismatch: ' + $verifiedSize) }
        $result.release_asset_verified = $true
        Write-Audit ('RELEASE_ASSET_VERIFIED=PASS :: sha256=' + $verifiedHash + '; size=' + $verifiedSize)

        $result.state = 'PASS'
        $result.success = $true
        $exitCode = 0
        Write-Audit 'PNCC_WU090_PUBLICATION=PASS'
    }
}
catch {
    $message = $_.Exception.Message
    $result.failure_detail = $message
    $result.publication_attempted = [bool]$script:PublicationAttempted
    if ($script:PublicationAttempted) {
        $result.state = 'PARTIAL_PUBLICATION_REQUIRES_RECONCILIATION'
        $result.failure_class = 'POST_MUTATION_VERIFICATION_OR_PROVIDER_FAILURE'
        Write-Audit ('FAIL :: PARTIAL_PUBLICATION_REQUIRES_RECONCILIATION :: ' + $message)
        try {
            $tagProbe = Invoke-GhText -Arguments @('api',('repos/{0}/git/ref/tags/{1}' -f $Repo,$TargetTag)) -AllowFailure
            if ($tagProbe.ExitCode -eq 0) { $result.tag_created_observed = $true }
        } catch {}
        try {
            $releaseProbe = Invoke-GhText -Arguments @('api',('repos/{0}/releases/tags/{1}' -f $Repo,$TargetTag)) -AllowFailure
            if ($releaseProbe.ExitCode -eq 0) { $result.release_created_observed = $true }
        } catch {}
        $exitCode = 3
    }
    else {
        $result.state = 'FAIL_PRECONDITION'
        $result.failure_class = 'PRE_MUTATION_VALIDATION_FAILURE'
        Write-Audit ('FAIL :: PRE_MUTATION_VALIDATION_FAILURE :: ' + $message)
        $exitCode = 2
    }
}
finally {
    $result.finished_utc = (Get-Date).ToUniversalTime().ToString('o')
    try { Save-Json -Object $result -Path $ResultPath } catch { Write-Host ('RESULT_WRITE_FAILED=' + $_.Exception.Message) }
    if ($script:TranscriptStarted) {
        try { Stop-Transcript | Out-Null } catch {}
        $script:TranscriptStarted = $false
    }
    try {
        if (Test-Path -LiteralPath $WorkRoot) { Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction Stop }
    } catch {
        Write-Host ('LOCAL_TEMP_CLEANUP_WARNING=' + $_.Exception.Message)
    }
}

try {
    if (Test-Path -LiteralPath $ReturnZip) { throw ('Return ZIP already exists: ' + $ReturnZip) }
    Compress-Archive -Path (Join-Path $EvidenceDir '*') -DestinationPath $ReturnZip -CompressionLevel Optimal
    $returnHash = (Get-FileHash -LiteralPath $ReturnZip -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host ('EVIDENCE_DIR=' + $EvidenceDir)
    Write-Host ('LOG_PATH=' + $LogPath)
    Write-Host ('RESULT_PATH=' + $ResultPath)
    Write-Host ('RETURN_ZIP=' + $ReturnZip)
    Write-Host ('RETURN_ZIP_SHA256=' + $returnHash)
}
catch {
    Write-Host ('RETURN_ZIP_FAILURE=' + $_.Exception.Message)
    if ($exitCode -eq 0) { $exitCode = 4 }
}

Write-Host ('EXIT_CODE=' + $exitCode)
exit $exitCode
