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
