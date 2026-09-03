#requires -Version 5.1

Describe 'PIPE-WU-162 CLI State Snapshot semantic qualification' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $cliPath = Join-Path $repoRoot 'tools\cli\Get-PnccStateSnapshot.ps1'
        if (-not (Test-Path -LiteralPath $cliPath -PathType Leaf)) { throw "CLI not found: $cliPath" }

        function Invoke-PnccSnapshotCliFixture {
            param(
                [Parameter(Mandatory=$true)][string]$Name,
                [Parameter(Mandatory=$true)]$Payload
            )
            $inputPath = Join-Path $TestDrive ($Name + '.json')
            $Payload | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $inputPath -Encoding UTF8
            $raw = & $cliPath -InputPath $inputPath -JsonDepth 16
            if ($LASTEXITCODE -ne 0) { throw "CLI failed for fixture $Name with exit code $LASTEXITCODE" }
            return ($raw | ConvertFrom-Json)
        }
    }

    It 'emits a read-only empty snapshot with exact dual-tunnel invariants and null runtime freshness' {
        $snapshot = Invoke-PnccSnapshotCliFixture -Name 'empty' -Payload ([pscustomobject]@{
            ModuleNames = @()
            CapturedAt = '2026-09-03T00:00:00Z'
        })

        $snapshot.SchemaVersion | Should -Be 1
        $snapshot.Contract | Should -Be 'PNCC_STATE_SNAPSHOT'
        $snapshot.ReadOnly | Should -BeTrue
        $snapshot.SecretsIncluded | Should -BeFalse
        @($snapshot.Modules).Count | Should -Be 0
        $snapshot.RuntimeEvidence.Present | Should -BeFalse
        $snapshot.RuntimeEvidence.AgeSeconds | Should -Be -1
        $snapshot.RuntimeEvidence.Fresh | Should -BeNullOrEmpty
        @($snapshot.Tunnels).Count | Should -Be 2

        $primary = @($snapshot.Tunnels | Where-Object { $_.Id -eq 'PRIMARY_AUTO' })
        $reserve = @($snapshot.Tunnels | Where-Object { $_.Id -eq 'RESERVE_MANUAL' })
        $primary.Count | Should -Be 1
        $primary[0].Host | Should -Be '127.0.0.1'
        $primary[0].Port | Should -Be 1081
        $primary[0].Lifecycle | Should -Be 'AUTO'
        $primary[0].AutomationMayManageLifecycle | Should -BeTrue
        $primary[0].SelectedForVpsRules | Should -BeTrue
        $reserve.Count | Should -Be 1
        $reserve[0].Host | Should -Be '127.0.0.1'
        $reserve[0].Port | Should -Be 1080
        $reserve[0].Lifecycle | Should -Be 'MANUAL_ONLY'
        $reserve[0].AutomationMayManageLifecycle | Should -BeFalse
        $reserve[0].SelectedForVpsRules | Should -BeFalse
    }

    It 'maps one module and preserves null metric failure class under PowerShell 5.1 execution' {
        $snapshot = Invoke-PnccSnapshotCliFixture -Name 'single' -Payload ([pscustomobject]@{
            ModuleNames = @('OpenAI')
            CapturedAt = '2026-09-03T00:01:00Z'
            OverallState = 'HEALTHY'
            RuntimeAgeSeconds = 42
            PrimarySocksListening = $true
            ReserveSocksListening = $true
            Config = [pscustomobject]@{ OpenAI = 'AUTO' }
            Runtime = [pscustomobject]@{
                Observed = [pscustomobject]@{ OpenAI = 'DIRECT' }
                Effective = [pscustomobject]@{ OpenAI = 'VPS' }
                Reason = [pscustomobject]@{ OpenAI = 'AUTO_FAILOVER' }
                Health = [pscustomobject]@{ OpenAI = 'HEALTHY' }
                Metrics = [pscustomobject]@{ OpenAI = [pscustomobject]@{ LatencyMs = 123; FailureClass = $null } }
            }
        })

        $snapshot.Overall.State | Should -Be 'HEALTHY'
        $snapshot.RuntimeEvidence.Present | Should -BeTrue
        $snapshot.RuntimeEvidence.AgeSeconds | Should -Be 42
        $snapshot.RuntimeEvidence.Fresh | Should -BeTrue
        @($snapshot.Modules).Count | Should -Be 1
        $module = @($snapshot.Modules)[0]
        $module.Id | Should -Be 'OpenAI'
        $module.Desired | Should -Be 'AUTO'
        $module.Configured | Should -Be 'AUTO'
        $module.Observed | Should -Be 'DIRECT'
        $module.Effective | Should -Be 'VPS'
        $module.Reason | Should -Be 'AUTO_FAILOVER'
        $module.Health | Should -Be 'HEALTHY'
        $module.LatencyMs | Should -Be 123
        $module.FailureClass | Should -BeNullOrEmpty
        @($snapshot.Tunnels | Where-Object Id -eq 'PRIMARY_AUTO')[0].Listening | Should -BeTrue
        @($snapshot.Tunnels | Where-Object Id -eq 'RESERVE_MANUAL')[0].Listening | Should -BeTrue
    }

    It 'preserves multiple-module ordering and reserve selection without granting reserve lifecycle automation' {
        $snapshot = Invoke-PnccSnapshotCliFixture -Name 'multiple' -Payload ([pscustomobject]@{
            ModuleNames = @('GitHub','Firefox')
            CapturedAt = '2026-09-03T00:02:00Z'
            RoutingTunnelId = 'RESERVE_MANUAL'
            RuntimeAgeSeconds = 301
            Config = [pscustomobject]@{ GitHub = 'DIRECT'; Firefox = 'VPS' }
            Runtime = [pscustomobject]@{
                ObservedState = [pscustomobject]@{ GitHub = 'DIRECT'; Firefox = 'VPS' }
                Effective = [pscustomobject]@{ GitHub = 'DIRECT'; Firefox = 'VPS' }
                DecisionReason = [pscustomobject]@{ GitHub = 'POLICY_DIRECT'; Firefox = 'MANUAL_ROUTE' }
                Health = [pscustomobject]@{ GitHub = 'HEALTHY'; Firefox = 'HEALTHY' }
                Metrics = [pscustomobject]@{
                    GitHub = [pscustomobject]@{ LatencyMs = 17; FailureClass = $null }
                    Firefox = [pscustomobject]@{ LatencyMs = 88; FailureClass = 'NONE' }
                }
            }
        })

        $snapshot.RuntimeEvidence.Fresh | Should -BeFalse
        @($snapshot.Modules).Count | Should -Be 2
        @($snapshot.Modules)[0].Id | Should -Be 'GitHub'
        @($snapshot.Modules)[0].Configured | Should -Be 'DIRECT'
        @($snapshot.Modules)[1].Id | Should -Be 'Firefox'
        @($snapshot.Modules)[1].Configured | Should -Be 'VPS'
        @($snapshot.Modules)[1].Reason | Should -Be 'MANUAL_ROUTE'

        $primary = @($snapshot.Tunnels | Where-Object Id -eq 'PRIMARY_AUTO')[0]
        $reserve = @($snapshot.Tunnels | Where-Object Id -eq 'RESERVE_MANUAL')[0]
        $primary.SelectedForVpsRules | Should -BeFalse
        $primary.AutomationMayManageLifecycle | Should -BeTrue
        $reserve.SelectedForVpsRules | Should -BeTrue
        $reserve.AutomationMayManageLifecycle | Should -BeFalse
        $reserve.Lifecycle | Should -Be 'MANUAL_ONLY'
    }
}
