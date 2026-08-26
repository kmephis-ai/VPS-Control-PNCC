Set-StrictMode -Version 3.0

$script:AllowedEvidenceStates = @('PASS', 'FAIL', 'UNKNOWN')
$script:RequiredEvidenceKeys = @(
    'SchemaVersion',
    'ValidatorSelfCheck',
    'HarnessOrchestration',
    'EnvironmentBaseline',
    'ProductExecutionStarted',
    'ProductInvariant',
    'EvidenceCoherent'
)

function ConvertTo-PnccClassificationResult {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('CLASSIFIED', 'NO_DEFECT', 'BLOCKED_UNCLASSIFIED')]
        [string]$Status,

        [AllowNull()]
        [ValidateSet('VALIDATOR_DEFECT', 'HARNESS_DEFECT', 'ENVIRONMENT_OR_BASELINE_BLOCKER', 'PRODUCT_DEFECT')]
        [string]$FailureClass,

        [Parameter(Mandatory = $true)]
        [ValidateSet('VALIDATOR_ONLY', 'HARNESS_ONLY', 'ENVIRONMENT_OR_EVIDENCE_ONLY', 'PRODUCT_ONLY', 'NONE')]
        [string]$MutationAuthority,

        [Parameter(Mandatory = $true)]
        [ValidateNotNullOrEmpty()]
        [string]$Reason
    )

    [pscustomobject][ordered]@{
        SchemaVersion      = 1
        Status             = $Status
        FailureClass       = $FailureClass
        MutationAuthority  = $MutationAuthority
        Reason             = $Reason
    }
}

function Test-PnccFailureEvidenceContract {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$EvidenceFacts
    )

    $actualKeys = @($EvidenceFacts.Keys | ForEach-Object { [string]$_ } | Sort-Object)
    $requiredKeys = @($script:RequiredEvidenceKeys | Sort-Object)

    if (($actualKeys -join '|') -ne ($requiredKeys -join '|')) {
        throw "FAILURE_EVIDENCE_CONTRACT_INVALID: expected exactly [$($requiredKeys -join ',')], got [$($actualKeys -join ',')]"
    }

    if ($EvidenceFacts.SchemaVersion -ne 1) {
        throw 'FAILURE_EVIDENCE_SCHEMA_VERSION_INVALID'
    }

    foreach ($name in @('ValidatorSelfCheck', 'HarnessOrchestration', 'EnvironmentBaseline', 'ProductInvariant')) {
        $value = [string]$EvidenceFacts[$name]
        if ($script:AllowedEvidenceStates -notcontains $value) {
            throw "FAILURE_EVIDENCE_STATE_INVALID:$name"
        }
    }

    if (($null -ne $EvidenceFacts.ProductExecutionStarted) -and ($EvidenceFacts.ProductExecutionStarted -isnot [bool])) {
        throw 'FAILURE_EVIDENCE_PRODUCT_EXECUTION_INVALID'
    }

    if ($EvidenceFacts.EvidenceCoherent -isnot [bool]) {
        throw 'FAILURE_EVIDENCE_COHERENCE_INVALID'
    }
}

function Resolve-PnccFailureClassification {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$EvidenceFacts
    )

    Test-PnccFailureEvidenceContract -EvidenceFacts $EvidenceFacts

    if (-not $EvidenceFacts.EvidenceCoherent) {
        return ConvertTo-PnccClassificationResult -Status 'BLOCKED_UNCLASSIFIED' -FailureClass $null -MutationAuthority 'NONE' -Reason 'EVIDENCE_CONTRADICTORY'
    }

    if ($EvidenceFacts.ValidatorSelfCheck -eq 'UNKNOWN') {
        return ConvertTo-PnccClassificationResult -Status 'BLOCKED_UNCLASSIFIED' -FailureClass $null -MutationAuthority 'NONE' -Reason 'VALIDATOR_STATE_UNKNOWN'
    }
    if ($EvidenceFacts.ValidatorSelfCheck -eq 'FAIL') {
        return ConvertTo-PnccClassificationResult -Status 'CLASSIFIED' -FailureClass 'VALIDATOR_DEFECT' -MutationAuthority 'VALIDATOR_ONLY' -Reason 'VALIDATOR_SELF_CHECK_FAILED'
    }

    if ($EvidenceFacts.HarnessOrchestration -eq 'UNKNOWN') {
        return ConvertTo-PnccClassificationResult -Status 'BLOCKED_UNCLASSIFIED' -FailureClass $null -MutationAuthority 'NONE' -Reason 'HARNESS_STATE_UNKNOWN'
    }
    if ($EvidenceFacts.HarnessOrchestration -eq 'FAIL') {
        return ConvertTo-PnccClassificationResult -Status 'CLASSIFIED' -FailureClass 'HARNESS_DEFECT' -MutationAuthority 'HARNESS_ONLY' -Reason 'HARNESS_ORCHESTRATION_FAILED'
    }

    if ($EvidenceFacts.EnvironmentBaseline -eq 'UNKNOWN') {
        return ConvertTo-PnccClassificationResult -Status 'BLOCKED_UNCLASSIFIED' -FailureClass $null -MutationAuthority 'NONE' -Reason 'ENVIRONMENT_STATE_UNKNOWN'
    }
    if ($EvidenceFacts.EnvironmentBaseline -eq 'FAIL') {
        return ConvertTo-PnccClassificationResult -Status 'CLASSIFIED' -FailureClass 'ENVIRONMENT_OR_BASELINE_BLOCKER' -MutationAuthority 'ENVIRONMENT_OR_EVIDENCE_ONLY' -Reason 'ENVIRONMENT_BASELINE_FAILED'
    }

    if ($null -eq $EvidenceFacts.ProductExecutionStarted) {
        return ConvertTo-PnccClassificationResult -Status 'BLOCKED_UNCLASSIFIED' -FailureClass $null -MutationAuthority 'NONE' -Reason 'PRODUCT_EXECUTION_STATE_UNKNOWN'
    }

    if (-not $EvidenceFacts.ProductExecutionStarted) {
        if ($EvidenceFacts.ProductInvariant -eq 'FAIL') {
            return ConvertTo-PnccClassificationResult -Status 'BLOCKED_UNCLASSIFIED' -FailureClass $null -MutationAuthority 'NONE' -Reason 'PRODUCT_FAILURE_WITHOUT_PRODUCT_EXECUTION'
        }
        return ConvertTo-PnccClassificationResult -Status 'NO_DEFECT' -FailureClass $null -MutationAuthority 'NONE' -Reason 'PRODUCT_NOT_EXECUTED'
    }

    if ($EvidenceFacts.ProductInvariant -eq 'UNKNOWN') {
        return ConvertTo-PnccClassificationResult -Status 'BLOCKED_UNCLASSIFIED' -FailureClass $null -MutationAuthority 'NONE' -Reason 'PRODUCT_INVARIANT_UNKNOWN'
    }
    if ($EvidenceFacts.ProductInvariant -eq 'FAIL') {
        return ConvertTo-PnccClassificationResult -Status 'CLASSIFIED' -FailureClass 'PRODUCT_DEFECT' -MutationAuthority 'PRODUCT_ONLY' -Reason 'PRODUCT_INVARIANT_FAILED_AFTER_EXECUTION'
    }

    return ConvertTo-PnccClassificationResult -Status 'NO_DEFECT' -FailureClass $null -MutationAuthority 'NONE' -Reason 'NO_FAILURE_EVIDENCE'
}

Export-ModuleMember -Function Resolve-PnccFailureClassification
