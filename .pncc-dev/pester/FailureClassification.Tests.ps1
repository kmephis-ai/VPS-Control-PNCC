Set-StrictMode -Version 3.0

BeforeAll {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $modulePath = Join-Path $repoRoot '.pncc-dev\quality\PNCC.FailureClassification.psm1'
    Import-Module -Name $modulePath -Force -ErrorAction Stop

    function New-TestEvidence {
        param(
            [string]$ValidatorSelfCheck = 'PASS',
            [string]$HarnessOrchestration = 'PASS',
            [string]$EnvironmentBaseline = 'PASS',
            [AllowNull()][object]$ProductExecutionStarted = $true,
            [string]$ProductInvariant = 'PASS',
            [bool]$EvidenceCoherent = $true
        )

        @{
            SchemaVersion            = 1
            ValidatorSelfCheck       = $ValidatorSelfCheck
            HarnessOrchestration     = $HarnessOrchestration
            EnvironmentBaseline      = $EnvironmentBaseline
            ProductExecutionStarted  = $ProductExecutionStarted
            ProductInvariant         = $ProductInvariant
            EvidenceCoherent         = $EvidenceCoherent
        }
    }
}

Describe 'PNCC fail-closed failure classification' {
    It 'classifies validator defect before any downstream mutation class' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence -ValidatorSelfCheck 'FAIL' -HarnessOrchestration 'FAIL' -EnvironmentBaseline 'FAIL' -ProductInvariant 'FAIL')
        $result.Status | Should -Be 'CLASSIFIED'
        $result.FailureClass | Should -Be 'VALIDATOR_DEFECT'
        $result.MutationAuthority | Should -Be 'VALIDATOR_ONLY'
    }

    It 'classifies harness defect only after validator self-check passes' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence -HarnessOrchestration 'FAIL')
        $result.FailureClass | Should -Be 'HARNESS_DEFECT'
        $result.MutationAuthority | Should -Be 'HARNESS_ONLY'
    }

    It 'classifies environment blocker only after validator and harness pass' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence -EnvironmentBaseline 'FAIL')
        $result.FailureClass | Should -Be 'ENVIRONMENT_OR_BASELINE_BLOCKER'
        $result.MutationAuthority | Should -Be 'ENVIRONMENT_OR_EVIDENCE_ONLY'
    }

    It 'classifies product defect only after product execution and invariant failure are proven' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence -ProductExecutionStarted $true -ProductInvariant 'FAIL')
        $result.Status | Should -Be 'CLASSIFIED'
        $result.FailureClass | Should -Be 'PRODUCT_DEFECT'
        $result.MutationAuthority | Should -Be 'PRODUCT_ONLY'
    }

    It 'refuses product defect when product execution did not start' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence -ProductExecutionStarted $false -ProductInvariant 'FAIL')
        $result.Status | Should -Be 'BLOCKED_UNCLASSIFIED'
        $result.FailureClass | Should -BeNullOrEmpty
        $result.MutationAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'PRODUCT_FAILURE_WITHOUT_PRODUCT_EXECUTION'
    }

    It 'refuses downstream classification when validator state is unknown' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence -ValidatorSelfCheck 'UNKNOWN' -HarnessOrchestration 'FAIL')
        $result.Status | Should -Be 'BLOCKED_UNCLASSIFIED'
        $result.FailureClass | Should -BeNullOrEmpty
        $result.MutationAuthority | Should -Be 'NONE'
    }

    It 'refuses classification when evidence is contradictory' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence -EvidenceCoherent $false -ProductInvariant 'FAIL')
        $result.Status | Should -Be 'BLOCKED_UNCLASSIFIED'
        $result.MutationAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'EVIDENCE_CONTRADICTORY'
    }

    It 'returns no defect when all evidence passes' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence)
        $result.Status | Should -Be 'NO_DEFECT'
        $result.FailureClass | Should -BeNullOrEmpty
        $result.MutationAuthority | Should -Be 'NONE'
    }

    It 'returns no defect when product did not execute and no failure was claimed' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence -ProductExecutionStarted $false -ProductInvariant 'UNKNOWN')
        $result.Status | Should -Be 'NO_DEFECT'
        $result.MutationAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'PRODUCT_NOT_EXECUTED'
    }

    It 'blocks when product execution state is unknown' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence -ProductExecutionStarted $null)
        $result.Status | Should -Be 'BLOCKED_UNCLASSIFIED'
        $result.MutationAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'PRODUCT_EXECUTION_STATE_UNKNOWN'
    }

    It 'blocks when executed product invariant state is unknown' {
        $result = Resolve-PnccFailureClassification -EvidenceFacts (New-TestEvidence -ProductInvariant 'UNKNOWN')
        $result.Status | Should -Be 'BLOCKED_UNCLASSIFIED'
        $result.MutationAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'PRODUCT_INVARIANT_UNKNOWN'
    }

    It 'rejects evidence with unknown fields instead of ignoring them' {
        $evidence = New-TestEvidence
        $evidence.Unexpected = 'value'
        { Resolve-PnccFailureClassification -EvidenceFacts $evidence } | Should -Throw '*FAILURE_EVIDENCE_CONTRACT_INVALID*'
    }

    It 'rejects evidence with missing required fields' {
        $evidence = New-TestEvidence
        $evidence.Remove('EnvironmentBaseline')
        { Resolve-PnccFailureClassification -EvidenceFacts $evidence } | Should -Throw '*FAILURE_EVIDENCE_CONTRACT_INVALID*'
    }
}
