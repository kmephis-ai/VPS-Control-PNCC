#requires -Version 5.1

Describe 'PIPE-WU-172 Status Center reserve-routing ControlState consistency' {
    BeforeAll {
        $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        . (Join-Path $repoRoot 'src\windows-v7\modules\V7-StatusCenter.ps1')

        function New-HealthyStatusInputs {
            $runtime = [pscustomobject]@{
                Health = [pscustomobject]@{ OpenAI = 'HEALTHY' }
                Effective = [pscustomobject]@{ OpenAI = 'DIRECT' }
            }
            $watchdog = [pscustomobject]@{ State = 'ON' }
            $proxifier = [pscustomobject]@{ Running = $true }
            $storage = [pscustomobject]@{ Ok = $true; Issues = @() }
            $consistency = [pscustomobject]@{
                Ok = $true
                Summary = [pscustomobject]@{ Passed=1; Checks=1; Errors=0; Warnings=0 }
            }
            [pscustomobject]@{
                Runtime=$runtime; Watchdog=$watchdog; Proxifier=$proxifier; Storage=$storage; Consistency=$consistency
            }
        }

        function New-Tunnels([bool]$ReserveListening) {
            @(
                [pscustomobject]@{ Id='PRIMARY_AUTO'; Listening=$true },
                [pscustomobject]@{ Id='RESERVE_MANUAL'; Listening=$ReserveListening }
            )
        }
    }

    It 'keeps healthy PRIMARY_AUTO model GOOD when reserve is OFF' {
        $i = New-HealthyStatusInputs
        $m = Get-V7StatusCenterModel -Runtime $i.Runtime -Watchdog $i.Watchdog -SocksUp $true -ProxifierStatus $i.Proxifier -StorageHealth $i.Storage -ModuleNames @('OpenAI') -OverallState 'HEALTHY' -RuntimeAgeSeconds 10 -Consistency $i.Consistency -Tunnels (New-Tunnels $false) -RoutingTunnelId 'PRIMARY_AUTO'
        $m.ControlState | Should -Be 'GOOD'
        (@($m.Nodes | Where-Object Id -eq 'DEPENDENCIES')[0].State) | Should -Be 'GOOD'
        (@($m.Nodes | Where-Object Id -eq 'TUNNEL_RESERVE')[0].State) | Should -Be 'NEUTRAL'
    }

    It 'marks top-level ControlState BAD when unavailable RESERVE_MANUAL is selected' {
        $i = New-HealthyStatusInputs
        $m = Get-V7StatusCenterModel -Runtime $i.Runtime -Watchdog $i.Watchdog -SocksUp $true -ProxifierStatus $i.Proxifier -StorageHealth $i.Storage -ModuleNames @('OpenAI') -OverallState 'HEALTHY' -RuntimeAgeSeconds 10 -Consistency $i.Consistency -Tunnels (New-Tunnels $false) -RoutingTunnelId 'RESERVE_MANUAL'
        $dep = @($m.Nodes | Where-Object Id -eq 'DEPENDENCIES')[0]
        $dep.State | Should -Be 'BAD'
        $dep.Detail | Should -Match 'RESERVE_MANUAL/1080'
        $m.ControlState | Should -Be 'BAD'
    }

    It 'does not mark selected available RESERVE_MANUAL as BAD' {
        $i = New-HealthyStatusInputs
        $m = Get-V7StatusCenterModel -Runtime $i.Runtime -Watchdog $i.Watchdog -SocksUp $true -ProxifierStatus $i.Proxifier -StorageHealth $i.Storage -ModuleNames @('OpenAI') -OverallState 'HEALTHY' -RuntimeAgeSeconds 10 -Consistency $i.Consistency -Tunnels (New-Tunnels $true) -RoutingTunnelId 'RESERVE_MANUAL'
        (@($m.Nodes | Where-Object Id -eq 'DEPENDENCIES')[0].State) | Should -Be 'GOOD'
        (@($m.Nodes | Where-Object Id -eq 'TUNNEL_RESERVE')[0].State) | Should -Be 'GOOD'
        $m.ControlState | Should -Be 'GOOD'
    }

    It 'computes ControlState after the manual reserve fail-closed dependency branch' {
        $modulePath = Join-Path $repoRoot 'src\windows-v7\modules\V7-StatusCenter.ps1'
        $text = Get-Content -LiteralPath $modulePath -Raw -Encoding UTF8
        $reserveIndex = $text.IndexOf("if(`$RoutingTunnelId -eq 'RESERVE_MANUAL'")
        $controlIndex = $text.IndexOf('$controlStates=@(')
        $reserveIndex | Should -BeGreaterThan -1
        $controlIndex | Should -BeGreaterThan $reserveIndex
    }
}
