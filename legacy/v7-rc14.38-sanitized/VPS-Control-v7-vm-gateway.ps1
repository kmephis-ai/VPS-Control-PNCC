#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Install','Remove','Status')][string]$Action = 'Status',
    [Parameter(Mandatory=$true)][string]$InterfaceAlias,
    [Parameter(Mandatory=$true)][string]$ListenAddress,
    [int]$ListenPort = 1081,
    [string]$ConnectAddress = '127.0.0.1',
    [int]$ConnectPort = 1081
)

$ErrorActionPreference = 'Stop'
$FirewallRuleName = "VPS Control V7 - VM SOCKS $ListenAddress`:$ListenPort"

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-ListenAddressOwned {
    $ips = @(Get-NetIPAddress -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 -ErrorAction Stop | ForEach-Object IPAddress)
    return ($ips -contains $ListenAddress)
}

function Get-PortProxyText {
    try { return ((& netsh.exe interface portproxy show v4tov4 2>&1) -join "`n") }
    catch { return '' }
}

function Test-OurMapping {
    $text = Get-PortProxyText
    if (-not $text) { return $false }
    $pattern = '(?m)^\s*' + [regex]::Escape($ListenAddress) + '\s+' + [regex]::Escape([string]$ListenPort) + '\s+' + [regex]::Escape($ConnectAddress) + '\s+' + [regex]::Escape([string]$ConnectPort) + '\s*$'
    return [regex]::IsMatch($text, $pattern)
}

function Test-FilterContains([object]$Value, [string]$Expected) {
    foreach ($item in @($Value)) {
        if ([string]$item -ieq $Expected) { return $true }
    }
    return $false
}

function Get-FirewallState {
    $result = [ordered]@{
        Exists = $false
        Count = 0
        Enabled = $false
        Direction = ''
        Action = ''
        Protocol = ''
        LocalAddress = ''
        LocalPort = ''
        InterfaceAlias = ''
        RemoteAddress = ''
        Healthy = $false
    }
    try {
        $rules = @(Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction SilentlyContinue)
        $result.Count = $rules.Count
        if ($rules.Count -ne 1) { return [pscustomobject]$result }
        $r = $rules[0]
        $result.Exists = $true
        $result.Enabled = ([string]$r.Enabled -eq 'True')
        $result.Direction = [string]$r.Direction
        $result.Action = [string]$r.Action

        $pf = $r | Get-NetFirewallPortFilter -ErrorAction Stop
        $af = $r | Get-NetFirewallAddressFilter -ErrorAction Stop
        $iflt = $r | Get-NetFirewallInterfaceFilter -ErrorAction Stop
        $result.Protocol = [string]$pf.Protocol
        $result.LocalPort = (@($pf.LocalPort) -join ',')
        $result.LocalAddress = (@($af.LocalAddress) -join ',')
        $result.RemoteAddress = (@($af.RemoteAddress) -join ',')
        $result.InterfaceAlias = (@($iflt.InterfaceAlias) -join ',')

        $protocolOk = (([string]$pf.Protocol -ieq 'TCP') -or ([string]$pf.Protocol -eq '6'))
        $portOk = Test-FilterContains $pf.LocalPort ([string]$ListenPort)
        $localAddressOk = Test-FilterContains $af.LocalAddress $ListenAddress
        $remoteOk = Test-FilterContains $af.RemoteAddress 'LocalSubnet'
        $ifaceOk = Test-FilterContains $iflt.InterfaceAlias $InterfaceAlias
        $result.Healthy = ($result.Enabled -and ([string]$r.Direction -ieq 'Inbound') -and ([string]$r.Action -ieq 'Allow') -and $protocolOk -and $portOk -and $localAddressOk -and $remoteOk -and $ifaceOk)
    }
    catch {
        $result.Healthy = $false
    }
    return [pscustomobject]$result
}

function Get-StatusObject {
    $ipOwned = $false
    try { $ipOwned = Test-ListenAddressOwned } catch { }
    $mapping = Test-OurMapping
    $fw = Get-FirewallState
    $socks = $false
    try {
        $client = New-Object Net.Sockets.TcpClient
        $iar = $client.BeginConnect($ConnectAddress, $ConnectPort, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne(300)) { $client.EndConnect($iar); $socks = $true }
        $client.Close()
    } catch { }
    return [pscustomobject]@{
        InterfaceAlias = $InterfaceAlias
        ListenAddress = $ListenAddress
        ListenPort = $ListenPort
        ConnectAddress = $ConnectAddress
        ConnectPort = $ConnectPort
        AddressBelongsToInterface = $ipOwned
        PortProxyInstalled = $mapping
        FirewallRuleInstalled = [bool]$fw.Exists
        FirewallRuleHealthy = [bool]$fw.Healthy
        FirewallRuleCount = [int]$fw.Count
        LocalSocksListening = $socks
        Ready = ($ipOwned -and $mapping -and [bool]$fw.Healthy -and $socks)
        TcpOnly = $true
    }
}

if ($Action -eq 'Status') {
    Get-StatusObject | ConvertTo-Json -Depth 4
    exit 0
}

if (-not (Test-Admin)) { throw 'Для включения/отключения шлюза VM нужны права администратора.' }
if ($ListenAddress -eq '0.0.0.0') { throw 'Привязка к 0.0.0.0 запрещена: выберите конкретный vEthernet IPv4.' }
if ($ListenAddress -eq '127.0.0.1') { throw 'Для VM нужен адрес vEthernet, а не loopback 127.0.0.1.' }

if ($Action -eq 'Install') {
    if (-not (Test-ListenAddressOwned)) { throw "Адрес $ListenAddress не принадлежит интерфейсу $InterfaceAlias." }
    $service = Get-Service iphlpsvc -ErrorAction SilentlyContinue
    if ($service -and $service.Status -ne 'Running') { Start-Service iphlpsvc -ErrorAction Stop }

    $already = Test-OurMapping
    if (-not $already) {
        $occupied = @(Get-NetTCPConnection -LocalAddress $ListenAddress -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue)
        if ($occupied.Count -gt 0) { throw "Порт $ListenAddress`:$ListenPort уже занят другим listener." }
    }

    & netsh.exe interface portproxy delete v4tov4 listenaddress=$ListenAddress listenport=$ListenPort | Out-Null
    & netsh.exe interface portproxy add v4tov4 listenaddress=$ListenAddress listenport=$ListenPort connectaddress=$ConnectAddress connectport=$ConnectPort | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "netsh portproxy add завершился кодом $LASTEXITCODE." }

    Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName $FirewallRuleName -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $ListenAddress -LocalPort $ListenPort -InterfaceAlias $InterfaceAlias -RemoteAddress LocalSubnet -Profile Any -Description 'VPS Control V7: optional TCP/SOCKS5 gateway for the selected Hyper-V virtual network only.' | Out-Null

    $status = Get-StatusObject
    if (-not $status.PortProxyInstalled -or -not $status.FirewallRuleHealthy) { throw 'Шлюз создан не полностью или firewall-правило отличается от ожидаемой безопасной конфигурации.' }
    $status | ConvertTo-Json -Depth 4
    exit 0
}

if ($Action -eq 'Remove') {
    & netsh.exe interface portproxy delete v4tov4 listenaddress=$ListenAddress listenport=$ListenPort | Out-Null
    Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    $status = Get-StatusObject
    if ($status.PortProxyInstalled -or $status.FirewallRuleInstalled) { throw 'Шлюз удалён не полностью; требуется ручная проверка portproxy/firewall.' }
    $status | ConvertTo-Json -Depth 4
    exit 0
}
