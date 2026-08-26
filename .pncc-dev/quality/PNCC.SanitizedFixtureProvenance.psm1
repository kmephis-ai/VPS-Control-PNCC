Set-StrictMode -Version 3.0

function ConvertTo-PnccProvenanceResult {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Status,
        [Parameter(Mandatory=$true)][string]$FailureClass,
        [Parameter(Mandatory=$true)][object[]]$Errors,
        [int]$EntryCount = 0,
        [int]$ActualFileCount = 0,
        [int]$VerifiedCount = 0,
        [string]$FixtureGitTreeSha = ''
    )

    return [pscustomobject][ordered]@{
        SchemaVersion = 1
        Status = $Status
        FailureClass = $FailureClass
        EntryCount = [int]$EntryCount
        ActualFileCount = [int]$ActualFileCount
        VerifiedCount = [int]$VerifiedCount
        FixtureGitTreeSha = [string]$FixtureGitTreeSha
        Errors = [object[]]@($Errors)
    }
}

function Test-PnccSha256Inventory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$FixtureRoot,
        [Parameter(Mandatory=$true)][string]$ManifestPath
    )

    $errors = New-Object System.Collections.ArrayList
    $entries = @{}
    $verifiedCount = 0
    $actualFileCount = 0

    try {
        $trimChars = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
        $rootFull = [IO.Path]::GetFullPath($FixtureRoot).TrimEnd($trimChars)
        $manifestFull = [IO.Path]::GetFullPath($ManifestPath)
    }
    catch {
        [void]$errors.Add('PATH_RESOLUTION_FAILED:' + $_.Exception.Message)
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors)
    }

    if (-not (Test-Path -LiteralPath $rootFull -PathType Container)) {
        [void]$errors.Add('FIXTURE_ROOT_MISSING')
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors)
    }
    if (-not (Test-Path -LiteralPath $manifestFull -PathType Leaf)) {
        [void]$errors.Add('MANIFEST_MISSING')
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors)
    }

    $rootPrefix = $rootFull + [IO.Path]::DirectorySeparatorChar
    if (-not $manifestFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        [void]$errors.Add('MANIFEST_OUTSIDE_FIXTURE_ROOT')
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors)
    }

    $lineNumber = 0
    foreach ($line in [IO.File]::ReadAllLines($manifestFull)) {
        $lineNumber++
        if ([string]::IsNullOrWhiteSpace($line)) {
            [void]$errors.Add("MALFORMED_LINE:$lineNumber")
            continue
        }

        $match = [regex]::Match($line, '^(?<hash>[0-9a-fA-F]{64})  (?<path>.+)$')
        if (-not $match.Success) {
            [void]$errors.Add("MALFORMED_LINE:$lineNumber")
            continue
        }

        $expectedHash = ([string]$match.Groups['hash'].Value).ToLowerInvariant()
        $relative = ([string]$match.Groups['path'].Value).Replace('\', '/').Trim()
        $segments = @($relative -split '/')

        if ([string]::IsNullOrWhiteSpace($relative) -or
            [IO.Path]::IsPathRooted($relative) -or
            $relative.Contains(':') -or
            $segments -contains '.' -or
            $segments -contains '..') {
            [void]$errors.Add("UNSAFE_PATH:${lineNumber}:$relative")
            continue
        }

        try {
            $candidateFull = [IO.Path]::GetFullPath((Join-Path $rootFull ($relative.Replace('/', [IO.Path]::DirectorySeparatorChar))))
        }
        catch {
            [void]$errors.Add("UNSAFE_PATH:${lineNumber}:$relative")
            continue
        }

        if (-not $candidateFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            [void]$errors.Add("UNSAFE_PATH:${lineNumber}:$relative")
            continue
        }
        if ($candidateFull.Equals($manifestFull, [StringComparison]::OrdinalIgnoreCase)) {
            [void]$errors.Add("MANIFEST_SELF_ENTRY:$lineNumber")
            continue
        }

        $key = $relative.ToLowerInvariant()
        if ($entries.ContainsKey($key)) {
            [void]$errors.Add("DUPLICATE_ENTRY:${lineNumber}:$relative")
            continue
        }

        $entries[$key] = [pscustomobject]@{
            RelativePath = $relative
            FullPath = $candidateFull
            ExpectedHash = $expectedHash
        }
    }

    $actualByKey = @{}
    foreach ($file in @(Get-ChildItem -LiteralPath $rootFull -Recurse -File -ErrorAction Stop)) {
        if ($file.FullName.Equals($manifestFull, [StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        $relative = $file.FullName.Substring($rootPrefix.Length).Replace('\', '/')
        $key = $relative.ToLowerInvariant()
        $actualByKey[$key] = [string]$relative
    }
    $actualFileCount = [int]$actualByKey.Count

    foreach ($key in @($entries.Keys)) {
        $entry = $entries[$key]
        if (-not $actualByKey.ContainsKey($key)) {
            [void]$errors.Add('MISSING_FILE:' + [string]$entry.RelativePath)
            continue
        }

        try {
            $actualHash = ((Get-FileHash -LiteralPath ([string]$entry.FullPath) -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
        }
        catch {
            [void]$errors.Add('HASH_READ_FAILED:' + [string]$entry.RelativePath)
            continue
        }

        if ($actualHash -ne [string]$entry.ExpectedHash) {
            [void]$errors.Add('HASH_MISMATCH:' + [string]$entry.RelativePath)
            continue
        }
        $verifiedCount++
    }

    foreach ($key in @($actualByKey.Keys)) {
        if (-not $entries.ContainsKey($key)) {
            [void]$errors.Add('UNLISTED_FILE:' + [string]$actualByKey[$key])
        }
    }

    if ($errors.Count -gt 0) {
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors) -EntryCount $entries.Count -ActualFileCount $actualFileCount -VerifiedCount $verifiedCount
    }

    return ConvertTo-PnccProvenanceResult -Status 'PASS' -FailureClass 'NONE' -Errors @() -EntryCount $entries.Count -ActualFileCount $actualFileCount -VerifiedCount $verifiedCount
}

function Test-PnccSanitizedFixtureProvenance {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$RepositoryRoot,
        [Parameter(Mandatory=$true)][string]$ContractPath
    )

    $errors = New-Object System.Collections.ArrayList
    $treeSha = ''
    $inventory = $null

    try {
        $repoRoot = [IO.Path]::GetFullPath($RepositoryRoot)
        $contractFull = [IO.Path]::GetFullPath($ContractPath)
        $contract = Get-Content -LiteralPath $contractFull -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        [void]$errors.Add('CONTRACT_READ_FAILED:' + $_.Exception.Message)
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors)
    }

    if ([int]$contract.SchemaVersion -ne 1) {
        [void]$errors.Add('CONTRACT_SCHEMA_UNSUPPORTED')
    }
    if ([string]$contract.IdentitySemantics -ne 'SANITIZED_NOT_BYTE_IDENTICAL_NOT_RUNTIME_QUALIFIED') {
        [void]$errors.Add('IDENTITY_SEMANTICS_INVALID')
    }
    if ([bool]$contract.OriginalPrivateCandidate.RuntimeQualificationAuthority) {
        [void]$errors.Add('RUNTIME_AUTHORITY_MUST_BE_FALSE')
    }
    if ([bool]$contract.OriginalPrivateCandidate.StableDoneAtPublication) {
        [void]$errors.Add('STABLE_DONE_AT_PUBLICATION_MUST_BE_FALSE')
    }

    $fixtureRelative = ([string]$contract.FixturePath).Replace('\', '/')
    $fixtureRoot = Join-Path $repoRoot ($fixtureRelative.Replace('/', [IO.Path]::DirectorySeparatorChar))
    $manifestPath = Join-Path $fixtureRoot ([string]$contract.ManifestRelativePath)

    try {
        $gitOutput = @(& git -C $repoRoot rev-parse ('HEAD:' + $fixtureRelative) 2>&1)
        $gitExitCode = $LASTEXITCODE
        if ($gitExitCode -ne 0) {
            [void]$errors.Add('GIT_TREE_RESOLUTION_FAILED:' + (($gitOutput | Out-String).Trim()))
        }
        else {
            $treeSha = (($gitOutput | Out-String).Trim()).ToLowerInvariant()
            if ($treeSha -ne ([string]$contract.FixtureGitTreeSha).ToLowerInvariant()) {
                [void]$errors.Add('GIT_TREE_MISMATCH')
            }
        }
    }
    catch {
        [void]$errors.Add('GIT_TREE_RESOLUTION_FAILED:' + $_.Exception.Message)
    }

    $inventory = Test-PnccSha256Inventory -FixtureRoot $fixtureRoot -ManifestPath $manifestPath
    if ([string]$inventory.Status -ne 'PASS') {
        foreach ($inventoryError in @($inventory.Errors)) {
            [void]$errors.Add('INVENTORY:' + [string]$inventoryError)
        }
    }
    if ([int]$inventory.EntryCount -ne [int]$contract.ManifestEntryCount) {
        [void]$errors.Add('MANIFEST_ENTRY_COUNT_MISMATCH')
    }

    $sanitationPath = Join-Path $fixtureRoot 'PUBLIC_SANITATION.md'
    try {
        $sanitation = [IO.File]::ReadAllText($sanitationPath)
        $requiredSanitationText = @(
            'sanitized public migration snapshot derived from',
            'It is **not** the exact runtime-qualified RC14.38 artifact',
            [string]$contract.OriginalPrivateCandidate.Version,
            [string]$contract.OriginalPrivateCandidate.ZipSha256,
            'status at migration: NOT Stable/DONE'
        )
        foreach ($requiredText in $requiredSanitationText) {
            if ($sanitation.IndexOf($requiredText, [StringComparison]::Ordinal) -lt 0) {
                [void]$errors.Add('SANITATION_RECORD_MISSING:' + $requiredText)
            }
        }
    }
    catch {
        [void]$errors.Add('SANITATION_RECORD_READ_FAILED:' + $_.Exception.Message)
    }

    if ($errors.Count -gt 0) {
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors) -EntryCount ([int]$inventory.EntryCount) -ActualFileCount ([int]$inventory.ActualFileCount) -VerifiedCount ([int]$inventory.VerifiedCount) -FixtureGitTreeSha $treeSha
    }

    return ConvertTo-PnccProvenanceResult -Status 'PASS' -FailureClass 'NONE' -Errors @() -EntryCount ([int]$inventory.EntryCount) -ActualFileCount ([int]$inventory.ActualFileCount) -VerifiedCount ([int]$inventory.VerifiedCount) -FixtureGitTreeSha $treeSha
}

Export-ModuleMember -Function Test-PnccSha256Inventory, Test-PnccSanitizedFixtureProvenance
