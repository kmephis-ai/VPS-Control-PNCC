Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Describe 'WU-090 v7.0.1 owner release publication executor' {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
        $runnerPath = Join-Path $repoRoot 'tools\release\Invoke-PnccV701StableReleasePublication.ps1'
        $runnerRaw = Get-Content -LiteralPath $runnerPath -Raw
        $tokens = $null
        $errors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($runnerPath, [ref]$tokens, [ref]$errors)
        $script:Wu090RunnerPath = $runnerPath
        $script:Wu090RunnerRaw = $runnerRaw
        $script:Wu090AstErrors = @($errors)
    }

    It 'is Windows PowerShell 5.1 parse-safe' {
        $script:Wu090AstErrors.Count | Should -Be 0
        $script:Wu090RunnerRaw | Should -Match '#requires -Version 5\.1'
    }

    It 'pins the exact Owner-authorized publication identity' {
        $script:Wu090RunnerRaw | Should -Match [regex]::Escape("`$AuthorizationMergeMain = 'ddd90993ed182c20a928f9b5692393bab0fe03ff'")
        $script:Wu090RunnerRaw | Should -Match [regex]::Escape("`$PreparationMain = '41e8c9c8bed2cc37423c33750d0748c49ff941b7'")
        $script:Wu090RunnerRaw | Should -Match [regex]::Escape("`$PreparedPromotionBlob = 'f20891555e6db3a0b5bb57488bac5e8ccf36eb71'")
        $script:Wu090RunnerRaw | Should -Match [regex]::Escape("`$AuthorizationReceiptBlob = 'a8011f0c1d7aafe6257c779b41dd04d3fe5e6346'")
        $script:Wu090RunnerRaw | Should -Match [regex]::Escape("`$AuthorizedPromotionBlob = 'd574d3ce50758a4c96ace4d32f828e2e14ccd55b'")
        $script:Wu090RunnerRaw | Should -Match 'RELEASE_TAG_STABLE_PROMOTION_ONLY'
    }

    It 'pins exact candidate and provider artifact bytes' {
        $script:Wu090RunnerRaw | Should -Match 'VPS-Control-v7\.0\.1\.zip'
        $script:Wu090RunnerRaw | Should -Match '22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72'
        $script:Wu090RunnerRaw | Should -Match '701893'
        $script:Wu090RunnerRaw | Should -Match '9711822972'
        $script:Wu090RunnerRaw | Should -Match '33242642394'
        $script:Wu090RunnerRaw | Should -Match 'sha256:47b036f4d328d516e193e0eda5ea480ae08bbabce32235da26692b931154dfd5'
        $script:Wu090RunnerRaw | Should -Match 'd5802332136087339482c9b3171c1c5c9c18411e'
    }

    It 'targets only v7.0.1 at the exact preparation merge commit' {
        $script:Wu090RunnerRaw | Should -Match [regex]::Escape("`$TargetTag = 'v7.0.1'")
        $script:Wu090RunnerRaw | Should -Match [regex]::Escape("`$ReleaseName = 'VPS Control PNCC v7.0.1'")
        $script:Wu090RunnerRaw | Should -Match "'--target',`$PreparationMain"
        $script:Wu090RunnerRaw | Should -Match [regex]::Escape("`$PreparedPromotionBlob = 'f20891555e6db3a0b5bb57488bac5e8ccf36eb71'")
    }

    It 'requires explicit Execute mode and defaults non-mutating' {
        $script:Wu090RunnerRaw | Should -Match '\[switch\]\$Execute'
        $script:Wu090RunnerRaw | Should -Match "if \(-not `\$Execute\)"
        $script:Wu090RunnerRaw | Should -Match "state = 'PLAN_PASS'"
    }

    It 'uses provider artifact download rather than rebuilding candidate bytes' {
        $script:Wu090RunnerRaw | Should -Match "'run','download'"
        $script:Wu090RunnerRaw | Should -Match "'--name',`$ProviderArtifactName"
        $script:Wu090RunnerRaw | Should -Match 'Get-FileHash'
        $script:Wu090RunnerRaw | Should -Not -Match '(?im)^\s*(dotnet|msbuild|npm|pnpm|yarn|cargo|go)\s+(build|pack|publish)\b'
    }

    It 'checks namespace before mutation and never overwrites release state' {
        $script:Wu090RunnerRaw | Should -Match 'Assert-TargetNamespaceAbsent'
        $script:Wu090RunnerRaw | Should -Match 'matching-refs/tags'
        $script:Wu090RunnerRaw | Should -Match 'releases/tags'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)--clobber'
        $script:Wu090RunnerRaw | Should -Not -Match "(?i)'release','delete'"
        $script:Wu090RunnerRaw | Should -Not -Match "(?i)'release','delete-asset'"
        $script:Wu090RunnerRaw | Should -Not -Match "(?i)'api'.*DELETE"
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)git\s+tag\s+-f'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)git\s+push.*--force'
    }

    It 'publishes through exact gh release create and verifies server digest' {
        $script:Wu090RunnerRaw | Should -Match "'release','create',`$TargetTag"
        $script:Wu090RunnerRaw | Should -Match "'--title',`$ReleaseName"
        $script:Wu090RunnerRaw | Should -Match "'--notes-file',`$NotesPath"
        $script:Wu090RunnerRaw | Should -Match "'sha256:' \+ `\$ArtifactSha256"
        $script:Wu090RunnerRaw | Should -Match "'release','download',`$TargetTag"
    }

    It 'never performs tunnel lifecycle mutation' {
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)RestartTunnel'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)Stop-Process'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)taskkill'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)TerminateProcess'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)-Action\s+Watchdog'
        $script:Wu090RunnerRaw | Should -Match 'reserve_1080_lifecycle_mutation = \$false'
        $script:Wu090RunnerRaw | Should -Match 'primary_1081_lifecycle_mutation = \$false'
    }

    It 'never retrieves or logs an authentication token' {
        $script:Wu090RunnerRaw | Should -Not -Match "(?i)gh\s+auth\s+token"
        $script:Wu090RunnerRaw | Should -Not -Match "(?i)'auth','token'"
        $script:Wu090RunnerRaw | Should -Match "'auth','status'"
    }

    It 'fails into reconciliation after any attempted publication' {
        $script:Wu090RunnerRaw | Should -Match 'PARTIAL_PUBLICATION_REQUIRES_RECONCILIATION'
        $script:Wu090RunnerRaw | Should -Match 'POST_MUTATION_VERIFICATION_OR_PROVIDER_FAILURE'
        $script:Wu090RunnerRaw | Should -Match 'PRE_MUTATION_VALIDATION_FAILURE'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)automatic.*rollback'
    }

    It 'always emits persistent evidence and a return ZIP' {
        $script:Wu090RunnerRaw | Should -Match 'Start-Transcript'
        $script:Wu090RunnerRaw | Should -Match 'wu090-publication-result\.json'
        $script:Wu090RunnerRaw | Should -Match 'provider-artifact-readback\.json'
        $script:Wu090RunnerRaw | Should -Match 'release-readback\.json'
        $script:Wu090RunnerRaw | Should -Match 'tag-readback\.json'
        $script:Wu090RunnerRaw | Should -Match 'PNCC-WU090-PUBLISH-RETURN-'
        $script:Wu090RunnerRaw | Should -Match 'RETURN_ZIP_SHA256='
    }
}
