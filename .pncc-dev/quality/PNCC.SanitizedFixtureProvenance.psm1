Set-StrictMode -Version 3.0

function ConvertTo-PnccProvenanceResult {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Status,
        [Parameter(Mandatory=$true)][string]$FailureClass,
        [Parameter(Mandatory=$true)][AllowEmptyCollection()][object[]]$Errors,
        [int]$EntryCount = 0,
        [int]$ActualFileCount = 0,
        [int]$VerifiedCount = 0,
        [string]$FixtureGitTreeSha = '',
        [int]$EolReconciledCount = 0,
        [object[]]$EolReconciledPaths = @()
    )

    return [pscustomobject][ordered]@{
        SchemaVersion = 1
        Status = $Status
        FailureClass = $FailureClass
        EntryCount = [int]$EntryCount
        ActualFileCount = [int]$ActualFileCount
        VerifiedCount = [int]$VerifiedCount
        FixtureGitTreeSha = [string]$FixtureGitTreeSha
        EolReconciledCount = [int]$EolReconciledCount
        EolReconciledPaths = [object[]]@($EolReconciledPaths)
        Errors = [object[]]@($Errors)
    }
}

function Get-PnccSha256FromBytes {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][byte[]]$Bytes)

    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Get-PnccGitBlobBytes {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$RepositoryRoot,
        [Parameter(Mandatory=$true)][string]$BlobSha
    )

    $process = New-Object Diagnostics.Process
    $memory = New-Object IO.MemoryStream
    try {
        $startInfo = New-Object Diagnostics.ProcessStartInfo
        $startInfo.FileName = 'git'
        $startInfo.Arguments = "cat-file blob $BlobSha"
        $startInfo.WorkingDirectory = $RepositoryRoot
        $startInfo.UseShellExecute = $false
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $startInfo.CreateNoWindow = $true
        $process.StartInfo = $startInfo
        [void]$process.Start()
        $process.StandardOutput.BaseStream.CopyTo($memory)
        $stderr = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) {
            return [pscustomobject]@{
                Success = $false
                Bytes = [byte[]]@()
                Error = $stderr.Trim()
            }
        }
        return [pscustomobject]@{
            Success = $true
            Bytes = [byte[]]$memory.ToArray()
            Error = ''
        }
    }
    catch {
        return [pscustomobject]@{
            Success = $false
            Bytes = [byte[]]@()
            Error = $_.Exception.Message
        }
    }
    finally {
        $memory.Dispose()
        $process.Dispose()
    }
}

function Get-PnccEolVariantHashes {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][byte[]]$Bytes)

    $result = [ordered]@{
        IsUtf8 = $false
        LfHash = ''
        CrlfHash = ''
    }

    $hasBom = $Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF
    $offset = 0
    if ($hasBom) { $offset = 3 }

    try {
        $utf8Strict = New-Object Text.UTF8Encoding($false, $true)
        $text = $utf8Strict.GetString($Bytes, $offset, $Bytes.Length - $offset)
    }
    catch {
        return [pscustomobject]$result
    }

    $lfText = ($text -replace "`r`n", "`n") -replace "`r", "`n"
    $crlfText = $lfText -replace "`n", "`r`n"
    $utf8NoBom = New-Object Text.UTF8Encoding($false)
    [byte[]]$lfBytes = $utf8NoBom.GetBytes($lfText)
    [byte[]]$crlfBytes = $utf8NoBom.GetBytes($crlfText)
    if ($hasBom) {
        [byte[]]$bom = @(0xEF, 0xBB, 0xBF)
        [byte[]]$lfBytes = @($bom + $lfBytes)
        [byte[]]$crlfBytes = @($bom + $crlfBytes)
    }

    $result.IsUtf8 = $true
    $result.LfHash = Get-PnccSha256FromBytes -Bytes $lfBytes
    $result.CrlfHash = Get-PnccSha256FromBytes -Bytes $crlfBytes
    return [pscustomobject]$result
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

function Test-PnccGitSha256Inventory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$RepositoryRoot,
        [Parameter(Mandatory=$true)][string]$FixtureRelativePath,
        [Parameter(Mandatory=$true)][string]$ManifestPath,
        [string[]]$AllowedEolReconciledPaths = @()
    )

    $errors = New-Object System.Collections.ArrayList
    $entries = @{}
    $allowedEol = @{}
    $reconciled = @{}
    $verifiedCount = 0
    $actualFileCount = 0

    foreach ($allowedPathRaw in @($AllowedEolReconciledPaths)) {
        $allowedPath = ([string]$allowedPathRaw).Replace('\', '/').Trim()
        $allowedSegments = @($allowedPath -split '/')
        if ([string]::IsNullOrWhiteSpace($allowedPath) -or
            [IO.Path]::IsPathRooted($allowedPath) -or
            $allowedPath.Contains(':') -or
            $allowedSegments -contains '.' -or
            $allowedSegments -contains '..') {
            [void]$errors.Add('EOL_ALLOWLIST_PATH_UNSAFE:' + $allowedPath)
            continue
        }
        $allowedKey = $allowedPath.ToLowerInvariant()
        if ($allowedEol.ContainsKey($allowedKey)) {
            [void]$errors.Add('EOL_ALLOWLIST_DUPLICATE:' + $allowedPath)
            continue
        }
        $allowedEol[$allowedKey] = $allowedPath
    }

    try {
        $repoRoot = [IO.Path]::GetFullPath($RepositoryRoot)
        $fixtureRelative = $FixtureRelativePath.Replace('\', '/').Trim('/')
        $fixtureRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot ($fixtureRelative.Replace('/', [IO.Path]::DirectorySeparatorChar))))
        $manifestFull = [IO.Path]::GetFullPath($ManifestPath)
    }
    catch {
        [void]$errors.Add('PATH_RESOLUTION_FAILED:' + $_.Exception.Message)
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors)
    }

    if ([string]::IsNullOrWhiteSpace($fixtureRelative) -or $fixtureRelative.Contains(':') -or $fixtureRelative -match '(^|/)\.\.(/|$)') {
        [void]$errors.Add('FIXTURE_RELATIVE_PATH_UNSAFE')
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors)
    }
    if (-not (Test-Path -LiteralPath $manifestFull -PathType Leaf)) {
        [void]$errors.Add('MANIFEST_MISSING')
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors)
    }

    $trimChars = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $fixtureRoot = $fixtureRoot.TrimEnd($trimChars)
    $rootPrefix = $fixtureRoot + [IO.Path]::DirectorySeparatorChar
    if (-not $manifestFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        [void]$errors.Add('MANIFEST_OUTSIDE_FIXTURE_ROOT')
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors)
    }
    $manifestRelative = $manifestFull.Substring($rootPrefix.Length).Replace('\', '/')

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
            $candidateFull = [IO.Path]::GetFullPath((Join-Path $fixtureRoot ($relative.Replace('/', [IO.Path]::DirectorySeparatorChar))))
        }
        catch {
            [void]$errors.Add("UNSAFE_PATH:${lineNumber}:$relative")
            continue
        }
        if (-not $candidateFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            [void]$errors.Add("UNSAFE_PATH:${lineNumber}:$relative")
            continue
        }
        if ($relative.Equals($manifestRelative, [StringComparison]::OrdinalIgnoreCase)) {
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
            ExpectedHash = $expectedHash
        }
    }

    $gitTreeOutput = @(& git -C $repoRoot ls-tree -r --name-only ('HEAD:' + $fixtureRelative) 2>&1)
    $gitTreeExitCode = $LASTEXITCODE
    if ($gitTreeExitCode -ne 0) {
        [void]$errors.Add('GIT_TREE_INVENTORY_FAILED:' + (($gitTreeOutput | Out-String).Trim()))
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors) -EntryCount $entries.Count
    }

    $actualByKey = @{}
    foreach ($rawPath in $gitTreeOutput) {
        $relative = ([string]$rawPath).Replace('\', '/').Trim()
        if ([string]::IsNullOrWhiteSpace($relative)) { continue }
        if ($relative.Equals($manifestRelative, [StringComparison]::OrdinalIgnoreCase)) { continue }
        $key = $relative.ToLowerInvariant()
        $actualByKey[$key] = $relative
    }
    $actualFileCount = [int]$actualByKey.Count

    foreach ($key in @($entries.Keys)) {
        $entry = $entries[$key]
        if (-not $actualByKey.ContainsKey($key)) {
            [void]$errors.Add('MISSING_FILE:' + [string]$entry.RelativePath)
            continue
        }

        $objectPath = $fixtureRelative + '/' + [string]$entry.RelativePath
        $blobOutput = @(& git -C $repoRoot rev-parse ('HEAD:' + $objectPath) 2>&1)
        $blobExitCode = $LASTEXITCODE
        if ($blobExitCode -ne 0) {
            [void]$errors.Add('GIT_BLOB_RESOLUTION_FAILED:' + [string]$entry.RelativePath)
            continue
        }
        $blobSha = (($blobOutput | Out-String).Trim()).ToLowerInvariant()
        $blobResult = Get-PnccGitBlobBytes -RepositoryRoot $repoRoot -BlobSha $blobSha
        if (-not [bool]$blobResult.Success) {
            [void]$errors.Add('GIT_BLOB_READ_FAILED:' + [string]$entry.RelativePath + ':' + [string]$blobResult.Error)
            continue
        }

        $blobBytes = [byte[]]$blobResult.Bytes
        $actualHash = Get-PnccSha256FromBytes -Bytes $blobBytes
        if ($actualHash -eq [string]$entry.ExpectedHash) {
            $verifiedCount++
            continue
        }

        $eolVariants = Get-PnccEolVariantHashes -Bytes $blobBytes
        $eolMatches = [bool]$eolVariants.IsUtf8 -and (
            [string]$entry.ExpectedHash -eq [string]$eolVariants.LfHash -or
            [string]$entry.ExpectedHash -eq [string]$eolVariants.CrlfHash
        )
        if ($eolMatches) {
            if (-not $allowedEol.ContainsKey($key)) {
                [void]$errors.Add('EOL_RECONCILIATION_NOT_ALLOWED:' + [string]$entry.RelativePath)
                continue
            }
            $reconciled[$key] = [string]$entry.RelativePath
            $verifiedCount++
            continue
        }

        [void]$errors.Add('HASH_MISMATCH:' + [string]$entry.RelativePath)
    }

    foreach ($key in @($actualByKey.Keys)) {
        if (-not $entries.ContainsKey($key)) {
            [void]$errors.Add('UNLISTED_FILE:' + [string]$actualByKey[$key])
        }
    }

    foreach ($allowedKey in @($allowedEol.Keys)) {
        if (-not $entries.ContainsKey($allowedKey)) {
            [void]$errors.Add('EOL_ALLOWLIST_ENTRY_MISSING:' + [string]$allowedEol[$allowedKey])
            continue
        }
        if (-not $reconciled.ContainsKey($allowedKey)) {
            [void]$errors.Add('EOL_ALLOWLIST_NOT_RECONCILED:' + [string]$allowedEol[$allowedKey])
        }
    }

    $reconciledPaths = @($reconciled.Values | Sort-Object)
    if ($errors.Count -gt 0) {
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors) -EntryCount $entries.Count -ActualFileCount $actualFileCount -VerifiedCount $verifiedCount -EolReconciledCount $reconciled.Count -EolReconciledPaths $reconciledPaths
    }

    return ConvertTo-PnccProvenanceResult -Status 'PASS' -FailureClass 'NONE' -Errors @() -EntryCount $entries.Count -ActualFileCount $actualFileCount -VerifiedCount $verifiedCount -EolReconciledCount $reconciled.Count -EolReconciledPaths $reconciledPaths
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
    if ([string]$contract.ManifestHashSemantics -ne 'SANITIZED_IMPORT_BYTES_WITH_EXPLICIT_GIT_EOL_RECONCILIATION') {
        [void]$errors.Add('MANIFEST_HASH_SEMANTICS_INVALID')
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
    $allowedEolPaths = @($contract.EolReconciledPaths | ForEach-Object { [string]$_ })

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

    $inventory = Test-PnccGitSha256Inventory -RepositoryRoot $repoRoot -FixtureRelativePath $fixtureRelative -ManifestPath $manifestPath -AllowedEolReconciledPaths $allowedEolPaths
    if ([string]$inventory.Status -ne 'PASS') {
        foreach ($inventoryError in @($inventory.Errors)) {
            [void]$errors.Add('INVENTORY:' + [string]$inventoryError)
        }
    }
    if ([int]$inventory.EntryCount -ne [int]$contract.ManifestEntryCount) {
        [void]$errors.Add('MANIFEST_ENTRY_COUNT_MISMATCH')
    }
    if ([int]$inventory.EolReconciledCount -ne $allowedEolPaths.Count) {
        [void]$errors.Add('EOL_RECONCILIATION_COUNT_MISMATCH')
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

    $reconciledPaths = @($inventory.EolReconciledPaths)
    if ($errors.Count -gt 0) {
        return ConvertTo-PnccProvenanceResult -Status 'FAIL' -FailureClass 'FIXTURE_PROVENANCE_INVALID' -Errors @($errors) -EntryCount ([int]$inventory.EntryCount) -ActualFileCount ([int]$inventory.ActualFileCount) -VerifiedCount ([int]$inventory.VerifiedCount) -FixtureGitTreeSha $treeSha -EolReconciledCount ([int]$inventory.EolReconciledCount) -EolReconciledPaths $reconciledPaths
    }

    return ConvertTo-PnccProvenanceResult -Status 'PASS' -FailureClass 'NONE' -Errors @() -EntryCount ([int]$inventory.EntryCount) -ActualFileCount ([int]$inventory.ActualFileCount) -VerifiedCount ([int]$inventory.VerifiedCount) -FixtureGitTreeSha $treeSha -EolReconciledCount ([int]$inventory.EolReconciledCount) -EolReconciledPaths $reconciledPaths
}

Export-ModuleMember -Function Test-PnccSha256Inventory, Test-PnccGitSha256Inventory, Test-PnccSanitizedFixtureProvenance
