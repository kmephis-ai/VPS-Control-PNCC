Set-StrictMode -Version 3.0

BeforeAll {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $modulePath = Join-Path $repoRoot '.pncc-dev\quality\PNCC.SanitizedFixtureProvenance.psm1'
    Import-Module $modulePath -Force -ErrorAction Stop

    function Write-DeepTestFile {
        param(
            [Parameter(Mandatory=$true)][string]$Path,
            [Parameter(Mandatory=$true)][string]$Content
        )
        $parent = Split-Path -Parent $Path
        if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
            [void](New-Item -ItemType Directory -Path $parent -Force)
        }
        [IO.File]::WriteAllText($Path, $Content, (New-Object Text.UTF8Encoding($false)))
    }

    function Get-DeepTestHash {
        param([Parameter(Mandatory=$true)][string]$Path)
        return ((Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
    }

    function Write-DeepManifest {
        param(
            [Parameter(Mandatory=$true)][string]$Path,
            [Parameter(Mandatory=$true)][string[]]$Lines
        )
        [IO.File]::WriteAllText($Path, (($Lines -join "`n") + "`n"), (New-Object Text.UTF8Encoding($false)))
    }

    function Initialize-DeepGitRepo {
        param([Parameter(Mandatory=$true)][string]$Path)
        & git -C $Path init | Out-Null
        & git -C $Path config core.autocrlf false
        & git -C $Path config user.email 'pncc-ci@example.invalid'
        & git -C $Path config user.name 'PNCC CI'
    }
}

Describe 'PNCC DEEP sanitized fixture SHA-256 inventory verifier' {
    It 'passes a complete valid recursive inventory' {
        $root = Join-Path $TestDrive 'valid'
        [void](New-Item -ItemType Directory -Path $root -Force)
        $a = Join-Path $root 'a.txt'
        $b = Join-Path $root 'nested\b.txt'
        Write-DeepTestFile -Path $a -Content 'alpha'
        Write-DeepTestFile -Path $b -Content 'beta'
        $manifest = Join-Path $root 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @(
            "$(Get-DeepTestHash $a)  a.txt",
            "$(Get-DeepTestHash $b)  nested/b.txt"
        )

        $result = Test-PnccSha256Inventory -FixtureRoot $root -ManifestPath $manifest
        $result.Status | Should -Be 'PASS'
        $result.EntryCount | Should -Be 2
        $result.ActualFileCount | Should -Be 2
        $result.VerifiedCount | Should -Be 2
        @($result.Errors).Count | Should -Be 0
    }

    It 'fails closed on a hash mismatch' {
        $root = Join-Path $TestDrive 'hash-mismatch'
        [void](New-Item -ItemType Directory -Path $root -Force)
        $a = Join-Path $root 'a.txt'
        Write-DeepTestFile -Path $a -Content 'alpha'
        $manifest = Join-Path $root 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @((('0' * 64) + '  a.txt'))

        $result = Test-PnccSha256Inventory -FixtureRoot $root -ManifestPath $manifest
        $result.Status | Should -Be 'FAIL'
        @($result.Errors) -join '|' | Should -Match 'HASH_MISMATCH:a.txt'
    }

    It 'fails closed when a listed file is missing' {
        $root = Join-Path $TestDrive 'missing'
        [void](New-Item -ItemType Directory -Path $root -Force)
        $manifest = Join-Path $root 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @((('0' * 64) + '  missing.txt'))

        $result = Test-PnccSha256Inventory -FixtureRoot $root -ManifestPath $manifest
        $result.Status | Should -Be 'FAIL'
        @($result.Errors) -join '|' | Should -Match 'MISSING_FILE:missing.txt'
    }

    It 'fails closed on an unlisted extra file' {
        $root = Join-Path $TestDrive 'extra'
        [void](New-Item -ItemType Directory -Path $root -Force)
        $a = Join-Path $root 'a.txt'
        $extra = Join-Path $root 'extra.txt'
        Write-DeepTestFile -Path $a -Content 'alpha'
        Write-DeepTestFile -Path $extra -Content 'extra'
        $manifest = Join-Path $root 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @("$(Get-DeepTestHash $a)  a.txt")

        $result = Test-PnccSha256Inventory -FixtureRoot $root -ManifestPath $manifest
        $result.Status | Should -Be 'FAIL'
        @($result.Errors) -join '|' | Should -Match 'UNLISTED_FILE:extra.txt'
    }

    It 'fails closed on a malformed manifest line' {
        $root = Join-Path $TestDrive 'malformed'
        [void](New-Item -ItemType Directory -Path $root -Force)
        $manifest = Join-Path $root 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @('not-a-sha256-manifest-line')

        $result = Test-PnccSha256Inventory -FixtureRoot $root -ManifestPath $manifest
        $result.Status | Should -Be 'FAIL'
        @($result.Errors) -join '|' | Should -Match 'MALFORMED_LINE:1'
    }

    It 'fails closed on duplicate manifest paths' {
        $root = Join-Path $TestDrive 'duplicate'
        [void](New-Item -ItemType Directory -Path $root -Force)
        $a = Join-Path $root 'a.txt'
        Write-DeepTestFile -Path $a -Content 'alpha'
        $hash = Get-DeepTestHash $a
        $manifest = Join-Path $root 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @("$hash  a.txt", "$hash  a.txt")

        $result = Test-PnccSha256Inventory -FixtureRoot $root -ManifestPath $manifest
        $result.Status | Should -Be 'FAIL'
        @($result.Errors) -join '|' | Should -Match 'DUPLICATE_ENTRY:2:a.txt'
    }

    It 'fails closed on parent-directory traversal' {
        $root = Join-Path $TestDrive 'traversal'
        [void](New-Item -ItemType Directory -Path $root -Force)
        $manifest = Join-Path $root 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @((('0' * 64) + '  ../outside.txt'))

        $result = Test-PnccSha256Inventory -FixtureRoot $root -ManifestPath $manifest
        $result.Status | Should -Be 'FAIL'
        @($result.Errors) -join '|' | Should -Match 'UNSAFE_PATH:1:'
    }

    It 'fails closed on an absolute manifest path' {
        $root = Join-Path $TestDrive 'absolute'
        [void](New-Item -ItemType Directory -Path $root -Force)
        $outside = [IO.Path]::GetFullPath((Join-Path $root '..\outside.txt'))
        $manifest = Join-Path $root 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @((('0' * 64) + '  ' + $outside))

        $result = Test-PnccSha256Inventory -FixtureRoot $root -ManifestPath $manifest
        $result.Status | Should -Be 'FAIL'
        @($result.Errors) -join '|' | Should -Match 'UNSAFE_PATH:1:'
    }

    It 'fails closed when the manifest tries to inventory itself' {
        $root = Join-Path $TestDrive 'self-entry'
        [void](New-Item -ItemType Directory -Path $root -Force)
        $manifest = Join-Path $root 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @((('0' * 64) + '  SANITIZED-SHA256.txt'))

        $result = Test-PnccSha256Inventory -FixtureRoot $root -ManifestPath $manifest
        $result.Status | Should -Be 'FAIL'
        @($result.Errors) -join '|' | Should -Match 'MANIFEST_SELF_ENTRY:1'
    }
}

Describe 'PNCC DEEP Git-object and historical EOL provenance semantics' {
    It 'hashes committed Git blob bytes instead of a transformed working tree' {
        $repo = Join-Path $TestDrive 'git-blob-semantics'
        $fixture = Join-Path $repo 'fixture'
        [void](New-Item -ItemType Directory -Path $fixture -Force)
        Write-DeepTestFile -Path (Join-Path $repo '.gitattributes') -Content '*.ps1 text eol=crlf'
        $scriptPath = Join-Path $fixture 'a.ps1'
        Write-DeepTestFile -Path $scriptPath -Content "alpha`nbeta`n"
        $expectedHash = Get-DeepTestHash $scriptPath
        $manifest = Join-Path $fixture 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @("$expectedHash  a.ps1")

        Initialize-DeepGitRepo -Path $repo
        & git -C $repo add --all
        & git -C $repo commit -m 'fixture' | Out-Null
        $LASTEXITCODE | Should -Be 0

        Write-DeepTestFile -Path $scriptPath -Content "alpha`r`nbeta`r`n"
        (Get-DeepTestHash $scriptPath) | Should -Not -Be $expectedHash

        $result = Test-PnccGitSha256Inventory -RepositoryRoot $repo -FixtureRelativePath 'fixture' -ManifestPath $manifest
        $result.Status | Should -Be 'PASS'
        $result.EntryCount | Should -Be 1
        $result.ActualFileCount | Should -Be 1
        $result.VerifiedCount | Should -Be 1
        $result.EolReconciledCount | Should -Be 0
        @($result.Errors).Count | Should -Be 0
    }

    It 'reconciles an explicitly allowlisted pre-import CRLF manifest entry against a normalized Git blob' {
        $repo = Join-Path $TestDrive 'git-eol-allowed'
        $fixture = Join-Path $repo 'fixture'
        [void](New-Item -ItemType Directory -Path $fixture -Force)
        Write-DeepTestFile -Path (Join-Path $repo '.gitattributes') -Content '*.ps1 text eol=crlf'
        $scriptPath = Join-Path $fixture 'a.ps1'
        Write-DeepTestFile -Path $scriptPath -Content "alpha`r`nbeta`r`n"
        $expectedHash = Get-DeepTestHash $scriptPath
        $manifest = Join-Path $fixture 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @("$expectedHash  a.ps1")

        Initialize-DeepGitRepo -Path $repo
        & git -C $repo add --all
        & git -C $repo commit -m 'fixture' | Out-Null
        $LASTEXITCODE | Should -Be 0

        $result = Test-PnccGitSha256Inventory -RepositoryRoot $repo -FixtureRelativePath 'fixture' -ManifestPath $manifest -AllowedEolReconciledPaths @('a.ps1')
        $result.Status | Should -Be 'PASS'
        $result.VerifiedCount | Should -Be 1
        $result.EolReconciledCount | Should -Be 1
        @($result.EolReconciledPaths) | Should -Contain 'a.ps1'
        @($result.Errors).Count | Should -Be 0
    }

    It 'fails closed when pre-import EOL reconciliation is not explicitly allowlisted' {
        $repo = Join-Path $TestDrive 'git-eol-blocked'
        $fixture = Join-Path $repo 'fixture'
        [void](New-Item -ItemType Directory -Path $fixture -Force)
        Write-DeepTestFile -Path (Join-Path $repo '.gitattributes') -Content '*.ps1 text eol=crlf'
        $scriptPath = Join-Path $fixture 'a.ps1'
        Write-DeepTestFile -Path $scriptPath -Content "alpha`r`nbeta`r`n"
        $expectedHash = Get-DeepTestHash $scriptPath
        $manifest = Join-Path $fixture 'SANITIZED-SHA256.txt'
        Write-DeepManifest -Path $manifest -Lines @("$expectedHash  a.ps1")

        Initialize-DeepGitRepo -Path $repo
        & git -C $repo add --all
        & git -C $repo commit -m 'fixture' | Out-Null
        $LASTEXITCODE | Should -Be 0

        $result = Test-PnccGitSha256Inventory -RepositoryRoot $repo -FixtureRelativePath 'fixture' -ManifestPath $manifest
        $result.Status | Should -Be 'FAIL'
        @($result.Errors) -join '|' | Should -Match 'EOL_RECONCILIATION_NOT_ALLOWED:a.ps1'
    }
}
