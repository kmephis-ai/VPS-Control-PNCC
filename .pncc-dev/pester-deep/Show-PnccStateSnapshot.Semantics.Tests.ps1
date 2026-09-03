#requires -Version 5.1

Describe 'PIPE-WU-164 unified read-only State Snapshot CLI semantics' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $showPath = Join-Path $repoRoot 'tools\cli\Show-PnccStateSnapshot.ps1'
        $formatPath = Join-Path $repoRoot 'tools\cli\Format-PnccStateSnapshot.ps1'
        if (-not (Test-Path -LiteralPath $showPath -PathType Leaf)) { throw "Show CLI not found: $showPath" }
        if (-not (Test-Path -LiteralPath $formatPath -PathType Leaf)) { throw "Formatter not found: $formatPath" }

        function New-Wu164Fixture {
            param([string]$Name,[string]$RoutingTunnelId='PRIMARY_AUTO')
            $path = Join-Path $TestDrive ($Name + '.json')
            [pscustomobject]@{
                ModuleNames = @('OpenAI')
                CapturedAt = '2026-09-03T04:00:00Z'
                OverallState = 'HEALTHY'
                RuntimeAgeSeconds = 42
                PrimarySocksListening = $true
                ReserveSocksListening = $true
                RoutingTunnelId = $RoutingTunnelId
                LastKnownGoodPresent = $true
                Config = [pscustomobject]@{ OpenAI = 'AUTO' }
                Runtime = [pscustomobject]@{
                    Effective = [pscustomobject]@{ OpenAI = 'VPS' }
                    Reason = [pscustomobject]@{ OpenAI = 'AUTO_FAILOVER' }
                    Health = [pscustomobject]@{ OpenAI = 'HEALTHY' }
                    Metrics = [pscustomobject]@{ OpenAI = [pscustomobject]@{ LatencyMs = 123; FailureClass = $null } }
                }
                Watchdog = [pscustomobject]@{ State='RUNNING'; Pid=1234; HeartbeatAge=5 }
                ProxifierStatus = [pscustomobject]@{ Running=$true; Pid=4321; Text='OK' }
            } | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $path -Encoding UTF8
            return $path
        }
    }

    It 'renders Russian status directly from state input without creating a temporary snapshot file' {
        $inputPath = New-Wu164Fixture -Name 'text'
        $before = @((Get-ChildItem -LiteralPath $TestDrive -File).Name | Sort-Object)
        $lines = @(& $showPath -InputPath $inputPath)
        $after = @((Get-ChildItem -LiteralPath $TestDrive -File).Name | Sort-Object)

        ($lines -join "`n") | Should -Match 'PNCC — состояние'
        ($lines -join "`n") | Should -Match 'PRIMARY_AUTO 127\.0\.0\.1:1081 \| lifecycle=AUTO'
        ($lines -join "`n") | Should -Match 'RESERVE_MANUAL 127\.0\.0\.1:1080 \| lifecycle=MANUAL_ONLY'
        ($lines -join "`n") | Should -Match 'OpenAI .* эффективно=VPS .* AUTO_FAILOVER'
        $after | Should -Be $before
    }

    It 'emits the exact read-only machine snapshot contract with -Json' {
        $inputPath = New-Wu164Fixture -Name 'json' -RoutingTunnelId 'RESERVE_MANUAL'
        $raw = [string](& $showPath -InputPath $inputPath -Json -JsonDepth 16)
        $snapshot = $raw | ConvertFrom-Json

        $snapshot.SchemaVersion | Should -Be 1
        $snapshot.Contract | Should -Be 'PNCC_STATE_SNAPSHOT'
        $snapshot.ReadOnly | Should -BeTrue
        $snapshot.SecretsIncluded | Should -BeFalse
        $snapshot.RoutingTunnelId | Should -Be 'RESERVE_MANUAL'
        @($snapshot.Tunnels | Where-Object Id -eq 'PRIMARY_AUTO')[0].Port | Should -Be 1081
        @($snapshot.Tunnels | Where-Object Id -eq 'PRIMARY_AUTO')[0].Lifecycle | Should -Be 'AUTO'
        @($snapshot.Tunnels | Where-Object Id -eq 'RESERVE_MANUAL')[0].Port | Should -Be 1080
        @($snapshot.Tunnels | Where-Object Id -eq 'RESERVE_MANUAL')[0].Lifecycle | Should -Be 'MANUAL_ONLY'
        @($snapshot.Tunnels | Where-Object Id -eq 'RESERVE_MANUAL')[0].AutomationMayManageLifecycle | Should -BeFalse
    }

    It 'accepts an in-memory snapshot JSON in the formatter without weakening validation' {
        $inputPath = New-Wu164Fixture -Name 'memory'
        $getPath = Join-Path (Split-Path -Parent $showPath) 'Get-PnccStateSnapshot.ps1'
        $snapshotJson = [string](& $getPath -InputPath $inputPath -JsonDepth 16)
        $text = @(& $formatPath -SnapshotJson $snapshotJson) -join "`n"
        $text | Should -Match 'Общее состояние: HEALTHY'

        $invalid = '{"SchemaVersion":1,"Contract":"NOT_PNCC","ReadOnly":true,"SecretsIncluded":false}'
        { & $formatPath -SnapshotJson $invalid } | Should -Throw '*PNCC_STATE_SNAPSHOT_CONTRACT_INVALID*'
    }
}
