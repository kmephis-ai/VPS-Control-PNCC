#requires -Version 5.1
# VPS Control Center dual-tunnel model.
# PRIMARY_AUTO  = 127.0.0.1:1081, automatic lifecycle.
# RESERVE_MANUAL = 127.0.0.1:1080, visible/diagnosed/manual lifecycle only.

function Get-V7TunnelRegistry {
    return @(
        [pscustomobject]@{
            Id='PRIMARY_AUTO';DisplayName='Основной AUTO';HostAddress='127.0.0.1';Port=1081;ProxyId=100;
            LifecycleMode='AUTO';Required=$true;RoutingEligible=$true;
            ManualStart=$true;ManualStop=$true;AutoStart=$true;AutoRecovery=$true;AutoStop=$false
        },
        [pscustomobject]@{
            Id='RESERVE_MANUAL';DisplayName='Резервный ручной';HostAddress='127.0.0.1';Port=1080;ProxyId=101;
            LifecycleMode='MANUAL_ONLY';Required=$false;RoutingEligible=$true;
            ManualStart=$true;ManualStop=$true;AutoStart=$false;AutoRecovery=$false;AutoStop=$false
        }
    )
}

function Get-V7TunnelDefinition([string]$Id) {
    return @(Get-V7TunnelRegistry | Where-Object { [string]$_.Id -eq $Id } | Select-Object -First 1)
}

function Get-V7TunnelLightMatrix {
    $rows=New-Object Collections.ArrayList
    foreach($t in @(Get-V7TunnelRegistry)){
        $listening=$false
        try{
            if(Get-Command Test-TcpListener -ErrorAction SilentlyContinue){
                $listening=[bool](Test-TcpListener ([string]$t.HostAddress) ([int]$t.Port) 180)
            }else{
                $client=New-Object Net.Sockets.TcpClient
                try{
                    $ar=$client.BeginConnect([string]$t.HostAddress,[int]$t.Port,$null,$null)
                    if($ar.AsyncWaitHandle.WaitOne(180,$false)){
                        $client.EndConnect($ar)
                        $listening=[bool]$client.Connected
                    }
                }catch{}finally{try{$client.Close()}catch{}}
            }
        }catch{}
        [void]$rows.Add([pscustomobject]@{
            Id=[string]$t.Id
            DisplayName=[string]$t.DisplayName
            Endpoint=([string]$t.HostAddress+':'+[int]$t.Port)
            Port=[int]$t.Port
            LifecycleMode=[string]$t.LifecycleMode
            Required=[bool]$t.Required
            AutoStart=[bool]$t.AutoStart
            AutoRecovery=[bool]$t.AutoRecovery
            Listening=[bool]$listening
        })
    }
    return @($rows)
}

function Test-V7DualTunnelContractObject($Contract) {
    if(-not $Contract){return $false}
    $primary=@($Contract.Tunnels|Where-Object{[string]$_.Id -eq 'PRIMARY_AUTO'}|Select-Object -First 1)
    $reserve=@($Contract.Tunnels|Where-Object{[string]$_.Id -eq 'RESERVE_MANUAL'}|Select-Object -First 1)
    if($primary.Count -ne 1 -or $reserve.Count -ne 1){return $false}
    return (
        [string]$primary[0].Host -eq '127.0.0.1' -and [int]$primary[0].Port -eq 1081 -and
        [string]$primary[0].LifecycleMode -eq 'AUTO' -and [bool]$primary[0].AutoStart -and [bool]$primary[0].AutoRecovery -and
        [string]$reserve[0].Host -eq '127.0.0.1' -and [int]$reserve[0].Port -eq 1080 -and
        [string]$reserve[0].LifecycleMode -eq 'MANUAL_ONLY' -and
        -not [bool]$reserve[0].AutoStart -and -not [bool]$reserve[0].AutoRecovery -and -not [bool]$reserve[0].AutoStop
    )
}
