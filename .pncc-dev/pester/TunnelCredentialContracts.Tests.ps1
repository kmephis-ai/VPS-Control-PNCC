Set-StrictMode -Version 3.0

BeforeAll {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $fixtureRoot = Join-Path $repoRoot 'legacy\v7-rc14.38-sanitized'
    $contractPath = Join-Path $fixtureRoot 'VPS-Control-v7-TUNNEL-CONTRACT.json'
    $managerPath = Join-Path $fixtureRoot 'VPS-Control-v7-tunnel-manager.ps1'

    $contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    $managerRaw = [IO.File]::ReadAllText($managerPath)

    $primary = @($contract.Tunnels | Where-Object { [string]$_.Id -eq 'PRIMARY_AUTO' })
    $reserve = @($contract.Tunnels | Where-Object { [string]$_.Id -eq 'RESERVE_MANUAL' })
    if ($primary.Count -ne 1 -or $reserve.Count -ne 1) {
        throw 'Tunnel contract must contain exactly one PRIMARY_AUTO and one RESERVE_MANUAL.'
    }
    $primary = $primary[0]
    $reserve = $reserve[0]

    $startMarker = "if(`$Action-eq'StartReserve'){"
    $startIndex = $managerRaw.IndexOf($startMarker)
    if ($startIndex -lt 0) {
        throw 'StartReserve block marker not found.'
    }
    $startReserveTail = $managerRaw.Substring($startIndex)
}

Describe 'PNCC sanitized tunnel and credential safety contract' {
    It 'pins PRIMARY_AUTO as the default and forbids automatic failover to reserve' {
        $contract.DefaultRoutingTunnelId | Should -Be 'PRIMARY_AUTO'
        [bool]$contract.AutomaticRouteFailoverToReserve | Should -BeFalse
    }

    It 'pins the primary automatic tunnel to loopback port 1081' {
        [string]$primary.Host | Should -Be '127.0.0.1'
        [int]$primary.Port | Should -Be 1081
        [string]$primary.LifecycleMode | Should -Be 'AUTO'
        [bool]$primary.Required | Should -BeTrue
        [bool]$primary.AutoStart | Should -BeTrue
        [bool]$primary.AutoRecovery | Should -BeTrue
        [bool]$primary.AutoStop | Should -BeFalse
    }

    It 'pins the reserve manual tunnel to loopback port 1080' {
        [string]$reserve.Host | Should -Be '127.0.0.1'
        [int]$reserve.Port | Should -Be 1080
        [string]$reserve.LifecycleMode | Should -Be 'MANUAL_ONLY'
        [bool]$reserve.Required | Should -BeFalse
        [bool]$reserve.RoutingEligible | Should -BeTrue
    }

    It 'forbids every automatic reserve lifecycle action' {
        [bool]$reserve.AutoStart | Should -BeFalse
        [bool]$reserve.AutoRecovery | Should -BeFalse
        [bool]$reserve.AutoStop | Should -BeFalse
        [bool]$contract.Invariants.ReserveMustNeverBeStartedAutomatically | Should -BeTrue
        [bool]$contract.Invariants.ReserveMustNeverBeStoppedAutomatically | Should -BeTrue
        [bool]$contract.Invariants.ReserveMustNeverBeRecoveredAutomatically | Should -BeTrue
        [bool]$contract.Invariants.PrimaryAutomaticLifecycleMustNotMutateReserve | Should -BeTrue
    }

    It 'keeps reserve adoption from transferring automatic lifecycle authority' {
        [bool]$contract.ReserveManualOwnershipPolicy.ExternallyStartedReserveMayBeAdopted | Should -BeTrue
        [bool]$contract.ReserveManualOwnershipPolicy.AutomaticLifecycleRemainsForbidden | Should -BeTrue
        [bool]$contract.ReserveManualOwnershipPolicy.AdoptionNeverTransfersAutomaticLifecycleAuthority | Should -BeTrue
        [bool]$contract.ReserveManualOwnershipPolicy.ManualStopRequiresProvenReserveOwnership | Should -BeTrue
    }

    It 'requires fail-closed PuTTY host-key trust' {
        [string]$contract.ManagedPuttyHostKeyTrust.MissingPortableTrust | Should -Be 'FAIL_CLOSED'
        [string]$contract.ManagedPuttyHostKeyTrust.RegistryConflict | Should -Be 'FAIL_CLOSED_NO_OVERWRITE'
        [bool]$contract.ManagedPuttyHostKeyTrust.UnknownHostKeyAcceptanceAllowed | Should -BeFalse
        [bool]$contract.ManagedPuttyHostKeyTrust.HostKeyVerificationDisableAllowed | Should -BeFalse
    }

    It 'requires DPAPI at rest and pwfile transport with no plaintext pw fallback' {
        [string]$contract.CredentialTransport.AtRest | Should -Be 'DPAPI'
        [string]$contract.CredentialTransport.PuttyArgument | Should -Be '-pwfile'
        [bool]$contract.CredentialTransport.PlaintextPwArgumentAllowed | Should -BeFalse
        [bool]$contract.CredentialTransport.ConvertToSecureStringAsPlainTextAllowed | Should -BeFalse
    }

    It 'requires creation-time protected local temporary credential storage' {
        [string]$contract.CredentialTransport.TemporaryRoot | Should -Be '%LOCALAPPDATA%\VPS-Control-v6.3\secure-credentials'
        [bool]$contract.CredentialTransport.CloudSyncedTemporaryStorageAllowed | Should -BeFalse
        [string]$contract.CredentialTransport.AclApplication | Should -Be 'FILE_SECURITY_AT_CREATION'
        [bool]$contract.CredentialTransport.SetAclPostCreationAllowed | Should -BeFalse
        [bool]$contract.CredentialTransport.InheritanceDisabled | Should -BeTrue
        @($contract.CredentialTransport.RequiredAccessSids) | Should -Contain 'CURRENT_USER'
        @($contract.CredentialTransport.RequiredAccessSids) | Should -Contain 'SYSTEM'
    }

    It 'keeps tunnel-manager constants aligned to 1080 reserve and 1081 primary' {
        $managerRaw | Should -Match "\`$ReservePort=1080"
        $managerRaw | Should -Match "\`$ReserveId='RESERVE_MANUAL'"
        $managerRaw | Should -Match "\`$PrimaryPort=1081"
    }

    It 'checks trusted host key before decrypting a password or preparing launch arguments' {
        $hostKeyIndex = $managerRaw.IndexOf('Ensure-V7OfficialPuttyHostKeyTrust', $startIndex)
        $passwordIndex = $managerRaw.IndexOf('Get-DpapiPassword', $startIndex)
        $argumentsIndex = $managerRaw.IndexOf("`$args=@('-ssh'", $startIndex)
        $hostKeyIndex | Should -BeGreaterThan $startIndex
        $passwordIndex | Should -BeGreaterThan $hostKeyIndex
        $argumentsIndex | Should -BeGreaterThan $passwordIndex
    }

    It 'constructs the manual reserve credential argument with pwfile and never literal plaintext pw' {
        $startReserveTail | Should -Match "(?i)'-pwfile'\s*,"
        $startReserveTail | Should -Not -Match "(?i)'-pw'\s*,"
        $startReserveTail | Should -Match '(?i)plaintext -pw fallback is forbidden'
    }

    It 'creates the temporary pwfile with creation-time ACL and deletes it in cleanup' {
        $managerRaw | Should -Match '\[IO\.FileMode\]::CreateNew'
        $managerRaw | Should -Match '\.SetAccessRuleProtection\(\$true,\$false\)'
        $managerRaw | Should -Match "S-1-5-18"
        $startReserveTail | Should -Match "(?i)Remove-Item\s+-LiteralPath\s+\`$pwfile"
        [bool]$contract.CredentialTransport.DeleteAfterTunnelIdentityGate | Should -BeTrue
    }
}
