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
        $script:Wu090RunnerRaw.Contains('#requires -Version 5.1') | Should -BeTrue
    }

    It 'pins the exact Owner-authorized publication identity' {
        $script:Wu090RunnerRaw.Contains('$AuthorizationMergeMain = ''ddd90993ed182c20a928f9b5692393bab0fe03ff''') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$PreparationMain = ''41e8c9c8bed2cc37423c33750d0748c49ff941b7''') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$PreparedPromotionBlob = ''f20891555e6db3a0b5bb57488bac5e8ccf36eb71''') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$AuthorizationReceiptBlob = ''a8011f0c1d7aafe6257c779b41dd04d3fe5e6346''') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$AuthorizedPromotionBlob = ''d574d3ce50758a4c96ace4d32f828e2e14ccd55b''') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$AuthorizationScope = ''RELEASE_TAG_STABLE_PROMOTION_ONLY''') | Should -BeTrue
    }

    It 'pins exact candidate and provider artifact bytes' {
        $script:Wu090RunnerRaw.Contains('$ArtifactName = ''VPS-Control-v7.0.1.zip''') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$ArtifactSha256 = ''22b843330516e481c467fe5cbe6d1d4c6758510c71bd2c46ebeec337f403ae72''') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$ArtifactSize = [int64]701893') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$ProviderArtifactId = [int64]9711822972') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$ProviderBuildRunId = [int64]33242642394') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$ProviderArtifactDigest = ''sha256:47b036f4d328d516e193e0eda5ea480ae08bbabce32235da26692b931154dfd5''') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$SourceSha = ''d5802332136087339482c9b3171c1c5c9c18411e''') | Should -BeTrue
    }

    It 'targets only v7.0.1 at the exact preparation merge commit' {
        $script:Wu090RunnerRaw.Contains('$TargetTag = ''v7.0.1''') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$ReleaseName = ''VPS Control PNCC v7.0.1''') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('''--target'',$PreparationMain') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$PreparedPromotionBlob = ''f20891555e6db3a0b5bb57488bac5e8ccf36eb71''') | Should -BeTrue
    }

    It 'requires explicit Execute mode and defaults non-mutating' {
        $script:Wu090RunnerRaw.Contains('[switch]$Execute') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('if (-not $Execute)') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('$result.state = ''PLAN_PASS''') | Should -BeTrue
    }

    It 'uses provider artifact download rather than rebuilding candidate bytes' {
        $script:Wu090RunnerRaw.Contains('''run'',''download'',[string]$ProviderBuildRunId') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('''--name'',$ProviderArtifactName') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('Get-FileHash') | Should -BeTrue
        $script:Wu090RunnerRaw | Should -Not -Match '(?im)^\s*(dotnet|msbuild|npm|pnpm|yarn|cargo|go)\s+(build|pack|publish)\b'
    }

    It 'checks namespace before mutation and never overwrites release state' {
        $script:Wu090RunnerRaw.Contains('Assert-TargetNamespaceAbsent') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('matching-refs/tags') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('releases/tags') | Should -BeTrue
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)--clobber'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)''release'',''delete'''
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)''release'',''delete-asset'''
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)''api''.*DELETE'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)git\s+tag\s+-f'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)git\s+push.*--force'
    }

    It 'publishes through exact gh release create and verifies server digest' {
        $script:Wu090RunnerRaw.Contains('''release'',''create'',$TargetTag') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('''--title'',$ReleaseName') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('''--notes-file'',$NotesPath') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('(''sha256:'' + $ArtifactSha256)') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('''release'',''download'',$TargetTag') | Should -BeTrue
    }

    It 'never performs tunnel lifecycle mutation' {
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)RestartTunnel'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)Stop-Process'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)taskkill'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)TerminateProcess'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)-Action\s+Watchdog'
        $script:Wu090RunnerRaw.Contains('reserve_1080_lifecycle_mutation = $false') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('primary_1081_lifecycle_mutation = $false') | Should -BeTrue
    }

    It 'never retrieves or logs an authentication token' {
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)gh\s+auth\s+token'
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)''auth'',''token'''
        $script:Wu090RunnerRaw.Contains('''auth'',''status''') | Should -BeTrue
    }

    It 'fails into reconciliation after any attempted publication' {
        $script:Wu090RunnerRaw.Contains('PARTIAL_PUBLICATION_REQUIRES_RECONCILIATION') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('POST_MUTATION_VERIFICATION_OR_PROVIDER_FAILURE') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('PRE_MUTATION_VALIDATION_FAILURE') | Should -BeTrue
        $script:Wu090RunnerRaw | Should -Not -Match '(?i)automatic.*rollback'
    }

    It 'always emits persistent evidence and a return ZIP' {
        $script:Wu090RunnerRaw.Contains('Start-Transcript') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('wu090-publication-result.json') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('provider-artifact-readback.json') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('release-readback.json') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('tag-readback.json') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('PNCC-WU090-PUBLISH-RETURN-') | Should -BeTrue
        $script:Wu090RunnerRaw.Contains('RETURN_ZIP_SHA256=') | Should -BeTrue
    }
}
