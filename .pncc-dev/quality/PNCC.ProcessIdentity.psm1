Set-StrictMode -Version 3.0

function Get-PnccPropertyValue {
    [CmdletBinding()]
    param(
        [AllowNull()][object]$InputObject,
        [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$Name
    )

    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function ConvertTo-PnccPathKey {
    [CmdletBinding()]
    param([AllowNull()][object]$Value)

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) { return '' }
    try {
        return ([IO.Path]::GetFullPath($text)).TrimEnd([char[]]@('\', '/')).ToLowerInvariant()
    }
    catch {
        return ''
    }
}

function ConvertTo-PnccUtcTick {
    [CmdletBinding()]
    param([AllowNull()][object]$Value)

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }
    try {
        $parsed = [DateTimeOffset]::Parse(
            $text,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind
        )
        return [long]$parsed.UtcDateTime.Ticks
    }
    catch {
        return $null
    }
}

function Test-PnccCommandMarker {
    [CmdletBinding()]
    param(
        [AllowNull()][object]$Text,
        [AllowEmptyCollection()][object[]]$Markers = @()
    )

    $commandLine = [string]$Text
    $required = @($Markers | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ([string]::IsNullOrWhiteSpace($commandLine) -or $required.Count -eq 0) { return $false }

    foreach ($marker in $required) {
        if ($commandLine.IndexOf($marker, [StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
    }
    return $true
}

function Test-PnccExpectedIdentity {
    [CmdletBinding()]
    param([AllowNull()][object]$Identity)

    if ($null -eq $Identity) { return $false }

    [int]$parsedProcessId = 0
    $processIdValue = Get-PnccPropertyValue -InputObject $Identity -Name 'ProcessId'
    if (-not [int]::TryParse([string]$processIdValue, [ref]$parsedProcessId) -or $parsedProcessId -le 0) { return $false }

    $processName = [string](Get-PnccPropertyValue -InputObject $Identity -Name 'ProcessName')
    $pathKey = ConvertTo-PnccPathKey (Get-PnccPropertyValue -InputObject $Identity -Name 'ExecutablePath')
    $creationTick = ConvertTo-PnccUtcTick (Get-PnccPropertyValue -InputObject $Identity -Name 'CreationTimeUtc')
    $markers = @(Get-PnccPropertyValue -InputObject $Identity -Name 'CommandLineMarkers')

    if ([string]::IsNullOrWhiteSpace($processName)) { return $false }
    if ([string]::IsNullOrWhiteSpace($pathKey)) { return $false }
    if ($null -eq $creationTick) { return $false }
    if (@($markers | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count -eq 0) { return $false }
    return $true
}

function Test-PnccObservedIdentity {
    [CmdletBinding()]
    param([AllowNull()][object]$Identity)

    if ($null -eq $Identity) { return $false }

    [int]$parsedProcessId = 0
    $processIdValue = Get-PnccPropertyValue -InputObject $Identity -Name 'ProcessId'
    if (-not [int]::TryParse([string]$processIdValue, [ref]$parsedProcessId) -or $parsedProcessId -le 0) { return $false }

    $processName = [string](Get-PnccPropertyValue -InputObject $Identity -Name 'ProcessName')
    $pathKey = ConvertTo-PnccPathKey (Get-PnccPropertyValue -InputObject $Identity -Name 'ExecutablePath')
    $commandLine = [string](Get-PnccPropertyValue -InputObject $Identity -Name 'CommandLine')
    $creationTick = ConvertTo-PnccUtcTick (Get-PnccPropertyValue -InputObject $Identity -Name 'CreationTimeUtc')

    if ([string]::IsNullOrWhiteSpace($processName)) { return $false }
    if ([string]::IsNullOrWhiteSpace($pathKey)) { return $false }
    if ([string]::IsNullOrWhiteSpace($commandLine)) { return $false }
    if ($null -eq $creationTick) { return $false }
    return $true
}

function Test-PnccManagedRule {
    [CmdletBinding()]
    param([AllowNull()][object]$Rule)

    if ($null -eq $Rule) { return $false }
    $role = [string](Get-PnccPropertyValue -InputObject $Rule -Name 'Role')
    $processName = [string](Get-PnccPropertyValue -InputObject $Rule -Name 'ProcessName')
    $pathKey = ConvertTo-PnccPathKey (Get-PnccPropertyValue -InputObject $Rule -Name 'ExecutablePath')
    $markers = @(Get-PnccPropertyValue -InputObject $Rule -Name 'CommandLineMarkers')

    if ([string]::IsNullOrWhiteSpace($role)) { return $false }
    if ([string]::IsNullOrWhiteSpace($processName)) { return $false }
    if ([string]::IsNullOrWhiteSpace($pathKey)) { return $false }
    if (@($markers | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count -eq 0) { return $false }
    return $true
}

function ConvertTo-PnccProcessEvidenceResult {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('OWNED', 'FOREIGN', 'NOT_RUNNING', 'CLEAN', 'DIRTY_OWNED', 'DIRTY_FOREIGN', 'BLOCKED_AMBIGUOUS')]
        [string]$Status,

        [Parameter(Mandatory = $true)]
        [ValidateSet('NONE', 'OWNED_PROCESS_ONLY')]
        [string]$CleanupAuthority,

        [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$Reason,
        [int]$RelevantCount = 0,
        [int]$OwnedCount = 0,
        [int]$ForeignCount = 0,
        [int]$AmbiguousCount = 0,
        [AllowEmptyCollection()][object[]]$OwnedProcessIds = @()
    )

    return [pscustomobject][ordered]@{
        SchemaVersion = 1
        Status = $Status
        CleanupAuthority = $CleanupAuthority
        Reason = $Reason
        RelevantCount = [int]$RelevantCount
        OwnedCount = [int]$OwnedCount
        ForeignCount = [int]$ForeignCount
        AmbiguousCount = [int]$AmbiguousCount
        OwnedProcessIds = [object[]]@($OwnedProcessIds)
        PerformsProcessMutation = $false
        RuntimeMutationAuthority = $false
    }
}

function Resolve-PnccPidOwnership {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$ExpectedIdentity,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$ObservedProcesses
    )

    if (-not (Test-PnccExpectedIdentity -Identity $ExpectedIdentity)) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'BLOCKED_AMBIGUOUS' -CleanupAuthority 'NONE' -Reason 'EXPECTED_IDENTITY_INCOMPLETE' -AmbiguousCount 1
    }

    $expectedProcessId = [int](Get-PnccPropertyValue -InputObject $ExpectedIdentity -Name 'ProcessId')
    $matching = @($ObservedProcesses | Where-Object {
        [int]$candidateId = 0
        $candidateValue = Get-PnccPropertyValue -InputObject $_ -Name 'ProcessId'
        [int]::TryParse([string]$candidateValue, [ref]$candidateId) -and $candidateId -eq $expectedProcessId
    })

    if ($matching.Count -eq 0) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'NOT_RUNNING' -CleanupAuthority 'NONE' -Reason 'PID_NOT_PRESENT'
    }
    if ($matching.Count -ne 1) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'BLOCKED_AMBIGUOUS' -CleanupAuthority 'NONE' -Reason 'DUPLICATE_PID_OBSERVATION' -RelevantCount $matching.Count -AmbiguousCount $matching.Count
    }

    $observed = $matching[0]
    if (-not (Test-PnccObservedIdentity -Identity $observed)) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'BLOCKED_AMBIGUOUS' -CleanupAuthority 'NONE' -Reason 'OBSERVED_IDENTITY_INCOMPLETE' -RelevantCount 1 -AmbiguousCount 1
    }

    $expectedName = [string](Get-PnccPropertyValue -InputObject $ExpectedIdentity -Name 'ProcessName')
    $observedName = [string](Get-PnccPropertyValue -InputObject $observed -Name 'ProcessName')
    if (-not [string]::Equals($expectedName, $observedName, [StringComparison]::OrdinalIgnoreCase)) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'FOREIGN' -CleanupAuthority 'NONE' -Reason 'PROCESS_NAME_MISMATCH' -RelevantCount 1 -ForeignCount 1
    }

    $expectedPath = ConvertTo-PnccPathKey (Get-PnccPropertyValue -InputObject $ExpectedIdentity -Name 'ExecutablePath')
    $observedPath = ConvertTo-PnccPathKey (Get-PnccPropertyValue -InputObject $observed -Name 'ExecutablePath')
    if ($expectedPath -ne $observedPath) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'FOREIGN' -CleanupAuthority 'NONE' -Reason 'EXECUTABLE_PATH_MISMATCH' -RelevantCount 1 -ForeignCount 1
    }

    $expectedCreationTick = ConvertTo-PnccUtcTick (Get-PnccPropertyValue -InputObject $ExpectedIdentity -Name 'CreationTimeUtc')
    $observedCreationTick = ConvertTo-PnccUtcTick (Get-PnccPropertyValue -InputObject $observed -Name 'CreationTimeUtc')
    if ($expectedCreationTick -ne $observedCreationTick) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'FOREIGN' -CleanupAuthority 'NONE' -Reason 'PID_REUSED' -RelevantCount 1 -ForeignCount 1
    }

    $markers = @(Get-PnccPropertyValue -InputObject $ExpectedIdentity -Name 'CommandLineMarkers')
    $observedCommandLine = Get-PnccPropertyValue -InputObject $observed -Name 'CommandLine'
    if (-not (Test-PnccCommandMarker -Text $observedCommandLine -Markers $markers)) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'FOREIGN' -CleanupAuthority 'NONE' -Reason 'COMMAND_LINE_MISMATCH' -RelevantCount 1 -ForeignCount 1
    }

    return ConvertTo-PnccProcessEvidenceResult -Status 'OWNED' -CleanupAuthority 'OWNED_PROCESS_ONLY' -Reason 'EXACT_IDENTITY_MATCH' -RelevantCount 1 -OwnedCount 1 -OwnedProcessIds @($expectedProcessId)
}

function Test-PnccProcessBaseline {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$ObservedProcesses,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$ManagedRules
    )

    if ($ManagedRules.Count -eq 0) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'BLOCKED_AMBIGUOUS' -CleanupAuthority 'NONE' -Reason 'MANAGED_RULE_SET_EMPTY' -AmbiguousCount 1
    }

    foreach ($rule in $ManagedRules) {
        if (-not (Test-PnccManagedRule -Rule $rule)) {
            return ConvertTo-PnccProcessEvidenceResult -Status 'BLOCKED_AMBIGUOUS' -CleanupAuthority 'NONE' -Reason 'MANAGED_RULE_INCOMPLETE' -AmbiguousCount 1
        }
    }

    $relevantCount = 0
    $ownedCount = 0
    $foreignCount = 0
    $ambiguousCount = 0
    $ownedIds = New-Object System.Collections.ArrayList

    foreach ($observed in $ObservedProcesses) {
        $observedName = [string](Get-PnccPropertyValue -InputObject $observed -Name 'ProcessName')
        if ([string]::IsNullOrWhiteSpace($observedName)) {
            $ambiguousCount++
            continue
        }

        $nameRules = @($ManagedRules | Where-Object {
            $ruleName = [string](Get-PnccPropertyValue -InputObject $_ -Name 'ProcessName')
            [string]::Equals($ruleName, $observedName, [StringComparison]::OrdinalIgnoreCase)
        })
        if ($nameRules.Count -eq 0) { continue }

        $relevantCount++
        [int]$observedProcessId = 0
        $processIdValue = Get-PnccPropertyValue -InputObject $observed -Name 'ProcessId'
        $observedPath = ConvertTo-PnccPathKey (Get-PnccPropertyValue -InputObject $observed -Name 'ExecutablePath')
        $observedCommandLine = [string](Get-PnccPropertyValue -InputObject $observed -Name 'CommandLine')

        if (-not [int]::TryParse([string]$processIdValue, [ref]$observedProcessId) -or
            $observedProcessId -le 0 -or
            [string]::IsNullOrWhiteSpace($observedPath) -or
            [string]::IsNullOrWhiteSpace($observedCommandLine)) {
            $ambiguousCount++
            continue
        }

        $matchedManagedRule = $false
        foreach ($rule in $nameRules) {
            $rulePath = ConvertTo-PnccPathKey (Get-PnccPropertyValue -InputObject $rule -Name 'ExecutablePath')
            $ruleMarkers = @(Get-PnccPropertyValue -InputObject $rule -Name 'CommandLineMarkers')
            if ($observedPath -eq $rulePath -and (Test-PnccCommandMarker -Text $observedCommandLine -Markers $ruleMarkers)) {
                $matchedManagedRule = $true
                break
            }
        }

        if ($matchedManagedRule) {
            $ownedCount++
            [void]$ownedIds.Add($observedProcessId)
        }
        else {
            $foreignCount++
        }
    }

    if ($ambiguousCount -gt 0) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'BLOCKED_AMBIGUOUS' -CleanupAuthority 'NONE' -Reason 'AMBIGUOUS_PROCESS_PRESENT' -RelevantCount $relevantCount -OwnedCount $ownedCount -ForeignCount $foreignCount -AmbiguousCount $ambiguousCount -OwnedProcessIds @($ownedIds)
    }
    if ($foreignCount -gt 0) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'DIRTY_FOREIGN' -CleanupAuthority 'NONE' -Reason 'FOREIGN_PROCESS_PRESENT' -RelevantCount $relevantCount -OwnedCount $ownedCount -ForeignCount $foreignCount -OwnedProcessIds @($ownedIds)
    }
    if ($ownedCount -gt 0) {
        return ConvertTo-PnccProcessEvidenceResult -Status 'DIRTY_OWNED' -CleanupAuthority 'OWNED_PROCESS_ONLY' -Reason 'OWNED_PROCESS_PRESENT' -RelevantCount $relevantCount -OwnedCount $ownedCount -OwnedProcessIds @($ownedIds)
    }

    return ConvertTo-PnccProcessEvidenceResult -Status 'CLEAN' -CleanupAuthority 'NONE' -Reason 'BASELINE_CLEAN'
}

Export-ModuleMember -Function Resolve-PnccPidOwnership, Test-PnccProcessBaseline
