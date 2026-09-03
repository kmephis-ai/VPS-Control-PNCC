#requires -Version 5.1

Describe 'PIPE-WU-163 Russian State Snapshot formatter semantics' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $formatter = Join-Path $repoRoot 'tools\cli\Format-PnccStateSnapshot.ps1'
        if (-not (Test-Path -LiteralPath $formatter -PathType Leaf)) { throw "Formatter not found: $formatter" }

        function Write-Wu163Fixture {
            param([Parameter(Mandatory=$true)][string]$Name,[Parameter(Mandatory=$true)]$Payload)
            $path = Join-Path $TestDrive ($Name + '.json')
            $Payload | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $path -Encoding UTF8
            return $path
        }
    }

    It 'renders deterministic Russian status and preserves exact tunnel lifecycle distinction' {
        $fixture = [pscustomobject]@{
            SchemaVersion = 1
            Contract = 'PNCC_STATE_SNAPSHOT'
            CapturedAt = '2026-09-03T03:00:00.0000000Z'
            ReadOnly = $true
            SecretsIncluded = $false
            Overall = [pscustomobject]@{ State = 'HEALTHY' }
            RuntimeEvidence = [pscustomobject]@{ Present = $true; AgeSeconds = 42; Fresh = $true }
            RoutingTunnelId = 'PRIMARY_AUTO'
            Tunnels = @(
                [pscustomobject]@{ Id='PRIMARY_AUTO'; Host='127.0.0.1'; Port=1081; Lifecycle='AUTO'; Listening=$true; SelectedForVpsRules=$true; AutomationMayManageLifecycle=$true },
                [pscustomobject]@{ Id='RESERVE_MANUAL'; Host='127.0.0.1'; Port=1080; Lifecycle='MANUAL_ONLY'; Listening=$false; SelectedForVpsRules=$false; AutomationMayManageLifecycle=$false }
            )
            Modules = @(
                [pscustomobject]@{ Id='OpenAI'; Desired='AUTO'; Configured='AUTO'; Observed='DIRECT'; Effective='VPS'; Reason='AUTO_FAILOVER'; Health='HEALTHY'; LatencyMs=123; FailureClass=$null }
            )
            Watchdog = [pscustomobject]@{ State='HEALTHY'; Detail='ok'; Fresh=$true; Pid=1234; HeartbeatAge=5 }
            Proxifier = [pscustomobject]@{ Running=$true; Pid=4321; Text='HEALTHY' }
            LastKnownGood = [pscustomobject]@{ Present=$true }
        }
        $path = Write-Wu163Fixture -Name 'healthy' -Payload $fixture
        $text = @(& $formatter -InputPath $path) -join "`n"

        $text | Should -Match 'PNCC — состояние'
        $text | Should -Match 'Общее состояние: HEALTHY'
        $text | Should -Match 'Runtime: есть=да; возраст=42 с; свежесть=да'
        $text | Should -Match 'PRIMARY_AUTO 127\.0\.0\.1:1081 \| lifecycle=AUTO .* автоуправление lifecycle=да'
        $text | Should -Match 'RESERVE_MANUAL 127\.0\.0\.1:1080 \| lifecycle=MANUAL_ONLY .* автоуправление lifecycle=нет'
        $text | Should -Match 'OpenAI \| желаемое=AUTO \| эффективно=VPS \| здоровье=HEALTHY \| причина=AUTO_FAILOVER \| задержка=123 мс'
        $text | Should -Match 'Watchdog: состояние=HEALTHY; свежесть=да; PID=1234; heartbeat=5'
        $text | Should -Match 'Proxifier: запущен=да; PID=4321; состояние=HEALTHY'
        $text | Should -Match 'Last Known Good: есть=да'
    }

    It 'renders absent runtime and empty modules without inventing values' {
        $fixture = [pscustomobject]@{
            SchemaVersion = 1
            Contract = 'PNCC_STATE_SNAPSHOT'
            CapturedAt = '2026-09-03T03:01:00.0000000Z'
            ReadOnly = $true
            SecretsIncluded = $false
            Overall = [pscustomobject]@{ State = 'UNKNOWN' }
            RuntimeEvidence = [pscustomobject]@{ Present = $false; AgeSeconds = -1; Fresh = $null }
            RoutingTunnelId = 'PRIMARY_AUTO'
            Tunnels = @(
                [pscustomobject]@{ Id='PRIMARY_AUTO'; Host='127.0.0.1'; Port=1081; Lifecycle='AUTO'; Listening=$false; SelectedForVpsRules=$true; AutomationMayManageLifecycle=$true },
                [pscustomobject]@{ Id='RESERVE_MANUAL'; Host='127.0.0.1'; Port=1080; Lifecycle='MANUAL_ONLY'; Listening=$false; SelectedForVpsRules=$false; AutomationMayManageLifecycle=$false }
            )
            Modules = @()
            Watchdog = [pscustomobject]@{ State=$null; Detail=$null; Fresh=$null; Pid=$null; HeartbeatAge=$null }
            Proxifier = [pscustomobject]@{ Running=$null; Pid=$null; Text=$null }
            LastKnownGood = [pscustomobject]@{ Present=$false }
        }
        $path = Write-Wu163Fixture -Name 'empty' -Payload $fixture
        $text = @(& $formatter -InputPath $path) -join "`n"

        $text | Should -Match 'Runtime: есть=нет; возраст=-1 с; свежесть=неизвестно'
        $text | Should -Match 'Модули:\n  нет данных'
        $text | Should -Match 'Watchdog: состояние=нет данных; свежесть=неизвестно; PID=нет данных; heartbeat=нет данных'
        $text | Should -Match 'Proxifier: запущен=неизвестно; PID=нет данных; состояние=нет данных'
        $text | Should -Match 'Last Known Good: есть=нет'
    }

    It 'fails closed for a non-PNCC snapshot contract' {
        $path = Write-Wu163Fixture -Name 'invalid' -Payload ([pscustomobject]@{
            SchemaVersion = 1
            Contract = 'NOT_PNCC_STATE_SNAPSHOT'
            ReadOnly = $true
            SecretsIncluded = $false
        })
        { & $formatter -InputPath $path } | Should -Throw '*PNCC_STATE_SNAPSHOT_CONTRACT_INVALID*'
    }
}
