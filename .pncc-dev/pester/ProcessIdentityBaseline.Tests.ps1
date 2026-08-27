Set-StrictMode -Version 3.0

BeforeAll {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $modulePath = Join-Path $repoRoot '.pncc-dev\quality\PNCC.ProcessIdentity.psm1'
    $contractPath = Join-Path $repoRoot '.pncc-dev\contracts\process-identity-baseline.json'
    Import-Module -Name $modulePath -Force -ErrorAction Stop
    $processContract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop

    function New-TestExpectedIdentity {
        param(
            [int]$ProcessId = 4120,
            [string]$ProcessName = 'powershell.exe',
            [string]$ExecutablePath = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe',
            [object[]]$CommandLineMarkers = @('PNCC-Watchdog.ps1', '-Action Watchdog'),
            [string]$CreationTimeUtc = '2026-08-27T01:02:03.0000000Z'
        )

        [pscustomobject]@{
            ProcessId = $ProcessId
            ProcessName = $ProcessName
            ExecutablePath = $ExecutablePath
            CommandLineMarkers = [object[]]@($CommandLineMarkers)
            CreationTimeUtc = $CreationTimeUtc
        }
    }

    function New-TestObservedProcess {
        param(
            [int]$ProcessId = 4120,
            [string]$ProcessName = 'powershell.exe',
            [string]$ExecutablePath = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe',
            [string]$CommandLine = 'powershell.exe -NoProfile -File C:\PNCC\PNCC-Watchdog.ps1 -Action Watchdog',
            [string]$CreationTimeUtc = '2026-08-27T01:02:03.0000000Z'
        )

        [pscustomobject]@{
            ProcessId = $ProcessId
            ProcessName = $ProcessName
            ExecutablePath = $ExecutablePath
            CommandLine = $CommandLine
            CreationTimeUtc = $CreationTimeUtc
        }
    }

    function New-TestManagedRule {
        param(
            [string]$Role = 'PRIMARY_WATCHDOG',
            [string]$ProcessName = 'powershell.exe',
            [string]$ExecutablePath = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe',
            [object[]]$CommandLineMarkers = @('PNCC-Watchdog.ps1', '-Action Watchdog')
        )

        [pscustomobject]@{
            Role = $Role
            ProcessName = $ProcessName
            ExecutablePath = $ExecutablePath
            CommandLineMarkers = [object[]]@($CommandLineMarkers)
        }
    }
}

Describe 'PNCC process identity contract' {
    It 'forbids PID-only authority and real runtime mutation' {
        $processContract.SchemaVersion | Should -Be 1
        $processContract.PidAloneAuthoritative | Should -Be $false
        $processContract.RuntimeMutationAuthority | Should -Be $false
        $processContract.Semantics.NoProcessMutation | Should -Be $true
        $processContract.Semantics.HostedCiIsRuntimeTruth | Should -Be $false
    }

    It 'requires complete expected and observed identity dimensions' {
        @($processContract.ExpectedIdentityFields) -join '|' | Should -Be 'ProcessId|ProcessName|ExecutablePath|CommandLineMarkers|CreationTimeUtc'
        @($processContract.ObservedIdentityFields) -join '|' | Should -Be 'ProcessId|ProcessName|ExecutablePath|CommandLine|CreationTimeUtc'
        $processContract.Semantics.PidReuseDetectionRequiresCreationIdentity | Should -Be $true
    }

    It 'pins fail-closed states and cleanup authorities' {
        @($processContract.OwnershipStates) -join '|' | Should -Be 'OWNED|FOREIGN|NOT_RUNNING|BLOCKED_AMBIGUOUS'
        @($processContract.BaselineStates) -join '|' | Should -Be 'CLEAN|DIRTY_OWNED|DIRTY_FOREIGN|BLOCKED_AMBIGUOUS'
        @($processContract.CleanupAuthorities) -join '|' | Should -Be 'NONE|OWNED_PROCESS_ONLY'
        $processContract.ForeignOrAmbiguousCleanupAuthority | Should -Be 'NONE'
    }
}

Describe 'PNCC exact PID ownership evidence' {
    It 'classifies an exact complete identity as owned' {
        $result = Resolve-PnccPidOwnership -ExpectedIdentity (New-TestExpectedIdentity) -ObservedProcesses @((New-TestObservedProcess))
        $result.Status | Should -Be 'OWNED'
        $result.CleanupAuthority | Should -Be 'OWNED_PROCESS_ONLY'
        $result.Reason | Should -Be 'EXACT_IDENTITY_MATCH'
        @($result.OwnedProcessIds) | Should -Be @(4120)
        $result.PerformsProcessMutation | Should -Be $false
    }

    It 'reports not running when the recorded PID is absent' {
        $result = Resolve-PnccPidOwnership -ExpectedIdentity (New-TestExpectedIdentity) -ObservedProcesses @((New-TestObservedProcess -ProcessId 9001))
        $result.Status | Should -Be 'NOT_RUNNING'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'PID_NOT_PRESENT'
    }

    It 'detects PID reuse from creation-time mismatch' {
        $result = Resolve-PnccPidOwnership -ExpectedIdentity (New-TestExpectedIdentity) -ObservedProcesses @((New-TestObservedProcess -CreationTimeUtc '2026-08-27T01:09:00.0000000Z'))
        $result.Status | Should -Be 'FOREIGN'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'PID_REUSED'
    }

    It 'treats executable-path mismatch as foreign' {
        $result = Resolve-PnccPidOwnership -ExpectedIdentity (New-TestExpectedIdentity) -ObservedProcesses @((New-TestObservedProcess -ExecutablePath 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'))
        $result.Status | Should -Be 'FOREIGN'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'EXECUTABLE_PATH_MISMATCH'
    }

    It 'treats process-name mismatch as foreign' {
        $result = Resolve-PnccPidOwnership -ExpectedIdentity (New-TestExpectedIdentity) -ObservedProcesses @((New-TestObservedProcess -ProcessName 'cmd.exe'))
        $result.Status | Should -Be 'FOREIGN'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'PROCESS_NAME_MISMATCH'
    }

    It 'treats missing command markers as foreign' {
        $result = Resolve-PnccPidOwnership -ExpectedIdentity (New-TestExpectedIdentity) -ObservedProcesses @((New-TestObservedProcess -CommandLine 'powershell.exe -NoProfile -File C:\Other\Worker.ps1'))
        $result.Status | Should -Be 'FOREIGN'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'COMMAND_LINE_MISMATCH'
    }

    It 'blocks when observed identity metadata is incomplete' {
        $result = Resolve-PnccPidOwnership -ExpectedIdentity (New-TestExpectedIdentity) -ObservedProcesses @((New-TestObservedProcess -CommandLine ''))
        $result.Status | Should -Be 'BLOCKED_AMBIGUOUS'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'OBSERVED_IDENTITY_INCOMPLETE'
    }

    It 'blocks PID-only expected evidence instead of inferring ownership' {
        $result = Resolve-PnccPidOwnership -ExpectedIdentity ([pscustomobject]@{ ProcessId = 4120 }) -ObservedProcesses @((New-TestObservedProcess))
        $result.Status | Should -Be 'BLOCKED_AMBIGUOUS'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'EXPECTED_IDENTITY_INCOMPLETE'
    }

    It 'blocks duplicate observations for one PID' {
        $observed = @(
            (New-TestObservedProcess),
            (New-TestObservedProcess -ProcessName 'cmd.exe')
        )
        $result = Resolve-PnccPidOwnership -ExpectedIdentity (New-TestExpectedIdentity) -ObservedProcesses $observed
        $result.Status | Should -Be 'BLOCKED_AMBIGUOUS'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.Reason | Should -Be 'DUPLICATE_PID_OBSERVATION'
    }
}

Describe 'PNCC dirty process baseline evidence' {
    It 'classifies an empty observed baseline as clean' {
        $result = Test-PnccProcessBaseline -ObservedProcesses @() -ManagedRules @((New-TestManagedRule))
        $result.Status | Should -Be 'CLEAN'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.RelevantCount | Should -Be 0
    }

    It 'classifies exact managed processes as dirty-owned' {
        $result = Test-PnccProcessBaseline -ObservedProcesses @((New-TestObservedProcess)) -ManagedRules @((New-TestManagedRule))
        $result.Status | Should -Be 'DIRTY_OWNED'
        $result.CleanupAuthority | Should -Be 'OWNED_PROCESS_ONLY'
        $result.OwnedCount | Should -Be 1
        @($result.OwnedProcessIds) | Should -Be @(4120)
    }

    It 'classifies a same-name nonmatching process as dirty-foreign' {
        $foreign = New-TestObservedProcess -CommandLine 'powershell.exe -NoProfile -File C:\Other\Worker.ps1'
        $result = Test-PnccProcessBaseline -ObservedProcesses @($foreign) -ManagedRules @((New-TestManagedRule))
        $result.Status | Should -Be 'DIRTY_FOREIGN'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.ForeignCount | Should -Be 1
    }

    It 'blocks a same-name process with incomplete metadata' {
        $ambiguous = New-TestObservedProcess -CommandLine ''
        $result = Test-PnccProcessBaseline -ObservedProcesses @($ambiguous) -ManagedRules @((New-TestManagedRule))
        $result.Status | Should -Be 'BLOCKED_AMBIGUOUS'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.AmbiguousCount | Should -Be 1
    }

    It 'never grants cleanup authority to a mixed owned and foreign baseline' {
        $observed = @(
            (New-TestObservedProcess -ProcessId 4120),
            (New-TestObservedProcess -ProcessId 4121 -CommandLine 'powershell.exe -NoProfile -File C:\Other\Worker.ps1')
        )
        $result = Test-PnccProcessBaseline -ObservedProcesses $observed -ManagedRules @((New-TestManagedRule))
        $result.Status | Should -Be 'DIRTY_FOREIGN'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.OwnedCount | Should -Be 1
        $result.ForeignCount | Should -Be 1
    }

    It 'never grants cleanup authority to a mixed owned and ambiguous baseline' {
        $observed = @(
            (New-TestObservedProcess -ProcessId 4120),
            (New-TestObservedProcess -ProcessId 4121 -CommandLine '')
        )
        $result = Test-PnccProcessBaseline -ObservedProcesses $observed -ManagedRules @((New-TestManagedRule))
        $result.Status | Should -Be 'BLOCKED_AMBIGUOUS'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.OwnedCount | Should -Be 1
        $result.AmbiguousCount | Should -Be 1
    }

    It 'ignores unrelated process names rather than treating them as managed' {
        $unrelated = New-TestObservedProcess -ProcessId 7000 -ProcessName 'notepad.exe' -ExecutablePath 'C:\Windows\System32\notepad.exe' -CommandLine 'notepad.exe C:\Temp\notes.txt'
        $result = Test-PnccProcessBaseline -ObservedProcesses @($unrelated) -ManagedRules @((New-TestManagedRule))
        $result.Status | Should -Be 'CLEAN'
        $result.CleanupAuthority | Should -Be 'NONE'
        $result.RelevantCount | Should -Be 0
    }
}
